# -*- coding: utf-8 -*-
"""无标注（annotation-free）可辨性代理：把 §3.3 的"自然下一步"做成**实测**。

背景：正文 §3.3 的代理 a_i = "实例标注框内**未被其他实例框覆盖**的像素数"，图级取中位数 p。
它的软肋是**需要实例级标注框**（[external-review] E 类意见："不可部署"）。
本脚本用**检测器框**替换标注框，按**同一函数形式**重算代理，并测量：
  1. 判别力：对语料"答 0"（弃权的可观测形式）的 AUC；
  2. 选择性预测：保留最可辨 20% 图后的 MAE 变化；
  3. ★ 近似误差/稳定性：换检测器（YOLO 切片 vs RetinaNet）与换分数阈值，代理序数与 AUC 变动多少
     —— 这是"可部署"必须给出的误差条，而不是一句"下一步可做"。

数据（都在本地）：
  · 检测框 npz：`analysis/data/harvest_A/{gaps__,rn__}boxes_st_a_test_*.npz`（已拼回整图坐标）
  · 语料逐图结果：`repro_github/data/derived/e2_pools/dense_results/vlm_st_a_base_whole.csv`
判据（先写死，避免事后挑口径）：
  · AUC ≥ 0.65 ⇒ "无标注代理可作分诊信号"；0.55–0.65 记"弱"；<0.55 记"不成立"；
  · 换检测器后 AUC 变动 ≤0.05 ⇒ "对检测器选择稳健"。
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
import csv
import io
import os
import sys

import numpy as np

sys.stdout.reconfigure(encoding='utf-8')
HA = NR('analysis', 'data', 'harvest_A')
CORP = RP('repro_github', 'data', 'derived', 'e2_pools', 'dense_results')
OUT = RP('analysis', 'work', 'a_lightfree_result.json')
SCORE_MIN = 0.30
NMS_IOU = 0.7


def load_boxes(path):
    z = np.load(path, allow_pickle=True)
    return {k: np.asarray(z[k], dtype=np.float32) for k in z.files}


def nms(b, iou_thr=NMS_IOU):
    """按分数降序的贪心 NMS（b: (N,5) = x1,y1,x2,y2,score）。"""
    if len(b) == 0:
        return b
    order = np.argsort(-b[:, 4])
    b = b[order]
    keep = []
    while len(b):
        cur = b[0]
        keep.append(cur)
        if len(b) == 1:
            break
        rest = b[1:]
        xx1 = np.maximum(cur[0], rest[:, 0]); yy1 = np.maximum(cur[1], rest[:, 1])
        xx2 = np.minimum(cur[2], rest[:, 2]); yy2 = np.minimum(cur[3], rest[:, 3])
        iw = np.clip(xx2 - xx1, 0, None); ih = np.clip(yy2 - yy1, 0, None)
        inter = iw * ih
        a1 = (cur[2] - cur[0]) * (cur[3] - cur[1])
        a2 = (rest[:, 2] - rest[:, 0]) * (rest[:, 3] - rest[:, 1])
        iou = inter / np.maximum(a1 + a2 - inter, 1e-9)
        b = rest[iou < iou_thr]
    return np.array(keep, dtype=np.float32)


def proxy(boxes, chunk=1500):
    """a_i = 自己的框面积 − 与其他框的相交面积（≥0）；返回中位数、均值、覆盖数、检测数。"""
    if len(boxes) == 0:
        return None
    x1, y1, x2, y2 = boxes[:, 0], boxes[:, 1], boxes[:, 2], boxes[:, 3]
    area = np.clip(x2 - x1, 0, None) * np.clip(y2 - y1, 0, None)
    covered = np.zeros(len(boxes), dtype=np.float64)
    for s in range(0, len(boxes), chunk):
        e = min(len(boxes), s + chunk)
        ix1 = np.maximum(x1[s:e, None], x1[None, :]); iy1 = np.maximum(y1[s:e, None], y1[None, :])
        ix2 = np.minimum(x2[s:e, None], x2[None, :]); iy2 = np.minimum(y2[s:e, None], y2[None, :])
        iw = np.clip(ix2 - ix1, 0, None); ih = np.clip(iy2 - iy1, 0, None)
        inter = iw * ih
        for i in range(s, e):
            inter[i - s, i] = 0.0
        covered[s:e] = inter.sum(axis=1)
    a = np.clip(area - covered, 0, None)
    return dict(n=len(boxes), med=float(np.median(a)), mean=float(a.mean()),
                q1=float(np.percentile(a, 25)), q3=float(np.percentile(a, 75)))


def rank(x):
    x = np.asarray(x, dtype=float)
    o = x.argsort()
    r = np.empty(len(x), dtype=float)
    r[o] = np.arange(1, len(x) + 1)
    # 并列取平均秩
    u, inv, cnt = np.unique(x, return_inverse=True, return_counts=True)
    if (cnt > 1).any():
        for k in np.where(cnt > 1)[0]:
            m = inv == k
            r[m] = r[m].mean()
    return r


def spearman(a, b):
    ra, rb = rank(a), rank(b)
    ra = ra - ra.mean(); rb = rb - rb.mean()
    return float((ra * rb).sum() / np.sqrt((ra ** 2).sum() * (rb ** 2).sum()))


def auc(score, label):
    """AUC(score → label=1)，用 Mann-Whitney（对并列稳健）。"""
    score = np.asarray(score, float); label = np.asarray(label, int)
    n1, n0 = int(label.sum()), int((1 - label).sum())
    if n1 == 0 or n0 == 0:
        return None
    r = rank(score)
    return float((r[label == 1].sum() - n1 * (n1 + 1) / 2.0) / (n1 * n0))


def load_corpus(ds='st_a'):
    p = os.path.join(RP('repro_github', 'data', 'derived', 'e2_pools', 'dense_results'), 'vlm_%s_base_whole.csv' % ds)
    out = {}
    for r in csv.DictReader(io.open(p, encoding='utf-8-sig')):
        it = r['item']
        key = os.path.splitext(it)[0]
        try:
            gt = float(r['gt']); pred = float(r['pred'])
        except (TypeError, ValueError):
            continue
        raw = (r.get('raw') or '').lower()
        out[key] = dict(gt=gt, pred=pred, zero=int(pred == 0),
                        abstain=int(('abstain' in raw) or ('refus' in raw)))
    return out


def evaluate(px, corp):
    keys = [k for k in px if k in corp]
    p = np.array([px[k]['med'] for k in keys], float)
    n = np.array([px[k]['n'] for k in keys], float)
    zero = np.array([corp[k]['zero'] for k in keys], int)
    gt = np.array([corp[k]['gt'] for k in keys], float)
    pr = np.array([corp[k]['pred'] for k in keys], float)
    ae = np.abs(pr - gt)
    rel = (pr - gt) / np.maximum(gt, 1)
    res = dict(n_images=len(keys), zero_rate=float(zero.mean()),
               auc_proxy_notzero=None, auc_count=None,
               spearman_proxy_absrel=spearman(p, np.abs(rel)) if len(keys) > 5 else None)
    # 判据方向：可辨性越高 ⇒ 越不容易答 0
    res['auc_proxy_notzero'] = auc(p, 1 - zero)
    res['auc_count_notzero'] = auc(n, 1 - zero)  # 平凡基线：检测数
    # 选择性预测：最可辨 20% vs 全部 vs 最不可辨 20%
    k = max(1, int(round(0.2 * len(keys))))
    hi = np.argsort(-p)[:k]; lo = np.argsort(p)[:k]
    res['mae_all'] = float(ae.mean())
    res['mae_top20'] = float(ae[hi].mean())
    res['mae_bottom20'] = float(ae[lo].mean())
    res['mae_reduction_top20_pct'] = float(100 * (1 - ae[hi].mean() / ae.mean()))
    res['rel_all'] = float(rel.mean()); res['rel_top20'] = float(rel[hi].mean())
    res['absrel_all'] = float(np.abs(rel).mean()); res['absrel_top20'] = float(np.abs(rel[hi].mean()))
    return res


def main():
    corp = load_corpus('st_a')
    print('语料 st_a：%d 张有 gt/pred' % len(corp))
    runs = [
        ('YOLO 切片 tile256 (score≥%.2f)' % SCORE_MIN,
         NR('analysis', 'data', 'harvest_A', 'gaps__boxes_st_a_test_ucf_tiles_full_s0_tile256_ms1024_iou0.7.npz')),
        ('YOLO 切片 tile512', NR('analysis', 'data', 'harvest_A', 'gaps__boxes_st_a_test_ucf_tiles_full_s0_tile512_ms1024_iou0.7.npz')),
        ('RetinaNet 整图', NR('analysis', 'data', 'harvest_A', 'rn__boxes_st_a_test_retinanet_whole_ms800.npz')),
        ('RetinaNet tile256', NR('analysis', 'data', 'harvest_A', 'rn__boxes_st_a_test_retinanet_tile256_ms800.npz')),
    ]
    allres = {}
    for name, path in runs:
        if not os.path.exists(path):
            print('  跳过（缺文件）：%s' % name); continue
        raw = load_boxes(path)
        px = {}
        for k, b in raw.items():
            key = os.path.splitext(k)[0]
            b = b[b[:, 4] >= SCORE_MIN] if b.shape[1] >= 5 else b
            b = nms(b)
            r = proxy(b)
            if r:
                px[key] = r
        ev = evaluate(px, corp)
        allres[name] = ev
        print('\n== %s ==' % name)
        print('  图数 %d；检测数中位 %.0f' % (ev['n_images'],
              float(np.median([px[k]['n'] for k in px]))))
        print('  AUC(代理 → 非零) = %.3f   |  AUC(检测数 → 非零) = %.3f（平凡基线）'
              % (ev['auc_proxy_notzero'], ev['auc_count_notzero']))
        print('  Spearman(代理, |相对偏差|) = %+.3f' % ev['spearman_proxy_absrel'])
        print('  MAE：全部 %.1f → 最可辨 20%% %.1f（降 %.1f%%）；最不可辨 20%% %.1f'
              % (ev['mae_all'], ev['mae_top20'], ev['mae_reduction_top20_pct'], ev['mae_bottom20']))
    if allres:
        a = [v['auc_proxy_notzero'] for v in allres.values()]
        m = [v['mae_reduction_top20_pct'] for v in allres.values()]
        print('\n== 跨检测器稳定性 ==')
        print('  AUC 范围 %.3f–%.3f（极差 %.3f）' % (min(a), max(a), max(a) - min(a)))
        print('  最可辨 20%% 的 MAE 降幅范围 %.1f%%–%.1f%%' % (min(m), max(m)))
        verdict = ('可作分诊信号' if min(a) >= 0.65 else ('弱' if min(a) >= 0.55 else '不成立'))
        spread = ('稳健' if (max(a) - min(a)) <= 0.05 else '对检测器敏感')
        print('  判定：AUC 下界 %.3f ⇒ %s；跨检测器极差 %.3f ⇒ %s' % (min(a), verdict, max(a) - min(a), spread))
        allres['_summary'] = dict(auc_min=min(a), auc_max=max(a), auc_spread=max(a) - min(a),
                                  mae_reduction_min=min(m), mae_reduction_max=max(m),
                                  verdict=verdict, detector_stability=spread)
    import json
    io.open(OUT, 'w', encoding='utf-8').write(json.dumps(allres, ensure_ascii=False, indent=1))
    print('\nJSON -> %s' % OUT)


if __name__ == '__main__':
    main()
