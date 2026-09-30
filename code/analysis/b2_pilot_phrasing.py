# -*- coding: utf-8 -*-
"""B2 试跑（第二信号）：**跨提示词措辞自洽性**——不需要任何标注，且数据已在手。

两个候选信号（都用零 GPU 的既有数据试）：
  ① 跨尺度不一致度   |pred_640 − pred_1536| / max(pred_1536,1)        → 见 b2_pilot.py
  ② 跨措辞不一致度   base / bestA / bestB / bestC 四个契约臂上数值答案的离散度（std/median）
判据（与实验方案 §2 冻结判据相同）：AUC ≥ 0.65（对大误差事件）且 MAE@20% ≤ 0.6 × MAE@100%。

为什么值得试 ②：E3 的四个新家族 + 三个锚点都跑过 `bestA/bestB/bestC`；
"换个说法答案是否稳定"是**模型自身的性质**，与标注、检测器、尺度都无关。
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
MER = RP('analysis', 'e2xt_a800', 'merged')
E2 = RP('analysis', 'e2_newh20')
ARMS = ['base', 'bestA', 'bestB', 'bestC']
ABSTAIN = ('abstain', 'cannot_judge', 'no_people')


def load(fam, ds, arm):
    for d, pre in ((MER, ''), (E2, '')):
        p = os.path.join(d, '%se1_%s_%s_%s.csv' % (pre, fam, ds, arm))
        if os.path.exists(p):
            out = {}
            for r in csv.DictReader(io.open(p, encoding='utf-8-sig')):
                raw = str(r.get('raw') or '').lower()
                if any(k in raw for k in ABSTAIN):
                    v = None
                else:
                    try:
                        v = float(str(r['pred']).strip())
                    except (TypeError, ValueError):
                        v = None
                try:
                    gt = float(r['gt'])
                except (TypeError, ValueError):
                    continue
                out[r['item']] = (v, gt)
            return out
    return None


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


FAMS = ['gemma3-12b', 'InternVL3_5-8B', 'Phi-3.5-vision-instruct',
        'llava-onevision-qwen2-7b-ov', 'qwen3-vl-32b-awq']
DOMS = ['st_a', 'ucf', 'visdrone', 'aitod']

res = {}
print('%-28s %-9s %5s %10s %8s %10s %10s %8s' %
      ('家族', '域', '共同n', 'AUC大误差', 'AUC答0', 'MAE@100%', 'MAE@20%', '判定'))
for fam in FAMS:
    for ds in DOMS:
        tabs = {a: load(fam, ds, a) for a in ARMS}
        if not tabs['base'] or not tabs['bestA']:
            continue
        keys = set(tabs['base'])
        for a in ARMS:
            if tabs[a]:
                keys &= set(tabs[a])
        keys = sorted(keys)
        rows = []
        for k in keys:
            vals = [tabs[a][k][0] for a in ARMS if tabs[a] and tabs[a][k][0] is not None]
            gt = tabs['base'][k][1]
            if len(vals) < 3 or gt <= 0:
                continue
            m = sum(vals) / len(vals)
            sd = (sum((v - m) ** 2 for v in vals) / len(vals)) ** 0.5
            dis = sd / max(abs(m), 1.0)                      # 归一化离散度
            err = abs((tabs['base'][k][0] if tabs['base'][k][0] is not None else 0) - gt) / gt
            z = int(tabs['base'][k][0] == 0)
            rows.append((k, dis, err, z))
        if len(rows) < 30:
            continue
        dis = [r[1] for r in rows]
        big = [1 if r[2] > 0.5 else 0 for r in rows]
        zz = [r[3] for r in rows]
        mae_all = sum(r[2] for r in rows) / len(rows)
        k20 = max(1, int(round(0.2 * len(rows))))
        keep = sorted(range(len(rows)), key=lambda i: dis[i])[:k20]
        mae20 = sum(rows[i][2] for i in keep) / len(keep)
        a_big, a_z = auc(dis, big), auc(dis, zz)
        ok = (a_big is not None and a_big >= 0.65) and (mae20 <= 0.6 * mae_all)
        res['%s|%s' % (fam, ds)] = dict(n=len(rows), auc_big=a_big, auc_zero=a_z,
                                        mae_all=mae_all, mae_20=mae20, usable=bool(ok))
        print('%-28s %-9s %5d %10s %8s %10.3f %10.3f %8s'
              % (fam, ds, len(rows),
                 ('%.3f' % a_big) if a_big is not None else '—',
                 ('%.3f' % a_z) if a_z is not None else '—',
                 mae_all, mae20, '可用' if ok else '不可用'))

print()
u = [v for v in res.values() if v['usable']]
print('=' * 96)
print('跨措辞试跑判定：%d/%d 个（家族×域）单元满足冻结判据' % (len(u), len(res)))
if res:
    a = [v['auc_big'] for v in res.values() if v['auc_big'] is not None]
    r20 = [v['mae_20'] / v['mae_all'] for v in res.values()]
    if a:
        print('  AUC(大误差) 范围 %.3f–%.3f；MAE@20%% 与 MAE@100%% 之比范围 %.2f–%.2f'
              % (min(a), max(a), min(r20), max(r20)))
print('=' * 96)
io.open(RP('analysis', 'work', 'b2_pilot_phrasing_result.json'), 'w', encoding='utf-8').write(
    json.dumps(res, ensure_ascii=False, indent=1))
print('JSON -> b2_pilot_phrasing_result.json')
