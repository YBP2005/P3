# -*- coding: utf-8 -*-
"""B2 **试跑**：用**已有**的双尺度结果先判"跨尺度自洽性"值不值得花 GPU。

信号：同一图、同一模型、同一提示词，在 **s640 与 s1536** 两个尺度各答一次；
不一致度 = |pred_640 − pred_1536| / max(pred_1536, 1)。
它不需要任何标注 ⇒ 若它能选掉坏样本，就回答了[external-review] 4/4 家点名的
"an annotation-free rule that works"。

判据（与 `路线B实验方案_P3_20260922.md` §2 的冻结判据**同一条**，此处原样套用）：
  · AUC ≥ 0.65（对"大误差"事件）
  · MAE@20% ≤ 0.6 × MAE@100%
两条都成立 ⇒ 该单元"可用"；本试跑统计有几个单元成立。

数据来源（都已拉回本地，无需 GPU）：
  · Gemma-3-12B：st_a、ucf（native / s640 / s1536）
  · InternVL3.5-8B、Phi-3.5-Vision：VisDrone（s640 / s1536）
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
import json
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')
L = RP('analysis', 'e2xt_a800')
ABL = RP('analysis', 'e2xt_a800', 'ablate')
ABL3 = RP('analysis', 'e2xt_a800', 'ablate3')
ABSTAIN = ('abstain', 'cannot_judge', 'no_people')


def load(p):
    if not os.path.exists(p):
        return None
    out = {}
    for r in csv.DictReader(io.open(p, encoding='utf-8-sig')):
        raw = str(r.get('raw') or '').lower()
        is_ab = any(k in raw for k in ABSTAIN)
        try:
            pred = float(str(r['pred']).strip())
        except (KeyError, TypeError, ValueError):
            pred = None
        try:
            gt = float(r['gt'])
        except (KeyError, TypeError, ValueError):
            continue
        out[r['item']] = (pred, gt, is_ab)
    return out


def rank(x):
    idx = sorted(range(len(x)), key=lambda i: x[i])
    r = [0.0] * len(x)
    for pos, i in enumerate(idx):
        r[i] = pos + 1
    return r


def auc(score, label):
    n1 = sum(label)
    n0 = len(label) - n1
    if n1 == 0 or n0 == 0:
        return None
    r = rank(score)
    s1 = sum(r[i] for i in range(len(label)) if label[i])
    return (s1 - n1 * (n1 + 1) / 2.0) / (n1 * n0)


UNITS = [
    ('Gemma-3-12B', 'st_a', ABL, 'gemma3-12b'),
    ('Gemma-3-12B', 'ucf', ABL, 'gemma3-12b'),
    ('InternVL3.5-8B', 'visdrone', ABL3, 'InternVL3_5-8B'),
    ('Phi-3.5-Vision', 'visdrone', ABL3, 'Phi-3.5-vision-instruct'),
]

res = {}
print('%-18s %-9s %5s %8s %8s %10s %10s %8s' %
      ('家族', '域', '共同n', 'AUC大误差', 'AUC答0', 'MAE@100%', 'MAE@20%', '判定'))
for fam, ds, d, tag in UNITS:
    lo = load(os.path.join(d, 'e1_%s_%s_base_s640.csv' % (tag, ds)))
    hi = load(os.path.join(d, 'e1_%s_%s_base_s1536.csv' % (tag, ds)))
    if not lo or not hi:
        print('%-18s %-9s   缺（%s）' % (fam, ds, 's640' if not lo else 's1536'))
        continue
    keys = sorted(set(lo) & set(hi))
    rows = []
    for k in keys:
        p_lo, gt, ab_lo = lo[k]
        p_hi, _, ab_hi = hi[k]
        if p_lo is None or p_hi is None or gt <= 0:
            continue
        dis = abs(p_lo - p_hi) / max(p_hi, 1.0)
        err = abs((p_hi - gt) / gt)
        rows.append((k, dis, err, int(p_hi == 0 or p_lo == 0), int(ab_lo or ab_hi)))
    if len(rows) < 30:
        print('%-18s %-9s   可用 item 太少（%d）' % (fam, ds, len(rows)))
        continue
    dis = [r[1] for r in rows]
    big = [1 if r[2] > 0.5 else 0 for r in rows]        # 大误差 = 相对误差 > 50%
    z = [r[3] for r in rows]
    mae_all = sum(abs(r[2]) for r in rows) / len(rows)
    k20 = max(1, int(round(0.2 * len(rows))))
    keep = sorted(range(len(rows)), key=lambda i: dis[i])[:k20]
    mae20 = sum(abs(rows[i][2]) for i in keep) / len(keep)
    a_big, a_z = auc(dis, big), auc(dis, z)
    ok = (a_big is not None and a_big >= 0.65) and (mae20 <= 0.6 * mae_all)
    res['%s|%s' % (fam, ds)] = dict(n=len(rows), auc_big=a_big, auc_zero=a_z,
                                    mae_all=mae_all, mae_20=mae20, usable=bool(ok))
    print('%-18s %-9s %5d %8s %8s %10.3f %10.3f %8s'
          % (fam, ds, len(rows),
             ('%.3f' % a_big) if a_big is not None else '—',
             ('%.3f' % a_z) if a_z is not None else '—',
             mae_all, mae20, '可用' if ok else '不可用'))
    print('      （误差是相对值；MAE 列为平均相对误差；判定= AUC≥0.65 且 MAE@20% ≤0.6×MAE@100%）')

print()
u = [v for v in res.values() if v['usable']]
print('=' * 96)
print('试跑判定：%d/%d 个（家族×域）单元满足冻结判据' % (len(u), len(res)))
if res:
    a = [v['auc_big'] for v in res.values() if v['auc_big'] is not None]
    if a:
        print('  AUC(大误差) 范围 %.3f–%.3f；MAE@20%%/MAE@100%% 比值范围 %.2f–%.2f'
              % (min(a), max(a),
                 min(v['mae_20'] / v['mae_all'] for v in res.values()),
                 max(v['mae_20'] / v['mae_all'] for v in res.values())))
print('=' * 96)
io.open(RP('analysis', 'work', 'b2_pilot_result.json'), 'w', encoding='utf-8').write(
    json.dumps(res, ensure_ascii=False, indent=1))
print('JSON -> b2_pilot_result.json')
