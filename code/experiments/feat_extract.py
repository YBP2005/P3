#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""feat_extract.py — 与模型无关的图像级"可确证性"特征（纯 CPU，不占 GPU）

动机：先前 L（可确证性得分）只用单变量代理 px/obj，风险-覆盖也是用 px/obj 当选择器。
本脚本为每张真实图算出一组**外生**特征，供后续用完整 L 重做选择器评估：
  sharp      : 灰度 Laplacian 方差（清晰度）
  edge_dens  : 归一化边缘密度
  loc_con    : 8x8 块灰度标准差的均值（局部对比度）
  probe_cnt  : 经典 blob 探针估计的实例数（模型无关的"能枚举出几个"）
  probe_rec  : probe_cnt / GT（探针召回）
  probe_px   : 每目标在探针尺度下的有效像素（探针域可辨性）

用法: python feat_extract.py <st_a|ucf|visdrone> [limit]
输出: /root/feat/feat_<ds>.csv
"""
import csv, math, os, sys, time
import cv2
import numpy as np

OUT = '/root/feat'
os.makedirs(OUT, exist_ok=True)
PROBE_PX = 512 * 512          # 探针固定预算，保证跨图可比


def load_gt(ds):
    if ds == 'ucf':
        idir = '/root/dense/ucf_qnrf/UCF-QNRF_ECCV18/Test'
        gt = {}
        with open('/root/dense/ucf_qnrf/counts.csv', encoding='utf-8-sig') as f:
            for r in csv.DictReader(f):
                if r['split'] == 'Test':
                    gt[os.path.splitext(os.path.basename(r['file']))[0]] = int(r['count'])
        return idir, gt, '.jpg'
    if ds == 'st_a':
        idir = '/root/dense/shanghaitech/images/part_A_test'
        gt = {}
        with open('/root/dense/shanghaitech/counts.csv', encoding='utf-8-sig') as f:
            for r in csv.DictReader(f):
                if r.get('part') == 'part_A' and r.get('split') == 'test':
                    gt[os.path.splitext(os.path.basename(r['file']))[0]] = int(r['count'])
        return idir, gt, '.jpg'
    if ds == 'visdrone':
        idir = '/root/aerial/visdrone/images'
        gt = {}
        with open('/root/aerial/gt_visdrone.csv', encoding='utf-8-sig') as f:
            for r in csv.DictReader(f):
                gt[r['item']] = int(r['gt'])
        return idir, gt, '.jpg'
    raise SystemExit('unknown ds ' + ds)


def probe(gray, n_gt):
    """经典 blob 探针：在固定 512x512 预算下找局部极大（DoG），按期望间距做非极大抑制。
    返回 (cnt, px_per_obj_probe)。模型无关。"""
    h0, w0 = gray.shape
    s = math.sqrt(PROBE_PX / float(w0 * h0))
    if s < 1.0:
        gray = cv2.resize(gray, (max(32, int(w0 * s)), max(32, int(h0 * s))),
                          interpolation=cv2.INTER_AREA)
    h, w = gray.shape
    g = cv2.GaussianBlur(gray, (0, 0), 1.2)
    dog = cv2.GaussianBlur(gray, (0, 0), 1.0) - cv2.GaussianBlur(gray, (0, 0), 2.5)
    # 期望间距：假设目标大致均匀分布
    spacing = max(3.0, math.sqrt(h * w / max(1.0, n_gt)))
    r = max(2, int(round(spacing / 2.0)))
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * r + 1, 2 * r + 1))
    mx = cv2.dilate(dog, k)
    peaks = (dog >= mx - 1e-6) & (dog > np.percentile(dog, 97.0))
    nlab, _ = cv2.connectedComponents(peaks.astype(np.uint8))
    cnt = max(0, nlab - 1)
    ppo_probe = (w * h) / max(1.0, n_gt)
    return cnt, ppo_probe


def feats(path, n_gt):
    im = cv2.imread(path, cv2.IMREAD_COLOR)
    if im is None:
        return None
    h, w = im.shape[:2]
    gray = cv2.cvtColor(im, cv2.COLOR_BGR2GRAY)
    lap = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    edges = cv2.Canny(gray, 60, 160)
    edge_dens = float((edges > 0).mean())
    g32 = gray.astype(np.float32)
    hh, ww = (h // 8) * 8, (w // 8) * 8
    if hh >= 8 and ww >= 8:
        blocks = g32[:hh, :ww].reshape(hh // 8, 8, ww // 8, 8).transpose(0, 2, 1, 3)
        loc_con = float(blocks.reshape(-1, 64).std(axis=1).mean())
    else:
        loc_con = float(g32.std())
    cnt, ppo_probe = probe(gray, n_gt)
    nat_px = w * h
    return dict(nat_w=w, nat_h=h, nat_px=nat_px, px_per_obj=nat_px / max(1, n_gt),
                sharp=lap, edge_dens=edge_dens, loc_con=loc_con,
                probe_cnt=cnt, probe_rec=cnt / max(1.0, n_gt), probe_px=ppo_probe)


def main():
    ds = sys.argv[1]
    lim = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    idir, gt, ext = load_gt(ds)
    names = [n for n in sorted(gt) if os.path.exists(os.path.join(idir, n + ext))]
    if lim > 0:
        names = names[:lim]
    out = os.path.join(OUT, 'feat_%s.csv' % ds)
    fh = open(out, 'w', encoding='utf-8-sig', newline='')
    wr = csv.writer(fh)
    wr.writerow(['item', 'dataset', 'gt', 'nat_w', 'nat_h', 'nat_px', 'px_per_obj',
                 'sharp', 'edge_dens', 'loc_con', 'probe_cnt', 'probe_rec', 'probe_px'])
    t0 = time.time()
    for i, n in enumerate(names):
        try:
            f = feats(os.path.join(idir, n + ext), gt[n])
            if f is None:
                continue
            wr.writerow([n, ds, gt[n], f['nat_w'], f['nat_h'], f['nat_px'],
                         '%.1f' % f['px_per_obj'], '%.2f' % f['sharp'],
                         '%.5f' % f['edge_dens'], '%.2f' % f['loc_con'],
                         f['probe_cnt'], '%.4f' % f['probe_rec'], '%.1f' % f['probe_px']])
        except Exception as ex:
            wr.writerow([n, ds, gt[n], '', '', '', '', '', '', '', '', '', str(ex)[:40]])
        if (i + 1) % 200 == 0:
            print('  %d/%d (%.1f img/s)' % (i + 1, len(names), (i + 1) / max(1e-9, time.time() - t0)),
                  flush=True)
    fh.close()
    print('[feat/%s] DONE %d -> %s' % (ds, len(names), out), flush=True)


if __name__ == '__main__':
    main()
