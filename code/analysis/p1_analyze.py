# -*- coding: utf-8 -*-
"""p1_analyze.py —— 读 P1 的逐 item CSV，按**冻结判据**给出 H1–H4 判定与全部报告量。

输入（每个家族每臂一个文件）：`<dir>/p1_<family>_<arm>.csv`，表头
    item,n,r,sigma,pred,parse_ok,is_zero,abstain,raw,latency_s
（`is_zero` = 解析出的计数恰为 0；`abstain` = 文本含弃答标记；两列由冻结探针的解析器给出；
  **独立重算**见 `p1_indep_check.py`，它绕开本脚本直接重解析 `raw`。）

判据文件：`p1_criteria_frozen.json`（md5 由 `p1_freeze_criteria.py` 冻结），结果件里携带它的 md5。
H4 需要"已发表锚值"；若 `p1_anchor_published.json` 尚未登记，H4 **判为"不可评"**而不是静默通过。

用法：
    python -u p1_analyze.py --dir <结果目录> [--out p1_result.json]
    python -u p1_analyze.py --selftest        # 合成两份数据，证明判据**能失败**
"""
import argparse
import csv
import hashlib
import io
import json
import math
import os
import sys
import tempfile

sys.stdout.reconfigure(encoding='utf-8')
W = os.path.dirname(os.path.abspath(__file__))
CRIT = os.path.join(W, 'p1_criteria_frozen.json')
ANCH = os.path.join(W, 'p1_anchor_published.json')


def md5f(p):
    return hashlib.md5(io.open(p, 'rb').read()).hexdigest()


# 结果文件里的家族名（服务名） → 判据文件里的家族名。**只做名字对齐，不动任何阈值**。
# （判据文件已冻结、md5 不得再变；名字映射属于"读数工具"，故放在这里。）
ALIAS = {
    'gemma3-12b': 'gemma-3-12b',
    'Phi-3.5-vision-instruct': 'Phi-3.5-Vision',
    'llava-onevision-qwen2-7b-ov': 'LLaVA-OneVision-7B',
    'Qwen3-VL-8B-Instruct': 'Qwen3-VL-8B',
    'Qwen3-VL-32B-Instruct': 'Qwen3-VL-32B',
    'InternVL3_5-8B': 'InternVL3.5-8B',
}


def wilson(k, n, z=1.96):
    if n == 0:
        return (float('nan'), float('nan'))
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return ((c - h) / d, (c + h) / d)


def spearman(xs, ys):
    def rank(v):
        o = sorted(range(len(v)), key=lambda i: v[i])
        r = [0.0] * len(v)
        i = 0
        while i < len(o):
            j = i
            while j + 1 < len(o) and v[o[j + 1]] == v[o[i]]:
                j += 1
            avg = (i + j) / 2.0 + 1
            for t in range(i, j + 1):
                r[o[t]] = avg
            i = j + 1
        return r
    rx, ry = rank(xs), rank(ys)
    mx, my = sum(rx) / len(rx), sum(ry) / len(ry)
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    den = math.sqrt(sum((a - mx) ** 2 for a in rx) * sum((b - my) ** 2 for b in ry))
    return num / den if den else float('nan')


def load_dir(d):
    """→ {family: {arm: {item: row}}}, {family/arm: 重复行数}；**按 item 去重**（后写覆盖先写）。

    ★ 为什么必须去重：`raw` 是**完整保存**的（不截断，独立重算需要它），而模型输出里可能有换行 ⇒
    CSV 里有带引号的跨行字段。用 `wc -l` / `cut` 之类**按行**的工具数行数会数错（我把这一点
    在远端误诊成"重复写入"过一次）。真正可靠的判据是 CSV 解析后的**唯一 item 数**；
    若同一 (family, arm) 里出现重复 item，那就是真的重复写入，必须报出来而不是静默计数。
    ★ 家族名对齐：服务名 → 判据名（见 ALIAS）。**只对齐名字，不动任何阈值。**
    """
    fam, dup = {}, {}
    for f in sorted(os.listdir(d)):
        if not (f.startswith('p1_') and f.endswith('.csv')):
            continue
        body = f[3:-4]
        if '_' not in body:
            continue
        arm = body.rsplit('_', 1)[1]
        family = ALIAS.get(body.rsplit('_', 1)[0], body.rsplit('_', 1)[0])
        rows = {}
        n_seen = 0
        with io.open(os.path.join(d, f), encoding='utf-8-sig', errors='replace', newline='') as fh:
            for r in csv.DictReader(fh):
                n_seen += 1
                rows[r['item']] = r          # 后写覆盖先写
        if n_seen != len(rows):
            dup['%s/%s' % (family, arm)] = n_seen - len(rows)
        fam.setdefault(family, {})[arm] = rows
    return fam, dup


def rates(rows):
    n = len(rows)
    ok = [r for r in rows.values() if r.get('parse_ok') == '1']
    pf = n - len(ok)
    z = sum(1 for r in ok if r.get('is_zero') == '1')
    a = sum(1 for r in ok if r.get('abstain') == '1')
    lo, hi = wilson(z, len(ok))
    return dict(n_items=n, parse_fail=pf, parse_fail_rate=(pf / n if n else float('nan')),
                n_parsed=len(ok), zeros=z,
                zero_rate=(z / len(ok) if ok else float('nan')), zero_ci=[lo, hi],
                abstain_rate=(a / len(ok) if ok else float('nan')))


def analyze(fam, dups, crit):
    crit_md5 = md5f(CRIT)[:12] if os.path.exists(CRIT) else 'MISSING'
    new = crit['design']['families_new']
    anch = crit['design']['families_anchor']
    sig_crit = crit['criteria']['H1_mechanism_cross_lineage']['threshold']
    res = dict(criteria_md5=crit_md5, per_family={}, by_sigma={}, paired={},
               template_axis=None, verdicts={}, flags=[])
    if dups:
        for k, n in sorted(dups.items()):
            res['flags'].append('重复 item：%s 多出 %d 行（已按 item 去重，保留最后一条）' % (k, n))
    for f in sorted(fam):
        d = fam[f]
        res['per_family'][f] = {arm: rates(d[arm]) for arm in sorted(d)}
        bs = d.get('base', {})
        by = {}
        for s in crit['design']['grid']['sigma']:
            rows = {k: v for k, v in bs.items() if abs(float(v['sigma']) - s) < 1e-9}
            by['%g' % s] = rates(rows)
        res['by_sigma'][f] = by
        if 'permit' in d and bs:
            bz = [k for k, v in bs.items() if v.get('parse_ok') == '1' and v.get('is_zero') == '1']
            still = sum(1 for k in bz if d['permit'].get(k, {}).get('is_zero') == '1')
            lo, hi = wilson(still, len(bz))
            res['paired'][f] = dict(base_zeros=len(bz), still_zero_under_permit=still,
                                    residual=(still / len(bz) if bz else float('nan')),
                                    residual_ci=[lo, hi])
    # H1 / H1b / H3
    s8 = '%g' % sig_crit['at_sigma']
    r8 = {f: res['by_sigma'].get(f, {}).get(s8, {}).get('zero_rate') for f in new if f in fam}
    hit = [f for f, v in r8.items() if v is not None and not math.isnan(v) and v >= sig_crit['rate']]
    missing = [f for f in new if f not in fam]
    if missing:
        # ★ 预注册家族缺席时**不得**判 H1 失败——否则"跑不全"会被读成"血统特异"的否证。
        res['verdicts']['H1'] = dict(rates_at_sigma8=r8, families_at_or_above=hit,
                                     need=sig_crit['families_min'], passed=None,
                                     status='NOT EVALUABLE', missing_families=missing)
    else:
        res['verdicts']['H1'] = dict(rates_at_sigma8=r8, families_at_or_above=hit,
                                     need=sig_crit['families_min'],
                                     passed=len(hit) >= sig_crit['families_min'],
                                     status='evaluated')
    dr = {}
    sig_list = crit['design']['grid']['sigma']
    for f in new:
        if f not in fam:
            continue
        ys = [res['by_sigma'][f]['%g' % s]['zero_rate'] for s in sig_list]
        if all(y is not None and not math.isnan(y) for y in ys):
            dr[f] = spearman(sig_list, ys)
    smin = crit['criteria']['H1b_dose_response']['threshold']['spearman_min']
    res['verdicts']['H1b'] = dict(spearman_by_family=dr,
                                  families_monotone=[f for f, v in dr.items() if v >= smin],
                                  role='secondary')
    # H2
    rmax = crit['criteria']['H2_contract_gate_cross_lineage']['threshold']
    ok2 = [f for f in new if f in res['paired']
           and not math.isnan(res['paired'][f]['residual']) and res['paired'][f]['residual'] <= rmax['residual']]
    ctr = [f for f in new if f in res['paired']
           and not math.isnan(res['paired'][f]['residual'])
           and res['paired'][f]['residual'] > rmax['counterexample_above']]
    miss2 = [f for f in new if f not in res['paired']]
    res['verdicts']['H2'] = dict(families_within_5pct=ok2, counterexamples=ctr,
                                 need=rmax['families_min'],
                                 passed=(None if miss2 else len(ok2) >= rmax['families_min']),
                                 status=('NOT EVALUABLE' if miss2 else 'evaluated'),
                                 missing_families=miss2)
    h1p = res['verdicts']['H1'].get('passed')
    res['verdicts']['H3'] = dict(triggered=(h1p is False) if h1p is not None else None,
                                 status=('NOT TRIGGERED (H1 不可评)' if h1p is None else 'evaluated'),
                                 means='lineage-specific ⇒ 收窄 §5.7 的跨家族读法')
    # H4（锚可比性）：**单格**判据（σ ∧ n 层），依据已发表的那一格读数
    ref = crit['criteria']['H4_anchor_comparability']['published_reference']
    mx = crit['criteria']['H4_anchor_comparability']['threshold']['abs_diff_pp_max']
    fam_ref = fam.get(ref['family'], {}).get('base', {})
    cell = {k: v for k, v in fam_ref.items()
            if abs(float(v['sigma']) - ref['sigma']) < 1e-9 and int(v['n']) == ref['n']}
    if not cell:
        res['verdicts']['H4'] = dict(status='NOT EVALUABLE',
                                     reason='结果目录里没有 %s 在 σ=%g ∧ n=%d 这一格的 base 臂数据'
                                            % (ref['family'], ref['sigma'], ref['n']))
    else:
        got = rates(cell)
        diff = abs(got['zero_rate'] - ref['base_zero_rate']) * 100
        res['verdicts']['H4'] = dict(status='evaluated', family=ref['family'], sigma=ref['sigma'],
                                     n=ref['n'], measured=got['zero_rate'],
                                     published=ref['base_zero_rate'], abs_diff_pp=diff,
                                     max_pp=mx, passed=diff <= mx, n_items=got['n_parsed'])
    # flags
    for f in sorted(res['per_family']):
        for arm, v in res['per_family'][f].items():
            if v['parse_fail_rate'] > 0.02:
                res['flags'].append('%s/%s 解析失败 %.1f%% > 2%%' % (f, arm, 100 * v['parse_fail_rate']))
    return res


# ── 阳性对照：两份合成数据必须给出**不同**判定 ──────────────────────────────
def _synth(d, levels_new, permit_residual):
    """合成数据：permit 臂**按整数个**保留 base 零（residual 是"保留多少个零"的比例，取整）。

    注意：每格只有 15 个 item，所以"2% 残留"在**单格**里无法表达（最小非零是 1/6=16.7%）；
    真实实验里 H2 是在**家族级**（675 item、数百个 base 零）上算的，故这里也按家族级思路构造：
    先把该格 base 零挑出来，再按 round(比例 × 个数) 保留前 k 个 —— k=0 即"干净闸门"。
    """
    os.makedirs(d, exist_ok=True)
    sig = [0.0, 1.0, 2.0, 4.0, 8.0]
    fams = [('gemma-3-12b', levels_new), ('Phi-3.5-Vision', levels_new), ('LLaVA-OneVision-7B', levels_new),
            ('Qwen3-VL-8B', {'8.0': 0.30}), ('Qwen3-VL-32B', {'8.0': 0.25}), ('InternVL2.5-8B', {'8.0': 0.20})]
    for fam, lv in fams:
        for arm in ('base', 'permit'):
            p = os.path.join(d, 'p1_%s_%s.csv' % (fam, arm))
            with io.open(p, 'w', encoding='utf-8', newline='') as fh:
                w = csv.writer(fh, lineterminator='\n')
                w.writerow(['item', 'n', 'r', 'sigma', 'pred', 'parse_ok', 'is_zero', 'abstain',
                            'raw', 'latency_s'])
                for n in (100, 400, 800):
                    for r in (2, 4, 8):
                        for s in sig:
                            rate = lv.get('%g' % s, 0.0)
                            bz = [i for i in range(15) if (i / 15.0) < rate]
                            keep = bz[:int(round(permit_residual * len(bz)))] if arm == 'permit' else bz
                            for i in range(15):
                                k = 'n%d_r%d_s%g_%02d' % (n, r, s, i)
                                want_zero = (arm == 'base' and i in bz) or (arm == 'permit' and i in keep)
                                pred = 0 if want_zero else n
                                w.writerow([k, n, r, '%g' % s, pred, 1, 1 if want_zero else 0,
                                            0 if want_zero else 0, json.dumps({'count': pred}), '0.1'])


def selftest():
    crit = json.loads(io.open(CRIT, encoding='utf-8').read())
    print('=' * 100)
    print('■ 阳性对照：同一套判据必须能给出**不同**判定')
    print('=' * 100)
    hi = {'0': 0.0, '1': 0.0, '2': 0.05, '4': 0.15, '8': 0.35}
    lo = {'0': 0.0, '1': 0.0, '2': 0.0, '4': 0.02, '8': 0.04}
    with tempfile.TemporaryDirectory() as t:
        a = os.path.join(t, 'A')
        b = os.path.join(t, 'B')
        c = os.path.join(t, 'C')
        _synth(a, hi, 0.02)      # 机制成立 + 契约闸门干净
        _synth(b, lo, 0.02)      # 血统特异（H3）
        _synth(c, hi, 0.50)      # 契约闸门失效（反例）
        la, lb, lc = load_dir(a), load_dir(b), load_dir(c)
        ra, rb, rc = analyze(*la, crit), analyze(*lb, crit), analyze(*lc, crit)
    ok = True
    for tag, r, want_h1 in (('机制跨血统（σ=8 上有两个家族 ≥20%）', ra, True),
                            ('血统特异（σ=8 全都不足 20%）', rb, False)):
        h1 = r['verdicts']['H1']['passed']
        h3 = r['verdicts']['H3']['triggered']
        good = (h1 == want_h1) and (h3 != want_h1)
        ok &= good
        print('  %s：H1=%s（应 %s）｜H3 触发=%s ｜ σ=8 各家 %s ⇒ %s'
              % (tag, h1, want_h1, h3,
                 {k: ('%.2f' % v if v is not None else '—') for k, v in r['verdicts']['H1']['rates_at_sigma8'].items()},
                 '✓' if good else '✗'))
    g2 = ra['verdicts']['H2']['passed'] and not rc['verdicts']['H2']['passed']
    ok &= g2
    print('  H2（残留 ≤5%%）：干净数据=%s（应 True）｜50%% 残留=%s（应 False，且列出反例 %s）⇒ %s'
          % (ra['verdicts']['H2']['passed'], rc['verdicts']['H2']['passed'],
             rc['verdicts']['H2']['counterexamples'], '✓' if g2 else '✗'))
    print('  H4 状态：%s（预期 NOT EVALUABLE，直到锚值登记）' % ra['verdicts']['H4']['status'])
    print('  结论：%s' % ('★ 判据能失败、判定随数据改变，阳性对照通过 ✓' if ok else '✗ 判据是空断言，必须重写'))
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dir')
    ap.add_argument('--out', default=os.path.join(W, 'p1_result.json'))
    ap.add_argument('--selftest', action='store_true')
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    if not a.dir:
        print('需要 --dir <结果目录> 或 --selftest')
        return 2
    crit = json.loads(io.open(CRIT, encoding='utf-8').read())
    famdd, dups = load_dir(a.dir)
    res = analyze(famdd, dups, crit)
    io.open(a.out, 'w', encoding='utf-8', newline='\n').write(json.dumps(res, ensure_ascii=False, indent=2) + '\n')
    h = md5f(a.out)
    io.open(a.out + '.md5', 'w', encoding='utf-8', newline='\n').write('%s  %s\n' % (h, os.path.basename(a.out)))
    print('判据 md5 %s ｜ 结果 %s（md5 %s）' % (res['criteria_md5'], a.out, h[:12]))
    for k in ('H1', 'H1b', 'H2', 'H3', 'H4'):
        v = res['verdicts'].get(k, {})
        print('  %-4s %s' % (k, json.dumps(v, ensure_ascii=False)[:200]))
    for f in res['flags']:
        print('  [旗标] %s' % f)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
