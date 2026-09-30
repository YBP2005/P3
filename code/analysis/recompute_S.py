# -*- coding: utf-8 -*-
"""从存档语料复算每格"弃权占欠数份额" S，用于核对 J.1 的 82–94% 与修 §5.5/附J 的自相矛盾句。
S = (1-w)/[1-w(1+rho_ans)]，w = G_ans/G（真值加权），rho_ans = (Σ pred_ans − G_ans)/G_ans。
同时打印 w、rho_ans、rho_total，便于对账。
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
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')
CORP = RP('analysis', 'e1_5090', 'corpus')
ARCH = NR('analysis', 'm5090_archive', 'unpacked', 'dense')


def load_gt(ds):
    """从存档的 counts.csv 取金标准（st_a/st_b 用 shanghaitech，ucf 用 ucf_qnrf）。"""
    g = {}
    if ds in ('st_a', 'st_b'):
        f = RP('analysis', 'm5090_archive', 'unpacked', 'dense', 'shanghaitech', 'counts.csv')
        want = 'part_A' if ds == 'st_a' else 'part_B'
        for r in csv.DictReader(open(f, encoding='utf-8-sig')):
            if (r.get('part') or '') == want and (r.get('split') or '') == 'test':
                g[os.path.splitext(os.path.basename(r['file']))[0]] = int(r['count'])
    else:
        f = RP('analysis', 'm5090_archive', 'unpacked', 'dense', 'ucf_qnrf', 'counts.csv')
        for r in csv.DictReader(open(f, encoding='utf-8-sig')):
            if (r.get('split') or '') == 'Test':
                g[os.path.splitext(os.path.basename(r['file']))[0]] = int(r['count'])
    return g


pat = __import__('re').compile(r'^vlm_(?P<ds>st_a|st_b|ucf)_(?P<arm>[a-z]+)_whole\.csv$')
gts = {}
print('%-6s %-7s %7s %9s %10s %9s %9s' % ('ds', 'arm', 'n', 'w', 'rho_ans', 'rho_tot', 'S'))
rows = []
for p in sorted(glob.glob(RP('analysis', 'e1_5090', 'corpus', '*.csv'))):
    m = pat.match(os.path.basename(p))
    if not m:
        continue
    ds, arm = m.group('ds'), m.group('arm')
    if ds not in gts:
        gts[ds] = load_gt(ds)
    g = gts[ds]
    recs = []
    for r in csv.DictReader(open(p, encoding='utf-8-sig')):
        it = r['item']
        if it not in g:
            continue
        try:
            pr = float(r['pred'])
        except Exception:
            continue
        if abs(pr) >= 1e5 or int(pr) == 1234567890:
            continue
        recs.append((g[it], pr))
    G = sum(x[0] for x in recs)
    Gans = sum(x[0] for x in recs if x[1] != 0)
    Sans = sum(x[1] for x in recs if x[1] != 0)
    P = sum(x[1] for x in recs)
    w = Gans / G
    rho_ans = (Sans - Gans) / Gans
    rho_tot = (P - G) / G
    S = (1 - w) / (1 - w * (1 + rho_ans))
    rows.append((ds, arm, len(recs), w, rho_ans, rho_tot, S))
    print('%-6s %-7s %7d %9.4f %9.2f%% %8.2f%% %8.1f%%' % (ds, arm, len(recs), w,
                                                           rho_ans * 100, rho_tot * 100, S * 100))

print()
base = {(d, a): s for d, a, n, w, ra, rt, s in rows if a == 'base'}
print('=== base 臂（对照 J.1 印出的 94.2 / 93.7 / 83.8 / 82.1）===')
for k in sorted(base):
    print('   %-6s %-5s S = %.1f%%' % (k[0], k[1], base[k] * 100))
print()
over = [(d, s) for d, a, n, w, ra, rt, s in rows if a == 'over']
under = [(d, s) for d, a, n, w, ra, rt, s in rows if a == 'under']
print('over 臂 S: %s' % ['%s %.1f%%' % (d, s * 100) for d, s in over])
print('under 臂 S: %s' % ['%s %.1f%%' % (d, s * 100) for d, s in under])
print()
dense = [(a, d, s) for d, a, n, w, ra, rt, s in rows if d in ('st_a', 'ucf')]
print('=== 稠密域（st_a/ucf）逐格 S ===')
for a, d, s in sorted(dense):
    print('   %-6s %-6s %.1f%%' % (d, a, s * 100))
