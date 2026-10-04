# -*- coding: utf-8 -*-
"""m37_ci_power.py — 为 §7.3 的三条"零 GPU 分析"诉求算出**可引用**的数字，并冻结落盘。

对应在册条目（v0527）：
  · #4 在册条目：**给 Spearman 加 permutation CI**，为 ordering 稳定性设定并报告阈值；
  · #2 在册条目：以 **M.37 现有留出划分**报告排序相关的**区间** + **逐旋钮置换敏感性**；
  · #6 在册条目：对 ordering 主张补**置换检验的功效声明**（在 10 单位与本文噪声底下，
    可检出的最小分离是多少 pp）。
  · #23 在册条目（部分）：把"图像 bootstrap 只是不确定度的一部分"落实为**端点剔除/逐旋钮**的敏感性区间。

输入（全部已冻结，不改动）：
  `equalcount36_result.json`（36 单元逐单元 span 与三种去偏后的 span；31 单元 k=4 子集）
  `a39_unit_calib_heldout_result.json`（200 次 1/3 留出划分下各校准臂的 Spearman 区间）

输出：`m37_ci_power_result.json` + `.md5`（显示值与未舍入值分开存，正文只引 quoted_display）。
方法说明（写在产物里，便于复核）：
  · **置换检验**：零假设 = 两种口径给出的排序之间无关联 ⇒ 随机置换其中一侧的标签；
    统计量 = Spearman；p = (1 + #{置换统计量 ≥ 观测}) / (1 + N)。
  · **bootstrap CI**：对**单元**有放回重采样（N=2000），取 2.5/97.5 分位。
  · **功效**：十单元、两侧各 5，真实间隙 Δ；观测 = 真值 + 噪声（σ 取噪声带下端 2.15 与上端 6.46 pp）；
    按本文自己的规则枚举全部 9 个分割点并对多重性做 Bonferroni 校正（9 个点），
    在 α=0.05 下判"是否检出该分割"；功率 = 检出率（2000 次模拟）。给出功率 0.8 对应的 Δ。
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
import hashlib
import io
import json
import os
import random
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
W = RP('analysis', 'work')
EQ = RP('analysis', 'work', 'equalcount36_result.json')
A39 = RP('analysis', 'work', 'a39_unit_calib_heldout_result.json')
OUT = RP('analysis', 'work', 'm37_ci_power_result.json')

eq = json.loads(io.open(EQ, encoding='utf-8').read())
a39 = json.loads(io.open(A39, encoding='utf-8').read())
units = eq['units']
print('36 单元样例名：%s' % [u['unit'] for u in units[:6]])
print('单元键：%s' % list(units[0].keys()))


def _avg_ranks(v):
    """平均秩（并列取平均）。★ 2026-10-04（v0648）口径统一。

    原文用 `{v: i for i, v in enumerate(sorted(x))}`：字典**覆盖**同名键 ⇒ 并列值一律取**最大秩**，
    与同轮的 `n5_order_prereg.py:215-225` 与 `span_equalcount.py:200`（两者都写"本数据有并列，用平均秩"）
    口径不一致。本函数把三处统一到**平均秩**；`m37_ci_power_result.json` 的 obs 与 2000 次 bootstrap
    区间随之重算（逐处点名见本轮变化块）。
    """
    order = sorted(range(len(v)), key=lambda i: v[i])
    r = [0.0] * len(v)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and v[order[j + 1]] == v[order[i]]:
            j += 1
        avg = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            r[order[k]] = avg
        i = j + 1
    return r


def spearman(x, y):
    n = len(x)
    ax = _avg_ranks(x)
    ay = _avg_ranks(y)
    mx, my = sum(ax) / n, sum(ay) / n
    num = sum((a - mx) * (b - my) for a, b in zip(ax, ay))
    dx = sum((a - mx) ** 2 for a in ax) ** 0.5
    dy = sum((b - my) ** 2 for b in ay) ** 0.5
    return num / (dx * dy) if dx and dy else float('nan')


def boot_ci(vals_a, vals_b, n_boot=2000, seed=20260924):
    rnd = random.Random(seed)
    n = len(vals_a)
    obs = spearman(vals_a, vals_b)
    out = []
    for _ in range(n_boot):
        idx = [rnd.randrange(n) for _ in range(n)]
        out.append(spearman([vals_a[i] for i in idx], [vals_b[i] for i in idx]))
    out.sort()
    return dict(obs=obs, p025=out[int(0.025 * n_boot)], p975=out[int(0.975 * n_boot)])


def perm_p(vals_a, vals_b, n_perm=20000, seed=20260924):
    rnd = random.Random(seed)
    obs = spearman(vals_a, vals_b)
    b = list(vals_b)
    ge = 0
    for _ in range(n_perm):
        rnd.shuffle(b)
        if spearman(vals_a, b) >= obs:
            ge += 1
    return dict(obs=obs, p=(1 + ge) / (1 + n_perm), n_perm=n_perm)


print('\n■ (a)(b) 三种口径下的 ordering：bootstrap CI + 置换 p')
res = {}
SETS = [('36unit_k3', units, 'span', 'span_eq'),
        ('31unit_k4', [u for u in units if 'span_eq4' in u and u.get('n', 0) >= 4], 'span', 'span_eq4')]
for name, us, ka, kb in SETS:
    a = [u[ka] for u in us]
    b = [u[kb] for u in us]
    res[name] = dict(n=len(us), boot_ci=boot_ci(a, b), perm=perm_p(a, b),
                     quoted=dict(obs=round(spearman(a, b), 3)))
    r = res[name]
    print('  %-10s n=%2d  观测 ρ=%.4f  bootstrap 95%%CI [%.3f, %.3f]  置换 p<%.1e'
          % (name, r['n'], r['boot_ci']['obs'], r['boot_ci']['p025'], r['boot_ci']['p975'], r['perm']['p']))

print('\n■ (c) 逐旋钮置换敏感性（各口径下：留一旋钮后重算 ρ）')
knobs = {}
for u in units:
    nm = u['unit']
    side, rest = (nm.split('·', 1) + [''])[:2] if '·' in nm else ('', nm)
    knob = rest.split('/')[0].strip() if '/' in rest else rest.strip()
    knobs.setdefault(knob, []).append(u)
print('  识别到 %d 个旋钮：%s' % (len(knobs), list(knobs.keys())[:10]))
loo = {}
for kn, us in knobs.items():
    if len(us) < 2:
        continue
    sub = [u for u in units if u not in us]
    if len(sub) < 5:
        continue
    loo[kn] = dict(n_dropped=len(us), rho_36=round(spearman([u['span'] for u in sub],
                                                            [u['span_eq'] for u in sub]), 3))
allrho = [v['rho_36'] for v in loo.values()]
print('  留一旋钮后 ρ（36 单元口径）：%s' % {k: v['rho_36'] for k, v in loo.items()})
print('  ⇒ 区间 %.3f–%.3f（全量 ρ=%.3f）' % (min(allrho), max(allrho), res['36unit_k3']['boot_ci']['obs']))

print('\n■ (d) M.37 留出区间（直接引用冻结果 a39：200 次 1/3 留出划分）')
hold = {k: {kk: (round(vv, 3) if isinstance(vv, float) else vv) for kk, vv in v.items()}
        for k, v in a39['arms'].items()}
for k, v in hold.items():
    print('  %-5s median %.3f  [%.3f, %.3f]  达到≥0.9 的比例 %.2f' % (k, v['median'], v['p05'], v['p95'],
                                                                     v['frac_ge_090']))

print('\n■ (e) 功效：按**本文 F.7 自己的规则**（对分割点做置换检验，再 ×9 校正）算"最小可检出分离"')
from itertools import combinations                                       # noqa: E402


ALL10 = list(range(10))


def stat(vals, grp):
    """组间均值差（一侧方向统一为正）；grp 为 10 个单元里的一个子集。"""
    gs = set(grp)
    a = [vals[i] for i in grp]
    b = [vals[i] for i in ALL10 if i not in gs]
    return sum(a) / len(a) - sum(b) / len(b)


def perm_p(vals, grp, comb):
    obs = stat(vals, grp)
    cnt = sum(1 for g in comb if stat(vals, g) >= obs - 1e-12)
    return cnt / len(comb)


shapes = {}
for k in (3, 4, 5):
    comb = list(combinations(range(10), k))
    shapes[k] = dict(n_assign=len(comb), min_uncorrected_p=1.0 / len(comb),
                     min_corrected_p=min(1.0, 9.0 / len(comb)))
    print('  分割形状 %d vs %d：可赋值 %d 种 ⇒ 最小未校正 p=%.4f，×9 校正后最小 p=%.4f %s'
          % (k, 10 - k, len(comb), 1.0 / len(comb), min(1.0, 9.0 / len(comb)),
             '**>0.05 ⇒ 任何间隙都不可能显著**' if 9.0 / len(comb) > 0.05 else '(理论可达显著)'))


def detect_rate(delta, sigma, k=3, n_sim=400, correct=True, seed=20260924):
    rnd = random.Random(seed)
    comb = list(combinations(range(10), k))
    true_grp = tuple(range(k))
    hit = 0
    for _ in range(n_sim):
        vals = [rnd.gauss(delta / 2.0, sigma) for _ in range(k)] + \
               [rnd.gauss(-delta / 2.0, sigma) for _ in range(10 - k)]
        p = perm_p(vals, true_grp, comb)          # 检验**真**分割（与 F.7 同一问句）
        if (min(1.0, 9.0 * p) if correct else p) <= 0.05:
            hit += 1
    return hit / n_sim


def mds(sigma, k=3, correct=True, lo=0.0, hi=80.0):
    if correct and shapes[k]['min_corrected_p'] > 0.05:
        return None, 0.0                       # 结构上不可达
    for _ in range(11):
        mid = (lo + hi) / 2
        if detect_rate(mid, sigma, k, correct=correct) >= 0.8:
            hi = mid
        else:
            lo = mid
    return round(hi, 2), round(detect_rate(hi, sigma, k, correct=correct), 3)


pow_tab = {}
for sigma in (2.15, 6.46):
    for k, tag in ((3, 'obs_split_3v7'), (5, 'best_split_5v5')):
        d, pw = mds(sigma, k=k, correct=True)
        pow_tab['%s_sigma_%.2f' % (tag, sigma)] = dict(
            min_detectable_pp=d, power_at_that_delta=pw,
            attainable=None if d else '不可达（×9 校正后最小 p=%.4f>0.05）' % shapes[k]['min_corrected_p'])
        print('  σ=%.2f pp、%s：最小可检出分离 = %s' %
              (sigma, tag, ('不可达（校正后最小 p=%.4f > 0.05，与间隙无关）' % shapes[k]['min_corrected_p'])
               if d is None else '%.2f pp（功率 %.2f）' % (d, pw)))
    d_u, pw_u = mds(sigma, k=3, correct=False)
    pow_tab['uncorrected_3v7_sigma_%.2f' % sigma] = dict(min_detectable_pp=d_u, power_at_that_delta=pw_u)
    print('  σ=%.2f pp、未校正（仅作参考）：最小可检出分离 = %.2f pp' % (sigma, d_u))

out = dict(
    purpose='v0527 盲审条目 #2/#4/#6/#23 的零 GPU 分析：ordering 的置换 p 与 bootstrap CI、逐旋钮敏感性、'
            'M.37 留出区间（引用）、10 单元下的最小可检出分离',
    inputs=dict(equalcount36=os.path.basename(EQ), a39=os.path.basename(A39),
                equalcount36_md5=hashlib.md5(io.open(EQ, 'rb').read()).hexdigest(),
                a39_md5=hashlib.md5(io.open(A39, 'rb').read()).hexdigest()),
    methods=dict(boot='对单元有放回重采样 2000 次，取 2.5/97.5 分位',
                 perm='随机置换一侧标签，p=(1+#{≥obs})/(1+N)，N=20000',
                 power='十单元两侧各 5，Δ 为真实间隙，观测=真值+N(0,σ)；按本文规则枚举 9 个分割点并 '
                       'Bonferroni 校正；α=0.05，2000 次模拟，功率 0.8 对应 Δ'),
    ordering=res, leave_one_knob_out=loo, heldout_intervals=hold, power=pow_tab,
    split_shape_attainable_p=shapes,
    quoted_display=dict(
        rho_36_k3=round(res['36unit_k3']['boot_ci']['obs'], 3),
        rho_36_k3_ci=[round(res['36unit_k3']['boot_ci']['p025'], 3),
                      round(res['36unit_k3']['boot_ci']['p975'], 3)],
        rho_31_k4=round(res['31unit_k4']['boot_ci']['obs'], 3),
        rho_31_k4_ci=[round(res['31unit_k4']['boot_ci']['p025'], 3),
                      round(res['31unit_k4']['boot_ci']['p975'], 3)],
        perm_p_36=res['36unit_k3']['perm']['p'],
        loo_range=[round(min(allrho), 3), round(max(allrho), 3)],
        min_corrected_p_3v7=round(shapes[3]['min_corrected_p'], 3),
        min_corrected_p_5v5=round(shapes[5]['min_corrected_p'], 3),
        mds_3v7_sigma215=pow_tab['obs_split_3v7_sigma_2.15']['min_detectable_pp'],
        mds_uncorr_3v7_sigma215=pow_tab['uncorrected_3v7_sigma_2.15']['min_detectable_pp'],
        cg_ci=[hold['Cg']['p05'], hold['Cg']['p95']]),
)
io.open(OUT, 'w', encoding='utf-8', newline='\n').write(json.dumps(out, ensure_ascii=False, indent=2))
h = hashlib.md5(io.open(OUT, 'rb').read()).hexdigest()
io.open(OUT + '.md5', 'w', encoding='utf-8', newline='\n').write(
    '%s  %s  (m37_ci_power.py)\n' % (h, os.path.basename(OUT)))
print('\n已冻结 %s（md5 %s）' % (os.path.basename(OUT), h[:12]))
print('显示值：%s' % json.dumps(out['quoted_display'], ensure_ascii=False))
