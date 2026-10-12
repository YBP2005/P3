# -*- coding: utf-8 -*-
"""Recompute every number in criteria_tables.md from raw/, pool/ and contracts/ alone."""
import io
import json
import hashlib
import os

HERE = os.path.dirname(os.path.abspath(__file__))
COND = ['no_name0_no_exit', 'no_name0_exit', 'name0_no_exit', 'name0_exit']
BUILDS = ['ivl358b', 'lov7b', 'q32fp8']


def rows(p):
    return [json.loads(l) for l in io.open(p, encoding='utf-8', newline='').read().splitlines() if l.strip()]


def truth(p):
    t = io.open(p, encoding='utf-8', newline='').read().splitlines()
    h = t[0].split(',')
    zi, ii = h.index('true_zero'), h.index('image')
    return set(os.path.basename(l.split(',')[ii]) for l in t[1:]
               if l.strip() and l.split(',')[zi].strip() == '1')


print('contract md5 (natural pool copy)')
for c in COND:
    p = os.path.join(HERE, 'contracts', 'contract_%s.txt' % c)
    print('  %-18s %s' % (c, hashlib.md5(io.open(p, 'rb').read()).hexdigest()))

man = io.open(os.path.join(HERE, 'pool', 'manifest.csv'), encoding='utf-8', newline='').read().splitlines()
print('pool manifest rows (excluding header) = %d' % (len(man) - 1))

for b in BUILDS:
    for c in COND:
        tz = truth(os.path.join(HERE, 'contracts', 'target_map_%s.csv' % c))
        r = rows(os.path.join(HERE, 'raw', b, '%s.jsonl' % c))
        sel = [x for x in r if x['image'] in tz]
        z = len([x for x in sel if x.get('is_zero') is True])
        dbl = len([x for x in sel if x.get('pred') == 0 and x.get('abstain') is True])
        bad = len([x for x in sel if x.get('parse_ok') is False])
        print('  %-8s %-18s %3d/%3d = %5.1f%%  double-flagged %d  unparseable %d'
              % (b, c, z, len(sel), 100.0 * z / len(sel), dbl, bad))
