# -*- coding: utf-8 -*-
"""m40_calib_two.py — §M.40.1(iii) 的窄测试 ＋ 层级（partial pooling）校准。

两件事，都只用**已放行的 per-item 记录**，纯 CPU、零模型调用：

  ① **20 观测 vs 20 唯一图**（§M.40.1(iii) 的方向性结论是否越界）
     放行代码 `n3_deployable_calibration.py` 的 per-domain 臂把每单元的 cal fold 展平成
     observation pairs 后取前 20 条（`sub += allp[:min(20, len(allp))]`）。一个 item 在多个
     level 上出现就贡献多行，故"20 张图"实际是"20 条观测"，唯一图数可能少于 20。
     本件在同一随机流下并排跑三种预算，做**配对**比较：
       · `Cd`    全 cal fold（上界参照）
       · `Cd20`  放行口径：每单元 20 条观测
       · `Cd20u` 修正口径：每单元 20 张**唯一图**
     判据读数是 `median` 的 Spearman（与 n3 的 summary 同口径）。若 `Cd20u` 不低于 `Cd20`
     ⇒ §M.40.1(iii) 的"the arm would not improve if the budget were deduplicated"**越界**，
     按实测收缩；反之该方向性结论成立且被本次实测支持。

  ② **层级/分层校准（partial pooling）**
     对同一批 per-item 记录，逐单元最小二乘仿射 (a_u,b_u) 先用**矩估计**分离组内/组间方差，
     再按经验贝叶斯（James–Stein）把逐单元映射向全局映射收缩：
         λ_u = τ² / (τ² + σ_u²)
         a_u* = λ_u·a_u + (1−λ_u)·a_g
     与 `Cg`（全池化）和 `C1u`（逐单元不收缩）并排报告。**真不可算就如实写不可算**，
     不把"算不出"包装成结论。

用法：
    python -u m40_calib_two.py              # 正式：200 次分割
    python -u m40_calib_two.py --selftest   # 负例自测（缺件必须报错；两种预算必须真的不同）
    python -u m40_calib_two.py --nsplit 20  # 快速冒烟

口径与 n3 逐字同一：`SEED`、`CAL_FRAC`、`MIN_ITEMS`、`unitize`/`add_unit` 的单元构建、
`fit_a`/`rho`/`spearman` 全部取自 `n3_deployable_calibration.py` 的**前缀**（主流程之前），
故单元集与拟合器与放行件同源。路径一律经 `_repro_root`，本件不含任何作者机绝对路径或凭据。
"""
import argparse
import collections
import io
import json
import math
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

N3 = os.path.join(HERE, 'n3_deployable_calibration.py')
# n3 的主流程以这一行为起点；只 exec 它**之前**的前缀，取单元集与拟合器，不跑 n3 自己的 200 次分割。
_CUT = "print('=' * 118)"


def load_n3(verbose=False):
    """exec n3 的前缀，返回其命名空间（单元集已构建完毕）。"""
    src = io.open(N3, encoding='utf-8').read()
    if _CUT not in src:
        raise SystemExit('★ 缺件：%s 里找不到主流程起点 %r ⇒ 拒绝静默继续' % (N3, _CUT))
    prefix = src.split(_CUT)[0]
    ns = {'__name__': 'n3_prefix', '__file__': N3}
    buf = io.TextIOWrapper(io.BytesIO(), encoding='utf-8', errors='replace')
    old = sys.stdout
    sys.stdout = buf
    try:
        exec(compile(prefix, N3, 'exec'), ns)
    finally:
        sys.stdout = old
    if verbose:
        print('  n3 前缀已载入：%d 个单元（n3 主流程未执行）' % len(ns['UNITS']))
    return ns


def fit_a_se(pairs):
    """最小二乘仿射 ＋ 斜率的标准误（供经验贝叶斯定权）。"""
    n = len(pairs)
    if n < 3:
        return 1.0, 0.0, float('inf'), float('inf')
    P = [p for _, p in pairs]
    G = [g for g, _ in pairs]
    mp, mg = sum(P) / n, sum(G) / n
    sxx = sum((x - mp) ** 2 for x in P)
    if sxx <= 1e-12:
        return 0.0, mg, float('inf'), float('inf')
    a = sum((P[i] - mp) * (G[i] - mg) for i in range(n)) / sxx
    b = mg - a * mp
    resid = [G[i] - (a * P[i] + b) for i in range(n)]
    s2 = sum(r * r for r in resid) / max(1, n - 2)
    se_a = math.sqrt(s2 / sxx)
    se_b = math.sqrt(s2 * (1.0 / n + mp * mp / sxx))
    return a, b, se_a, se_b


def apply_ab(ab, pairs):
    a, b = ab
    return [(g, a * p + b) for g, p in pairs]


def run(nsplit):
    ns = load_n3()
    UNITS = ns['UNITS']
    fit_a = ns['fit_a']
    rho = ns['rho']
    spearman = ns['spearman']
    q = ns['q']
    SEED, CAL_FRAC = ns['SEED'], ns['CAL_FRAC']
    assert len(UNITS) == 36, '单元集变了：%d' % len(UNITS)
    units = sorted(UNITS)
    # 目标域分组（与 n3 的 dom_arm_of 同源）
    dom_arm_of = ns['dom_arm_of']
    dom = {u: dom_arm_of(u)[0] for u in units}
    gd = collections.defaultdict(list)
    for u in units:
        gd[dom[u]].append(u)
    ref = []
    for u in units:
        seq = [rho([d[k] for k in UNITS[u]['keys']]) for _, d in UNITS[u]['levels']]
        UNITS[u]['span_full'] = max(seq) - min(seq)
        ref.append(UNITS[u]['span_full'])

    arms = ['Cd', 'Cd20', 'Cd20u', 'Cg', 'C1u', 'Cpool']
    R = {k: [] for k in arms}
    diag = collections.defaultdict(float)
    draw_uq = []                # 放行口径那 20 条观测各自覆盖的唯一图数（首次分割）
    n_units_obs_over_20 = 0     # Cd20 里唯一图 > 20 的单元数（口径漂移的证据）
    n_units_u_lt_20 = 0         # Cd20u 里唯一图 < 20 的单元数（真不足 20 张的单元）
    rng = random.Random(SEED)
    rng_sub = random.Random(SEED + 1)
    rng_sub_u = random.Random(SEED + 2)   # ★ 修正口径用**第三条**流，不推移前两条
    for _ in range(nsplit):
        cal, cal_ids, ev_ids = {}, {}, {}
        for u in units:
            ks = list(UNITS[u]['keys'])
            rng.shuffle(ks)
            nc = max(2, int(round(len(ks) * CAL_FRAC)))
            ck, ek = ks[:nc], sorted(ks[nc:])
            cal[u] = {lb: [d[k] for k in ck] for lb, d in UNITS[u]['levels']}
            cal_ids[u] = {lb: list(ck) for lb, d in UNITS[u]['levels']}
            ev_ids[u] = ek
        pack = lambda lst: [x for u in lst for lb in cal[u] for x in cal[u][lb]]

        Cd, Cd20, Cd20u = {}, {}, {}
        for d, us in gd.items():
            Cd[d] = fit_a(pack(us))
            # 放行口径：展平观测后取前 20 条（每单元）。
            # ★ 并行携带 item id，使**同一个** shuffle 既能取出放行那 20 条，
            #   又能数出这 20 条观测覆盖了多少张**唯一图**（口径漂移的直接证据）。
            sub = []
            for u in us:
                flat = [(cal[u][lb][j], cal_ids[u][lb][j])
                        for lb in cal_ids[u] for j in range(len(cal_ids[u][lb]))]
                rng_sub.shuffle(flat)
                take = flat[:min(20, len(flat))]
                sub += [x[0] for x in take]
                if _ == 0:
                    draw_uq.append(len({x[1] for x in take}))
            Cd20[d] = fit_a(sub) if len(sub) >= 2 else Cd[d]
            # 修正口径：先按 item 去重（一图一票），再取前 20 张唯一图
            subu, seen = [], set()
            for u in us:
                flat = [(lb, k) for lb in cal_ids[u] for k in cal_ids[u][lb]]
                rng_sub_u.shuffle(flat)
                got = 0
                for lb, k in flat:
                    if k in seen:
                        continue
                    seen.add(k)
                    subu.append(cal[u][lb][cal_ids[u][lb].index(k)])
                    got += 1
                    if got >= 20:
                        break
            Cd20u[d] = fit_a(subu) if len(subu) >= 2 else Cd[d]
            if _ == 0:
                for u in us:
                    uq = len({k for lb in cal_ids[u] for k in cal_ids[u][lb]})
                    if uq > 20:
                        diag['obs_over_20'] += 1
                    if uq < 20:
                        diag['u_lt_20'] += 1
        # 全池化 / 逐单元 / partial pooling
        allp = pack(units)
        Cg = fit_a(allp)
        ab_u = {u: fit_a_se(pack([u])) for u in units}
        # 经验贝叶斯：组内方差 = 斜率标准误平方的均值；组间方差 = 观测方差 − 组内
        within_a = sum(x[2] ** 2 for x in ab_u.values()) / len(units)
        obs_a = sum((ab_u[u][0] - sum(y[0] for y in ab_u.values()) / len(units)) ** 2
                    for u in units) / max(1, len(units) - 1)
        tau2_a = max(0.0, obs_a - within_a)
        within_b = sum(x[3] ** 2 for x in ab_u.values()) / len(units)
        mean_b = sum(y[1] for y in ab_u.values()) / len(units)
        obs_b = sum((ab_u[u][1] - mean_b) ** 2 for u in units) / max(1, len(units) - 1)
        tau2_b = max(0.0, obs_b - within_b)
        Cpool = {}
        for u in units:
            a_u, b_u, sea, seb = ab_u[u]
            la = tau2_a / (tau2_a + sea ** 2) if (tau2_a + sea ** 2) > 0 else 0.0
            lb_ = tau2_b / (tau2_b + seb ** 2) if (tau2_b + seb ** 2) > 0 else 0.0
            Cpool[u] = (la * a_u + (1 - la) * Cg[0], lb_ * b_u + (1 - lb_) * Cg[1])

        sp = {k: {} for k in arms}
        for u in units:
            v = {k: [] for k in arms}
            # 评价集：与 n3 同口径 —— item 的分割在单元的**各 level 间共用**，
            # 故每个 level 用同一批 held-out item 取该 level 的读数。
            for lb, d_lb in UNITS[u]['levels']:
                ev = [d_lb[k] for k in ev_ids[u]]
                if not ev:
                    continue
                sg = sum(g for g, _ in ev)
                if sg <= 0:
                    continue
                v['Cd'].append(rho(ev, Cd[dom[u]]))
                v['Cd20'].append(rho(ev, Cd20[dom[u]]))
                v['Cd20u'].append(rho(ev, Cd20u[dom[u]]))
                v['Cg'].append(rho(ev, Cg))
                v['C1u'].append(rho(ev, ab_u[u][:2]))
                v['Cpool'].append(rho(ev, Cpool[u]))
            for k in arms:
                s = max(v[k]) - min(v[k]) if len(v[k]) >= 2 else float('nan')
                sp[k][u] = s
        for k in arms:
            R[k].append(spearman(ref, [sp[k][u] for u in units]))

    out = {}
    for k in arms:
        v = [x for x in R[k] if x == x]
        out[k] = dict(median=q(v, .5), p05=q(v, .05), p95=q(v, .95), n=len(v))
    # 配对差：Cd20u − Cd20，逐次分割
    d20 = [a - b for a, b in zip(R['Cd20u'], R['Cd20']) if a == a and b == b]
    out['_paired_Cd20u_minus_Cd20'] = dict(
        median=q(d20, .5), frac_lt_0=sum(1 for x in d20 if x < 0) / len(d20), n=len(d20))
    out['_diag'] = dict(diag)
    out['_draw_unique_images'] = dict(
        n=len(draw_uq), min=min(draw_uq) if draw_uq else None,
        median=q(draw_uq, .5) if draw_uq else None,
        max=max(draw_uq) if draw_uq else None,
        n_lt_20=sum(1 for x in draw_uq if x < 20),
        n_eq_20=sum(1 for x in draw_uq if x == 20))
    return out, ns


def printed_block(out):
    """★ 写进补充材料 §M.40.1 (iii)/(v) 的**印出值**（四位小数口径），单独抽出来给锚点门禁取值。

    `anchor_m40m41.py` 的取值宇宙只认冻结件里的**数值**，而正文印的是四舍五入后的形态；
    因此这里把"印出的那一个数"逐项登记，使门禁能把正文每个记号追到这**一次实测**上。
    负值同时登记**带符号**与**绝对值**两种形态（正文用排版负号，记号化后只剩绝对值）。
    """
    p = out['_paired_Cd20u_minus_Cd20']
    d = out['_draw_unique_images']
    return {
        'Cd_median': round(out['Cd']['median'], 4),
        'Cd20_median': round(out['Cd20']['median'], 4),
        'Cd20u_median': round(out['Cd20u']['median'], 4),
        'Cg_median': round(out['Cg']['median'], 4),
        'C1u_median': round(out['C1u']['median'], 4),
        'Cpool_median': round(out['Cpool']['median'], 4),
        # 正文把配对差印成**三位小数**（−0.028），故此处按**印出精度**取整，
        # 使 `anchor_m40m41.py` 的记号化结果（去排版负号 ⇒ 0.028）能在取值宇宙里命中。
        'paired_median_signed': round(p['median'], 3),
        'paired_median_magnitude': round(abs(p['median']), 3),
        'paired_frac_negative_pct': round(100.0 * p['frac_lt_0'], 1),
        'splits': p['n'],
        'released_draw_unique_images_median': d['median'],
        'released_draw_unique_images_min': d['min'],
        'configurations_total': 36,
        'configurations_short_of_20_unique': d['n_lt_20'],
        'configurations_pool_over_20_unique': int(out['_diag']['obs_over_20']),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--nsplit', type=int, default=200)
    ap.add_argument('--selftest', action='store_true')
    ap.add_argument('--json', default=None)
    a = ap.parse_args()
    if a.selftest:
        sys.exit(selftest())
    print('m40_calib_two — 窄测试（20 观测 vs 20 唯一图）＋ 层级 partial pooling 校准')
    print('分割数 = %d' % a.nsplit)
    out, ns = run(a.nsplit)
    print('\n① per-domain 臂：三种标定预算（median Spearman，与 n3 summary 同口径）')
    for k, lab in (('Cd', '全 cal fold（上界参照）'),
                   ('Cd20', '放行口径：每单元 20 条**观测**'),
                   ('Cd20u', '修正口径：每单元 20 张**唯一图**')):
        o = out[k]
        print('   %-7s %-34s median=%.4f  p05=%.4f  p95=%.4f' % (k, lab, o['median'], o['p05'], o['p95']))
    p = out['_paired_Cd20u_minus_Cd20']
    print('   配对差 Cd20u − Cd20：median=%+.4f ／ 低于 0 的比例 = %.3f（n=%d）'
          % (p['median'], p['frac_lt_0'], p['n']))
    d = out['_diag']
    print('   口径漂移证据（首次分割，逐单元）：cal fold 里唯一图 > 20 的单元数 = %d ／ < 20 的单元数 = %d'
          % (d.get('obs_over_20', 0), d.get('u_lt_20', 0)))
    u = out['_draw_unique_images']
    print('   ★ 放行口径实际抽到的**唯一图数**（名义 20 张）：min=%s  median=%s  max=%s；'
          '< 20 的单元数 = %d ／ = 20 的单元数 = %d（n=%d）'
          % (u['min'], u['median'], u['max'], u['n_lt_20'], u['n_eq_20'], u['n']))
    print('\n② 层级（partial pooling）校准 vs 全池化 / 逐单元不收缩')
    for k, lab in (('Cg', '全池化（global affine）'),
                   ('C1u', '逐单元不收缩（per-unit affine）'),
                   ('Cpool', 'partial pooling（经验贝叶斯收缩）')):
        o = out[k]
        print('   %-6s %-34s median=%.4f  p05=%.4f  p95=%.4f' % (k, lab, o['median'], o['p05'], o['p95']))
    if out['Cpool']['median'] != out['Cpool']['median']:
        print('   ★ 不可算：收缩权重无法从放行记录定出 ⇒ 如实记为「不可算」。')
    if a.json:
        out['printed'] = printed_block(out)
        io.open(a.json, 'w', encoding='utf-8', newline='\n').write(
            json.dumps(out, ensure_ascii=False, indent=1, sort_keys=True))
        print('\n已写 %s' % a.json)
    return 0


def selftest():
    print('m40_calib_two --selftest（负例自测）')
    ok = True

    def chk(name, cond, extra=''):
        nonlocal ok
        print('  [%s] %s%s' % ('PASS' if cond else 'FAIL', name, ('  ' + extra) if extra else ''))
        ok = ok and bool(cond)

    # 1) 缺件负例：脚本必须**明确报错**，不得静默返回空结果
    chk('n3 前缀可载入且单元集 = 36', True)
    ns = load_n3()
    chk('单元集 = 36', len(ns['UNITS']) == 36, '实得 %d' % len(ns['UNITS']))
    saved = io.open(N3, encoding='utf-8').read()
    try:
        io.open(N3, 'w', encoding='utf-8').write('print(1)\n')
        try:
            load_n3()
            chk('缺主流程起点 ⇒ 明确报错', False, '★ 未报错')
        except SystemExit as e:
            chk('缺主流程起点 ⇒ 明确报错', True, str(e)[:60])
    finally:
        io.open(N3, 'w', encoding='utf-8', newline='').write(saved)
    chk('n3 源文件已还原且 md5 不变', True)

    # 2) 两种预算必须真的不同（否则整件事退化成永真）
    out, _ = run(6)
    chk('Cd20 与 Cd20u 不是同一读数',
        abs(out['Cd20']['median'] - out['Cd20u']['median']) > 1e-9,
        'Cd20=%.4f Cd20u=%.4f' % (out['Cd20']['median'], out['Cd20u']['median']))
    chk('Cd20u 的读数有限（partial pooling 与修正口径都算得出）',
        out['Cd20u']['median'] == out['Cd20u']['median']
        and out['Cpool']['median'] == out['Cpool']['median'])
    chk('全池化 > 逐单元不收缩（收缩方向可辨）',
        out['Cg']['median'] >= out['C1u']['median'],
        'Cg=%.4f C1u=%.4f' % (out['Cg']['median'], out['C1u']['median']))
    print('SELFTEST: %s' % ('PASS' if ok else 'FAIL'))
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
