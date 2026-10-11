# -*- coding: utf-8 -*-
"""Independent recomputation of the budget-matched readings, straight from raw/*.jsonl.

This is deliberately NOT the analyzer: it re-derives the quantities from the per-call records with its
own code path, so a reader can check the released analyzer against a second implementation. It reads
manifest.csv and raw/*.jsonl only, makes no model call, needs no GPU, and touches no network.

Per-call values are the median over the three service starts, as in the analyzer and in the frozen
protocol. Ground truth is taken per level (the D2 repair); the density cost proxy is ceil(d/8) (the D1
repair). The criterion is Spearman(full-level, budget-matched) == 1.0 and the top knob unchanged.
"""
import collections
import io
import itertools
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ALIASES = ['ivl358b', 'lov7b', 'q32fp8']
KNOBS = ['density', 'res']
LEVELS = {'density': ['24', '30', '36'], 'res': ['px640', 'px704', 'px832']}
STARTS = ['start1', 'start2', 'start3']
N_LEVELS = 3


# ----------------------------------------------------------------------------- statistics
def spearman(x, y):
    def rank(v):
        order = sorted(range(len(v)), key=lambda i: v[i])
        r = [0.0] * len(v)
        i = 0
        while i < len(order):
            j = i
            while j + 1 < len(order) and v[order[j + 1]] == v[order[i]]:
                j += 1
            avg = (i + j) / 2.0 + 1.0
            for k in range(i, j + 1):
                r[order[k]] = avg
            i = j + 1
        return r

    rx, ry = rank(x), rank(y)
    n = len(x)
    mx = sum(rx) / n
    my = sum(ry) / n
    num = sum((rx[i] - mx) * (ry[i] - my) for i in range(n))
    dx = math.sqrt(sum((rx[i] - mx) ** 2 for i in range(n)))
    dy = math.sqrt(sum((ry[i] - my) ** 2 for i in range(n)))
    return num / (dx * dy) if dx and dy else float('nan')


def upper_median(xs):
    return sorted(xs)[len(xs) // 2]


def wilson(k, n, z=1.96):
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5) / d
    return max(0.0, c - h), min(1.0, c + h)


def cost_of(knob, label, shipped=False):
    if knob == 'density':
        if shipped:
            # the defect as first shipped: one parser for both knobs, so a label like '24', '30', '36'
            # is read as its characters after the first -> 4, 0, 6
            return float(math.ceil(int(str(label)[1:]) / 8.0))
        return float(math.ceil(int(label) / 8.0))     # D1 repair: bare numeric label
    return float(int(label[2:]) ** 2)                 # res: px<digits>


# ----------------------------------------------------------------------------- data
def read_manifest():
    """-> (man, phys2logical)

    `item` is the LOGICAL name and `image` the PHYSICAL path. For the resolution knob the three levels
    share one logical name (`res_0000.png`) while the physical files differ
    (`images/res_0000_px640.png`, `..._px704.png`, `..._px832.png`), so the physical path is the only
    safe key for a raw record and the logical name the only safe key for a unit's item set. Both maps
    are returned; keying on the physical basename alone silently collapses the three res levels.
    """
    man, phys2logical = {}, {}
    path = os.path.join(HERE, 'manifest.csv')
    with io.open(path, encoding='utf-8-sig') as fh:
        head = fh.readline().rstrip('\n').split(',')
        for line in fh:
            v = line.rstrip('\n').split(',')
            if len(v) != len(head):
                continue
            r = dict(zip(head, v))
            man[(r['item'], r['knob'], r['level'])] = r
            phys2logical[(os.path.basename(r['image']), r['knob'], r['level'])] = r['item']
    return man, phys2logical


def read_raw(phys2logical):
    """-> recs[(alias, knob, level, start)][logical_item] = prediction (None when unparseable/abstained)"""
    recs, unresolved = {}, 0
    base = os.path.join(HERE, 'raw')
    for fn in sorted(os.listdir(base)):
        if not fn.endswith('.jsonl'):
            continue
        parts = fn[:-6].split('__')
        if len(parts) != 4:
            continue
        alias, knob, level, start = parts
        per = {}
        with io.open(os.path.join(base, fn), encoding='utf-8') as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                r = json.loads(line)
                if str(r.get('http')) != '200':
                    continue
                phys = os.path.basename(str(r.get('image', '')))
                logical = phys2logical.get((phys, knob, level))
                if logical is None:
                    unresolved += 1
                    continue
                p = r.get('pred')
                per[logical] = int(p) if isinstance(p, (int, float)) and not r.get('abstain') else None
        recs[(alias, knob, level, start)] = per
    if unresolved:
        raise SystemExit('unresolved physical image names: %d (manifest/data mismatch)' % unresolved)
    return recs


def build_units(man, recs, per_level_gt, shipped_cost=False):
    units = {}
    for alias in ALIASES:
        for knob in KNOBS:
            lvs = LEVELS[knob]
            # per item and level: median over starts of the parseable readings
            vals = {}
            for lv in lvs:
                want = [it for (it, k, l) in man if k == knob and l == lv]
                for img in want:
                    acc = []
                    for st in STARTS:
                        v = recs.get((alias, knob, lv, st), {}).get(img)
                        if v is not None:
                            acc.append(v)
                    if len(acc) == len(STARTS):
                        vals[(lv, img)] = sorted(acc)[len(acc) // 2]
            common = set.intersection(*[set(i for (l, i) in vals if l == lv) for lv in lvs])
            common = sorted(common)
            if len(common) < 20:
                continue
            mae, rho = [], []
            for lv in lvs:
                if per_level_gt:
                    gt = [float(man[(i, knob, lv)]['count_gt']) for i in common]
                else:
                    gt = [float(man[(i, knob, lvs[0])]['count_gt']) for i in common]
                pred = [float(vals[(lv, i)]) for i in common]
                mae.append(sum(abs(pred[t] - gt[t]) for t in range(len(common))) / len(common))
                sg = sum(gt)
                rho.append(100.0 * (sum(pred) - sg) / sg if sg else float('nan'))
            units['%s / %s' % (alias, knob)] = dict(
                mae=mae, cost=[cost_of(knob, lv, shipped_cost) for lv in lvs], rho=rho,
                span_full=max(rho) - min(rho), common_n=len(common))
    return units


def measure(units, B, C):
    span_bm, usable = {}, []
    for u, d in units.items():
        best = None
        for i, j in itertools.combinations(range(N_LEVELS), 2):
            ci, cj = d['cost'][i], d['cost'][j]
            if ci is None or cj is None:
                continue
            me, ce = max(d['mae'][i], d['mae'][j]), max(ci, cj)
            mi, cm = min(d['mae'][i], d['mae'][j]), min(ci, cj)
            if mi <= 0 or cm <= 0:
                continue
            if me / mi <= 1 + B and ce / cm <= C:
                delta = abs(d['rho'][i] - d['rho'][j])
                best = delta if best is None else max(best, delta)
        if best is not None:
            span_bm[u] = best
            usable.append(u)
    top_full = max(units, key=lambda u: units[u]['span_full'])
    top_bm = max(usable, key=lambda u: span_bm[u]) if usable else None
    out = dict(n_units=len(units), n_usable=len(usable),
               frac_comparable=len(usable) / len(units), top_full=top_full, top_bm=top_bm,
               top_changed=(top_full != top_bm))
    out['not_computable'] = sorted(set(units) - set(usable))
    if len(usable) >= 2:
        out['spearman'] = spearman([units[u]['span_full'] for u in usable],
                                   [span_bm[u] for u in usable])
        out['retention_median'] = upper_median([span_bm[u] / units[u]['span_full'] for u in usable])
    else:
        out['spearman'] = float('nan')
        out['retention_median'] = float('nan')
    out['pass'] = (out['spearman'] == out['spearman'] and abs(out['spearman'] - 1.0) < 1e-12
                   and not out['top_changed'])
    return out


def main():
    if not os.path.isdir(os.path.join(HERE, 'raw')):
        sys.exit('raw/ not found next to this script')
    man, phys2logical = read_manifest()
    recs = read_raw(phys2logical)
    print('manifest rows = %d  |  raw cells = %d  |  http==200 rows = %d'
          % (len(man), len(recs), sum(len(v) for v in recs.values())))
    for tag, gt, shipped in (
            ('pre-registered caliber (per-level GT, cost ceil(d/8))', True, False),
            ('as first shipped (GT reused from level 0, density cost mis-parsed)', False, True)):
        units = build_units(man, recs, per_level_gt=gt, shipped_cost=shipped)
        print('\n--- %s ---' % tag)
        print('  common items per unit: %s'
              % ', '.join('%s=%d' % (u, d['common_n']) for u, d in sorted(units.items())))
        for B, C in ((0.10, 2.0), (0.25, 4.0)):
            r = measure(units, B, C)
            lo, hi = wilson(r['n_usable'], r['n_units'])
            print('  (B,C)=(%.2f,%.1f)  usable=%d/%d = %.4f [Wilson %.3f, %.3f]  Spearman=%.4f  '
                  'retention=%.3f  top change=%s  => %s'
                  % (B, C, r['n_usable'], r['n_units'], r['frac_comparable'], lo, hi,
                     r['spearman'], r['retention_median'], r['top_changed'],
                     'PASS' if r['pass'] else 'FAIL'))
            if r['not_computable']:
                print('       not computable: %s' % ', '.join(r['not_computable']))
        r = measure(units, float('inf'), 2.0)
        print('  cost ceiling released (C=2), error budget kept=inf: Spearman=%.4f retention=%.3f '
              'top change=%s => %s'
              % (r['spearman'], r['retention_median'], r['top_changed'],
                 'PASS' if r['pass'] else 'FAIL'))
        r = measure(units, 0.10, float('inf'))
        print('  error budget released (B=0.10), cost ceiling kept=inf: Spearman=%.4f retention=%.3f '
              'top change=%s => %s'
              % (r['spearman'], r['retention_median'], r['top_changed'],
                 'PASS' if r['pass'] else 'FAIL'))


if __name__ == '__main__':
    main()
