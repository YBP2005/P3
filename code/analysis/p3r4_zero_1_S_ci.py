# -*- coding: utf-8 -*-
"""p3r4_zero_1_S_ci.py —— P3 第 4 轮 ①：给 §5.5 Table 3 的四个 S 值加 **block bootstrap** 95% 区间。

## 来源与授权
早前一次核查 #12：§5.5 的 Table 3 逐格 S（94.2 / 93.7 / 83.8 / 82.1 %）只有点估计，而 §7.3 的
排序已给簇级区间。冻结/后续件已明写该处 "no new inference"、逐项 CSV 已存盘 ⇒ **只是重采样**。

## 铁律合规
* **0 次模型推理、0 GPU**：只读已存盘的逐项 CSV，全部在本地重算。
* **不改任何冻结件**（`*_criteria_frozen*.json` / `*_result.json` 一律只读）。
* **不写 `repro_github\\`**：本脚本只写 `analysis\\work\\p3r4_zero_*` 新文件。
* 口径**复用既有件**，不另创：
  - 单元统计与数据卫生 = `p4_decomp_verify.py::unit_stats()` **逐字**（按 item 去重、
    剔 `pred >= 1e5`、剔空/不可解析 `pred`、`gt` 由行内读）；
  - bootstrap 分位口径 = `m37_ci_power.py::boot_ci()`（N 次有放回重抽，取 2.5 / 97.5 分位，
    用 `out[int(q*N)]` 索引，seed 20260924）；
  - 簇级（按 knob 整块重抽）= `p3r2_plan_m37_cluster.py::boot_block()` 的分位口径。

## 单元（unit）的定义 —— 写死，跑前声明
语料里**每个 (域 × 契约臂 × 切块档) 单元恰好是一份逐项 CSV**；四个 headline 域各只有一份
`base` / 整图 单元（`dense_results/vlm_st_a_base_whole.csv` 等）。
⇒ **单元 = 同一个域内的一批图像**（与 §7.3 "unit bootstrap" 的既有用法同源：§7.3 的单元就是
"一个 (knob × 域/构建) 单元"，这里每个域只有一个单元）。
因此本脚本给三层读数，**三层都印，不混用**：
  (A) 域内 **图像级 block bootstrap**（主读数）：有放回重抽该域 182 / 334 / 226 / 400 张图，
      每抽一次重算 G / G_N / P 与 S；
  (B) **域级**（4 个 headline 域当 4 个簇）整块重抽：量化"四值区间的**位置**"的不确定度；
  (C) **纯重采样对照**：S 在重抽下的分位区间（与 (A) 同一次重抽的副产品，用于说明 S 的
      抽样分布是否偏斜）。

## 已知且**必须并印**的口径事实（一手实测，本脚本断言）
Table 3 末列标题写 `abstention term, item-count convention`，而**实测**该列四个值
（56.6 / 53.9 / 68.1 / 68.2）逐位等于**这四个 base 臂单元的未加权弃权率**
`100 * (n - n_answered) / n`（56.5934 / 53.8922 / 68.1416 / 68.2500）。
真正的"item-count 口径 S"（`1-w_i)/(1-w_i(1+rho_a,i))`，w_i = n_answered/n）印出来是
86.8 / 80.0 / 84.4 / 87.6 —— **与表内那四个数完全不同**。
⇒ 本脚本**不改任何冻结件**，只如实记录：这一列是**未加权弃权率**，与它的标题不符
（属既有登记项 P-12 的同类命名问题，不是新发现）。**本轮的四个 S（Table 3 的 S 列）不受影响。**

用法：
  python p3r4_zero_1_S_ci.py --selftest   # 阴性对照（不读语料）
  python p3r4_zero_1_S_ci.py              # 全量，写结果 JSON + md5
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
import argparse
import csv
import hashlib
import io
import json
import os
import random
import re
import sys
import time

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

W = os.path.dirname(os.path.abspath(__file__))
PM = RP('analysis', 'data', 'pod_mirror')
OUT = os.path.join(W, 'p3r4_zero_1_S_ci_result.json')

# ── 口径常量：全部**逐字**取自既有件，不新创 ──────────────────────────────────
SEED = 20260924          # 与 m37_ci_power.py / p3r2_plan_m37_cluster.py 同
N_BOOT = 2000            # 与 m37_ci_power.py::boot_ci 默认同
ANOM = 1e5               # p4_decomp_verify.py：剔 pred >= 1e5

# 四个 headline 域：(显示名, 单元 CSV 相对 pod_mirror 的路径, Table 3 印的 S, Table 3 末列印值)
DOMAINS = [
    ('ShanghaiTech-A', r'dense_results\vlm_st_a_base_whole.csv', 94.2, 56.6),
    ('UCF-QNRF',       r'dense_results\vlm_ucf_base_whole.csv',  93.7, 53.9),
    ('AI-TOD',         r'aerial_results\aer_aitod_base.csv',     83.8, 68.1),
    ('VisDrone',       r'aerial_results\aer_visdrone_base.csv',  82.1, 68.2),
]

NAME = re.compile(r'^(vlm|aer|ext)_(.+?)_(base|over|under)(?:_(whole|tile\d+))?\.csv$')


# ══════════════════════════════════════════════════════════════════════════════
# 单元统计：逐字照抄 p4_decomp_verify.py::unit_stats() 的**数据卫生**与**口径**
# ══════════════════════════════════════════════════════════════════════════════
def load(p):
    with io.open(p, encoding='utf-8-sig', errors='replace') as f:
        return [r for r in csv.DictReader(f) if '#r' not in str(r.get('item') or '')]


def rows_clean(path):
    """返回 [(item, gt, pred)]，已按 p4 的口径清洗（去重、剔空、剔 pred>=1e5）。"""
    seen, out = set(), []
    for r in load(path):
        k = str(r.get('item') or '').strip()
        if k in seen:
            continue
        seen.add(k)
        s = str(r.get('pred') or '').strip()
        if s == '':
            continue
        try:
            v = float(s)
        except Exception:
            continue
        if v >= ANOM:
            continue
        g = str(r.get('gt') or '').strip()
        try:
            gv = float(g) if g != '' else 0.0
        except Exception:
            gv = 0.0
        out.append((k, gv, v))
    return out


def S_of(recs, weight):
    """recs = [(item, gt, pred)]；weight='gt' 用真值加权口径、weight='item' 用计数口径。
    返回 (S_percent, w, rho_total, rho_answered, n, n_answered)，退化时 S 为 None。"""
    if weight == 'gt':
        n = len(recs)
        G = sum(g for _, g, _ in recs)
        ans = [(g, p) for _, g, p in recs if p > 0]
        GN = sum(g for g, _ in ans)
        P = sum(p for _, p in ans)
    else:
        n = len(recs)
        G = float(sum(1 for _ in recs))
        ans = [(1.0, p) for _, g, p in recs if p > 0]
        GN = float(len(ans))
        P = sum(p for _, p in ans)
    na = len(ans)
    if G <= 0 or GN <= 0 or na == 0 or na == n:
        return (None, None, None, None, n, na)
    w = GN / G
    rho_t = (P - G) / G
    rho_a = (P - GN) / GN
    if rho_t >= 0:
        return (None, w, rho_t, rho_a, n, na)
    S = 100.0 * (1 - w) / (1 - w * (1 + rho_a))
    return (S, w, rho_t, rho_a, n, na)


def q(sorted_vals, frac):
    """分位口径**逐字**照抄 m37_ci_power.py::boot_ci()：out[int(frac * N)]。"""
    return sorted_vals[int(frac * len(sorted_vals))]


def boot_domain(recs, n_boot=N_BOOT, seed=SEED):
    """域内**图像级** block bootstrap：有放回重抽 len(recs) 张图，每抽一次重算 S。"""
    rnd = random.Random(seed)
    n = len(recs)
    point, w, rt, ra, _n, na = S_of(recs, 'gt')
    draws, wn, ran = [], [], []
    for _ in range(n_boot):
        idx = [rnd.randrange(n) for _ in range(n)]
        sub = [recs[i] for i in idx]
        s, ww, rtt, raa, _nn, _na = S_of(sub, 'gt')
        if s is not None:
            draws.append(s)
        if ww is not None:
            wn.append(ww)
            ran.append(raa)
    draws.sort()
    wn.sort()
    ran.sort()
    return dict(point=point, p025=q(draws, 0.025), p975=q(draws, 0.975),
                n_boot=n_boot, n_effective=len(draws), seed=seed,
                w_point=w, w_p025=q(wn, 0.025), w_p975=q(wn, 0.975),
                rho_a_point=ra, rho_a_p025=q(ran, 0.025), rho_a_p975=q(ran, 0.975),
                n_items=n, n_answered=na)


def boot_cluster(dom_recs, n_boot=N_BOOT, seed=SEED):
    """域级**整块**重抽（4 个 headline 域 = 4 个簇）：量化"四值位置"的不确定度。"""
    rnd = random.Random(seed)
    K = len(dom_recs)
    pts = [S_of(r, 'gt')[0] for r in dom_recs]
    lo_all, hi_all = [], []
    for _ in range(n_boot):
        pick = [dom_recs[rnd.randrange(K)] for _ in range(K)]
        vals = [S_of(pick[i], 'gt')[0] for i in range(K)]
        vals = [v for v in vals if v is not None]
        if len(vals) >= 2:
            lo_all.append(min(vals))
            hi_all.append(max(vals))
    lo_all.sort()
    hi_all.sort()
    return dict(n_clusters=K, point_range=[min(pts), max(pts)],
                p025_of_low=q(lo_all, 0.025), p975_of_low=q(lo_all, 0.975),
                p025_of_high=q(hi_all, 0.025), p975_of_high=q(hi_all, 0.975),
                n_boot=n_boot, n_effective=len(lo_all), seed=seed,
                note='簇 = 域；簇内保留 (item, gt, pred) 配对，按簇整块有放回重抽；'
                     '每抽一次取重抽后四值的 min/max 作为该次的范围端点')


# ══════════════════════════════════════════════════════════════════════════════
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--selftest', action='store_true')
    args = ap.parse_args()

    if args.selftest:
        return selftest()

    t0 = time.time()
    print('=' * 116)
    print('P3R4-① §5.5 Table 3 四个 S 的 block bootstrap 95% 区间（0 次推理，纯重采样）')
    print('=' * 116)

    doms = []
    for name, rel, printed_S, printed_col in DOMAINS:
        p = os.path.join(PM, rel)
        assert os.path.exists(p), '缺单元件：%s' % p
        recs = rows_clean(p)
        md5 = hashlib.md5(io.open(p, 'rb').read()).hexdigest()
        doms.append(dict(name=name, rel=rel, path=p, recs=recs, md5=md5,
                         printed_S=printed_S, printed_col=printed_col))
        print('  读入 %-16s n=%-4d  印 S=%.1f%%  印末列=%.1f%%  md5 %s'
              % (name, len(recs), printed_S, printed_col, md5[:10]))

    # ── 自证 1：点估计必须**逐位复现** Table 3 的四个 S ──────────────────────────
    print('\n① 自证：点估计逐位复现 Table 3（J.1 的 w / rho_answered 也对账）')
    ok = True
    for d in doms:
        S, w, rt, ra, n, na = S_of(d['recs'], 'gt')
        d['point'] = dict(S=S, w=w, rho_t=100 * rt, rho_a=100 * ra, n=n, n_answered=na)
        d['unweighted_abstention'] = 100.0 * (n - na) / n
        d['S_item_convention'] = S_of(d['recs'], 'item')[0]
        hit = abs(S - d['printed_S']) <= 0.05
        ok = ok and hit
        print('   %-16s S=%.4f%%（印 %.1f%% %s）  w=%.4f  rho_ans=%.2f%%  未加权弃权=%.4f%%（末列印 %.1f%%）'
              % (d['name'], S, d['printed_S'], 'OK' if hit else '<-- 不符', w, 100 * ra,
                 d['unweighted_abstention'], d['printed_col']))
    assert ok, '点估计未复现 Table 3 ⇒ 语料或口径变了，拒绝继续'

    # ── 自证 2：末列 = 未加权弃权率（不是 item-count 口径的 S）────────────────────
    print('\n② 自证：Table 3 末列的**真实口径**（这是既有登记项，不是本轮新缺陷）')
    print('   %-16s %-14s %-14s %-14s' % ('domain', '末列印值', '未加权弃权率', 'item-count 口径 S'))
    for d in doms:
        m1 = abs(d['unweighted_abstention'] - d['printed_col']) <= 0.05
        m2 = (d['S_item_convention'] is None
              or abs(d['S_item_convention'] - d['printed_col']) > 0.05)
        print('   %-16s %-14.1f %-14.4f %-14s   %s'
              % (d['name'], d['printed_col'], d['unweighted_abstention'],
                 ('%.4f' % d['S_item_convention']) if d['S_item_convention'] is not None else 'undefined',
                 '末列 == 未加权弃权率 ✓' if (m1 and m2) else '<-- 口径待查'))
        assert m1, '%s：末列不等于未加权弃权率' % d['name']
        assert m2, '%s：末列等于 item-count 口径 S ⇒ 断言前提有变' % d['name']

    # ── 主读数 (A)：域内图像级 block bootstrap ─────────────────────────────────
    print('\n③ 主读数 (A)：域内**图像级** block bootstrap（N=%d，seed %d，分位口径同 m37_ci_power）'
          % (N_BOOT, SEED))
    rows = {}
    for d in doms:
        b = boot_domain(d['recs'])
        rows[d['name']] = b
        print('   %-16s S = %6.2f%%  95%% CI [%6.2f, %6.2f]   '
              '(w %.4f [%.4f, %.4f]; rho_ans %.2f%% [%.2f, %.2f])'
              % (d['name'], b['point'], b['p025'], b['p975'],
                 b['w_point'], b['w_p025'], b['w_p975'],
                 b['rho_a_point'], b['rho_a_p025'], b['rho_a_p975']))

    # ── 主读数 (B)：域级整块重抽 ────────────────────────────────────────────────
    print('\n④ 主读数 (B)：**域级**整块重抽（4 个 headline 域 = 4 个簇）')
    cb = boot_cluster([d['recs'] for d in doms])
    print('   观测四值范围 = [%.2f, %.2f]' % tuple(cb['point_range']))
    print('   重抽后「下端」的 95%% 区间 = [%.2f, %.2f]' % (cb['p025_of_low'], cb['p975_of_low']))
    print('   重抽后「上端」的 95%% 区间 = [%.2f, %.2f]' % (cb['p025_of_high'], cb['p975_of_high']))

    # ── 与 §7.3 / §M.37 的口径一致性说明 ───────────────────────────────────────
    print('\n⑤ 与 §7.3 簇级口径的一致性（复算 §7.3 / M.37 已印的区间，作阴性对照）')
    EQ = os.path.join(W, 'equalcount36_result.json')
    M37 = os.path.join(W, 'm37_ci_power_result.json')
    eq = json.loads(io.open(EQ, encoding='utf-8').read())
    m37 = json.loads(io.open(M37, encoding='utf-8').read())
    units = eq['units']
    u31 = [u for u in units if 'span_eq4' in u and u.get('n', 0) >= 4]
    assert len(units) == 36 and len(u31) == 31, '36/31 单元集规模不符'
    got36 = [round(m37['ordering']['36unit_k3']['boot_ci']['p025'], 3),
             round(m37['ordering']['36unit_k3']['boot_ci']['p975'], 3)]
    got31 = [round(m37['ordering']['31unit_k4']['boot_ci']['p025'], 3),
             round(m37['ordering']['31unit_k4']['boot_ci']['p975'], 3)]
    print('   冻结件 M.37 印：31@k4 = %s；36@k3 = %s（§7.3 正文印 0.939-0.996 / 0.836-0.983）'
          % (got31, got36))
    print('   ⇒ 本脚本的 S 区间用的是**同一条分位口径**（out[int(q*N)]）与**同一 seed**，')
    print('     单元定义按语料结构写死为「域内一批图像」（每个 headline 域恰一个单元）。')
    # 同一条口径也能复算 §7.3 的区间（本脚本内联实现，证明口径确实一致）
    def spearman(x, y):
        n = len(x)
        rx = {v: i for i, v in enumerate(sorted(x))}
        ry = {v: i for i, v in enumerate(sorted(y))}
        ax = [rx[v] for v in x]
        ay = [ry[v] for v in y]
        mx, my = sum(ax) / n, sum(ay) / n
        num = sum((a - mx) * (b - my) for a, b in zip(ax, ay))
        dx = sum((a - mx) ** 2 for a in ax) ** 0.5
        dy = sum((b - my) ** 2 for b in ay) ** 0.5
        return num / (dx * dy) if dx and dy else float('nan')

    def boot_ci(a, b, n_boot=N_BOOT, seed=SEED):
        rnd = random.Random(seed)
        n = len(a)
        out = [spearman([a[i] for i in [rnd.randrange(n) for _ in range(n)]],
                        [b[i] for i in [rnd.randrange(n) for _ in range(n)]])
               for _ in range(0)]
        # ★ 上面那种写法会消耗两倍随机数；改成与 m37_ci_power.py::boot_ci **逐字同序**：
        rnd = random.Random(seed)
        out = []
        for _ in range(n_boot):
            idx = [rnd.randrange(n) for _ in range(n)]
            out.append(spearman([a[i] for i in idx], [b[i] for i in idx]))
        out.sort()
        return out[int(0.025 * n_boot)], out[int(0.975 * n_boot)]

    r36 = boot_ci([u['span'] for u in units], [u['span_eq'] for u in units])
    r31 = boot_ci([u['span'] for u in u31], [u['span_eq4'] for u in u31])
    print('   本脚本同口径复算：     31@k4 = [%.3f, %.3f]；36@k3 = [%.3f, %.3f]'
          % (r31[0], r31[1], r36[0], r36[1]))
    nc = (abs(round(r31[0], 3) - got31[0]) <= 0.001 and abs(round(r31[1], 3) - got31[1]) <= 0.001
          and abs(round(r36[0], 3) - got36[0]) <= 0.001 and abs(round(r36[1], 3) - got36[1]) <= 0.001)
    print('   ⇒ 阴性对照 %s（同口径 + 同 seed 必须逐位复现冻结件）' % ('通过 ✓' if nc else '**失败**'))
    assert nc, 'bootstrap 口径与 m37_ci_power.py 不一致'

    out = dict(
        purpose='P3R4-①：给 §5.5 Table 3 的四个 S 值加 block bootstrap 95% 区间。'
                '0 次推理、0 新数据，纯重采样；口径复用 m37_ci_power.py::boot_ci + '
                'p4_decomp_verify.py::unit_stats。',
        unit_definition='语料结构：每个 (域 × 契约臂 × 切块档) 恰好一份逐项 CSV；四个 headline 域各只有'
                        '一份 base/整图 单元 ⇒ 单元 = 域内的一批图像（与该域的全部图像重合）。'
                        '与 §7.3 的单元口径同源（那里一个单元 = 一个 knob × 域/构建）；'
                        '但 §7.3 有 31/36 个单元可重抽，这里**每个域只有 1 个单元**，'
                        '故 (A) 只能给域内图像级区间，(B) 另给域级整块区间。',
        design=dict(seed=SEED, n_boot=N_BOOT, quantile='out[int(q*N)]（逐字同 m37_ci_power.py::boot_ci）',
                    resample_A='域内有放回重抽 len(items) 张图；簇内保留 (gt, pred) 配对',
                    resample_B='4 个域当 4 个簇，按簇整块有放回重抽'),
        inputs={d['name']: dict(path=d['rel'], md5=d['md5'], n_items=len(d['recs']))
                for d in doms},
        point_estimates={d['name']: d['point'] for d in doms},
        A_image_level_within_domain=rows,
        B_domain_level_cluster=cb,
        table3_last_column_audit={
            'printed': {d['name']: d['printed_col'] for d in doms},
            'unweighted_abstention_rate': {d['name']: d['unweighted_abstention'] for d in doms},
            'item_count_convention_S': {d['name']: d['S_item_convention'] for d in doms},
            'finding': '末列四个印值逐位等于**未加权弃权率**，不等于 item-count 口径的 S；'
                       '列标题与内容不符。属既有登记项（第 3 轮 P-12 的同类命名问题），'
                       '**本轮不改任何冻结件**，只如实记录。Table 3 的 S 列（本轮对象）不受影响。',
        },
        caliber_consistency=dict(
            frozen_m37_31k4=got31, frozen_m37_36k3=got36,
            recomputed_31k4=[round(r31[0], 3), round(r31[1], 3)],
            recomputed_36k3=[round(r36[0], 3), round(r36[1], 3)],
            negative_control_pass=bool(nc),
            note='分位口径与 seed 与 m37_ci_power.py 逐字相同；31/36 单元 bootstrap 区间逐位复现冻结件。',
        ),
        created_by='p3r4_zero_1_S_ci.py',
        created_at=time.strftime('%Y-%m-%dT%H:%M:%S'),
        no_inference=True,

    )
    io.open(OUT, 'w', encoding='utf-8', newline='\n').write(json.dumps(out, ensure_ascii=False, indent=2))
    h = md5f(OUT)
    io.open(OUT + '.md5', 'w', encoding='utf-8', newline='\n').write(
        '%s  %s  (p3r4_zero_1_S_ci.py)\n' % (h, os.path.basename(OUT)))
    print('\n已写 %s（md5 %s）' % (os.path.basename(OUT), h[:12]))
    print('用时 %.1f s' % (time.time() - t0))
    return 0


def md5f(p):
    return hashlib.md5(io.open(p, 'rb').read()).hexdigest()


def selftest():
    """阴性对照（不读语料）：口径实现的边界行为。"""
    print('P3R4-① selftest（阴性对照，不读语料）')
    ctl = []
    # 1) 全弃权 / 无弃权 ⇒ S 无定义
    recs_all_ab = [('a', 10.0, 0.0), ('b', 20.0, 0.0)]
    ctl.append(('全弃权 ⇒ S 无定义', S_of(recs_all_ab, 'gt')[0] is None))
    recs_no_ab = [('a', 10.0, 5.0), ('b', 20.0, 30.0)]
    ctl.append(('无弃权 ⇒ S 无定义', S_of(recs_no_ab, 'gt')[0] is None))
    # 2) rho_total >= 0 ⇒ S 无定义（定义域边界）
    recs_pos = [('a', 10.0, 0.0), ('b', 10.0, 40.0)]
    ctl.append(('rho_total >= 0 ⇒ S 无定义', S_of(recs_pos, 'gt')[0] is None))
    # 3) 恒等式：rho_t = w(1+rho_a) - 1
    recs = [('a', 100.0, 0.0), ('b', 300.0, 200.0), ('c', 100.0, 120.0)]
    S, w, rt, ra, n, na = S_of(recs, 'gt')
    ctl.append(('恒等式 rho_t = w(1+rho_a) - 1 精确成立',
                abs(rt - (w * (1 + ra) - 1)) < 1e-12))
    # 4) 闭式 S = (1-w)/(1-w(1+rho_a))
    ctl.append(('闭式 S 与上式一致',
                abs(S - 100 * (1 - w) / (1 - w * (1 + ra))) < 1e-9))
    # 5) 分位口径与手算一致
    v = sorted([float(i) for i in range(1000)])
    ctl.append(('q(0.025)=v[25]、q(0.975)=v[975]', q(v, 0.025) == 25.0 and q(v, 0.975) == 975.0))
    # 6) 抽掉全部弃权项后 S 必须变化（bootstrap 确实在重算，不是摆设）
    rnd = random.Random(1)
    sub = [recs[1], recs[2]]
    ctl.append(('抽掉弃权项后 S/无定义 与原点不同',
                S_of(sub, 'gt')[0] != S))
    ok = True
    for nm, passed in ctl:
        print('  [%s] %s' % ('PASS' if passed else 'FAIL', nm))
        ok = ok and passed
    print('SELFTEST: %s' % ('PASS' if ok else 'FAIL'))
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
