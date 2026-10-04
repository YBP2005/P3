# -*- coding: utf-8 -*-
"""p2_noise3_cmp.py — 3 遍独立重复的噪声底比对（**按源聚类**给区间）。

为什么要另写一份（不扩原 `p2_noise_cmp.py`）：
  · 原脚本**写死** R1/R2 两遍，只给一个"逐项一致率"点估计；
  · 在册条目里 在册条目与 在册条目都点名要求"**按图像聚类**估区间"，否则
    "≥100 项" 仍会被质疑独立性（同一张图的多项观测不是独立样本）。
  · 本脚本：3 遍两两比对 + 逐项一致率 + **以"源"为聚类单位**的 bootstrap 区间
    （同源内的项共享域/图像统计，是最自然的聚类单位；更细的聚类需要父图 id，池里没有）。

判据（跑前定）：
  报告 **逐项一致率的点估计** 与 **按源聚类的 95% 区间**；
  并明确：**点估计不得单独引用**（在册条目：0.00 pp 没有稳定性界时不能进结论句）。
"""
import csv
import glob
import io
import itertools
import math
import os
import random
import sys

sys.stdout.reconfigure(encoding='utf-8')
REPS = 3
BASE = '/root/p2_noise4_rep'


def load(d):
    """→ {key: (group, pred, raw)}"""
    out = {}
    for fp in glob.glob(os.path.join(d, '*.csv')):
        for r in csv.DictReader(io.open(fp, encoding='utf-8')):
            out[r['key']] = (r.get('group', '?'), r.get('pred', ''), r.get('raw', ''))
    return out


def agree(a, b, idx):
    """逐项一致率；返回 (same, n, per_group{group:(same,n)})"""
    keys = sorted(set(a) & set(b))
    pg = {}
    same = 0
    for k in keys:
        s = 1 if a[k][idx] == b[k][idx] else 0
        same += s
        g = a[k][0]
        x = pg.setdefault(g, [0, 0])
        x[0] += s
        x[1] += 1
    return same, len(keys), pg


def boot_by_group(pg, n=5000, seed=20260926):
    """以"源"为聚类单位做 bootstrap：重抽源（有放回），源内的项整体进出。

    ⚠ 这是**保守**做法：聚类数只有 2–3 个源 ⇒ 区间会偏宽。
    宽区间是**诚实**的（`31` §2.2：界必须写清是怎么来的），不是缺陷。
    """
    groups = sorted(pg)
    if len(groups) < 2:
        return None
    rnd = random.Random(seed)
    vals = []
    for _ in range(n):
        pick = [rnd.choice(groups) for _ in groups]
        s = sum(pg[g][0] for g in pick)
        t = sum(pg[g][1] for g in pick)
        if t:
            vals.append(100.0 * (1 - s / t))
    vals.sort()
    return vals[int(0.025 * len(vals))], vals[int(0.975 * len(vals))]


def main():
    reps = {}
    for r in range(1, REPS + 1):
        d = '%s%d' % (BASE, r)
        if not os.path.isdir(d):
            print('✗ 缺 %s' % d); sys.exit(2)
        reps[r] = load(d)
        print('rep%d：%d 项' % (r, len(reps[r])))

    print()
    print('=' * 88)
    print('① `--workers 4` 噪声底 ｜ %d 遍独立重复 ｜ 全池' % REPS)
    print('=' * 88)
    print('%-14s %10s %12s %14s %-22s' % ('比较', '可比项', 'pred 一致', 'raw 一致', 'pred 差异(pp)'))
    print('-' * 88)
    disp = []
    for i, j in itertools.combinations(range(1, REPS + 1), 2):
        sp, n, pg = agree(reps[i], reps[j], 1)
        sr, _, _ = agree(reps[i], reps[j], 2)
        d = 100.0 * (1 - sp / n) if n else float('nan')
        disp.append((d, i, j, pg))
        print('%-14s %10d %8d/%-4d %8d/%-6d %10.4f' % ('rep%d vs rep%d' % (i, j), n, sp, n, sr, n, d))

    if disp:
        ds = [x[0] for x in disp]
        print('-' * 88)
        print('  **差异点估计**：均值 %.4f pp ｜ 最大 %.4f pp ｜ 最小 %.4f pp'
              % (sum(ds) / len(ds), max(ds), min(ds)))
        print()
        print('② 按源聚类的 bootstrap 区间（最保守的一对比较：差异最大的那对）')
        d, i, j, pg = max(disp, key=lambda x: x[0])
        print('  取 rep%d vs rep%d（差异最大）' % (i, j))
        for g in sorted(pg):
            s, t = pg[g]
            print('    %-6s %4d/%-4d 一致  ⇒ 该源差异 %.4f pp' % (g, s, t, 100.0 * (1 - s / t)))
        iv = boot_by_group(pg)
        if iv:
            print('    聚类 bootstrap 95%% 区间 = [%.3f, %.3f] pp（聚类单位 = 源，n=%d 源）' % (iv[0], iv[1], len(pg)))
            print('    ⚠ 聚类数只有 %d ⇒ 区间偏宽，这是**保守**而非缺陷；引用时必须连区间一起给。'
                  % len(pg))
        print()
        print('  对照（旧值，仅 n=20 且 workers=1）：0.00 pp，95% 单侧上界约 14%')
        print('  对照（会议侧，别人的栈）：batch=1+贪婪 ⇒ 0 ｜ vLLM 连续批处理 ⇒ ≤2.6 pp ｜ 托管端点 ⇒ 2.15–6.46 pp')
        print()
        print('  ★ 结论口径：**点估计不得单独引用**；引用时必须带上面的聚类区间。')
    return 0


if __name__ == '__main__':
    sys.exit(main())
