# -*- coding: utf-8 -*-
"""A5-3 建池：解包 FSC-147 全量 → 建 manifest（含逐图类名/GT/切分，并标出 A5-1 已用的 300 图）。"""
import zipfile, os, io, csv, json, sys, collections, hashlib

Z = '/root/fsc147_full/FSC147_full.zip'
OUT = '/root/fsc147_full/pool'
EX = os.path.join(OUT, 'images')
os.makedirs(EX, exist_ok=True)

z = zipfile.ZipFile(Z)
names = z.namelist()
imgs = [n for n in names if n.lower().endswith(('.jpg', '.jpeg', '.png'))]
print('条目 %d ｜ 图像 %d' % (len(names), len(imgs)))
print('样例:', imgs[:3])
tops = collections.Counter(n.split('/')[0] for n in names)
print('顶层:', tops.most_common(6))

# ① 解包图像（跳过已存在）
n_new = 0
for n in imgs:
    base = os.path.basename(n)
    dst = os.path.join(EX, base)
    if os.path.exists(dst):
        continue
    with z.open(n) as src, open(dst, 'wb') as fh:
        fh.write(src.read())
    n_new += 1
print('新解出图像 %d ｜ 目录现有 %d' % (n_new, len(os.listdir(EX))))

# ② 类名 / GT / 切分
cls = {}
for ln in io.open('/root/fsc147/ImageClasses_FSC147.txt', encoding='utf-8'):
    ln = ln.rstrip('\r\n')
    if '\t' in ln:
        a, b = ln.split('\t', 1)
    else:
        p = ln.split(None, 1)
        a, b = (p + [''] * 2)[:2]
    cls[a.strip()] = b.strip()

ann = json.load(io.open('/root/fsc147/annotation_FSC147_384.json', encoding='utf-8'))
splits = json.load(io.open('/root/fsc147/Train_Test_Val_FSC_147.json', encoding='utf-8'))
split_of = {}
for k, v in splits.items():
    if not isinstance(v, list):
        continue
    for stem in v:
        split_of[str(stem)] = k

used = set()
p = '/root/fsc147/sample_test_ids.txt'
if os.path.exists(p):
    for ln in io.open(p, encoding='utf-8'):
        if ln.strip():
            used.add(ln.strip())

rows = []
for fn in sorted(os.listdir(EX)):
    stem = os.path.splitext(fn)[0]
    key = fn if fn in ann else (stem if stem in ann else (stem + '.jpg' if stem + '.jpg' in ann else None))
    pts = ann.get(key, {}).get('points') if key else None
    rows.append(dict(image=fn, item=stem, class_name=cls.get(fn, cls.get(stem, '')),
                     count_gt=(len(pts) if pts is not None else ''),
                     split=split_of.get(stem, split_of.get(fn, 'unsplit')),
                     used_in_a51=int(fn in used or stem in used)))

with io.open(os.path.join(OUT, 'manifest.csv'), 'w', encoding='utf-8', newline='') as fh:
    w = csv.DictWriter(fh, fieldnames=['image', 'item', 'class_name', 'count_gt', 'split', 'used_in_a51'])
    w.writeheader()
    for r in rows:
        w.writerow(r)

avail = [r for r in rows if not r['used_in_a51']]
miss_cls = sum(1 for r in avail if not r['class_name'])
miss_gt = sum(1 for r in avail if r['count_gt'] == '')
zero_gt = sum(1 for r in avail if str(r['count_gt']) == '0')
rep = ['# A5-3 建池报告（FSC-147 全量）', '',
       '- 解出图像总数：**%d**' % len(rows),
       '- 其中 A5-1 已用：**%d** ⇒ 本实验可用框：**%d**' % (len(rows) - len(avail), len(avail)),
       '- 可用框内 缺类名：**%d**｜缺 GT：**%d**｜GT=0 的图：**%d**' % (miss_cls, miss_gt, zero_gt),
       '- 切分分布（可用框）：%s' % dict(collections.Counter(r['split'] for r in avail))]
open(os.path.join(OUT, 'POOL_REPORT.md'), 'w', encoding='utf-8').write('\n'.join(rep) + '\n')
print('\n'.join(rep))
print('manifest →', os.path.join(OUT, 'manifest.csv'))
