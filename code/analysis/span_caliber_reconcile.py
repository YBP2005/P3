#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""span_caliber_reconcile.py — reconcile the three unit sets whose spans for the same knob differ by
3-10x in this paper.

Charge (CONFIRMED): the same knob's span reads **26.8-53.7 pp** in §F.2, **85.9 / 97.7** in
§F.9 and **160.7 / 259.4** in §M.37's unit table -- a 3-10x difference with no sentence in the main text
converting between them, so a reader cannot tell whether the paper contradicts itself.

It does not: the three rows are three **different unit sets** measured on three different objects, and §F.2's
own caliber note already forbids subtracting one from another. This script reads the three tables out of the
supplement, asserts every value it reconciles, and checks that the reconciliation paragraph is printed.

Usage:
  python span_caliber_reconcile.py            # print the reconciliation
  python span_caliber_reconcile.py --check    # recompute + assert the §F.2 paragraph
  python span_caliber_reconcile.py --selftest # negative controls
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
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')
SUPP = RP('PaperB_英文补充材料_PR_20260919.md')

# What the three tables print (asserted, not assumed).
F2 = {
    'output contract': '26.8–53.7 pp',
    'tiling level': '1.9–28.6 pp',
}
F9_ISOTONIC_OUTPUT_CONTRACT = [85.9, 97.7]
M37_OUTPUT_CONTRACT = [160.7, 259.4]
M37_TILING = [260.4, 114.6, 61.6, 40.5, 40.0, 32.9]


def section(text, start_pat, end_pat):
    i = text.index(start_pat)
    j = text.index(end_pat, i + 1)
    return text[i:j]


def sup():
    return io.open(SUPP, encoding='utf-8').read()


def f2_row(text, knob):
    seg = section(text, '### F.2 ', '### F.3 ')
    for line in seg.split('\n'):
        if line.startswith('| ') and knob.split()[0].lower() in line.lower():
            cells = [c.strip().strip('*') for c in line.strip('|').split('|')]
            return cells
    return None


def f9_isotonic(text):
    seg = section(text, '### F.9 ', '### F.10 ')
    vals = []
    for line in seg.split('\n'):
        if line.startswith('| VLM, output contract'):
            cells = [c.strip().strip('*') for c in line.strip('|').split('|')]
            vals.append(float(cells[2]))
    return sorted(vals)


def m37_units(text):
    seg = section(text, '**The 36 units themselves.**', 'The unit-name prefix gives')
    out = {}
    for line in seg.split('\n'):
        if not line.startswith('| ') or line.startswith('| unit') or set(line) <= set('|- '):
            continue
        cells = [c.strip() for c in line.strip('|').split('|')]
        if len(cells) < 2:
            continue
        try:
            out[cells[0]] = float(cells[1])
        except ValueError:
            continue
    return out


def reconcile(text, verbose=True):
    r = {}
    f2 = f2_row(text, 'output contract')
    r['f2_output_contract'] = f2[3] if f2 else None
    r['f9_iso'] = f9_isotonic(text)
    u = m37_units(text)
    r['m37_oc'] = sorted(v for k, v in u.items() if k.startswith('VLM·output contract'))
    r['m37_tile'] = sorted((v for k, v in u.items() if k.startswith('VLM·tiling')), reverse=True)
    if verbose:
        print('§F.2  output contract : %s' % r['f2_output_contract'])
        print('§F.9  output contract (isotonic): %s' % r['f9_iso'])
        print('§M.37 output contract (per unit): %s' % r['m37_oc'])
        print('§M.37 tiling          (per unit): %s' % r['m37_tile'])
        print('§F.2  tiling level    : %s' % (f2_row(text, 'tiling') or [None] * 4)[3])
    return r


def problems(r):
    bad = []
    if r['f2_output_contract'] != F2['output contract']:
        bad.append('§F.2 output-contract span is %s, expected %s'
                   % (r['f2_output_contract'], F2['output contract']))
    if r['f9_iso'] != sorted(F9_ISOTONIC_OUTPUT_CONTRACT):
        bad.append('§F.9 isotonic output-contract values are %s, expected %s'
                   % (r['f9_iso'], sorted(F9_ISOTONIC_OUTPUT_CONTRACT)))
    if r['m37_oc'] != sorted(M37_OUTPUT_CONTRACT):
        bad.append('§M.37 output-contract units are %s, expected %s'
                   % (r['m37_oc'], sorted(M37_OUTPUT_CONTRACT)))
    if r['m37_tile'] != sorted(M37_TILING, reverse=True):
        bad.append('§M.37 tiling units are %s, expected %s'
                   % (r['m37_tile'], sorted(M37_TILING, reverse=True)))
    return bad


DECL = [
    '**Reconciling the three unit sets.**',
    'The table above reports **one span per knob**, pooling that knob over its domains on the '
    '**uncalibrated** pooled relative deviation, with the detector row flagged below; §F.9 splits '
    '**four of the six** knobs into **ten (knob × domain) units** and reports them '
    '**isotonic-calibrated**; §M.37 rebuilds **36 configuration-level units** from the same per-item '
    'records, uncalibrated.',
    'the three rows differ by **3.0–9.7×**',
    'Subtracting one row from another is the construction §F.10\'s caliber rule already forbids',
]


def squash(s):
    return ' '.join(s.split())


def check():
    text = sup()
    r = reconcile(text)
    fails = problems(r)
    sq = squash(text)
    for d in DECL:
        if squash(d) not in sq:
            fails.append('reconciliation declaration missing: %s' % d[:70])
    for x in fails:
        print('MISSING: %s' % x)
    print('SPAN-RECONCILE CHECK: %s' % ('PASS' if not fails else 'FAIL'))
    return not fails


def selftest():
    text = sup()
    r = reconcile(text, verbose=False)
    ctl = [('the three tables read as expected', not problems(r))]

    # (1) The three unit sets must genuinely disagree -- otherwise there is nothing to reconcile and
    #     the paragraph would be padding.
    lo = float(F2['output contract'].split('–')[0].replace(' pp', ''))
    ctl.append(('§M.37/§F.2 ratio spans %.1fx-%.1fx (the charge was 3-10x)'
                % (min(M37_OUTPUT_CONTRACT) / float(F2['output contract'].split('–')[1].replace(' pp', '')),
                   max(M37_OUTPUT_CONTRACT) / lo),
                abs(max(M37_OUTPUT_CONTRACT) / lo - 9.7) < 0.1))

    # (2) §F.9 is isotonic-calibrated and §M.37 is not: their values must differ.
    ctl.append(('§F.9 (isotonic) != §M.37 (uncalibrated) for the same knob',
                set(F9_ISOTONIC_OUTPUT_CONTRACT) != set(M37_OUTPUT_CONTRACT)))

    # (3) The tiling knob must be absent from §F.9's ten units -- the reconciliation table says so.
    seg = section(text, '### F.9 ', '### F.10 ')
    ctl.append(('§F.9 has no tiling unit', 'tiling' not in seg.lower()))

    # (4) The declared range spans two different pairings of the ends, and they differ by more than 3x --
    #     a single naive ratio would understate or overstate the discrepancy.
    lo_f2 = float(F2['output contract'].split('–')[0].replace(' pp', ''))
    hi_f2 = float(F2['output contract'].split('–')[1].replace(' pp', ''))
    low_ratio = min(M37_OUTPUT_CONTRACT) / hi_f2
    high_ratio = max(M37_OUTPUT_CONTRACT) / lo_f2
    ctl.append(('the two end-pairings give %.1fx and %.1fx (declared 3.0-9.7x)'
                % (low_ratio, high_ratio),
                abs(low_ratio - 3.0) < 0.1 and abs(high_ratio - 9.7) < 0.1
                and high_ratio / low_ratio > 3.0))

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
    reconcile(sup())
