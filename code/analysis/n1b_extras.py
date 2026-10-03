# -*- coding: utf-8 -*-
"""n1b_extras.py —— N1/N1b 的**加做**部分（承上：`n1_span_artefact_tests.py`）。

承上结果：L 与 rankcorr 的 Spearman 都远低于[external-review]的 0.85；而 GT 分层的"最小剖面"配对
退化到 9 项（不可用）。本脚本回答三个跟进问题：

A. **低 Spearman 是不是"池化 → 逐项"这一轴造成的？**（而不是"量纲/尺度"这一轴）
   加一个 `rho_mean` = 逐项 (p−g)/g 的**均值**：它与池化 ρ 共享同一个函数形式、只换池化方式。
   若 Spearman(池化 ρ, 逐项均值 ρ) 很高，则说明低相关**不是**池化造成的。
B. **稳健性**：L / rankcorr 的 Spearman 在四个子集上各是多少（全集 / 剔除两个已退役复现 /
   只留档位 ≥4 / 两者都做）。
C. L 改用**各档自己的 item 集**（而非各档交集）重算，看结论是否依赖交集口径。
D. **GT 支持表**：每个单元的 GT 分布（min/中位/max + 分箱剖面）—— 用来说明为什么
   "绝对 GT 剖面的等量配对"在这 36 个单元上**不可行**（各单元的 GT 支持几乎不相交）。
E. **形状配对**（可行的替代）：每个单元按**自身** GT 的 5 等分箱各抽 q 项（q 取各单元最小箱容量），
   使各单元的 **GT 形状**一致，再重算 ρ 跨度与 Spearman。并如实说明它**不**消除绝对口径差。

只读；只新建本脚本与其产物 JSON。
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
import itertools
import json
import math
import os
import random
import statistics as st
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
import n1_span_artefact_tests as N   # noqa: E402

WORK = RP('analysis', 'work')
OUT = RP('analysis', 'work', 'n1b_extras_result.json')
SEED = 20260924
RETIRED = ['density·CSRNet / st', 'density·CSRNet / ladder']


def stat_rho_mean(pairs):
    v = [100.0 * (p - g) / g for g, p in pairs if g]
    return sum(v) / len(v) if v else None


def stat_rho_med(pairs):
    v = [100.0 * (p - g) / g for g, p in pairs if g]
    return st.median(v) if v else None


def span_own_levels(u, fnstat):
    """各档用**自己的** item 集（不做交集）。"""
    seq = []
    for _, d in N.UNITS[u]['levels']:
        v = fnstat(list(d.values()))
        if v is None or v != v:
            return None
        seq.append(v)
    return max(seq) - min(seq)


def main():
    N.build_units()
    units = sorted(N.UNITS)
    ref = json.load(open(N.REF, encoding='utf-8'))
    refmap = {x['unit']: x for x in ref['units']}
    both = [u for u in units if u in refmap]
    out = {}
    print('=' * 112)
    print('■ A. 诊断：低相关是"池化→逐项"造成的，还是"函数形式/量纲"造成的？')
    print('=' * 112)
    sp = {k: {} for k in ('rho', 'L', 'rankcorr', 'rho_mean', 'rho_med')}
    for u in both:
        for k, f in (('rho', N.stat_rho), ('L', N.stat_L), ('rankcorr', N.stat_rankcorr),
                     ('rho_mean', stat_rho_mean), ('rho_med', stat_rho_med)):
            sp[k][u] = N.span_under(u, N.UNITS[u]['keys'], f)
    a = N.spearman([sp['rho'][u] for u in both], [sp['rho_mean'][u] for u in both])
    b = N.spearman([sp['rho'][u] for u in both], [sp['rho_med'][u] for u in both])
    c = N.spearman([sp['rho_mean'][u] for u in both], [sp['L'][u] for u in both])
    d = N.spearman([sp['rho_mean'][u] for u in both], [sp['rankcorr'][u] for u in both])
    print('  Spearman(池化 ρ, 逐项均值 (p−g)/g)   = **%.3f**' % a)
    print('  Spearman(池化 ρ, 逐项中位 (p−g)/g)   = **%.3f**' % b)
    print('  Spearman(逐项均值 ρ, L)             = **%.3f**' % c)
    print('  Spearman(逐项均值 ρ, rankcorr)      = **%.3f**' % d)
    print('  ⇒ 若第一行很高而第三/四行很低，则低相关来自**函数形式（log/秩）**这一轴，')
    print('    不是"池化 vs 逐项"这一轴；反之则池化本身是主因。')
    out['A_pooling_diagnostic'] = {'spearman_pooled_vs_itemmean': a, 'spearman_pooled_vs_itemmedian': b,
                                   'spearman_itemmean_vs_L': c, 'spearman_itemmean_vs_rankcorr': d}

    print()
    print('=' * 112)
    print('■ B. 稳健性：四个子集上 L / rankcorr 的 Spearman')
    print('=' * 112)
    nlevel = {u: len(N.UNITS[u]['levels']) for u in both}
    subsets = {
        '全部 36': both,
        '剔除 2 个已退役复现(D=34)': [u for u in both if u not in RETIRED],
        '只留档位 ≥4(N=31)': [u for u in both if nlevel[u] >= 4],
        '两者都做': [u for u in both if u not in RETIRED and nlevel[u] >= 4],
    }
    for name, sub in subsets.items():
        row = {}
        for k in ('L', 'rankcorr'):
            s = N.spearman([sp['rho'][u] for u in sub], [sp[k][u] for u in sub])
            row[k] = s
        top_rho = max(sub, key=lambda u: sp['rho'][u])
        topL = max(sub, key=lambda u: sp['L'][u])
        topR = max(sub, key=lambda u: sp['rankcorr'][u])
        print('  %-26s n=%2d ｜ Spearman(ρ,L)=%.3f ｜ Spearman(ρ,R)=%.3f ｜ top: ρ=%s ｜ L=%s ｜ R=%s'
              % (name, len(sub), row['L'], row['rankcorr'], top_rho[:26], topL[:26], topR[:26]))
        out.setdefault('B_robustness', {})[name] = {'n': len(sub), **row,
                                                    'top_rho': top_rho, 'top_L': topL, 'top_R': topR}
    print('  （评审判据 0.85）')

    print()
    print('=' * 112)
    print('■ C. L 改用各档**自己的** item 集（不取交集）')
    print('=' * 112)
    spL_own = {u: span_own_levels(u, N.stat_L) for u in both}
    spR_own = {u: span_own_levels(u, N.stat_rankcorr) for u in both}
    okL = [u for u in both if spL_own[u] is not None]
    okR = [u for u in both if spR_own[u] is not None]
    sL = N.spearman([sp['rho'][u] for u in okL], [spL_own[u] for u in okL])
    sR = N.spearman([sp['rho'][u] for u in okR], [spR_own[u] for u in okR])
    print('  Spearman(ρ 序, L_own 序)       = **%.3f**（n=%d）' % (sL, len(okL)))
    print('  Spearman(ρ 序, rankcorr_own 序) = **%.3f**（n=%d）' % (sR, len(okR)))
    print('  ⇒ 与交集口径相比：L %.3f→%.3f ｜ R %.3f→%.3f ⇒ %s'
          % (out['A_pooling_diagnostic'].get('x', float('nan')), sL, float('nan'), sR,
             '口径不敏感' if abs(sL - 0.629) < 0.05 and abs(sR - 0.595) < 0.05 else '**口径敏感**'))
    out['C_own_levels'] = {'spearman_L_own': sL, 'n_L': len(okL),
                           'spearman_rankcorr_own': sR, 'n_R': len(okR)}

    print()
    print('=' * 112)
    print('■ D. GT 支持表：为什么"绝对 GT 剖面的等量配对"在 36 单元上不可行')
    print('=' * 112)
    BINS = [(1, 5), (5, 20), (20, 50), (50, 100), (100, 200), (200, 500), (500, 10 ** 9)]
    prof, gts = {}, {}
    for u in both:
        g = [N.UNITS[u]['levels'][0][1][k][0] for k in N.UNITS[u]['keys']]
        gts[u] = (min(g), st.median(g), max(g))
        c = [0] * len(BINS)
        for x in g:
            for i, (a, b) in enumerate(BINS):
                if a <= x < b:
                    c[i] += 1
                    break
        prof[u] = c
    print('  %-46s %6s %6s %6s ｜ 分箱剖面 %s' % ('unit', 'gt_min', 'gt_med', 'gt_max', ' '.join('%d-%d' % b for b in BINS[:5])))
    for u in sorted(both, key=lambda x: gts[x][1]):
        print('  %-46s %6.0f %6.0f %6.0f ｜ %s'
              % (u[:46], gts[u][0], gts[u][1], gts[u][2], ' '.join('%4d' % x for x in prof[u][:5])))
    target = [min(prof[u][i] for u in both) for i in range(len(BINS))]
    print('  「最小剖面」目标 = %s ⇒ 合计 **%d** 项 ⇒ 等量绝对 GT 配对**不可行**（<20 的最小单元资格）'
          % (target, sum(target)))
    out['D_gt_support'] = {'bins': BINS, 'min_profile_target': target,
                           'gt_min_med_max': {u: gts[u] for u in both}, 'profile': prof,
                           'absolute_matching_feasible': sum(target) >= 20}

    print()
    print('=' * 112)
    print('■ E. 形状配对（可行替代）：各单元按**自身** GT 的 5 等分箱各抽 q 项')
    print('=' * 112)
    NB = 5
    cells = {}
    for u in both:
        g = sorted((N.UNITS[u]['levels'][0][1][k][0], k) for k in N.UNITS[u]['keys'])
        n = len(g)
        b = [g[int(round(i * (n - 1) / NB))][0] for i in range(NB + 1)]
        buckets = [[] for _ in range(NB)]
        for x, k in g:
            i = 0
            while i < NB - 1 and x >= b[i + 1]:
                i += 1
            buckets[i].append(k)
        cells[u] = buckets
    q = min(min(len(c) for c in cells[u]) for u in both)
    print('  5 等分箱 × q 项，q = 各单元最小箱容量 = **%d** ⇒ 每单元配对后 %d 项' % (q, NB * q))
    if q * NB < 20:
        print('  !! %d < 20 ⇒ 形状配对同样**不可用**' % (q * NB))
        out['E_shape_matched'] = {'feasible': False, 'q': q, 'items_per_unit': NB * q}
    else:
        rng = random.Random(SEED)
        matched = {}
        for u in both:
            ks = []
            for c in cells[u]:
                c = sorted(c)
                rng.shuffle(c)
                ks.extend(c[:q])
            matched[u] = sorted(ks)
        spm = {u: N.span_under(u, matched[u], N.stat_rho) for u in both}
        ok = [u for u in both if spm[u] is not None]
        s = N.spearman([sp['rho'][u] for u in ok], [spm[u] for u in ok])
        drop = 1 - s
        of = sorted(ok, key=lambda u: -sp['rho'][u])
        om = sorted(ok, key=lambda u: -spm[u])
        print('  Spearman(全集 ρ 序, 形状配对后 ρ 序) = **%.3f** ｜ 降幅 %.3f ｜ 判据：降幅 > 0.2 ⇒ GT 口径伪影'
              % (s, drop))
        print('  最高位：全集 %s ｜ 配对后 %s ｜ %s'
              % (of[0][:40], om[0][:40], '同一条' if of[0] == om[0] else '**不同**'))
        print('  前 6 名重合 %d/6 ｜ 末 6 名重合 %d/6'
              % (len(set(of[:6]) & set(om[:6])), len(set(of[-6:]) & set(om[-6:]))))
        print('  ⚠ 形状配对只统一 **GT 分布的相对形状**；各单元的**绝对** GT 口径仍然不同，')
        print('    故它**不能**排除"绝对 GT 计数口径"这一解释，只能排除"GT 分布形状"这一支。')
        out['E_shape_matched'] = {'feasible': True, 'q': q, 'items_per_unit': NB * q,
                                  'spearman_vs_full': s, 'drop': drop, 'threshold_drop': 0.2,
                                  'artifact_shape': bool(drop > 0.2), 'top_full': of[0], 'top_matched': om[0],
                                  'spans_matched': spm}

    # 像素预算与顶端单元在各口径下的位次（供报告）
    rk = {}
    for k in ('rho', 'L', 'rankcorr', 'rho_mean'):
        order = sorted([u for u in both if sp[k][u] is not None], key=lambda u: -sp[k][u])
        rk[k] = {u: order.index(u) + 1 for u in order}
    out['ranks'] = rk
    print()
    print('  像素预算 6 单元在四个口径下的位次：')
    for u in [x for x in both if 'pixel budget' in x]:
        print('    %-44s ρ %2d ｜ L %2d ｜ R %2d ｜ 逐项均值ρ %2d'
              % (u[:44], rk['rho'][u], rk['L'][u], rk['rankcorr'][u], rk['rho_mean'][u]))
    open(OUT, 'w', encoding='utf-8').write(json.dumps(out, ensure_ascii=False, indent=1))
    print('\nJSON -> %s' % OUT)


if __name__ == '__main__':
    main()
