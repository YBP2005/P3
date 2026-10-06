# -*- coding: utf-8 -*-
"""★★ 预注册条款的正面对照（纯 ANALYSIS，不新增推理）：**"跨度"是不是旋钮扫描网格的函数？**

预注册条款的原话：
  "跨度天然随扫描密度与端点选取增长。检验：对每个旋钮在**相同点数、相同分位栅格**下重算跨度
   （子采样到 min 点数），看排序是否保持。"
  "去掉最端点重算跨度" ⇒ 若崩塌，则"response spectrum"须改写为 endpoint-sensitivity report。

本脚本做三件事，全部只用**已发布**的逐图记录：
  ① 重建每个 (旋钮 × 域) 单元的**逐档 ρ 阶梯**（池化 ρ，异常值 pred≥1e5 剔除，同一 item 交集）；
  ② **等点数子采样**：把所有阶梯按分位位置统一降到 k = 4 档（全局最少档数），重算跨度；
  ③ **端点扰动**：分别剔除最高档 / 最低档后重算跨度；
  最后给出与全长阶梯排序的 **Spearman 秩相关**（预注册条款给的判据是 ≥0.8）。

阶梯来源（每个都写明文件来源，可回溯）：
  · 检测 τ        : analysis/data/threeway_curves_v2.csv（域内 16 档 / COCO 32 档 × 3 个 imgsz）
  · 密度·输入尺度  : analysis/data/threeway_curves.csv（mult 6 档 / short 4 档 × st_a,ucf）
  · VLM·像素预算   : analysis/data/pod_mirror/res_ctrl__{q32,ivl}/res_ctrl_<ds>.csv（budget 5 档）
  · VLM·提示词族   : analysis/data/pod_mirror/dense_prompt_results/*_V{1..5}_*.csv（5 档）
  · VLM·切块级别   : analysis/data/pod_mirror/tile_results/*_tile{2..6}.csv（5 档）
  · VLM·输出契约   : analysis/e2_newh20/e1_qwen3-vl-32b-awq_<ds>_{base,permit,bestA,bestB,bestC,channel}.csv（6 档）
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
import csv
import glob
import io
import json
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')
ROOT = NR()
DATA = NR('analysis', 'data')
PM = RP('analysis', 'data', 'pod_mirror')
E2 = RP('analysis', 'e2_newh20')
OUT = RP('analysis', 'work', 'span_equalcount_result.json')
ANOM = 1e5

LADDERS = {}       # unit → list[(level_label, {item: (gt, pred)})]


def load_csv(p, pred_col='pred', gt_col='gt'):
    with io.open(p, encoding='utf-8-sig') as f:
        rows = [r for r in csv.DictReader(f) if '#r' not in str(r.get('item') or '')]
    out = {}
    for r in rows:
        it = str(r.get('item') or '')
        try:
            gt = float(r.get(gt_col) or '')
            pr = float(r.get(pred_col) or '')
        except (TypeError, ValueError):
            continue          # 弃答（pred 空）不参与池化 ρ
        if pr >= ANOM or gt <= 0:
            continue
        out[it] = (gt, pr)
    return out


def pooled(items):
    """同一 item 集合上的池化 ρ（%）。"""
    sg = sum(g for g, _ in items.values())
    sp = sum(p for _, p in items.values())
    return 100.0 * (sp - sg) / sg if sg else None


def add(unit, levels):
    """levels = [(label, dict)]；不同档取同一 item 交集，保证各档可比。"""
    keys = None
    for _, d in levels:
        keys = set(d) if keys is None else (keys & set(d))
    keys = sorted(keys)
    seq = []
    for lb, d in levels:
        sub = {k: d[k] for k in keys}
        r = pooled(sub)
        if r is not None:
            seq.append((lb, r))
    if len(seq) >= 3:
        LADDERS[unit] = seq


# ---------- ① 检测 τ ----------
p = NR('analysis', 'data', 'threeway_curves_v2.csv')
if os.path.exists(p):
    rows = list(csv.DictReader(io.open(p, encoding='utf-8-sig')))
    for para in sorted(set(r['paradigm'] for r in rows)):
        for sz in sorted(set(r['knob'] for r in rows if r['paradigm'] == para)):
            seq = [(r['setting'], float(r['rho'])) for r in rows
                   if r['paradigm'] == para and r['knob'] == sz]
            seq.sort(key=lambda x: float(x[0]))
            if len(seq) >= 3:
                LADDERS['%s / VisDrone / %s' % (para, sz)] = seq

# ---------- ② 密度回归输入尺度 ----------
p = NR('analysis', 'data', 'threeway_curves.csv')
if os.path.exists(p):
    rows = list(csv.DictReader(io.open(p, encoding='utf-8-sig')))
    for para in ('密度回归',):
        for ds in sorted(set(r['domain'] for r in rows if r['paradigm'] == para)):
            for knob in sorted(set(r['knob'] for r in rows if r['paradigm'] == para and r['domain'] == ds)):
                seq = [(r['setting'], float(r['rho'])) for r in rows
                       if r['paradigm'] == para and r['domain'] == ds and r['knob'] == knob]
                if len(seq) >= 3:
                    LADDERS['density / %s / %s' % (ds, knob)] = seq
    # 像素预算（threeway 版，另一套读数）
    for para in ('VLM·Qwen32B', 'VLM·InternVL8B'):
        for ds in sorted(set(r['domain'] for r in rows if r['paradigm'] == para)):
            seq = [(r['setting'], float(r['rho'])) for r in rows
                   if r['paradigm'] == para and r['domain'] == ds]
            if len(seq) >= 3:
                LADDERS['pxbudget(threeway) / %s / %s' % (para.split('·')[1], ds)] = seq

# ---------- ③ 像素预算（res_ctrl：逐图，可重算） ----------
for mdl in ('q32', 'ivl'):
    for f in sorted(glob.glob(os.path.join(RP('analysis', 'data', 'pod_mirror'), 'res_ctrl__%s' % mdl, 'res_ctrl_*.csv'))):
        ds = os.path.basename(f)[len('res_ctrl_'):-4]
        with io.open(f, encoding='utf-8-sig') as fh:
            rows = [r for r in csv.DictReader(fh) if '#r' not in str(r.get('item') or '')]
        buds = sorted(set(r['budget'] for r in rows), key=lambda x: float(x))
        levels = []
        for b in buds:
            d = load_csv(f)
            d = {k: v for k, v in d.items()}
            # 逐 budget 过滤
            with io.open(f, encoding='utf-8-sig') as fh:
                rr = [r for r in csv.DictReader(fh) if r['budget'] == b]
            dd = {}
            for r in rr:
                try:
                    gt, pr = float(r['gt']), float(r['pred'])
                except (TypeError, ValueError):
                    continue
                if pr >= ANOM or gt <= 0:
                    continue
                dd[str(r['item'])] = (gt, pr)
            levels.append(('budget=%s' % b, dd))
        add('pxbudget(res_ctrl) / %s / %s' % (mdl, ds), levels)

# ---------- ④ 提示词族 V1–V5 ----------
for ds in ('st_a', 'ucf', 'visdrone'):
    for arm in ('base',):
        files = sorted(glob.glob(os.path.join(RP('analysis', 'data', 'pod_mirror', 'dense_prompt_results'), 'vlm_%s_%s_V*.csv' % (ds, arm))))
        if not files:
            continue
        levels = [(os.path.basename(f).split('_V')[1][0], load_csv(f)) for f in files]
        add('promptfamily / %s / %s' % (ds, arm), levels)
    files = sorted(glob.glob(os.path.join(RP('analysis', 'data', 'pod_mirror', 'ivl_dense_prompt_results'), 'ivl_%s_%s_V*.csv' % (ds, 'base'))))
    if files:
        levels = [(os.path.basename(f).split('_V')[1][0], load_csv(f)) for f in files]
        add('promptfamily(ivl) / %s / base' % ds, levels)

# ---------- ⑤ 切块级别 ----------
for ds in ('st_a', 'ucf', 'visdrone'):
    files = sorted(glob.glob(os.path.join(RP('analysis', 'data', 'pod_mirror', 'tile_results'), 'vlm_%s_base_tile*.csv' % ds)))
    if files:
        levels = [(os.path.basename(f).split('tile')[1][0], load_csv(f)) for f in files]
        add('tiling / %s / base' % ds, levels)
    files = sorted(glob.glob(RP('analysis', 'data', 'pod_mirror', 'ivl_aerial_tile_results', 'ivl_*tile*.csv'))) if ds == 'visdrone' else []
    if files:
        levels = [(os.path.basename(f).split('tile')[1][0], load_csv(f)) for f in files]
        add('tiling(ivl) / %s / base' % ds, levels)

# ---------- ⑥ 输出契约（E2 普查 6 臂） ----------
for ds in ('st_a', 'ucf', 'visdrone', 'aitod'):
    levels = []
    for arm in ('base', 'permit', 'bestA', 'bestB', 'bestC', 'channel'):
        f = os.path.join(RP('analysis', 'e2_newh20'), 'e1_qwen3-vl-32b-awq_%s_%s.csv' % (ds, arm))
        if os.path.exists(f):
            levels.append((arm, load_csv(f)))
    if len(levels) >= 3:
        add('contract(E2) / q32awq / %s' % ds, levels)


def span(seq):
    v = [x[1] for x in seq]
    return max(v) - min(v)


def equalize(seq, k):
    """按**分位位置**把阶梯降到 k 档：取索引 round(i*(n-1)/(k-1))，去重后保序。"""
    n = len(seq)
    if n <= k:
        return seq
    idx = sorted(set(int(round(i * (n - 1) / float(k - 1))) for i in range(k)))
    return [seq[i] for i in idx]


def spearman(a, b):
    """秩相关（无并列时等价于 Pearson on ranks；本数据有并列，用平均秩）。"""
    def rank(x):
        s = sorted(range(len(x)), key=lambda i: x[i])
        r = [0.0] * len(x)
        i = 0
        while i < len(s):
            j = i
            while j + 1 < len(s) and x[s[j + 1]] == x[s[i]]:
                j += 1
            avg = (i + j) / 2.0 + 1
            for t in range(i, j + 1):
                r[s[t]] = avg
            i = j + 1
        return r
    ra, rb = rank(a), rank(b)
    n = len(a)
    ma, mb = sum(ra) / n, sum(rb) / n
    num = sum((ra[i] - ma) * (rb[i] - mb) for i in range(n))
    da = sum((ra[i] - ma) ** 2 for i in range(n)) ** 0.5
    db = sum((rb[i] - mb) ** 2 for i in range(n)) ** 0.5
    return num / (da * db) if da and db else float('nan')


units = sorted(LADDERS)
kmin = min(len(LADDERS[u]) for u in units)
print('单元数 %d；阶梯档数分布：%s；等点数目标 k=%d'
      % (len(units), sorted(set(len(LADDERS[u]) for u in units)), kmin))
print()
print('%-46s %5s %9s %9s %9s %9s' % ('单元', '档数', '全长跨度', '等k跨度', '去高档', '去低档'))
rows = []
for u in units:
    seq = LADDERS[u]
    s_full = span(seq)
    s_eq = span(equalize(seq, kmin))
    s_hi = span(seq[:-1]) if len(seq) > 3 else float('nan')
    s_lo = span(seq[1:]) if len(seq) > 3 else float('nan')
    rows.append(dict(unit=u, n=len(seq), span=s_full, span_eq=s_eq, span_drop_high=s_hi,
                     span_drop_low=s_lo))
    print('%-46s %5d %9.1f %9.1f %9.1f %9.1f' % (u, len(seq), s_full, s_eq, s_hi, s_lo))

print()
res = dict(units=rows, k_equal=kmin)

# 秩相关：全长 vs 三个变体
for tag, key in (('等点数子采样', 'span_eq'), ('剔除最高档', 'span_drop_high'),
                 ('剔除最低档', 'span_drop_low')):
    sub = [(r['span'], r[key]) for r in rows if r[key] == r[key]]      # 去 NaN
    rho = spearman([a for a, _ in sub], [b for _, b in sub])
    res['spearman_' + key] = rho
    print('Spearman(全长排序, %s排序) = %.3f   n=%d' % (tag, rho, len(sub)))

# 相对变化
import statistics as st
shrink = [r['span_eq'] / r['span'] for r in rows if r['span']]
dhi = [(r['span'] - r['span_drop_high']) / r['span'] for r in rows if r['span'] and r['span_drop_high'] == r['span_drop_high']]
dlo = [(r['span'] - r['span_drop_low']) / r['span'] for r in rows if r['span'] and r['span_drop_low'] == r['span_drop_low']]
res['shrink_eq_median'] = st.median(shrink)
res['drop_high_median'] = st.median(dhi)
res['drop_low_median'] = st.median(dlo)
print()
print('等点数后跨度中位保留率 %.2f（1.00 = 完全不变）' % res['shrink_eq_median'])
print('剔除最高档后跨度中位下降 %.0f%%；剔除最低档后中位下降 %.0f%%'
      % (100 * res['drop_high_median'], 100 * res['drop_low_median']))

# ★ 可引用区间必须由脚本算出并**断言**，不许手写：
#   稿内写"域内 2.2–2.3×、零样本 COCO 5–10×"，此处即为该句的唯一出处（上一次手写 2.2–5.0 就是错的）。
inner = [r['span'] / r['span_eq'] for r in rows if 'tau' in r['unit'] and '域内' in r['unit']]
coco = [r['span'] / r['span_eq'] for r in rows if 'tau' in r['unit'] and 'COCO' in r['unit']]
res['tau_shrink'] = dict(in_domain=[min(inner), max(inner)], coco=[min(coco), max(coco)])
print()
print('τ 单元的等点数缩小倍率：域内 %.2f–%.2f ；零样本 COCO %.2f–%.2f'
      % (min(inner), max(inner), min(coco), max(coco)))
assert 2.1 <= min(inner) and max(inner) <= 2.4, '域内 τ 缩小倍率与稿内表述不符'
assert 4.5 <= min(coco) and max(coco) <= 10.5, 'COCO τ 缩小倍率与稿内表述不符'

io.open(OUT, 'w', encoding='utf-8', newline='\n').write(json.dumps(res, ensure_ascii=False, indent=2))
print()
print('已冻结 %s' % OUT)
