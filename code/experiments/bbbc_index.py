#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""bbbc_index.py — 解析 BBBC005 文件名 → 计数/焦距索引（CPU）
命名: SIMCEPImages_<well>_C<count>_F<focus>_s<site>_w<w>.TIF
输出: /root/bbbc/index.csv  + 分布报告
"""
import csv, glob, os, re, collections
import numpy as np
from PIL import Image

ROOT = '/root/bbbc'
PAT = re.compile(r'SIMCEPImages_([A-Z]\d+)_C(\d+)_F(\d+)_s(\d+)_w(\d+)\.TIF$')
rows = []
for sub in ['BBBC005_v1_images', 'synthetic_2_ground_truth', 'BBBC005_v1_ground_truth']:
    d = os.path.join(ROOT, sub)
    if not os.path.isdir(d):
        continue
    for p in glob.glob(os.path.join(d, '*.TIF')):
        m = PAT.search(os.path.basename(p))
        if not m:
            continue
        rows.append(dict(set=sub, item=os.path.basename(p)[:-4], well=m.group(1),
                         count=int(m.group(2)), focus=int(m.group(3)),
                         site=int(m.group(4)), w=int(m.group(5)), path=p))
print('解析到 %d 个文件' % len(rows))
by = collections.Counter(r['set'] for r in rows)
print('按目录:', dict(by))

imgs = [r for r in rows if r['set'] == 'BBBC005_v1_images']
print('\n【BBBC005_v1_images】%d 张' % len(imgs))
cs = sorted({r['count'] for r in imgs}); fs = sorted({r['focus'] for r in imgs})
print('  count 取值 %d 个: %s ... %s' % (len(cs), cs[:12], cs[-6:]))
print('  focus 取值 %d 个: %s ... %s' % (len(fs), fs[:10], fs[-6:]))
cnt_f = collections.Counter(r['focus'] for r in imgs)
print('  每个 F 档的图像数: %s' % dict(sorted(cnt_f.items())[:12]))
cnt_c = collections.Counter(r['count'] for r in imgs)
top = cnt_c.most_common(8)
print('  每个 C 值的图像数(前8): %s' % top)
print('  每 (C,F) 组合的图像数中位: %.0f' % np.median(list(collections.Counter((r['count'], r['focus']) for r in imgs).values())))

# 图像尺寸抽样
for r in imgs[:3]:
    try:
        im = Image.open(r['path'])
        print('  样本 %s  size=%s mode=%s' % (r['item'], im.size, im.mode))
    except Exception as e:
        print('  样本读取失败', type(e).__name__)

out = '/root/bbbc/index.csv'
with open(out, 'w', encoding='utf-8-sig', newline='') as f:
    w = csv.DictWriter(f, fieldnames=['set', 'item', 'well', 'count', 'focus', 'site',
                                      'w', 'path'])
    w.writeheader()
    for r in rows:
        w.writerow(r)
print('\n索引 -> %s (%d 行)' % (out, len(rows)))

# 供 G2 用的两个子集
sub1 = [r for r in imgs if r['focus'] == 1]
print('\n子集1(在焦 F=1): %d 张, count 范围 %d..%d' % (len(sub1), min(r['count'] for r in sub1),
                                                  max(r['count'] for r in sub1)))
for c in [10, 30, 50, 70, 90]:
    n = len([r for r in imgs if r['count'] == c])
    print('  子集2 候选 C=%d: %d 张 (F 档 %d 个)' % (c, n, len({r['focus'] for r in imgs if r['count'] == c})))
