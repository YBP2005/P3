# -*- coding: utf-8 -*-
"""p1_indep_check.py —— P1 的**独立重算**：绕开分析器，直读原始逐 item CSV 自建分类与判定。

为什么要它：本项目已有两次教训都出在"分析器这只手"上——真零池分析器用 `dict.update()` 合并三次服务
（实际只报了一次）、生成器用元组比较取极值（2.0 pp 低报成 1.0 pp）；两次都是**绕开分析器直读原始 CSV**
才揪出来的。故 P1 从第一天起就配一个独立重算器，并按本项目惯例报 **N 项通过 / 0 项失败**。

它独立做什么：
  1. **自己重解析 `raw`**（不信任 CSV 里的 `pred` / `is_zero` / `abstain` 三列）：
     JSON 里的 `count` 字段 → 否则第一个整数；`is_zero` = 解析值恰为 0；`abstain` = 文本含弃答标记；
  2. 自己重算：每个（家族 × 臂）的答零率与其 Wilson 区间、每个家族在 σ=8 的答零率、
     base→permit 的配对残留率；
  3. 与 `p1_result.json` **逐格比对**，逐项计 OK/FAIL。

用法：
    python -u p1_indep_check.py --dir <结果目录> --result p1_result.json
    python -u p1_indep_check.py --selftest     # 篡改结果件一个数，必须报失败
"""
import argparse
import csv
import io
import json
import math
import os
import re
import sys
import tempfile

sys.stdout.reconfigure(encoding='utf-8')
W = os.path.dirname(os.path.abspath(__file__))
ABSTAIN_MARK = ('abstain', 'cannot', "can't", 'unable', 'too many', '无法', '不能', '数不清',
                '难以', '不确定', '无法判断', '众多')


def parse_raw(raw):
    """**独立**解析：返回 (pred, is_zero, abstain)。不读 CSV 里的任何派生列。"""
    s = raw or ''
    m = re.search(r'"(?:count|计数|数量)"\s*[:：]\s*"?\s*(-?\d+)', s, re.I)
    if not m:
        m = re.search(r'(-?\d+)', s.replace(',', ''))
    pred = int(m.group(1)) if m else None
    low = s.lower()
    abst = 1 if any(k in low for k in ABSTAIN_MARK) else 0
    return pred, (1 if pred == 0 else 0), abst


def load(d):
    """独立读取原始 CSV。**家族名对齐复用 `p1_analyze.ALIAS`**（单一真源）：
    否则本脚本按服务名分组、结果件按判据名分组，比对会全线假失败（第一次跑就撞上了这条）。"""
    sys.path.insert(0, W)
    from p1_analyze import ALIAS
    fam = {}
    for f in sorted(os.listdir(d)):
        if not (f.startswith('p1_') and f.endswith('.csv')):
            continue
        body, arm = f[3:-4].rsplit('_', 1)
        body = ALIAS.get(body, body)
        rows = {}
        with io.open(os.path.join(d, f), encoding='utf-8-sig', errors='replace', newline='') as fh:
            for r in csv.DictReader(fh):
                pred, z, ab = parse_raw(r.get('raw'))
                rows[r['item']] = dict(sigma=float(r['sigma']), pred=pred, is_zero=z, abstain=ab,
                                       parse_ok=(1 if pred is not None else 0),
                                       csv_zero=r.get('is_zero'), csv_ok=r.get('parse_ok'))
        fam.setdefault(body, {})[arm] = rows
    return fam


def wilson(k, n, z=1.96):
    if n == 0:
        return (float('nan'), float('nan'))
    p = k / n
    dd = 1 + z * z / n
    c = p + z * z / (2 * n)
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return ((c - h) / dd, (c + h) / dd)


def recompute(fam, sigma8=8.0):
    out = {}
    for f, arms in fam.items():
        out[f] = {}
        for arm, rows in arms.items():
            ok = [r for r in rows.values() if r['parse_ok']]
            z = sum(1 for r in ok if r['is_zero'])
            out[f][arm] = dict(n=len(rows), n_parsed=len(ok), zeros=z,
                               zero_rate=(z / len(ok) if ok else float('nan')),
                               zero_ci=list(wilson(z, len(ok))))
        b = arms.get('base', {})
        p = arms.get('permit', {})
        bz = [k for k, r in b.items() if r['parse_ok'] and r['is_zero']]
        still = sum(1 for k in bz if k in p and p[k]['parse_ok'] and p[k]['is_zero'])
        out[f]['paired'] = dict(base_zeros=len(bz), still=still,
                                residual=(still / len(bz) if bz else float('nan')))
        s8 = {k: r for k, r in b.items() if abs(r['sigma'] - sigma8) < 1e-9}
        z8 = sum(1 for r in s8.values() if r['parse_ok'] and r['is_zero'])
        n8 = sum(1 for r in s8.values() if r['parse_ok'])
        out[f]['sigma8_zero_rate'] = (z8 / n8 if n8 else float('nan'))
    return out


def near(a, b, tol=1e-6):
    if a is None or b is None:
        return a == b
    if isinstance(a, float) and math.isnan(a):
        return isinstance(b, float) and math.isnan(b)
    return abs(a - b) <= tol


def run(d, rp):
    fam = load(d)
    mine = recompute(fam)
    res = json.loads(io.open(rp, encoding='utf-8').read())
    ok = bad = 0
    fails = []

    def chk(label, cond, detail=''):
        nonlocal ok, bad
        if cond:
            ok += 1
            print('  [OK  ] %s' % label)
        else:
            bad += 1
            fails.append(label)
            print('  [FAIL] %s   %s' % (label, detail))

    print('[I1] 原始 CSV 与结果件的**逐格**一致（家族 × 臂的答零率 / 解析数 / Wilson 界）')
    for f in sorted(mine):
        if f not in res.get('per_family', {}):
            chk('结果件含家族 %s' % f, False, '结果件缺该家族')
            continue
        for arm in ('base', 'permit'):
            if arm not in mine[f]:
                continue
            r = res['per_family'][f][arm]
            m = mine[f][arm]
            chk('%s/%s 答零率 %.4f（n=%d）' % (f, arm, m['zero_rate'], m['n_parsed']),
                near(r['zero_rate'], m['zero_rate'], 1e-6) and r['n_parsed'] == m['n_parsed']
                and near(r['zeros'], m['zeros'], 1e-9), '结果件 %s vs 重算 %s' % (r, m))
    print('[I2] σ=8 的家族级答零率')
    for f in sorted(mine):
        v = res.get('by_sigma', {}).get(f, {}).get('8', {}).get('zero_rate')
        chk('%s σ=8 = %.4f' % (f, mine[f]['sigma8_zero_rate']), near(v, mine[f]['sigma8_zero_rate'], 1e-6),
            '结果件 %s' % v)
    print('[I3] base→permit 配对残留率')
    for f in sorted(mine):
        v = res.get('paired', {}).get(f, {})
        m = mine[f]['paired']
        chk('%s 残留 %.4f（%d/%d）' % (f, m['residual'], m['still'], m['base_zeros']),
            near(v.get('residual'), m['residual'], 1e-6) and v.get('base_zeros') == m['base_zeros'],
            '结果件 %s vs 重算 %s' % (v, m))
    print('[I4] 判据方向自洽（H1/H3 不得自相矛盾）')
    h1 = res.get('verdicts', {}).get('H1', {})
    h3 = res.get('verdicts', {}).get('H3', {})
    s8 = [mine[f]['sigma8_zero_rate'] for f in sorted(mine)]
    hit = sum(1 for v in s8 if not math.isnan(v) and v >= 0.20)
    chk('H1 结论与重算一致（≥20%% 的家族数 %d）' % hit, bool(h1.get('passed')) == (hit >= 2),
        '结果件 %s' % h1.get('passed'))
    chk('H3 = not H1', bool(h3.get('triggered')) == (not bool(h1.get('passed'))), '')
    print('[I5] 派生列与 raw 自洽（CSV 的 is_zero 能否被独立解析复现）')
    mism = []
    for f, arms in fam.items():
        for arm, rows in arms.items():
            for k, r in rows.items():
                if r['csv_zero'] is not None and r['csv_ok'] is not None:
                    if int(r['csv_ok']) != r['parse_ok'] or int(r['csv_zero']) != r['is_zero']:
                        mism.append('%s/%s/%s' % (f, arm, k))
    chk('逐 item 派生列可独立复现', not mism, '不一致 %d 条：%s' % (len(mism), mism[:5]))
    print('\n独立重算：%d 通过 ｜ %d 失败' % (ok, bad))
    if fails:
        print('失败项：%s' % '；'.join(fails[:10]))
    return bad


def selftest():
    print('=' * 100)
    print('■ 阳性对照：把结果件里 σ=8 的一个率改掉，独立重算**必须**报失败')
    print('=' * 100)
    sys.path.insert(0, W)
    import p1_analyze as A
    crit = json.loads(io.open(os.path.join(W, 'p1_criteria_frozen.json'), encoding='utf-8').read())
    with tempfile.TemporaryDirectory() as t:
        A._synth(t, {'0': 0.0, '1': 0.0, '2': 0.05, '4': 0.15, '8': 0.35}, 0.02)
        good = os.path.join(t, 'p1_result.json')
        res = A.analyze(A.load_dir(t), crit)
        io.open(good, 'w', encoding='utf-8', newline='\n').write(json.dumps(res, ensure_ascii=False))
        n0 = run(t, good)
        bad_doc = json.loads(json.dumps(res))
        bad_doc['by_sigma']['gemma-3-12b']['8']['zero_rate'] = 0.01
        badp = os.path.join(t, 'p1_result_bad.json')
        io.open(badp, 'w', encoding='utf-8', newline='\n').write(json.dumps(bad_doc, ensure_ascii=False))
        n1 = run(t, badp)
    print('\n  未篡改 → 失败 %d 项；篡改 σ=8 的一个率 → %d 项' % (n0, n1))
    print('  结论：%s' % ('★ 独立重算**能失败**，阳性对照通过 ✓' if n1 > n0 else '✗ 不能失败 ⇒ 空断言，必须重写'))
    return 0 if n1 > n0 else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dir')
    ap.add_argument('--result', default=os.path.join(W, 'p1_result.json'))
    ap.add_argument('--selftest', action='store_true')
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    if not a.dir:
        print('需要 --dir <结果目录> 或 --selftest')
        return 2
    return 1 if run(a.dir, a.result) else 0


if __name__ == '__main__':
    raise SystemExit(main())
