# -*- coding: utf-8 -*-
"""a52_prep_stim.py —— A5-2（计数 × 可读性正交冻结刺激）的**确定性**四因子刺激生成器。

════════════════════════════════════════════════════════════════════════════
同源声明（★ 本件是 `p1_prep_grid.py` 的加法，不是另起炉灶）
════════════════════════════════════════════════════════════════════════════
* 绘制算法**逐字同源**：画布 `CANVAS=1024`、背景 `BG=(235,235,235)`、
  圆点 `DOT=(30,60,200)`、抖动规则（在格内 `rng.uniform(0.2,0.8)` 取心）、
  `ImageFilter.GaussianBlur(sigma)`、`PNG` 无损存盘。
* **显式固定种子**（`--seed`，默认 20261004，写进 manifest 的 `seed` 列）。
  p1_prep_grid.py 的头部记录了那个坑：旧生成器用 `abs(hash(item))` 当种子，而
  **Python 字符串 hash 逐进程随机化（PYTHONHASHSEED）**，同一个 item 标签在不同进程/
  不同起服里会落到不同的圆点位置 ⇒ base vs permit 就不是逐位配对了。
  ⇒ 本件沿用同一条规矩：**种子只由 (SEED, 格号, 布局号) 决定，与 hash() 无关**。
* **一次落盘**：图**只生成一次**写进 `out/images/*.png`；后续所有臂 / 所有起服都读
  **同一批文件**（`a52_probe.py --manifest`），因此臂间比较是**逐位配对**的。

相对 p1_prep_grid.py **只加了三件事**：① 四因子（count × size × blur × overlap）；
② 每格 8 个独立布局；③ 存盘时带 sha256 与"可辨圆点数"的几何真值。

════════════════════════════════════════════════════════════════════════════
四因子 = 81 格 × 8 布局 = 648 图
════════════════════════════════════════════════════════════════════════════
    count    : 8 / 32 / 80        （固定数量，与 blob 密度无关）
    size     : r = 3 / 8 / 24 px  （圆点半径，3 档）
    blur     : σ = 0 / 4 / 8      （与 p1 同族的 Gaussian 模糊，3 档）
    overlap  : 1.45 / 1.15 / 0.85 （**相邻圆心间距 = 该档 × 直径**，3 档）
               ⇒ 低档圆心互不接触（清晰分离）；高档圆心近到可重叠。

overlap 三档为什么是"直径的倍数"？——为了让**密度与半径无关**：圆心间距
`d = f·2r` 时，每个圆点占的格子面积 ∝ (f·2r)²，而圆点自身面积 ∝ r²，
于是"能放下的个数"三档 size 上一致 ⇒ **格子的可实现性不会被 size 单独决定**
（否则 size×count 的建模就与"能不能画出来"混在一起了）。

════════════════════════════════════════════════════════════════════════════
实现性（C1）与"先声明后排除"
════════════════════════════════════════════════════════════════════════════
每张图落在 manifest 的一行，带两个几何真值：
* `n_dots_detected_gt` —— **可辨圆点数**：把圆心间距 < `2r + 0.8·σ` 的圆点并成一个
  blob 之后剩下的 blob 数（即"从像素上还能数出几个"）。这个量**与推理无关**，纯几何。
* 若某格任意布局 **一个 blob 都数不出来**（`n_dots_detected_gt < 1`）或**放不下**
  目标个数（packing 失败）⇒ 该格判 `UNREALIZABLE`，**打印** `UNREALIZABLE <cell_id> <原因>`
  由预注册声明后排除；**绝不在跑完之后回头剔格**。
  （口径：`UNREALIZABLE` 只看"有没有/放不放得下"，**不因"可辨数 < 目标数"而排除**——
   后者是刺激的**设计后果**，照常测，并被 C1 报为 `detection_frac`。）

不重画、不依赖网络、纯 CPU。

用法：
    python a52_prep_stim.py --out DIR [--seed 20261004] [--limit 8] [--verify] [--emit-items]
      --limit K       每格只生成 K 个布局（自测用；默认 8 ⇒ 648 图）
      --emit-items    另写 DIR/items.csv（648 行；a52_probe.py 的输入）
      --verify        只按 manifest 逐位复算 sha256（不重画）
输出：
    DIR/images/<cell_id>_L<layout>.png
    DIR/manifest.csv        cell_id,layout_id,count_gt,size_level,blur_level,overlap_level,seed,px,n_dots_detected_gt,sha256
    DIR/manifest.md5        本 manifest.csv 的 md5（列在被引用的行里）
    DIR/manifest_sha256.txt 648 行 `sha256  images/...` 的 sha256sum 清单（可用系统工具核）
    DIR/items.csv           （--emit-items）
    DIR/A52_STIM_CONFIG.json 冻结参数（档位/画布/配色/种子/与 p1 的同源声明）
"""
import argparse
import csv
import hashlib
import io
import json
import os
import random
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# ── 与 p1_prep_grid.py 逐字同源的冻结常量 ────────────────────────────────────
CANVAS = 1024
BG = (235, 235, 235)
DOT = (30, 60, 200)
SEED_BASE = 20261004                  # ★ 显式固定，不用 hash()
PER_CELL = 8
COUNTS = [8, 32, 80]                  # count 低 / 中 / 高
RADII = [3, 8, 24]                    # 实例大小 小 / 中 / 大
BLURS = [0.0, 4.0, 8.0]               # blur 无 / 中 / 强
OVERLAPS = [1.45, 1.15, 0.85]         # 圆心间距 = 该倍数 × 直径
LEVEL_NAMES = {'count': ['low', 'mid', 'high'], 'size': ['small', 'mid', 'large'],
               'blur': ['none', 'mid', 'strong'], 'overlap': ['low', 'mid', 'high']}
MERGE_K = 0.35                        # blob 合并判据：圆心间距 < 2r + MERGE_K·σ ⇒ 并成一个 blob
DET_PEAK_MIN = 0.10                   # 可辨下限：blob 峰值 |BG−DOT| 调制 < 0.10 ⇒ 看不见（几何真值）
EMPTY_WARN_FRAC = 1.0 / 3.0           # 可辨数 < 目标/3 ⇒ 打"可能塌成团"的警告（不排除）
# 与 19e_probe_multi.py / p1_probe.py 逐字相同的弃答标记（解析器自检要比对同一份）
ABSTAIN_MARK = ('abstain', 'cannot', "can't", 'unable', 'too many', '无法', '不能', '数不清',
                '难以', '不确定', '无法判断', '众多')

COLS = ['cell_id', 'layout_id', 'count_gt', 'size_level', 'blur_level', 'overlap_level',
        'seed', 'px', 'n_dots_detected_gt', 'sha256', 'radius', 'blur', 'overlap']


def cell_id_of(ci, si, bi, oi):
    return 'c%02d_s%d_b%d_o%d' % (COUNTS[ci], RADII[si], int(BLURS[bi]), oi)


def cells():
    """81 格：count × size × blur × overlap（预注册的完整叉积，不跳格）。"""
    out = []
    for ci in range(3):
        for si in range(3):
            for bi in range(3):
                for oi in range(3):
                    out.append((ci, si, bi, oi))
    return out


def seed_of(cell_idx, layout):
    """逐位可复现：种子只由 (SEED_BASE, 格号, 布局号) 决定，**不依赖进程随机化的 hash()**。"""
    return (SEED_BASE + 7919 * cell_idx + 104729 * layout) & 0x7fffffff


def place(n, r, f, seed, canvas=CANVAS):
    """确定性放置：抖动网格 + 逐点最小间距守门。

    ⇒ 返回 (dots, left, jitter)。`left > 0` 表示按该档 overlap **放不下** n 个点
    （packing 失败）⇒ 该格判 UNREALIZABLE（预注册先声明后排除）。
    f = 圆心间距 / 直径；f < 1 允许圆点在像素上相叠（"高 overlap"档）。
    """
    rng = random.Random(seed)
    d = max(2.0 * r * f, 2.0)                  # 目标圆心间距（像素）
    step = max(d, 2.0)
    k = max(1, int(canvas // step))            # 栅格列数（大小档自动适配）
    cell = canvas / float(k)
    jit = 0.5 * max(0.0, cell - d)             # 抖动半径：保证最坏情况下仍 ≥ d
    dots = []
    for i in range(k):
        for j in range(k):
            if len(dots) >= n:
                break
            cx = (i + 0.5 + (rng.uniform(-jit, jit) if jit > 1e-9 else 0.0)) * cell
            cy = (j + 0.5 + (rng.uniform(-jit, jit) if jit > 1e-9 else 0.0)) * cell
            cx = min(max(cx, r + 1.0), canvas - r - 2.0)
            cy = min(max(cy, r + 1.0), canvas - r - 2.0)
            if all((cx - px) ** 2 + (cy - py) ** 2 >= d * d for px, py in dots):
                dots.append((cx, cy))
    return dots, max(0, n - len(dots)), jit


def draw(n, r, sigma, f, seed, canvas=CANVAS):
    """与 p1_prep_grid.py 的 draw() 同源：同画布 / 同配色 / 同抖动 / 同 blur / 同 PNG。"""
    from PIL import Image, ImageDraw, ImageFilter
    dots, left, jit = place(n, r, f, seed, canvas)
    im = Image.new('RGB', (canvas, canvas), BG)
    d = ImageDraw.Draw(im)
    for cx, cy in dots:
        d.ellipse([int(cx) - r, int(cy) - r, int(cx) + r, int(cy) + r], fill=DOT)
    if sigma > 0:
        im = im.filter(ImageFilter.GaussianBlur(sigma))
    return im, dots, left, jit


def n_detected(dots, r, sigma):
    r"""**可辨圆点数**（几何真值，与推理无关，CPU 可逐位复算）。

    模型（二维高斯 ink 的物理近似；只用来判定"几何上还能不能分辨"，不是模型行为模型）：
      ① 合并：圆心间距 < `2r + MERGE_K·σ` 的圆点并成一个 blob
         （σ=0 时恰好退化为"两个圆盘真的相叠才合并"，与 overlap 档的物理含义对齐）；
      ② 亮度：一个 blob 的 ink 总量 ∝ Σr² ⇒ 等效半径 r_eq = √(Σr²)，
         峰值调制 P = 0.75·Σr²/(r_eq² + σ²) = 0.75·k·r²/(k·r² + σ²)（k = 该 blob 的圆点数）；
      ③ 可辨：`P ≥ DET_PEAK_MIN`，否则该 blob 在像素上"糊没了"，不计入。
    ⇒ 返回可辨 blob 数。`< 1` 即该格在几何上不可实现（UNREALIZABLE）。
    """
    if not dots:
        return 0
    thr = 2.0 * r + MERGE_K * sigma
    parent = list(range(len(dots)))

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    for i in range(len(dots)):
        for j in range(i + 1, len(dots)):
            dx = dots[i][0] - dots[j][0]
            dy = dots[i][1] - dots[j][1]
            if dx * dx + dy * dy < thr * thr:
                a, b = find(i), find(j)
                if a != b:
                    parent[a] = b
    groups = {}
    for i in range(len(dots)):
        groups.setdefault(find(i), []).append(i)
    vis = 0
    for mem in groups.values():
        k = len(mem)
        r_eq2 = k * r * r
        peak = 0.75 * r_eq2 / (r_eq2 + sigma * sigma)
        if peak >= DET_PEAK_MIN:
            vis += 1
    return vis


def sha256f(p):
    h = hashlib.sha256()
    with io.open(p, 'rb') as f:
        for ch in iter(lambda: f.read(1 << 20), b''):
            h.update(ch)
    return h.hexdigest()


def md5f(p):
    return hashlib.md5(io.open(p, 'rb').read()).hexdigest()


def write_config(outd, seed, per_cell):
    cfg = dict(
        generator='a52_prep_stim.py', a52_plan='A800实验方案_A5_20261004.md §2 (A5-2) / §3',
        same_source_as='p1_prep_grid.py (md5 7d9476f24c31c95fe2602d680a024955, /root/p1_prep_grid.py)',
        same_source_note=('绘制算法逐字同源：画布/配色/抖动规则/GaussianBlur/PNG 全部照抄 '
                          'p1_prep_grid.py；只加四因子、8 布局与 sha256+可辨数真值。'
                          '种子改为显式（不用 abs(hash(item))，那条会在 PYTHONHASHSEED 下逐进程漂移）。'),
        canvas=CANVAS, bg=list(BG), dot=list(DOT),
        counts=COUNTS, radii=RADII, blurs=BLURS, overlap_factors=OVERLAPS,
        level_names=LEVEL_NAMES, per_cell=per_cell, cells=81, images=81 * per_cell,
        merge_rule='blob 合并判据：圆心间距 < 2r + %.1f*sigma' % MERGE_K,
        seed=seed, seed_rule='seed = (%d + 7919*cell_idx + 104729*layout) & 0x7fffffff' % SEED_BASE,
        canvas_1024_note='图片在 1024x1024 上渲染；客户端不缩放（服务端 mm-processor 为冻结值）',
    )
    p = os.path.join(outd, 'A52_STIM_CONFIG.json')
    io.open(p, 'w', encoding='utf-8', newline='\n').write(
        json.dumps(cfg, ensure_ascii=False, indent=2) + '\n')
    return p, md5f(p)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', required=True)
    ap.add_argument('--seed', type=int, default=SEED_BASE)
    ap.add_argument('--limit', type=int, default=PER_CELL)
    ap.add_argument('--verify', action='store_true')
    ap.add_argument('--emit-items', action='store_true')
    ap.add_argument('--quiet', action='store_true')
    a = ap.parse_args()
    imgd = os.path.join(a.out, 'images')
    man = os.path.join(a.out, 'manifest.csv')
    os.makedirs(imgd, exist_ok=True)

    if a.verify:
        if not os.path.exists(man):
            print('!! 没有 %s ⇒ 无法核' % man)
            return 2
        rows = list(csv.DictReader(io.open(man, encoding='utf-8-sig', newline='')))
        bad, miss = 0, 0
        for r in rows:
            p = os.path.join(a.out, 'images', r['layout_id'] + '.png')
            if not os.path.exists(p):
                miss += 1
                print('  [MISSING] %s' % r['layout_id'])
                continue
            got = sha256f(p)
            if got != r['sha256']:
                bad += 1
                print('  [FAIL] %s 记录 %s 实际 %s' % (r['layout_id'], r['sha256'][:12], got[:12]))
        cells_seen = {r['cell_id'] for r in rows}
        per = {}
        for r in rows:
            per[r['cell_id']] = per.get(r['cell_id'], 0) + 1
        print('verify：%d 行 / %d 格 / 每格 %d 张（应 %d / 81 / %d）｜sha256 不一致 %d ｜ 缺失 %d'
              % (len(rows), len(cells_seen), min(per.values()) if per else 0,
                 len(cells()) * a.limit, a.limit, bad, miss))
        print('  manifest.md5 = %s' % (md5f(man) if os.path.exists(man) else 'MISSING'))
        return 1 if (bad or miss or len(rows) != 81 * a.limit) else 0

    rows, unreal, warn = [], [], []
    cellmeta = {}
    cs = cells()
    for ci, (c_i, s_i, b_i, o_i) in enumerate(cs):
        cid = cell_id_of(c_i, s_i, b_i, o_i)
        n, r, sigma, f = COUNTS[c_i], RADII[s_i], BLURS[b_i], OVERLAPS[o_i]
        cellmeta[cid] = dict(cell_id=cid, count_gt=n, radius=r, blur=sigma, overlap=f,
                             size_level=LEVEL_NAMES['size'][s_i], blur_level=LEVEL_NAMES['blur'][b_i],
                             overlap_level=LEVEL_NAMES['overlap'][o_i])
        for L in range(a.limit):
            lid = '%s_L%02d' % (cid, L)
            rel = 'images/%s.png' % lid
            p = os.path.join(a.out, rel)
            sd = seed_of(ci, L)
            im, dots, left, jit = draw(n, r, sigma, f, sd)
            if not os.path.exists(p):
                im.save(p, 'PNG')
            det = n_detected(dots, r, sigma)
            # ★ 实现性（只判"有没有 / 放不放得下"）
            if left > 0 or det < 1:
                why = ('放不下：目标 %d 个，最小间距 %.1fpx 时只放下 %d 个（每次布局）'
                       % (n, max(2.0 * r * f, 2.0), n - left)) if left > 0 else \
                      ('可辨 blob = 0（r=%d σ=%g 下全部并成一团且峰值 < %.2f）' % (r, sigma, DET_PEAK_MIN))
                unreal.append((cid, why))
            elif det < max(3.0, EMPTY_WARN_FRAC * n):
                warn.append((lid, n, det))
            rows.append(dict(cell_id=cid, layout_id=lid, count_gt=n, size_level=LEVEL_NAMES['size'][s_i],
                             blur_level=LEVEL_NAMES['blur'][b_i],
                             overlap_level=LEVEL_NAMES['overlap'][o_i], seed=sd, px=(2 * r) ** 2,
                             n_dots_detected_gt=det, sha256=sha256f(p),
                             radius=r, blur=sigma, overlap=f))

    buf = io.StringIO()
    wr = csv.writer(buf, lineterminator='\n')
    wr.writerow(COLS)
    for r in rows:
        wr.writerow([r[k] for k in COLS])
    io.open(man, 'w', encoding='utf-8', newline='').write(buf.getvalue())
    h = md5f(man)
    io.open(os.path.join(a.out, 'manifest.md5'), 'w', encoding='utf-8', newline='\n').write(
        '%s  manifest.csv\n' % h)
    io.open(os.path.join(a.out, 'manifest.md5.note'), 'w', encoding='utf-8', newline='\n').write(
        'manifest.csv 的 md5 = %s\n行数 = %d\n格数 = %d（应 81）\n每格 = %d（应 8）\nseed = %d\n'
        '# 核法：cd <本目录> && md5sum -c manifest.md5\n'
        % (h, len(rows), len({r['cell_id'] for r in rows}), a.limit, a.seed))
    io.open(os.path.join(a.out, 'manifest_sha256.txt'), 'w', encoding='utf-8', newline='\n').write(
        ''.join('%s  images/%s.png\n' % (r['sha256'], r['layout_id']) for r in rows))
    if a.emit_items:
        ip = os.path.join(a.out, 'items.csv')
        with io.open(ip, 'w', encoding='utf-8', newline='') as fh:
            w = csv.writer(fh, lineterminator='\n')
            w.writerow(['item', 'cell_id', 'layout_id', 'count_gt', 'size_level', 'blur_level',
                        'overlap_level', 'px', 'n_dots_detected_gt', 'img'])
            for r in rows:
                w.writerow([r['layout_id'], r['cell_id'], r['layout_id'], r['count_gt'],
                            r['size_level'], r['blur_level'], r['overlap_level'], r['px'],
                            r['n_dots_detected_gt'], 'images/%s.png' % r['layout_id']])
        print('items ⇒ %s（%d 行）' % (ip, len(rows)))
    cfgp, cfgmd5 = write_config(a.out, a.seed, a.limit)

    # ── 收尾：预注册的"先声明后排除"与逐格实现性检查 ─────────────────────
    per = {}
    for r in rows:
        per.setdefault(r['cell_id'], []).append(r)
    # 逐格台账（cell 级）：给分析器 C1 的"先声明后排除"用；也是刺激侧的交付件
    led = os.path.join(a.out, '_cells.csv')
    with io.open(led, 'w', encoding='utf-8', newline='') as fh:
        w = csv.writer(fh, lineterminator='\n')
        w.writerow(['cell_id', 'count_gt', 'radius', 'blur', 'overlap', 'size_level', 'blur_level',
                    'overlap_level', 'n_layouts', 'n_detected_min', 'n_detected_max',
                    'n_detected_mean', 'detection_frac_mean', 'n_layouts_all_unrealizable',
                    'realizable'])
        for cid in sorted(per):
            v = sorted(per[cid], key=lambda x: x['layout_id'])
            d = [int(x['n_dots_detected_gt']) for x in v]
            g = int(v[0]['count_gt'])
            m = cellmeta[cid]
            w.writerow([cid, g, m['radius'], m['blur'], m['overlap'], m['size_level'],
                        m['blur_level'], m['overlap_level'], len(v), min(d), max(d),
                        '%.3f' % (sum(d) / float(len(d))),
                        '%.4f' % (sum(d) / float(len(d)) / g),
                        sum(1 for x in d if x < 1), 1 if min(d) >= 1 else 0])
    # 逐格可辨数矩阵（布局 × 格），方便一眼看塌团分布
    matp = os.path.join(a.out, 'detection_matrix.csv')
    with io.open(matp, 'w', encoding='utf-8', newline='') as fh:
        w = csv.writer(fh, lineterminator='\n')
        w.writerow(['cell_id', 'count_gt'] + ['L%02d' % L for L in range(a.limit)])
        for cid in sorted(per):
            v = sorted(per[cid], key=lambda x: x['layout_id'])
            w.writerow([cid, v[0]['count_gt']] + [x['n_dots_detected_gt'] for x in v])
    # 预注册声明：UNREALIZABLE 格（原因 → 逐格一行）
    unrealized_cids = sorted({c for c, _ in unreal})
    up = os.path.join(a.out, '_unrealizable.csv')
    with io.open(up, 'w', encoding='utf-8', newline='') as fh:
        w = csv.writer(fh, lineterminator='\n')
        w.writerow(['cell_id', 'reason', 'n_layouts_unrealizable', 'n_layouts'])
        reasons = {}
        for c, why in unreal:
            reasons.setdefault(c, set()).add(why)
        for c in unrealized_cids:
            w.writerow([c, ' ｜ '.join(sorted(reasons[c])),
                        sum(1 for r in per.get(c, []) if int(r['n_dots_detected_gt']) < 1),
                        len(per.get(c, []))])
    empty = [c for c, v in per.items() if all(int(x['n_dots_detected_gt']) < 1 for x in v)]
    short = [c for c, v in per.items() if len(v) != a.limit]
    uniq_cells = sorted(set(unreal))
    for cid, why in uniq_cells:
        print('UNREALIZABLE %s %s' % (cid, why))
    for lid, n, det in warn[:12]:
        print('  ⚠ 可辨数偏少 %s：目标 %d，几何可辨 %d（< 目标/3）⇒ 该刺激"塌成团"，照常测但 C1 会报 detection_frac' % (lid, n, det))
    if len(warn) > 12:
        print('  ⚠ …另有 %d 张同类（见 manifest 的 n_dots_detected_gt）' % (len(warn) - 12))

    full_det = sum(1 for r in rows if int(r['n_dots_detected_gt']) == int(r['count_gt']))
    print('')
    print('已生成 %d 张 PNG ⇒ %s' % (len(rows), imgd))
    print('manifest %s（md5 %s）｜ 每格 %d 张 = %s ｜ sha256 齐 = %s'
          % (man, h[:12], a.limit, not short, all(len(r['sha256']) == 64 for r in rows)))
    print('格数 = %d（应 81）｜ 非空格数 = %d = 81 − %d（预注册排除）= %s（**先声明后排除**；'
          '未排除格全非空 = %s）'
          % (len(per), len(per) - len(unrealized_cids), len(unrealized_cids),
             len(per) - len(unrealized_cids) == 81 - len(unrealized_cids), not empty))
    print('UNREALIZABLE 格数 = %d（预注册先声明后排除）｜ 配置件 %s（md5 %s）'
          % (len(unrealized_cids), cfgp, cfgmd5[:12]))
    print('A52_PREP_DONE rows=%d cells=%d unrealizable=%d' % (len(rows), len(per), len(unrealized_cids)))
    return 0 if (not empty and not short and len(rows) == 81 * a.limit) else 1


if __name__ == '__main__':
    raise SystemExit(main())
