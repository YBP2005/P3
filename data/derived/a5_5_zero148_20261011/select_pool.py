# -*- coding: utf-8 -*-
"""实验 2 池：FSC-147 的 COCO 子集抽 150 图 + 配"该图不存在的目标词"（冻结种子）。
产出 <out>/pool_list.csv: blind_id,fname,own_class,asked_class,count_gt_own,split
并把 150 张图拷到 <out>/images/（盲名 blind_id.png）
"""
import os, io, csv, json, sys, random, shutil

POOL = '/root/fsc147_full/pool'
OUT = sys.argv[1] if len(sys.argv) > 1 else '/root/a54_zero150/pool'
N = int(sys.argv[2]) if len(sys.argv) > 2 else 150
SEED = 20261011

# 类名
cls = {}
for ln in io.open('/root/fsc147/ImageClasses_FSC147.txt', encoding='utf-8'):
    ln = ln.rstrip('\r\n')
    if '\t' in ln:
        a, b = ln.split('\t', 1)
    else:
        p = ln.split(None, 1)
        a, b = (p + [''] * 2)[:2]
    cls[a.strip()] = b.strip()

# 用 A5-3 已建的 manifest（含 split 与 count_gt）
rows = [r for r in csv.DictReader(io.open(os.path.join(POOL, 'manifest.csv'), encoding='utf-8', newline=''))]
coco = [r for r in rows if r['split'] in ('test_coco', 'val_coco')]
print('COCO 子集图数 =', len(coco))

random.seed(SEED)
pick = random.sample(coco, min(N, len(coco)))
classes = sorted({v for v in cls.values() if v})
out_rows = []
os.makedirs(os.path.join(OUT, 'images'), exist_ok=True)
for i, r in enumerate(pick, 1):
    own = cls.get(r['image'], cls.get(r['item'], ''))
    cand = [c for c in classes if c != own]
    asked = random.Random(SEED + i).choice(cand)      # 冻结：按 (SEED+i) 决定被问目标词
    bid = 'blind_%03d' % i
    src = os.path.join(POOL, 'images', r['image'])
    dst = os.path.join(OUT, 'images', bid + '.png')
    if os.path.exists(src):
        shutil.copyfile(src, dst)
    out_rows.append(dict(blind_id=bid, fname=r['image'], own_class=own, asked_class=asked,
                         count_gt_own=r['count_gt'], split=r['split']))

with io.open(os.path.join(OUT, 'pool_list.csv'), 'w', encoding='utf-8', newline='') as fh:
    w = csv.DictWriter(fh, fieldnames=list(out_rows[0].keys()))
    w.writeheader()
    for x in out_rows:
        w.writerow(x)
io.open(os.path.join(OUT, 'POOL_SEED.txt'), 'w', encoding='utf-8').write(
    'SEED=%d\nN=%d\nsource=FSC-147 COCO splits (test_coco,val_coco)\nrule=asked_class != own_class (frozen choice by Random(SEED+i))\n' % (SEED, N))
print('已生成 pool_list.csv（%d 行）与 images/（盲名）' % len(out_rows))
print('样例:', out_rows[0])
print('被问类别分布（前 5）:', list({r['asked_class'] for r in out_rows})[:5])
