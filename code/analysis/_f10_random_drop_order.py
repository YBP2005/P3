# -*- coding: utf-8 -*-
"""_f10_random_drop_order.py —— 随机删档下的**24 单元**跨度保留率与**排序**保全率（在册条目与 T3/T5）。

## 与 `_f10_random_drop.py` 的分工
前者只做检测 τ 六条阶梯（`threeway_curves_v2.csv`），答复"随机删档会不会缩短跨度"。
本脚本把**全部 24 个单元**（与 F.10 同一套：六族阶梯 × 域/构建）都拉进来，并回答**两个**问题：
  ① **幅度**：随机抽 k=4 档后的跨度保留率（中位 / p05 / 最小 / ≥0.90 占比）；
  ② **排序**：随机删档后的单元排序与全长排序的 Spearman（这正是本文真正主张的东西）。
「等点数分位子采样」保留首尾 ⇒ 对跨度是按构造的空操作（保留率 1.00）；**随机删档不保留端点**，
才是对"扫描密度"的诚实扰动。两者**都要报**，否则结论会依赖所选的扰动方式。

阶梯构造**直接 import** `span_equalcount2.py` 的 `build()`（不另写一遍），故口径与 F.10 逐字一致。
产物：`f10_random_drop_order_result.json`（+ .md5）。用法：python -u _f10_random_drop_order.py
"""
import hashlib
import importlib.util
import io
import json
import os
import random
import statistics as st
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
W = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(W, 'f10_random_drop_order_result.json')
K, NDRAW, SEED = 4, 2000, 20260924

spec = importlib.util.spec_from_file_location('sec2', os.path.join(W, 'span_equalcount2.py'))
sec2 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sec2)          # span_equalcount2.py 有 __main__ 守卫，import 不会跑主流程


def span(seq):
    v = [x[1] for x in seq]
    return max(v) - min(v)


def rank(x):
    s = sorted(range(len(x)), key=lambda i: x[i])
    r = [0.0] * len(x)
    i = 0
    while i < len(s):
        j = i
        while j + 1 < len(s) and x[s[j + 1]] == x[s[i]]:
            j += 1
        avg = (i + j) / 2.0 + 1
        for t in range(i, j + 1):
            r[s[t]] = avg
        i = j + 1
    return r


def spearman(a, b):
    ra, rb = rank(a), rank(b)
    n = len(a)
    ma, mb = sum(ra) / n, sum(rb) / n
    num = sum((ra[i] - ma) * (rb[i] - mb) for i in range(n))
    da = sum((ra[i] - ma) ** 2 for i in range(n)) ** 0.5
    db = sum((rb[i] - mb) ** 2 for i in range(n)) ** 0.5
    return num / (da * db) if da and db else float('nan')


def main():
    rnd = random.Random(SEED)
    res = dict(purpose='F.10 随机删档：24 单元的幅度保留率与排序保全率（多条在册条目/ T3 / T5）',
               design='随机抽 k=4 档（不放回）%d 次；幅度=抽样跨度/全长跨度；排序=抽样跨度向量与全长跨度向量的 Spearman'
                      % NDRAW, k=K, per_caliber={})
    for cal in ('person', 'allclass'):
        L = sec2.build(cal)                     # 与 F.10 同一套 24 单元
        units = sorted(L)
        full = [span(L[u]) for u in units]
        rets, rhos = [], []
        for _ in range(NDRAW):
            sub = []
            for u in units:
                seq = L[u]
                n = len(seq)
                ix = sorted(rnd.sample(range(n), K)) if n > K else list(range(n))
                sub.append(span([seq[i] for i in ix]))
            rets.append([s / f for s, f in zip(sub, full) if f])
            rhos.append(spearman(full, sub))
        flat = sorted(x for r in rets for x in r)
        rhos_s = sorted(rhos)
        d = dict(n_units=len(units),
                 unit_retention=dict(median=round(st.median(flat), 3),
                                     p05=round(flat[int(0.05 * len(flat))], 3),
                                     p95=round(flat[int(0.95 * len(flat))], 3),
                                     minimum=round(flat[0], 3),
                                     frac_ge_090=round(sum(1 for x in flat if x >= 0.90) / len(flat), 3)),
                 ordering_spearman=dict(median=round(st.median(rhos_s), 3),
                                        p05=round(rhos_s[int(0.05 * len(rhos_s))], 3),
                                        p95=round(rhos_s[int(0.95 * len(rhos_s))], 3),
                                        minimum=round(rhos_s[0], 3)))
        res['per_caliber'][cal] = d
        print('\n' + '=' * 100)
        print('■ 口径 = %s（%d 单元，随机抽 k=%d × %d 次）' % (cal, len(units), K, NDRAW))
        print('=' * 100)
        print('  幅度（单元×抽样 的跨度保留率）：中位 %.2f ｜ p05 %.2f ｜ p95 %.2f ｜ 最小 %.2f ｜ ≥0.90 占比 %.2f'
              % (d['unit_retention']['median'], d['unit_retention']['p05'], d['unit_retention']['p95'],
                 d['unit_retention']['minimum'], d['unit_retention']['frac_ge_090']))
        print('  排序（抽样跨度 vs 全长跨度的 Spearman）：中位 %.3f ｜ 5–95%% [%.3f, %.3f] ｜ 最小 %.3f'
              % (d['ordering_spearman']['median'], d['ordering_spearman']['p05'],
                 d['ordering_spearman']['p95'], d['ordering_spearman']['minimum']))
    io.open(OUT, 'w', encoding='utf-8', newline='\n').write(json.dumps(res, ensure_ascii=False, indent=2))
    h = hashlib.md5(io.open(OUT, 'rb').read()).hexdigest()
    io.open(OUT + '.md5', 'w', encoding='utf-8', newline='\n').write(
        '%s  %s  (_f10_random_drop_order.py)\n' % (h, os.path.basename(OUT)))
    print('\n已冻结 %s（md5 %s）' % (os.path.basename(OUT), h[:12]))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
