#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""p2e_density_run.py —— P2-E 的 **density knob**：官方 DM-Count 在 st_a 182 图上跑输入尺度档位。

★ 仪器**逐字**取官方仓库（`cvlab-stonybrook/DM-Count`，2026-10-02 用 codeload tar.gz 取回）：
    from models import vgg19 ; model = vgg19()
    model.load_state_dict(torch.load(model_path, device))      # 官方就是裸 state_dict
    outputs, _ = model(inputs) ; count = outputs.sum()         # 官方 test.py L56-59 的用法
  归一化（官方 `datasets/crowd.py` L59）：ImageNet mean/std，缩放用 `Image.BICUBIC`。
★ 缩放约定由 **G1 闸门**实测锁定（`p2e_protocol_check.py`，对既有 CSRNet ladder 命中 100%）：
    protocol=mult , value=v  ⇒ 两个方向都 ×v
    protocol=short, value=v  ⇒ 缩放使 min(W,H)=v
★ 输出列与既有 ladder **完全同构**：item,dataset,protocol,value,gt,in_w,in_h,in_px,px_per_obj,pred
   —— 这样"官方 DM-Count" 与 "CSRNet" 两支的差**只是模型之差**。

用法：
  python3 p2e_density_run.py --data st_a --protocol mult --values 0.5,0.75,1.0,1.25,1.5 [--gpu 0]
  python3 p2e_density_run.py --data ucf  --protocol mult --values 0.5,0.75,1.0,1.25,1.5 --model model_qnrf.pth
"""
import argparse
import csv
import glob
import io
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from p2e_common import OUT, load_csv, w  # noqa: E402

REPO = '/root/p3r8_p2e/code/dmcount_repo'
WEIGHTS = '/root/p3r8_p2e/weights/dmcount_official'
DATA = {
    'st_a': ('/root/dense/shanghaitech/images/part_A_test',
             '/root/p3r8_p2e/ref/gt_st_a_test.csv', 'model_sh_A.pth'),
    'ucf': ('/root/dense/ucf/images', '/root/dense/ucf/gt_ucf_test.csv', 'model_qnrf.pth'),
}
# 原图尺寸源（只用来核对缩放约定，不影响推理）
SIZES = {'st_a': '/root/p3r8_p2e/ref/det_st_a_test_yolo11n_whole.csv'}


def img_path(d, item):
    for e in ('.jpg', '.jpeg', '.png'):
        p = os.path.join(d, item + e)
        if os.path.exists(p):
            return p
    g = glob.glob(os.path.join(d, item + '.*'))
    return g[0] if g else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--data', default='st_a', choices=sorted(DATA))
    ap.add_argument('--protocol', default='mult', choices=('mult', 'short'))
    ap.add_argument('--values', default='0.5,0.75,1.0,1.25,1.5')
    ap.add_argument('--model', default='')
    ap.add_argument('--gpu', default='0')
    ap.add_argument('--out', default=os.path.join(OUT, 'p2e_density_ladder.csv'))
    A = ap.parse_args()
    vals = [float(x) for x in A.values.split(',') if x.strip()]

    os.environ['CUDA_VISIBLE_DEVICES'] = A.gpu
    sys.path.insert(0, REPO)
    import torch                     # noqa: E402
    from PIL import Image            # noqa: E402
    from torchvision import transforms  # noqa: E402
    from models import vgg19         # noqa: E402  （官方仓库）
    dev = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

    imgdir, gtcsv, wname = DATA[A.data]
    model_path = os.path.join(WEIGHTS, A.model or wname)
    model = vgg19().to(dev).eval()
    sd = torch.load(model_path, map_location=dev)
    model.load_state_dict(sd)
    print('仪器：官方 vgg19() ← %s（%d B）' % (os.path.basename(model_path), os.path.getsize(model_path)))
    print('约定：protocol=%s values=%s ｜ data=%s ｜ device=%s' % (A.protocol, vals, A.data, dev))

    gt = {}
    for r in load_csv(gtcsv):
        it = str(r.get('item') or r.get('name') or '').strip()
        for e in ('.jpg', '.jpeg', '.png'):
            if it.endswith(e):
                it = it[:-len(e)]
        try:
            gt[it] = float(r.get('gt') or r.get('count'))
        except Exception:
            pass
    tf = transforms.Compose([transforms.ToTensor(),
                             transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])])
    rows = []
    for v in vals:
        done = 0
        for it in sorted(gt):
            p = img_path(imgdir, it)
            if not p:
                continue
            im = Image.open(p).convert('RGB')
            W, H = im.size
            if A.protocol == 'mult':
                nw, nh = max(1, int(round(W * v))), max(1, int(round(H * v)))
            else:
                s = v / float(min(W, H))
                nw, nh = max(1, int(round(W * s))), max(1, int(round(H * s)))
            im2 = im.resize((nw, nh), Image.BICUBIC)
            x = tf(im2).unsqueeze(0).to(dev)
            with torch.no_grad():
                out, _ = model(x)
                pred = float(out.sum().item())
            rows.append([it, A.data, A.protocol, '%.4f' % v, gt[it], nw, nh, nw * nh,
                         '%.1f' % ((nw * nh) / gt[it] if gt[it] else 0), '%.4f' % pred])
            done += 1
        print('   value=%-7s 完成 %d 项' % (v, done))
    p = w(A.out, ['item', 'dataset', 'protocol', 'value', 'gt', 'in_w', 'in_h', 'in_px',
                  'px_per_obj', 'pred'], rows)
    print('已写 %s（%d 行）' % (p, len(rows)))
    print('P2E_DENSITY_DONE')
    return 0


if __name__ == '__main__':
    sys.exit(main())
