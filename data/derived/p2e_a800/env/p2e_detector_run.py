#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""p2e_detector_run.py —— P2-E 的 **detector knob**：YOLO11n（COCO 零样本）在 182 张 st_a 上**整幅**跑。

★ 仪器选型依据：论文自己的 dense 端 E5 数据就是 **yolo11n 整幅 + 300 上限 + τ 列 0.05…0.9**
  （`analysis/data/E5_data/det_st_a_test_yolo11n_whole.csv`，182 项）。本脚本复刻该协议，
  **只补上缺的那一维：输入尺寸**（上级 2026-10-02 决定：整幅，不做 2×2 平铺）。
★ `τ` 是**后处理**：本脚本对每张图**保存全部原始检测的 score/label**（topk=300），
  于是任何 τ 都能事后算，**不需要重新推理** —— 这就是"五档水平"能便宜的原因。
★ 档位（判据件 `knobs.detector.primary_levels`，跑前固定）：
  imgsz ∈ {640, 896, 1024, 1280, 1536}，τ 主档固定 0.25；副口径报 5×13 全网格。

用法：
  python3 p2e_detector_run.py [--gpu 0] [--imgsz 640,896,1024,1280,1536] [--limit N]
  产出：out/p2e_detector_raw.csv（逐检测）与 out/p2e_detector_ladder.csv（τ×imgsz 汇总，列与 VisDrone ladder 同构）
"""
import argparse
import io
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from p2e_common import OUT, load_csv, w  # noqa: E402

IMGDIR = '/root/dense/shanghaitech/images/part_A_test'
GTCSV = '/root/p3r8_p2e/ref/gt_st_a_test.csv'
TAUS = [0.05, 0.1, 0.15, 0.2, 0.25, 0.3, 0.35, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]
TOPK = 300


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--gpu', default='0')
    ap.add_argument('--imgsz', default='640,896,1024,1280,1536')
    ap.add_argument('--weights', default='yolo11n.pt')
    ap.add_argument('--limit', type=int, default=0)
    A = ap.parse_args()
    sizes = [int(x) for x in A.imgsz.split(',') if x.strip()]
    os.environ['CUDA_VISIBLE_DEVICES'] = A.gpu
    from ultralytics import YOLO  # noqa: E402

    fps = [os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', A.weights), A.weights,
           os.path.join('/root/p3r8_p2e/weights', A.weights)]
    wp = next((p for p in fps if os.path.exists(p)), A.weights)
    model = YOLO(wp)
    print('仪器：ultralytics %s ｜ 权重 %s ｜ 整幅（无平铺）｜ topk=%d' % (A.weights, wp, TOPK))
    print('档位 imgsz=%s ｜ τ 网格=%s（τ 为后处理，不需重推理）' % (sizes, TAUS))

    gt = {}
    for r in load_csv(GTCSV):
        it = str(r.get('item') or r.get('name') or '').strip()
        for e in ('.jpg', '.jpeg', '.png'):
            if it.endswith(e):
                it = it[:-len(e)]
        try:
            gt[it] = float(r.get('gt') or r.get('count'))
        except Exception:
            pass
    items = sorted(gt)
    if A.limit:
        items = items[:A.limit]

    raw = []
    for sz in sizes:
        for it in items:
            p = None
            for e in ('.jpg', '.jpeg', '.png'):
                q = os.path.join(IMGDIR, it + e)
                if os.path.exists(q):
                    p = q
                    break
            if not p:
                continue
            res = model.predict(source=p, imgsz=sz, conf=0.001, max_det=TOPK, verbose=False)[0]
            b = res.boxes
            if b is None or len(b) == 0:
                continue
            cls = b.cls.cpu().numpy().tolist()
            sc = b.conf.cpu().numpy().tolist()
            for k, (c, s) in enumerate(zip(cls, sc)):
                raw.append([it, sz, gt[it], k + 1, '%.5f' % s, int(c), 1 if int(c) == 0 else 0])
        print('   imgsz=%-5d 完成（累计原始检测 %d 条）' % (sz, len(raw)))
    pr = w(os.path.join(OUT, 'p2e_detector_raw.csv'),
           ['item', 'imgsz', 'gt', 'rank', 'score', 'cls', 'is_person'], raw)

    # 事后按 τ 汇总（列与既有 VisDrone ladder 同构）
    agg = {}
    for it, sz, g, rank, s, c, isp in raw:
        agg.setdefault((it, sz), []).append((float(s), int(isp)))
    lad = []
    for (it, sz), ds in sorted(agg.items()):
        g = gt[it]
        for t in TAUS:
            keep = [isp for (s, isp) in ds if s >= t]
            lad.append([it, A.weights, '%.2f' % t, sz, g, len(keep), sum(keep)])
    pl = w(os.path.join(OUT, 'p2e_detector_ladder.csv'),
           ['item', 'weights', 'tau', 'imgsz', 'gt', 'n_det', 'n_det_person'], lad)
    print('已写 %s（%d 条原始检测）与 %s（%d 行）' % (pr, len(raw), pl, len(lad)))
    print('P2E_DETECTOR_DONE')
    return 0


if __name__ == '__main__':
    sys.exit(main())
