#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""mk_b3.py — Batch 3 清单生成
A3ext  计数-偏差曲线扩展到更多小计数域：CountBench / FSC147（两族均跑）
E5b    时序重设计（修地板效应）：真实 ST-A 图上做**从可答区间开始**的模糊斜坡
"""
import csv, glob, os, random, sys
import numpy as np
from PIL import Image, ImageFilter

OUT = '/root/b3'
os.makedirs(OUT, exist_ok=True)
os.makedirs('/root/b3/seq2', exist_ok=True)
HDR = ['exp', 'item', 'domain', 'path', 'gt', 'arm', 'budget', 'nsample', 'temp']
rows = []
report = []

# ---------- A3ext：找小计数域 ----------
def counts_files():
    cands = []
    for pat in ['/root/ext/*/counts.csv', '/root/ext/*/*.csv', '/root/ext/*/*/counts.csv',
                '/root/ext/fsc147/*.csv', '/root/ext/fsc147/**/*.csv',
                '/root/*/counts.csv']:
        cands += glob.glob(pat, recursive=True)
    return sorted(set(cands))


def pick_images(csvpath, ds, want=300, cap=1200):
    rows_ = list(csv.DictReader(open(csvpath, encoding='utf-8-sig')))
    if not rows_:
        return []
    cols = {c.lower().strip(): c for c in rows_[0]}
    cfile = cols.get('file') or cols.get('image') or cols.get('path') or cols.get('item')
    ccount = (cols.get('count') or cols.get('number') or cols.get('gt')
              or cols.get('n') or cols.get('num'))
    if not cfile or not ccount:
        report.append('  %s: 列名不识别 %s' % (ds, list(cols)))
        return []
    base = os.path.dirname(csvpath)
    out = []
    for r in rows_:
        try:
            n = int(float(r[ccount]))
        except Exception:
            continue
        if not (1 <= n <= cap):
            continue
        fn = r[cfile]
        hits = [os.path.join(base, fn), os.path.join(base, 'images', fn),
                os.path.join(base, 'images', os.path.basename(fn))]
        for h in hits:
            if os.path.exists(h):
                out.append((os.path.splitext(os.path.basename(h))[0], h, n))
                break
    # 按计数对数分箱均匀抽样
    if len(out) > want:
        out.sort(key=lambda x: x[2])
        idx = np.linspace(0, len(out) - 1, want).astype(int)
        out = [out[i] for i in idx]
    report.append('  %s: 命中 %d 张（计数 %d–%d）' % (ds, len(out),
                 min([x[2] for x in out]) if out else 0, max([x[2] for x in out]) if out else 0))
    return out


report.append('=== A3ext 数据域 ===')
for csvpath in counts_files():
    ds = os.path.basename(os.path.dirname(csvpath))
    if ds in ('dense', 'ext', 'aerial', 'b3', 'b2', 'bbbc', 'root'):
        continue
    got = pick_images(csvpath, ds)
    for it, p, n in got:
        rows.append(['A3', it, ds + '_obj', p, n, 'objects', 0, 1, 0.0])

# ---------- E5b：真实图上的模糊斜坡 ----------
report.append('=== E5b 时序重设计 ===')
gt = {}
base_st = '/root/dense/shanghaitech'
for r in csv.DictReader(open(os.path.join(base_st, 'counts.csv'), encoding='utf-8-sig')):
    k = {x.lower(): x for x in r}
    if (r.get(k.get('part', ''), '') or '').startswith('part_A') and r.get(k.get('split', ''), '') == 'test':
        gt[os.path.splitext(os.path.basename(r[k.get('file', 'file')]))[0]] = int(r[k.get('count', 'count')])
idir = os.path.join(base_st, 'images', 'part_A_test')
names = [n for n in sorted(gt) if os.path.exists(os.path.join(idir, n + '.jpg'))]
random.Random(23).shuffle(names)
CLIPS, FRAMES = 30, 30
SIGMA_MAX = 9.0
nclip = 0
for name in names[:CLIPS]:
    im0 = Image.open(os.path.join(idir, name + '.jpg')).convert('RGB')
    for t in range(FRAMES):
        sig = SIGMA_MAX * t / float(FRAMES - 1)     # 第 0 帧=原图（可答区间），末帧重度模糊
        im = im0 if sig == 0 else im0.filter(ImageFilter.GaussianBlur(sig))
        p = '/root/b3/seq2/%s_f%02d.jpg' % (name, t)
        im.save(p, 'JPEG', quality=92)
        rows.append(['E5b', '%s_f%02d' % (name, t), 'st_a', p, gt[name], 'base', 0, 1, 0.0])
    nclip += 1
report.append('  E5b: %d clip × %d 帧 = %d 帧（模糊 0 → %.1f）' % (nclip, FRAMES, nclip * FRAMES, SIGMA_MAX))

with open(os.path.join(OUT, 'manifest.csv'), 'w', encoding='utf-8-sig', newline='') as f:
    w = csv.writer(f); w.writerow(HDR)
    for r in rows:
        w.writerow(r)
import collections
print('\n'.join(report))
print('\n清单 %d 行 -> %s' % (len(rows), os.path.join(OUT, 'manifest.csv')))
for k, v in collections.Counter(r[0] for r in rows).items():
    print('  %-6s %6d 行' % (k, v))
for k, v in sorted(collections.Counter(r[2] for r in rows if r[0] == 'A3').items()):
    print('  A3 域 %-14s %5d' % (k, v))
