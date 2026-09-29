#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""mk_e5d.py — E5d：真实 ST-A 图 + 模糊斜坡（起点在可答区间）
E5b 用了合成点阵（起点就弃权）、E5c 用了降采样（不诱发弃权），两者都没看到"起始"。
E5d 用真实图 + 逐渐加模糊：第 0 帧=原生（IVL 在此 0% 弃权，确属可答区间），
第 29 帧=重度模糊（σ=8），从而给出干净的"弃权起始"。
额外嵌套一条**对照序列**（同样 30 帧，但用降采样）以同时验证"模糊 vs 分辨率"的分工。

清单列: exp,item,domain,path,gt,arm,budget,nsample,temp,prompt
"""
import csv, os, random, sys
from PIL import Image, ImageFilter

OUT = '/root/b5'
os.makedirs('/root/b5/blur', exist_ok=True)
os.makedirs('/root/b5/scale', exist_ok=True)
HDR = ['exp', 'item', 'domain', 'path', 'gt', 'arm', 'budget', 'nsample', 'temp', 'prompt']
rows = []

base_st = '/root/dense/shanghaitech'
gt = {}
for r in csv.DictReader(open(os.path.join(base_st, 'counts.csv'), encoding='utf-8-sig')):
    k = {x.lower(): x for x in r}
    if (r.get(k.get('part', ''), '') or '').startswith('part_A') and r.get(k.get('split', ''), '') == 'test':
        gt[os.path.splitext(os.path.basename(r[k.get('file', 'file')]))[0]] = int(r[k.get('count', 'count')])
IDIR = os.path.join(base_st, 'images', 'part_A_test')
names = [n for n in sorted(gt) if os.path.exists(os.path.join(IDIR, n + '.jpg'))]
random.Random(47).shuffle(names)
CLIPS, FRAMES = 30, 30
SIG_MAX = 8.0

for nm in names[:CLIPS]:
    im0 = Image.open(os.path.join(IDIR, nm + '.jpg')).convert('RGB')
    W, H = im0.size
    for t in range(FRAMES):
        # 序列 A：模糊斜坡（可辨性下降，分辨率不变）
        sig = SIG_MAX * t / float(FRAMES - 1)
        im = im0 if sig == 0 else im0.filter(ImageFilter.GaussianBlur(sig))
        p = '/root/b5/blur/%s_f%02d.jpg' % (nm, t)
        im.save(p, 'JPEG', quality=92)
        rows.append(['E5d', '%s_f%02d' % (nm, t), 'st_a', p, gt[nm], 'base', 0, 1, 0.0, ''])
        # 序列 B：降采样对照（同样的帧数，只改分辨率）
        sc = 1.0 - 0.85 * t / float(FRAMES - 1)
        nw, nh = max(64, int(W * sc)), max(64, int(H * sc))
        im2 = im0 if (nw, nh) == (W, H) else im0.resize((nw, nh), Image.LANCZOS)
        p2 = '/root/b5/scale/%s_f%02d.jpg' % (nm, t)
        im2.save(p2, 'JPEG', quality=92)
        rows.append(['E5e', '%s_f%02d' % (nm, t), 'st_a', p2, gt[nm], 'base', 0, 1, 0.0, ''])

with open(os.path.join(OUT, 'manifest.csv'), 'w', encoding='utf-8-sig', newline='') as f:
    w = csv.writer(f); w.writerow(HDR)
    for r in rows:
        w.writerow(r)
import collections
print('清单 %d 行 -> %s' % (len(rows), os.path.join(OUT, 'manifest.csv')))
for k, v in collections.Counter(r[0] for r in rows).items():
    print('  %-5s %5d' % (k, v))
