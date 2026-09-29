# -*- coding: utf-8 -*-
"""回语料重算 ShanghaiTech-A 的弃权率**按切块级别**的阶梯，据此定 §5.8(0.0%) 与 §1/§7.7(1.1%) 各属哪一级。
数据：analysis/m5090_archive/unpacked_all/root/{dense_results,tile_results}/*.csv + dense/shanghaitech/counts.csv
"""
import csv
import glob
import io
import os
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')
ARC = r'<WORKDIR>\PaperB\analysis\m5090_archive\unpacked_all\root'
CNT = r'<WORKDIR>\PaperB\analysis\m5090_archive\unpacked\dense\shanghaitech\counts.csv'
gt = {}
for r in csv.DictReader(io.open(CNT, encoding='utf-8-sig')):
    if (r.get('part') or '') == 'part_A' and (r.get('split') or '') == 'test':
        gt[os.path.splitext(os.path.basename(r['file']))[0]] = int(r['count'])
print('st_a test 金标准 %d 项' % len(gt))

def rate(p):
    rows = [r for r in csv.DictReader(io.open(p, encoding='utf-8-sig')) if r.get('item') in gt]
    if not rows:
        return None, 0
    z = sum(1 for r in rows if (r.get('pred') or '').strip() in ('0', '0.0'))
    return z / len(rows) * 100, len(rows)

cands = [('whole', os.path.join(ARC, 'dense_results', 'vlm_st_a_base_whole.csv'))]
for k in (2, 3, 4, 5):
    cands.append(('tile%d' % k, os.path.join(ARC, 'tile_results', 'vlm_st_a_base_tile%d.csv' % k)))
print()
print('%-8s %8s %6s  %s' % ('level', 'abstain%', 'n', 'file'))
got = {}
for nm, p in cands:
    if os.path.exists(p):
        v, n = rate(p)
        got[nm] = v
        print('%-8s %7.2f%% %6d  %s' % (nm, v if v is not None else -1, n, os.path.basename(p)))
    else:
        print('%-8s %8s %6s  （缺）%s' % (nm, '-', '-', os.path.basename(p)))

print()
ms = r'<WORKDIR>\PaperB\PaperB_英文稿_PR_20260919.md'
t = io.open(ms, encoding='utf-8').read()
plan = []
if got.get('whole') and got.get('tile2'):
    ladder = ', '.join('%s: %.1f%%' % (k.replace('tile', '') + 'x' + k.replace('tile', ''),
                                       got[k]) for k in ('tile2', 'tile3', 'tile4') if got.get(k))
    # §1：把 1.1% 的级别写清
    old = 'drops the ShanghaiTech-A [30] abstention rate from **56.6%** to **1.1%** (2×2: 6.0%)'
    new = 'drops the ShanghaiTech-A [30] abstention rate from **56.6%** to **1.1%** (per level: %s)' % ladder
    if old in t:
        t = t.replace(old, new, 1); plan.append('§1 已补各级读数')
    # §5.8：把 0.0% 的级别写清
    old2 = 'reduces the ShanghaiTech-A abstention rate from **56.6%** to **0.0%**'
    new2 = ('reduces the ShanghaiTech-A abstention rate from **56.6%** to **0.0%** at the finest level measured '
            '(per level: %s)' % ladder)
    if old2 in t:
        t = t.replace(old2, new2, 1); plan.append('§5.8 已补级别')
    io.open(ms, 'w', encoding='utf-8', newline='\n').write(t)
for p in plan:
    print('  ', p)
print('（若上面某处显示 MISS，说明该句锚点形状不同，需人工补）')
