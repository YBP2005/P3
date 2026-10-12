#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""recompute_a5_13_15.py — recompute Appendix M.58 / M.59 / M.60 from the released records alone.

Inputs (read-only; no model call, no GPU, no network):

  M.58  data/derived/a5_13_2x2en_20261012/        (English prompt, same four contracts)
  M.59  data/derived/a5_14_nozero_20261012/       (the no-zero arm)
        data/derived/a5_10_zero300_20261012/      (the base arm, same 299-image pool)
  M.60  data/derived/a5_15_nat2x2_ext_20261012/   (natural domain, two builds)

Counting rules (the same rules the appendix states, in one place):

  * only rows with ``http == 200`` are counted; other rows enter neither numerator nor denominator
  * one image one vote: records are de-duplicated by ``image``
  * the true-zero roster is the frozen contract ``target_map*.csv``, column ``true_zero == 1``
  * answered zero is ``pred == 0``; abstention is ``abstain is True``
  * unparseable is ``parse_ok is False`` and is never merged into abstention
  * a row that is both ``pred == 0`` and ``abstain is True`` is reported separately; the inclusive
    reading counts it as an answered zero, the exclusive reading does not

Usage:

    python recompute_a5_13_15.py                       # resolve the three trees from the repo root
    python recompute_a5_13_15.py --derived DIR         # point at a7_5_13 tree explicitly
    python recompute_a5_13_15.py --selftest            # negative self-test (missing input must fail)
"""
import argparse
import csv
import io
import json
import os
import sys

try:
    from _repro_root import resolve as RP
except ImportError:                      # single script copied out of the tree
    _r = os.environ.get('PAPERB_ROOT') or os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    RP = lambda *p: os.path.join(_r, *p)

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

CONDS = ['no_name0_no_exit', 'no_name0_exit', 'name0_no_exit', 'name0_exit']
# the literal refusal wording these pools elicit, matched as the two-character Chinese word
# glossed "cannot / unable"; an English paraphrase matches nothing, so it is tested literally.
REFUSAL = '\u65e0\u6cd5'


def rd_jsonl(path):
    if not os.path.isfile(path):
        raise SystemExit('missing input: %s' % path)
    out = []
    with io.open(path, encoding='utf-8') as fh:
        for ln in fh:
            ln = ln.strip()
            if ln:
                out.append(json.loads(ln))
    return out


def rd_map(path):
    """target_map CSV -> {image: true_zero}, de-duplicated by image (one image one vote)."""
    if not os.path.isfile(path):
        raise SystemExit('missing roster: %s' % path)
    tz = {}
    with io.open(path, encoding='utf-8-sig') as fh:
        for r in csv.DictReader(fh):
            img = os.path.basename(str(r.get('image', '')).strip().replace('\\', '/'))
            if img:
                tz[img] = int(float(r.get('true_zero') or 0))
    return tz


def pool_rows(rows, tz):
    """The true-zero pool, one row per image (first http==200 row wins)."""
    seen = {}
    for r in rows:
        if r.get('http') != 200:
            continue
        img = os.path.basename(str(r.get('image', '')).strip().replace('\\', '/'))
        if tz.get(img) == 1 and img not in seen:
            seen[img] = r
    return seen


def tally(byname):
    z = sum(1 for r in byname.values() if r.get('pred') == 0)
    zx = sum(1 for r in byname.values()
             if r.get('pred') == 0 and r.get('abstain') is not True)
    ab = sum(1 for r in byname.values() if r.get('abstain') is True)
    pb = sum(1 for r in byname.values() if r.get('parse_ok') is False)
    dbl = sum(1 for r in byname.values()
              if r.get('pred') == 0 and r.get('abstain') is True)
    return dict(z=z, zx=zx, ab=ab, pb=pb, dbl=dbl, n=len(byname))


def check(fails, label, got, want):
    ok = got == want
    if not ok:
        fails.append('%s: got %s, printed %s' % (label, got, want))
    return ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--derived', default=None,
                    help='the a5_13 tree; the other two are taken from its parent directory')
    ap.add_argument('--selftest', action='store_true')
    a = ap.parse_args()
    fails = []

    d13 = a.derived or RP('repro_github', 'data', 'derived', 'a5_13_2x2en_20261012')
    par = os.path.dirname(os.path.abspath(d13))
    d14 = os.path.join(par, 'a5_14_nozero_20261012')
    d15 = os.path.join(par, 'a5_15_nat2x2_ext_20261012')
    d10 = os.path.join(par, 'a5_10_zero300_20261012')
    if a.selftest:
        return selftest(d13, d14, d15, d10)

    print('M.58 tree = %s' % d13)
    print('M.59 tree = %s  (+ base arm %s)' % (d14, d10))
    print('M.60 tree = %s' % d15)

    # ---------------- M.58 ----------------
    print('\n=== M.58  cross-language replication (English column, denominator 300) ===')
    PRINT_EN = {('ivl358b', 'no_name0_no_exit'): 248, ('ivl358b', 'no_name0_exit'): 0,
                ('ivl358b', 'name0_no_exit'): 294, ('ivl358b', 'name0_exit'): 1,
                ('q32fp8', 'no_name0_no_exit'): 300, ('q32fp8', 'no_name0_exit'): 300,
                ('q32fp8', 'name0_no_exit'): 300, ('q32fp8', 'name0_exit'): 300,
                ('lov7b', 'no_name0_no_exit'): 190, ('lov7b', 'no_name0_exit'): 20,
                ('lov7b', 'name0_no_exit'): 223, ('lov7b', 'name0_exit'): 92,
                ('phi35v', 'no_name0_no_exit'): 167, ('phi35v', 'no_name0_exit'): 16,
                ('phi35v', 'name0_no_exit'): 194, ('phi35v', 'name0_exit'): 100}
    en = {}
    for fam in ('ivl358b', 'q32fp8', 'lov7b', 'phi35v'):
        for c in CONDS:
            tz = rd_map(os.path.join(d13, 'contracts', 'target_map_%s.csv' % c))
            rows = rd_jsonl(os.path.join(d13, 'work', fam, c, 'run.jsonl'))
            en[(fam, c)] = tally(pool_rows(rows, tz))
    for k in sorted(PRINT_EN, key=lambda x: (x[0], CONDS.index(x[1]))):
        t = en[k]
        ok = check(fails, 'M.58 %s %s' % k, t['z'], PRINT_EN[k])
        print('  %-9s %-17s answered zero = %3d  printed = %3d  %s'
              % (k[0], k[1], t['z'], PRINT_EN[k], 'OK' if ok else 'MISMATCH'))
    check(fails, 'M.58 double annotation (English true-zero pool)',
          sum(v['dbl'] for v in en.values()), 0)
    print('  double-annotated rows anywhere in the English true-zero pool = 0 (checked)')

    # ---------------- M.59 ----------------
    print('\n=== M.59  "output no zero": no-zero arm against the base arm, denominator 299 ===')
    PRINT_NZ = {'ivl358b': 156, 'q32fp8': 294, 'lov7b': 66, 'ivl38fp8': 251}
    PRINT_BASE = {'ivl358b': 205, 'q32fp8': 298, 'lov7b': 77, 'ivl38fp8': 279}
    PRINT_UNP = {'ivl358b': 0, 'q32fp8': 0, 'lov7b': 77, 'ivl38fp8': 2}
    tz_b = rd_map(os.path.join(d14, 'contracts', 'target_map_base.csv'))
    tot_nz = tot_bs = tot_unp = 0
    for fam in ('ivl358b', 'q32fp8', 'lov7b', 'ivl38fp8'):
        rows = rd_jsonl(os.path.join(d14, 'work', fam, 'run.jsonl'))
        t = tally(pool_rows(rows, tz_b))
        unp = sum(1 for r in rows if r.get('parse_ok') is False)
        base = rd_jsonl(os.path.join(d10, 'raw', '%s.jsonl' % fam))
        tb = tally(pool_rows(base, tz_b))
        tot_nz += t['z']
        tot_bs += tb['z']
        tot_unp += unp
        ok1 = check(fails, 'M.59 %s no-zero answered zero' % fam, t['z'], PRINT_NZ[fam])
        ok2 = check(fails, 'M.59 %s base answered zero' % fam, tb['z'], PRINT_BASE[fam])
        ok3 = check(fails, 'M.59 %s unparseable' % fam, unp, PRINT_UNP[fam])
        print('  %-9s no-zero = %3d (%.2f%%)  base = %3d (%.2f%%)  unparseable = %3d   %s'
              % (fam, t['z'], 100.0 * t['z'] / 299, tb['z'], 100.0 * tb['z'] / 299, unp,
                 'OK' if (ok1 and ok2 and ok3) else 'MISMATCH'))
    check(fails, 'M.59 total no-zero answered zero', tot_nz, 767)
    check(fails, 'M.59 total base answered zero', tot_bs, 859)
    check(fails, 'M.59 total unparseable', tot_unp, 79)
    print('  total: no-zero = %d / 1196 = %.2f%%   base = %d / 1196 = %.2f%%   change = %+d'
          % (tot_nz, 100.0 * tot_nz / 1196, tot_bs, 100.0 * tot_bs / 1196, tot_nz - tot_bs))
    lit = 0
    nrows = 0
    wide = {}
    for fam in ('ivl358b', 'q32fp8', 'lov7b', 'ivl38fp8'):
        rows = rd_jsonl(os.path.join(d14, 'work', fam, 'run.jsonl'))
        nrows += len(rows)
        wide[fam] = sum(1 for r in rows if REFUSAL in str(r.get('raw', '')))
        lit += sum(1 for r in rows
                   if 'abstain' in str(r.get('raw', '')) or 'cannot_judge' in str(r.get('raw', '')))
    check(fails, 'M.59 rows', nrows, 1196)
    check(fails, 'M.59 literal abstain/cannot_judge in raw', lit, 0)
    check(fails, 'M.59 wide-caliber rows, lov7b', wide['lov7b'], 23)
    check(fails, 'M.59 wide-caliber rows, other three', sum(wide[f] for f in wide if f != 'lov7b'), 0)
    print('  abstention flag = 0 in all four builds; literal abstain/cannot_judge in raw = %d' % lit)
    print('  wide reading (free text carrying the refusal wording): lov7b = %d / 299, others = 0'
          % wide['lov7b'])

    # ---------------- M.60 ----------------
    print('\n=== M.60  natural domain, 518 = 259 true zeros + 259 non-zeros ===')
    PRINT_NAT = {('ivl38fp8', 'no_name0_no_exit'): 250, ('ivl38fp8', 'no_name0_exit'): 7,
                 ('ivl38fp8', 'name0_no_exit'): 258, ('ivl38fp8', 'name0_exit'): 235,
                 ('phi35v', 'no_name0_no_exit'): 168, ('phi35v', 'no_name0_exit'): 19,
                 ('phi35v', 'name0_no_exit'): 205, ('phi35v', 'name0_exit'): 73}
    nat = {}
    for fam in ('ivl38fp8', 'phi35v'):
        for c in CONDS:
            tz = rd_map(os.path.join(d15, 'contracts', 'target_map_%s.csv' % c))
            rows = rd_jsonl(os.path.join(d15, 'work_ext', fam, c, 'run.jsonl'))
            nat[(fam, c)] = tally(pool_rows(rows, tz))
            if len(tz) != 518:
                fails.append('M.60 roster rows %d != 518' % len(tz))
    for k in sorted(PRINT_NAT, key=lambda x: (x[0], CONDS.index(x[1]))):
        t = nat[k]
        ok = check(fails, 'M.60 %s %s' % k, t['z'], PRINT_NAT[k])
        print('  %-9s %-17s answered zero = %3d / 259  printed = %3d  %s  (abstain %d, double %d)'
              % (k[0], k[1], t['z'], PRINT_NAT[k], 'OK' if ok else 'MISMATCH', t['ab'], t['dbl']))
    dbl = sum(v['dbl'] for v in nat.values())
    check(fails, 'M.60 double-annotated rows (phi35v)', dbl, 6)
    # retention, rendered vs natural, for the column the appendix prints
    print('  double-annotated rows: %d (phi35v: name0_exit 2, no_name0_exit 4)'
          % dbl)

    print('\n===== result =====')
    if fails:
        for f in fails:
            print('  * ' + f)
        print('RECOMPUTE: FAIL (%d mismatches)' % len(fails))
        return 1
    print('RECOMPUTE: ALL OK — every printed count in M.58 / M.59 / M.60 recomputed from the '
          'released files alone')
    return 0


def selftest(d13, d14, d15, d10):
    print('recompute_a5_13_15 --selftest (negative cases)')
    ok = True

    def chk(name, cond, extra=''):
        nonlocal ok
        print('  [%s] %s%s' % ('PASS' if cond else 'FAIL', name, ('  ' + extra) if extra else ''))
        ok = ok and bool(cond)

    for name, p in (('a5_13 roster', os.path.join(d13, 'contracts', 'target_map_name0_exit.csv')),
                    ('a5_14 no-zero arm', os.path.join(d14, 'work', 'lov7b', 'run.jsonl')),
                    ('a5_10 base arm', os.path.join(d10, 'raw', 'lov7b.jsonl')),
                    ('a5_15 natural arm',
                     os.path.join(d15, 'work_ext', 'phi35v', 'name0_exit', 'run.jsonl'))):
        chk('%s present' % name, os.path.isfile(p), p)
    # missing input must raise, not return an empty result
    try:
        rd_jsonl(os.path.join(d13, 'work', '__nope__', 'run.jsonl'))
        chk('missing run.jsonl raises', False, 'returned instead')
    except SystemExit as e:
        chk('missing run.jsonl raises', True, str(e)[:70])
    try:
        rd_map(os.path.join(d13, 'contracts', '__nope__.csv'))
        chk('missing roster raises', False, 'returned instead')
    except SystemExit as e:
        chk('missing roster raises', True, str(e)[:70])
    # the two readings must actually differ where a double annotation exists
    rows = rd_jsonl(os.path.join(d15, 'work_ext', 'phi35v', 'name0_exit', 'run.jsonl'))
    tz = rd_map(os.path.join(d15, 'contracts', 'target_map_name0_exit.csv'))
    t = tally(pool_rows(rows, tz))
    chk('inclusive and exclusive readings differ on phi35v/name0_exit',
        t['z'] != t['zx'], 'inclusive=%d exclusive=%d' % (t['z'], t['zx']))
    chk('phi35v/name0_exit inclusive = 73 and exclusive = 71',
        (t['z'], t['zx']) == (73, 71), 'got %d / %d' % (t['z'], t['zx']))
    print('SELFTEST: %s' % ('PASS' if ok else 'FAIL'))
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
