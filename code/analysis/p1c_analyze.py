# -*- coding: utf-8 -*-
"""p1c_analyze.py —— P1c（生态版：真实图像 × {clean, blur4, down15}）分析，按冻结判据给 H8/H9/H10。

输入：`<dir>/p1b_<treatment>_<family>_<arm>.csv`（treatment ∈ clean|blur4|down15）。
域由 item 前缀区分：`st_a__*`（密集）/ `visdrone__*`（航拍）。
用法：python -u p1c_analyze.py --dir <目录> [--out p1c_result.json] | --selftest
"""
import argparse
import csv
import hashlib
import io
import json
import os
import sys
import tempfile

sys.stdout.reconfigure(encoding='utf-8')
W = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, W)
from p1_analyze import ALIAS, wilson

CRIT = os.path.join(W, 'p1c_criteria_frozen.json')
TREAT = ('clean', 'blur4', 'down15')


def md5f(p):
    return hashlib.md5(io.open(p, 'rb').read()).hexdigest()


def domain_of(item):
    return 'st_a' if item.startswith('st_a__') else ('visdrone' if item.startswith('visdrone__') else '?')


def load(d):
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


def paired(b, p):
    bz = [k for k, r in b.items() if r.get('parse_ok') == '1' and r.get('is_zero') == '1']
    still = sum(1 for k in bz if p.get(k, {}).get('is_zero') == '1')
    lo, hi = wilson(still, len(bz))
    return dict(base_zeros=len(bz), still_zero=still,
                residual=(still / len(bz) if bz else float('nan')), ci=[lo, hi])


def analyze(fam, crit):
    res = dict(criteria_md5=(md5f(CRIT)[:12] if os.path.exists(CRIT) else 'MISSING'),
               per_family={}, verdicts={}, flags=[])
    for f in sorted({k[0] for k in fam}):
        ent = {}
        for t in TREAT:
            if (f, t) not in fam:
                continue
            d = fam[(f, t)]
            b = d.get('base', {})
            entry = dict(all=rate(b), paired=paired(b, d.get('permit', {})))
            for dom in ('st_a', 'visdrone'):
                sub = {k: v for k, v in b.items() if domain_of(k) == dom}
                entry[dom] = rate(sub)
            ent[t] = entry
        res['per_family'][f] = ent
    thr = crit['criteria']
    # H8：密集子集上 blur4 的 base 零率高于 clean
    up, down = [], []
    for f, ent in res['per_family'].items():
        if 'clean' in ent and 'blur4' in ent:
            dn = ent['blur4']['st_a']['rate'] - ent['clean']['st_a']['rate']
            (up if dn > 0 else down).append(f)
    res['verdicts']['H8'] = dict(
        families_blur_above_clean=up, families_not=down,
        need=thr['H8_blur_gate_on_real_images']['threshold']['families_min'],
        passed=len(up) >= thr['H8_blur_gate_on_real_images']['threshold']['families_min'],
        down15_vs_clean={f: (ent.get('down15', {}).get('st_a', {}).get('rate', float('nan'))
                             - ent.get('clean', {}).get('st_a', {}).get('rate', float('nan')))
                         for f, ent in res['per_family'].items() if 'clean' in ent})
    # H9：凡 base 零 ≥10 的格子，permit 残留 ≤5%
    mn = thr['H9_contract_gate']['threshold']['min_base_zeros']
    rmax = thr['H9_contract_gate']['threshold']['residual']
    checked, viol = [], []
    for f, ent in res['per_family'].items():
        for t, v in ent.items():
            if v['paired']['base_zeros'] >= mn:
                checked.append('%s/%s(%d)' % (f, t, v['paired']['base_zeros']))
                if not (v['paired']['residual'] == v['paired']['residual']) or v['paired']['residual'] > rmax:
                    viol.append('%s/%s=%.3f' % (f, t, v['paired']['residual']))
    # ★ 没有任何格子达到 ≥10 个 base 零时，H9 **不可评**——不能默默判"通过"（空断言）。
    res['verdicts']['H9'] = dict(checked=checked, violations=viol,
                                 passed=(None if not checked else not viol),
                                 status=('NOT EVALUABLE（没有 ≥%d 个 base 零的格子）' % mn
                                         if not checked else 'evaluated'))
    # H10：非 Qwen 家族在真实密集图上的零数
    z10 = thr['H10_dense_zeros_beyond_one_lineage']['threshold']['zeros']
    counts = {}
    for f, ent in res['per_family'].items():
        for t, v in ent.items():
            counts['%s/%s/st_a' % (f, t)] = v['st_a']['zeros']
    nonq = {k: v for k, v in counts.items() if not k.startswith('Qwen')}
    res['verdicts']['H10'] = dict(dense_base_zero_counts=counts,
                                  non_qwen_at_or_above=[k for k, v in nonq.items() if v >= z10],
                                  thresholds=z10,
                                  note='只报数量，不设通过阈值')
    for f, ent in res['per_family'].items():
        for t, v in ent.items():
            if v['all']['parse_fail'] / max(1, v['all']['n']) > 0.5:
                res['flags'].append('%s/%s base 解析失败 %.0f%%'
                                    % (f, t, 100.0 * v['all']['parse_fail'] / max(1, v['all']['n'])))
    return res


def _synth(d, mode):
    os.makedirs(d, exist_ok=True)
    base = {'Phi-3.5-Vision': (0.02, 0.30), 'LLaVA-OneVision-7B': (0.00, 0.35), 'Qwen3-VL-8B': (0.02, 0.45)}
    for f, (c, bl) in base.items():
        for t in TREAT:
            # 'nochange' 模式里 blur4 与 clean 同率（用来验证 H8 **能失败**）；
            # 其余模式里 blur4 有效（leak 模式要测的是契约泄漏，不是 blur 失效）。
            r = {'clean': c, 'blur4': (c if mode == 'nochange' else bl), 'down15': c}[t]
            for arm in ('base', 'permit'):
                p = os.path.join(d, 'p1b_%s_%s_%s.csv' % (t, f.replace(' ', '_'), arm))
                with io.open(p, 'w', encoding='utf-8', newline='') as fh:
                    w = csv.writer(fh, lineterminator='\n')
                    w.writerow(['item', 'n', 'r', 'sigma', 'gt', 'pred', 'parse_ok', 'is_zero',
                                'abstain', 'raw', 'latency_s'])
                    for dom, n in (('st_a', 150), ('visdrone', 150)):
                        for i in range(n):
                            zero = (i / float(n)) < r
                            if arm == 'permit':
                                zero = zero and (mode == 'leak' and i % 2 == 0)
                            w.writerow(['%s__img%03d' % (dom, i), 0, 0, 0, 100, 0 if zero else 100,
                                        1, 1 if zero else 0, 0, json.dumps({'count': 0 if zero else 100}), 0.1])
    return d


def selftest():
    crit = json.loads(io.open(CRIT, encoding='utf-8').read())
    print('=' * 100)
    print('■ 阳性对照：blur 有效 / blur 无效 / 契约泄漏 三种数据必须给出**不同**判定')
    print('=' * 100)
    ok = True
    with tempfile.TemporaryDirectory() as t:
        # 'nochange' 里没有任何格子达到 ≥10 个 base 零 ⇒ H9 按设计**不可评**（None），不是"通过"
        for mode, wh8, wh9 in (('blur', True, True), ('nochange', False, None), ('leak', True, False)):
            r = analyze(load(_synth(os.path.join(t, mode), mode)), crit)
            h8, h9 = r['verdicts']['H8']['passed'], r['verdicts']['H9']['passed']
            good = (h8 == wh8) and (h9 == wh9)
            ok &= good
            print('  %-9s：H8=%s（应 %s）｜H9=%s（应 %s）｜H9 检查格=%d｜H10 非 Qwen 密集零 ≥10 的格子 %s ⇒ %s'
                  % (mode, h8, wh8, h9, wh9, len(r['verdicts']['H9']['checked']),
                     r['verdicts']['H10']['non_qwen_at_or_above'], '✓' if good else '✗'))
    print('  结论：%s' % ('★ 判据能失败、判定随数据改变 ✓' if ok else '✗ 判据是空断言'))
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dir')
    ap.add_argument('--out', default=os.path.join(W, 'p1c_result.json'))
    ap.add_argument('--selftest', action='store_true')
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    crit = json.loads(io.open(CRIT, encoding='utf-8').read())
    res = analyze(load(a.dir), crit)
    io.open(a.out, 'w', encoding='utf-8', newline='\n').write(json.dumps(res, ensure_ascii=False, indent=2) + '\n')
    h = md5f(a.out)
    io.open(a.out + '.md5', 'w', encoding='utf-8', newline='\n').write('%s  %s\n' % (h, os.path.basename(a.out)))
    print('判据 md5 %s ｜ 结果 md5 %s' % (res['criteria_md5'], h[:12]))
    for f, ent in res['per_family'].items():
        for t, v in ent.items():
            print('  %-22s %-7s base零=%4d/%4d (%.3f) ｜ st_a零=%3d/%3d ｜ permit残=%s'
                  % (f, t, v['all']['zeros'], v['all']['n_parsed'], v['all']['rate'],
                     v['st_a']['zeros'], v['st_a']['n_parsed'],
                     ('%.3f' % v['paired']['residual']) if v['paired']['residual'] == v['paired']['residual'] else 'n/a'))
    print('  H8', json.dumps(res['verdicts']['H8'], ensure_ascii=False))
    print('  H9', json.dumps(res['verdicts']['H9'], ensure_ascii=False))
    print('  H10', json.dumps(res['verdicts']['H10'], ensure_ascii=False))
    for x in res['flags']:
        print('  [旗标] %s' % x)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
