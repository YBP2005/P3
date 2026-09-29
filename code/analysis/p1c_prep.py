#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""p1c_prep.py —— P1c（生态版）的图像与 manifest 生成：**真实图像 × {clean, blur4, down15}**。

为什么要生态版：P1 的受控网格用的是合成圆点，回答了"机制能不能被诱发"；但 glm53flash 的原话是
"在 2–3 个 E3 家族补一组 blur/tiling 对照（每家族 300 张 × 2 臂）"——**真实图像**上的对照才贴近原话，
也才能回答 dspro 那条的**另一个侧面**：真实密集图上，非 Qwen 血统会不会也答 0。

样本：150 张 ShanghaiTech-A（密集）+ 150 张 VisDrone（航拍），固定顺序（排序后按固定步长取），
GT 来自语料自身的计数表。三种处理：
  * `clean`  —— 原图（对照）
  * `blur4`  —— 高斯模糊 σ=4（§5.7 的"模糊门控"那一侧）
  * `down15` —— 缩放到 **15% 的像素**（线性 ×√0.15≈0.387；§5.7 的"分辨率不是门控"那一侧）
输出：每处理一个目录（images/ + manifest.csv + manifest.md5），供 `p1_probe.py --grid <dir>` 直接读。

用法：python3 p1c_prep.py [--root /root/p1c] [--per 150]
"""
import argparse
import csv
import hashlib
import io
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')
DENSE = '/root/dense/shanghaitech/images/part_A_test'
AER = '/root/aerial/visdrone/images'
GT_STA = '/root/dense/shanghaitech/counts.csv'
GT_VIS = '/root/aerial/gt_visdrone.csv'


def load_sta():
    """ShanghaiTech-A test：counts.csv 里 part==A、split==test 的行。"""
    out = {}
    for r in csv.DictReader(io.open(GT_STA, encoding='utf-8-sig')):
        if r.get('part') == 'part_A' and r.get('split') == 'test':
            out[os.path.splitext(os.path.basename(r['file']))[0]] = int(r['count'])
    return out


def load_vis():
    return {r['item']: int(r['gt']) for r in csv.DictReader(io.open(GT_VIS, encoding='utf-8-sig'))}


def pick(items, n):
    """确定性抽样：排序后等步长取 n 个（不用随机，避免"每次不同"）。"""
    items = sorted(items)
    if len(items) <= n:
        return items
    step = len(items) / float(n)
    return [items[int(i * step)] for i in range(n)]


def find_image(d, stem):
    for ext in ('', '.jpg', '.png', '.jpeg', '.JPG', '.tif'):
        p = os.path.join(d, stem + ext)
        if os.path.exists(p):
            return p
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', default='/root/p1c')
    ap.add_argument('--per', type=int, default=150)
    a = ap.parse_args()
    from PIL import Image, ImageFilter
    sta, vis = load_sta(), load_vis()
    s_items = pick([k for k in sta if find_image(DENSE, k)], a.per)
    v_items = pick([k for k in vis if find_image(AER, k)], a.per)
    print('  ShanghaiTech-A %d 张（GT %d–%d）｜VisDrone %d 张（GT %d–%d）'
          % (len(s_items), min(sta[k] for k in s_items), max(sta[k] for k in s_items),
             len(v_items), min(vis[k] for k in v_items), max(vis[k] for k in v_items)))
    rows_all = []
    for src, items, gtd, tag in (('sta', s_items, sta, 'st_a'), ('vis', v_items, vis, 'visdrone')):
        for k in items:
            rows_all.append(dict(item='%s__%s' % (tag, k), src=src,
                                 path=find_image(DENSE if src == 'sta' else AER, k),
                                 gt=gtd[k]))
    for treat in ('clean', 'blur4', 'down15'):
        d = os.path.join(a.root, treat)
        os.makedirs(os.path.join(d, 'images'), exist_ok=True)
        rows = []
        for r in rows_all:
            im = Image.open(r['path']).convert('RGB')
            if treat == 'blur4':
                im = im.filter(ImageFilter.GaussianBlur(4.0))
            elif treat == 'down15':
                w, h = im.size
                s = 0.15 ** 0.5
                im = im.resize((max(1, int(round(w * s))), max(1, int(round(h * s)))),
                               Image.LANCZOS)
            rel = os.path.join('images', r['item'] + '.png')
            p = os.path.join(d, rel)
            im.save(p, 'PNG')
            rows.append(dict(item=r['item'], n=0, r=0, sigma=0, gt=r['gt'],
                             src=r['src'], path=rel.replace('\\', '/'),
                             size='%dx%d' % im.size, md5=hashlib.md5(io.open(p, 'rb').read()).hexdigest()))
        buf = io.StringIO()
        w = csv.writer(buf, lineterminator='\n')
        w.writerow(['item', 'n', 'r', 'sigma', 'gt', 'src', 'path', 'size', 'md5'])
        for x in rows:
            w.writerow([x['item'], x['n'], x['r'], x['sigma'], x['gt'], x['src'], x['path'],
                        x['size'], x['md5']])
        io.open(os.path.join(d, 'manifest.csv'), 'w', encoding='utf-8', newline='').write(buf.getvalue())
        h = hashlib.md5(io.open(os.path.join(d, 'manifest.csv'), 'rb').read()).hexdigest()
        io.open(os.path.join(d, 'manifest.md5'), 'w', encoding='utf-8', newline='\n').write(
            '%s  manifest.csv  (%s, %d items)\n' % (h, treat, len(rows)))
        print('  %-7s → %s（%d 项，manifest md5 %s）' % (treat, d, len(rows), h[:12]))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
