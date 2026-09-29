# -*- coding: utf-8 -*-
"""p1b_analyze.py —— P1b（模板轴）的分析：按冻结判据给 H5/H6/H7。

输入：目录下 `p1b_<tag>_<family>_<arm>.csv`（tag ∈ native|sys），由 `p1_probe.py --tag` 产出。
判据：`p1b_criteria_frozen.json`（跑之前冻结；结果件携带其 md5）。
用法：python -u p1b_analyze.py --dir <目录> [--out p1b_result.json] | --selftest
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
sys.path.insert(0, W)
from p1_analyze import ALIAS, wilson  # 复用同一套 Wilson 区间与家族名对齐

CRIT = os.path.join(W, 'p1b_criteria_frozen.json')


def md5f(p):
    return hashlib.md5(io.open(p, 'rb').read()).hexdigest()


def load(d):
    """→ {(family, tag): {arm: {item: row}}}"""
    out = {}
    for f in sorted(os.listdir(d)):
        if not (f.startswith('p1b_') and f.endswith('.csv')):
            continue
        body = f[4:-4]
        tag, rest = body.split('_', 1)
        fam_raw, arm = rest.rsplit('_', 1)
        fam = ALIAS.get(fam_raw, fam_raw)
        rows = {}
        with io.open(os.path.join(d, f), encoding='utf-8-sig', errors='replace', newline='') as fh:
            for r in csv.DictReader(fh):
                rows[r['item']] = r
        out.setdefault((fam, tag), {})[arm] = rows
    return out


def rate(rows):
    ok = [r for r in rows.values() if r.get('parse_ok') == '1']
    z = sum(1 for r in ok if r.get('is_zero') == '1')
    lo, hi = wilson(z, len(ok))
    return dict(n=len(rows), n_parsed=len(ok), zeros=z,
                rate=(z / len(ok) if ok else float('nan')), ci=[lo, hi],
                parse_fail=len(rows) - len(ok))


def paired(base_rows, permit_rows):
    bz = [k for k, r in base_rows.items() if r.get('parse_ok') == '1' and r.get('is_zero') == '1']
    still = sum(1 for k in bz if permit_rows.get(k, {}).get('is_zero') == '1')
    lo, hi = wilson(still, len(bz))
    return dict(base_zeros=len(bz), still_zero=still,
                residual=(still / len(bz) if bz else float('nan')), ci=[lo, hi])


def analyze(fam, crit):
    try:
        cm = md5f(CRIT)[:12]
    except Exception:
        cm = 'MISSING'
    res = dict(criteria_md5=cm, per_family={}, verdicts={}, flags=[])
    for f in sorted({k[0] for k in fam}):
        ent = {}
        for tag in ('native', 'sys'):
            if (f, tag) not in fam:
                continue
            d = fam[(f, tag)]
            ent[tag] = dict(base=rate(d.get('base', {})), permit=rate(d.get('permit', {})),
                            paired=paired(d.get('base', {}), d.get('permit', {})))
        res['per_family'][f] = ent
    thr = crit['criteria']
    # H5：两种模板下 permit 残留都 ≤5%
    ok5, bad5 = [], []
    for f, ent in res['per_family'].items():
        if 'native' not in ent or 'sys' not in ent:
            continue
        rn, rs = ent['native']['paired']['residual'], ent['sys']['paired']['residual']
        okn = (rn == rn and rn <= thr['H5_gate_survives_template_change']['threshold']['residual']) or (rn != rn)
        oks = (rs == rs and rs <= thr['H5_gate_survives_template_change']['threshold']['residual']) or (rs != rs)
        (ok5 if (okn and oks) else bad5).append(f)
    res['verdicts']['H5'] = dict(families_both_templates_ok=ok5, failing=bad5,
                                 need=thr['H5_gate_survives_template_change']['threshold']['families_min'],
                                 passed=len(ok5) >= thr['H5_gate_survives_template_change']['threshold']['families_min'])
    # H6：模板对绝对率的移动
    d6 = {}
    for f, ent in res['per_family'].items():
        if 'native' in ent and 'sys' in ent:
            d6[f] = (ent['sys']['base']['rate'] - ent['native']['base']['rate']) * 100
    fo = thr['H6_template_effect_quantified']['threshold']['first_order_pp']
    res['verdicts']['H6'] = dict(delta_base_zero_rate_pp=d6,
                                 first_order_families=[f for f, v in d6.items() if abs(v) >= fo],
                                 first_order_pp=fo)
    # H7：交互是否可测（sys 下 base 零率是否 ≥20%）
    mn = thr['H7_interaction_measurable']['threshold']['base_zero_rate_min']
    meas, notm = [], []
    for f, ent in res['per_family'].items():
        if 'sys' in ent:
            (meas if ent['sys']['base']['rate'] >= mn else notm).append(f)
    res['verdicts']['H7'] = dict(interaction_measurable=meas, not_measurable=notm,
                                 base_zero_rate_min=mn,
                                 note='不可测 = 该家族在 sys 下没有零可供门控，不得记作"无交互"')
    for f, ent in res['per_family'].items():
        for tag, v in ent.items():
            if v['permit']['parse_fail'] / max(1, v['permit']['n']) > 0.02:
                res['flags'].append('%s/%s permit 解析失败 %.1f%%（散文式拒答，属预期）'
                                    % (f, tag, 100.0 * v['permit']['parse_fail'] / max(1, v['permit']['n'])))
    return res


def _synth(d, mode):
    os.makedirs(d, exist_ok=True)
    fams = {'Phi-3.5-Vision': 0.34, 'LLaVA-OneVision-7B': 0.43, 'Qwen3-VL-8B': 0.43}
    for f, r0 in fams.items():
        for tag in ('native', 'sys'):
            r = r0 if (mode == 'ok' or tag == 'native') else (0.05 if mode == 'suppress' else r0)
            for arm in ('base', 'permit'):
                p = os.path.join(d, 'p1b_%s_%s_%s.csv' % (tag, f.replace(' ', '_'), arm))
                with io.open(p, 'w', encoding='utf-8', newline='') as fh:
                    w = csv.writer(fh, lineterminator='\n')
                    w.writerow(['item', 'n', 'r', 'sigma', 'gt', 'pred', 'parse_ok', 'is_zero',
                                'abstain', 'raw', 'latency_s'])
                    for i in range(135):
                        bz = (i / 135.0) < r
                        if arm == 'permit':
                            # 'leak' 模式下 permit 保留约一半的 base 零（否则 1/45 = 2.2% 根本不算泄漏）
                            zero = bz and (i % 2 == 0) if mode == 'leak' else False
                        else:
                            zero = bz
                        w.writerow(['n100_r2_s8_%03d' % i, 0, 0, 8, 0, 0 if zero else 100, 1,
                                    1 if zero else 0, 0, json.dumps({'count': 0 if zero else 100}), 0.1])
    return d


def selftest():
    crit = json.loads(io.open(CRIT, encoding='utf-8').read())
    print('=' * 100)
    print('■ 阳性对照：三种合成数据必须给出**不同**判定')
    print('=' * 100)
    ok = True
    with tempfile.TemporaryDirectory() as t:
        for mode, want_h5 in (('ok', True), ('suppress', True), ('leak', False)):
            d = _synth(os.path.join(t, mode), mode)
            r = analyze(load(d), crit)
            h5 = r['verdicts']['H5']['passed']
            meas = len(r['verdicts']['H7']['interaction_measurable'])
            good = (h5 == want_h5)
            ok &= good
            print('  %-9s：H5=%s（应 %s）｜可测家族数=%d｜Δ(sys) pp=%s ⇒ %s'
                  % (mode, h5, want_h5, meas,
                     {k: round(v, 1) for k, v in r['verdicts']['H6']['delta_base_zero_rate_pp'].items()},
                     '✓' if good else '✗'))
    print('  结论：%s' % ('★ 判据能失败、判定随数据改变 ✓' if ok else '✗ 判据是空断言'))
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dir')
    ap.add_argument('--out', default=os.path.join(W, 'p1b_result.json'))
    ap.add_argument('--selftest', action='store_true')
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    crit = json.loads(io.open(CRIT, encoding='utf-8').read())
    res = analyze(load(a.dir), crit)
    io.open(a.out, 'w', encoding='utf-8', newline='\n').write(json.dumps(res, ensure_ascii=False, indent=2) + '\n')
    h = md5f(a.out)
    io.open(a.out + '.md5', 'w', encoding='utf-8', newline='\n').write('%s  %s\n' % (h, os.path.basename(a.out)))
    print('判据 md5 %s ｜ 结果 %s（md5 %s）' % (res['criteria_md5'], a.out, h[:12]))
    for f, ent in res['per_family'].items():
        line = []
        for tag in ('native', 'sys'):
            if tag in ent:
                line.append('%s: base=%.3f (%d/%d) permit残=%s' % (
                    tag, ent[tag]['base']['rate'], ent[tag]['base']['zeros'], ent[tag]['base']['n_parsed'],
                    ('%.3f' % ent[tag]['paired']['residual']) if ent[tag]['paired']['residual'] == ent[tag]['paired']['residual'] else 'n/a'))
        print('  %-22s %s' % (f, ' ｜ '.join(line)))
    print('  H5', json.dumps(res['verdicts']['H5'], ensure_ascii=False))
    print('  H6', json.dumps(res['verdicts']['H6'], ensure_ascii=False))
    print('  H7', json.dumps(res['verdicts']['H7'], ensure_ascii=False))
    for x in res['flags']:
        print('  [旗标] %s' % x)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
