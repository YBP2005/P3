# -*- coding: utf-8 -*-
"""_f10_random_drop_order.py —— 随机删档下的**24 单元**跨度保留率与**排序**保全率（预注册条款与 T3/T5）。

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
import argparse
import hashlib
import importlib.util
import io
import json
import os
import random
import statistics as st
import sys
import tempfile

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
W = os.path.dirname(os.path.abspath(__file__))
# ★ 2026-10-06（v0654）：**默认不写回**。
#   起因（放行树上实测到）：旧版 `main()` 把产物**无条件写进本目录**
#   （放行树上就是 `code/analysis/`，即**评审面自身**），而且——因为放行树上 `sec2.build()`
#   因输入未放行只能建出 **2** 个单元——它会**静默**把随包冻结的 24 单元件覆盖成
#   `n_units: 2`，把"我少读了 10 族阶梯"伪装成"这一轮算出来的就是 2 个单元"。
#   现在两条一起改：(a) 默认写到**临时目录**，只有显式 `--apply` 才写回树内冻结件；
#   (b) `EXP_UNITS` 断言：单元数不等于 24 **即报错退出**（不许静默出残缺件）。
FROZEN = os.path.join(W, 'f10_random_drop_order_result.json')
TMP_OUT = os.path.join(tempfile.gettempdir(), 'f10_random_drop_order_result.json')
EXP_UNITS = 24
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
    ap = argparse.ArgumentParser(description='F.10 随机删档：24 单元的幅度保留率与排序保全率')
    ap.add_argument('--out', default=TMP_OUT,
                    help='写出路径（默认 = 临时目录；★ 不覆盖包内任何件）')
    ap.add_argument('--apply', action='store_true',
                    help='写回树内冻结件 %s（+ .md5）；不给该开关则一次都不碰本树' % FROZEN)
    a = ap.parse_args()
    dest = FROZEN if a.apply else a.out

    rnd = random.Random(SEED)
    res = dict(purpose='F.10 随机删档：24 单元的幅度保留率与排序保全率（多条预注册条款/ T3 / T5）',
               design='随机抽 k=4 档（不放回）%d 次；幅度=抽样跨度/全长跨度；排序=抽样跨度向量与全长跨度向量的 Spearman'
                      % NDRAW, k=K, per_caliber={})
    for cal in ('person', 'allclass'):
        L = sec2.build(cal)                     # 与 F.10 同一套 24 单元
        units = sorted(L)
        # ★ 断言：单元集必须与冻结件同规模。放行树上若输入缺族，这里**当场报错**，
        #   而不是安静地写出一个只有 2 个单元、却顶着同名 `.md5` 的"新冻结件"。
        if len(units) != EXP_UNITS:
            raise SystemExit(
                '!! 单元数 %d ≠ 期望 %d（口径 %s）⇒ 拒绝出件（不许静默）。\n'
                '   缺的族通常是检测 τ（`data/derived/threeway_curves_v2.csv`）与密度回归\n'
                '   （`data/derived/threeway_curves.csv`）：两件缺席时只剩 %d 个单元。\n'
                '   本脚本的产物是**随包冻结件**，残缺件会冒充真件 ⇒ 直接失败。'
                % (len(units), EXP_UNITS, cal, len(units)))
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
    os.makedirs(os.path.dirname(os.path.abspath(dest)) or '.', exist_ok=True)
    io.open(dest, 'w', encoding='utf-8', newline='\n').write(json.dumps(res, ensure_ascii=False, indent=2))
    h = hashlib.md5(io.open(dest, 'rb').read()).hexdigest()
    if a.apply:
        io.open(dest + '.md5', 'w', encoding='utf-8', newline='\n').write(
            '%s  %s  (_f10_random_drop_order.py)\n' % (h, os.path.basename(dest)))
    print('\n已写 %s（md5 %s）%s' % (dest, h[:12],
                                    '＋旁车 .md5' if a.apply else '（默认落临时目录；树内冻结件未动）'))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
