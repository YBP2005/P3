# -*- coding: utf-8 -*-
"""实验 3 语料渲染：新参数族 + 逐图目标词 + 10% 真零图（GT 由构造保证）。
输出: <out>/images/*.png, <out>/manifest.csv(item,target_word,count_gt,family,color,size,blur,overlap,seed,px,sha256)
契约: 复用 x01 三臂契约模板，把"目标物体"替换为逐图目标词 -> target_map.csv(cond_b_*)
"""
import os, io, csv, json, hashlib, random, sys
from PIL import Image, ImageDraw, ImageFilter

OUT = sys.argv[1] if len(sys.argv) > 1 else '/root/a55_domain2/pool'
N = int(sys.argv[2]) if len(sys.argv) > 2 else 1000
os.makedirs(os.path.join(OUT, 'images'), exist_ok=True)
C = '/root/incoming/x01_corpus/contracts'
def rd(n): return io.open(os.path.join(C, n), encoding='utf-8').read().strip()
tpl = {'base': rd('base.txt'), 'permit': rd('permit.txt'), 'channel': rd('channel.txt')}

FAMS = [('circles', 'red'), ('circles', 'blue'), ('squares', 'green'), ('squares', 'yellow')]
random.seed(20261010)
rows = []
for i in range(N):
    seed = 20261010 + i
    rnd = random.Random(seed)
    fam, col = FAMS[i % len(FAMS)]                      # 目标词 = 该图实际存在的目标
    px = rnd.choice([640, 768, 896])                    # 新尺寸档（与既有语料不重叠）
    size = rnd.choice([14, 18, 22, 26])
    blur = rnd.choice([0, 1, 2])
    overlap = rnd.choice([0.0, 0.2, 0.4])
    zero_img = (i % 10 == 9)                            # ★ 10% 真零图（含目标族但非被问目标）
    n = 0 if zero_img else rnd.choice([12, 24, 48, 96, 160])
    img = Image.new('RGB', (px, px), (250, 250, 250))
    dr = ImageDraw.Draw(img)
    placed = []
    other = [f for f in FAMS if f != (fam, col)]
    # 真零图：只画"其它族"，使被问目标完全不存在
    draw_fams = other if zero_img else [(fam, col)]
    for _ in range(len(draw_fams)):
        pass
    def scatter(f, c, k):
        colmap = {'red': (200, 40, 40), 'blue': (40, 60, 200), 'green': (40, 160, 70), 'yellow': (210, 180, 40)}
        for _ in range(k):
            for _try in range(50):
                x = rnd.randint(size, px - size); y = rnd.randint(size, px - size)
                ok = True
                for (ox, oy) in placed:
                    if abs(x - ox) < size * (2 - overlap) and abs(y - oy) < size * (2 - overlap):
                        ok = False; break
                if ok:
                    placed.append((x, y))
                    if f == 'circles':
                        dr.ellipse([x - size // 2, y - size // 2, x + size // 2, y + size // 2], fill=colmap[c])
                    else:
                        dr.rectangle([x - size // 2, y - size // 2, x + size // 2, y + size // 2], fill=colmap[c])
                    break
    if zero_img:
        scatter(other[0][0], other[0][1], rnd.choice([12, 24, 48]))
    else:
        scatter(fam, col, n)
    if blur:
        img = img.filter(ImageFilter.GaussianBlur(blur))
    name = 'img_%04d.png' % (i + 1)
    p = os.path.join(OUT, 'images', name)
    img.save(p)
    sha = hashlib.sha256(open(p, 'rb').read()).hexdigest()
    tw = '%s %s' % (col, fam)
    rows.append(dict(item=name, target_word=tw, count_gt=(0 if zero_img else n), family=fam, color=col,
                     size=size, blur=blur, overlap=overlap, seed=seed, px=px, sha256=sha, true_zero=int(zero_img)))

with io.open(os.path.join(OUT, 'manifest.csv'), 'w', encoding='utf-8', newline='') as fh:
    w = csv.DictWriter(fh, fieldnames=list(rows[0].keys())); w.writeheader()
    for r in rows: w.writerow(r)

tm = []
for r in rows:
    d = dict(image=r['item'], class_name=r['target_word'], gt_count=r['count_gt'], true_zero=r['true_zero'])
    for a in tpl: d['cond_b_' + a] = tpl[a].replace('目标物体', r['target_word'])
    tm.append(d)
with io.open(os.path.join(OUT, 'target_map.csv'), 'w', encoding='utf-8', newline='') as fh:
    w = csv.DictWriter(fh, fieldnames=list(tm[0].keys())); w.writeheader()
    for x in tm: w.writerow(x)

nz = sum(r['true_zero'] for r in rows)
print('渲染 %d 图 → %s' % (len(rows), os.path.join(OUT, 'images')))
print('真零图 %d（%.1f%%）｜目标词分布 %s' % (nz, 100.0 * nz / len(rows), dict((k, sum(1 for r in rows if r['target_word'] == k)) for k in sorted({r['target_word'] for r in rows}))))
print('GT 分布（非零图）:', sorted({r['count_gt'] for r in rows if not r['true_zero']}))
print('target_map →', os.path.join(OUT, 'target_map.csv'))
