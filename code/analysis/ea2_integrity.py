# -*- coding: utf-8 -*-
"""ea2_integrity.py — E2 产物的**冻结前完整性核验**（对照断言，不是描述）。

设计承诺了三件事，任何一件不成立，后续统计就不可比：
  ① 真零池的每一行 `gt` 都必须是 **0**（池的定义）；
  ② 同一 (build, serving, lang, stratum) 下，`base/permit/channel` **三臂的 item 集必须完全相同**
     （"同批图上的同 item 配对"）；
  ③ 同一 (build, lang, stratum, arm) 在 **3 次服务之间 item 集必须完全相同**（换服务不换图）。
另核：CN 与 EN 两侧 item 集一致（同批图的语义等价英译）。
用法：python -u ea2_integrity.py [--root D:\\deepseek\\PaperB\\analysis\\ea2_z0]
"""
import argparse
import collections
import csv
import glob
import io
import os
import re
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')


def read(f):
    rows = list(csv.DictReader(io.open(f, encoding='utf-8-sig', errors='replace')))
    items = set()
    bad_gt = []
    for r in rows:
        it = str(r.get('item') or '')
        if '#' in it:
            continue
        items.add(it)
        try:
            if float(r.get('gt')) != 0.0:
                bad_gt.append((it, r.get('gt')))
        except (TypeError, ValueError):
            bad_gt.append((it, r.get('gt')))
    return items, bad_gt, len(rows)


ap = argparse.ArgumentParser()
ap.add_argument('--root', default=r'<WORKDIR>\PaperB\analysis\ea2_z0')
A = ap.parse_args()

by = collections.defaultdict(dict)     # (build, srv, lang, stratum) -> arm -> items
meta = {}
for f in glob.glob(os.path.join(A.root, '*', '*.csv')):
    dirn = os.path.basename(os.path.dirname(f))
    m = re.match(r'^(cn|en)_(.+)_s(\d)$', dirn)
    if not m:
        continue
    lang, build, srv = m.group(1), m.group(2), int(m.group(3))
    mm = re.match(r'^e1_(.+?)_(z0easy|z0hard)_(base|permit|channel)_.*\.csv$', os.path.basename(f))
    if not mm:
        continue
    model, stratum, arm = mm.group(1), mm.group(2), mm.group(3)
    items, bad_gt, n = read(f)
    by[(build, srv, lang, stratum)][arm] = items
    meta[(build, srv, lang, stratum, arm)] = (n, len(bad_gt), bad_gt[:2])

print('读到 %d 个 (build, 服务, 语言, 分层) 组' % len(by))
fail = 0
print('\n① gt==0 核验')
for k, arms in sorted(by.items()):
    for arm in ('base', 'permit', 'channel'):
        if arm not in arms:
            continue
        n, nbad, sample = meta[k + (arm,)]
        if nbad:
            print('   !! %s/%s 非零 gt 行 %d 例（%s）' % (k, arm, nbad, sample))
            fail += 1
if not fail:
    print('   ✓ 全部行 gt==0（池定义成立）')

print('\n② 同组三臂 item 集一致')
bad2 = 0
for k, arms in sorted(by.items()):
    if len(arms) < 3:
        print('   !! %s 只有臂 %s' % (k, sorted(arms)))
        bad2 += 1
        continue
    a, b, c = arms['base'], arms['permit'], arms['channel']
    if not (a == b == c):
        print('   !! %s item 集不一致：base %d / permit %d / channel %d；差集 base-permit %s'
              % (k, len(a), len(b), len(c), list(a - b)[:3]))
        bad2 += 1
print('   %s' % ('✓ 全部一致（%d 组）' % len(by) if not bad2 else '问题组 %d' % bad2))

print('\n③ 三次服务之间 item 集一致（同 build/语言/分层）')
bad3 = 0
for build in sorted({k[0] for k in by}):
    for lang in ('cn', 'en'):
        for stratum in ('z0easy', 'z0hard'):
            sets = [by[(build, s, lang, stratum)]['base'] for s in (1, 2, 3)
                    if (build, s, lang, stratum) in by and 'base' in by[(build, s, lang, stratum)]]
            if len(sets) < 2:
                continue
            if not all(s == sets[0] for s in sets):
                print('   !! %s/%s/%s 三次服务 item 集不一致（%s）'
                      % (build, lang, stratum, [len(s) for s in sets]))
                bad3 += 1
print('   %s' % ('✓ 全部一致' if not bad3 else '问题组 %d' % bad3))

print('\n④ CN/EN item 集一致（同 build/服务/分层）')
bad4 = 0
for build in sorted({k[0] for k in by}):
    for srv in (1, 2, 3):
        for stratum in ('z0easy', 'z0hard'):
            kc, ke = (build, srv, 'cn', stratum), (build, srv, 'en', stratum)
            if kc in by and ke in by and 'base' in by[kc] and 'base' in by[ke]:
                if by[kc]['base'] != by[ke]['base']:
                    print('   !! %s/s%d/%s CN/EN item 集不一致' % (build, srv, stratum))
                    bad4 += 1
print('   %s' % ('✓ 全部一致' if not bad4 else '问题组 %d' % bad4))

print('\n结论：%s' % ('全部对照通过，可冻结' if not (fail + bad2 + bad3 + bad4)
                     else '**有 %d 项未通过，冻结前须查**' % (fail + bad2 + bad3 + bad4)))
sys.exit(0 if not (fail + bad2 + bad3 + bad4) else 1)
