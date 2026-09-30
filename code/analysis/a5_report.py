# -*- coding: utf-8 -*-
"""A5 报告器：按**冻结判据**（a5_criteria_frozen.json）出 P1/P2/P3 判定 + Wilson 95% CI。

不改判据，只实现冻结文件里已写明的报告纪律：
  - 所有比例给二项 95% CI（Wilson）
  - 跨家族比较只在同一 item 集合上做（配对）；P2 的密集域 vs 航拍域是**不同 item 集**，
    因此给 Newcombe 差值的 CI，并在输出里标注 "unpaired"
  - 预测值 >=1e5 视为异常并剔除
  - 弃答（pred 空且 raw 无弃答词）计入 unparsed，不计入池化 rho

用法：
    python a5_report.py                       # 默认 analysis/e2xt_a800/merged
    python a5_report.py <zero_dir> <nonzero_dir> <out_json>
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
import csv
import glob
import hashlib
import io
import json
import math
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')
DOMS_DENSE = ['st_a', 'ucf']
DOMS_AERIAL = ['visdrone', 'aitod']
DS_ALL = ['st_a', 'st_b', 'ucf', 'visdrone', 'aitod', 'countbench']
ABSTAIN_WORDS = ('abstain', 'cannot_judge', 'no_people')
ANOM = 1e5

# ★ 2026-09-26 修正（"691/3" 事故的**根因**）：
#   P1 的**家族级**累加此前遍历 `DS_ALL`，而它是冻结判据 `design.domains` 的**超集**
#   （多出 `st_b` 与 `countbench`），且**没有任何作用域闸门** ⇒ 那个"恰好带 `countbench` 文件"
#   的家族（锚 `qwen3-vl-32b-awq`）被静默并入，于是家族级 = **五域**、而印出的逐域列 = **四域**，
#   残差 **6 / 2 正是 `countbench`**（它不在冻结设计里，补充材料另有两处明写它被排除）。
#   `countbench` 自己那格是 **2/6 = 33.3% > 30%** ⇒ 若它在范围内就是**域级反例**，
#   所以"排除它"这件事本身是**承重**的，不能只写在散文里。
#   现改为**从冻结判据读** `design.domains`，并断言其 md5 —— 这同时让
#   `reporting.no_post_hoc_change`（"判定脚本只读不改"）第一次真正生效：**本脚本此前从不打开该文件**。
CRIT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'a5_criteria_frozen.json')
CRIT_MD5 = 'eaeafbc4ad4602e0a0f092d1306aea3c'


def load_scope():
    """从**冻结判据**读回作用域域集（P1 家族级口径的唯一权威来源）。"""
    raw = io.open(CRIT_PATH, 'rb').read()
    got = hashlib.md5(raw).hexdigest()
    assert got == CRIT_MD5, \
        '冻结判据 md5 变了（%s ≠ %s）⇒ 停下：这是有意新开一轮，还是文件被改过？' % (got, CRIT_MD5)
    return list(json.loads(raw.decode('utf-8'))['design']['domains'])


DS_SCOPE = load_scope()



def wilson(k, n, z=1.959963985):
    if n == 0:
        return (None, None)
    p = k / float(n)
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def newcombe(k1, n1, k2, n2):
    """两独立比例差 (p1-p2) 的 Newcombe 混合 Wilson CI。"""
    if not n1 or not n2:
        return (None, None)
    l1, u1 = wilson(k1, n1)
    l2, u2 = wilson(k2, n2)
    p1, p2 = k1 / float(n1), k2 / float(n2)
    lo = (p1 - p2) - math.sqrt((p1 - l1) ** 2 + (u2 - p2) ** 2)
    hi = (p1 - p2) + math.sqrt((u1 - p1) ** 2 + (p2 - l2) ** 2)
    return (lo, hi)


def load(p):
    with io.open(p, encoding='utf-8-sig') as f:
        return [r for r in csv.DictReader(f) if '#r' not in str(r.get('item') or '')]


def cls(r):
    raw = str(r.get('raw') or '').lower()
    p = str(r.get('pred') or '').strip()
    for k in ABSTAIN_WORDS:
        if k in raw:
            return k
    if p == '':
        return 'unparsed'
    try:
        v = float(p)
    except ValueError:
        return 'unparsed'
    if v >= ANOM:
        return 'anomaly'
    return 'zero' if v == 0 else 'nonzero'


def parse(fn):
    if not fn.startswith('e1_'):
        return None
    body = fn[3:-4]
    # 非零池文件在 E2 里叫 e1_nz_<fam>_<ds>_<arm>.csv；剥掉 nz_ 以便与零池同键
    if body.startswith('nz_'):
        body = body[3:]
    for ds in DS_ALL:
        i = body.find('_' + ds + '_')
        if i > 0:
            return body[:i], ds, body[i + len(ds) + 2:]
    return None


def tab(d):
    t = {}
    for p in glob.glob(os.path.join(d, '*.csv')):
        k = parse(os.path.basename(p))
        if k:
            t[k] = p
    return t


def col(t, fam, ds, arm):
    p = t.get((fam, ds, arm))
    return {r['item']: cls(r) for r in load(p)} if p else None


def main():
    zd = sys.argv[1] if len(sys.argv) > 1 else RP('analysis', 'e2xt_a800', 'merged')
    nzd = sys.argv[2] if len(sys.argv) > 2 else RP('analysis', 'e2xt_a800', 'nonzero')
    out = sys.argv[3] if len(sys.argv) > 3 else RP('analysis', 'work', 'a5_report.json')
    t = tab(zd)
    tn = tab(nzd)
    fams = sorted(set(k[0] for k in t))
    print('零池文件 %d 个 / 家族 %d 个：%s' % (len(t), len(fams), ', '.join(fams)))
    print('P1 家族级作用域（冻结判据 design.domains，md5 %s）：%s' % (CRIT_MD5[:12], ', '.join(DS_SCOPE)))
    print('  （`DS_ALL` = %s 仅作诊断名单纯列，**不**用于 P1 家族级）' % ', '.join(DS_ALL))
    # ---- 同一 item 集合校验（冻结判据：跨家族比较只在同一 item 集合上做）
    itemchk = {}
    for ds in DS_ALL:
        sets = {}
        for m in fams:
            p = t.get((m, ds, 'base'))
            if p:
                sets[m] = tuple(sorted(r['item'] for r in load(p)))
        if len(sets) < 2:
            continue
        uniq = {}
        for m, s in sets.items():
            uniq.setdefault(len(s), []).append(m)
        itemchk[ds] = {'n_families': len(sets), 'n_ref': len(next(iter(sets.values()))) if sets else 0,
                       'all_equal': len(set(sets.values())) == 1,
                       'per_family_n': {m: len(s) for m, s in sets.items()}}
    if itemchk:
        print('同一 item 集合校验：')
        for ds, v in itemchk.items():
            print('  %-9s 家族 %d 个、n=%s、item 集合完全一致：%s'
                  % (ds, v['n_families'],
                     sorted(set(v['per_family_n'].values())), '是' if v['all_equal'] else '否'))
    # 交集子集（配对用）：跨家族只在**所有家族都有的 item** 上比
    inter = {}
    for ds in DS_ALL:
        sets = []
        for m in fams:
            p = t.get((m, ds, 'base'))
            if p:
                sets.append(set(r['item'] for r in load(p)))
        inter[ds] = set.intersection(*sets) if sets else set()
    if any(inter.values()):
        print('交集子集（配对用）：%s'
              % ', '.join('%s=%d' % (ds, len(inter[ds])) for ds in DS_ALL if inter[ds]))
    print()

    res = {'zero_files': len(t), 'families': {}, 'item_set_check': itemchk, 'anchor_note': None,
           'criteria_md5': CRIT_MD5, 'scope_domains': DS_SCOPE,
           'ds_all_diagnostic_only': DS_ALL}
    rows = []
    for m in fams:
        per = {'model': m, 'domains': {}, 'p1': {}, 'p2': {}, 'p3': {}, 'nonzero_pool': {}}
        # ---- P1：permit 臂下"仍答 0"
        num = den = 0
        perds = {}
        for ds in DS_SCOPE:
            b = col(t, m, ds, 'base')
            p = col(t, m, ds, 'permit')
            if not b or not p:
                continue
            z = [k for k, v in b.items() if v == 'zero']
            if not z:
                perds[ds] = None
                continue
            k = sum(1 for x in z if p.get(x) == 'zero')
            num += k
            den += len(z)
            lo, hi = wilson(k, len(z))
            perds[ds] = {'n_zero': len(z), 'still_zero': k, 'ratio': k / float(len(z)),
                         'ci': [lo, hi]}
            per['domains'][ds] = {
                'n': len(b),
                'zero_n': sum(1 for v in b.values() if v == 'zero'),
                'zero_rate': sum(1 for v in b.values() if v == 'zero') / float(len(b)),
                'unparsed_n': sum(1 for v in b.values() if v == 'unparsed'),
                'anomaly_n': sum(1 for v in b.values() if v == 'anomaly'),
                'base_permit_pair_n': len(z),
                'permit_still_zero': k,
            }
        if den:
            lo, hi = wilson(num, den)
            per['p1'] = {'pooled_n': den, 'still_zero': num, 'ratio': num / float(den),
                         'ci': [lo, hi], 'per_domain': perds}
        # ---- P2：密集域 vs 航拍域 base 出零率
        # 冻结判据的配对纪律 ⇒ 主口径用**交集子集**；同时报全池（若有差异）以便对照。
        def agg(dss, paired=True):
            n = k = 0
            for ds in dss:
                b = col(t, m, ds, 'base')
                if not b:
                    continue
                keys = [x for x in b if (not paired or not inter[ds] or x in inter[ds])]
                n += len(keys)
                k += sum(1 for x in keys if b[x] == 'zero')
            return k, n
        kd, nd = agg(DOMS_DENSE)
        ka, na = agg(DOMS_AERIAL)
        kdf, ndf = agg(DOMS_DENSE, paired=False)
        kaf, naf = agg(DOMS_AERIAL, paired=False)
        if nd and na:
            gap = (kd / float(nd) - ka / float(na)) * 100
            lo, hi = newcombe(kd, nd, ka, na)
            per['p2'] = {'dense': {'k': kd, 'n': nd, 'rate': kd / float(nd),
                                   'ci': list(wilson(kd, nd))},
                         'aerial': {'k': ka, 'n': na, 'rate': ka / float(na),
                                    'ci': list(wilson(ka, na))},
                         'full_pool': {'dense': {'k': kdf, 'n': ndf,
                                                 'rate': (kdf / float(ndf)) if ndf else None},
                                       'aerial': {'k': kaf, 'n': naf,
                                                  'rate': (kaf / float(naf)) if naf else None}},
                         'paired_subset': True,
                         'gap_pp': gap, 'gap_ci_pp': [None if lo is None else lo * 100,
                                                      None if hi is None else hi * 100],
                         'gap_abs_pp': abs(gap),
                         'gap_aerial_minus_dense_pp': -gap,
                         'gap_dense_minus_aerial_pp': gap,
                         'paired': False}
        # ---- P3：permit 的减零方向（家族内 base->permit 同一 item 集，配对）
        b = col(t, m, 'st_a', 'base')
        p = col(t, m, 'st_a', 'permit')
        dirs = []
        for ds in DS_ALL:
            bb = col(t, m, ds, 'base')
            pp = col(t, m, ds, 'permit')
            if not bb or not pp:
                continue
            zb = [k for k, v in bb.items() if v == 'zero']
            if not zb:
                continue
            rb = len(zb) / float(len(bb))
            rp = sum(1 for x in zb if pp.get(x) == 'zero') / float(len(bb))
            dirs.append({'ds': ds, 'base_zero_rate': rb, 'permit_zero_rate_on_base_items': rp,
                         'delta_pp': (rp - rb) * 100})
        per['p3'] = {'per_domain': dirs,
                     'all_negative': bool(dirs) and all(d['delta_pp'] < 0 for d in dirs)}
        # ---- 非零池特异性：base 非零的 item 在 permit/channel 下是否仍是数（而非变弃答）
        nzs = {}
        for ds in DS_ALL:
            bn = col(tn, m, ds, 'base')
            pn = col(tn, m, ds, 'permit')
            cn = col(tn, m, ds, 'channel')
            if not bn:
                continue
            nb = [k for k, v in bn.items() if v == 'nonzero']
            if not nb:
                continue
            row = {'n_nonzero': len(nb)}
            if pn:
                row['permit_still_nonzero'] = sum(1 for x in nb if pn.get(x) == 'nonzero') / float(len(nb))
                row['permit_abstain'] = sum(1 for x in nb if pn.get(x) in ABSTAIN_WORDS) / float(len(nb))
            if cn:
                row['channel_still_nonzero'] = sum(1 for x in nb if cn.get(x) == 'nonzero') / float(len(nb))
            nzs[ds] = row
        per['nonzero_pool'] = nzs
        res['families'][m] = per
        rows.append(per)

    hdr = ('%-28s %6s %7s %16s %9s %9s %10s %10s %6s'
           % ('家族', '仍0_n', '仍0', 'Wilson95%CI', '密集零', '航拍零', '航-密(pp)', '|差|(pp)', '方向'))
    print(hdr)
    print('-' * len(hdr))
    for r in rows:
        p1 = r['p1']
        p2 = r['p2']
        rr = ('%6d %6.3f [%.3f,%.3f]' % (p1['pooled_n'], p1['ratio'], p1['ci'][0], p1['ci'][1])) if p1 else '%6s %6s %16s' % ('—', '—', '—')
        d = ('%9.3f' % p2['dense']['rate']) if p2 else '%9s' % '—'
        a = ('%9.3f' % p2['aerial']['rate']) if p2 else '%9s' % '—'
        g = ('%+10.1f' % p2['gap_aerial_minus_dense_pp']) if p2 else '%10s' % '—'
        ga = ('%10.1f' % p2['gap_abs_pp']) if p2 else '%10s' % '—'
        print('%-28s %s %s %s %s %s %s' % (r['model'], rr, d, a, g, ga,
                                           '负' if r['p3']['all_negative'] else '异常'))

    p1ok = [r['model'] for r in rows if r['p1'] and r['p1']['ratio'] <= 0.05]
    p1bad = [r['model'] for r in rows if r['p1'] and r['p1']['ratio'] > 0.30]
    p1mid = [r['model'] for r in rows if r['p1'] and 0.05 < r['p1']['ratio'] <= 0.30]
    # P2 两种读法都给：冻结文件写"密集域与航拍域之差"，字面是 密-航；而 §11.2 主张的方向是 航-密。
    p2_abs = [r['model'] for r in rows if r['p2'] and r['p2']['gap_abs_pp'] >= 30.0]
    p2_amd = [r['model'] for r in rows if r['p2'] and r['p2']['gap_aerial_minus_dense_pp'] >= 30.0]
    p2_dma = [r['model'] for r in rows if r['p2'] and r['p2']['gap_dense_minus_aerial_pp'] >= 30.0]
    p3ok = [r['model'] for r in rows if r['p3']['all_negative']]
    n = len(rows)
    print()
    print('P1 permit 把"仍答 0"压到 <=5%%：%d/%d 通过（判据 >=5/6）  反例(>30%%)：%s  部分(5-30%%]：%s'
          % (len(p1ok), n, p1bad or '无', p1mid or '无'))
    print('P2 |密集-航拍| >=30 pp：%d/%d（判据 >=5/6）' % (len(p2_abs), n))
    print('   P2 分方向：航-密 >=30 pp 的 %d/%d；密-航 >=30 pp 的 %d/%d（观测方向以"航>密"为主）'
          % (len(p2_amd), n, len(p2_dma), n))
    print('P3 permit 减零方向一致：%d/%d' % (len(p3ok), n))
    if n >= 6:
        need_frac = math.ceil(5 * n / 6.0)
        print('判定（冻结判据写的是"≥5/6 家族"；实到 %d 家族，故同时给两种读法）：' % n)
        print('  按字面"≥5 家族"：P1 %s；P2(|差|) %s'
              % ('通过' if len(p1ok) >= 5 else '不通过',
                 '通过' if len(p2_abs) >= 5 else '不通过'))
        print('  按比例"≥%d/%d 家族"（保守）：P1 %s；P2(|差|) %s'
              % (need_frac, n,
                 '通过' if len(p1ok) >= need_frac else '不通过',
                 '通过' if len(p2_abs) >= need_frac else '不通过'))
    else:
        print('判定：家族数 %d < 6 ⇒ 暂不判定' % n)
    res['verdict'] = {'n_families': n, 'p1_pass': p1ok, 'p1_counterexample': p1bad,
                      'p1_partial': p1mid,
                      'p2_pass_abs': p2_abs, 'p2_pass_aerial_minus_dense': p2_amd,
                      'p2_pass_dense_minus_aerial': p2_dma, 'p3_pass': p3ok,
                      'p1_verdict_literal_ge5': bool(n >= 6 and len(p1ok) >= 5),
                      'p2_verdict_literal_ge5': bool(n >= 6 and len(p2_abs) >= 5),
                      'p1_verdict_fractional': bool(n >= 6 and len(p1ok) >= math.ceil(5 * n / 6.0)),
                      'p2_verdict_fractional': bool(n >= 6 and len(p2_abs) >= math.ceil(5 * n / 6.0)),
                      'note_p2_sign': ('冻结文件的"密集域与航拍域之差"字面为 密-航；'
                                       '实测方向以"航>密"为主（与 E2 §11.2 的两类主张一致），'
                                       '故同时报出两个方向与绝对差。')}
    with io.open(out, 'w', encoding='utf-8') as f:
        f.write(json.dumps(res, ensure_ascii=False, indent=1))
    print('JSON -> %s' % out)


if __name__ == '__main__':
    main()
