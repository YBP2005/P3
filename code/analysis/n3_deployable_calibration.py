# -*- coding: utf-8 -*-
"""n3_deployable_calibration.py — 【N3】把**部署者真能用的**校准族补进 M.37 的阶梯。

## 为什么写这个脚本
四家评审用不同的话说了同一件事：M.37 的校准阶梯只测了少数几族，而**部署者可用的那几族缺席**。
它们全是**已发布逐项记录上的离线拟合 —— 零新模型调用**。

请求清单（与提出者）：
  #1 **目标域、小样本、免全量标注**（"真实部署中唯一可用的形式"）：在**目标域的一小撮已标注样本**上
     拟合映射，再应用到**未参与拟合的目标域 item** 上；某位评审的具体配方是"**每域拟合 20 张**"。（dsflash, grok47）
  #2 **conformal / 分位覆盖**校准。（dsflash）
  #3 **按 (域 × 契约) 共享仿射 / Platt**。（qwen38max）
  #4 **对数量级仿射**与 **Poisson / 负二项缩放**（计数单元）。（qwen38max）
  #5 **斜率带正下界的仿射**、**单调分段线性**、以及**只含截距**（阴性对照）。（gpt6sol）
  #6 **温度缩放 / 局部核回归**。（gemini38flash）

## 纪律（先复现，再加臂）
  1. **逐字复制** `a39_perknob_rung.py`（36 单元集）与 `perknob_rung_8unit.py`（8 单元集）的
     载入、单元构建、`rho/fit_a/fit_iso/fit_qnt/spearman` 与**协议**（seed 20260923、200 次分割、1/3 留出、
     每 unit 独立 shuffle 且各档共用同一折）；
  2. 先算**原有六臂**并与两件冻结件逐臂比对（36 单元 ↔ `a39_unit_calib_heldout_result.json`、
     8 单元 ↔ `per_unit_affine_heldout_result.json`）；**对不上就退出**，不进入新臂；
  3. 复现通过后才加新臂。

## 两个必须同时报的量（这是本任务的核心判据）
  · **排序保持性**：重建跨度序 vs 全 item 跨度序的 Spearman（论文自己的门槛 ≥0.9）；
  · **幅度可比性**：标定后跨度的**跨单元异质性** `span_p90/span_p10`
    （"压缩跨度"的可操作定义 —— 若这一族真的把幅度压到一个共同尺度，该比值应 →1）
    以及**保留率极散** `max/min(retention)`（论文既有行的口径：1× / 9× / 95× / 898×）。

  ★ 部署者问题的答案形状因此是一个 2×2：**有没有哪一族同时做到
    "幅度异质性显著下降"与"排序 Spearman ≥0.9"**。

## 一族的"可部署性"分四档（逐族标注）
  `nothing` 免校准 ｜ `global` 只需任意一小撮已标注样本（假设可迁移）
  ｜ `per-domain` 需**目标域**的少量已标注样本（评审说的"部署中唯一可用形式"）
  ｜ `per-domain×contract` 还需同契约 ｜ `per-unit` 每个配置各需一小撮已标注样本

用法：
    python -u n3_deployable_calibration.py            # 正式：200 次分割
    python -u n3_deployable_calibration.py --nsplit 5 # 计时用
输出：n3_deployable_calibration_result.json（新文件）+ 屏幕报告
"""
import bisect
import collections
import csv
import glob
import hashlib
import io
import json
import math
import os
import random
import re
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

W = r'<WORKDIR>\PaperB\analysis\work'
ROOT = r'<WORKDIR>\PaperB'
PM = os.path.join(ROOT, 'analysis', 'data', 'pod_mirror')
WW = r'E:\Edu_workplace\work'
B = os.path.join(WW, 'b_harvest_20260917')
FROZEN36 = os.path.join(W, 'a39_unit_calib_heldout_result.json')
FROZEN8 = os.path.join(W, 'per_unit_affine_heldout_result.json')
OUT = os.path.join(W, 'n3_deployable_calibration_result.json')
ANOM, SENT = 1e5, 1234567890
SEED = 20260923
CAL_FRAC = 1 / 3.0
MIN_ITEMS = 20
NSPLIT = 200
for _i, _a in enumerate(sys.argv):
    if _a == '--nsplit':
        NSPLIT = int(sys.argv[_i + 1])

KNOBS = [('K1 detection·threshold τ × input size', 'det·'),
         ('K2 density regression·input scale', 'density·'),
         ('K3 VLM·output contract', 'VLM·output contract'),
         ('K4 VLM·prompt family', 'VLM·prompt family'),
         ('K5 VLM·tiling level', 'VLM·tiling'),
         ('K6 VLM·pixel budget', 'VLM·pixel budget')]
KL = [lab for lab, _ in KNOBS]


def knob_of(name):
    for lab, pref in KNOBS:
        if name.startswith(pref):
            return lab
    return None


# ---------------------------------------------------------------- 域 / 契约 归属
_DOMFIX = {'st': 'st_a', 'visdrone': 'visdrone', 'aitod': 'aitod', 'ucf': 'ucf',
           'st_a': 'st_a', 'coco': 'coco', 'bbbc005': 'bbbc005'}


def dom_arm_of(name):
    """→ (domain, arm)。域用于 #1/#3 的"目标域"分组；arm 用于 #3 的"域 × 契约"。"""
    p = name.split(' / ')
    if name.startswith('VLM·tiling') or name.startswith('VLM·prompt family'):
        return _DOMFIX.get(p[-2].lower(), p[-2].lower()), p[-1].lower()
    if name.startswith('VLM·pixel budget'):
        return _DOMFIX.get(p[-1].lower(), p[-1].lower()), None
    if name.startswith('VLM·output contract'):
        return '(no-domain)', None          # 这两个 unit 是跨域池化的，本身没有域
    if name.startswith('density·official DM-Count'):
        return _DOMFIX.get(p[-1].lower(), p[-1].lower()), None
    if name.startswith('density·CSRNet'):
        return _DOMFIX.get(p[-1].lower(), p[-1].lower()), None
    if name.startswith('det·in-domain/VisDrone'):
        return 'visdrone', None
    if name.startswith('det·zero-shot COCO'):
        return 'coco', None
    if name.startswith('det·in-domain(micro)/BBBC005'):
        return 'bbbc005', None
    return '(unknown)', None


# ---------------------------------------------------------------- 基础工具（逐字复制）
def load(p):
    return list(csv.DictReader(io.open(p, encoding='utf-8-sig', errors='replace')))


def fn(s):
    try:
        return float(s)
    except Exception:
        return None


def unitize(rows, dims, pcol):
    out = collections.defaultdict(dict)
    for r in rows:
        g = fn(r.get('gt')); p = fn(r.get(pcol))
        if g is None or g <= 0 or p is None or p >= ANOM or p == SENT:
            continue
        try:
            key = tuple(str(r[d]).strip() for d in dims)
        except KeyError:
            continue
        out[key][str(r['item']).strip()] = (g, float(p))
    return out


UNITS = {}
SRC = set()


def add_unit(name, bylevel, src):
    lv = sorted(bylevel)
    if len(lv) < 3:
        return
    common = set.intersection(*[set(bylevel[s]) for s in lv])
    if len(common) < MIN_ITEMS:
        return
    UNITS[name] = dict(levels=[(s, bylevel[s]) for s in lv], keys=sorted(common))
    SRC.add(src)


# ================= 一、36 单元集（逐字复制 a39_perknob_rung.py） =================
for lab, path, pcol in (
        ('det·in-domain/VisDrone', os.path.join(PM, 'A', 'det_yolo_ladder_visdrone_det.csv'), 'n_det_person'),
        ('det·zero-shot COCO', os.path.join(PM, 'A', 'det_yolo_ladder_yolo12n.csv'), 'n_det_person'),
        ('det·in-domain(micro)/BBBC005', os.path.join(B, 'bbbc_eval', 'ladder.csv'), 'n_det')):
    if not os.path.exists(path):
        continue
    u = unitize(load(path), ['tau', 'imgsz'], pcol)
    add_unit(lab + ' (full grid)', {k: v for k, v in u.items()}, path)
    for sz in sorted({k[1] for k in u if len(k) > 1}):
        add_unit('%s / tau@%s' % (lab, sz), {k: v for k, v in u.items() if len(k) > 1 and k[1] == sz}, path)

p = os.path.join(WW, 'dm_ladder.csv')
if os.path.exists(p):
    u = unitize(load(p), ['dataset', 'protocol', 'value'], 'pred')
    for ds in sorted({k[0] for k in u}):
        add_unit('density·official DM-Count / %s' % ds, {k: v for k, v in u.items() if k[0] == ds}, p)
for lab, path in (('density·CSRNet', os.path.join(PM, 'A', 'csrsta_ladder_st_a.csv')),
                  ('density·CSRNet', os.path.join(PM, 'A', 'csrucf_ladder_ucf.csv'))):
    if os.path.exists(path):
        u = unitize(load(path), ['protocol', 'value'], 'pred')
        add_unit('%s / %s' % (lab, os.path.basename(path).split('_')[-2]), {k: v for k, v in u.items()}, path)

for mdl in ('ivl', 'q32'):
    for f in sorted(glob.glob(os.path.join(PM, 'res_ctrl__%s' % mdl, 'res_ctrl_*.csv'))):
        ds = os.path.basename(f)[len('res_ctrl_'):-4]
        u = unitize(load(f), ['budget'], 'pred')
        add_unit('VLM·pixel budget / %s / %s' % (mdl, ds), {k: v for k, v in u.items()}, f)

for sub, mdl in (('tile_results', 'Qwen32B'), ('b2__out_32b_ctile', 'Qwen32B(ctile)'),
                 ('b2__out_8b_ctile', 'Qwen8B(ctile)')):
    d = os.path.join(PM, sub)
    if not os.path.isdir(d):
        continue
    groups = collections.defaultdict(dict)
    for f in sorted(os.listdir(d)):
        m = re.match(r'^vlm_([a-z0-9]+)_(base|over|under|[a-z0-9]+)_(whole|tile\d+)\.csv$', f)
        if not m:
            continue
        dom, arm, lvl = m.groups()
        d2 = {}
        for r in load(os.path.join(d, f)):
            g = fn(r.get('gt')); pp = fn(r.get('pred'))
            if g is None or g <= 0 or pp is None or pp >= ANOM or pp == SENT:
                continue
            d2[str(r['item']).strip()] = (g, float(pp))
        groups[(dom, arm)][lvl] = d2
    for (dom, arm), bl in sorted(groups.items()):
        add_unit('VLM·tiling / %s / %s / %s' % (mdl, dom, arm), bl, d)

for mdl, pth in (('ivl', os.path.join(PM, 'b2__out_ivl', 'E1.csv')),
                 ('q32', os.path.join(PM, 'b2__out_q32', 'E1.csv'))):
    if os.path.exists(pth):
        u = unitize(load(pth), ['arm'], 'pred')
        add_unit('VLM·output contract / %s' % mdl, {k: v for k, v in u.items()}, pth)

for sub, mdl in (('dense_prompt_results', 'Qwen32B'), ('ivl_dense_prompt_results', 'IVL')):
    d = os.path.join(PM, sub)
    if not os.path.isdir(d):
        continue
    groups = collections.defaultdict(dict)
    for f in sorted(os.listdir(d)):
        m = re.match(r'^([a-z0-9]+)_(base|over|under)_(V\d+)_([a-z_]+)\.csv$', f)
        if not m:
            continue
        dom, arm, lvl, _ = m.groups()
        d2 = {}
        for r in load(os.path.join(d, f)):
            g = fn(r.get('gt')); pp = fn(r.get('pred'))
            if g is None or g <= 0 or pp is None or pp >= ANOM or pp == SENT:
                continue
            d2[str(r['item']).strip()] = (g, float(pp))
        groups[(dom, arm)][lvl] = d2
    for (dom, arm), bl in sorted(groups.items()):
        add_unit('VLM·prompt family / %s / %s / %s' % (mdl, dom, arm), bl, d)


# ================= 二、8 单元集（逐字复制 perknob_rung_8unit.py，仅用于复现闸门 B） =================
def _kv(rows):
    out = {}
    for r in rows:
        try:
            gt, pr = float(r['gt']), float(r['pred'])
        except (TypeError, ValueError):
            continue
        if pr >= ANOM or gt <= 0:
            continue
        out[str(r['item'])] = (gt, pr)
    return out


def load_csv(p):
    with io.open(p, encoding='utf-8-sig') as f:
        return _kv([r for r in csv.DictReader(f) if '#r' not in str(r.get('item') or '')])


def load_csv_level(p, key, val):
    with io.open(p, encoding='utf-8-sig') as f:
        rows = [r for r in csv.DictReader(f) if '#r' not in str(r.get('item') or '')]
    return _kv([r for r in rows if r.get(key) == val])


L8 = {}


def add8(unit, levels, src):
    keys = None
    for _, d in levels:
        keys = set(d) if keys is None else (keys & set(d))
    keys = sorted(keys)
    if len(levels) >= 3 and keys:
        L8[unit] = dict(levels=levels, keys=keys)
        SRC.add(src)


for mdl in ('q32', 'ivl'):
    for f in sorted(glob.glob(os.path.join(PM, 'res_ctrl__%s' % mdl, 'res_ctrl_*.csv'))):
        ds = os.path.basename(f)[len('res_ctrl_'):-4]
        with io.open(f, encoding='utf-8-sig') as fh:
            buds = sorted(set(r['budget'] for r in csv.DictReader(fh)), key=float)
        add8('pxbudget(res_ctrl) / %s / %s' % (mdl, ds),
             [('budget=%s' % b, load_csv_level(f, 'budget', b)) for b in buds], f)

for ds in ('st_a', 'ucf', 'visdrone'):
    files = sorted(glob.glob(os.path.join(PM, 'tile_results', 'vlm_%s_base_tile*.csv' % ds)))
    if files:
        add8('tiling / %s / base' % ds,
             [(os.path.basename(f).split('tile')[1][0], load_csv(f)) for f in files],
             os.path.join(PM, 'tile_results'))


# ================= 三、工具（逐字复制既有脚本） =================
def rho(pairs, ab=None):
    if ab is not None:
        a, b = ab
        pairs = [(g, a * p + b) for g, p in pairs]
    sg = sum(g for g, _ in pairs)
    return 100.0 * (sum(p for _, p in pairs) - sg) / sg if sg else None


def fit_a(pairs):
    n = len(pairs)
    if n < 2:
        return 1.0, 0.0
    P = [p for _, p in pairs]; G = [g for g, _ in pairs]
    mp, mg = sum(P) / n, sum(G) / n
    spp = sum((x - mp) ** 2 for x in P)
    if spp == 0:
        return 0.0, mg
    a = sum((P[i] - mp) * (G[i] - mg) for i in range(n)) / spp
    return a, mg - a * mp


def fit_iso(pairs):
    from sklearn.isotonic import IsotonicRegression
    ir = IsotonicRegression(out_of_bounds='clip')
    ir.fit([p for _, p in pairs], [g for g, _ in pairs])
    return lambda P: [float(x) for x in ir.predict(P)]


def fit_qnt(pairs):
    cg = sorted(g for g, _ in pairs)
    cp = sorted(p for _, p in pairs)

    def f(P):
        out = []
        for x in P:
            lo, hi = 0, len(cp)
            while lo < hi:
                mid = (lo + hi) // 2
                if cp[mid] < x:
                    lo = mid + 1
                else:
                    hi = mid
            out.append(cg[min(lo, len(cg) - 1)])
        return out
    return f


def spearman(x, y):
    def rank(v):
        s = sorted(range(len(v)), key=lambda i: v[i])
        r = [0.0] * len(v)
        i = 0
        while i < len(s):
            j = i
            while j + 1 < len(s) and v[s[j + 1]] == v[s[i]]:
                j += 1
            avg = (i + j) / 2.0 + 1
            for t in range(i, j + 1):
                r[s[t]] = avg
            i = j + 1
        return r
    ra, rb = rank(x), rank(y)
    n = len(x)
    ma, mb = sum(ra) / n, sum(rb) / n
    num = sum((ra[i] - ma) * (rb[i] - mb) for i in range(n))
    da = sum((ra[i] - ma) ** 2 for i in range(n)) ** 0.5
    db = sum((rb[i] - mb) ** 2 for i in range(n)) ** 0.5
    return num / (da * db) if da and db else float('nan')


def q(v, pp):
    v = sorted(v)
    return v[min(len(v) - 1, max(0, int(round(pp * (len(v) - 1)))))]


def md5(p):
    if os.path.isdir(p):
        h = hashlib.md5()
        for f in sorted(os.listdir(p)):
            h.update(f.encode('utf-8'))
            h.update(hashlib.md5(io.open(os.path.join(p, f), 'rb').read()).hexdigest().encode())
        return h.hexdigest() + ' (dir)'
    return hashlib.md5(io.open(p, 'rb').read()).hexdigest()


# ================= 四、新族（本次要实现的那几族） =================
# 全部返回 f(list_of_pred) -> list_of_calibrated_pred；拟合只用标定折的 (gt, pred) 对。


def mk_affine(pairs):
    a, b = fit_a(pairs)
    return lambda P: [a * x + b for x in P], dict(a=a, b=b)


def mk_log(pairs):
    """#4 对数量级仿射：log(gt+1) = a·log(pred+1) + b，再 exp 回来。"""
    X = [math.log(max(p, 0.0) + 1.0) for _, p in pairs]
    Y = [math.log(max(g, 0.0) + 1.0) for g, _ in pairs]
    n = len(X)
    mx, my = sum(X) / n, sum(Y) / n
    sxx = sum((x - mx) ** 2 for x in X)
    a = (sum((X[i] - mx) * (Y[i] - my) for i in range(n)) / sxx) if sxx else 0.0
    b = my - a * mx
    return (lambda P: [math.exp(a * math.log(max(x, 0.0) + 1.0) + b) - 1.0 for x in P],
            dict(a=a, b=b))


def mk_ps(pairs):
    """#4 Poisson 式**纯缩放**（无截距）：c = Σgt/Σpred，即在标定集上把 ρ 归零的那个 c。"""
    sp = sum(p for _, p in pairs); sg = sum(g for g, _ in pairs)
    c = (sg / sp) if sp else 1.0
    return lambda P: [c * x for x in P], dict(c=c)


def mk_slp(pairs, amin=0.05):
    """#5 斜率带正下界的仿射（下界 0.05，防负斜率）。"""
    a, b = fit_a(pairs)
    a2 = a if a >= amin else amin
    return lambda P: [a2 * x + b for x in P], dict(a_fit=a, a_used=a2, b=b)


def _pava(v):
    """pool-adjacent-violators：把序列变成非降。"""
    w = [1.0] * len(v)
    val = list(v)
    i = 0
    while i < len(val) - 1:
        if val[i] > val[i + 1] + 1e-15:
            tw = w[i] + w[i + 1]
            tv = (val[i] * w[i] + val[i + 1] * w[i + 1]) / tw
            val[i:i + 2] = [tv]
            w[i:i + 2] = [tw]
            if i > 0:
                i -= 1
        else:
            i += 1
    return val


def mk_mono(pairs, K=6):
    """#5 单调**分段线性**映射：分位分箱取箱内中位 → PAVA 强制非降 → 节点线性插值（端点夹住）。"""
    import numpy as np
    n = len(pairs)
    if n < 4:
        return None, None
    P = np.array([p for _, p in pairs], float)
    G = np.array([g for g, _ in pairs], float)
    o = np.argsort(P)
    Ps, Gs = P[o], G[o]
    k = max(2, min(K, n // 2))
    cuts = np.quantile(Ps, np.linspace(0.0, 1.0, k + 1))
    cuts[0] -= 1e-12
    cuts[-1] += 1e-12
    idx = np.clip(np.searchsorted(cuts, Ps, side='right') - 1, 0, k - 1)
    nodes, vals = [], []
    for j in range(k):
        m = (idx == j)
        if not m.any():
            continue
        nodes.append(float(Ps[m].mean()))
        vals.append(float(np.median(Gs[m])))
    if len(nodes) < 2:
        return None, None
    vals = _pava(vals)
    # 节点去重（保严格递增）——分位切点在预测值大量重复时会重合，重合节点会让插值下标越界
    nv = []
    for nn, vv in zip(nodes, vals):
        if nv and nn <= nv[-1][0]:
            nv[-1] = (nv[-1][0], max(nv[-1][1], vv))
            continue
        nv.append((nn, vv))
    if len(nv) < 2:
        return None, None
    nd = [a for a, _ in nv]
    vl = _pava([b for _, b in nv])

    def f(X):
        out = []
        for x in X:
            if x <= nd[0]:
                out.append(vl[0])
            elif x >= nd[-1]:
                out.append(vl[-1])
            else:
                j = max(0, min(bisect.bisect_right(nd, x) - 1, len(nd) - 2))
                x0, x1 = nd[j], nd[j + 1]
                t = (x - x0) / (x1 - x0) if x1 > x0 else 0.0
                out.append(vl[j] + t * (vl[j + 1] - vl[j]))
        return out
    return f, dict(knots=nd, values=vl)


def mk_lkr(pairs, mult=0.30, M=300):
    """#6 局部核回归（Nadaraya–Watson，高斯核，带宽 = 0.30×IQR(pred)）。

    ⚠ 计算纪律：全局档的标定池可达上万对，而高斯核在每个评估点上的权重**只由邻近的标定点决定**
      ⇒ 用**分位等距**抽稀到至多 M=300 个标定点，结果与用全池在双精度下不可区分，
      但把每次求值的代价从 O(n_eval×n_cal) 降到 O(n_eval×M)。抽稀是**确定性的**（不引入随机性）。"""
    import numpy as np
    P = np.array([p for _, p in pairs], float)
    G = np.array([g for g, _ in pairs], float)
    o = np.argsort(P)
    Ps, Gs = P[o], G[o]
    if len(Ps) > M:
        keep = np.unique(np.round(np.linspace(0, len(Ps) - 1, M)).astype(int))
        Ps, Gs = Ps[keep], Gs[keep]
    iqr = float(np.percentile(P, 75) - np.percentile(P, 25))
    bw = mult * iqr
    if bw <= 0:
        sd = float(P.std())
        bw = 0.1 * sd if sd > 0 else 1.0

    def f(X):
        Xa = np.asarray(X, float)
        D = (Xa[:, None] - Ps[None, :]) / bw
        W = np.exp(-0.5 * D * D)
        s = W.sum(1)
        out = np.where(s > 1e-12, (W @ Gs) / np.maximum(s, 1e-12), 0.0)
        bad = s <= 1e-12                      # 权重全零 ⇒ 回退到最近邻（searchsorted，O(log n)）
        if bad.any():
            idx = np.clip(np.searchsorted(Ps, Xa[bad]), 0, len(Ps) - 1)
            idx2 = np.clip(idx - 1, 0, len(Ps) - 1)
            pick = np.where(np.abs(Ps[idx] - Xa[bad]) <= np.abs(Ps[idx2] - Xa[bad]), idx, idx2)
            out[bad] = Gs[pick]
        return [float(v) for v in out]
    return f, dict(bw=bw, n_kernel_points=len(Ps))


def mk_temp(pairs):
    """#6 温度/幂缩放：pred' = A·pred^T，T 走格点、A 对每个 T 取闭式最小二乘。"""
    P = [max(p, 1e-9) for _, p in pairs]
    G = [g for g, _ in pairs]
    best = None
    for i in range(33):
        T = 1.6 * i / 32.0
        base = [x ** T if T > 0 else 1.0 for x in P]
        den = sum(b * b for b in base)
        if den <= 0:
            continue
        A = sum(G[j] * base[j] for j in range(len(G))) / den
        err = sum((A * base[j] - G[j]) ** 2 for j in range(len(G)))
        if best is None or err < best[0]:
            best = (err, T, A)
    T, A = best[1], best[2]
    if T <= 0:
        return lambda X: [A for _ in X], dict(T=T, A=A)
    return lambda X: [A * (max(x, 1e-9) ** T) for x in X], dict(T=T, A=A)


def mk_int(pairs):
    """#5 只含截距（**阴性对照**）：常数映射，把所有跨度压成 0。"""
    m = sum(g for g, _ in pairs) / len(pairs)
    return lambda X: [m for _ in X], dict(m=m)


def mk_psc(pairs):
    """#3/#2 的 Platt 式**单调 S 形**（对二值目标的 Platt 不适用于计数目标；这是最近的良定义点映射）。
    pred' = lo + (hi-lo)·sigmoid(a·z+b)，z = (pred − med)/IQR。
    拟合用 (a,b) 的粗格点 + 给定 (a,b) 时 (lo,hi) 的**闭式最小二乘**（比 least_squares 快两个数量级）。"""
    import numpy as np
    P = np.array([p for _, p in pairs], float)
    G = np.array([g for g, _ in pairs], float)
    if len(P) < 8:
        return None, None
    iqr = float(np.percentile(P, 75) - np.percentile(P, 25))
    if iqr <= 0:
        iqr = float(P.std()) or 1.0
    med = float(np.median(P))
    z = (P - med) / iqr
    best = None
    for a in np.linspace(-4.0, 4.0, 13):
        for b in np.linspace(-4.0, 4.0, 13):
            t = np.clip(a * z + b, -500.0, 500.0)
            s = 1.0 / (1.0 + np.exp(-t))
            A = np.stack([1.0 - s, s], 1)
            try:
                coef, *_ = np.linalg.lstsq(A, G, rcond=None)
            except Exception:
                continue
            err = float(((A @ coef - G) ** 2).sum())
            if best is None or err < best[0]:
                best = (err, float(a), float(b), float(coef[0]), float(coef[1]))
    if best is None:
        return None, None
    _, a, b, lo, hi = best

    def _sig(t):
        if t >= 0:
            return 1.0 / (1.0 + math.exp(-t))
        e = math.exp(t)
        return e / (1.0 + e)

    def f(X):
        return [lo + (hi - lo) * _sig(a * ((x - med) / iqr) + b) for x in X]
    return f, dict(a=a, b=b, lo=lo, hi=hi)


# 族注册：名字 → (拟合器, 需要的最小标定对数)
FAM = {
    'affine': (mk_affine, 2),
    'log': (mk_log, 2),
    'poisson_scale': (mk_ps, 1),
    'slope_floor': (mk_slp, 2),
    'mono_pwl': (mk_mono, 4),
    'kernel': (mk_lkr, 3),
    'temp_power': (mk_temp, 3),
    'intercept_only': (mk_int, 1),
    'platt_sigmoid': (mk_psc, 8),
}

GRAN = ['global', 'per_domain', 'per_dom_arm', 'per_unit']


# ================= 五、跑一套单元集 =================
def run(uname, UNITSET, nsplit, groups_extra, knobfn=None):
    knobfn = knobfn or knob_of
    units = sorted(UNITSET)
    knob = {u: knobfn(u) for u in units}
    grp = collections.defaultdict(list)
    for u in units:
        grp[knob[u]].append(u)
    for u in units:
        seq = [rho([d[k] for k in UNITSET[u]['keys']]) for _, d in UNITSET[u]['levels']]
        UNITSET[u]['span_full'] = max(seq) - min(seq)
    ref = [UNITSET[u]['span_full'] for u in units]

    # 分组（#1 目标域 / #3 域×契约 / S12 的 knob）
    dom = {u: dom_arm_of(u)[0] for u in units}
    darm = {u: (dom_arm_of(u)[0], dom_arm_of(u)[1]) for u in units}
    gd = collections.defaultdict(list)
    gda = collections.defaultdict(list)
    for u in units:
        gd[dom[u]].append(u)
        gda[darm[u]].append(u)

    ARMS = ['C0e', 'Cg', 'C1u', 'C2l', 'ISO', 'QNT', 'Ck', 'SISOk', 'SISOg',
            'Cd', 'Cd20', 'Cd20s', 'Cda']
    for g in GRAN:
        for f in FAM:
            ARMS.append('%s@%s' % (f, g))
    R = {k: [] for k in ARMS}
    Rdom = {k: [] for k in ARMS}
    Rknob = {k: [] for k in ARMS}
    span_post = {u: {k: [] for k in ARMS} for u in units}
    diag = collections.defaultdict(list)

    rng = random.Random(SEED)
    # ★★ 关键纪律：`rng` **只**用于"每 unit 的分割"这一件事，且顺序与参照脚本逐字一致。
    #   #1 的"每配置 20 张"抽稀必须用**另一条**随机流 —— 否则它会推移 rng 的流，
    #   后面 unit 的分割就与参照脚本不同源，复现闸门会失败（而稳的臂看不出来、噪声大的臂看出来）。
    rng_sub = random.Random(SEED + 1)
    for _ in range(nsplit):
        cal, ev = {}, {}
        for u in units:
            ks = list(UNITSET[u]['keys'])
            rng.shuffle(ks)
            nc = max(2, int(round(len(ks) * CAL_FRAC)))
            ck, ek = set(ks[:nc]), set(ks[nc:])
            cal[u] = {lb: [d[k] for k in ck] for lb, d in UNITSET[u]['levels']}
            ev[u] = {lb: [d[k] for k in ek] for lb, d in UNITSET[u]['levels']}
        pack = lambda lst: [x for u in lst for lb in cal[u] for x in cal[u][lb]]
        # ---- 既有六臂 + S12 三臂
        C1 = {u: fit_a(pack([u])) for u in units}
        Cg = fit_a(pack(units))
        SISOg = fit_iso(pack(units))
        Ck = {}; SISOk = {}
        for lab in KL:
            if not grp[lab]:
                continue
            Ck[lab] = fit_a(pack(grp[lab])); SISOk[lab] = fit_iso(pack(grp[lab]))
        # ---- #1 目标域共享仿射（三种标定量）
        Cd = {}; Cd20 = {}; Cd20s = {}
        for d, us in gd.items():
            Cd[d] = fit_a(pack(us))
            sub = []
            for u in us:
                pr = cal[u]
                allp = [x for lb in pr for x in pr[lb]]
                rng_sub.shuffle(allp)
                sub += allp[:min(20, len(allp))]
            Cd20[d] = fit_a(sub) if len(sub) >= 2 else Cd[d]
            allp = pack(us)
            rng_sub.shuffle(allp)
            Cd20s[d] = fit_a(allp[:min(20, len(allp))]) if len(allp) >= 2 else Cd[d]
        # ---- #3 域 × 契约
        Cda = {k: (fit_a(pack(v)) if len(pack(v)) >= 2 else Cg) for k, v in gda.items()}
        # ---- 各族在各粒度上的映射
        MAPS = {}
        for f, (fitter, minn) in FAM.items():
            # global
            pool = pack(units)
            m, _ = fitter(pool) if len(pool) >= minn else (None, None)
            MAPS[('%s@global' % f,)] = m
            # per domain
            for d, us in gd.items():
                pool = pack(us)
                mm, _ = fitter(pool) if len(pool) >= minn else (None, None)
                MAPS[('%s@per_domain' % f, d)] = mm
            # per (domain × arm)
            for k2, us in gda.items():
                pool = pack(us)
                mm, _ = fitter(pool) if len(pool) >= minn else (None, None)
                MAPS[('%s@per_dom_arm' % f, k2)] = mm
            # per unit
            for u in units:
                pool = pack([u])
                mm, _ = fitter(pool) if len(pool) >= minn else (None, None)
                MAPS[('%s@per_unit' % f, u)] = mm

        def apply_map(m, P):
            if m is None:
                return None
            return m(P)

        sp_unit = {k: {} for k in ARMS}
        for u in units:
            v = {k: [] for k in ARMS}
            for lb, _ in UNITSET[u]['levels']:
                e, c = ev[u][lb], cal[u][lb]
                v['C0e'].append(rho(e))
                v['C1u'].append(rho(e, C1[u]))
                v['C2l'].append(rho(e, fit_a(c)))
                v['Cg'].append(rho(e, Cg))
                v['Cd'].append(rho(e, Cd[dom[u]]))
                v['Cd20'].append(rho(e, Cd20[dom[u]]))
                v['Cd20s'].append(rho(e, Cd20s[dom[u]]))
                v['Cda'].append(rho(e, Cda[darm[u]]))
                if Ck.get(knob[u]):
                    v['Ck'].append(rho(e, Ck[knob[u]]))
                    pe = [p for _, p in e]; sg = sum(g for g, _ in e)
                    v['SISOk'].append(100.0 * (sum(SISOk[knob[u]](pe)) - sg) / sg)
                pe = [p for _, p in e]; sg = sum(g for g, _ in e)
                v['ISO'].append(100.0 * (sum(fit_iso(c)(pe)) - sg) / sg)
                v['QNT'].append(100.0 * (sum(fit_qnt(c)(pe)) - sg) / sg)
                v['SISOg'].append(100.0 * (sum(SISOg(pe)) - sg) / sg)
                for f in FAM:
                    for g in GRAN:
                        key = '%s@%s' % (f, g)
                        if g == 'global':
                            m = MAPS[(key,)]
                        elif g == 'per_domain':
                            m = MAPS[(key, dom[u])]
                        elif g == 'per_dom_arm':
                            m = MAPS[(key, darm[u])]
                        else:
                            m = MAPS[(key, u)]
                        out = apply_map(m, pe)
                        if out is None:
                            v[key].append(float('nan'))
                        else:
                            v[key].append(100.0 * (sum(out) - sg) / sg)
            for k in ARMS:
                s = max(v[k]) - min(v[k]) if not any(x != x for x in v[k]) else float('nan')
                sp_unit[k][u] = s
                span_post[u][k].append(s)
            # 逐域 / knob 层面的排序（中位跨度）
            for k in ARMS:
                if len(grp[knob[u]]) >= 1:
                    pass
        for k in ARMS:
            R[k].append(spearman(ref, [sp_unit[k][u] for u in units]))
            _mk = [q([sp_unit[k][u] for u in gd[d]], .5) for d in sorted(gd) if gd[d]]
            _rk = [q([UNITSET[u]['span_full'] for u in gd[d]], .5) for d in sorted(gd) if gd[d]]
            Rdom[k].append(spearman(_rk, _mk) if len(gd) >= 3 else float('nan'))
            _mk = [q([sp_unit[k][u] for u in grp[lab]], .5) for lab in KL if grp[lab]]
            _rk = [q([UNITSET[u]['span_full'] for u in grp[lab]], .5) for lab in KL if grp[lab]]
            Rknob[k].append(spearman(_rk, _mk))

    # 复现闸门由调用方比对
    summary = {}
    for k in ARMS:
        v = [x for x in R[k] if x == x]
        if not v:
            summary[k] = dict(median=float('nan'), p05=float('nan'), p95=float('nan'),
                              frac_ge_090=float('nan'), frac_ge_080=float('nan'),
                              dom_median=q(Rdom[k], .5) if any(x == x for x in Rdom[k]) else float('nan'),
                              knob_median=q(Rknob[k], .5) if any(x == x for x in Rknob[k]) else float('nan'),
                              span_median=float('nan'), span_p10=float('nan'), span_p90=float('nan'),
                              span_p90_over_p10=float('nan'), retention_spread=float('nan'))
            continue
        meds = [q(span_post[u][k], .5) for u in units]
        meds = [x for x in meds if x == x]
        rets = [q(span_post[u][k], .5) / UNITSET[u]['span_full'] for u in units
                if UNITSET[u]['span_full'] > 1e-9 and q(span_post[u][k], .5) == q(span_post[u][k], .5)]
        summary[k] = dict(
            median=q(v, .5), p05=q(v, .05), p95=q(v, .95),
            frac_ge_090=sum(1 for x in v if x >= .9) / len(v),
            frac_ge_080=sum(1 for x in v if x >= .8) / len(v),
            dom_median=q(Rdom[k], .5) if any(x == x for x in Rdom[k]) else float('nan'),
            knob_median=q(Rknob[k], .5) if any(x == x for x in Rknob[k]) else float('nan'),
            span_median=q(meds, .5) if meds else float('nan'),
            span_p10=q(meds, .10) if meds else float('nan'),
            span_p90=q(meds, .90) if meds else float('nan'),
            span_p90_over_p10=(q(meds, .90) / q(meds, .10)) if meds and q(meds, .10) > 0 else float('nan'),
            retention_spread=(max(rets) / min(rets)) if rets and min(rets) > 0 else float('nan'),
        )
    return dict(units=units, summary=summary, groups=dict(
        domains={d: gd[d] for d in sorted(gd)},
        dom_arm={'%s|%s' % (k[0], k[1]): v for k, v in sorted(gda.items(), key=lambda kv: str(kv[0]))},
        knobs={l: grp[l] for l in KL if grp[l]}), span_full={u: UNITSET[u]['span_full'] for u in units})


print('=' * 118)
print('■ N3：部署者可用的校准族 —— 36 单元集（主报告集）')
print('=' * 118)

if '--diag-units' in sys.argv:
    fz = json.load(io.open(FROZEN36, encoding='utf-8'))
    fzu = fz['per_unit']
    mine = {}
    for u in sorted(UNITS):
        seq = [rho([d[k] for k in UNITS[u]['keys']]) for _, d in UNITS[u]['levels']]
        mine[u] = max(seq) - min(seq)
    inter = sorted(set(mine) & set(fzu))
    print('units: mine %d ｜ frozen %d ｜ common %d' % (len(mine), len(fzu), len(inter)))
    print('mine-only :', sorted(set(mine) - set(fzu)))
    print('frozen-only:', sorted(set(fzu) - set(mine)))
    bad = [(u, mine[u], fzu[u]['span_full']) for u in inter if abs(mine[u] - fzu[u]['span_full']) > 1e-6]
    print('span_full 不符：%d / %d' % (len(bad), len(inter)))
    for u, a, b in bad[:25]:
        print('   %-50s mine %13.4f  frozen %13.4f  Δ %+11.4f' % (u, a, b, a - b))
    print('levels/keys 抽样：')
    for u in sorted(UNITS)[:3]:
        print('   %-50s levels=%d keys=%d' % (u, len(UNITS[u]['levels']), len(UNITS[u]['keys'])))
    nl = sorted(len(UNITS[u]['levels']) for u in UNITS)
    print('levels 分布：min %d max %d sum %d' % (nl[0], nl[-1], sum(nl)))
    sys.exit(0)

res36 = run('36', UNITS, NSPLIT, None)
fz36 = json.load(io.open(FROZEN36, encoding='utf-8'))['arms']
print('\n【复现闸门 A】原六臂 vs %s（md5 %s）' % (os.path.basename(FROZEN36), md5(FROZEN36)))
gateA = True
for k in ('C0e', 'C1u', 'C2l', 'Cg', 'ISO', 'QNT'):
    mine, theirs = res36['summary'][k]['median'], fz36[k]['median']
    ok = abs(mine - theirs) < 5e-4
    gateA &= ok
    print('  %-5s 本脚本 %.4f ｜ 冻结 %.4f ｜ Δ %+.4f  %s' % (k, mine, theirs, mine - theirs, '✓' if ok else '✗'))
print('  闸门 A %s' % ('全过 ⇒ 新臂与既有臂同源同协议' if gateA else '**未过**'))

print('\n【复现闸门 B】8 单元集原六臂 vs %s（md5 %s）' % (os.path.basename(FROZEN8), md5(FROZEN8)))
def knob_of8(name):
    return 'K6 VLM·pixel budget' if name.startswith('pxbudget') else 'K5 VLM·tiling level'


res8 = run('8', L8, min(NSPLIT, 200), None, knobfn=knob_of8)
fz8 = json.load(io.open(FROZEN8, encoding='utf-8'))['arms']
gateB = True
for k in ('C0e', 'C1u', 'C2l', 'Cg', 'ISO', 'QNT'):
    mine, theirs = res8['summary'][k]['median'], fz8[k]['median']
    ok = abs(mine - theirs) < 5e-4
    gateB &= ok
    print('  %-5s 本脚本 %.4f ｜ 冻结 %.4f ｜ Δ %+.4f  %s' % (k, mine, theirs, mine - theirs, '✓' if ok else '✗'))
print('  闸门 B %s' % ('全过' if gateB else '**未过**'))
if not (gateA and gateB):
    print('\n!! 复现闸门未过 ⇒ 两侧不同源，**停止**，不解释新臂。')

DEPLOY = {
    'C0e': 'nothing', 'Cg': 'global', 'C1u': 'per-unit', 'C2l': 'per-unit',
    'ISO': 'per-unit', 'QNT': 'per-unit', 'Ck': 'per-knob', 'SISOk': 'per-knob', 'SISOg': 'global',
    'Cd': 'per-domain', 'Cd20': 'per-domain (20/unit)', 'Cd20s': 'per-domain (20 total)', 'Cda': 'per-domain×contract',
}
for f in FAM:
    DEPLOY['%s@global' % f] = 'global'
    DEPLOY['%s@per_domain' % f] = 'per-domain'
    DEPLOY['%s@per_dom_arm' % f] = 'per-domain×contract'
    DEPLOY['%s@per_unit' % f] = 'per-unit'

PRETTY = {
    'C0e': 'C0e 对照：留出但不校准', 'Cg': 'Cg 全局单组仿射（上端点）',
    'Ck': 'Ck 按 knob 池化（S12）', 'SISOk': 'SISOk 按 knob 保序（S12）', 'SISOg': 'SISOg 全局保序（S12）',
    'C1u': 'C1u 逐 unit 仿射（下端点）', 'C2l': 'C2l 逐 unit 逐档仿射',
    'ISO': 'ISO 逐 unit 逐档保序', 'QNT': 'QNT 逐 unit 逐档分位',
    'Cd': '#1 Cd  按**目标域**池化仿射', 'Cd20': '#1 Cd20  按域池化、**每配置 20 张**',
    'Cd20s': '#1 Cd20s 按域池化、**每域共 20 对**', 'Cda': '#3 Cda 按 (域 × 契约) 池化仿射',
}

ORDER = (['C0e', 'Cg', 'Ck', 'SISOk', 'SISOg', 'C1u', 'C2l', 'ISO', 'QNT', 'Cd', 'Cd20', 'Cd20s', 'Cda']
         + ['%s@%s' % (f, g) for f in ('affine', 'log', 'poisson_scale', 'slope_floor', 'mono_pwl',
                                       'kernel', 'temp_power', 'intercept_only', 'platt_sigmoid')
            for g in GRAN])

print('\n' + '=' * 118)
print('■ 36 单元集：%d 次分割、1/3 留出、seed %d ｜ 门槛 ρ≥0.9（论文自己的）' % (NSPLIT, SEED))
print('=' * 118)
print('  %-46s %8s %14s %7s %7s %9s %9s %13s' %
      ('臂', '中位ρ', '5–95%', 'P≥.9', 'P≥.8', '域序ρ', 'knob序ρ', '保留率极差'))
for k in ORDER:
    s = res36['summary'].get(k)
    if not s:
        continue
    nm = PRETTY.get(k, '  ' + k)
    print('  %-46s %8.3f %14s %6.0f%% %6.0f%% %9.3f %9.3f %12s'
          % (nm, s['median'], '%.3f–%.3f' % (s['p05'], s['p95']), 100 * s['frac_ge_090'],
             100 * s['frac_ge_080'], s['dom_median'], s['knob_median'],
             ('%.0f×' % s['retention_spread']) if s['retention_spread'] == s['retention_spread'] else 'nan'))

print('\n' + '=' * 118)
print('■ 幅度可比性：标定后跨度的**跨单元异质性**（"压缩"的可操作定义）')
print('=' * 118)
print('  %-46s %10s %10s %10s %12s' % ('臂', 'span中位', 'span p10', 'span p90', 'p90/p10'))
for k in ORDER:
    s = res36['summary'].get(k)
    if not s:
        continue
    print('  %-46s %10.1f %10.2f %10.1f %11s'
          % (PRETTY.get(k, '  ' + k), s['span_median'], s['span_p10'], s['span_p90'],
             ('%.0f×' % s['span_p90_over_p10']) if s['span_p90_over_p10'] == s['span_p90_over_p10'] else 'nan'))

json.dump(dict(
    script='n3_deployable_calibration.py',
    unit_sets=dict(set36=dict(n=len(res36['units']), units=res36['units']),
                   set8=dict(n=len(res8['units']), units=res8['units'])),
    protocol=dict(nsplit=NSPLIT, seed=SEED, calib_frac=CAL_FRAC,
                  split='random 1/3 per unit via rng.shuffle, drawn once and reused across levels'),
    replication_gate=dict(
        frozen36=os.path.basename(FROZEN36), frozen36_md5=md5(FROZEN36),
        frozen8=os.path.basename(FROZEN8), frozen8_md5=md5(FROZEN8),
        gateA_pass=bool(gateA), gateB_pass=bool(gateB)),
    deployability=DEPLOY,
    groups36=res36['groups'],
    summary36=res36['summary'], summary8=res8['summary'],
    span_full36=res36['span_full'],
    families={f: dict(min_cal_pairs=FAM[f][1]) for f in FAM},
    notes=dict(
        conformal='conformal 产生的是**区间**，不是点映射；本表的被测量是跨度的点统计量 ⇒ 无法在同一被测量上评分（最近的良定义点映射是 QNT 分位映射，已在既有行里）',
        platt='对二值目标的 Platt scaling 不适用于计数目标；以 platt_sigmoid（单调 S 形）作最近的良定义点映射替代，并单列',
        knots='mono_pwl 的分位分箱在标定对 <4 时不可拟合，该格记为 nan',
    ),
), io.open(OUT, 'w', encoding='utf-8', newline='\n'), ensure_ascii=False, indent=2)
print('\n已写出 %s' % OUT)
print('\n【输入件 md5】')
for pth in sorted(SRC):
    print('  %-58s %s' % (os.path.basename(pth), md5(pth)))
print('  %-58s %s' % (os.path.basename(FROZEN36), md5(FROZEN36)))
print('  %-58s %s' % (os.path.basename(FROZEN8), md5(FROZEN8)))
