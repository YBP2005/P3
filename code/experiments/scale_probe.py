#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""scale_probe.py — 尺度选择探针（Lindeberg 归一化 LoG），纯 CPU

动机：G1 发现 px/obj（每目标像素数，假设目标铺满画布）在跨域时失效：
VisDrone 的 px/obj 高达 10^4–10^6 却弃权 41–54%。猜测真正的可辨性变量是
**目标本身的像素尺度 σ***，而非"面积/个数"。
本脚本用尺度空间归一化拉普拉斯响应在每张图上选出**特征目标半径 σ\***（原生像素），
供检验"弃权是否在 σ* 上跨域塌缩到一条曲线"。

用法: python scale_probe.py <st_a|ucf|visdrone>
输出: /root/feat/scale_<ds>.csv
"""
import csv, math, os, sys, time
import cv2
import numpy as np

OUT = '/root/feat'
os.makedirs(OUT, exist_ok=True)
WORK = 512.0                       # 工作分辨率长边
SIGMAS = [0.8, 1.2, 1.8, 2.5, 3.5, 5.0, 7.0, 10.0, 14.0]
TOPF = 0.02                        # 取响应最强的 2% 像素参与统计


def load_gt(ds):
    if ds == 'ucf':
        idir = '/root/dense/ucf_qnrf/UCF-QNRF_ECCV18/Test'
        gt = {}
        with open('/root/dense/ucf_qnrf/counts.csv', encoding='utf-8-sig') as f:
            for r in csv.DictReader(f):
                if r['split'] == 'Test':
                    gt[os.path.splitext(os.path.basename(r['file']))[0]] = int(r['count'])
        return idir, gt
    if ds == 'st_a':
        idir = '/root/dense/shanghaitech/images/part_A_test'
        gt = {}
        with open('/root/dense/shanghaitech/counts.csv', encoding='utf-8-sig') as f:
            for r in csv.DictReader(f):
                if r.get('part') == 'part_A' and r.get('split') == 'test':
                    gt[os.path.splitext(os.path.basename(r['file']))[0]] = int(r['count'])
        return idir, gt
    if ds == 'visdrone':
        idir = '/root/aerial/visdrone/images'
        gt = {}
        with open('/root/aerial/gt_visdrone.csv', encoding='utf-8-sig') as f:
            for r in csv.DictReader(f):
                gt[r['item']] = int(r['gt'])
        return idir, gt
    raise SystemExit('unknown ' + ds)


def probe(img_gray):
    h0, w0 = img_gray.shape
    f = WORK / float(max(h0, w0))
    if f < 1.0:
        g = cv2.resize(img_gray, (max(16, int(w0 * f)), max(16, int(h0 * f))),
                       interpolation=cv2.INTER_AREA)
    else:
        g = img_gray
        f = 1.0
    g = g.astype(np.float32)
    resp = []
    for s in SIGMAS:
        L = cv2.GaussianBlur(g, (0, 0), s)
        lap = cv2.Laplacian(L, cv2.CV_32F)
        resp.append(np.abs(lap) * (s * s))          # 尺度归一化
    R = np.stack(resp, 0)                            # (S,H,W)
    mx = R.max(0)
    am = R.argmax(0)
    thr = np.percentile(mx, 100 * (1 - TOPF))
    sel = mx >= thr
    s_hat = float(np.median([SIGMAS[i] for i in am[sel]])) if sel.sum() > 0 else float('nan')
    s_nat = s_hat / f                                # 换算回原生像素
    # 由特征半径推"一图能放下多少个"（只作参考）
    n_cap = (max(h0, w0) / max(1e-6, s_nat * 2.0)) ** 2
    return s_nat, n_cap, float(np.median(mx[sel])) if sel.sum() else float('nan')


def main():
    ds = sys.argv[1]
    idir, gt = load_gt(ds)
    names = [n for n in sorted(gt) if os.path.exists(os.path.join(idir, n + '.jpg'))]
    out = os.path.join(OUT, 'scale_%s.csv' % ds)
    fh = open(out, 'w', encoding='utf-8-sig', newline='')
    wr = csv.writer(fh)
    wr.writerow(['item', 'dataset', 'gt', 'nat_w', 'nat_h', 'px_per_obj',
                 'sigma_star', 'n_cap', 'resp_med'])
    t0 = time.time()
    for i, n in enumerate(names):
        try:
            im = cv2.imread(os.path.join(idir, n + '.jpg'), cv2.IMREAD_GRAYSCALE)
            if im is None:
                continue
            h, w = im.shape
            s, nc, rm = probe(im)
            wr.writerow([n, ds, gt[n], w, h, '%.1f' % (w * h / max(1, gt[n])),
                         '%.3f' % s, '%.1f' % nc, '%.1f' % rm])
        except Exception as ex:
            wr.writerow([n, ds, gt[n], '', '', '', '', '', str(ex)[:40]])
        if (i + 1) % 100 == 0:
            print('  %d/%d (%.1f img/s)' % (i + 1, len(names), (i + 1) / max(1e-9, time.time() - t0)), flush=True)
    fh.close()
    print('[scale/%s] DONE %d -> %s' % (ds, len(names), out), flush=True)


if __name__ == '__main__':
    main()
