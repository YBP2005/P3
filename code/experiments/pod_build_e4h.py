#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""pod_build_e4h.py — 构建 BBBC005 留出集清单 man_E4H.csv
   留出集 = index.csv 中 F=1 且**不在** man_E4.csv（已用集）里的 item。
   格式与 man_E4.csv 一致: exp,item,domain,path,gt,arm,budget,nsample,temp
"""
import csv, io, os, sys

IDX = '/root/bbbc/index.csv'
USED = '/root/b2/man_E4.csv'
OUT = '/root/b2/man_E4H.csv'
LIMIT = int(os.environ.get('E4H_LIMIT', '0') or 0)

used = set()
with io.open(USED, encoding='utf-8-sig', newline='') as f:
    for r in csv.DictReader(f):
        used.add(r['item'].strip())
print('已用集 %d 项' % len(used))

rows = []
with io.open(IDX, encoding='utf-8-sig', newline='') as f:
    for r in csv.DictReader(f):
        if str(r.get('focus', '')).strip() != '1':
            continue
        it = r['item'].strip()
        if it in used:
            continue
        rows.append((it, r['path'].strip(), int(r['count'])))
rows.sort()
# 唯一化（index.csv 有 21600 行 / 19200 唯一）
seen, uniq = set(), []
for it, p, c in rows:
    if it in seen:
        continue
    seen.add(it); uniq.append((it, p, c))
print('F1 留出集 %d 项（唯一）' % len(uniq))
if LIMIT:
    uniq = uniq[:LIMIT]
    print('按 E4H_LIMIT 截取 %d 项' % len(uniq))

with io.open(OUT, 'w', encoding='utf-8-sig', newline='') as f:
    w = csv.writer(f)
    w.writerow(['exp', 'item', 'domain', 'path', 'gt', 'arm', 'budget', 'nsample', 'temp'])
    for it, p, c in uniq:
        w.writerow(['E4H', it, 'bbbc', p, c, 'cells', 0, 1, 0.0])
print('已写 %s（%d 数据行 + 表头）' % (OUT, len(uniq)))
# 校验：与已用集零交集
inter = used & set(x[0] for x in uniq)
print('与已用集交集 = %d（必须为 0）' % len(inter))
print('GT 范围 %d-%d，均值 %.1f' % (min(c for _, _, c in uniq), max(c for _, _, c in uniq),
                                    sum(c for _, _, c in uniq) / len(uniq)))
sys.exit(0 if len(inter) == 0 else 9)
