# -*- coding: utf-8 -*-
"""A5 判定器：按**冻结判据**（a5_criteria_frozen.json，md5 见 .md5 旁车）判 P1/P2/P3。

判据（照抄冻结文件，不在此处改）：
  P1 契约效应跨家族：每个家族 permit 臂把零池"仍答 0"压到 ≤5%；≥5/6 家族通过；
     反例规则：某家族 permit 仍答 0 >30% ⇒ 记"家族依赖"。
  P2 两类答 0 跨家族：密集域(st_a+ucf) 与航拍域(visdrone+aitod) 的 base 答 0 率差 ≥30 pp；≥5/6 家族通过。
  P3 方向一致性：permit 的减零效应方向一致（都为正）。
输入：远端 `/root/e1_results/*.csv`（本脚本在 A800 上运行，也可在本地对拉回的 CSV 运行）。
"""
import csv
import glob
import io
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')
D = sys.argv[1] if len(sys.argv) > 1 else '/root/e1_results'
DZ = sys.argv[2] if len(sys.argv) > 2 else '/root/e1_results_nonzero'
DOMS_DENSE = ['st_a', 'ucf']
DOMS_AERIAL = ['visdrone', 'aitod']


def load(p):
    with io.open(p, encoding='utf-8-sig') as f:
        return [r for r in csv.DictReader(f) if '#r' not in str(r.get('item') or '')]


def cls(r):
    raw = str(r.get('raw') or '').lower()
    p = str(r.get('pred') or '').strip()
    for k in ('abstain', 'cannot_judge', 'no_people'):
        if k in raw:
            return k
    if p == '':
        return 'unparsed'
    try:
        return 'zero' if float(p) == 0 else 'nonzero'
    except ValueError:
        return 'unparsed'


def parse(fn):
    if not fn.startswith('e1_'):
        return None
    body = fn[3:-4]
    for ds in ('st_a', 'st_b', 'ucf', 'visdrone', 'aitod', 'countbench'):
        i = body.find('_' + ds + '_')
        if i > 0:
            return body[:i], ds, body[i + len(ds) + 2:]
    return None


TAB = {}
for p in glob.glob(os.path.join(D, '*.csv')):
    k = parse(os.path.basename(p))
    if k:
        TAB[k] = p
MODELS = sorted(set(k[0] for k in TAB))
print('零池文件 %d 个，家族 %d 个：%s' % (len(TAB), len(MODELS), MODELS))
print()

rows = []
for m in MODELS:
    per = {'model': m}
    # P1：permit 把"仍答 0"压到多少
    ratios = []
    for ds in DOMS_DENSE + DOMS_AERIAL:
        bp = TAB.get((m, ds, 'base'))
        pp = TAB.get((m, ds, 'permit'))
        if not bp or not pp:
            continue
        base = {r['item']: cls(r) for r in load(bp)}
        pmt = {r['item']: cls(r) for r in load(pp)}
        z = [k for k, v in base.items() if v == 'zero']
        if not z:
            continue
        still0 = sum(1 for k in z if pmt.get(k) == 'zero')
        ratios.append(still0 / float(len(z)))
    per['permit_still_zero'] = (sum(ratios) / len(ratios)) if ratios else None
    # P2：密集域 vs 航拍域 base 出零率
    def zr(ds):
        bp = TAB.get((m, ds, 'base'))
        if not bp:
            return None
        rr = load(bp)
        return sum(1 for r in rr if cls(r) == 'zero') / float(len(rr)) if rr else None
    d = [zr(x) for x in DOMS_DENSE]
    a = [zr(x) for x in DOMS_AERIAL]
    d = [x for x in d if x is not None]
    a = [x for x in a if x is not None]
    per['dense_zero'] = sum(d) / len(d) if d else None
    per['aerial_zero'] = sum(a) / len(a) if a else None
    per['gap_pp'] = (100 * (per['dense_zero'] - per['aerial_zero'])
                     if d and a else None)
    rows.append(per)

print('%-22s %10s %10s %10s %10s' % ('家族', 'permit仍0', '密集域零', '航拍域零', '差(pp)'))
for r in rows:
    f = lambda v, p='%.3f': ('—' if v is None else p % v)
    print('%-22s %10s %10s %10s %10s' % (r['model'], f(r['permit_still_zero']),
                                         f(r['dense_zero']), f(r['aerial_zero']),
                                         ('—' if r['gap_pp'] is None else '%+.1f' % r['gap_pp'])))
print()

p1 = [r for r in rows if r['permit_still_zero'] is not None and r['permit_still_zero'] <= 0.05]
p1_bad = [r for r in rows if r['permit_still_zero'] is not None and r['permit_still_zero'] > 0.30]
p2 = [r for r in rows if r['gap_pp'] is not None and r['gap_pp'] >= 30.0]
n = len(rows)
print('P1（permit 把"仍答 0"压到 ≤5%%）：%d/%d 家族通过（判据：≥5/6）' % (len(p1), n))
print('  反例（>30%%）：%s' % ([r['model'] for r in p1_bad] or '无'))
print('P2（密集-航拍 出零率差 ≥30 pp）：%d/%d 家族通过（判据：≥5/6）' % (len(p2), n))
if n >= 6:
    print('判定：P1 %s；P2 %s' % ('通过' if len(p1) >= 5 else '不通过',
                                  '通过' if len(p2) >= 5 else '不通过'))
else:
    print('判定：目前只有 %d 个家族，判据要求 ≥6（3 锚点 + 3 新家族）⇒ 暂不判定' % n)
