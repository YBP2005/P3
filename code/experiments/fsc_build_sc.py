# -*- coding: utf-8 -*-
"""fsc_build_sc.py — 由**发布件**按**统一直线比例**重渲染 FSC-147 图像（E1 分辨率敏感性用）。

## 为什么推翻上一版（`fsc_build768.py`，longest-side 口径）
上一版把**最长边**归一到 N。核对发布件后确认：FSC-147 官方发布件 `images_384_VarV2` 的 6146 张图
**短边恒为 384**（占比 100%），**长边在 384–1918 之间随长宽比变化**。也就是说"384"是**短边约束**，
不是统一画布。按最长边归一会在高长宽比图上把短边压到 384 以下（例：384×1229 → 240×768，
面积比 0.391）⇒ "768 = 上采样"这个标签对部分图是**假的**，分辨率对比被长宽比污染。
⇒ 本版改为**统一直线缩放**：scale = N / 短边(384)，对每张图用**同一个**比例，长宽比与内容逐像素不变：
     · N=256：scale=0.667，面积 0.444×（信息只减不增 → 干净的"更低分辨率"点）
     · N=768：scale=2.000，面积 4.000×（**同一信息、更大画布**，如实标注 upsampled）
   源图短边 ≠ 384 即**拒绝**该图并在报告里列出（不静默放过）。

产物目录内含 `images/`、`annotation_FSC147_384.json`（软链）、`sample_test_ids.txt`（软链）、
`build_report.txt`（逐图 src/dst 尺寸与实测缩放比例）。用法：
  python fsc_build_sc.py --src /root/fsc147 --out /root/fsc147_sc256 --side 256
  python fsc_build_sc.py --src /root/fsc147 --out /root/fsc147_sc768 --side 768
"""
import argparse
import io
import os
import sys
from PIL import Image

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
ap = argparse.ArgumentParser()
ap.add_argument('--src', default='/root/fsc147')
ap.add_argument('--out', required=True)
ap.add_argument('--side', type=int, required=True, help='目标**短边**像素（源短边固定 384）')
ap.add_argument('--only-ids', default='sample_test_ids.txt')
A = ap.parse_args()

ids = [x.strip() for x in io.open(os.path.join(A.src, A.only_ids)) if x.strip()]
os.makedirs(os.path.join(A.out, 'images'), exist_ok=True)
for f in ('annotation_FSC147_384.json', 'sample_test_ids.txt'):
    lk = os.path.join(A.out, f)
    if not os.path.exists(lk):
        try:
            os.symlink(os.path.join(A.src, f), lk)
        except OSError:
            import shutil
            shutil.copy2(os.path.join(A.src, f), lk)

rep = ['src=%s side=%d ids=%d' % (A.src, A.side, len(ids)), 'item\tsrc_wxh\tdst_wxh\tratio_meas/ratio_nominal']
ok = bad = 0
scales = []
for it in ids:
    sp = os.path.join(A.src, 'images', it)
    if not os.path.exists(sp):
        rep.append('%s\tMISSING' % it); bad += 1; continue
    with Image.open(sp) as im:
        w, h = im.size
        if min(w, h) != 384:
            rep.append('%s\t%d x %d\t短边≠384 ⇒ 跳过' % (it, w, h)); bad += 1; continue
        s = A.side / 384.0
        nw, nh = max(1, round(w * s)), max(1, round(h * s))
        im.convert('RGB').resize((nw, nh), Image.LANCZOS).save(os.path.join(A.out, 'images', it), quality=95)
    scales.append(((nw * nh) / float(w * h)) / (s * s))
    rep.append('%s\t%dx%d\t%dx%d\t%.4f' % (it, w, h, nw, nh, scales[-1]))
    ok += 1

rep.insert(1, 'ok=%d skip=%d ｜ 实测面积比/标称值：%.4f–%.4f（应≈1.0000）'
           % (ok, bad, min(scales), max(scales)))
io.open(os.path.join(A.out, 'build_report.txt'), 'w', encoding='utf-8', newline='\n').write('\n'.join(rep) + '\n')
print('写出 %s：ok=%d skip=%d ｜ scale=%.4f（短边 384→%d）｜ 面积比应=%.3f'
      % (A.out, ok, bad, A.side / 384.0, A.side, (A.side / 384.0) ** 2))
print('  实测面积比/标称：%.4f–%.4f' % (min(scales), max(scales)))
sys.exit(1 if bad else 0)
