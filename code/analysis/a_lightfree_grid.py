# -*- coding: utf-8 -*-
"""尽职检查：无标注代理的负结果是否只是**阈值/合并参数**没调好？
对判别力最好的那一档（YOLO 切片 tile256）做 score × NMS 网格，看 AUC 上界与稳定性。
若任何设置都到不了 0.65 或跨设置极差 >0.05，则负结果站得住。
"""


# ── 复现包统一根：`_repro_root.py`（与本文件同目录）──────────────────────────────
# RP(*parts) = 作者树相对路径 -> 绝对路径（作者树上原样；放行树上查前缀映射表）；
# NR(*parts) = **未随包发布**的作者侧路径（放行树上落到 _NOT_RELEASED/，使失败可见）。
try:
    from _repro_root import resolve as RP, not_released as NR
except ImportError:                      # 只拷走单个脚本时：就地反推仓库根，无前缀映射表
    import os as _o
    _r = _o.environ.get('PAPERB_ROOT') or _o.path.dirname(_o.path.dirname(_o.path.abspath(__file__)))
    RP = lambda *p: _o.path.join(_r, *p)
    NR = lambda *p: _o.path.join(_r, '_NOT_RELEASED', *p)
import io
import json
import sys

import numpy as np

sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, RP('analysis', 'work'))
from a_lightfree import (HA, load_boxes, nms, proxy, evaluate, load_corpus, auc)

P = HA + r'\gaps__boxes_st_a_test_ucf_tiles_full_s0_tile256_ms1024_iou0.7.npz'
corp = load_corpus('st_a')
raw = load_boxes(P)
print('图数 %d（原始检测框）' % len(raw))
rows = []
for score in (0.20, 0.30, 0.50, 0.70):
    for iou in (0.5, 0.7, 0.9):
        px = {}
        for k, b in raw.items():
            key = k.rsplit('.', 1)[0]
            b = b[b[:, 4] >= score]
            b = nms(b, iou)
            r = proxy(b)
            if r:
                px[key] = r
        ev = evaluate(px, corp)
        med_n = float(np.median([px[k]['n'] for k in px]))
        rows.append((score, iou, ev['auc_proxy_notzero'], ev['mae_reduction_top20_pct'],
                     ev['spearman_proxy_absrel'], med_n, ev['n_images']))
        print('  score≥%.2f NMS%.1f → AUC %.3f | MAE降 %+6.1f%% | ρ %+0.3f | 检测数中位 %.0f | 图 %d'
              % (score, iou, ev['auc_proxy_notzero'], ev['mae_reduction_top20_pct'],
                 ev['spearman_proxy_absrel'], med_n, ev['n_images']))

a = [r[2] for r in rows]
print()
print('AUC 上界 %.3f（判据 0.65）⇒ %s' % (max(a), '可达' if max(a) >= 0.65 else '**任何参数都达不到**'))
print('跨参数极差 %.3f（判据 ≤0.05）⇒ %s' % (max(a) - min(a), '稳健' if max(a) - min(a) <= 0.05 else '**敏感**'))
io.open(RP('analysis', 'work', 'a_lightfree_grid.json'), 'w', encoding='utf-8').write(
    json.dumps([dict(score=s, nms_i=i, auc=x, mae_red=m, rho=r, n_med=n, imgs=nimg)
                for s, i, x, m, r, n, nimg in rows], ensure_ascii=False, indent=1))
print('JSON -> a_lightfree_grid.json')
