#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""pod_build_e4f4.py — 构建 BBBC005 的 **F=4 独立条件**留出清单（剔除已用的 10 项）
   输出 /root/b2/man_E4F4.csv，exp=E4F4，格式同 man_E4.csv
"""
import csv, io, os, sys

IDX = '/root/bbbc/index.csv'
USED = '/root/b2/man_E4.csv'
OUT = '/root/b2/man_E4F4.csv'
FOCUS = os.environ.get('E4F_FOCUS', '4')

used = set()
with io.open(USED, encoding='utf-8-sig', newline='') as f:
    for r in csv.DictReader(f):
        used.add(r['item'].strip())
print('已用集 %d 项' % len(used))

seen, rows = set(), []
with io.open(IDX, encoding='utf-8-sig', newline='') as f:
    for r in csv.DictReader(f):
        if str(r.get('focus', '')).strip() != FOCUS:
            continue
        it = r['item'].strip()
        if it in seen or it in used:
            continue
        seen.add(it)
        rows.append((it, r['path'].strip(), int(r['count'])))
rows.sort()
print('F=%s 留出集 %d 项（唯一、且未在 E4 中出现）' % (FOCUS, len(rows)))
assert rows, '留出集为空，中止'
assert not (used & set(x[0] for x in rows)), '与已用集有交集'

with io.open(OUT, 'w', encoding='utf-8-sig', newline='') as f:
    w = csv.writer(f)
    w.writerow(['exp', 'item', 'domain', 'path', 'gt', 'arm', 'budget', 'nsample', 'temp'])
    for it, p, c in rows:
        w.writerow(['E4F4', it, 'bbbc', p, c, 'cells', 0, 1, 0.0])
cs = [c for _, _, c in rows]
print('已写 %s（%d 数据行 + 表头）' % (OUT, len(rows)))
print('GT 范围 %d-%d，均值 %.1f' % (min(cs), max(cs), sum(cs) / len(cs)))
