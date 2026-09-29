#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""mk_b4.py — Batch 4 清单
E5c  时序重设计：真实 ST-A 图做**降采样斜坡**（第 0 帧=原生，IVL 在此 100% 作答），
     从而让"弃权起始"真的由可辨性驱动（修 Batch 2 的地板效应）
E3v  契约 × 预算扩到航拍域 VisDrone
A3b  小计数域补 TallyQA（用其自带 question 作逐行提示词，count=groundtruth）
"""
import csv, glob, os, random, sys
from PIL import Image

OUT = '/root/b4'
os.makedirs(OUT, exist_ok=True)
os.makedirs('/root/b4/seq3', exist_ok=True)
HDR = ['exp', 'item', 'domain', 'path', 'gt', 'arm', 'budget', 'nsample', 'temp', 'prompt']
rows = []

STAT = '/root/dense/shanghaitech/counts.csv'
gt = {}
for r in csv.DictReader(open(STAT, encoding='utf-8-sig')):
    k = {x.lower(): x for x in r}
    if (r.get(k.get('part', ''), '') or '').startswith('part_A') and r.get(k.get('split', ''), '') == 'test':
        gt[os.path.splitext(os.path.basename(r[k.get('file', 'file')]))[0]] = int(r[k.get('count', 'count')])
IDIR = '/root/dense/shanghaitech/images/part_A_test'
names = [n for n in sorted(gt) if os.path.exists(os.path.join(IDIR, n + '.jpg'))]

# ---------- E5c：降采样斜坡（第 0 帧原生 → 第 29 帧 15%） ----------
random.Random(41).shuffle(names)
CLIPS, FRAMES = 30, 30
for nm in names[:CLIPS]:
    im0 = Image.open(os.path.join(IDIR, nm + '.jpg')).convert('RGB')
    W, H = im0.size
    for t in range(FRAMES):
        sc = 1.0 - 0.85 * t / float(FRAMES - 1)
        nw, nh = max(64, int(W * sc)), max(64, int(H * sc))
        im = im0 if (nw, nh) == (W, H) else im0.resize((nw, nh), Image.LANCZOS)
        p = '/root/b4/seq3/%s_f%02d.jpg' % (nm, t)
        im.save(p, 'JPEG', quality=92)
        rows.append(['E5c', '%s_f%02d' % (nm, t), 'st_a', p, gt[nm], 'base', 0, 1, 0.0, ''])

# ---------- E3v：VisDrone 契约 × 预算 ----------
vd = {}
for r in csv.DictReader(open('/root/aerial/gt_visdrone.csv', encoding='utf-8-sig')):
    vd[r['item']] = int(r['gt'])
vn = [n for n in sorted(vd) if os.path.exists('/root/aerial/visdrone/images/%s.jpg' % n)]
for n in vn[:200]:
    for arm in ['base', 'forbid0']:
        for b in [0, 200000]:
            rows.append(['E3v', n, 'visdrone', '/root/aerial/visdrone/images/%s.jpg' % n,
                         vd[n], arm, b, 1, 0.0, ''])

# ---------- A3b：TallyQA（question 作提示词） ----------
for cf in glob.glob('/root/ext/tallyqa/*.csv'):
    rs = list(csv.DictReader(open(cf, encoding='utf-8-sig')))
    if not rs:
        continue
    cols = {c.lower().strip(): c for c in rs[0]}
    cf_, cc = cols.get('file'), cols.get('groundtruth') or cols.get('count')
    cq = cols.get('question')
    if not cf_ or not cc:
        continue
    base = os.path.dirname(cf)
    got = []
    for r in rs:
        try:
            n = int(float(r[cc]))
        except Exception:
            continue
        if not (1 <= n <= 100):
            continue
        fn = r[cf_]
        for h in [os.path.join(base, fn), os.path.join(base, 'images', fn),
                  os.path.join(base, 'images', os.path.basename(fn))]:
            if os.path.exists(h):
                q = (r.get(cq, '') if cq else '') or ''
                q = q.replace(',', '，').replace('"', '').strip()
                pr = ('%s 以JSON格式输出：{"count": 数量}，只输出JSON。' % q) if q else ''
                got.append((os.path.splitext(os.path.basename(h))[0], h, n, pr))
                break
    if len(got) > 300:
        got.sort(key=lambda x: x[2])
        import numpy as _np
        got = [got[i] for i in _np.linspace(0, len(got) - 1, 300).astype(int)]
    print('  tallyqa: 命中 %d 张' % len(got))
    for it, p, n, pr in got:
        rows.append(['A3b', it, 'tallyqa', p, n, 'base', 0, 1, 0.0, pr])

with open(os.path.join(OUT, 'manifest.csv'), 'w', encoding='utf-8-sig', newline='') as f:
    w = csv.writer(f); w.writerow(HDR)
    for r in rows:
        w.writerow(r)
import collections
print('清单 %d 行 -> %s' % (len(rows), os.path.join(OUT, 'manifest.csv')))
for k, v in collections.Counter(r[0] for r in rows).items():
    print('  %-6s %6d' % (k, v))
