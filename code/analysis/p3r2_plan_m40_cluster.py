# -*- coding: utf-8 -*-
"""p3r2_plan_m40_cluster.py —— E5：§M.40 逐构建表的**按起服聚类**读数（只重抽"起服"这一层，不把 item×start 当独立）。

背景：§M.40 的真零行把 n = 153 × 3 起服 = 459 个观测当独立喂给 Wilson；而 3 次起服是
**同一批 153 个项目的重复观测**，不构成额外的独立单元。本器给出：
  * 合并率（459）与合并 Wilson 95%（= 现印口径，作对照）
  * **每个起服各自的率**与三者极差（诚实的最小充分统计量：只有 3 个簇）
  * **簇自助** 95% 区间（重抽 3 个起服，B=2000，seed 20260930）

输入只用已放行件 `data/derived/ea2/<lang>_<build>_s<k>/*.csv`（180 件）。
用法：python _e5_m40_cluster.py [--apply]
"""
import collections
import csv
import io
import json
import os
import random
import statistics as st
import sys

# 放行件相对路径：<repo>/code/analysis/ -> <repo>/data/derived/ea2
A = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'data', 'derived', 'ea2')
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                   'p3r2_plan_m40_cluster_result.json')
B = 2000
SEED = 20260930

BUILDS = [('ivl8b', 'InternVL3.5-8B'), ('phi35', 'Phi-3.5-vision-instruct'),
          ('q32', 'Qwen3-VL-32B-Instruct'), ('gemma12b', 'gemma-3-12b'),
          ('llavaov', 'LLaVA-OneVision-7B')]
POOLS = ['z0easy', 'z0hard']
ARMS = ['base', 'channel']


def wilson(k, n, z=1.959964):
    if not n:
        return (0.0, 0.0)
    p = k / float(n)
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    h = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5)
    return (100 * max(0.0, (c - h) / d), 100 * min(1.0, (c + h) / d))


def rate(rows, arm):
    """返回 (分子, 分母)。channel 臂的 no_people / cannot_judge 记在 raw 里；base 臂的零记在 pred。"""
    if arm == 'channel':
        np_ = sum(1 for r in rows if r['pred'].strip() == '' and 'no_people' in r['raw'])
        cj = sum(1 for r in rows if r['pred'].strip() == '' and 'cannot_judge' in r['raw'])
        return len(rows), np_, cj
    z = sum(1 for r in rows if r['pred'].strip() == '0')
    return len(rows), z, None


def main():
    apply = '--apply' in sys.argv
    rnd = random.Random(SEED)
    out = dict(purpose='§M.40 真零行：合并 Wilson 与**按起服聚类**读数的对照', seed=SEED, B=B, rows=[])
    print('%-24s %-8s %-10s %-22s %-24s %-22s' % ('build', 'pool', '量', '合并率 [Wilson]', '三起服各自的率', '簇自助 95%'))
    for key, disp in BUILDS:
        for pool in POOLS:
            # 载入 3 个起服
            S = {}
            ok = True
            for k in (1, 2, 3):
                d = os.path.join(A, 'cn_%s_s%d' % (key, k))
                fs = [f for f in os.listdir(d) if pool in f and f.endswith('.csv')] if os.path.isdir(d) else []
                if not fs:
                    ok = False
                    break
                S[k] = {a: list(csv.DictReader(io.open(os.path.join(d, f), encoding='utf-8', errors='replace')))
                        for a in ARMS
                        for f in fs if ('_%s_native' % a) in f}
            if not ok:
                print('  %-22s %-8s （起服目录缺失，跳过）' % (disp, pool))
                continue
            for arm, metric in (('channel', 'no_people'), ('channel', 'cannot_judge'), ('base', 'zero')):
                per = []
                for k in (1, 2, 3):
                    rows = S[k][arm]
                    n, np_, cj = rate(rows, arm)
                    num = np_ if metric == 'no_people' else (cj if metric == 'cannot_judge' else np_)
                    per.append((num, n))
                N = sum(n for _, n in per)
                K = sum(k for k, _ in per)
                pooled = 100.0 * K / N
                lo, hi = wilson(K, N)
                # 簇自助：重抽 3 个起服
                bs = []
                for _ in range(B):
                    pick = [per[rnd.randrange(3)] for _ in range(3)]
                    bs.append(100.0 * sum(k for k, _ in pick) / sum(n for _, n in pick))
                bs.sort()
                clo, chi = bs[int(0.025 * B)], bs[min(B - 1, int(0.975 * B))]
                pr = [100.0 * k / n for k, n in per]
                span = max(pr) - min(pr)
                out['rows'].append(dict(build=disp, pool=pool, arm=arm, metric=metric, n=N, k=K,
                                        pooled=round(pooled, 2), wilson=[round(lo, 2), round(hi, 2)],
                                        per_start=[round(x, 2) for x in pr], start_span=round(span, 2),
                                        cluster_ci=[round(clo, 2), round(chi, 2)],
                                        cluster_width=round(chi - clo, 2),
                                        wilson_width=round(hi - lo, 2)))
                print('%-24s %-8s %-10s %7.1f%% [%5.2f,%6.2f]  %-24s [%5.2f,%6.2f]'
                      % (disp[:22], pool, metric, pooled, lo, hi,
                         '/'.join('%.1f' % x for x in pr), clo, chi))
    # 汇总结论
    w = [r for r in out['rows'] if r['metric'] == 'no_people']
    wider = sum(1 for r in w if r['cluster_width'] > r['wilson_width'])
    out['summary'] = dict(
        note='只有 3 个起服 ⇒ 簇自助是最小充分读数；start_span 是三个率本身的极差',
        n_cells=len(out['rows']),
        cluster_wider_than_wilson='%d/%d' % (wider, len(w)),
        max_start_span=max(r['start_span'] for r in out['rows']),
        median_cluster_width=round(st.median(r['cluster_width'] for r in out['rows']), 2),
        median_wilson_width=round(st.median(r['wilson_width'] for r in out['rows']), 2))
    print()
    print('汇总：', json.dumps(out['summary'], ensure_ascii=False))
    if apply:
        io.open(OUT, 'w', encoding='utf-8', newline='\n').write(json.dumps(out, ensure_ascii=False, indent=2))
        print('已写 %s' % OUT)
    else:
        print('（未写盘；加 --apply）')


main()
