#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""close_parse_issue.py —— 把"parse 缺陷是否污染往轮数字"这件事**钉死**。

三问：
  ① 往轮的 46 个 abstain 类臂，用**往轮口径 `cls_of`（raw 子串）**分类时，`unparsed` 有多少？
     （若 ≈0 ⇒ 空 `pred` 未污染任何结论。）
  ② P2 的 12 个臂文件，用**同一口径 `cls_of`** 分类，与 P2 自己"重解析 pred"的结果是否一致？
     （口径不一致会让 P2 与往轮不可比 ⇒ 必须报出来。）
  ③ 两套口径下 P2 的关键率（base 零率、permit 弃答率 / 零率、channel 出口率）差多少？
"""
import collections
import csv
import glob
import io
import os
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')
BASE = r'<WORKDIR>\PaperB'


def cls_of(raw, pred):
    """与 analysis/work/ea2_mixed_analyze.py 的 cls_of **逐字一致**（往轮口径）。"""
    r = (raw or '').lower()
    for k in ('abstain', 'cannot_judge', 'no_people'):
        if k in r:
            return k
    p = (pred or '').strip()
    if p == '':
        return 'unparsed'
    try:
        return 'zero' if float(p) == 0 else 'nonzero'
    except ValueError:
        return 'unparsed'


KEYS = ('zero', 'nonzero', 'no_people', 'cannot_judge', 'abstain', 'unparsed')

print('=' * 92)
print('① 往轮 abstain 类臂：用往轮口径（raw 子串）分类')
print('=' * 92)
pats = ['analysis/e1_results_census/*.csv', 'analysis/p5a_results_ml16384/*.csv']
tot = collections.Counter()
files = 0
worst = []
for pat in pats:
    for f in sorted(glob.glob(os.path.join(BASE, pat))):
        b = os.path.basename(f).lower()
        if not any(k in b for k in ('permit', 'abstain', 'channel', 'enum')):
            continue
        rows = list(csv.DictReader(io.open(f, encoding='utf-8')))
        if not rows:
            continue
        files += 1
        c = collections.Counter(cls_of(r.get('raw'), r.get('pred')) for r in rows)
        for k in KEYS:
            tot[k] += c.get(k, 0)
        if c.get('unparsed', 0) > 0:
            worst.append((os.path.basename(f), c.get('unparsed', 0), len(rows)))
n = sum(tot.values())
print('  文件数 %d ｜ 记录数 %d' % (files, n))
print('  分类分布：%s' % {k: '%d (%.2f%%)' % (v, 100.0 * v / n) for k, v in tot.items()})
print('  **unparsed = %d (%.3f%%)**' % (tot['unparsed'], 100.0 * tot['unparsed'] / n))
if worst:
    print('  仍有 unparsed 的文件（前 8）：')
    for w in worst[:8]:
        print('    %-58s %d/%d' % w)

print()
print('=' * 92)
print('② P2 的 12 臂：往轮口径（raw 子串） vs P2 重解析口径')
print('=' * 92)
P2 = os.path.join(BASE, 'analysis/p2_a800/p2_probe_results_reparsed')
agree = disagree = 0
detail = []
for f in sorted(glob.glob(os.path.join(P2, '*.csv'))):
    rows = list(csv.DictReader(io.open(f, encoding='utf-8')))
    if not rows:
        continue
    c_raw = collections.Counter(cls_of(r.get('raw'), r.get('pred')) for r in rows)
    # P2 自己的口径：直接看重解析后的 pred
    c_p2 = collections.Counter()
    for r in rows:
        p = str(r.get('pred', '')).strip()
        if p == '':
            c_p2['unparsed'] += 1
        elif p.lower() in ('abstain', 'cannot_judge', 'no_people'):
            c_p2[p.lower()] += 1
        else:
            try:
                c_p2['zero' if float(p) == 0 else 'nonzero'] += 1
            except ValueError:
                c_p2['unparsed'] += 1
    same = sum((c_raw & c_p2).values())
    diff = len(rows) - same
    agree += same
    disagree += diff
    detail.append((os.path.basename(f), len(rows), same, diff))

for name, nn, s, d in detail:
    print('  %-48s n=%-4d 一致 %-4d 不一致 %-4d %s' % (name, nn, s, d, '' if d == 0 else '← 注意'))
tt = agree + disagree
print('  合计：一致 %d (%.4f%%) ｜ 不一致 %d' % (agree, 100.0 * agree / tt, disagree))
print()
print('结论：① 若 unparsed≈0 ⇒ 往轮数字未被污染；② 若不一致=0 ⇒ P2 与往轮口径等价。')
