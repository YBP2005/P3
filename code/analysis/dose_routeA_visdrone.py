#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""dose_routeA_visdrone.py — the numbers behind §5.8's Route A sentence, recomputed from the
frozen per-item prompt-strength dose records.

Why this exists: §5.8 says that tiling "lifts the suppressed directional authority of prompts in
the aerial domain (+13.9% whole-image to **+160.4%** at 3×3)" and points at Appendices M.8 and
M.11 -- but neither appendix printed those two numbers, so the claim had no in-submission source.
This script recomputes them, and the adjacent ShanghaiTech-A / UCF-QNRF cells, from the frozen
per-item dose files, so the M.8 paragraph is a recomputation anchor rather than a transcription.

Sources (frozen, per item, 400 VisDrone items x 7 levels whole-image, 2 levels at 3x3):
  analysis/data/pod_mirror/dose_results/dose_visdrone.csv           whole image, L1-L7
  analysis/data/pod_mirror/dose_tile_results/dose_tile3_visdrone.csv  3x3, L1 and L4 only

Usage:
  python dose_routeA_visdrone.py            # recompute and print
  python dose_routeA_visdrone.py --check    # recompute + assert the M.8 paragraph
  python dose_routeA_visdrone.py --selftest # negative controls
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
import io
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')
ROOT = NR()
PM = RP('analysis', 'data', 'pod_mirror')
SUPP = RP('PaperB_英文补充材料_PR_20260919.md')
ANOM = 1e5

FILES = [
    ('VisDrone whole', RP('analysis', 'data', 'pod_mirror', 'dose_results', 'dose_visdrone.csv')),
    ('VisDrone 3x3', RP('analysis', 'data', 'pod_mirror', 'dose_tile_results', 'dose_tile3_visdrone.csv')),
    ('ShanghaiTech-A whole', RP('analysis', 'data', 'pod_mirror', 'dose_results', 'dose_st_a.csv')),
    ('UCF-QNRF whole', RP('analysis', 'data', 'pod_mirror', 'dose_results', 'dose_ucf.csv')),
]
L1, L4 = 'L1_随便给', 'L4_中性'

# The main text prints these; every one must be reproduced.
PRINTED = {
    ('VisDrone whole', L1): 13.9,
    ('VisDrone 3x3', L1): 160.4,
    ('VisDrone whole', L4): -71.3,
    ('VisDrone 3x3', L4): -17.7,
}


def load(path):
    return list(csv.DictReader(io.open(path, encoding='utf-8-sig')))


def stats(rows, level):
    sub = [r for r in rows if r['level'] == level]
    kept = []
    for r in sub:
        try:
            gt, pr = float(r['gt']), float(r['pred'])
        except (TypeError, ValueError):
            continue                       # unparsed / refused-without-value
        if pr >= ANOM or gt <= 0:
            continue                       # canonical filter: anomaly and zero-GT dropped
        kept.append((gt, pr, r))
    sg = sum(g for g, _, _ in kept)
    sp = sum(p for _, p, _ in kept)
    rho = 100.0 * (sp - sg) / sg if sg else float('nan')
    n_zero = sum(1 for r in sub if str(r.get('zero', '0')) == '1')
    return dict(rho=rho, n_kept=len(kept), n_level=len(sub),
                abst=100.0 * n_zero / len(sub) if sub else float('nan'))


def compute():
    res = {}
    for name, path in FILES:
        rows = load(path)
        levels = sorted(set(r['level'] for r in rows))
        res[name] = {lv: stats(rows, lv) for lv in levels}
        print('== %s  (%d rows, %d levels)' % (name, len(rows), len(levels)))
        for lv in levels:
            d = res[name][lv]
            mark = ''
            if (name, lv) in PRINTED:
                mark = '   [printed %.1f]' % PRINTED[(name, lv)]
            print('   %-16s rho=%+9.2f  abst=%6.2f%%  kept=%d/%d%s'
                  % (lv, d['rho'], d['abst'], d['n_kept'], d['n_level'], mark))
    return res


def check_printed(res):
    bad = []
    for (name, lv), want in PRINTED.items():
        got = res[name][lv]['rho']
        if abs(got - want) > 0.05:
            bad.append('%s / %s: recomputed %+.2f vs printed %+.1f' % (name, lv, got, want))
    # the amplification the skeleton records as 11.5x
    amp = res['VisDrone 3x3'][L1]['rho'] / res['VisDrone whole'][L1]['rho']
    if not (11.0 < amp < 12.0):
        bad.append('amplification %.2fx outside the recorded 11.5x' % amp)
    return bad


DECL = [
    'the loosest of the seven prompt-strength levels moves $\\rho$ from **+13.9%** at whole image '
    'to **+160.4%** at 3×3',
    'an **11.5×** amplification',
    'the superseded unfiltered figure for that cell was **+1277.6%**',
]


def squash(s):
    return ' '.join(s.split())


def check():
    res = compute()
    fails = check_printed(res)
    text = squash(io.open(SUPP, encoding='utf-8').read())
    for d in DECL:
        if squash(d) not in text:
            fails.append('M.8 Route-A declaration missing: %s' % d[:70])
    for x in fails:
        print('MISSING: %s' % x)
    print('DOSE-ROUTEA CHECK: %s' % ('PASS' if not fails else 'FAIL'))
    return not fails


def selftest():
    ctl = []
    res = compute()
    ctl.append(('recomputed values == printed values', not check_printed(res)))

    # (1) The canonical filter must matter: without it the aerial 3x3 L1 cell is inflated by
    #     a single item (pred 100,025 against gt 24).  That is exactly why the skeleton records
    #     a superseded +1277.6% for this cell.
    rows = load(RP('analysis', 'data', 'pod_mirror', 'dose_tile_results', 'dose_tile3_visdrone.csv'))
    sub = [r for r in rows if r['level'] == L1]
    def rho_of(keep):
        sg = sum(float(r['gt']) for r in keep)
        sp = sum(float(r['pred']) for r in keep)
        return 100.0 * (sp - sg) / sg
    unf = rho_of([r for r in sub if float(r['gt']) > 0])
    can = res['VisDrone 3x3'][L1]['rho']
    ctl.append(('unfiltered %.1f%% >> canonical %.1f%%: the filter is load-bearing' % (unf, can),
                unf > can + 500))

    # (2) The single driving item must be identifiable.
    worst = max((r for r in sub if float(r['gt']) > 0), key=lambda r: float(r['pred']))
    ctl.append(('the driving item has pred %s vs gt %s'
                % (worst['pred'], worst['gt']),
                float(worst['pred']) >= ANOM and float(worst['gt']) == 24.0))

    # (3) Tiling must *raise* the aerial prompt authority -- if it did not, the §5.8 sentence
    #     would be backwards.
    ctl.append(('3x3 authority > whole-image authority (%.1f > %.1f)'
                % (res['VisDrone 3x3'][L1]['rho'], res['VisDrone whole'][L1]['rho']),
                res['VisDrone 3x3'][L1]['rho'] > res['VisDrone whole'][L1]['rho']))

    # (4) Abstention must fall under tiling, which is Route A's whole point.
    ctl.append(('3x3 abstention below whole-image (%.1f%% < %.1f%%)'
                % (res['VisDrone 3x3'][L4]['abst'], res['VisDrone whole'][L4]['abst']),
                res['VisDrone 3x3'][L4]['abst'] < res['VisDrone whole'][L4]['abst']))

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
    compute()
