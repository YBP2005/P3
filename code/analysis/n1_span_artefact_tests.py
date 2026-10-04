# -*- coding: utf-8 -*-
"""n1_span_artefact_tests.py ——在册条目的"跨度是不是伪影"零新跑检验（N1 / N1b）。

**只读**：不改任何既有文件；只新建本脚本与其产物 JSON。

## 三个检验（全部只用**已发布逐项记录**重算，不转录任何数）
N1   —— 把相对偏差 ρ 换成**无量纲**量，重算 36 单元跨度并重排：
        (i)  ρ（纸面口径，复现闸门用）
        (ii) L = median( ln(pred+1) − ln(gt+1) )（在册条目逐字给出的变换）
        (iii) R = 逐项 **Spearman(pred, gt)**（我另加：对 pred/gt 的任意单调重标定都完全不变，
             是"绝对数值尺度伪影"这一质疑的**最强形式**，比 L 更彻底）
       判据（在册条目给）：Spearman(ρ 序, L 序) **≥ 0.85** ⇒ 该质疑被排除。
N1b-1 —— **GT 分层配对**：把各单元按 GT 计数分布配对到同一剖面后重算 ρ 跨度并重排，
       判据（在册条目给）：Spearman 相对全集的**降幅 > 0.2** ⇒ 跨度是 GT 口径伪影。
N1b-2 —— **有符号绝对计数误差**取代 ρ（median 与 mean 两种），报与 ρ 序的 Spearman。
外加 —— 随机删档（k=4，不放回）保留率：中位 / 5 分位 / 最小（第三家要的"每个跨度都该带"）。

## 单元构建
逐字复制 `a39_unit_calib_heldout.py` 的载入器与资格规则（档位 ≥3 且各档 item 交集 ≥20），
因此单元集与 `equalcount36_result.json` 同源，**可逐单元对冻结跨度做复现闸门**。
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
import collections
import csv
import glob
import hashlib
import io
import itertools
import json
import math
import os
import random
import re
import statistics as st
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
PM = RP('analysis', 'data', 'pod_mirror')
W = NR('@shared', 'work')
B = NR('@shared', 'work', 'b_harvest_20260917')
WORK = RP('analysis', 'work')
REF = RP('analysis', 'work', 'equalcount36_result.json')
OUT = RP('analysis', 'work', 'n1_span_artefact_result.json')
ANOM, SENT = 1e5, 1234567890
MIN_ITEMS = 20
K_DROP = 4
NDRAW = 2000
SEED = 20260924

FILES = []          # (role, path) —— 供 md5 清单


def load(p):
    FILES.append(p)
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


def add_unit(name, bylevel):
    lv = sorted(bylevel)
    if len(lv) < 3:
        return
    common = set.intersection(*[set(bylevel[s]) for s in lv])
    if len(common) < MIN_ITEMS:
        return
    ks = sorted(common)
    UNITS[name] = dict(levels=[(s, bylevel[s]) for s in lv], keys=ks)


def build_units():
    for lab, path, pcol in (
            ('det·in-domain/VisDrone', RP('analysis', 'data', 'pod_mirror', 'A', 'det_yolo_ladder_visdrone_det.csv'), 'n_det_person'),
            ('det·zero-shot COCO', RP('analysis', 'data', 'pod_mirror', 'A', 'det_yolo_ladder_yolo12n.csv'), 'n_det_person'),
            ('det·in-domain(micro)/BBBC005', NR('@shared', 'work', 'b_harvest_20260917', 'bbbc_eval', 'ladder.csv'), 'n_det')):
        if not os.path.exists(path):
            continue
        u = unitize(load(path), ['tau', 'imgsz'], pcol)
        add_unit(lab + ' (full grid)', dict(u))
        for sz in sorted({k[1] for k in u if len(k) > 1}):
            add_unit('%s / tau@%s' % (lab, sz), {k: v for k, v in u.items() if len(k) > 1 and k[1] == sz})

    p = NR('@shared', 'work', 'dm_ladder.csv')
    if os.path.exists(p):
        u = unitize(load(p), ['dataset', 'protocol', 'value'], 'pred')
        for ds in sorted({k[0] for k in u}):
            add_unit('density·official DM-Count / %s' % ds, {k: v for k, v in u.items() if k[0] == ds})
    for lab, path in (('density·CSRNet', RP('analysis', 'data', 'pod_mirror', 'A', 'csrsta_ladder_st_a.csv')),
                      ('density·CSRNet', RP('analysis', 'data', 'pod_mirror', 'A', 'csrucf_ladder_ucf.csv'))):
        if os.path.exists(path):
            u = unitize(load(path), ['protocol', 'value'], 'pred')
            add_unit('%s / %s' % (lab, os.path.basename(path).split('_')[-2]), dict(u))

    for mdl in ('ivl', 'q32'):
        for f in sorted(glob.glob(os.path.join(RP('analysis', 'data', 'pod_mirror'), 'res_ctrl__%s' % mdl, 'res_ctrl_*.csv'))):
            ds = os.path.basename(f)[len('res_ctrl_'):-4]
            u = unitize(load(f), ['budget'], 'pred')
            add_unit('VLM·pixel budget / %s / %s' % (mdl, ds), dict(u))

    for sub, mdl in (('tile_results', 'Qwen32B'), ('b2__out_32b_ctile', 'Qwen32B(ctile)'),
                     ('b2__out_8b_ctile', 'Qwen8B(ctile)')):
        d = os.path.join(RP('analysis', 'data', 'pod_mirror'), sub)
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

    for mdl, p in (('ivl', RP('analysis', 'data', 'pod_mirror', 'b2__out_ivl', 'E1.csv')),
                   ('q32', RP('analysis', 'data', 'pod_mirror', 'b2__out_q32', 'E1.csv'))):
        if os.path.exists(p):
            u = unitize(load(p), ['arm'], 'pred')
            add_unit('VLM·output contract / %s' % mdl, dict(u))

    for sub, mdl in (('dense_prompt_results', 'Qwen32B'), ('ivl_dense_prompt_results', 'IVL')):
        d = os.path.join(RP('analysis', 'data', 'pod_mirror'), sub)
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


# ---------------- 统计量 ----------------
def stat_rho(pairs):
    sg = sum(g for g, _ in pairs)
    return 100.0 * (sum(p for _, p in pairs) - sg) / sg if sg else None


def stat_L(pairs):
    v = [math.log(p + 1.0) - math.log(g + 1.0) for g, p in pairs]
    return st.median(v) if v else None


def stat_abs_med(pairs):
    v = [p - g for g, p in pairs]
    return st.median(v) if v else None


def stat_abs_mean(pairs):
    v = [p - g for g, p in pairs]
    return sum(v) / len(v) if v else None


def _rank(v):
    s = sorted(range(len(v)), key=lambda i: v[i])
    r = [0.0] * len(v)
    i = 0
    while i < len(s):
        j = i
        while j + 1 < len(s) and v[s[j + 1]] == v[s[i]]:
            j += 1
        avg = (i + j) / 2.0 + 1
        for t in range(i, j + 1):
            r[s[t]] = avg
        i = j + 1
    return r


def spearman(x, y):
    if len(x) < 3:
        return float('nan')
    ra, rb = _rank(x), _rank(y)
    n = len(x)
    ma, mb = sum(ra) / n, sum(rb) / n
    num = sum((ra[i] - ma) * (rb[i] - mb) for i in range(n))
    da = sum((ra[i] - ma) ** 2 for i in range(n)) ** 0.5
    db = sum((rb[i] - mb) ** 2 for i in range(n)) ** 0.5
    return num / (da * db) if da and db else float('nan')


def stat_rankcorr(pairs):
    if len(pairs) < 3:
        return None
    g = [x[0] for x in pairs]
    p = [x[1] for x in pairs]
    s = spearman(p, g)
    return None if (s != s) else s


STATS = [('rho', stat_rho), ('L', stat_L), ('rankcorr', stat_rankcorr),
         ('abs_med', stat_abs_med), ('abs_mean', stat_abs_mean)]


def span_under(unit, keys, fnstat):
    seq = []
    for _, d in UNITS[unit]['levels']:
        pr = [d[k] for k in keys]
        v = fnstat(pr)
        if v is None or v != v:
            return None
        seq.append(v)
    return max(seq) - min(seq)


def md5(p):
    return hashlib.md5(io.open(p, 'rb').read()).hexdigest()


def main():
    build_units()
    units = sorted(UNITS)
    print('=' * 112)
    print('■ N1：单元集（逐字复制 a39 载入器与资格规则：档位 ≥3 且各档交集 ≥%d）' % MIN_ITEMS)
    print('=' * 112)
    print('  建成 %d 个单元' % len(units))

    ref = json.load(io.open(REF, encoding='utf-8'))
    refmap = {u['unit']: u for u in ref['units']}
    print('  冻结件 equalcount36_result.json（md5 %s）有 %d 个单元' % (md5(REF)[:12], len(refmap)))
    only_mine = sorted(set(units) - set(refmap))
    only_ref = sorted(set(refmap) - set(units))
    print('  仅在本次：%s' % (only_mine or '无'))
    print('  仅在冻结件：%s' % (only_ref or '无'))
    both = [u for u in units if u in refmap]

    spans = {name: {} for name, _ in STATS}
    for u in both:
        for name, f in STATS:
            spans[name][u] = span_under(u, UNITS[u]['keys'], f)

    # ---- 复现闸门：ρ 跨度 vs 冻结件
    d = [abs(spans['rho'][u] - refmap[u]['span']) for u in both]
    print('\n  【复现闸门】本次 ρ 跨度 vs 冻结件 span：n=%d ｜ max|Δ| = %.6g ｜ 中位|Δ| = %.3g'
          % (len(d), max(d), st.median(d)))
    bad = [(u, spans['rho'][u], refmap[u]['span']) for u in both
           if abs(spans['rho'][u] - refmap[u]['span']) > 1e-6]
    print('  >1e-6 的单元：%s' % ([b[0] for b in bad] or '无'))

    print()
    print('=' * 112)
    print('■ N1 结果：三个口径的 36 单元跨度与排序')
    print('=' * 112)
    print('  %-48s %10s %10s %10s' % ('unit', 'rho(pp)', 'L(log)', 'R(rank)'))
    for u in sorted(both, key=lambda x: -(spans['rho'][x] or -1)):
        print('  %-48s %10.3f %10.4f %10.4f'
              % (u[:48], spans['rho'][u], spans['L'][u] if spans['L'][u] is not None else float('nan'),
                 spans['rankcorr'][u] if spans['rankcorr'][u] is not None else float('nan')))

    out = {'unit_set': 'a39 per-item sources, rebuilt verbatim', 'n_units': len(both),
           'replication_gate': {'ref': os.path.basename(REF), 'ref_md5': md5(REF),
                                'max_abs_delta': max(d), 'median_abs_delta': st.median(d),
                                'mismatches': [b[0] for b in bad]},
           'spans': spans, 'n1': {}, 'n1b': {}}

    print()
    for other, thresh, label in (('L', 0.85, '评审逐字变换 L = median(ln(pred+1)-ln(gt+1))'),
                                 ('rankcorr', 0.85, '我另加的最强形式：逐项 Spearman(pred, gt)')):
        ok = [u for u in both if spans[other][u] is not None]
        s = spearman([spans['rho'][u] for u in ok], [spans[other][u] for u in ok])
        top_rho = max(both, key=lambda u: spans['rho'][u])
        top_o = max(ok, key=lambda u: spans[other][u])
        bot_rho = sorted(both, key=lambda u: spans['rho'][u])[:6]
        bot_o = sorted(ok, key=lambda u: spans[other][u])[:6]
        budget = [u for u in both if 'pixel budget' in u]
        br = sorted(budget, key=lambda u: spans['rho'][u])
        bo = sorted(budget, key=lambda u: spans[other][u])
        rank_of_budget_rho = [sorted(both, key=lambda u: -spans['rho'][u]).index(u) + 1 for u in budget]
        rank_of_budget_o = [sorted(ok, key=lambda u: -spans[other][u]).index(u) + 1 for u in budget]
        ratio = {}
        for u in ok:
            if spans['rho'][u]:
                ratio[u] = spans[other][u] / spans['rho'][u]
        rv = sorted(ratio.values())
        print('  ── %s' % label)
        print('     Spearman(ρ 序, %s 序) = **%.3f**（判据 ≥%.2f ⇒ %s）｜ 可比单元 %d/%d'
              % (other, s, thresh, '排除该质疑' if s >= thresh else '**未达标**', len(ok), len(both)))
        print('     最高位：ρ = %s ｜ %s = %s ｜ %s'
              % (top_rho[:44], other, top_o[:44], '同一条' if top_rho == top_o else '**不同**'))
        print('     最低 6 条重合数：%d/6' % len(set(bot_rho) & set(bot_o)))
        print('     像素预算单元：ρ 序位次 %s ｜ %s 序位次 %s（共 %d 条）'
              % (rank_of_budget_rho, other, rank_of_budget_o, len(both)))
        print('     逐单元跨度比 %s/ρ：中位 %.4g ｜ min %.4g ｜ max %.4g'
              % (other, st.median(rv), rv[0], rv[-1]))
        out['n1'][other] = {'spearman_vs_rho': s, 'threshold': thresh, 'pass': bool(s >= thresh),
                            'n_units': len(ok), 'top_rho': top_rho, 'top_other': top_o,
                            'top_same': top_rho == top_o,
                            'bottom6_overlap': len(set(bot_rho) & set(bot_o)),
                            'budget_ranks_rho': rank_of_budget_rho,
                            'budget_ranks_other': rank_of_budget_o,
                            'span_ratio_median': st.median(rv), 'span_ratio_min': rv[0],
                            'span_ratio_max': rv[-1]}
        print()

    # ---------------- N1b-2 有符号绝对计数误差 ----------------
    print('=' * 112)
    print('■ N1b-2：有符号**绝对计数误差**取代 ρ')
    print('=' * 112)
    for other, label in (('abs_med', 'median(pred − gt)'), ('abs_mean', 'mean(pred − gt)')):
        ok = [u for u in both if spans[other][u] is not None]
        s = spearman([spans['rho'][u] for u in ok], [spans[other][u] for u in ok])
        top_rho = max(both, key=lambda u: spans['rho'][u])
        top_o = max(ok, key=lambda u: spans[other][u])
        print('  %-22s Spearman(ρ 序, 本序) = **%.3f**（n=%d）｜ 最高位：ρ=%s ｜ 本=%s'
              % (label, s, len(ok), top_rho[:40], top_o[:40]))
        out['n1b'][other] = {'spearman_vs_rho': s, 'n_units': len(ok),
                             'top_rho': top_rho, 'top_other': top_o}
    print()

    # ---------------- N1b-1 GT 分层配对 ----------------
    print('=' * 112)
    print('■ N1b-1：GT 分层配对（把各单元按 GT 计数分布配到同一剖面后重算 ρ 跨度）')
    print('=' * 112)
    BINS = [(1, 5), (5, 20), (20, 50), (50, 100), (100, 200), (200, 500), (500, 10 ** 9)]

    def profile(u, keys):
        c = [0] * len(BINS)
        for k in keys:
            g = UNITS[u]['levels'][0][1][k][0]
            for i, (a, b) in enumerate(BINS):
                if a <= g < b:
                    c[i] += 1
                    break
        return c

    prof = {u: profile(u, UNITS[u]['keys']) for u in both}
    target = [min(prof[u][i] for u in both) for i in range(len(BINS))]
    print('  GT 分箱 %s' % (BINS,))
    print('  各单元在各箱的**最小值**（配对目标）= %s ｜ 合计 %d 项' % (target, sum(target)))

    rng = random.Random(SEED)
    matched = {u: [] for u in both}
    for u in both:
        avail = collections.defaultdict(list)
        for k in UNITS[u]['keys']:
            g = UNITS[u]['levels'][0][1][k][0]
            for i, (a, b) in enumerate(BINS):
                if a <= g < b:
                    avail[i].append(k)
                    break
        for i in range(len(BINS)):
            lst = sorted(avail[i])
            rng.shuffle(lst)
            matched[u].extend(lst[:target[i]])
        matched[u] = sorted(matched[u])
    nmin = min(len(matched[u]) for u in both)
    print('  配对后每个单元的 item 数：min %d ｜ median %d ｜ max %d'
          % (nmin, st.median([len(matched[u]) for u in both]), max(len(matched[u]) for u in both)))

    if nmin < MIN_ITEMS:
        print('  !! 配对后最小 item 数 %d < %d ⇒ **配对不可用**，本检验判为"released records 不支持等量配对"' % (nmin, MIN_ITEMS))
        out['n1b']['gt_stratified'] = {'computable': False, 'min_items_after_match': nmin}
    else:
        sp_m = {u: span_under(u, matched[u], stat_rho) for u in both}
        ok = [u for u in both if sp_m[u] is not None]
        s_full = spearman([spans['rho'][u] for u in ok], [sp_m[u] for u in ok])
        print('  Spearman(全集 ρ 序, 配对后 ρ 序) = **%.3f**（n=%d）' % (s_full, len(ok)))
        print('  ⇒ 降幅 = %.3f ｜ 判据：降幅 > 0.2 ⇒ GT 口径伪影'
              % (1 - s_full if s_full == s_full else float('nan')))
        order_f = sorted(ok, key=lambda u: -spans['rho'][u])
        order_m = sorted(ok, key=lambda u: -sp_m[u])
        print('  最高位：全集 %s ｜ 配对后 %s ｜ %s'
              % (order_f[0][:40], order_m[0][:40], '同一条' if order_f[0] == order_m[0] else '**不同**'))
        print('  前 6 名重合 %d/6 ｜ 末 6 名重合 %d/6'
              % (len(set(order_f[:6]) & set(order_m[:6])), len(set(order_f[-6:]) & set(order_m[-6:]))))
        out['n1b']['gt_stratified'] = {'computable': True, 'bins': BINS, 'target_per_bin': target,
                                       'min_items_after_match': nmin,
                                       'spearman_vs_full': s_full, 'drop': 1 - s_full,
                                       'threshold_drop': 0.2, 'artifact': bool(1 - s_full > 0.2),
                                       'top_full': order_f[0], 'top_matched': order_m[0],
                                       'spans_matched': sp_m}
    print()

    # ---------------- 随机删档保留率 ----------------
    print('=' * 112)
    print('■ 附：随机删档（k=%d，不放回）保留率 —— ρ 口径，全部 36 单元' % K_DROP)
    print('=' * 112)
    rng2 = random.Random(SEED)
    rows = []
    for u in both:
        seq = [stat_rho([d[k] for k in UNITS[u]['keys']]) for _, d in UNITS[u]['levels']]
        full = max(seq) - min(seq)
        n = len(seq)
        if n <= K_DROP or full == 0:
            rows.append((u, n, None, None, None))
            continue
        idxs = list(itertools.combinations(range(n), K_DROP))
        if len(idxs) > NDRAW:
            idxs = rng2.sample(idxs, NDRAW)
        rs = []
        for c in idxs:
            v = [seq[i] for i in c]
            rs.append((max(v) - min(v)) / full)
        rs.sort()
        rows.append((u, n, st.median(rs), rs[int(0.05 * (len(rs) - 1))], rs[0]))
        if abs(full - (max(seq) - min(seq))) > 1e-9:
            print('  (warn) %s span 复算不一致' % u)
    got = [r for r in rows if r[2] is not None]
    print('  可删档的单元 %d/%d（其余档位 ≤%d 或跨度为 0）' % (len(got), len(rows), K_DROP))
    if got:
        med = [r[2] for r in got]
        p5 = [r[3] for r in got]
        mn = [r[4] for r in got]
        print('  保留率：中位(的单元中位) %.3f ｜ 全局中位 %.3f ｜ 5 分位（单元级）中位 %.3f'
              % (st.median(med), st.median([x for r in got for x in (r[2],)]), st.median(p5)))
        print('  **5 分位最差** %.3f（%s）｜ **最小保留率** %.3f（%s）'
              % (min(p5), min(got, key=lambda r: r[3])[0][:44], min(mn), min(got, key=lambda r: r[4])[0][:44]))
        print('  最低 8 个单元的最小保留率：')
        for r in sorted(got, key=lambda r: r[4])[:8]:
            print('     %-50s n=%2d 中位 %.3f 5%% %.3f min %.3f' % (r[0][:50], r[1], r[2], r[3], r[4]))
        out['random_drop'] = {'k': K_DROP, 'ndraw': NDRAW, 'n_units': len(got),
                              'median_of_medians': st.median(med),
                              'median_of_p5': st.median(p5), 'worst_p5': min(p5), 'worst_min': min(mn),
                              'per_unit': {r[0]: {'n_levels': r[1], 'median': r[2], 'p5': r[3], 'min': r[4]}
                                           for r in rows}}

    # ---------------- 文件清单 ----------------
    inv = []
    for p in sorted(set(FILES)):
        inv.append({'path': p.replace(RP() + os.sep, '').replace('E:' + os.sep + 'Edu_workplace' + os.sep, 'E:' + os.sep * 2),
                    'md5': md5(p), 'n_bytes': os.path.getsize(p)})
    out['file_inventory'] = inv
    print()
    print('=' * 112)
    print('■ 输入逐项记录清单（%d 个文件，全部实测 md5）' % len(inv))
    print('=' * 112)
    for r in inv:
        print('  %-64s %s' % (r['path'][:64], r['md5']))
    io.open(OUT, 'w', encoding='utf-8').write(json.dumps(out, ensure_ascii=False, indent=1))
    print('\nJSON -> %s' % OUT)


if __name__ == '__main__':
    main()
