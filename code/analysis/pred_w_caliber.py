#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""pred_w_caliber.py — why the calibration table has no family of the form f(pred, w).

Charge (CONFIRMED): Proposition 4 decomposes the aggregate bias with $w=G_N/G$, so a
two-dimensional calibrator taking $(pred, w)$ looks like the most deployable candidate — and it is absent
from the eleven shapes of §M.37.

The answer is not "we forgot". Proposition 4's $w$ is a **ground-truth** quantity, so it is (i) unobservable
at deployment and (ii) undefined on a held-out item, which is the unit the §M.37 protocol holds out. Its
observable analogue changes the *estimand* rather than the prediction, and that family is already reported
as the paper's two conventions, quantified in §5.12. This script asserts the three facts the note rests on
and checks that the note is printed -- it does not recompute §5.12.

Usage:
  python pred_w_caliber.py --check
  python pred_w_caliber.py --selftest
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
import io
import json
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')
ROOT = NR()
SUPP = RP('PaperB_英文补充材料_PR_20260919.md')
MAIN = RP('PaperB_英文稿_PR_20260919.md')
FROZEN = RP('analysis', 'work', 'convention_rank_result.json')


def squash(s):
    return ' '.join(s.split())


def facts():
    f = json.loads(io.open(FROZEN, encoding='utf-8').read())
    # largest single |rho_all - rho_ans| across the 44 configuration rows, and the smallest Spearman
    worst, top = 0.0, None
    for ds, u in f['units'].items():
        for r in u['rows']:
            d = abs(r['rho_all'] - r['rho_ans'])
            if d > worst:
                worst, top = d, (ds, r['cfg'])
        sp = u['spearman']
        if top is not None:
            pass
    sps = [u['spearman'] for u in f['units'].values()]
    return dict(worst=worst, worst_where=top, sp_min=min(sps), sp_max=max(sps),
                n_units=f['n_units'])


REQUIRED = [
    ('§M.21 states w = G_N/G over the answered items',
     'with\n$w=G_N/G$.', 'with $w=G_N/G$.'),
    ('§M.37 note is printed',
     '**A family with the abstention share as a second input is not an omitted row.**', None),
    ('the note names the ground-truth objection',
     'Proposition 4\'s $w = G_N/G$ is a **ground-truth** quantity', None),
    ('the note names the held-out-item objection',
     'it is not defined on a held-out **item**', None),
    ('the note points at §5.12 for the measured effect',
     'quantifies in §5.12 (one configuration\'s bias moves by up to **48.2 pp**', None),
]


def check():
    sup = io.open(SUPP, encoding='utf-8').read()
    sq = squash(sup)
    fa = facts()
    fails = []
    for name, needle, alt in REQUIRED:
        if squash(needle) not in sq and (alt is None or squash(alt) not in sq):
            fails.append('missing: %s' % name)
    # The two numbers the note quotes must be the frozen ones.
    if abs(fa['worst'] - 48.2) > 0.05:
        fails.append('frozen largest single |delta rho| is %.2f, note says 48.2' % fa['worst'])
    if abs(fa['sp_min'] - 0.476) > 0.001 or abs(fa['sp_max'] - 1.0) > 0.001:
        fails.append('frozen Spearman range is %.3f-%.3f, note says 1.000 -> 0.476'
                     % (fa['sp_min'], fa['sp_max']))
    for x in fails:
        print('MISSING: %s' % x)
    print('PRED-W CALIBER CHECK: %s' % ('PASS' if not fails else 'FAIL'))
    return not fails


def selftest():
    fa = facts()
    ctl = []
    ctl.append(('frozen 48.2 pp is the largest single |delta rho| (%.2f at %s)'
                % (fa['worst'], fa['worst_where']), abs(fa['worst'] - 48.2) < 0.05))
    ctl.append(('frozen Spearman range is %.3f-%.3f' % (fa['sp_min'], fa['sp_max']),
                abs(fa['sp_min'] - 0.476) < 0.001 and abs(fa['sp_max'] - 1.0) < 0.001))
    ctl.append(('the census has four units, not one', fa['n_units'] == 4))

    # Negative control: a calibrator input that is NOT ground truth (the prediction) would not be
    # covered by this argument -- i.e. the objection really is specific to w.
    m21 = io.open(SUPP, encoding='utf-8').read()
    ctl.append(('Prop 4 defines w from gt, not from pred',
                'Let $G=\\sum_i gt_i$ over all items' in m21 and 'gt_i' in m21))

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
    print(json.dumps(facts(), ensure_ascii=False, indent=1))
