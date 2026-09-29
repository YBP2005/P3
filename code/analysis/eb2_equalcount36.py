# -*- coding: utf-8 -*-
"""eb2_equalcount36.py —— 在**可完全重算的 36-unit 集**上重算"等档数网格化 + 去端点"的排序稳健性。

## 为什么
F.10 现在的 0.964 / 0.977 / 0.993 建在 **24 个单元**上，其中 **16 个来自预计算的池化 ρ 表**
（无逐项记录）⇒ 评审把这条当作可复现性缺口（T5/T3）。
M.37 已经有**一个完全逐项可重算的 36-unit 集**（A39 的逐项来源）。本脚本在同一构造上补出
F.10 那三种扰动的 Spearman ⇒ 让"排序稳健"这件事落在**可重算单元集**上。

单元构造与 `a39_unit_calib_heldout.py` **逐字同源**（同文件、同规则：档位 ≥3 且各档交集 ≥20）。
"""
import collections
import csv
import glob
import io
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')
PM = r'<WORKDIR>\PaperB\analysis\data\pod_mirror'
W = r'E:\Edu_workplace\work'
B = os.path.join(W, 'b_harvest_20260917')
OUT = r'<WORKDIR>\PaperB\analysis\work\equalcount36_result.json'
ANOM, SENT = 1e5, 1234567890
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
    lv = sorted(bylevel)
    if len(lv) < 3:
        return
    common = set.intersection(*[set(bylevel[s]) for s in lv])
    if len(common) < MIN_ITEMS:
        return
    UNITS[name] = dict(levels=[(s, bylevel[s]) for s in lv], keys=sorted(common))


# —— 与 a39_unit_calib_heldout.py 同源的六族构造 ——
for lab, path, pcol in (
        ('det·in-domain/VisDrone', os.path.join(PM, 'A', 'det_yolo_ladder_visdrone_det.csv'), 'n_det_person'),
        ('det·zero-shot COCO', os.path.join(PM, 'A', 'det_yolo_ladder_yolo12n.csv'), 'n_det_person'),
        ('det·in-domain(micro)/BBBC005', os.path.join(B, 'bbbc_eval', 'ladder.csv'), 'n_det')):
    if not os.path.exists(path):
        continue
    u = unitize(load(path), ['tau', 'imgsz'], pcol)
    add_unit(lab + ' (full grid)', {k: v for k, v in u.items()})
    for sz in sorted({k[1] for k in u if len(k) > 1}):
        add_unit('%s / tau@%s' % (lab, sz), {k: v for k, v in u.items() if len(k) > 1 and k[1] == sz})

p = os.path.join(W, 'dm_ladder.csv')
if os.path.exists(p):
    u = unitize(load(p), ['dataset', 'protocol', 'value'], 'pred')
    for ds in sorted({k[0] for k in u}):
        add_unit('density·official DM-Count / %s' % ds, {k: v for k, v in u.items() if k[0] == ds})
for lab, path in (('density·CSRNet', os.path.join(PM, 'A', 'csrsta_ladder_st_a.csv')),
                  ('density·CSRNet', os.path.join(PM, 'A', 'csrucf_ladder_ucf.csv'))):
    if os.path.exists(path):
        u = unitize(load(path), ['protocol', 'value'], 'pred')
        add_unit('%s / %s' % (lab, os.path.basename(path).split('_')[-2]), {k: v for k, v in u.items()})

for mdl in ('ivl', 'q32'):
    for f in sorted(glob.glob(os.path.join(PM, 'res_ctrl__%s' % mdl, 'res_ctrl_*.csv'))):
        ds = os.path.basename(f)[len('res_ctrl_'):-4]
        u = unitize(load(f), ['budget'], 'pred')
        add_unit('VLM·pixel budget / %s / %s' % (mdl, ds), {k: v for k, v in u.items()})

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
        add_unit('VLM·tiling / %s / %s / %s' % (mdl, dom, arm), bl)

for mdl, pp in (('ivl', os.path.join(PM, 'b2__out_ivl', 'E1.csv')), ('q32', os.path.join(PM, 'b2__out_q32', 'E1.csv'))):
    if os.path.exists(pp):
        add_unit('VLM·output contract / %s' % mdl, {k: v for k, v in unitize(load(pp), ['arm'], 'pred').items()})

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
        add_unit('VLM·prompt family / %s / %s / %s' % (mdl, dom, arm), bl)


def rho(pairs):
    sg = sum(g for g, _ in pairs)
    return 100.0 * (sum(p for _, p in pairs) - sg) / sg if sg else None


def span(seq):
    v = [x for x in seq if x is not None]
    return (max(v) - min(v)) if len(v) >= 2 else None


def equalize(seq, k):
    n = len(seq)
    if n <= k:
        return seq
    idx = sorted(set(int(round(i * (n - 1) / float(k - 1))) for i in range(k)))
    return [seq[i] for i in idx]


def spearman(a, b):
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


units = sorted(UNITS)
rows = []
for u in units:
    seq = [rho([d[k] for k in UNITS[u]['keys']]) for _, d in UNITS[u]['levels']]
    seq = [x for x in seq if x is not None]
    if len(seq) < 3:
        continue
    k = min(len(seq), 4)
    rows.append(dict(unit=u, n=len(seq), span=span(seq), span_eq=span(equalize(seq, k)),
                     span_drop_high=span(seq[:-1]), span_drop_low=span(seq[1:])))
kmin = min(r['n'] for r in rows)
for r in rows:
    r['span_eq'] = span(equalize([rho([d[k2] for k2 in UNITS[r['unit']]['keys']])
                                  for _, d in UNITS[r['unit']]['levels']], kmin))
print('■ 36-unit（可完全重算）集：%d 个单元；等档数目标 k=%d' % (len(rows), kmin))
sp = {}
for tag, key in (('equal-count', 'span_eq'), ('drop-high', 'span_drop_high'), ('drop-low', 'span_drop_low')):
    sub = [(r['span'], r[key]) for r in rows if r[key] is not None]
    sp[key] = spearman([a for a, _ in sub], [b for _, b in sub])
    print('   Spearman(全长, %-12s) = %.3f   n=%d' % (tag, sp[key], len(sub)))
print('   ⇒ 与 24-unit 集的 0.964 / 0.977 / 0.993 并列报告。')

# ★ 同口径变体：24-unit 集的等档数目标是 k=4，而 36 集里含只有 3 档的单元（kmin=3）。
#   为与 24 集**同口径**比较，另报"仅取档数 ≥4 的单元、等档数到 k=4"的子集。
sub4 = [r for r in rows if r['n'] >= 4]
sp4 = {}
if sub4:
    k4 = 4
    for r in sub4:
        r['span_eq4'] = span(equalize([rho([d[k2] for k2 in UNITS[r['unit']]['keys']])
                                       for _, d in UNITS[r['unit']]['levels']], k4))
    for tag, key in (('equal-count k=4', 'span_eq4'), ('drop-high', 'span_drop_high'),
                     ('drop-low', 'span_drop_low')):
        sb = [(r['span'], r[key]) for r in sub4 if r[key] is not None]
        sp4[key] = spearman([a for a, _ in sb], [b for _, b in sb])
        print('   [n>=4 子集 %d 单元] Spearman(全长, %-14s) = %.3f' % (len(sb), tag, sp4[key]))

json.dump(dict(unit_set='36-unit A39 per-item sources (fully recomputable)', n_units=len(rows), k_equal=kmin,
               spearman=sp, n_units_ge4=len(sub4), k_equal_k4=4, spearman_subset_ge4=sp4, units=rows),
          io.open(OUT, 'w', encoding='utf-8', newline='\n'), ensure_ascii=False, indent=2)
print('已写出 %s' % OUT)
