#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""corpus_pi_zero.py — the corpus's empty-item base rate is zero, and it is checkable.

Why this exists: the natural new-data request is a blind-labelled pool that would measure
$\\pi$, the mixed corpus's base rate of genuinely empty items, so that the zero channel's **precision**
$p\\,\\pi/q$ can be reported instead of merely bounded.

For *this* paper's corpus that measurement is not needed, and the reason is already in the records: the
corpus's own annotations give **every** item at least one target. §M.21.9 says so in words ("the corpus has
no true zeros"); this script makes it a number that can be checked, and §M.21.9 now prints the counts.

Scope: this is a statement about the **ground-truth annotations**, not about the images. An item could in
principle be truly empty and carry a spurious box; that residual is a property of the source datasets, and
it is named as an assumption rather than measured. What the count rules out is the reading in which the
corpus's own true-zero rate is unknown and could be large.

Usage:
  python corpus_pi_zero.py            # recount and print
  python corpus_pi_zero.py --check    # recount + assert the §M.21.9 sentence
  python corpus_pi_zero.py --selftest # negative controls
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
import argparse
import csv
import glob
import io
import os
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')
ROOT = NR()
E2 = RP('analysis', 'e2_newh20')
CORP = RP('analysis', 'e1_5090', 'corpus')
SUPP = RP('PaperB_英文补充材料_PR_20260919.md')

# The corpus pools, and where each domain's full pool lives.
SOURCES = [('ShanghaiTech-A', RP('analysis', 'e1_5090', 'corpus', 'vlm_st_a_base_whole.csv')),
           ('ShanghaiTech-B', RP('analysis', 'e1_5090', 'corpus', 'vlm_st_b_base_whole.csv')),
           ('UCF-QNRF', RP('analysis', 'e1_5090', 'corpus', 'vlm_ucf_base_whole.csv')),
           ('VisDrone', RP('analysis', 'e2_newh20', 'e1_qwen3-vl-32b-awq_visdrone_base.csv')),
           ('AI-TOD', RP('analysis', 'e2_newh20', 'e1_qwen3-vl-32b-awq_aitod_base.csv'))]
EXPECT = {'ShanghaiTech-A': 182, 'ShanghaiTech-B': 316, 'UCF-QNRF': 334,
          'VisDrone': 273, 'AI-TOD': 154}


def rows(p):
    with io.open(p, encoding='utf-8-sig') as f:
        return [r for r in csv.DictReader(f) if '#r' not in str(r.get('item') or '')]


def count():
    out = {}
    for name, p in SOURCES:
        rs = rows(p)
        z = sum(1 for r in rs if str(r.get('gt')).strip() in ('0', '0.0', ''))
        out[name] = (len(rs), z)
    return out


def squash(s):
    return ' '.join(s.split())


DECL = [
    'the base rate $\\pi$ that the precision would need is **zero by annotation**',
    '**182** (ShanghaiTech-A), **316** (ShanghaiTech-B), **334** (UCF-QNRF), **273** (VisDrone) and '
    '**154** (AI-TOD)',
    '**1,259** items in all, and the count of items with a ground-truth count of zero is **0**',
    'the residual assumption is that the source annotations are complete, which we name rather than measure',
]


def check():
    c = count()
    print(c)
    fails = []
    for k, (n, z) in c.items():
        if n != EXPECT[k]:
            fails.append('%s n=%d, expected %d' % (k, n, EXPECT[k]))
        if z != 0:
            fails.append('%s has %d zero-GT items' % (k, z))
    sq = squash(io.open(SUPP, encoding='utf-8').read())
    for d in DECL:
        if squash(d) not in sq:
            fails.append('declaration missing: %s' % d[:70])
    tot = sum(n for n, _ in c.values())
    if tot != 1259:
        fails.append('total is %d, declared 1,259' % tot)
    for x in fails:
        print('MISSING: %s' % x)
    print('CORPUS-PI-ZERO CHECK: %s' % ('PASS' if not fails else 'FAIL'))
    return not fails


def selftest():
    c = count()
    ctl = []
    ctl.append(('every domain pool reproduces its size', all(c[k][0] == EXPECT[k] for k in EXPECT)))
    ctl.append(('every domain has zero zero-GT items', all(z == 0 for _, z in c.values())))

    # (1) The union is not one file repeated -- five distinct domains, five distinct pools.
    ctl.append(('five domains, sum %d' % sum(n for n, _ in c.values()),
                len(c) == 5 and sum(n for n, _ in c.values()) == 1259))

    # (2) The control must be capable of failing: a synthetic zero-GT row must be counted.
    probe = [{'gt': '0'}, {'gt': '3'}, {'gt': ''}]
    z = sum(1 for r in probe if str(r.get('gt')).strip() in ('0', '0.0', ''))
    ctl.append(('the zero-GT detector finds %d of 3 synthetic rows (2 zeros + 1 blank)' % z, z == 2))

    # (3) The reading this rules out: if pi were large, precision
    #     p*pi/q would be large.  Assert the paper still declines to identify precision.
    sq = squash(io.open(SUPP, encoding='utf-8').read())
    ctl.append(('§M.21.9 still declines to identify the precision',
                'It does not identify the precision' in sq))

    ok = True
    for name, passed in ctl:
        print('  [%s] %s' % ('PASS' if passed else 'FAIL', name))
        ok = ok and passed
    print('SELFTEST: %s' % ('PASS' if ok else 'FAIL'))
    return ok


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--check', action='store_true')
    ap.add_argument('--selftest', action='store_true')
    a = ap.parse_args()
    if a.selftest:
        sys.exit(0 if selftest() else 1)
    if a.check:
        sys.exit(0 if check() else 1)
    print(count())
