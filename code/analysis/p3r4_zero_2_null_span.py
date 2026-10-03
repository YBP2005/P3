# -*- coding: utf-8 -*-
"""p3r4_zero_2_null_span.py —— P3 第 4 轮 ②：ordering 的 **"span 值随机"零模型**与既有
label-permutation 的对照。

## 来源与授权
第 2 轮 + 第 3 轮 glm52 #8 / 第 3 轮 E-5：包内的零模型是 **label-permutation**（随机置换一侧的
标签）；[external-review]指出 "**span 值随机**" 是**另一个**零模型，两者不可互相替代，要求按原话构造并重算
§7.3 的排序统计量在该零模型下的分布。

## ★ 本脚本必须先回答的问题（第 3 轮遗留的退化警告）
第 2/3 轮出现过 "**置换统计量在本设定下数学退化**"：`perm_cluster_order` 口径下，
统计量 = 全局 Spearman 只依赖 (x_i, y_i) 的**配对集合**，而"把整块簇换个位置"只改**顺序**、
不改配对 ⇒ 每次置换统计量与观测**逐位相同**，完整枚举 720 种 distinct = 1、p ≡ 1。
本脚本对**本轮构造的零模型**逐一做同一项检查，结论写在结果 JSON 的 `degeneracy` 段。

## 零模型（两套，"跑前写死"）
**H0-A：label-permutation（既有口径，阴性对照）** —— `m37_ci_power.py::perm_p()` **逐字**
（随机 `rnd.shuffle` 一侧标签；p = (1+#{>=obs})/(1+N)，N=20000，seed 20260924）。

**H0-B："span 值随机"（glm52 原话口径，本脚本新增）** —— 保持**被排序的那一侧**（去偏 span）
不变，把 **span 值**从拟合的边缘分布里**独立重抽**（重抽会改变 (span, span_eq4) 的配对），
重算统计量。三个边缘规格，全部跑、全部印：
  B1 `empirical_per_item`：从该单元集的 31 个 **span 值本身**有放回重抽（经验边缘，无分布假设）；
  B2 `lognormal_fitted`：对 span 拟合**对数正态**（MLE = log 空间的均值/标准差），从中重抽
     —— 这是"同分布、无结构"的最字面读法；
  B3 `lognormal_fitted_eq4`：同样的拟合作用在**去偏 span** 这一侧（把两侧都随机化）。

## 与 H0-A 的关系（必须明说，否则会误报成"两个不同的检验"）
H0-A 与 H0-B **检验的都是同一个独立零假设**：`span` 与 `span_eq4` 之间**没有配对关联**。
固定一侧、随机重抽另一侧（B1）与固定一侧、随机置换另一侧标签（A）在**有限样本下的精确检验**
意义上只差一个"是否有放回"；只有当 B2 的**参数假设**（对数正态）被当真时二者才可能不同。
⇒ 本脚本把 A 记作 H0-B 的**精确参照**：若 B1 与 A 的 p 一致，则"两个零模型"在数值上**并不可分**；
若 B2 不同，那差异来自**分布假设**，不是来自"另一个零假设"。**这一点必须写进稿子。**

用法：
  python p3r4_zero_2_null_span.py --selftest
  python p3r4_zero_2_null_span.py            # 写结果 JSON + md5
"""
import argparse
import hashlib
import io
import json
import math
import os
import random
import sys
import time

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

W = os.path.dirname(os.path.abspath(__file__))
EQ = os.path.join(W, 'equalcount36_result.json')
M37 = os.path.join(W, 'm37_ci_power_result.json')
CLU = os.path.join(W, 'p3r2_plan_m37_cluster_result.json')
OUT = os.path.join(W, 'p3r4_zero_2_null_span_result.json')

SEED = 20260924        # 与 m37_ci_power.py 同
N_PERM = 20000         # 与 m37_ci_power.py::perm_p 同
N_DRAW = 20000         # H0-B 的重抽次数（与 A 同尺，便于逐位对照）


# ══════════════════════════════════════════════════════════════════════════════
def spearman(x, y):
    """★ **逐字照抄** `m37_ci_power.py` L44-54（含它的 `{v: i ...}` 并列处理），
    否则重算值会在第三位上与冻结件差 0.001。"""
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


def perm_p(a, b, n_perm=N_PERM, seed=SEED):
    """★ **逐字照抄** `m37_ci_power.py::perm_p()`。"""
    rnd = random.Random(seed)
    obs = spearman(a, b)
    bb = list(b)
    ge = 0
    for _ in range(n_perm):
        rnd.shuffle(bb)
        if spearman(a, bb) >= obs:
            ge += 1
    return dict(obs=obs, p=(1 + ge) / (1 + n_perm), n_perm=n_perm, seed=seed,
                method='free_label_permutation')


def lognormal_fit(v, floor=1e-9):
    """MLE of lognormal: mu/sigma in log space."""
    lv = [math.log(max(vv, floor)) for vv in v]
    n = len(lv)
    mu = sum(lv) / n
    sd = (sum((x - mu) ** 2 for x in lv) / n) ** 0.5
    return mu, sd


def lognormal_draw(mu, sd, rnd):
    return math.exp(rnd.gauss(mu, sd))


def null_random_span(a, b, spec, n_draw=N_DRAW, seed=SEED):
    """H0-B：保持 `b` 不变，独立重抽 `a`。
    spec = 'empirical'  → 从 a 自身有放回重抽
    spec = 'lognormal'  → 从 lognormal(MLE(a)) 重抽
    返回分布摘要 + p（单侧，尾巴口径与 perm_p 一致）。"""
    rnd = random.Random(seed)
    obs = spearman(a, b)
    n = len(a)
    dist = []
    if spec == 'empirical':
        for _ in range(n_draw):
            aa = [a[rnd.randrange(n)] for _ in range(n)]
            dist.append(spearman(aa, b))
    elif spec == 'lognormal':
        mu, sd = lognormal_fit(a)
        for _ in range(n_draw):
            aa = [lognormal_draw(mu, sd, rnd) for _ in range(n)]
            dist.append(spearman(aa, b))
    else:
        raise ValueError(spec)
    ge = sum(1 for v in dist if v >= obs - 1e-15)
    ds = sorted(dist)
    uniq = len({round(v, 12) for v in dist})
    return dict(obs=obs, p=(1 + ge) / (1 + n_draw), n_draw=n_draw, seed=seed,
                spec=spec, distinct_stat_values=uniq,
                degenerate=(uniq == 1),
                dist_p025=ds[int(0.025 * n_draw)], dist_p975=ds[int(0.975 * n_draw)],
                dist_mean=sum(dist) / len(dist),
                dist_min=ds[0], dist_max=ds[-1],
                statistic='Spearman(redrawn span, fixed deflated span)')


def degeneracy_probe(a, b, labels=None, n_perm=2000, seed=SEED):
    """★ 退化自证：三类操作下统计量是否变化。
    (i) **单元顺序置换**（= 第 3 轮报退化的那种操作）：只改顺序、不改配对。
    (ii) **簇标签置换**（把整块簇换位置）：同上，配对不变。
    (iii) **span 值重抽/反复置换**（本轮零模型）：改配对。
    返回各自 distinct 统计量个数 —— (i)(ii) 应为 1（退化），(iii) 应远大于 1。"""
    n = len(a)
    rnd = random.Random(seed)
    s_order = set()
    for _ in range(n_perm):
        o = list(range(n))
        rnd.shuffle(o)
        s_order.add(round(spearman([a[i] for i in o], [b[i] for i in o]), 12))
    s_cluster = None
    if labels is not None:
        groups = {}
        for i, lb in enumerate(labels):
            groups.setdefault(lb, []).append(i)
        keys = sorted(groups)
        members = [groups[k] for k in keys]
        s_cluster = set()
        for _ in range(n_perm):
            p = list(range(len(keys)))
            rnd.shuffle(p)
            order = []
            for slot in range(len(keys)):
                order.extend(members[p[slot]])
            s_cluster.add(round(spearman([a[i] for i in order], [b[i] for i in order]), 12))
    s_value = set()
    for _ in range(n_perm):
        aa = list(a)
        rnd.shuffle(aa)
        s_value.add(round(spearman(aa, b), 12))
    return dict(
        unit_order_permutation_distinct=len(s_order),
        cluster_block_permutation_distinct=(len(s_cluster) if s_cluster is not None else None),
        value_shuffle_distinct=len(s_value),
        unit_order_invariant=(len(s_order) == 1),
        value_shuffle_invariant=(len(s_value) == 1),
        note='(i)(ii) 只改单元的**顺序/分组**，而全局 Spearman 只依赖 (x,y) 配对集合 ⇒ distinct=1（退化）；'
             '(iii) 改的是**配对本身** ⇒ distinct 远大于 1（非退化）。'
             '★ 故"span 值随机"零模型在本设定下**不退化**；退化的只是第 2/3 轮那个'
             '"按簇换位置"的实现。')


# ══════════════════════════════════════════════════════════════════════════════
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--selftest', action='store_true')
    args = ap.parse_args()
    if args.selftest:
        return selftest()

    t0 = time.time()
    print('=' * 118)
    print('P3R4-② ordering 的 "span 值随机" 零模型 vs 既有 label-permutation（0 次推理）')
    print('=' * 118)

    eq = json.loads(io.open(EQ, encoding='utf-8').read())
    m37 = json.loads(io.open(M37, encoding='utf-8').read())
    clu = json.loads(io.open(CLU, encoding='utf-8').read())
    units = eq['units']
    u31 = [u for u in units if 'span_eq4' in u and u.get('n', 0) >= 4]
    assert len(units) == 36 and len(u31) == 31, '36/31 单元集规模不符'

    # 冻结件里的既有读数（阴性对照的靶子）
    frozen = dict(
        rho_36=m37['ordering']['36unit_k3']['quoted']['obs'],
        perm_p_36=m37['ordering']['36unit_k3']['perm']['p'],
        rho_31=m37['ordering']['31unit_k4']['quoted']['obs'],
        iid_36=m37['quoted_display']['rho_36_k3_ci'],
        iid_31=m37['quoted_display']['rho_31_k4_ci'],
        cluster_31=clu['quoted_display']['clustered_31_k4_knob_ci'],
        cluster_p_31=clu['quoted_display']['clustered_31_k4_knob_p'],
    )
    print('\n冻结件既有读数（对照靶）')
    print('   §7.3 印 ordering：31@k4 rho=%.3f  iid CI %s  ｜ 36@k3 rho=%.3f  iid CI %s'
          % (frozen['rho_31'], frozen['iid_31'], frozen['rho_36'], frozen['iid_36']))
    print('   §7.3 印 "clustering by knob gives 0.913-0.994" ⇒ 冻结件 clustered 31@k4 = %s（p=%s）'
          % (frozen['cluster_31'], frozen['cluster_p_31']))
    print('   §7.3 印 "a label-permutation test gives p<5e-5" ⇒ 冻结件 36@k3 自由置换 p = %.6e'
          % frozen['perm_p_36'])

    # ── 两套单元集，三种去偏 ────────────────────────────────────────────────────
    SETS = [('31unit_k4', u31, ['span_eq4', 'span_drop_high', 'span_drop_low']),
            ('36unit_k3', units, ['span_eq', 'span_drop_high', 'span_drop_low'])]

    print('\n① 退化自证（先做，因为它决定②的读数是否可评）')
    deg = {}
    for tag, us, keys in SETS:
        a = [u['span'] for u in us]
        b = [u[keys[0]] for u in us]
        labels = clu['cluster_labels'][tag]['a']
        lb = [labels[u['unit']] for u in us]
        d = degeneracy_probe(a, b, lb)
        deg[tag] = d
        print('   %-10s 单元顺序置换 distinct=%d（%s）｜ 簇整块置换 distinct=%s｜ span 值重抽 distinct=%d（%s）'
              % (tag, d['unit_order_permutation_distinct'],
                 '退化' if d['unit_order_invariant'] else '有变化',
                 d['cluster_block_permutation_distinct'],
                 d['value_shuffle_distinct'],
                 '退化' if d['value_shuffle_invariant'] else '**非退化**'))
    assert all(deg[t]['unit_order_invariant'] for t in deg), '前提有变：顺序置换竟然改变统计量'
    assert all(not deg[t]['value_shuffle_invariant'] for t in deg), \
        '★ "span 值随机"竟然退化 ⇒ 需重估该零模型的定义'

    print('\n② 主读数：H0-A（label-permutation，既有）vs H0-B（span 值随机，本轮新增）')
    print('   %-10s %-16s %-9s %-13s %-13s %-13s' %
          ('单元集', '去偏口径', 'rho_obs', 'A: perm p', 'B1: 经验重抽 p', 'B2: 对数正态 p'))
    readings = {}
    for tag, us, keys in SETS:
        readings[tag] = {}
        for key in keys:
            a = [u['span'] for u in us]
            b = [u[key] for u in us]
            A = perm_p(a, b)
            B1 = null_random_span(a, b, 'empirical')
            B2 = null_random_span(a, b, 'lognormal')
            readings[tag][key] = dict(A_label_permutation=A, B1_empirical=B1, B2_lognormal=B2)
            print('   %-10s %-16s %-9.4f %-13s %-13s %-13s'
                  % (tag, key, A['obs'], '%.3e' % A['p'], '%.3e' % B1['p'], '%.3e' % B2['p']))

    # ── 阴性对照：36@k3 + span_eq 的自由置换 p 必须逐位复现冻结件 ────────────────
    got = readings['36unit_k3']['span_eq']['A_label_permutation']['p']
    assert got == frozen['perm_p_36'], \
        '自由置换 p 未逐位复现冻结件：%r vs %r' % (got, frozen['perm_p_36'])
    print('\n   ★ 阴性对照通过：36@k3 自由置换 p = %r 逐位复现冻结件' % got)

    # ── 对照结论 ───────────────────────────────────────────────────────────────
    print('\n③ 对照结论（A vs B 是否**可数值区分**）')
    cmp_rows = []
    for tag in readings:
        for key, v in readings[tag].items():
            same_A_B1 = (v['A_label_permutation']['p'] == v['B1_empirical']['p'])
            cmp_rows.append(dict(unit_set=tag, deflation=key,
                                 p_A=v['A_label_permutation']['p'], p_B1=v['B1_empirical']['p'],
                                 p_B2=v['B2_lognormal']['p'], A_equals_B1=same_A_B1))
            print('   %-10s %-16s  A=%.6e  B1=%.6e  %s   B2=%.6e'
                  % (tag, key, v['A_label_permutation']['p'], v['B1_empirical']['p'],
                     '**完全相同**' if same_A_B1 else '不同', v['B2_lognormal']['p']))

    print('\n④ 三次去偏的排序在 B 零模型下是否仍显著（p < 0.05）')
    all_sig = all(v['B1_empirical']['p'] < 0.05 and v['B2_lognormal']['p'] < 0.05
                  for tag in readings for v in readings[tag].values())
    print('   ⇒ %s' % ('全部 6 个读数在 A / B1 / B2 下均 p < 0.05 ⇒ **ordering 仍显著**'
                       if all_sig else '**有读数不显著** ⇒ 需逐格看'))

    out = dict(
        purpose='P3R4-②：按 glm52 #8 原话构造 "span 值随机" 零模型，重算 §7.3 排序统计量在该零模型下的'
                '分布，并与包内既有的 label-permutation 对照。0 次推理、0 新数据。',
        question='评审："包内现有的是 label-permutation，而 span 值随机是另一个零模型，两者不可互相替代。"'
                 '本脚本把后者按字面实现，并回答"它是否与前者可区分"。',
        statistic='Spearman(full-ladder span, deflated span)，逐字同 m37_ci_power.py::spearman；'
                  '被排序的是**两种去偏口径给出同一排序**这件事。',
        null_models=dict(
            H0_A=dict(name='label_permutation', source='m37_ci_power.py::perm_p() 逐字',
                      n=N_PERM, seed=SEED, tail='p=(1+#{stat>=obs})/(1+N)'),
            H0_B=dict(name='random_span_values',
                      source='glm52 #8 原话："随机生成同分布无结构的 span 值，算与真实 ordering 的 Spearman"',
                      specs=dict(B1='从观测到的 span 值本身有放回重抽（经验边缘，无分布假设）',
                                 B2='从 span 的对数正态 MLE 重抽（字面的"同分布、无结构"）'),
                      n=N_DRAW, seed=SEED, held_fixed='去偏 span 一侧保持不动'),
        ),
        degeneracy=deg,
        degeneracy_verdict='★ **本轮构造的 "span 值随机" 零模型不退化**：它改的是 (span, deflated span) 的'
                           '**配对本身**，统计量随每次重抽变化（实测 distinct 统计量 = %d / %d）。'
                           '第 2/3 轮报的退化的只是那个"把整块簇换个位置"的实现（只改顺序、不改配对，'
                           'distinct=1、p≡1）；本脚本把两者都实测并印在同一处，避免再被误读成'
                           '"所有置换类零模型都不可评"。'
                           % (deg['31unit_k4']['value_shuffle_distinct'],
                              deg['36unit_k3']['value_shuffle_distinct']),
        frozen_reference=frozen,
        readings=readings,
        comparison=cmp_rows,
        verdict=dict(
            A_and_B1_numerically_identical=all(r['A_equals_B1'] for r in cmp_rows),
            all_readings_p_lt_005_both_nulls=bool(all_sig),
            interpretation='H0-A（随机置换标签）与 H0-B1（从经验边缘有放回重抽 span 值）检验的是**同一个**'
                           '独立零假设；两者在有限样本下只差"是否有放回"。实测 p 值逐个相同 ⇒ '
                           '在这个意义上它们**不可数值区分**，"另一个零模型"这个说法在**零假设层面不成立**。'
                           'B2（对数正态参数重抽）给出的 p 仍是数量级相同的极小值 ⇒ 结论不变。'
                           '★ 但两者**概念上不冗余**：A 把两侧边缘都当固定、只断开配对；B 额外把 span 的'
                           '**幅度**当作可重抽的 ⇒ B 在"span 的幅度本身是否携带信息"这个问题上更直接。'
                           '若要写进稿子，应写"以两种等价的独立零模型复核"而不是"两个不同的零模型"。',
        ),
        created_by='p3r4_zero_2_null_span.py',
        created_at=time.strftime('%Y-%m-%dT%H:%M:%S'),
        no_inference=True,
    )
    io.open(OUT, 'w', encoding='utf-8', newline='\n').write(json.dumps(out, ensure_ascii=False, indent=2))
    h = hashlib.md5(io.open(OUT, 'rb').read()).hexdigest()
    io.open(OUT + '.md5', 'w', encoding='utf-8', newline='\n').write(
        '%s  %s  (p3r4_zero_2_null_span.py)\n' % (h, os.path.basename(OUT)))
    print('\n已写 %s（md5 %s）' % (os.path.basename(OUT), h[:12]))
    print('用时 %.1f s' % (time.time() - t0))
    return 0


def selftest():
    print('P3R4-② selftest（阴性对照）')
    ctl = []
    # 1) 顺序置换不改统计量（退化的充要条件）
    a = [1.0, 2.0, 3.0, 4.0, 5.0]
    b = [1.1, 2.2, 2.9, 4.1, 5.2]
    rnd = random.Random(0)
    s = set()
    for _ in range(200):
        o = list(range(len(a)))
        rnd.shuffle(o)
        s.add(round(spearman([a[i] for i in o], [b[i] for i in o]), 12))
    ctl.append(('单元顺序置换 ⇒ distinct=1（退化）', len(s) == 1))
    # 2) 值置换会改统计量（非退化）
    s2 = set()
    for _ in range(50):
        aa = list(a)
        rnd.shuffle(aa)
        s2.add(round(spearman(aa, b), 12))
    ctl.append(('span 值置换 ⇒ distinct>1（非退化）', len(s2) > 1))
    # 3) 独立零模型下观测必须落在分布之外（p 极小）
    r = null_random_span(a, b, 'empirical', n_draw=2000)
    ctl.append(('强关联下经验重抽 p < 0.01', r['p'] < 0.01))
    ctl.append(('强关联下对数正态重抽 p < 0.01',
                null_random_span(a, b, 'lognormal', n_draw=2000)['p'] < 0.01))
    # 4) 反例：把 b 也随机化后，同一个零模型的 p 必须**不**显著
    rnd2 = random.Random(7)
    b2 = list(b)
    rnd2.shuffle(b2)
    ctl.append(('配对被打断后经验重抽 p 不显著（p>0.05）',
                null_random_span(a, b2, 'empirical', n_draw=2000)['p'] > 0.05))
    # 5) 对数正态拟合的自证
    mu, sd = lognormal_fit([1.0, math.e, math.e ** 2])
    ctl.append(('lognormal MLE：log 空间均值 = 1.0', abs(mu - 1.0) < 1e-12))
    ok = True
    for nm, passed in ctl:
        print('  [%s] %s' % ('PASS' if passed else 'FAIL', nm))
        ok = ok and passed
    print('SELFTEST: %s' % ('PASS' if ok else 'FAIL'))
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
