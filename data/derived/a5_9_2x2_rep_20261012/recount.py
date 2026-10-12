# -*- coding: utf-8 -*-
"""Recompute every number in criteria_tables.md from raw/ and contracts/ alone."""
import io
import json
import math
import os
import random

HERE = os.path.dirname(os.path.abspath(__file__))
COND = ['no_name0_no_exit', 'no_name0_exit', 'name0_no_exit', 'name0_exit']
BUILDS = ['ivl358b', 'q32fp8', 'lov7b']
Z = 1.6448536269514722


def wilson(k, n, z=Z):
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return max(0.0, (c - h) / d), min(1.0, (c + h) / d)


def boot(vals, n_boot=2000, seed=20261011):
    rnd = random.Random(seed)
    n = len(vals)
    out = []
    for _ in range(n_boot):
        s = 0.0
        for _ in range(n):
            s += vals[rnd.randrange(n)]
        out.append(s / n)
    out.sort()
    return out[int(0.05 * n_boot)], out[int(0.95 * n_boot)]


def rows(p):
    return [json.loads(l) for l in io.open(p, encoding='utf-8', newline='').read().splitlines() if l.strip()]


def truth(p):
    t = io.open(p, encoding='utf-8', newline='').read().splitlines()
    h = t[0].split(',')
    zi, ii = h.index('true_zero'), h.index('image')
    return set(os.path.basename(l.split(',')[ii]) for l in t[1:]
               if l.strip() and l.split(',')[zi].strip() == '1')


print('build    condition          rep1 rep2 rep3   mean  range  rate   bootLB bootUB wilLB  wilUB')
for b in BUILDS:
    for c in COND:
        tz = truth(os.path.join(HERE, 'contracts', 'target_map_%s.csv' % c))
        per, reps = {}, []
        for k in (1, 2, 3):
            r = rows(os.path.join(HERE, 'raw', b, 'start%d' % k, '%s.jsonl' % c))
            reps.append(len([x for x in r if x['image'] in tz and x.get('is_zero') is True]))
            for x in r:
                if x['image'] in tz:
                    per.setdefault(x['image'], []).append(1.0 if x.get('is_zero') is True else 0.0)
        vals = [sum(v) / len(v) for v in per.values()]
        mean = sum(reps) / 3.0
        bl, bu = boot(vals)
        wl, wu = wilson(int(round(mean)), 100)
        print('%-8s %-18s %4d %4d %4d %6.2f %6d %.4f %.4f %.4f %.4f %.4f'
              % (b, c, reps[0], reps[1], reps[2], mean, max(reps) - min(reps), mean / 100.0, bl, bu, wl, wu))
