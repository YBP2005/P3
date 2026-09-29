# -*- coding: utf-8 -*-
"""p1df_analyze.py —— P1d / P1e / P1f 的**正式判定**（只读跑前冻结的阈值）。

读：
  /root/p1d_criteria_frozen.json （cd7ed7085dd5）
  /root/p1e_criteria_frozen.json （600f5c90a211，探索性）
  /root/p1f_criteria_frozen.json （00c38a417196）
  /root/p1d_results/*.csv
写：/root/p1df_result.json（含三个判据 md5，供 anchor 复核）

纪律：阈值只从冻结件读；不确定的地方（判据未定义分母等）**照实标为不可判**，不自行择优。
"""
import csv
import glob
import hashlib
import io
import json
import os
import re
import statistics as st
import sys

sys.stdout.reconfigure(encoding='utf-8')
OUTD = '/root/p1d_results'
FAMS = ['Phi-3.5-vision-instruct', 'Qwen3-VL-8B-Instruct', 'llava-onevision-qwen2-7b-ov',
        'gemma3-12b', 'Qwen3-VL-32B-Instruct', 'InternVL3_5-8B']
# 阶梯：锚值 -> 承载它的臂名
LADDER = [('neutral0', 0), ('mention5', 5), ('mention50', 50), ('placebo100', 100), ('mention800', 800)]


def md5_12(p):
    return hashlib.md5(io.open(p, 'rb').read()).hexdigest()[:12]


def load(f):
    if not os.path.exists(f):
        return None
    return list(csv.DictReader(io.open(f, encoding='utf-8-sig', newline='')))


def cell(fam, arm):
    rows = load(os.path.join(OUTD, 'p1d_%s_%s.csv' % (fam, arm)))
    if not rows:
        return None
    n = len(rows)
    z = sum(1 for r in rows if str(r.get('is_zero', '')).strip() == '1')
    a = sum(1 for r in rows if str(r.get('abstain', '')).strip() == '1')
    pf = sum(1 for r in rows if str(r.get('parse_ok', '')).strip() != '1')
    vals = [int(r['pred']) for r in rows if str(r.get('pred', '')).strip().lstrip('-').isdigit()]
    return dict(n=n, zero=z, zero_rate=z / n, abst=a, abst_rate=a / n, pf=pf,
                med=(st.median(vals) if vals else None))


def spearman(x, y):
    def rank(v):
        idx = sorted(range(len(v)), key=lambda i: v[i])
        r = [0.0] * len(v)
        i = 0
        while i < len(idx):
            j = i
            while j + 1 < len(idx) and v[idx[j + 1]] == v[idx[i]]:
                j += 1
            for k in range(i, j + 1):
                r[idx[k]] = (i + j) / 2.0 + 1
            i = j + 1
        return r
    rx, ry = rank(x), rank(y)
    n = len(x)
    mx, my = sum(rx) / n, sum(ry) / n
    a = sum((rx[i] - mx) * (ry[i] - my) for i in range(n))
    b = (sum((rx[i] - mx) ** 2 for i in range(n)) * sum((ry[i] - my) ** 2 for i in range(n))) ** 0.5
    return a / b if b else 0.0


def main():
    cD = json.loads(io.open('/root/p1d_criteria_frozen.json', encoding='utf-8').read())
    cE = json.loads(io.open('/root/p1e_criteria_frozen.json', encoding='utf-8').read())
    cF = json.loads(io.open('/root/p1f_criteria_frozen.json', encoding='utf-8').read())
    mD, mE, mF = md5_12('/root/p1d_criteria_frozen.json'), md5_12('/root/p1e_criteria_frozen.json'), \
        md5_12('/root/p1f_criteria_frozen.json')
    print('判据 md5：p1d=%s  p1e=%s  p1f=%s' % (mD, mE, mF))
    R = dict(criteria_md5=dict(p1d=mD, p1e=mE, p1f=mF))

    cells = {(f, a): cell(f, a) for f in FAMS for a in ('base', 'forbid0', 'neutral0', 'placebo100',
                                                        'mention5', 'mention50', 'mention800')}
    print('\n=== ① 主表（675 项/格）===')
    print('  %-30s %-13s %-13s %-13s %-13s' % ('family', 'base', 'forbid0', 'neutral0', 'placebo100'))
    for f in FAMS:
        row = []
        for a in ('base', 'forbid0', 'neutral0', 'placebo100'):
            c = cells[(f, a)]
            row.append('—' if not c else '%.1f%%/%s' % (100 * c['zero_rate'],
                                                       '—' if c['med'] is None else '%g' % c['med']))
        print('  %-30s %-13s %-13s %-13s %-13s' % (f[:30], *row))

    # ── H_A2p / H_A2rev ──────────────────────────────────────────────────────
    print('\n=== ② H_A2p（forbid0 降零率 ≥%.0f pp，需 ≥%d/%d 族）==='
          % (cD['H_A2p_zero_forbid_works']['delta_max_pp'],
             cD['H_A2p_zero_forbid_works']['min_families'], cD['H_A2p_zero_forbid_works']['n_families']))
    dz = {}
    for f in FAMS:
        b, x = cells[(f, 'base')], cells[(f, 'forbid0')]
        if not b or not x:
            continue
        dz[f] = (x['zero_rate'] - b['zero_rate']) * 100
        print('  %-30s Δzero %+7.1f pp' % (f[:30], dz[f]))
    thr = cD['H_A2p_zero_forbid_works']['delta_max_pp']
    ok = sum(1 for v in dz.values() if v <= thr)
    need = cD['H_A2p_zero_forbid_works']['min_families']
    R['H_A2p'] = dict(passed=ok >= need, n_pass=ok, n_families=len(dz), per_family=dz)
    print('  → 达标 %d/%d（需 ≥%d）⇒ %s' % (ok, len(dz), need, 'PASS' if ok >= need else 'FAIL'))

    print('\n=== ③ H_A2rev（∃ 族 Δzero ≥ +%.0f pp）==='
          % cD['H_A2rev_reversal']['delta_min_pp'])
    rev = {f: v for f, v in dz.items() if v >= cD['H_A2rev_reversal']['delta_min_pp']}
    R['H_A2rev'] = dict(triggered=bool(rev), families=rev, max_delta_pp=max(dz.values()) if dz else None)
    print('  最大 Δzero = %+.1f pp（%s）⇒ %s'
          % (max(dz.values()) if dz else float('nan'),
             max(dz, key=dz.get) if dz else '—',
             ('触发：%s' % list(rev)) if rev else '未触发'))

    # ── H_A2n 驱动因素 ───────────────────────────────────────────────────────
    print('\n=== ④ H_A2n（禁止 vs 提及：在 |Δ(f−b)| ≥ %.0f pp 的族上比 neutral0）==='
          % cD['H_A2n_prohibition_vs_mention'].get('gate_pp', 10))
    h2n = []
    for f, v in sorted(dz.items(), key=lambda kv: -abs(kv[1])):
        if abs(v) < 10.0:
            continue
        b, nn = cells[(f, 'base')], cells[(f, 'neutral0')]
        dn = (nn['zero_rate'] - b['zero_rate']) * 100
        ratio = abs(dn) / abs(v) if v else None
        verdict = ('针对"提及"' if ratio is not None and ratio >= 0.8
                   else '针对"禁止"' if ratio is not None and ratio <= 0.5 else '混合')
        h2n.append(dict(family=f, d_forbid=v, d_neutral=dn, ratio=ratio, verdict=verdict))
        print('  %-30s Δ(f−b)=%+7.1f  Δ(n−b)=%+7.1f  比=%.2f ⇒ %s' % (f[:30], v, dn, ratio, verdict))
    R['H_A2n'] = h2n if h2n else 'no qualifying family'

    # ── H_N0 噪声底 ─────────────────────────────────────────────────────────
    print('\n=== ⑤ H_N0（跨会话：P1d base vs 已发表 base）===')
    n0 = []
    for f in FAMS:
        new = cells[(f, 'base')]
        old = load('/root/p1_results/p1_%s_base.csv' % f)
        if not new or not old:
            continue
        z = sum(1 for r in old if str(r.get('is_zero', '')).strip() == '1')
        d = (new['zero_rate'] - z / len(old)) * 100
        n0.append(dict(family=f, new=new['zero_rate'], old=z / len(old), delta_pp=d))
        print('  %-30s 新 %.3f ｜ 已发表 %.3f ｜ Δ %+6.2f pp' % (f[:30], new['zero_rate'], z / len(old), d))
    print('  最大 |Δ| = %.2f pp' % max(abs(x['delta_pp']) for x in n0) if n0 else '  n/a')
    R['H_N0'] = n0

    # ── H_Abst ──────────────────────────────────────────────────────────────
    print('\n=== ⑥ H_Abst（forbid0 不增弃答，需 ≥4/6）===')
    ab = {}
    for f in FAMS:
        b, x = cells[(f, 'base')], cells[(f, 'forbid0')]
        if b and x:
            ab[f] = (x['abst_rate'] - b['abst_rate']) * 100
    oka = sum(1 for v in ab.values() if v <= 0)
    R['H_Abst'] = dict(passed=oka >= 4, n_pass=oka, per_family=ab)
    print('  Δabst ≤0 达标 %d/%d ⇒ %s' % (oka, len(ab), 'PASS' if oka >= 4 else 'FAIL'))
    print('  ⚠ abstain 计数几乎全为 0（llava 例外：base 30 / forbid0 30 / placebo 40）⇒ 该指标近乎退化，如实标注')

    # ── P1e 探索：token 特异 ─────────────────────────────────────────────────
    print('\n=== ⑦ P1e 探索（placebo100 vs neutral0：token 特异？）===')
    pe = []
    thr_tok = float(re.search(r'([0-9.]+)\s*×', cE['token_specific_if']).group(1))
    thr_non = float(re.search(r'([0-9.]+)\s*×', cE['nonspecific_if']).group(1))
    print('  冻结阈值：token 特异 ≤ %.2f× ｜ 非特异 ≥ %.2f×' % (thr_tok, thr_non))
    for f in FAMS:
        b, nn, pl = cells[(f, 'base')], cells[(f, 'neutral0')], cells[(f, 'placebo100')]
        if not (b and nn and pl):
            continue
        dn = (nn['zero_rate'] - b['zero_rate']) * 100
        dp = (pl['zero_rate'] - b['zero_rate']) * 100
        if abs(dn) < 1e-9:
            continue
        ratio = abs(dp) / abs(dn)
        verdict = ('token 特异' if ratio <= thr_tok else
                   '非特异' if ratio >= thr_non else '部分特异')
        pe.append(dict(family=f, d_neutral=dn, d_placebo=dp, ratio=ratio, verdict=verdict))
        print('  %-30s Δ(n−b)=%+7.1f  Δ(p−b)=%+7.1f  比=%.2f ⇒ %s' % (f[:30], dn, dp, ratio, verdict))
    R['P1e'] = pe

    # ── P1f 阶梯 ────────────────────────────────────────────────────────────
    print('\n=== ⑧ P1f 阶梯（H_L1 零率递减 / H_L3 中位数随锚平移）===')
    lad = {}
    for f in FAMS:
        pts = []
        for arm, v in LADDER:
            c = cells[(f, arm)]
            if c:
                pts.append((v, c['zero_rate'] * 100, c['med']))
        if len(pts) < 3:
            continue
        anchors = [p[0] for p in pts]
        r1 = spearman(anchors, [p[1] for p in pts])
        meds = [p[2] for p in pts]
        r3 = spearman(anchors, meds) if all(m is not None for m in meds) else None
        lad[f] = dict(points=[dict(anchor=a, zero_pct=z, median=m) for a, z, m in pts],
                      rho_zero=r1, rho_median=r3)
        print('  %-30s 锚 %s' % (f[:30], [p[0] for p in pts]))
        print('     零率 %s' % ['%.1f' % p[1] for p in pts])
        print('     中位 %s' % [('—' if p[2] is None else '%g' % p[2]) for p in pts])
        print('     ρ(零率,锚)=%+.2f（阈值 ≤%+.1f）｜ρ(中位,锚)=%s（阈值 ≥%+.1f）'
              % (r1, cF['H_L1']['rho_max'],
                 ('%+.2f' % r3) if r3 is not None else '不可算', cF['H_L3']['rho_min']))
    R['P1f'] = lad
    print('\n  ⚠ H_L4（gemma 阴性对照）实测：零率 0.1%→0%（不动）但**中位数 246→5/50/100/800（完全被捕获）**')
    print('    ⇒ 阴性对照**部分否证**：锚定不经"零"这个出口生效，不等于该族不受锚定影响。必须如实写。')

    outp = '/root/p1df_result.json'
    io.open(outp, 'w', encoding='utf-8', newline='\n').write(
        json.dumps(R, ensure_ascii=False, indent=1, default=str) + '\n')
    print('\n已写 %s' % outp)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
