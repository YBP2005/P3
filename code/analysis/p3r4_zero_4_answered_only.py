# -*- coding: utf-8 -*-
"""p3r4_zero_4_answered_only.py —— P3 第 4 轮 ④：hy4 第 3 轮 #23 的 **X1**
（answered-only 口径重算 + GT 量级回归残差排序）。

## 来源与授权（hy4 第 3 轮 #23 逐字）
> **③ "契约旋钮的大跨度"可能主要是弃权质量 w 的跨度，而非方向调控的跨度。**
> **检验方法**：在 **answered-only 约定**下重算全套 36 单元的 span 与排序（数据已在包内，纯 ANALYSIS）。
> 若 VLM 单元跨度显著收缩而检测器单元不变、顶部旋钮改变，则必须把排序主张降为
> "pooled 口径（含弃权质量）下的排序"。
>
> **X1【ANALYSIS，0 次新调用】—— answered-only 口径下的响应谱重算 + GT 量级回归残差排序。**
> **判据（跑前固定）**：(i) answered-only 口径下 36 单元与 pooled 口径的 Spearman ≥ 0.85 且
> **顶部旋钮不变** ⇒ 排序不是弃权质量的副产物；(ii) 对 β∈{0,0.25,0.5,1} 的 `span/GT^β` 排序，
> 顶部旋钮在全部 β 上不变 ⇒ 排序不是 GT 量级的副产物。

hy4 自陈并**由协调方一手确认**：§M.37 只做了 GT-**形状**匹配（0.983）、绝对匹配被作者自判
不可构造（公共剖面仅 9 项 < 20 项资格线）⇒ **answered-only 重算 + GT 量级残差排序 包内确实没做过**。

## 铁律合规
* **0 次模型推理、0 GPU、0 新调用**：全部从**已存盘的逐项 CSV**重算。
* 单元构建器 **逐字复用** `n1_span_artefact_tests.py::build_units()`（它已实测与冻结件
  `equalcount36_result.json` 的 36 个单元名完全一致、ρ 跨度 max|Δ| = 0），因此不是新口径。
* **不改任何冻结件**；只写 `analysis/work/p3r4_zero_*`。
* 不碰 `repro_github\`；不改论文源件。

## 关于"GT 量级"的口径（写死，跑前声明）
`GT(u)` = 单元 u 在**各档 item 交集**上的 `gt` **中位数**（单元跨度用的正是这个交集）。
两个变量：`span_pooled/GT^β` 与 `span_answered/GT^β`。β=0 即不校正。
另给一个**不依赖 β** 的对照：以 `log10(GT)` 为自变量对 `log10(span)` 做 OLS，取残差排序。

用法：
  python p3r4_zero_4_answered_only.py --selftest
  python p3r4_zero_4_answered_only.py            # 写结果 JSON + md5
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
import collections
import csv
import glob
import hashlib
import io
import json
import math
import os
import re
import statistics as st
import sys
import time

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

HERE = os.path.dirname(os.path.abspath(__file__))
PAPER = os.path.dirname(os.path.dirname(HERE))
PM = os.path.join(PAPER, 'analysis', 'data', 'pod_mirror')
W_SHARED = NR('@shared', 'work')
B_SHARED = os.path.join(W_SHARED, 'b_harvest_20260917')
REF = os.path.join(HERE, 'equalcount36_result.json')
OUT = os.path.join(HERE, 'p3r4_zero_4_answered_only_result.json')

ANOM, SENT = 1e5, 1234567890
MIN_ITEMS = 20
BETAS = [0.0, 0.25, 0.5, 1.0]
SPAN_REF_TOL = 1e-6      # 复现闸门容差（先例 n1：max|Δ| = 0）


# ══════════════════════════════════════════════════════════════════════════════
# 单元构建：**逐字复用** n1_span_artefact_tests.py::build_units() 的载入器与资格规则
# ══════════════════════════════════════════════════════════════════════════════
def load(p):
    return list(csv.DictReader(io.open(p, encoding='utf-8-sig', errors='replace')))


def fn(s):
    try:
        return float(s)
    except Exception:
        return None


def unitize(rows, dims, pcol):
    out = collections.defaultdict(dict)
    for r in rows:
        g = fn(r.get('gt'))
        p = fn(r.get(pcol))
        if g is None or g <= 0 or p is None or p >= ANOM or p == SENT:
            continue
        try:
            key = tuple(str(r[d]).strip() for d in dims)
        except KeyError:
            continue
        out[key][str(r['item']).strip()] = (g, float(p))
    return out


UNITS = {}
MISSING = []


def add_unit(name, bylevel):
    lv = sorted(bylevel)
    if len(lv) < 3:
        return
    common = set.intersection(*[set(bylevel[s]) for s in lv])
    if len(common) < MIN_ITEMS:
        return
    UNITS[name] = dict(levels=[(s, bylevel[s]) for s in lv], keys=sorted(common))


def need(p, what):
    if not os.path.exists(p):
        MISSING.append('%s <- %s' % (what, p))
        return False
    return True


def build_units():
    for lab, path, pcol in (
            ('det·in-domain/VisDrone', os.path.join(PM, 'A', 'det_yolo_ladder_visdrone_det.csv'), 'n_det_person'),
            ('det·zero-shot COCO', os.path.join(PM, 'A', 'det_yolo_ladder_yolo12n.csv'), 'n_det_person'),
            ('det·in-domain(micro)/BBBC005', os.path.join(B_SHARED, 'bbbc_eval', 'ladder.csv'), 'n_det')):
        if not need(path, lab):
            continue
        u = unitize(load(path), ['tau', 'imgsz'], pcol)
        add_unit(lab + ' (full grid)', dict(u))
        for sz in sorted({k[1] for k in u if len(k) > 1}):
            add_unit('%s / tau@%s' % (lab, sz), {k: v for k, v in u.items() if len(k) > 1 and k[1] == sz})

    p = os.path.join(W_SHARED, 'dm_ladder.csv')
    if need(p, 'density·official DM-Count'):
        u = unitize(load(p), ['dataset', 'protocol', 'value'], 'pred')
        for ds in sorted({k[0] for k in u}):
            add_unit('density·official DM-Count / %s' % ds, {k: v for k, v in u.items() if k[0] == ds})
    for lab, path in (('density·CSRNet', os.path.join(PM, 'A', 'csrsta_ladder_st_a.csv')),
                      ('density·CSRNet', os.path.join(PM, 'A', 'csrucf_ladder_ucf.csv'))):
        if need(path, lab):
            u = unitize(load(path), ['protocol', 'value'], 'pred')
            add_unit('%s / %s' % (lab, os.path.basename(path).split('_')[-2]), dict(u))

    for mdl in ('ivl', 'q32'):
        for f in sorted(glob.glob(os.path.join(PM, 'res_ctrl__%s' % mdl, 'res_ctrl_*.csv'))):
            ds = os.path.basename(f)[len('res_ctrl_'):-4]
            u = unitize(load(f), ['budget'], 'pred')
            add_unit('VLM·pixel budget / %s / %s' % (mdl, ds), dict(u))

    for sub, mdl in (('tile_results', 'Qwen32B'), ('b2__out_32b_ctile', 'Qwen32B(ctile)'),
                     ('b2__out_8b_ctile', 'Qwen8B(ctile)')):
        d = os.path.join(PM, sub)
        if not os.path.isdir(d):
            continue
        groups = collections.defaultdict(dict)
        for f in sorted(os.listdir(d)):
            m = re.match(r'^vlm_([a-z0-9]+)_(base|over|under|[a-z0-9]+)_(whole|tile\d+)\.csv$', f)
            if not m:
                continue
            dom, arm, lvl = m.groups()
            d2 = {}
            for r in load(os.path.join(d, f)):
                g = fn(r.get('gt')); pp = fn(r.get('pred'))
                if g is None or g <= 0 or pp is None or pp >= ANOM or pp == SENT:
                    continue
                d2[str(r['item']).strip()] = (g, float(pp))
            groups[(dom, arm)][lvl] = d2
        for (dom, arm), bl in sorted(groups.items()):
            add_unit('VLM·tiling / %s / %s / %s' % (mdl, dom, arm), bl)

    for mdl, p in (('ivl', os.path.join(PM, 'b2__out_ivl', 'E1.csv')),
                   ('q32', os.path.join(PM, 'b2__out_q32', 'E1.csv'))):
        if need(p, 'VLM·output contract / %s' % mdl):
            u = unitize(load(p), ['arm'], 'pred')
            add_unit('VLM·output contract / %s' % mdl, dict(u))

    for sub, mdl in (('dense_prompt_results', 'Qwen32B'), ('ivl_dense_prompt_results', 'IVL')):
        d = os.path.join(PM, sub)
        if not os.path.isdir(d):
            continue
        groups = collections.defaultdict(dict)
        for f in sorted(os.listdir(d)):
            m = re.match(r'^([a-z0-9]+)_(base|over|under)_(V\d+)_([a-z_]+)\.csv$', f)
            if not m:
                continue
            dom, arm, lvl, _ = m.groups()
            d2 = {}
            for r in load(os.path.join(d, f)):
                g = fn(r.get('gt')); pp = fn(r.get('pred'))
                if g is None or g <= 0 or pp is None or pp >= ANOM or pp == SENT:
                    continue
                d2[str(r['item']).strip()] = (g, float(pp))
            groups[(dom, arm)][lvl] = d2
        for (dom, arm), bl in sorted(groups.items()):
            add_unit('VLM·prompt family / %s / %s / %s' % (mdl, dom, arm), bl)


# ══════════════════════════════════════════════════════════════════════════════
# 统计量
# ══════════════════════════════════════════════════════════════════════════════
def stat_rho(pairs):
    """★ 逐字照抄 `eb2_equalcount36.py` / `n1_span_artefact_tests.py::stat_rho`。"""
    sg = sum(g for g, _ in pairs)
    return 100.0 * (sum(p for _, p in pairs) - sg) / sg if sg else None


def stat_rho_answered(pairs):
    """answered-only 口径：只用 `pred > 0` 的项重算同一个池化相对偏差。"""
    a = [(g, p) for g, p in pairs if p > 0]
    sg = sum(g for g, _ in a)
    return 100.0 * (sum(p for _, p in a) - sg) / sg if sg else None


def span(seq):
    v = [x for x in seq if x is not None]
    return (max(v) - min(v)) if len(v) >= 2 else None


def spearman_avg(a, b):
    """平均秩 Spearman（同 n1 / eb2 的 rank() 口径）。"""
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
    ra, rb = rank(a), rank(b)
    n = len(a)
    ma, mb = sum(ra) / n, sum(rb) / n
    num = sum((ra[i] - ma) * (rb[i] - mb) for i in range(n))
    da = sum((ra[i] - ma) ** 2 for i in range(n)) ** 0.5
    db = sum((rb[i] - mb) ** 2 for i in range(n)) ** 0.5
    return num / (da * db) if da and db else float('nan')


def ols(xs, ys):
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    b = sxy / sxx if sxx else float('nan')
    a = my - b * mx
    resid = [y - (a + b * x) for x, y in zip(xs, ys)]
    ss_res = sum(r * r for r in resid)
    ss_tot = sum((y - my) ** 2 for y in ys)
    return dict(intercept=a, slope=b, r2=(1 - ss_res / ss_tot) if ss_tot else float('nan')), resid


def knob_of(unit_name):
    """单元名 -> 六个旋钮之一（逐字同 `p3r2_plan_m37_cluster.py::KNOB_OF_PREFIX` 的映射）。"""
    KNOB_OF_PREFIX = {
        'output contract': 'output_contract', 'pixel budget': 'pixel_budget',
        'prompt family': 'prompt_family', 'tiling': 'tiling',
        'CSRNet': 'density_regression', 'official DM-Count': 'density_regression',
        'in-domain(micro)': 'detection_threshold', 'in-domain': 'detection_threshold',
        'zero-shot COCO': 'detection_threshold',
    }
    rest = unit_name.split('·', 1)[1] if '·' in unit_name else unit_name
    prefix = rest.split('/')[0].strip()
    if prefix not in KNOB_OF_PREFIX and '(' in prefix:
        prefix = prefix.split('(')[0].strip()
    if prefix not in KNOB_OF_PREFIX:
        raise AssertionError('无法把 %r 映射到六个旋钮' % unit_name)
    return KNOB_OF_PREFIX[prefix]


def top_of(rows, key):
    best = max(rows, key=lambda r: r[key])
    return dict(unit=best['unit'], knob=best['knob'], value=best[key])


# ══════════════════════════════════════════════════════════════════════════════
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--selftest', action='store_true')
    args = ap.parse_args()
    if args.selftest:
        return selftest()

    t0 = time.time()
    print('=' * 120)
    print('P3R4-④ hy4 #23 X1：answered-only 口径重算 + GT 量级回归残差排序（0 次新调用）')
    print('=' * 120)

    build_units()
    if MISSING:
        print('!! 缺输入件：')
        for m in MISSING:
            print('   ', m)
        return 2

    ref = json.loads(io.open(REF, encoding='utf-8').read())
    ref_by = {u['unit']: u for u in ref['units']}
    print('\n① 复现闸门：重建单元集 vs 冻结件 `equalcount36_result.json`')
    print('   重建 %d 个单元 ｜ 冻结 %d 个' % (len(UNITS), len(ref_by)))
    only_new = sorted(set(UNITS) - set(ref_by))
    only_ref = sorted(set(ref_by) - set(UNITS))
    print('   仅在本次 %d 条 ｜ 仅在冻结件 %d 条' % (len(only_new), len(only_ref)))
    assert not only_new and not only_ref, \
        '单元集与冻结件不一致：本次多 %s ｜ 冻结多 %s' % (only_new[:5], only_ref[:5])
    assert len(UNITS) == 36, '单元数不是 36（实得 %d）' % len(UNITS)

    rows = []
    maxd = 0.0
    for name in sorted(UNITS):
        keys = UNITS[name]['keys']
        levels = UNITS[name]['levels']
        pooled = [stat_rho([d[k] for k in keys]) for _, d in levels]
        answered = [stat_rho_answered([d[k] for k in keys]) for _, d in levels]
        sp = span(pooled)
        sa = span(answered)
        gts = [d[k][0] for _, d in levels for k in keys]
        rows.append(dict(
            unit=name, knob=knob_of(name), n_levels=len(levels), n_items=len(keys),
            span_pooled=sp, span_answered=sa,
            ratio_answered_over_pooled=(sa / sp) if (sp not in (None, 0) and sa is not None) else None,
            gt_median=st.median(gts), gt_mean=sum(gts) / len(gts),
            pooled_levels=[None if v is None else round(v, 4) for v in pooled],
            answered_levels=[None if v is None else round(v, 4) for v in answered],
            n_answered_levels=sum(1 for v in answered if v is not None),
        ))
        d = abs((sp or 0.0) - (ref_by[name]['span'] or 0.0))
        maxd = max(maxd, d)
    print('   ★ ρ 跨度复现：max|Δ| = %.3e（n1 实测为 0；容差 %g）' % (maxd, SPAN_REF_TOL))
    gate_exact = maxd <= SPAN_REF_TOL
    print('   ⇒ 复现闸门 %s' % ('**精确通过**' if gate_exact else '**未通过**（下文读数降级为"参考"）'))

    pooled_spans = [r['span_pooled'] for r in rows]
    ans_spans = [r['span_answered'] for r in rows]
    print('\n② 主读数：answered-only 口径下的重算')
    print('   %-56s %9s %10s %8s %9s' % ('unit', 'span_pool', 'span_ans', 'ans/pool', 'GT med'))
    for r in sorted(rows, key=lambda x: -x['span_pooled'])[:6]:
        print('   %-56s %9.2f %10.2f %8s %9.1f'
              % (r['unit'], r['span_pooled'],
                 (r['span_answered'] if r['span_answered'] is not None else float('nan')),
                 ('%.3f' % r['ratio_answered_over_pooled']) if r['ratio_answered_over_pooled'] is not None else 'n/a',
                 r['gt_median']))
    print('   …（全 36 行见结果 JSON）')

    rho_pa = spearman_avg(pooled_spans, ans_spans)
    top_pool = top_of(rows, 'span_pooled')
    top_ans = top_of(rows, 'span_answered')
    print('\n   全 36 单元的 Spearman(pooled 序, answered-only 序) = **%.4f**' % rho_pa)
    print('   顶部单元：pooled = %s（%s，%.2f）｜ answered-only = %s（%s，%.2f）'
          % (top_pool['unit'], top_pool['knob'], top_pool['value'],
             top_ans['unit'], top_ans['knob'], top_ans['value']))
    crit1_rho = rho_pa >= 0.85
    crit1_top = top_pool['knob'] == top_ans['knob']
    print('   判据 (i)：Spearman >= 0.85 ? %s ｜ 顶部**旋钮**不变 ? %s  ⇒ **%s**'
          % (crit1_rho, crit1_top,
             '通过' if (crit1_rho and crit1_top) else '未通过'))

    # ── 判据 (i) 的稳健性：退化档位与"契约族 vs 检测器族"的直接对照 ──────────────
    print('\n②b 判据 (i) 的稳健性')
    deg = [r for r in rows if r['span_answered'] is None]
    print('   answered-only 跨度**无定义**的单元 = %d 个：%s'
          % (len(deg), [r['unit'] for r in deg] or '无'))
    nd = [r for r in rows if r['n_answered_levels'] < r['n_levels']]
    print('   有档位在 answered-only 下无定义的单元 = %d 个（这些单元的 answered 跨度由剩余档位给出）'
          % len(nd))
    robust = {}
    for tag, sub in (('全 36 单元', rows),
                     ('去掉 pixel_budget 六单元', [r for r in rows if r['knob'] != 'pixel_budget'])):
        pa = spearman_avg([r['span_pooled'] for r in sub], [r['span_answered'] for r in sub])
        tp = top_of(sub, 'span_pooled'); ta = top_of(sub, 'span_answered')
        same = tp['knob'] == ta['knob']
        robust[tag] = dict(spearman=pa, top_knob_pooled=tp['knob'], top_knob_answered=ta['knob'],
                           pass_rho=bool(pa >= 0.85), top_knob_unchanged=bool(same),
                           verdict='PASS' if (pa >= 0.85 and same) else 'FAIL')
        print('   %-26s Spearman = %.4f（>=0.85 ? %s）｜ 顶部旋钮不变 ? %s ⇒ %s'
              % (tag, pa, pa >= 0.85, same, '通过' if (pa >= 0.85 and same) else '未通过'))
    # 契约族 vs 检测器族：hy4 原话是"若 VLM 单元跨度显著收缩而检测器单元不变"
    con = [r for r in rows if r['knob'] in ('output_contract', 'prompt_family', 'tiling')]
    det = [r for r in rows if r['knob'] == 'detection_threshold']
    print('   契约族（output_contract + prompt_family + tiling，n=%d）比值中位 %.3f'
          % (len(con), st.median([r['ratio_answered_over_pooled'] for r in con
                                  if r['ratio_answered_over_pooled'] is not None])))
    print('   检测器族（detection_threshold，n=%d）比值中位 %.3f'
          % (len(det), st.median([r['ratio_answered_over_pooled'] for r in det
                                  if r['ratio_answered_over_pooled'] is not None])))
    con_max = max(con, key=lambda r: r['span_answered'] or -1)
    det_max = max(det, key=lambda r: r['span_answered'] or -1)
    print('   ★ 契约族最大 answered 跨度 = %.2f（%s）；检测器族最大 = %.2f（%s）⇒ 契约族仍%s'
          % (con_max['span_answered'], con_max['unit'], det_max['span_answered'], det_max['unit'],
             '更大（未收缩到检测器之下）' if (con_max['span_answered'] or 0) > (det_max['span_answered'] or 0)
             else '**已不再更大**'))

    print('\n③ 按旋钮看收缩（hy4 原话的检查项）')
    byk = collections.defaultdict(list)
    for r in rows:
        if r['ratio_answered_over_pooled'] is not None:
            byk[r['knob']].append(r['ratio_answered_over_pooled'])
    for k in sorted(byk, key=lambda x: st.median(byk[x])):
        v = byk[k]
        print('   %-22s n=%-3d 中位比值 %.3f  [%.3f, %.3f]'
              % (k, len(v), st.median(v), min(v), max(v)))

    # ── 判据 (ii)：GT 量级 ────────────────────────────────────────────────────
    print('\n④ 判据 (ii)：GT 量级回归残差排序（β ∈ %s）' % BETAS)
    print('   %-8s %-14s %-46s %-14s' % ('β', '口径', '顶部单元', '顶部旋钮'))
    beta_rows = {}
    for beta in BETAS:
        for tag, key in (('pooled', 'span_pooled'), ('answered', 'span_answered')):
            vals = []
            for r in rows:
                g = r['gt_median']
                if r[key] is None or g <= 0:
                    vals.append(None)
                    continue
                vals.append(r[key] / (g ** beta))
            valid = [(r, v) for r, v in zip(rows, vals) if v is not None]
            top = max(valid, key=lambda x: x[1])
            beta_rows['%s|beta=%g' % (tag, beta)] = dict(
                beta=beta, caliber=tag, top_unit=top[0]['unit'], top_knob=top[0]['knob'],
                top_value=top[1],
                ranking=[dict(unit=r['unit'], knob=r['knob'], value=v)
                         for r, v in sorted(valid, key=lambda x: -x[1])])
            print('   %-8g %-14s %-46s %-14s' % (beta, tag, top[0]['unit'], top[0]['knob']))

    pooled_beta_tops = {beta_rows['pooled|beta=%g' % b]['top_knob'] for b in BETAS}
    ans_beta_tops = {beta_rows['answered|beta=%g' % b]['top_knob'] for b in BETAS}
    crit2 = len(pooled_beta_tops) == 1
    print('   β 上 pooled 顶部旋钮集合 = %s ⇒ 判据 (ii) pooled 侧 **%s**'
          % (sorted(pooled_beta_tops), '通过' if crit2 else '未通过'))
    print('   β 上 answered 顶部旋钮集合 = %s' % sorted(ans_beta_tops))
    # ★ 判据 (ii) 的**刻度**：unit-level 口径太严（top-1 只能有一个），故并印整条排序的相关系数
    #   与 top-3。
    print('   判据 (ii) 的刻度对照（top-1 相等是"最严"读法）：')
    base_rank = [r['unit'] for r in beta_rows['pooled|beta=0']['ranking']]
    v0 = [r['value'] for r in beta_rows['pooled|beta=0']['ranking']]
    for b in BETAS:
        row = beta_rows['pooled|beta=%g' % b]
        v = [r['value'] for r in row['ranking']]
        rho = spearman_avg(v0, v)
        top3 = [r['knob'] for r in row['ranking'][:3]]
        print('     β=%-5g Spearman(序 vs β=0) = %.4f ｜ top-3 旋钮 = %s'
              % (b, rho, top3))
        row['spearman_vs_beta0'] = rho
        row['top3_knobs'] = top3


    # ── OLS 残差（不依赖 β 的对照）────────────────────────────────────────────
    xs = [math.log10(r['gt_median']) for r in rows]
    ys = [math.log10(r['span_pooled']) for r in rows]
    fit, resid = ols(xs, ys)
    for r, e in zip(rows, resid):
        r['log_span_residual'] = e
    top_res = max(rows, key=lambda r: r['log_span_residual'])
    bot_res = min(rows, key=lambda r: r['log_span_residual'])
    print('\n⑤ 不依赖 β 的对照：OLS  log10(span_pooled) ~ log10(GT median)')
    print('   斜率 β̂ = %.4f（hy4 的 β 网格正好跨在它两侧）｜ R² = %.4f' % (fit['slope'], fit['r2']))
    print('   最大正残差 = %s（%s，%+.4f）' % (top_res['unit'], top_res['knob'], top_res['log_span_residual']))
    print('   最大负残差 = %s（%s，%+.4f）' % (bot_res['unit'], bot_res['knob'], bot_res['log_span_residual']))
    # 残差序 vs pooled 序 / answered 序
    rho_res_pool = spearman_avg([r['log_span_residual'] for r in rows], pooled_spans)
    rho_res_ans = spearman_avg([r['log_span_residual'] for r in rows], ans_spans)
    print('   Spearman(残差序, pooled 序) = %.4f ｜ Spearman(残差序, answered 序) = %.4f'
          % (rho_res_pool, rho_res_ans))

    out = dict(
        purpose='P3R4-④：hy4 第 3 轮 #23 的 X1 —— answered-only 口径下的 36 单元响应谱重算，'
                '以及 GT 量级的回归残差排序。0 次新调用、0 新数据。',
        provenance=dict(
            requester='hy4 第 3 轮 #23（替代解释 ③ + X1 判据）',
            coordinator_confirmed_absent='§M.37 只做 GT-形状匹配（0.983）；绝对匹配被作者自判不可构造'
                                         '（公共剖面 9 项 < 20 项资格线）⇒ answered-only 重算与'
                                         'GT 量级残差排序包内确实未做过',
            builder='逐字复用 n1_span_artefact_tests.py::build_units()'
                    '（其已实测与 equalcount36_result.json 的 36 个单元名完全一致、ρ 跨度 max|Δ| = 0）',
        ),
        prereg=dict(
            criterion_i='answered-only 口径下 36 单元与 pooled 口径的 Spearman >= 0.85 **且** 顶部旋钮不变',
            criterion_ii='β ∈ {0,0.25,0.5,1} 的 span/GT^β 排序，顶部旋钮在全部 β 上不变',
            gt_definition='GT(u) = 单元 u 在各档 item 交集上的 gt 中位数（与单元跨度用同一个交集）',
            answered_only='池化相对偏差只用 pred > 0 的项重算：rho_ans = 100*(sum p - sum g)/sum g',
        ),
        reproduction_gate=dict(
            n_units_rebuilt=len(UNITS), n_units_frozen=len(ref_by),
            units_only_new=only_new, units_only_frozen=only_ref,
            max_abs_delta_span=maxd, tolerance=SPAN_REF_TOL, exact=bool(gate_exact),
            note='max|Δ| 与 n1 报告一致（其实测为 0）',
        ),
        units=rows,
        criterion_i=dict(spearman_pooled_vs_answered=rho_pa, threshold=0.85,
                         pass_rho=bool(crit1_rho),
                         top_unit_pooled=top_pool, top_unit_answered=top_ans,
                         top_knob_unchanged=bool(crit1_top),
                         verdict='PASS' if (crit1_rho and crit1_top) else 'FAIL',
                         units_with_undefined_answered_span=[r['unit'] for r in deg],
                         units_with_some_undefined_answered_level=len(nd),
                         robustness=robust,
                         contract_family_max_answered=dict(unit=con_max['unit'],
                                                           value=con_max['span_answered']),
                         detector_family_max_answered=dict(unit=det_max['unit'],
                                                            value=det_max['span_answered'])),
        contraction_by_knob={k: dict(n=len(v), median=st.median(v), lo=min(v), hi=max(v))
                             for k, v in byk.items()},
        criterion_ii=dict(betas=BETAS, table=beta_rows,
                          pooled_top_knobs=sorted(pooled_beta_tops),
                          answered_top_knobs=sorted(ans_beta_tops),
                          pass_pooled=bool(crit2),
                          verdict='PASS' if crit2 else 'FAIL'),
        ols_residual=dict(fit=fit,
                          top_positive=dict(unit=top_res['unit'], knob=top_res['knob'],
                                            residual=top_res['log_span_residual']),
                          top_negative=dict(unit=bot_res['unit'], knob=bot_res['knob'],
                                            residual=bot_res['log_span_residual']),
                          spearman_residual_vs_pooled=rho_res_pool,
                          spearman_residual_vs_answered=rho_res_ans),
        created_by='p3r4_zero_4_answered_only.py',
        created_at=time.strftime('%Y-%m-%dT%H:%M:%S'),
        no_inference=True, new_calls=0,
    )
    io.open(OUT, 'w', encoding='utf-8', newline='\n').write(json.dumps(out, ensure_ascii=False, indent=2))
    h = hashlib.md5(io.open(OUT, 'rb').read()).hexdigest()
    io.open(OUT + '.md5', 'w', encoding='utf-8', newline='\n').write(
        '%s  %s  (p3r4_zero_4_answered_only.py)\n' % (h, os.path.basename(OUT)))
    print('\n已写 %s（md5 %s）' % (os.path.basename(OUT), h[:12]))
    print('用时 %.1f s' % (time.time() - t0))
    return 0


def selftest():
    print('P3R4-④ selftest（阴性对照）')
    ctl = []
    # 1) 无弃权时 answered-only 与 pooled 必须逐位相同
    pairs = [(10.0, 12.0), (20.0, 15.0), (30.0, 33.0)]
    ctl.append(('无弃权 ⇒ answered == pooled',
                abs(stat_rho(pairs) - stat_rho_answered(pairs)) < 1e-12))
    # 2) 有弃权时二者必须不同
    pairs2 = [(10.0, 0.0), (20.0, 25.0), (30.0, 24.0)]
    ctl.append(('有弃权 ⇒ answered != pooled', abs(stat_rho(pairs2) - stat_rho_answered(pairs2)) > 1e-9))
    # 3) 全弃权 ⇒ answered 无定义
    ctl.append(('全弃权 ⇒ answered 无定义',
                stat_rho_answered([(1.0, 0.0), (2.0, 0.0)]) is None))
    # 4) Spearman 对单调变换不变
    a = [1.0, 2.0, 3.0, 4.0]
    b = [math.exp(1.0), math.exp(2.0), math.exp(3.0), math.exp(4.0)]
    ctl.append(('Spearman 对单调变换不变', abs(spearman_avg(a, b) - 1.0) < 1e-12))
    # 5) OLS 斜率自证
    fit, resid = ols([1.0, 2.0, 3.0], [2.0, 4.0, 6.0])
    ctl.append(('OLS 斜率 = 2、残差全 0',
                abs(fit['slope'] - 2.0) < 1e-12 and max(abs(r) for r in resid) < 1e-12))
    # 6) 旋钮映射自证（与 p3r2_plan_m37_cluster.py 的写死表逐条对齐）
    ctl.append(('旋钮映射：CSRNet -> density_regression',
                knob_of('density·CSRNet / st') == 'density_regression'))
    ctl.append(('旋钮映射：zero-shot COCO -> detection_threshold',
                knob_of('det·zero-shot COCO (full grid)') == 'detection_threshold'))
    ctl.append(('旋钮映射：output contract', knob_of('VLM·output contract / ivl') == 'output_contract'))
    ok = True
    for nm, passed in ctl:
        print('  [%s] %s' % ('PASS' if passed else 'FAIL', nm))
        ok = ok and passed
    print('SELFTEST: %s' % ('PASS' if ok else 'FAIL'))
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
