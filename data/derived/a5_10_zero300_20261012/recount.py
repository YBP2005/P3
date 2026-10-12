# -*- coding: utf-8 -*-
"""Recompute every number in criteria_tables.md from raw/ and pool/ alone."""
import io
import json
import math
import os

HERE = os.path.dirname(os.path.abspath(__file__))
BUILDS = ['ivl358b', 'q32fp8', 'lov7b', 'ivl38fp8']
Z = 1.6448536269514722


def wilson(k, n, z=Z):
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return max(0.0, (c - h) / d), min(1.0, (c + h) / d)


def rows(p):
    return [json.loads(l) for l in io.open(p, encoding='utf-8', newline='').read().splitlines() if l.strip()]


def truth(p):
    t = io.open(p, encoding='utf-8', newline='').read().splitlines()
    h = t[0].split(',')
    zi, ii = h.index('true_zero'), h.index('image')
    return set(os.path.basename(l.split(',')[ii]) for l in t[1:]
               if l.strip() and l.split(',')[zi].strip() == '1')


tot = {'299': [0, 0], '148': [0, 0]}
for pool, pfx, tzf, den in (('148', 'pool148_', 'target_map_148.csv', 148),
                            ('299', '', 'target_map.csv', 299)):
    tz = truth(os.path.join(HERE, 'pool', tzf))
    print('pool %s (%d true-zero images)' % (pool, len(tz)))
    for b in BUILDS:
        r = rows(os.path.join(HERE, 'raw', '%s%s.jsonl' % (pfx, b)))
        sel = [x for x in r if x['image'] in tz]
        z = len([x for x in sel if x.get('is_zero') is True])
        bad = len([x for x in sel if x.get('parse_ok') is False])
        tot[pool][0] += z
        tot[pool][1] += len(sel)
        print('  %-9s %3d/%3d = %5.1f%%  Wilson UB95 %.4f  unparseable %3d  parseable-row rate %5.1f%%'
              % (b, z, len(sel), 100.0 * z / len(sel), wilson(z, len(sel))[1], bad,
                 100.0 * z / (len(sel) - bad) if len(sel) > bad else float('nan')))
for pool in ('148', '299'):
    z, n = tot[pool]
    print('  pooled %s: %d/%d = %.1f%%' % (pool, z, n, 100.0 * z / n))
