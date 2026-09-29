#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ea_build_z0.py —— **E-A 的真零池构造器**（CPU）。

## 为什么这样构造
盘上**没有**任何 GT=0 的图（实测：st_a 最小 66、ucf 65、st_b 9、visdrone/aitod 最小 1）。
于是用 **UCF-QNRF 的头部点标注**（`*_ann.mat` 的 `annPoints`，N×2）构造**真零窗口**：
在密集域原图上滑窗，保留**窗口（外扩 margin 后）内一个头部点都没有**的窗口
⇒ 按**数据集自己的标注**，该窗口的正确答案 **就是 0**。

## 两个分层（E-A 的机制检验靠它）
对每个合格窗口算一个**杂波代理**（灰度 Laplacian 标准差），按杂波排序二分：
  · `z0easy`  = 低杂波（天空/路面/平坦区）——"看起来就该是 0"
  · `z0hard`  = 高杂波（树丛/纹理/人群远景但无标注头）——"看起来可能有人"
若模型在 easy 上答 0、在 hard 上弃权 ⇒ **弃权由可辨性触发，而非由"没有目标"触发**，
这正是 §5.6/§7.9 的机制预测在**真零条件下**的独立检验。

## 产物
  /root/z0/images/z0easy_<n>.jpg, z0hard_<n>.jpg
  /root/z0/gt_z0.csv  (item,gt,stratum,clutter,src_image,box)
"""
import argparse, csv, glob, os, sys
import numpy as np
from PIL import Image
import scipy.io as sio

SRC = '/root/dense/ucf_qnrf/UCF-QNRF_ECCV18/Test'


def clutter_of(im):
    """杂波代理：灰度下采样后 Laplacian 的标准差（越大越"看起来有东西"）。"""
    g = np.asarray(im.convert('L').resize((256, 256)), dtype=np.float32)
    lap = (-4 * g[1:-1, 1:-1] + g[:-2, 1:-1] + g[2:, 1:-1] + g[1:-1, :-2] + g[1:-1, 2:])
    return float(lap.std())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default='/root/z0')
    ap.add_argument('--per', type=int, default=200, help='每层目标条数（默认 200，最终按杂波二分）')
    ap.add_argument('--margin', type=int, default=48, help='排除头部点的外扩像素')
    ap.add_argument('--frac', type=float, default=0.35, help='窗口边长 = frac × min(H,W)')
    ap.add_argument('--max-per-image', type=int, default=2, help='每图最多取几个窗口')
    A = ap.parse_args()
    imgd = os.path.join(A.out, 'images')
    os.makedirs(imgd, exist_ok=True)

    mats = sorted(glob.glob(os.path.join(SRC, '*_ann.mat')))
    print('源图 %d 张' % len(mats))
    cands = []
    for fi, mf in enumerate(mats):
        base = os.path.basename(mf).replace('_ann.mat', '')
        ip = os.path.join(SRC, base + '.jpg')
        if not os.path.exists(ip):
            continue
        d = sio.loadmat(mf)
        pts = d.get('annPoints')
        if pts is None:
            continue
        pts = np.asarray(pts, dtype=np.float32).reshape(-1, 2)
        im = Image.open(ip).convert('RGB')
        W, H = im.size
        s = int(max(320, min(800, round(A.frac * min(W, H)))))
        if W <= s or H <= s:
            continue
        got = 0
        for y in range(0, H - s + 1, s // 2):
            if got >= A.max_per_image:
                break
            for x in range(0, W - s + 1, s // 2):
                if got >= A.max_per_image:
                    break
                x0, y0, x1, y1 = x, y, x + s, y + s
                mx0, my0 = x0 - A.margin, y0 - A.margin
                mx1, my1 = x1 + A.margin, y1 + A.margin
                inside = ((pts[:, 0] >= mx0) & (pts[:, 0] < mx1) &
                          (pts[:, 1] >= my0) & (pts[:, 1] < my1))
                if inside.any():
                    continue                      # 外扩框内有头 ⇒ 不是真零
                crop = im.crop((x0, y0, x1, y1))
                cands.append(dict(src=base, box=(x0, y0, x1, y1), size=s,
                                  clutter=clutter_of(crop), _im=crop))
                got += 1
        if (fi + 1) % 50 == 0:
            print('  已扫 %d/%d 张，候选 %d 个' % (fi + 1, len(mats), len(cands)))

    if len(cands) < 2 * A.per:
        print('!! 候选不足（%d < %d），把 --per 调小或 --margin 调小' % (len(cands), 2 * A.per))
    cands.sort(key=lambda c: c['clutter'])
    n = min(A.per, len(cands) // 2)
    easy, hard = cands[:n], cands[-n:]
    rows = []
    for stratum, group in (('z0easy', easy), ('z0hard', hard)):
        for i, c in enumerate(group):
            fn = '%s_%04d.jpg' % (stratum, i)
            c['_im'].save(os.path.join(imgd, fn), 'JPEG', quality=92)
            rows.append(dict(item=fn, gt=0, stratum=stratum,
                             clutter='%.4f' % c['clutter'], src_image=c['src'],
                             box='%d_%d_%d_%d' % c['box']))
    with open(os.path.join(A.out, 'gt_z0.csv'), 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=['item', 'gt', 'stratum', 'clutter', 'src_image', 'box'])
        w.writeheader()
        w.writerows(rows)
    cl_e = [float(r['clutter']) for r in rows if r['stratum'] == 'z0easy']
    cl_h = [float(r['clutter']) for r in rows if r['stratum'] == 'z0hard']
    print('候选 %d 个；写出 %d 条（easy %d，hard %d）'
          % (len(cands), len(rows), len(cl_e), len(cl_h)))
    print('杂波代理：easy %.2f–%.2f（中位 %.2f）；hard %.2f–%.2f（中位 %.2f）'
          % (min(cl_e), max(cl_e), float(np.median(cl_e)),
             min(cl_h), max(cl_h), float(np.median(cl_h))))
    print('产物：%s / %s' % (imgd, os.path.join(A.out, 'gt_z0.csv')))


if __name__ == '__main__':
    main()
