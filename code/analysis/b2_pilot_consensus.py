# -*- coding: utf-8 -*-
"""B2 试跑（第三信号）：**跨家族共识**——完全不需要标注，且七家族的答案都在同一批 item 上。

信号：对家族 F 的每个 item，取其**与其它家族中位数的差异**：
      dis_F = |pred_F − median_{G≠F}(pred_G)| / max(median_{G≠F}(pred_G), 1)
（"别人都这么说，你不一样" —— 这是与标注、检测器、尺度、措辞都无关的信号。）

度量用**稳健版**（前两轮试跑暴露的问题：相对误差的极端离群值会主导 MAE 腿）：
  · err_i = min(|pred_i − gt_i| / gt_i, 1)      ← 有界相对误差（clip 到 1）
  · 同时报**中位**相对误差，避免单点爆炸
判据同前（AUC ≥ 0.65 且 有界MAE@20% ≤ 0.6 × 有界MAE@100%），并额外报告"与随机/与零信号"的对照。
"""
import csv
import io
import json
import os
import statistics as st
import sys

sys.stdout.reconfigure(encoding='utf-8')
MER = r'<WORKDIR>\PaperB\analysis\e2xt_a800\merged'
E2 = r'<WORKDIR>\PaperB\analysis\e2_newh20'
FAMS = ['gemma3-12b', 'InternVL3_5-8B', 'Phi-3.5-vision-instruct',
        'llava-onevision-qwen2-7b-ov', 'qwen3-vl-32b-awq', 'internvl25-8b-awq', 'qwen25vl-72b-awq']
DOMS = ['st_a', 'ucf', 'visdrone', 'aitod']
ABSTAIN = ('abstain', 'cannot_judge', 'no_people')


def load(fam, ds):
    for d in (MER, E2):
        p = os.path.join(d, 'e1_%s_%s_base.csv' % (fam, ds))
        if os.path.exists(p):
            out = {}
            for r in csv.DictReader(io.open(p, encoding='utf-8-sig')):
                raw = str(r.get('raw') or '').lower()
                v = None if any(k in raw for k in ABSTAIN) else None
                if v is None:
                    try:
                        v = float(str(r['pred']).strip())
                    except (TypeError, ValueError):
                        v = None
                try:
                    gt = float(r['gt'])
                except (TypeError, ValueError):
                    continue
                if v is not None:
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
    n1 = sum(label); n0 = len(label) - n1
    if n1 == 0 or n0 == 0:
        return None
    r = rank(score)
    s1 = sum(r[i] for i in range(len(label)) if label[i])
    return (s1 - n1 * (n1 + 1) / 2.0) / (n1 * n0)


res = {}
print('%-24s %-9s %5s %10s %10s %10s %9s %8s' %
      ('家族', '域', 'n', 'AUC大误差', 'AUC答0', 'clipMAE100', 'clipMAE20', '判定'))
for ds in DOMS:
    tabs = {f: load(f, ds) for f in FAMS}
    tabs = {f: t for f, t in tabs.items() if t}
    if len(tabs) < 3:
        continue
    for fam in sorted(tabs):
        peers = [t for f, t in tabs.items() if f != fam]
        rows = []
        for k in sorted(tabs[fam]):
            if not all(k in p for p in peers):
                continue
            pf, gt = tabs[fam][k]
            med = st.median([p[k][0] for p in peers])
            dis = abs(pf - med) / max(abs(med), 1.0)
            err = min(abs(pf - gt) / gt, 1.0) if gt > 0 else None
            if err is None:
                continue
            rows.append((k, dis, err, int(pf == 0)))
        if len(rows) < 30:
            continue
        dis = [r[1] for r in rows]
        big = [1 if r[2] > 0.5 else 0 for r in rows]
        zz = [r[3] for r in rows]
        if sum(big) < 5:
            continue
        mae_all = sum(r[2] for r in rows) / len(rows)
        k20 = max(1, int(round(0.2 * len(rows))))
        keep = sorted(range(len(rows)), key=lambda i: dis[i])[:k20]
        mae20 = sum(rows[i][2] for i in keep) / len(keep)
        a_big, a_z = auc(dis, big), auc(dis, zz)
        ok = (a_big is not None and a_big >= 0.65) and (mae20 <= 0.6 * mae_all)
        res['%s|%s' % (fam, ds)] = dict(n=len(rows), n_big=sum(big), auc_big=a_big, auc_zero=a_z,
                                        clipmae_all=mae_all, clipmae_20=mae20, usable=bool(ok))
        print('%-24s %-9s %5d %10s %10s %10.3f %9.3f %8s'
              % (fam, ds, len(rows),
                 ('%.3f' % a_big) if a_big is not None else '—',
                 ('%.3f' % a_z) if a_z is not None else '—',
                 mae_all, mae20, '可用' if ok else '不可用'))

u = [v for v in res.values() if v['usable']]
print()
print('=' * 96)
print('跨家族共识试跑判定：%d/%d 个（家族×域）单元满足冻结判据' % (len(u), len(res)))
if res:
    a = [v['auc_big'] for v in res.values() if v['auc_big'] is not None]
    r20 = [v['clipmae_20'] / v['clipmae_all'] for v in res.values() if v['clipmae_all']]
    if a:
        print('  AUC(大误差) 中位 %.3f，范围 %.3f–%.3f；clipMAE@20%% 与 @100%% 之比中位 %.2f'
              % (st.median(a), min(a), max(a), st.median(r20)))
print('=' * 96)
io.open(r'<WORKDIR>\PaperB\analysis\work\b2_pilot_consensus_result.json', 'w', encoding='utf-8').write(
    json.dumps(res, ensure_ascii=False, indent=1))
print('JSON -> b2_pilot_consensus_result.json')
