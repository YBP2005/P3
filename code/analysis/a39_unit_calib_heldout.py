# -*- coding: utf-8 -*-
"""a39_unit_calib_heldout.py —— 在 **A39 自己的单元集**上独立复现"留出校准 → 排序保持性"（零 GPU）

## 为什么另立一个脚本（与 per_unit_affine_heldout.py 的关系）
`per_unit_affine_heldout.py` 跑的是 **F.10 的 24-unit 排序对象**，但其中只有 8 个 unit 在冻结管线的
同源源文件里带逐项记录；其余 16 个来自**已预算好的 ρ 表**（`threeway_curves*.csv`）。
本脚本用 **A39 的逐项来源**（`a39_calib3.py` 的同一批文件与同一批 unit 定义）再建一套单元集，
覆盖**检测器 τ、密度回归、VLM 契约、VLM 问法族**这四个在 F.10 里无法逐项检验的族。
⇒ 两套单元集**各自独立报告、不混池**（来自不同文件、不同 item 交集）。

## 族定义与判据（与 per_unit_affine_heldout.py 逐字一致，便于对照）
    fit_a(P, G) = lstsq([P, 1], G)   ⇒ 校准器 pred′ = a·pred + b（A39 定义，可部署）
    C1u = 每 unit 一组 (a,b)（跨该 unit 全部档位），留出折拟合；C2l = 逐档重拟合；
    Cg  = **全部 unit 合并**一组 (a,b)（"一个温度参数"质疑）；ISO = 逐档保序（可部署方向 p→g）；
    QNT = 逐档分位数映射（不可部署）；C0e = 留出但不校准（对照）。
    留出比例 1/3；每 unit 一次分割跨档复用；200 次分割；判据 Spearman ≥0.9（评审底线 ≥0.8）。

## 单元资格（沿用 A39 规则，不自行放宽）
    档位数 ≥3，且**各档 item 交集** ≥20。
"""


# ── 复现包统一根：`_repro_root.py`（与本文件同目录）──────────────────────────────
# RP(*parts) = 作者树相对路径 -> 绝对路径（作者树上原样；放行树上查前缀映射表）；
# NR(*parts) = **未随包发布**的作者侧路径（放行树上落到 _NOT_RELEASED/，使失败可见）。
try:
    from _repro_root import resolve as RP, not_released as NR
except ImportError:                      # 只拷走单个脚本时：就地反推仓库根，无前缀映射表
    import os as _o
    _r = _o.environ.get('PAPERB_ROOT') or _o.path.dirname(_o.path.dirname(_o.path.abspath(__file__)))
    RP = lambda *p: _o.path.join(_r, *p)
    NR = lambda *p: _o.path.join(_r, '_NOT_RELEASED', *p)
import collections
import csv
import glob
import io
import json
import os
import random
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')
PM = RP('analysis', 'data', 'pod_mirror')
W = NR('@shared', 'work')
B = NR('@shared', 'work', 'b_harvest_20260917')
OUT = RP('analysis', 'work', 'a39_unit_calib_heldout_result.json')
ANOM, SENT = 1e5, 1234567890
NSPLIT = 200
SEED = 20260923
CAL_FRAC = 1 / 3.0
MIN_ITEMS = 20


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


def add_unit(name, bylevel):
    """bylevel: {level_label: {item:(g,p)}}；按 A39 规则判资格，并取各档 item 交集。"""
    lv = sorted(bylevel)
    if len(lv) < 3:
        return
    common = set.intersection(*[set(bylevel[s]) for s in lv])
    if len(common) < MIN_ITEMS:
        return
    ks = sorted(common)
    UNITS[name] = dict(levels=[(s, bylevel[s]) for s in lv], keys=ks)


# ---------- 一、检测器 τ ----------
for lab, path, pcol in (
        ('det·in-domain/VisDrone', RP('analysis', 'data', 'pod_mirror', 'A', 'det_yolo_ladder_visdrone_det.csv'), 'n_det_person'),
        ('det·zero-shot COCO', RP('analysis', 'data', 'pod_mirror', 'A', 'det_yolo_ladder_yolo12n.csv'), 'n_det_person'),
        ('det·in-domain(micro)/BBBC005', NR('@shared', 'work', 'b_harvest_20260917', 'bbbc_eval', 'ladder.csv'), 'n_det')):
    if not os.path.exists(path):
        continue
    u = unitize(load(path), ['tau', 'imgsz'], pcol)
    add_unit(lab + ' (full grid)', {k: v for k, v in u.items()})
    for sz in sorted({k[1] for k in u if len(k) > 1}):
        add_unit('%s / tau@%s' % (lab, sz), {k: v for k, v in u.items() if len(k) > 1 and k[1] == sz})

# ---------- 二、密度回归 ----------
p = NR('@shared', 'work', 'dm_ladder.csv')
if os.path.exists(p):
    u = unitize(load(p), ['dataset', 'protocol', 'value'], 'pred')
    for ds in sorted({k[0] for k in u}):
        add_unit('density·official DM-Count / %s' % ds, {k: v for k, v in u.items() if k[0] == ds})
for lab, path in (('density·CSRNet', RP('analysis', 'data', 'pod_mirror', 'A', 'csrsta_ladder_st_a.csv')),
                  ('density·CSRNet', RP('analysis', 'data', 'pod_mirror', 'A', 'csrucf_ladder_ucf.csv'))):
    if os.path.exists(path):
        u = unitize(load(path), ['protocol', 'value'], 'pred')
        add_unit('%s / %s' % (lab, os.path.basename(path).split('_')[-2]), {k: v for k, v in u.items()})

# ---------- 三、VLM 像素预算（res_ctrl） ----------
for mdl in ('ivl', 'q32'):
    for f in sorted(glob.glob(os.path.join(RP('analysis', 'data', 'pod_mirror'), 'res_ctrl__%s' % mdl, 'res_ctrl_*.csv'))):
        ds = os.path.basename(f)[len('res_ctrl_'):-4]
        u = unitize(load(f), ['budget'], 'pred')
        add_unit('VLM·pixel budget / %s / %s' % (mdl, ds), {k: v for k, v in u.items()})

# ---------- 四、VLM 切块 ----------
for sub, mdl in (('tile_results', 'Qwen32B'), ('b2__out_32b_ctile', 'Qwen32B(ctile)'),
                 ('b2__out_8b_ctile', 'Qwen8B(ctile)')):
    d = os.path.join(RP('analysis', 'data', 'pod_mirror'), sub)
    if not os.path.isdir(d):
        continue
    groups = collections.defaultdict(dict)
    for f in sorted(os.listdir(d)):
        m = re.match(r'^vlm_([a-z0-9]+)_(base|over|under|[a-z0-9]+)_(whole|tile\d+)\.csv$', f)
        if not m:
            continue
        dom, arm, lvl = m.groups()
        rows = load(os.path.join(d, f))
        d2 = {}
        for r in rows:
            g = fn(r.get('gt')); pp = fn(r.get('pred'))
            if g is None or g <= 0 or pp is None or pp >= ANOM or pp == SENT:
                continue
            d2[str(r['item']).strip()] = (g, float(pp))
        groups[(dom, arm)][lvl] = d2
    for (dom, arm), bl in sorted(groups.items()):
        add_unit('VLM·tiling / %s / %s / %s' % (mdl, dom, arm), bl)

# ---------- 五、VLM 输出契约 ----------
for mdl, p in (('ivl', RP('analysis', 'data', 'pod_mirror', 'b2__out_ivl', 'E1.csv')),
               ('q32', RP('analysis', 'data', 'pod_mirror', 'b2__out_q32', 'E1.csv'))):
    if os.path.exists(p):
        u = unitize(load(p), ['arm'], 'pred')
        add_unit('VLM·output contract / %s' % mdl, {k: v for k, v in u.items()})

# ---------- 六、VLM 问法族 V1–V5 ----------
for sub, mdl in (('dense_prompt_results', 'Qwen32B'), ('ivl_dense_prompt_results', 'IVL')):
    d = os.path.join(RP('analysis', 'data', 'pod_mirror'), sub)
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
        add_unit('VLM·prompt family / %s / %s / %s' % (mdl, dom, arm), bl)


# ---------------- 工具（与 per_unit_affine_heldout.py 同定义） ----------------
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


def q(v, p):
    v = sorted(v)
    return v[min(len(v) - 1, max(0, int(round(p * (len(v) - 1)))))]


units = sorted(UNITS)
print('=' * 112)
print('■ A39 单元集（逐项来源、A39 资格规则：档位≥3 且各档交集≥%d item）' % MIN_ITEMS)
print('=' * 112)
for u in units:
    print('  %-52s 档位 %2d  交集 %4d' % (u, len(UNITS[u]['levels']), len(UNITS[u]['keys'])))
if len(units) < 5:
    sys.exit('!! 合格 unit 太少（%d）' % len(units))

for u in units:
    seq = [rho([d[k] for k in UNITS[u]['keys']]) for _, d in UNITS[u]['levels']]
    UNITS[u]['span_full'] = max(seq) - min(seq)
ref = [UNITS[u]['span_full'] for u in units]

rng = random.Random(SEED)
R = {k: [] for k in ('C0e', 'C1u', 'C2l', 'Cg', 'ISO', 'QNT')}
ratio = {u: {k: [] for k in ('C1u', 'Cg')} for u in units}
absA, relCg, relA = {u: [] for u in units}, [], []

for _ in range(NSPLIT):
    sp = {k: [] for k in R}
    cal, ev = {}, {}
    for u in units:
        ks = list(UNITS[u]['keys'])
        rng.shuffle(ks)
        nc = max(2, int(round(len(ks) * CAL_FRAC)))
        ck, ek = set(ks[:nc]), set(ks[nc:])
        cal[u] = {lb: [d[k] for k in ck] for lb, d in UNITS[u]['levels']}
        ev[u] = {lb: [d[k] for k in ek] for lb, d in UNITS[u]['levels']}
    C1 = {u: fit_a([x for lb in cal[u] for x in cal[u][lb]]) for u in units}
    Cg = fit_a([x for u in units for lb in cal[u] for x in cal[u][lb]])
    for u in units:
        vC0, vC1, vC2, vCg, vISO, vQNT = [], [], [], [], [], []
        for lb, _ in UNITS[u]['levels']:
            e, c = ev[u][lb], cal[u][lb]
            vC0.append(rho(e)); vC1.append(rho(e, C1[u]))
            vC2.append(rho(e, fit_a(c))); vCg.append(rho(e, Cg))
            pe = [p for _, p in e]; sg = sum(g for g, _ in e)
            vISO.append(100.0 * (sum(fit_iso(c)(pe)) - sg) / sg)
            vQNT.append(100.0 * (sum(fit_qnt(c)(pe)) - sg) / sg)
            absA[u].append(abs(C1[u][0]))
        s0 = max(vC0) - min(vC0)
        sp['C0e'].append(s0)
        for k, v in (('C1u', vC1), ('C2l', vC2), ('Cg', vCg), ('ISO', vISO), ('QNT', vQNT)):
            s = max(v) - min(v)
            sp[k].append(s)
            if s0 > 1e-9 and k in ratio[u]:
                ratio[u][k].append(s / s0)
        if s0 > 1e-9:
            relA.append(abs((max(vC1) - min(vC1)) / s0 - abs(C1[u][0])))
    # ★ 定理推论必须在**本分割全部 unit 处理完之后**比（跨 unit、同一次分割）
    _rs = [ratio[x]['Cg'][-1] for x in units if ratio[x]['Cg']]
    if len(_rs) >= 2:
        relCg.append(max(_rs) - min(_rs))
    for k in R:
        R[k].append(spearman(ref, sp[k]))

NAMES = [('★ C1u 逐 unit 一组 (a,b)（A39 的 C1，留出）', 'C1u'),
         ('★ C2l 逐 unit 逐档 (a,b)（A39 的 C2，留出）', 'C2l'),
         ('★ Cg 全局单组 (a,b)（“一个温度参数”）', 'Cg'),
         ('★ ISO 逐 unit 逐档保序（可部署）', 'ISO'),
         ('★ QNT 逐 unit 逐档分位数映射（不可部署）', 'QNT'),
         ('○ C0e 对照：留出但不校准', 'C0e')]


def line(v):
    if any(x != x for x in v):
        return '   nan(退化)'
    return '%9.3f %11s %9.0f%% %9.0f%%' % (
        q(v, .5), '%.3f–%.3f' % (q(v, .05), q(v, .95)),
        100 * sum(1 for x in v if x >= .9) / len(v), 100 * sum(1 for x in v if x >= .8) / len(v))


print('\n' + '=' * 112)
print('■ 排序保持性：%d 个 unit、%d 次分割、标定集 1/3（参照序 = 全 item 跨度序）' % (len(units), NSPLIT))
print('=' * 112)
print('  %-44s %9s %11s %10s %10s' % ('臂', '中位 ρ', '5–95%', 'P(≥0.9)', 'P(≥0.8)'))
for nm, k in NAMES:
    print('  %-44s %s' % (nm, line(R[k])))
print('\n  【定理验证】C1u：span比 − |a| 最大偏差 = %.3e  ⇒ %s'
      % (max(relA), '通过' if max(relA) < 1e-9 else '未通过'))
print('  【定理推论】Cg：同一次分割内跨 unit 跨度比极差（%d 次取最大）= %.3e  ⇒ %s'
      % (len(relCg), max(relCg), '通过（全局校准 ⇒ 排序精确不变）' if max(relCg) < 1e-9 else '未通过'))
av = [x for u in units for x in absA[u]]
print('  逐 unit |a_u| 实测跨 %.3f–%.3f' % (min(av), max(av)))


def arm(v):
    if any(x != x for x in v):
        return dict(degenerate=True)
    return dict(median=q(v, .5), p05=q(v, .05), p95=q(v, .95),
                frac_ge_090=sum(1 for x in v if x >= .9) / len(v),
                frac_ge_080=sum(1 for x in v if x >= .8) / len(v))


json.dump(dict(
    unit_set='A39 per-item sources (a39_calib3.py same files and same unit definitions)',
    eligibility='>=3 levels and >=20 common items (A39 rule)',
    n_units=len(units), units=units, nsplit=NSPLIT, seed=SEED, calib_frac=CAL_FRAC,
    arms={k: arm(R[k]) for _, k in NAMES},
    theorem_span_eq_abs_a_max_dev=max(relA),
    corollary_global_same_ratio_max_range=max(relCg),
    per_unit={u: dict(span_full=UNITS[u]['span_full'],
                      slope_median=q(absA[u], .5),
                      ratio_C1u_median=q(ratio[u]['C1u'], .5),
                      ratio_Cg_median=q(ratio[u]['Cg'], .5)) for u in units},
), io.open(OUT, 'w', encoding='utf-8', newline='\n'), ensure_ascii=False, indent=2)
print('\n已写出 %s' % OUT)
