# -*- coding: utf-8 -*-
"""analyze_a57.py —— 实验 1「预算匹配预注册复验」的分析器。

★ 本件**不联网、不连任何机器、不执行任何远端命令**。它只读本地文件：
     <out>/manifest.csv          渲染件（本目录 render_a57.py 产出）
     <out>/work/<alias>/<knob>/<level>/start<K>/run.jsonl   放量件（run_a57.sh 产出）

## 口径来源（逐字照抄，不改口径）
补材 `D:\\deepseek\\PaperB\\PaperB_英文补充材料_PR_20260919.md`
  L5788-L5795  §M.45(b) 共同错误与成本预算的可比条件与成本代理
  L5797-L5801  §M.45(b) 已印结果表（28 单元、两个 (B,C) 常数）
  L5802-L5811  §M.45(b) 判据被 miss、以及两个**事后**单边诊断
  L5832-L5843  span / B* / "可保留档对"的形式化
上游实现（已印代码，零新跑的）：
  `analysis/work/n6_budget_matched.py`（md5 见本目录 PLAN.md）
  `analysis/work/n6_criteria_frozen.json`
  `analysis/work/n5_order_prereg.py` :: span_of / spearman / rho_arr

## 五个统计量（与已印口径一一对应）
  per-unit span_full   = max_l rho(l) − min_l rho(l)              （全档位排序用）
  per-unit MAE(l)      = mean_i |pred(l,i) − gt(i)|               （公共 item 交集上）
  per-unit cost(l)     = 该档**已声明**的成本代理（见 COST_PROXY）
  admissible pair (a,b)⇔ max(MAE_a,MAE_b)/min(...) ≤ 1+B 且 max(cost_a,cost_b)/min(...) ≤ C
  span_BM              = 所有可保留档对上 |rho(a) − rho(b)| 的最大值；无可保留档对 ⇒ 记为**不可算**
  rho(l)               = 100 * (Σpred − Σgt) / Σgt                  （百分比口径，同 n5::rho_arr）

## 三个预注册读数
  spearman(full, BM)   = 全档位排序 vs 预算匹配排序的 Spearman（同 n5::spearman，并列取平均秩）
  top knob             = 全档位 span 最大者 vs span_BM 最大者
  retention            = span_BM / span_full（中位数与逐单元比）
  符合可比条件的单元比例 = 有 ≥1 个可保留档对的单元数 / 参与检的单元数（**含不可算单元作分母**）

## 用法
  python analyze_a57.py --selftest                 # 只用内嵌 §M.45 冻结核回归自证
  python analyze_a57.py --out /root/a57_work/pool  # 实跑分析（+ 自动先跑 selftest）
  python analyze_a57.py --out ... --write-fixture <path>   # 导出内嵌冻结核
"""
from __future__ import annotations

import argparse
import collections
import csv
import hashlib
import io
import itertools
import json
import math
import os
import random
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# ============================================================================
# 0. 本检的冻结件（预注册）—— 与 PREREGISTRATION.md 一一对应
# ============================================================================
B_PRIMARY, C_PRIMARY = 0.10, 2.0          # §M.45(b) 预注册主判据常数（原文 L5799）
B_SECONDARY, C_SECONDARY = 0.25, 4.0      # §M.45(b) 预注册次判据常数（原文 L5800）
B_POSTHOE_COST_ONLY = float('inf')        # 事后单边诊断：只放成本上限（原文 L5806）
B_POSTHOE_MAE_ONLY = 0.10                 # 事后单边诊断：只放误差预算（原文 L5808）

FAMILIES = {                              # alias -> served 目录名（起服前须核对）
    'q32fp8': 'Qwen3-VL-32B-Instruct-FP8',
    'ivl358b': 'InternVL3_5-8B',
    'lov7b': 'llava-onevision-qwen2-7b-ov',
}
KNOBS = ('density', 'res')
LEVELS = {'density': (24, 30, 36), 'res': (640, 704, 832)}
LEVEL_MEAN = {'density': {24: '24', 30: '30', 36: '36'},
              'res': {640: 'px640', 704: 'px704', 832: 'px832'}}
MIN_VALID_FRAC = 0.80                     # 停止规则：有效读数 <80% ⇒ 该格 INCONCLUSIVE
N_ITEMS = 100                             # 每格固定 100 图（冻结，不得事后加样）
N_STARTS = 3                              # 同一起服次数（冻结）
BOOT_N = 2000                             # 排序不确定性的 bootstrap 重抽次数（单元层）
BOOT_SEED = 20261011

# 成本代理（预注册，见 PREREGISTRATION.md §4）：knob -> (单位, 解析函数, 是否单调)
COST_PROXY = {
    # 密度档：声明代理 = 计数算力「位数块」ceil(d/8)（固定尺寸、只变目标数 ⇒ 推理称量单调）
    'density': ('count_compute_ceil_d_over_8', lambda lab: float(math.ceil(int(lab[1:]) / 8.0))),
    # 分辨率档：声明代理 = 实际像素数 px²（标签形如 px640）
    'res': ('input_pixels_px2', lambda lab: float(int(lab[2:]) ** 2)),
}


def cost_of(knob, label):
    """成本代理；解析不出 ⇒ None ⇒ 该档对不参与可比判定（与已印代码同语义）。"""
    if knob not in COST_PROXY:
        return None
    fn = COST_PROXY[knob][1]
    try:
        return fn(str(label))
    except Exception:
        return None


def unit_key(family, knob):
    return '%s / %s' % (family, knob)


# ============================================================================
# 1. 工具（逐字对齐 n5_order_prereg.py）
# ============================================================================
def rho_arr(G, P):
    sg = sum(G)
    return 100.0 * (sum(P) - sg) / sg if sg else float('nan')


def span_of_levels(rhos):
    return max(rhos) - min(rhos) if rhos else float('nan')


def spearman(x, y):
    n = len(x)
    if n < 2:
        return float('nan')

    def rank(v):
        s = sorted(range(n), key=lambda i: v[i])
        r = [0.0] * n
        i = 0
        while i < n:
            j = i
            while j + 1 < n and v[s[j + 1]] == v[s[i]]:
                j += 1
            avg = (i + j) / 2.0 + 1
            for t in range(i, j + 1):
                r[s[t]] = avg
            i = j + 1
        return r
    a, b = rank(x), rank(y)
    ma, mb = sum(a) / n, sum(b) / n
    num = sum((a[i] - ma) * (b[i] - mb) for i in range(n))
    da = sum((t - ma) ** 2 for t in a) ** 0.5
    db = sum((t - mb) ** 2 for t in b) ** 0.5
    return num / (da * db) if da and db else float('nan')


def percentile(xs, q):
    if not xs:
        return float('nan')
    s = sorted(xs)
    i = min(len(s) - 1, max(0, int(q * (len(s) - 1))))
    return s[i]


def upper_median(xs):
    """**已印口径的中位数**：升序后取 `x[len(x)//2]`（偶数个时取上中位数，不做两数平均）。

    ★ 这不是笔误：已印实现 `n6_budget_matched.py` 用 `sorted(...)[len(usable) // 2]`；
      本件逐位对齐它（否则 primary 的 retention 会读成 0.453 而非已印的 0.477，
      secondary 会读成 0.542 而非 0.582）。回归自证里对这条有直接对照。
    """
    if not xs:
        return float('nan')
    return sorted(xs)[len(xs) // 2]


# ============================================================================
# 2. §M.45(b) 核心：预算匹配跨度与排序统计
# ============================================================================
def budget_matched(units, B, C, cost_lookup):
    """units: {u: {'levels': [...], 'mae': [...], 'cost': [...], 'rho': [...], 'span_full': f}}

    返回 dict：span_bm / n_pairs / undefined / usable / spearman / retention / top_*
    ★ 与已印代码 `n6_budget_matched.py::main` 的循环逐行同构：
       cost 为 None 的档对 **skip**（不判不剔）；mi<=0 或 ci<=0 的档对 skip；
       一个可保留档对都没有 ⇒ 该单元进 `undefined`（**不填数、不剔单元**）。
    """
    span_bm, n_pairs, undefined = {}, {}, []
    for u, d in units.items():
        best, cnt = None, 0
        for i, j in itertools.combinations(range(len(d['levels'])), 2):
            ci_, cj = d['cost'][i], d['cost'][j]
            if ci_ is None or cj is None:
                continue
            me, ce = max(d['mae'][i], d['mae'][j]), max(ci_, cj)
            mi, cmin = min(d['mae'][i], d['mae'][j]), min(ci_, cj)
            if mi <= 0 or cmin <= 0:
                continue
            if me / mi <= 1 + B and ce / cmin <= C:
                cnt += 1
                delta = abs(d['rho'][i] - d['rho'][j])
                best = delta if best is None else max(best, delta)
        if best is None:
            undefined.append(u)
        else:
            span_bm[u] = best
            n_pairs[u] = cnt
    usable = [u for u in units if u in span_bm]
    denom = len(units)
    res = {
        'B': B, 'C': C,
        'span_bm': span_bm, 'n_pairs': n_pairs, 'undefined': sorted(undefined),
        'usable': sorted(usable),
        'n_units': denom, 'n_usable': len(usable), 'n_undefined': len(undefined),
        'frac_comparable': (len(usable) / denom) if denom else float('nan'),
        'frac_comparable_ge1pairs': (sum(1 for u in units if n_pairs.get(u, 0) >= 1) / denom)
        if denom else float('nan'),
    }
    res['median_n_pairs'] = (upper_median([n_pairs[u] for u in usable])
                             if usable else float('nan'))
    if len(usable) >= 2:
        res['spearman'] = spearman([units[u]['span_full'] for u in usable],
                                   [span_bm[u] for u in usable])
    else:
        res['spearman'] = float('nan')
    res['retention'] = {u: (span_bm[u] / units[u]['span_full']
                            if units[u]['span_full'] else float('nan')) for u in usable}
    res['retention_median'] = (upper_median(list(res['retention'].values()))
                               if res['retention'] else float('nan'))
    res['top_full'] = max(units, key=lambda u: units[u]['span_full']) if units else None
    res['top_bm'] = max(usable, key=lambda u: span_bm[u]) if usable else None
    res['top_changed'] = (res['top_bm'] != res['top_full'])
    # 与已印判据一致：排序完全一致（rho=1）且顶端不变
    res['pass'] = bool(res['spearman'] == res['spearman']
                       and abs(res['spearman'] - 1.0) < 1e-12
                       and res['top_full'] == res['top_bm'])
    return res


def bootstrap_spearman_ci(units, B, C, n=BOOT_N, seed=BOOT_SEED):
    """单元层 bootstrap：对参与检的单元有放回重抽 n 次，看 Spearman 的 95% 百分位区间。
    ★ 这是**本检新增**的不确定性量（已印 §M.45(b) 未印区间）；不替代已印口径，只作补充。"""
    usable = [u for u in units if units[u].get('_bm') is not None]
    if len(usable) < 3:
        return float('nan'), float('nan')
    rnd = random.Random(seed)
    rhos = []
    for _ in range(n):
        pick = [usable[rnd.randrange(len(usable))] for _ in range(len(usable))]
        x = [units[u]['span_full'] for u in pick]
        y = [units[u]['_bm'] for u in pick]
        r = spearman(x, y)
        if r == r:
            rhos.append(r)
    return percentile(rhos, 0.025), percentile(rhos, 0.975)


# ============================================================================
# 3. §M.45 冻结核的回归自证（内嵌，零新跑）
# ============================================================================
FIXTURE_M45_28 = json.loads(r'''{"VLM·pixel budget / ivl / st_a":{"m":[161.880282,161.880282,160.211268,158.859155,162.0],"r":[-52.61384,-52.61384,-52.070436,-51.602696,-52.625304],"s":1.022607,"c":[null,null,null,null,null]},"VLM·pixel budget / ivl / ucf":{"m":[254.279279,248.288288,244.040541,244.594595,247.414414],"r":[-69.123013,-67.494429,-66.317684,-66.490339,-67.256876],"s":2.805329,"c":[null,null,null,null,null]},"VLM·pixel budget / ivl / visdrone":{"m":[17.335,17.52,18.85,18.1675,18.19],"r":[-77.009053,-78.014977,-84.139935,-80.708617,-80.831564],"s":7.130882,"c":[null,null,null,null,null]},"VLM·pixel budget / q32 / st_a":{"m":[368.153846,368.450549,366.467033,360.906593,364.340659],"r":[-81.377596,-81.443534,-83.250488,-79.256169,-80.226218],"s":3.994319,"c":[null,null,null,null,null]},"VLM·pixel budget / q32 / ucf":{"m":[632.302395,660.39521,667.748503,645.107784,648.838323],"r":[-78.769568,-87.373765,-92.845869,-87.5595,-87.441229],"s":14.076301,"c":[null,null,null,null,null]},"VLM·pixel budget / q32 / visdrone":{"m":[16.4875,16.6325,19.0075,17.145,16.61],"r":[-70.269364,-70.984688,-84.866436,-74.90779,-71.129988],"s":14.597072,"c":[null,null,null,null,null]},"VLM·tiling / Qwen32B / ucf / base":{"m":[492.979042,438.640719,354.050898,312.52994,284.302395],"r":[-59.104141,-45.696652,-34.798669,-26.700454,-18.572256],"s":40.531885,"c":[4.0,9.0,16.0,25.0,36.0]},"VLM·tiling / Qwen32B(ctile) / ucf / base":{"m":[490.742515,437.60479,654.338323],"r":[-58.727257,-46.236367,-86.244779],"s":40.008412,"c":[4.0,9.0,1.0]},"VLM·tiling / Qwen32B(ctile) / ucf / choice":{"m":[1443.811377,1965.625749,481.008982],"r":[200.216136,273.399076,13.023525],"s":260.375551,"c":[4.0,9.0,1.0]},"VLM·tiling / Qwen32B(ctile) / ucf / forbid0":{"m":[1037.946108,846.994012,773.54491],"r":[141.474303,115.662129,79.834421],"s":61.639882,"c":[4.0,9.0,1.0]},"VLM·tiling / Qwen32B(ctile) / ucf / range":{"m":[1830.102102,1544.612613,1040.618619],"r":[257.267184,217.493678,142.6863],"s":114.580884,"c":[4.0,9.0,1.0]},"VLM·tiling / Qwen8B(ctile) / ucf / base":{"m":[387.942943,338.948949,539.285285],"r":[-51.739726,-41.652782,-74.584944],"s":32.932162,"c":[4.0,9.0,1.0]},"density·CSRNet / ladder":{"m":[367.809804,230.105882,371.652941,693.921569,1054.113725,1603.033333,1323.845098,211.992157,281.262745,857.145098],"r":[-73.197409,-23.112342,50.958364,129.431459,203.618059,314.207281,256.920826,-33.542748,28.66586,164.732509],"s":387.40469,"c":[0.5,0.75,1.0,1.25,1.5,2.0,1024.0,384.0,512.0,768.0]},"density·CSRNet / st":{"m":[292.488889,157.779085,408.226144,1111.713725,2242.45098,5815.533987,4177.754902,154.635948,281.592157,1607.357516],"r":[-69.501771,-14.225321,85.361247,262.329316,532.107225,1381.82503,992.726129,-25.647792,58.8268,381.943375],"s":1451.3268,"c":[0.5,0.75,1.0,1.25,1.5,2.0,1024.0,384.0,512.0,768.0]},"density·official DM-Count / st_a":{"m":[130.282083,84.034938,69.373736,68.653944,65.956269,69.388489,66.316899,94.619214,76.83636,68.297086],"r":[-28.354839,-11.151845,-3.338394,0.544329,2.825086,4.258134,3.609135,-16.443475,-6.549818,1.409326],"s":32.612973,"c":[0.5,0.75,1.0,1.25,1.5,2.0,1024.0,384.0,512.0,768.0]},"density·official DM-Count / ucf":{"m":[192.398161,102.278555,81.172322,76.250971,81.130309,92.5628,81.256653,213.028486,147.108521,88.566143],"r":[-30.403987,-13.061976,-5.547927,-1.179623,1.307525,1.311172,-2.795344,-33.765838,-21.914179,-8.387233],"s":35.07701,"c":[0.5,0.75,1.0,1.25,1.5,2.0,1024.0,384.0,512.0,768.0]},"det·in-domain(micro)/BBBC005 (full grid)":{"m":[9.971154,43.387821,7.416667,2.192308,15.112179,2.317308,2.544872,6.304487,2.708333,3.570513,3.067308,3.689103,5.358974,4.669872,5.134615,8.25641,13.387821,7.490385],"r":[19.744859,85.916476,14.648388,2.475248,29.925108,1.973851,-3.160701,12.306423,-3.090886,-6.473724,3.179741,-6.048489,-10.43412,-7.279766,-9.697893,-16.298553,-26.396293,-14.680122],"s":112.31277,"c":[1048576.0,2359296.0,409600.0,1048576.0,2359296.0,409600.0,1048576.0,2359296.0,409600.0,1048576.0,2359296.0,409600.0,1048576.0,2359296.0,409600.0,1048576.0,2359296.0,409600.0]},"det·in-domain(micro)/BBBC005 / tau@1024":{"m":[9.971154,2.192308,2.544872,3.570513,5.358974,8.25641],"r":[19.744859,2.475248,-3.160701,-6.473724,-10.43412,-16.298553],"s":36.043412,"c":[1048576.0,1048576.0,1048576.0,1048576.0,1048576.0,1048576.0]},"det·in-domain(micro)/BBBC005 / tau@1536":{"m":[43.387821,15.112179,6.304487,3.067308,4.669872,13.387821],"r":[85.916476,29.925108,12.306423,3.179741,-7.279766,-26.396293],"s":112.31277,"c":[2359296.0,2359296.0,2359296.0,2359296.0,2359296.0,2359296.0]},"det·in-domain(micro)/BBBC005 / tau@640":{"m":[7.416667,2.317308,2.708333,3.689103,5.134615,7.490385],"r":[14.648388,1.973851,-3.090886,-6.048489,-9.697893,-14.680122],"s":29.32851,"c":[409600.0,409600.0,409600.0,409600.0,409600.0,409600.0]},"det·in-domain/VisDrone (full grid)":{"m":[22.13,29.21,17.3425,15.845,17.6125,15.9025,14.8875,15.0375,16.31,15.04,14.6625,16.88,15.62,14.715,17.99,16.695,15.3525,19.22,18.9075,17.685,20.61,20.2325,19.295,21.3525],"r":[68.82754,109.422153,0.391193,4.940203,27.707611,-39.801051,-28.311166,-12.261093,-59.304795,-49.334973,-36.96211,-71.822957,-63.596736,-53.649268,-79.937409,-73.208897,-64.792668,-85.838829,-84.240528,-78.462054,-92.142618,-90.454901,-86.263552,-95.462166],"s":204.884319,"c":[1048576.0,2359296.0,409600.0,1048576.0,2359296.0,409600.0,1048576.0,2359296.0,409600.0,1048576.0,2359296.0,409600.0,1048576.0,2359296.0,409600.0,1048576.0,2359296.0,409600.0,1048576.0,2359296.0,409600.0,1048576.0,2359296.0,409600.0]},"det·in-domain/VisDrone / tau@1024":{"m":[22.13,15.845,14.8875,15.04,15.62,16.695,18.9075,20.2325],"r":[68.82754,4.940203,-28.311166,-49.334973,-63.596736,-73.208897,-84.240528,-90.454901],"s":159.282441,"c":[1048576.0,1048576.0,1048576.0,1048576.0,1048576.0,1048576.0,1048576.0,1048576.0]},"det·in-domain/VisDrone / tau@1536":{"m":[29.21,17.6125,15.0375,14.6625,14.715,15.3525,17.685,19.295],"r":[109.422153,27.707611,-12.261093,-36.96211,-53.649268,-64.792668,-78.462054,-86.263552],"s":195.685705,"c":[2359296.0,2359296.0,2359296.0,2359296.0,2359296.0,2359296.0,2359296.0,2359296.0]},"det·in-domain/VisDrone / tau@640":{"m":[17.3425,15.9025,16.31,16.88,17.99,19.22,20.61,21.3525],"r":[0.391193,-39.801051,-59.304795,-71.822957,-79.937409,-85.838829,-92.142618,-95.462166],"s":95.853359,"c":[409600.0,409600.0,409600.0,409600.0,409600.0,409600.0,409600.0,409600.0]},"det·zero-shot COCO (full grid)":{"m":[25.515,22.565,29.56,28.96,24.175,31.825,30.665,26.38,32.79,31.54,28.155,33.405,32.125,29.435,33.82,32.66,30.305,34.075,33.46,31.71,34.495,34.055,32.62,34.83],"r":[-66.076988,-36.866686,-82.139825,-80.441551,-63.331446,-89.767903,-86.314747,-73.365412,-92.782338,-89.102746,-79.323521,-94.523068,-90.87178,-83.088027,-95.697707,-92.442683,-85.692046,-96.447778,-94.707048,-89.75375,-97.636569,-96.391169,-92.329465,-98.584772],"s":61.718087,"c":[1048576.0,2359296.0,409600.0,1048576.0,2359296.0,409600.0,1048576.0,2359296.0,409600.0,1048576.0,2359296.0,409600.0,1048576.0,2359296.0,409600.0,1048576.0,2359296.0,409600.0,1048576.0,2359296.0,409600.0,1048576.0,2359296.0,409600.0]},"det·zero-shot COCO / tau@1024":{"m":[25.515,28.96,30.665,31.54,32.125,32.66,33.46,34.055],"r":[-66.076988,-80.441551,-86.314747,-89.102746,-90.87178,-92.442683,-94.707048,-96.391169],"s":30.314181,"c":[1048576.0,1048576.0,1048576.0,1048576.0,1048576.0,1048576.0,1048576.0,1048576.0]},"det·zero-shot COCO / tau@1536":{"m":[22.565,24.175,26.38,28.155,29.435,30.305,31.71,32.62],"r":[-36.866686,-63.331446,-73.365412,-79.323521,-83.088027,-85.692046,-89.75375,-92.329465],"s":55.46278,"c":[2359296.0,2359296.0,2359296.0,2359296.0,2359296.0,2359296.0,2359296.0,2359296.0]},"det·zero-shot COCO / tau@640":{"m":[29.56,31.825,32.79,33.405,33.82,34.075,34.495,34.83],"r":[-82.139825,-89.767903,-92.782338,-94.523068,-95.697707,-96.447778,-97.636569,-98.584772],"s":16.444948,"c":[409600.0,409600.0,409600.0,409600.0,409600.0,409600.0,409600.0,409600.0]}}''')

FIXTURE_EXPECT = {
    # tag: (B, C, n_usable, spearman, retention_median, top_full, top_bm)
    'primary_B10_C2':            (0.10, 2.0, 14, 0.7674, 0.477, 'density·CSRNet / st', 'det·in-domain/VisDrone (full grid)'),
    'secondary_B25_C4':          (0.25, 4.0, 20, 0.8227, 0.582, 'density·CSRNet / st', 'det·in-domain/VisDrone (full grid)'),
    'posthoc_cost_only_C2':      (float('inf'), 2.0, 17, 0.9275, 1.000, 'density·CSRNet / st', 'density·CSRNet / st'),
    'posthoc_mae_only_B10':      (0.10, float('inf'), 16, 0.8292, 0.477, 'density·CSRNet / st', 'det·in-domain/VisDrone (full grid)'),
}


def fixture_units_strict_cost():
    """§1.3 的 **R2 读法**：按 L5791–L5793 的字面语义给 pixel-budget 档补上成本代理。

    公开的 5 档预算标签对应 0 / 1048576 / 200000 / 400000 / 800000：
    `native`（budget=0）按已印上限 `1048576` 记（`n6_criteria_frozen.json::cost_proxy`）。
    ★ 这是 **post-hoc 口径对照**，不是预注册判据；只在**参考侧（已印 28 单元）**上有意义，
      本域（x57）每个 knob 都有可解析的声明成本，不存在这一歧义。
    """
    out = {}
    KNOWN = [1048576.0, 1048576.0, 200000.0, 400000.0, 800000.0]
    for u, d in FIXTURE_M45_28.items():
        c = list(d['c'])
        if all(x is None for x in c) and u.startswith('VLM·pixel budget'):
            c = KNOWN[:len(c)] if len(c) == len(KNOWN) else [1048576.0] * len(c)
        out[u] = {'levels': list(range(len(d['m']))), 'mae': [float(x) for x in d['m']],
                  'cost': c, 'rho': [float(x) for x in d['r']], 'span_full': float(d['s'])}
    return out


def fixture_units():
    out = {}
    for u, d in FIXTURE_M45_28.items():
        out[u] = {'levels': list(range(len(d['m']))), 'mae': [float(x) for x in d['m']],
                  'cost': d['c'], 'rho': [float(x) for x in d['r']],
                  'span_full': float(d['s'])}
    return out


def selftest(verbose=True):
    """把已印 §M.45(b) 的 28 单元输入喂进本件，看四个读数是否逐位复现。
    这是「实现是否与原文对齐」的唯一证据；对不上必须如实写「未能自证」。"""
    units = fixture_units()
    rows, ok_all = [], True
    for tag, (B, C) in (('primary_B10_C2', (B_PRIMARY, C_PRIMARY)),
                        ('secondary_B25_C4', (B_SECONDARY, C_SECONDARY)),
                        ('posthoc_cost_only_C2', (B_POSTHOE_COST_ONLY, C_PRIMARY)),
                        ('posthoc_mae_only_B10', (B_POSTHOE_MAE_ONLY, float('inf')))):
        r = budget_matched(units, B, C, None)
        exp = FIXTURE_EXPECT[tag]
        got = (r['n_usable'], round(r['spearman'], 4), round(r['retention_median'], 3),
               r['top_full'], r['top_bm'])
        want = (exp[2], exp[3], exp[4], exp[5], exp[6])
        ok = (got == want)
        ok_all &= ok
        rows.append((tag, B, C, want, got, ok))
        if verbose:
            print('  [selftest] %-22s usable=%-2d rho=%.4f ret=%.3f top_changed=%s  %s'
                  % (tag, r['n_usable'], r['spearman'], r['retention_median'],
                     r['top_changed'], 'MATCH' if ok else 'MISMATCH'))
            if not ok:
                print('             want=%s' % (want,))
                print('             got =%s' % (got,))
    if verbose:
        print('  [selftest] 结论：%s' % ('★ 自证通过（四个读数逐位复现已印 §M.45(b) 数值）'
                                        if ok_all else '★ 未能自证（逐位对照有 MISMATCH，见上）'))
    return ok_all, rows


# ============================================================================
# 4. 实跑数据的读入
# ============================================================================
def read_manifest(path):
    """键 = (item, knob, level_label)。

    ★ 为什么不是只按 item 键：同一张图**逐档重复出现**（每档一行，GT 不同），
      只按 item 键会让后一行覆盖前一行（静默丢档）。这是本件实跑前发现的接口陷阱，
      写在这里以免复制到别处。
    """
    man = {}
    with io.open(path, encoding='utf-8-sig', newline='') as fh:
        for r in csv.DictReader(fh):
            item = str(r['item']).strip()
            knob = (r.get('knob') or '').strip()
            level = (r.get('level') or '').strip()
            key = (item, knob, level)
            assert key not in man, 'manifest 重复行：%s' % (key,)
            gt = float(r['count_gt'])
            if not (gt > 0):
                raise ValueError('manifest 的 count_gt 必须 > 0（rho 的分母）：%s/%s = %r'
                                 % (item, level, gt))
            rel_img = (r.get('image') or '').strip() or ('images/' + item)
            # ★ 物理文件走 manifest 的 image 列（res knob 的 item 名不带档、物理名带 px，
            #   两者不能互相推导）；item 只作**逻辑名/公共交集键**。
            man[key] = dict(item=item,
                            target_word=(r.get('target_word') or '').strip(),
                            count_gt=gt,
                            knob=knob, level=level,
                            px=int(float(r['px'])), seed=int(float(r['seed'])),
                            sha256=(r.get('sha256') or '').strip(),
                            rel_image=rel_img,
                            path=os.path.join(os.path.dirname(os.path.abspath(path)),
                                              *rel_img.split('/')))
    return man


def check_image_consistency(man, knobs, levels):
    """预注册的档间同一性规则（逐 knob 冻结，见 PREREGISTRATION.md §3.3）。

    density：**同 seed × 同画布 × 逐档真渲染 × 字节互异**
             GT 就是"画了几个"，所以低档不能拿高档的图充数（否则构造 GT 就是错的）。
             同一 item 同 seed 同画布 ⇒ 三张图互相嵌套（低档落点集是高阶的前缀），
             这是"同 item 换档"的可核查代理；同时要求三档 sha 互异（证明确实逐档渲染）。
    res    ：**场景同一 × 字节互异**——像素档必然改字节；要求同 item 的 seed / count_gt /
             target_word 逐级相同（同一场景重渲），且 sha256 逐级不同。
             ★ 声明：此时 span 是"像素档 + 重渲"的合成效应，不是纯像素效应（限制 §8）。
    ★ 两个 knob 都**不要求字节同一**（公开 M.45 的 pixel-budget 档是同一照片重编码，
      本域无法照搬）；此处写明，避免被读成"已印条件"。
    返回 (ok, messages)。
    """
    CONSIST = {'density': ('same_seed_canvas', 'distinct_bytes'),
               'res': ('same_scene', 'distinct_bytes')}
    msgs, ok = [], True
    per = collections.defaultdict(dict)          # (knob,item) -> {level: record}
    for (item, knob, level), m in man.items():
        per[(knob, item)][level] = m
    for knob in knobs:
        labs = sorted({LEVEL_MEAN[knob][lv] for lv in levels[knob]})
        rule = CONSIST.get(knob, ('same_bytes',))
        bad_bytes, bad_scene, bad_distinct = 0, 0, 0
        for (k2, item), d in per.items():
            if k2 != knob:
                continue
            if 'same_bytes' in rule and len({d.get(l, {}).get('sha256') for l in labs}) != 1:
                bad_bytes += 1
            if 'same_scene' in rule:
                seeds = {d.get(l, {}).get('seed') for l in labs}
                gts = {d.get(l, {}).get('count_gt') for l in labs}
                words = {d.get(l, {}).get('target_word') for l in labs}
                if len(seeds) != 1 or len(gts) != 1 or len(words) != 1:
                    bad_scene += 1
            if 'same_seed_canvas' in rule:
                seeds = {d.get(l, {}).get('seed') for l in labs}
                pxs = {d.get(l, {}).get('px') for l in labs}
                if len(seeds) != 1 or len(pxs) != 1:
                    bad_scene += 1
            if 'distinct_bytes' in rule:
                if len({d.get(l, {}).get('sha256') for l in labs}) != len(labs):
                    bad_distinct += 1
        msgs.append('%s（规则 %s）：字节不一致 %d ｜ seed/场景不一致 %d ｜ 字节未全异 %d'
                    % (knob, '+'.join(rule), bad_bytes, bad_scene, bad_distinct))
        ok &= (bad_bytes == 0 and bad_scene == 0 and bad_distinct == 0)
    return ok, msgs


def read_runs(outdir, aliases, knobs, levels):
    """返回 records[(alias,knob,level,start)][item] = [pred,...]（只收 http==200 且 parse_ok）"""
    recs = collections.defaultdict(lambda: collections.defaultdict(list))
    stats = collections.defaultdict(lambda: dict(rows=0, ok=0, http_non200=0,
                                                 unparsed=0, dup=0))
    for alias in aliases:
        for knob in knobs:
            for lv in levels[knob]:
                lab = LEVEL_MEAN[knob][lv]
                for k in range(1, N_STARTS + 1):
                    d = os.path.join(outdir, 'work', alias, knob, lab, 'start%d' % k)
                    p = os.path.join(d, 'run.jsonl')
                    st = stats[(alias, knob, lv, k)]
                    if not os.path.exists(p):
                        continue
                    seen = set()
                    for ln in io.open(p, encoding='utf-8', errors='replace'):
                        ln = ln.strip()
                        if not ln:
                            continue
                        try:
                            r = json.loads(ln)
                        except Exception:
                            continue
                        st['rows'] += 1
                        if r.get('http') != 200:
                            st['http_non200'] += 1
                            continue
                        key = str(r.get('item') or r.get('image') or '').strip()
                        if not key:
                            continue
                        if key in seen:
                            st['dup'] += 1
                            continue
                        seen.add(key)
                        if not r.get('parse_ok') or r.get('pred') is None:
                            st['unparsed'] += 1
                            continue
                        recs[(alias, knob, lv, k)][key].append(float(r['pred']))
                        st['ok'] += 1
    return recs, stats


def build_units_from_runs(man, recs, aliases, knobs, levels, valid_frac_min):
    """把 (alias, knob) 变成一个「单元」：档 = levels[knob]，每档的逐图读数 = 3 次起服的中位数。"""
    units, diag = {}, []
    for alias in aliases:
        for knob in knobs:
            lv_list = list(levels[knob])
            per_level, ok_levels = {}, True
            for lv in lv_list:
                # 公共 item 交集：manifest 该 (knob,level) 的全部 item，且三次起服都有有效读数
                # ★ 键 = (item, knob, level_label)；level 列写的是档位标签（LEVEL_MEAN）。
                lab = LEVEL_MEAN[knob][lv]
                want = [(it, m) for (it, k2, l2), m in man.items()
                        if k2 == knob and l2 == lab]
                vals, nvalid = {}, 0
                for it, m in want:
                    per_start = []
                    for k in range(1, N_STARTS + 1):
                        v = recs.get((alias, knob, lv, k), {}).get(it)
                        if v:
                            per_start.append(statistics.median(v))
                    if len(per_start) == N_STARTS:
                        vals[it] = statistics.median(per_start)
                        nvalid += 1
                frac = (nvalid / len(want)) if want else 0.0
                ok_level = (nvalid >= 2 and frac >= valid_frac_min)
                ok_levels &= ok_level
                per_level[lv] = dict(vals=vals, n_want=len(want), n_valid=nvalid, frac=frac,
                                     ok=ok_level)
            if not ok_levels:
                diag.append(dict(unit=unit_key(alias, knob), status='INCONCLUSIVE',
                                 detail={str(lv): round(per_level[lv]['frac'], 3) for lv in lv_list}))
                continue
            common = set.intersection(*[set(per_level[lv]['vals']) for lv in lv_list])
            common = sorted(common)
            if len(common) < 20:
                diag.append(dict(unit=unit_key(alias, knob), status='INCONCLUSIVE',
                                 detail='common items = %d < 20' % len(common)))
                continue
            gt = {it: man[(it, knob, LEVEL_MEAN[knob][lv_list[0]])]['count_gt'] for it in common}
            mae = [sum(abs(per_level[lv]['vals'][it] - gt[it]) for it in common) / len(common)
                   for lv in lv_list]
            rhos = [rho_arr([gt[it] for it in common],
                            [per_level[lv]['vals'][it] for it in common]) for lv in lv_list]
            costs = [cost_of(knob, LEVEL_MEAN[knob][lv]) for lv in lv_list]
            units[unit_key(alias, knob)] = dict(
                levels=[LEVEL_MEAN[knob][lv] for lv in lv_list], mae=mae, cost=costs, rho=rhos,
                span_full=span_of_levels(rhos), common_n=len(common),
                per_level={str(lv): dict(mae=mae[i], rho=rhos[i], cost=costs[i],
                                         n_valid=per_level[lv]['n_valid'],
                                         frac=per_level[lv]['frac'])
                           for i, lv in enumerate(lv_list)})
            diag.append(dict(unit=unit_key(alias, knob), status='OK',
                             detail='common_n=%d' % len(common)))
    return units, diag


# ============================================================================
# 5. 报告
# ============================================================================
def mdcells(row):
    """Markdown 表格单元格：把字段里的 | 转义（档位标签用 | 连接会造成列错位）。"""
    return ' | '.join(str(x).replace('|', r'\|') for x in row)


def write_csv(path, header, rows):
    with io.open(path, 'w', encoding='utf-8-sig', newline='') as fh:
        w = csv.writer(fh)
        w.writerow(header)
        w.writerows(rows)
    return path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default=None, help='渲染/放量根目录（含 manifest.csv 与 work/）')
    ap.add_argument('--selftest', action='store_true', help='只跑内嵌 §M.45 冻结核回归自证')
    ap.add_argument('--write-fixture', default=None, help='把内嵌冻结核导出为 JSON')
    ap.add_argument('--results', default=os.path.join(HERE, 'results'))
    ap.add_argument('--boot', type=int, default=BOOT_N)
    args = ap.parse_args()

    if args.write_fixture:
        with io.open(args.write_fixture, 'w', encoding='utf-8') as fh:
            fh.write(json.dumps(FIXTURE_M45_28, ensure_ascii=False, indent=1))
        print('fixture -> %s' % args.write_fixture)
        return 0

    print('=' * 100)
    print('analyze_a57 — 实验 1「预算匹配预注册复验」｜§M.45(b) 口径（原文 L5788-L5833）')
    print('=' * 100)
    print('[selftest] 用内嵌 §M.45 冻结核（28 单元）回归自证：')
    ok_selftest, self_rows = selftest(verbose=True)
    if args.selftest:
        return 0 if ok_selftest else 3

    if not args.out:
        print('\n（未给 --out ⇒ 只做 selftest。实跑：python analyze_a57.py --out <根目录>）')
        return 0 if ok_selftest else 3

    man_path = os.path.join(args.out, 'manifest.csv')
    if not os.path.exists(man_path):
        print('!! 缺 manifest.csv：%s' % man_path)
        return 2
    man = read_manifest(man_path)
    aliases = list(FAMILIES)          # 家族白名单（★ 冻结：只在预注册的 3 个家族上算）
    img_ok, img_msgs = check_image_consistency(man, KNOBS, LEVELS)
    print('\n[图像一致性] ' + ' ｜ '.join(img_msgs) + '  ⇒ %s' % ('OK' if img_ok else '★ 不一致'))
    if not img_ok:
        print('!! 同一 knob 的各级不是同一批图像 ⇒ M.45 的 span 不可算（预注册条件 A4 失败）。')
        return 4
    recs, stats = read_runs(args.out, aliases, KNOBS, LEVELS)
    units, diag = build_units_from_runs(man, recs, aliases, KNOBS, LEVELS, MIN_VALID_FRAC)

    n_drop = sum(1 for d in diag if d['status'] != 'OK')
    print('\n[数据] manifest 行 %d（%d item × %d 档）｜ 可算单元（family×knob）%d ｜ 未定/剔除 %d'
          % (len(man), len({k[0] for k in man}), len({k[2] for k in man}), len(units), n_drop))
    for d in diag:
        if d['status'] != 'OK':
            print('   [未定] %s : %s' % (d['unit'], d['detail']))

    tags = [('primary_B10_C2', B_PRIMARY, C_PRIMARY, '预注册主判据 (B,C)=(0.10,2.0)'),
            ('secondary_B25_C4', B_SECONDARY, C_SECONDARY, '预注册次判据 (B,C)=(0.25,4.0)'),
            ('posthoc_cost_only_C2', B_POSTHOE_COST_ONLY, C_PRIMARY, '事后单边诊断：只放成本上限'),
            ('posthoc_mae_only_B10', B_POSTHOE_MAE_ONLY, float('inf'), '事后单边诊断：只放误差预算')]
    out = {'n_units': len(units), 'families': FAMILIES, 'levels': LEVELS,
           'selftest_pass': ok_selftest, 'units_raw': {u: {k: v for k, v in d.items()
                                                           if k != 'per_level'}
                                                       for u, d in units.items()}}
    summary_rows, detail_rows = [], []
    for tag, B, C, desc in tags:
        r = budget_matched(units, B, C, None)
        for u, d in units.items():
            d['_bm'] = r['span_bm'].get(u)
        lo, hi = bootstrap_spearman_ci(units, B, C, n=args.boot)
        out[tag] = {k: v for k, v in r.items() if k not in ('retention',)}
        out[tag]['boot_ci'] = [lo, hi]
        out[tag]['desc'] = desc
        summary_rows.append([
            tag, desc, '%.2f' % B if B != float('inf') else 'inf', C,
            r['n_units'], r['n_usable'], r['n_undefined'],
            '%.4f' % r['frac_comparable'], '%.4f' % r['frac_comparable_ge1pairs'],
            '%.4f' % r['spearman'], '%.4f' % lo, '%.4f' % hi,
            '%.3f' % r['retention_median'], '%.1f' % r['median_n_pairs'],
            (r['top_full'] or ''), (r['top_bm'] or ''), 'YES' if r['top_changed'] else 'NO',
            'PASS' if r['pass'] else 'FAIL'])
        for u in sorted(units):
            d = units[u]
            detail_rows.append([
                tag, u, len(d['levels']), '|'.join(d['levels']),
                ';'.join('%.4f' % x for x in d['mae']),
                ';'.join('%.4f' % x for x in d['rho']),
                ';'.join('-' if x is None else '%.4g' % x for x in d['cost']),
                '%.6f' % d['span_full'], r['n_pairs'].get(u, 0),
                ('%.6f' % r['span_bm'][u]) if u in r['span_bm'] else '',
                ('%.4f' % r['retention'][u]) if u in r['retention'] else '',
                'COMPARABLE' if u in r['span_bm'] else 'NO_ADMISSIBLE_PAIR'])

    # ---- §1.3 R2：严格成本语义的 post-hoc 口径对照（参考侧的 28 单元） ----
    fx_r2 = fixture_units_strict_cost()
    r_r2 = budget_matched(fx_r2, B_PRIMARY, C_PRIMARY, None)
    for u, d in fx_r2.items():
        d['_bm'] = r_r2['span_bm'].get(u)
    lo2, hi2 = bootstrap_spearman_ci(fx_r2, B_PRIMARY, C_PRIMARY, n=args.boot)
    summary_rows.append(['R2_strict_cost_semantics',
                         'post-hoc 口径对照（§1.3 R2：按 L5791-L5793 语义解析 pixel-budget 成本）',
                         '0.10', 2.0, r_r2['n_units'], r_r2['n_usable'], r_r2['n_undefined'],
                         '%.4f' % r_r2['frac_comparable'], '%.4f' % r_r2['frac_comparable_ge1pairs'],
                         '%.4f' % r_r2['spearman'], '%.4f' % lo2, '%.4f' % hi2,
                         '%.3f' % r_r2['retention_median'], '%.1f' % r_r2['median_n_pairs'],
                         (r_r2['top_full'] or ''), (r_r2['top_bm'] or ''),
                         'YES' if r_r2['top_changed'] else 'NO',
                         'PASS' if r_r2['pass'] else 'FAIL'])
    print('')
    print('[R2 口径对照（post-hoc）] 参考侧 28 单元：可用 %d ｜ Spearman %.4f ｜ retention %.3f '
          '｜ 已印 R1 读数为 14 / 0.7674 / 0.477'
          % (r_r2['n_usable'], r_r2['spearman'], r_r2['retention_median']))
    out['R2_strict_cost_semantics'] = {k: v for k, v in r_r2.items() if k != 'retention'}

    os.makedirs(args.results, exist_ok=True)
    p1 = write_csv(os.path.join(args.results, 'a57_budget_matched_summary.csv'),
                   ['tag', 'desc', 'B', 'C', 'n_units', 'n_usable', 'n_undefined',
                    'frac_comparable', 'frac_comparable_ge1pairs', 'spearman',
                    'boot_ci_lo', 'boot_ci_hi', 'retention_median', 'median_n_pairs',
                    'top_full', 'top_bm', 'top_changed', 'verdict'], summary_rows)
    p2 = write_csv(os.path.join(args.results, 'a57_budget_matched_units.csv'),
                   ['tag', 'unit', 'n_levels', 'levels', 'mae', 'rho', 'cost', 'span_full',
                    'n_admissible_pairs', 'span_bm', 'retention', 'status'], detail_rows)
    p3 = write_csv(os.path.join(args.results, 'a57_cell_coverage.csv'),
                   ['alias', 'knob', 'level', 'start', 'rows', 'ok', 'http_non200',
                    'unparsed', 'dup'],
                   [[a, k, lv, s] + [stats[(a, k, lv, s)][f] for f in
                                     ('rows', 'ok', 'http_non200', 'unparsed', 'dup')]
                    for (a, k, lv, s) in sorted(stats)])
    with io.open(os.path.join(args.results, 'a57_budget_matched.json'), 'w',
                 encoding='utf-8') as fh:
        fh.write(json.dumps(out, ensure_ascii=False, indent=1))

    # ---- Markdown ----
    md = []
    md.append('# 实验 1「预算匹配预注册复验」——结果（§M.45(b) 口径）\n')
    md.append('* 单元 = `family / knob`；档 = 该 knob 的 3 级；逐图读数 = 3 次独立起服的**中位数**；')
    md.append('* 有效读数 < %.0f%% 的格 ⇒ 该单元 `INCONCLUSIVE`（**不加样**，见预注册停止规则）；'
              % (MIN_VALID_FRAC * 100))
    md.append('* `rho` = 100·(Σpred−Σgt)/Σgt；`span` = max rho − min rho；'
              '可保留档对 ⇔ MAE 比 ≤ 1+B 且 成本比 ≤ C。\n')
    md.append('## 0 回归自证（与已印 §M.45(b) 的 28 单元逐位对照）\n')
    md.append('| tag | B | C | 期望 usable | 期望 rho | 期望 ret | 实测 usable | 实测 rho | 实测 ret | 一致 |')
    md.append('|---|---|---|---|---|---|---|---|---|---|')
    for tag, B, C, want, got, ok in self_rows:
        md.append('| %s | %s | %s | %d | %.4f | %.3f | %d | %.4f | %.3f | %s |'
                  % (tag, ('%g' % B), ('%g' % C), want[0], want[1], want[2],
                     got[0], got[1], got[2], 'YES' if ok else 'NO'))
    md.append('')
    md.append('**自证结论：%s**\n' % ('通过（本件实现与已印 M.45(b) 读数对齐）' if ok_selftest
                                     else '**未能自证**（逐位对照有 MISMATCH；本表读数不得当作口径对齐的证据）'))
    md.append('## 1 图像同一性闸门（预注册条件 A4）\n')
    md.append('* ' + ' ｜ '.join(img_msgs))
    md.append('* 结论：**%s**\n' % ('通过' if img_ok else '★ 不通过（分析中止）'))
    md.append('## 2 主/次判据与两个事后单边诊断\n')
    md.append('| tag | 说明 | B | C | 参与单元 | 符合可比条件 | 比例 | 无任何可保留档对 | Spearman | '
              'bootstrap 95% CI | retention 中位 | 首位（全档位） | 首位（预算匹配） | 首位变 | 判据 |')
    md.append('|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|')
    for row in summary_rows:
        md.append('| ' + mdcells(row) + ' |')
    md.append('')
    md.append('## 3 逐单元\n')
    md.append('| tag | unit | 档数 | 档位标签 | MAE（各档） | rho（各档） | cost（各档） | span_full | '
              '可保留档对 | span_BM | retention | 状态 |')
    md.append('|---|---|---|---|---|---|---|---|---|---|---|---|')
    for row in detail_rows:
        md.append('| ' + mdcells(row) + ' |')
    md.append('')
    md.append('## 4 覆盖/缺失\n')
    md.append('| alias | knob | level | start | rows | ok | http≠200 | 未解析 | 重复 |')
    md.append('|---|---|---|---|---|---|---|---|---|')
    for row in sorted(stats):
        s = stats[row]
        md.append('| %s | %s | %s | %d | %d | %d | %d | %d | %d |'
                  % (row[0], row[1], row[2], row[3], s['rows'], s['ok'],
                     s['http_non200'], s['unparsed'], s['dup']))
    p4 = os.path.join(args.results, 'RESULTS_a57.md')
    with io.open(p4, 'w', encoding='utf-8') as fh:
        fh.write('\n'.join(md) + '\n')

    print('\n[输出]')
    for p in (p1, p2, p3, os.path.join(args.results, 'a57_budget_matched.json'), p4):
        print('  %s' % p)
    print('\n[判据] 主判据 (B,C)=(0.10,2.0)：%s'
          % ('PASS' if out['primary_B10_C2']['pass'] else
             'FAIL（排序未完全一致或首位变 ⇒ 按实测改写法）'))
    print('[读数] 符合可比条件的单元比例 = %.4f（%d/%d）；首位：全档位 %s ／ 预算匹配 %s'
          % (out['primary_B10_C2']['frac_comparable'],
             out['primary_B10_C2']['n_usable'], out['primary_B10_C2']['n_units'],
             out['primary_B10_C2']['top_full'], out['primary_B10_C2']['top_bm']))
    if not ok_selftest:
        print('★ 未能自证：本件读数与已印 §M.45(b) 未逐位对齐，必须在报告里如实写明。')
    return 0


if __name__ == '__main__':
    sys.exit(main())
