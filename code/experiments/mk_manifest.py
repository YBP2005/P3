#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""mk_manifest.py — 生成 Batch 2 的全部清单，并合成 E5 的时序帧

E1  契约 × 域        : 3 域 × 4 契约（base/forbid0/range/choice）× ~200 图
E3  契约 × 预算 2×2  : ucf × {base,forbid0} × {native,200k} × 120 图
E7  采样稳定性       : 200 图（按可辨性分低/高各半）× 8 次 × T=1
E4  显微域           : BBBC005 在焦全计数档 + 固定计数 × 16 焦距档
E5  时序稳定性       : 合成 20 clip × 30 帧（模糊斜坡），另存帧图
"""
import csv, math, os, random, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

OUT = '/root/b2'
os.makedirs(OUT, exist_ok=True)
os.makedirs('/root/b2/seq', exist_ok=True)
HDR = ['exp', 'item', 'domain', 'path', 'gt', 'arm', 'budget', 'nsample', 'temp']
rows = []


def gt_of(ds):
    g = {}
    if ds == 'st_a':
        d = '/root/dense/shanghaitech/images/part_A_test'
        for r in csv.DictReader(open('/root/dense/shanghaitech/counts.csv', encoding='utf-8-sig')):
            if r.get('part') == 'part_A' and r.get('split') == 'test':
                g[os.path.splitext(os.path.basename(r['file']))[0]] = int(r['count'])
        return d, g
    if ds == 'ucf':
        d = '/root/dense/ucf_qnrf/UCF-QNRF_ECCV18/Test'
        for r in csv.DictReader(open('/root/dense/ucf_qnrf/counts.csv', encoding='utf-8-sig')):
            if r['split'] == 'Test':
                g[os.path.splitext(os.path.basename(r['file']))[0]] = int(r['count'])
        return d, g
    d = '/root/aerial/visdrone/images'
    for r in csv.DictReader(open('/root/aerial/gt_visdrone.csv', encoding='utf-8-sig')):
        g[r['item']] = int(r['gt'])
    return d, g


DS = {}
for ds in ['st_a', 'ucf', 'visdrone']:
    d, g = gt_of(ds)
    names = [n for n in sorted(g) if os.path.exists(os.path.join(d, n + '.jpg'))]
    DS[ds] = (d, g, names)
    print('%-9s 可用图 %d' % (ds, len(names)))

# ---------- E1 契约 × 域 ----------
for ds in ['st_a', 'ucf', 'visdrone']:
    d, g, names = DS[ds]
    sel = names[:200]
    for n in sel:
        for arm in ['base', 'forbid0', 'range', 'choice']:
            rows.append(['E1', n, ds, os.path.join(d, n + '.jpg'), g[n], arm, 0, 1, 0.0])

# ---------- E3 契约 × 预算 ----------
d, g, names = DS['ucf']
for n in names[:120]:
    for arm in ['base', 'forbid0']:
        for b in [0, 200000]:
            rows.append(['E3', n, 'ucf', os.path.join(d, n + '.jpg'), g[n], arm, b, 1, 0.0])

# ---------- E7 采样稳定性（低/高可辨性各半） ----------
cand = []
for ds in ['ucf', 'visdrone']:
    d, g, names = DS[ds]
    for n in names:
        p = os.path.join(d, n + '.jpg')
        cand.append((ds, n, p, g[n]))
cand.sort(key=lambda x: x[2])
random.Random(11).shuffle(cand)
lo = cand[:100]; hi = cand[-100:]
for ds, n, p, gv in lo + hi:
    rows.append(['E7', n, ds, p, gv, 'base', 0, 8, 1.0])

# ---------- E4 显微域（BBBC005） ----------
idx = list(csv.DictReader(open('/root/bbbc/index.csv', encoding='utf-8-sig')))
main = [r for r in idx if r['set'] == 'BBBC005_v1_images']
in_focus = [r for r in main if int(r['focus']) == 1]
print('BBBC 在焦 %d 张' % len(in_focus))
for r in in_focus:
    rows.append(['E4', r['item'], 'bbbc', r['path'], int(r['count']), 'cells', 0, 1, 0.0])
focus_axis = [r for r in main if int(r['count']) == 53]
focus_axis.sort(key=lambda r: int(r['focus']))
random.Random(5).shuffle(focus_axis)
picked, seen = [], {}
for r in focus_axis:
    f = int(r['focus'])
    if seen.get(f, 0) < 10:
        picked.append(r); seen[f] = seen.get(f, 0) + 1
print('BBBC 焦距档 %d 张（%d 个 F 档）' % (len(picked), len(seen)))
for r in picked:
    rows.append(['E4', r['item'], 'bbbc', r['path'], int(r['count']), 'cells', 0, 1, 0.0])

# ---------- E5 合成时序（模糊斜坡） ----------
rng = np.random.RandomState(3)
N, CANVAS, DOTS = 300, 1024, 6
CLIPS, FRAMES = 20, 30
for c in range(CLIPS):
    seed = rng.randint(0, 10 ** 6)
    rr = np.random.RandomState(seed)
    # 抖动栅格排布，避免完美规则性
    cols = int(math.ceil(math.sqrt(N)))
    step = CANVAS / (cols + 1)
    pts = []
    for i in range(N):
        cx = (i % cols) + 1
        cy = (i // cols) + 1
        if cy * step > CANVAS:
            continue
        pts.append((cx * step + rr.uniform(-step * .25, step * .25),
                    cy * step + rr.uniform(-step * .25, step * .25)))
    for t in range(FRAMES):
        ramp = t / float(FRAMES - 1)
        blur = 0.4 + 6.0 * ramp                      # 模糊斜坡
        base = Image.new('L', (CANVAS, CANVAS), 235)
        dr = ImageDraw.Draw(base)
        for (x, y) in pts:
            dr.ellipse([x - DOTS, y - DOTS, x + DOTS, y + DOTS], fill=25)
        base = base.filter(ImageFilter.GaussianBlur(blur))
        p = '/root/b2/seq/c%02d_f%02d.jpg' % (c, t)
        base.convert('RGB').save(p, 'JPEG', quality=92)
        rows.append(['E5', 'c%02d_f%02d' % (c, t), 'seq', p, len(pts), 'base', 0, 1, 0.0])
print('E5 帧数 %d' % (CLIPS * FRAMES))

with open(os.path.join(OUT, 'manifest.csv'), 'w', encoding='utf-8-sig', newline='') as f:
    w = csv.writer(f); w.writerow(HDR)
    for r in rows:
        w.writerow(r)
import collections
print('\n清单 %d 行 -> %s' % (len(rows), os.path.join(OUT, 'manifest.csv')))
for k, v in collections.Counter(r[0] for r in rows).items():
    print('  %-4s %6d 行' % (k, v))
