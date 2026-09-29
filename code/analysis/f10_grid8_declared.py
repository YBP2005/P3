#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""f10_grid8_declared.py — the 8-level detector-τ spans behind §4.1, recomputed from the
frozen per-item ladder records, and the F.10 declaration that makes them traceable.

Why this exists: §4.1 quotes the zero-shot all-detections ladder as **63.1-156.0 pp** on the
8-level grid, but F.10's table prints only the **16-level** column (78.3 / 105.0 / 156.0), so
`63.1` had no in-submission source.  This script recomputes the whole 8-level grid -- both
calibers, both ladders, all three input sizes -- from the frozen per-item CSVs and asserts
every value the manuscript prints, so the F.10 declaration is a recomputation anchor rather
than a copied table.

Sources (frozen, per item):
  COCO-pretrained   analysis/data/pod_mirror/A/det_yolo_ladder_yolo12n.csv      200 items x 8 tau x 3 imgsz
  in-domain         analysis/data/pod_mirror/A/det_yolo_ladder_visdrone_det.csv 400 items x 8 tau x 3 imgsz

Usage:
  python f10_grid8_declared.py            # recompute and print
  python f10_grid8_declared.py --check    # recompute + assert the F.10 declaration
  python f10_grid8_declared.py --selftest # negative controls
"""
import argparse
import csv
import io
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')
ROOT = r'<WORKDIR>\PaperB'
LAD = os.path.join(ROOT, 'analysis', 'data', 'pod_mirror', 'A')
SUPP = os.path.join(ROOT, 'PaperB_英文补充材料_PR_20260919.md')
ANOM = 1e5

LADDERS = [
    ('zero-shot COCO', 'det_yolo_ladder_yolo12n.csv', 200),
    ('in-domain', 'det_yolo_ladder_visdrone_det.csv', 400),
]
IMGSZ = ['640', '1024', '1536']
CALIBERS = [('all-detections', 'n_det'), ('person-matched', 'n_det_person')]

# What the submission prints (8-level grid).  §4.1 quotes the endpoints; F.10 will quote the grid.
PRINTED = {
    ('zero-shot COCO', 'all-detections'): {'640': 63.1, '1024': 94.3, '1536': 156.0},
    ('zero-shot COCO', 'person-matched'): {'640': 16.4, '1024': 30.3, '1536': 55.5},
    ('in-domain', 'all-detections'):      {'640': 352.8, '1024': 438.1, '1536': 508.3},
    ('in-domain', 'person-matched'):      {'640': 95.9, '1024': 159.3, '1536': 195.7},
}


def load(path):
    with io.open(path, encoding='utf-8-sig') as f:
        return [r for r in csv.DictReader(f)]


def rho(pairs):
    sg = sum(g for g, _ in pairs)
    sp = sum(p for _, p in pairs)
    return 100.0 * (sp - sg) / sg if sg else None


def ladder_spans(name, fname, n_items):
    """Pooled rho at each tau on the common item intersection, then max - min."""
    rows = load(os.path.join(LAD, fname))
    out = {}
    for cal, col in CALIBERS:
        for sz in IMGSZ:
            sub = [r for r in rows if r['imgsz'] == sz]
            taus = sorted(set(r['tau'] for r in sub), key=float)
            per = {t: {} for t in taus}
            for r in sub:
                try:
                    gt, pr = float(r['gt']), float(r[col])
                except (TypeError, ValueError):
                    continue
                if pr >= ANOM or gt <= 0:
                    continue
                per[r['tau']][r['item']] = (gt, pr)
            keys = None
            for t in taus:
                keys = set(per[t]) if keys is None else (keys & set(per[t]))
            keys = sorted(keys)
            seq = [(t, rho([per[t][k] for k in keys])) for t in taus]
            seq = [(t, v) for t, v in seq if v is not None]
            vals = [v for _, v in seq]
            out[(cal, sz)] = dict(n_items=len(keys), n_levels=len(seq),
                                  lo=min(vals), hi=max(vals), span=max(vals) - min(vals))
    return out


def compute():
    res = {}
    for name, fname, n in LADDERS:
        spans = ladder_spans(name, fname, n)
        res[name] = spans
        print('== %s  (%s, expected %d items)' % (name, fname, n))
        for (cal, sz), d in sorted(spans.items()):
            print('   %-16s @%-5s levels=%d items=%d  span=%8.2f  -> %.1f  [printed %.1f]'
                  % (cal, sz, d['n_levels'], d['n_items'], d['span'],
                     d['span'], PRINTED[(name, cal)][sz]))
    return res


def check_printed(res):
    bad = []
    for name, _f, _n in LADDERS:
        for cal, _c in CALIBERS:
            for sz in IMGSZ:
                d = res[name][(cal, sz)]
                want = PRINTED[(name, cal)][sz]
                if abs(d['span'] - want) > 0.05:
                    bad.append('%s / %s / @%s: recomputed %.2f vs printed %.1f'
                               % (name, cal, sz, d['span'], want))
    return bad


DECL = [
    '**63.1 / 94.3** on the all-detections caliber (§4.1, 8 levels) against **20.2 / 33.7** '
    'and **78.3 / 105.0** here (16 levels)',
    '**The 8-level column is recomputed cell for cell from the per-item ladder records in '
    '`f10_grid8_declared.py`, which asserts all twelve of its values**',
    'the in-domain 640 row is **95.85** pp, printed **95.8** here and **95.9** in §4.1',
    'the in-domain 1536 span endpoint is **508.35** pp, printed **508.4** here and **508.3** there',
]


def squash(s):
    return ' '.join(s.split())


def check():
    res = compute()
    fails = check_printed(res)
    text = squash(io.open(SUPP, encoding='utf-8').read())
    for d in DECL:
        if squash(d) not in text:
            fails.append('F.10 declaration missing: %s' % d[:70])
    for x in fails:
        print('MISSING: %s' % x)
    print('F10-8LEVEL CHECK: %s' % ('PASS' if not fails else 'FAIL'))
    return not fails


def selftest():
    """Negative controls.  Each must fire."""
    ctl = []
    res = compute()

    # (1) The recomputation must reproduce every printed 8-level value.
    ctl.append(('recomputed 8-level grid == printed values', not check_printed(res)))

    # (2) The 8-level grid must NOT equal the 16-level column: if it did, the whole
    #     "two grids" declaration would be empty.  F.10's 16-level zero-shot all-det is
    #     78.3 / 105.0 / 156.0.
    eight = [res['zero-shot COCO'][('all-detections', s)]['span'] for s in IMGSZ]
    sixteen = [78.3, 105.0, 156.0]
    ctl.append(('8-level zero-shot differs from the 16-level column at 640/1024',
                abs(eight[0] - sixteen[0]) > 1.0 and abs(eight[1] - sixteen[1]) > 1.0))

    # (3) The two calibers must not be the same quantity (otherwise F.10's caliber split is void).
    a = res['in-domain'][('all-detections', '1536')]['span']
    p = res['in-domain'][('person-matched', '1536')]['span']
    ctl.append(('all-detections != person-matched at in-domain @1536 (%.1f vs %.1f)' % (a, p),
                abs(a - p) > 50))

    # (4) Dropping the loosest tau must change the span -- i.e. the span really is a
    #     functional of the admitted level set, as Proposition 3 says.
    rows = load(os.path.join(LAD, 'det_yolo_ladder_yolo12n.csv'))
    sub = [r for r in rows if r['imgsz'] == '640']
    taus = sorted(set(r['tau'] for r in sub), key=float)
    per = {t: {} for t in taus}
    for r in sub:
        per[r['tau']][r['item']] = (float(r['gt']), float(r['n_det']))
    keys = sorted(set.intersection(*[set(per[t]) for t in taus]))
    full = [rho([per[t][k] for k in keys]) for t in taus]
    drop = [rho([per[t][k] for k in keys]) for t in taus[1:]]
    ctl.append(('dropping the loosest level shrinks the span (%.1f -> %.1f)'
                % (max(full) - min(full), max(drop) - min(drop)),
                (max(drop) - min(drop)) < (max(full) - min(full)) - 1.0))

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
