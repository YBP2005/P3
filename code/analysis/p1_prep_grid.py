# -*- coding: utf-8 -*-
"""p1_prep_grid.py —— P1 受控版（n × r × σ 圆点网格）的**确定性**图像生成 + manifest。

## 为什么要另写一个生成器（不是重造轮子）
既有两个生成器 `12_abstain_causal.py` / `21_legibility_gaps.py` 用
`abs(hash(item)) & 0xffff` 当种子，而 **Python 字符串 `hash` 逐进程随机化**（PYTHONHASHSEED）：
三个臂在**不同进程/不同起服**里跑时，同一个 item 标签会落到**不同的圆点位置**。
项目里已记录过这条限制（`PaperB_A7_8B并入与规模不变性_20260916.md` §18.4：同分布、非逐位相同）。
⇒ P1 改用**显式固定种子**把图**一次生成落盘**，各臂/各起服都读同一批文件，于是 base vs permit 是
**逐位配对**，配对差值的方差也小得多。绘制算法与 `12_abstain_causal.py` **逐字同源**（画布 1024、
网格抖动放置、BG/DOT 同色），只把"种子来源"和"存盘格式"改掉（JPEG→**PNG**，无损、可核 md5）。

## 网格（与 G.2 的 675 张同规格）
n ∈ {100,400,800} × r ∈ {2,4,8} × σ ∈ {0,1,2,4,8} × 每格 15 张 = **675 张**
item 名：`n{n}_r{r}_s{sigma}_{i:02d}`；`gt = n`；`px_per_obj = (2r)^2`。

## 用法
    python -u p1_prep_grid.py [--out DIR] [--limit K] [--verify]
      --limit K   每格只生成 K 张（自测用；默认 15）
      --verify    只按 manifest 重算 md5 并与记录比对（不重画）
输出：DIR/images/*.png、DIR/manifest.csv、DIR/manifest.md5
"""
import argparse
import csv
import hashlib
import io
import os
import random
import sys

sys.stdout.reconfigure(encoding='utf-8')
W = os.path.dirname(os.path.abspath(__file__))
DEF_OUT = os.path.join(os.path.dirname(W), 'p1_grid')
CANVAS = 1024
BG = (235, 235, 235)
DOT = (30, 60, 200)
NS = [100, 400, 800]
RS = [2, 4, 8]
SIGMAS = [0.0, 1.0, 2.0, 4.0, 8.0]
PER_CELL = 15
SEED_BASE = 20260925          # ★ 显式固定，不用 hash()


def items(per_cell=PER_CELL):
    out = []
    for n in NS:
        for r in RS:
            for s in SIGMAS:
                for i in range(per_cell):
                    out.append(('n%d_r%d_s%s_%02d' % (n, r, ('%g' % s), i), n, r, s, i))
    return out


def seed_of(idx, item):
    """逐位可复现：种子只由 index 与 SEED_BASE 决定，**不依赖进程随机化的 hash()**。"""
    return (SEED_BASE + 7919 * idx) & 0x7fffffff


def draw(n, r, sigma, seed, canvas=CANVAS):
    from PIL import Image, ImageDraw, ImageFilter
    rng = random.Random(seed)
    im = Image.new('RGB', (canvas, canvas), BG)
    d = ImageDraw.Draw(im)
    k = int(n ** 0.5) + 1
    cell = canvas / k
    placed = 0
    for i in range(k):
        for j in range(k):
            if placed >= n:
                break
            cx = int((i + rng.uniform(0.2, 0.8)) * cell)
            cy = int((j + rng.uniform(0.2, 0.8)) * cell)
            cx = min(max(cx, r + 1), canvas - r - 2)
            cy = min(max(cy, r + 1), canvas - r - 2)
            d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=DOT)
            placed += 1
    if sigma > 0:
        im = im.filter(ImageFilter.GaussianBlur(sigma))
    return im


def md5f(p):
    return hashlib.md5(io.open(p, 'rb').read()).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default=DEF_OUT)
    ap.add_argument('--limit', type=int, default=PER_CELL)
    ap.add_argument('--verify', action='store_true')
    a = ap.parse_args()
    imgd = os.path.join(a.out, 'images')
    man = os.path.join(a.out, 'manifest.csv')
    os.makedirs(imgd, exist_ok=True)
    rows = []
    it = items(a.limit)
    if a.verify:
        bad = 0
        with io.open(man, encoding='utf-8', newline='') as f:
            for r in csv.DictReader(f):
                p = os.path.join(a.out, r['path'])
                got = md5f(p) if os.path.exists(p) else 'MISSING'
                if got != r['md5']:
                    bad += 1
                    print('  [FAIL] %s 记录 %s 实际 %s' % (r['item'], r['md5'][:12], got[:12]))
        print('verify：%d 张，逐位一致 %d，不一致/缺失 %d' % (len(list(csv.DictReader(
            io.open(man, encoding='utf-8', newline='')))), 0 if bad else 1, bad))
        return 1 if bad else 0
    for idx, (item, n, r, s, i) in enumerate(it):
        rel = os.path.join('images', item + '.png')
        p = os.path.join(a.out, rel)
        if not os.path.exists(p):
            draw(n, r, s, seed_of(idx, item)).save(p, 'PNG')
        rows.append(dict(item=item, n=n, r=r, sigma=('%g' % s), px_per_obj=(2 * r) ** 2,
                         gt=n, path=rel.replace('\\', '/'), bytes=os.path.getsize(p),
                         md5=md5f(p)))
    buf = io.StringIO()
    wr = csv.writer(buf, lineterminator='\n')
    wr.writerow(['item', 'n', 'r', 'sigma', 'px_per_obj', 'gt', 'path', 'bytes', 'md5'])
    for r in rows:
        wr.writerow([r['item'], r['n'], r['r'], r['sigma'], r['px_per_obj'], r['gt'],
                     r['path'], r['bytes'], r['md5']])
    io.open(man, 'w', encoding='utf-8', newline='').write(buf.getvalue())
    h = md5f(man)
    io.open(os.path.join(a.out, 'manifest.md5'), 'w', encoding='utf-8', newline='\n').write(
        '%s  manifest.csv  (%d items, per_cell=%d)\n' % (h, len(rows), a.limit))
    print('已生成 %d 张 PNG ⇒ %s' % (len(rows), imgd))
    print('manifest %s (md5 %s)' % (man, h[:12]))
    print('网格：n%s × r%s × σ%s × 每格 %d' % (NS, RS, SIGMAS, a.limit))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
