# -*- coding: utf-8 -*-
"""稳健列全：各模型在①零池 base 出零率 ②非零池 permit/channel 弃答率。"""
import csv
import glob
import os
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')
D = r'<WORKDIR>\PaperB\analysis\e2_newh20'
DOMS = ['st_a', 'st_b', 'ucf', 'visdrone', 'aitod', 'countbench']


def num(v):
    try:
        return float(str(v).strip())
    except Exception:
        return None


def ab(r):
    b = ' '.join(str(v or '') for k, v in r.items() if k not in ('pred', 'gt')).lower()
    return ('abstain' in b) or ('cannot_judge' in b) or ('no_people' in b)


def load(p):
    with open(p, encoding='utf-8-sig') as f:
        return [r for r in csv.DictReader(f) if '#r' not in str(r.get('item', ''))]


def parse(fn):
    """e1_<model>_<ds>_<arm>.csv（可带 nz__ 前缀）"""
    pre = 'nonzero' if fn.startswith('nz__') else 'zero'
    if fn.startswith('nz__'):
        fn = fn[4:]
    if not fn.startswith('e1_'):
        return None
    body = fn[3:-4]
    for ds in sorted(DOMS, key=len, reverse=True):
        i = body.find('_' + ds + '_')
        if i > 0:
            return pre, body[:i], ds, body[i + len(ds) + 2:]
    return None


tab = {}
for p in glob.glob(os.path.join(D, '*.csv')):
    k = parse(os.path.basename(p))
    if k:
        tab[k] = p

models = sorted(set(k[1] for k in tab))
print('共 %d 个模型标签：' % len(models))
for m in models:
    print('   ', m)

print()
print('=' * 92)
print('① 零池 base 臂出零率')
print('=' * 92)
print('  %-24s %-14s %-14s %-14s %-14s' % ('模型', 'st_a', 'ucf', 'visdrone', 'aitod'))
for m in models:
    cells = []
    for ds in ('st_a', 'ucf', 'visdrone', 'aitod'):
        p = tab.get(('zero', m, ds, 'base'))
        if p:
            r = load(p)
            z = sum(1 for x in r if num(x.get('pred')) == 0)
            cells.append('%d/%d(%d%%)' % (z, len(r), round(100.0 * z / len(r))) if r else '-')
        else:
            cells.append('-')
    if any(c != '-' for c in cells):
        print('  %-24s %-14s %-14s %-14s %-14s' % (m, *cells))

print()
print('=' * 92)
print('② 非零池 permit 弃答率（饱和性检验）')
print('=' * 92)
print('  %-24s %-14s %-14s %-14s %-14s' % ('模型', 'st_a', 'ucf', 'visdrone', 'aitod'))
for m in models:
    cells = []
    for ds in ('st_a', 'ucf', 'visdrone', 'aitod'):
        p = tab.get(('nonzero', m, ds, 'permit'))
        if p:
            r = load(p)
            cells.append('%d%%' % round(100.0 * sum(1 for x in r if ab(x)) / len(r)) if r else '-')
        else:
            cells.append('-')
    if any(c != '-' for c in cells):
        print('  %-24s %-14s %-14s %-14s %-14s' % (m, *cells))
