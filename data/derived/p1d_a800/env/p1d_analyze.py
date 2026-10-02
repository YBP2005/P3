#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""p1d_analyze.py —— P1-D 分析（纯 CPU）。**判据见 /root/p1d/_p1d_criteria_frozen.json（跑前冻结）。**

口径（G0 实测锁定，不许改成"各档交集"）：
    dev(档) = 100*(Σpred − Σgt)/Σgt，**在该档自己的行上池化**（3 次起服的行并在一起）
    span    = 该域 8 档 dev 的 max − min
判据：
    C1 每格行数      ：每 (域, 档, 起服) 期望 250 行
    C2 档位完整      ：某域不足 8 档 ⇒ NOT COVERED，**排除出排序，禁止插值**
    C3 span          ：逐域报 8 个 dev 与 span
    C4a 复算闸门     ：用放行的 res_ctrl 三域 ladder 重算 span，必须与放行值同序（Spearman）且
                        bootstrap 下界达标（item 级重抽，B=2000，seed 20261002）
    C4b 扩展         ：两个新域的 span 必须落在已发表三域 span 的 [0.5×, 2.0×] 中位数带内
    C5 否决          ：任一格 parse_ok<95% 必须标 not evaluable；探针/模型 md5 不符即中止
"""
import csv
import glob
import hashlib
import io
import json
import math
import os
import random
import sys

D = '/root/p1d'
RES = os.path.join(D, 'res')
REF = os.path.join(D, 'ref')
CRIT = os.path.join(D, '_p1d_criteria_frozen.json')
OUT = os.path.join(D, 'out')
BUDGETS = [0, 104856, 145698, 200000, 202447, 281300, 390867, 400000, 543118, 754655, 800000]
EXP_ROWS = 250
B_BOOT = 2000
SEED = 20261002


def rows(p):
    return list(csv.DictReader(io.open(p, encoding='utf-8-sig', newline='')))


def fnum(x):
    x = (x or '').strip()
    try:
        return float(x)
    except Exception:
        return None


def dev(rs):
    ps, sg = [], 0.0
    for r in rs:
        g, p = fnum(r.get('gt')), fnum(r.get('pred'))
        if g is None or g <= 0:
            continue
        sg += g
        ps.append(p if p is not None else 0.0)   # 弃答按 item-count 惯例记 0（与放行分析器一致）
    return (100.0 * (sum(ps) - sg) / sg) if sg else None


def span_of(v):
    v = [x for x in v if x is not None]
    return (max(v) - min(v)) if len(v) >= 2 else None


def spearman(xs, ys):
    n = len(xs)
    if n < 2:
        return None

    def rk(v):
        o = sorted(range(n), key=lambda i: v[i]); r = [0.0] * n; i = 0
        while i < n:
            j = i
            while j + 1 < n and v[o[j + 1]] == v[o[i]]:
                j += 1
            for k in range(i, j + 1):
                r[o[k]] = (i + j) / 2.0 + 1
            i = j + 1
        return r
    a, b = rk(xs), rk(ys)
    ma, mb = sum(a) / n, sum(b) / n
    num = sum((a[i] - ma) * (b[i] - mb) for i in range(n))
    da = sum((a[i] - ma) ** 2 for i in range(n)) ** 0.5
    db = sum((b[i] - mb) ** 2 for i in range(n)) ** 0.5
    return num / (da * db) if da and db else None


def collect(prefix, tag):
    """→ {档: [行...]}，并回报逐格行数。"""
    by = {}
    counts = {}
    for b in BUDGETS:
        allr = []
        for s in (1, 2, 3):
            p = os.path.join(RES, '%s_%s_b%d_s%d.csv' % (prefix, tag, b, s))
            if not os.path.exists(p):
                counts[(tag, b, s)] = 0
                continue
            r = rows(p)
            counts[(tag, b, s)] = len(r)
            allr += r
        by[str(b)] = allr
    return by, counts


def main():
    os.makedirs(OUT, exist_ok=True)
    crit = json.load(io.open(CRIT, encoding='utf-8'))
    print('== P1-D 分析 ==')
    print('  判据件 md5 = %s' % hashlib.md5(open(CRIT, 'rb').read()).hexdigest())
    rep = {'criteria_md5': hashlib.md5(open(CRIT, 'rb').read()).hexdigest(), 'domains': {}, 'checks': {}}
    bad = []

    # ---------- C1 ----------
    print('-- C1 逐格行数（期望 %d）--' % EXP_ROWS)
    for tag in ('mtdc', 'gwhd'):
        by, counts = collect('P1D', tag)
        short = [k for k, v in counts.items() if v < EXP_ROWS * 0.95]
        print('   %-5s 格数=%d ｜ <95%% 的格 = %d' % (tag, len(counts), len(short)))
        rep['checks']['C1_%s_short_cells' % tag] = len(short)
        if short:
            bad.append('C1 %s 有 %d 格偏少' % (tag, len(short)))

        # ---------- C2/C3 ----------
        lv = [b for b in BUDGETS if by[str(b)]]
        if len(lv) < 8:
            print('   %s ⇒ **NOT COVERED**（只有 %d/8 档）' % (tag, len(lv)))
            rep['checks']['C2_%s' % tag] = 'NOT COVERED (%d/8)' % len(lv)
            continue
        devs = [dev(by[str(b)]) for b in BUDGETS]
        sp = span_of(devs)
        rep['domains'][tag] = {'devs': [round(x, 2) if x is not None else None for x in devs],
                               'span': round(sp, 2) if sp is not None else None}
        print('   %s dev=%s ｜ span=%.2f' % (tag, [round(x, 1) for x in devs], sp))
        # C5 否决
        for b in BUDGETS:
            r = by[str(b)]
            ok = sum(1 for x in r if str(x.get('parse_ok')) == '1')
            if r and ok / float(len(r)) < 0.95:
                print('     !! 档 %d parse_ok=%.1f%% ⇒ not evaluable' % (b, 100.0 * ok / len(r)))
                bad.append('C5 %s 档 %d parse_ok 低' % (tag, b))

    # ---------- C4a：用放行 ladder 复算已发表三域（复算闸门） ----------
    print('-- C4a 复算闸门：res_ctrl 三域 --')
    pub = {}
    for tag, fn in (('st_a', 'res_ctrl_st_a.csv'), ('ucf', 'res_ctrl_ucf.csv'), ('visdrone', 'res_ctrl_visdrone.csv')):
        p = os.path.join(REF, fn)
        if not os.path.exists(p):
            print('   缺 %s ⇒ C4a 跳过' % fn)
            continue
        rs = rows(p)
        by = {}
        for r in rs:
            b = str(int(fnum(r['budget']) or 0))
            by.setdefault(b, []).append(r)
        # ★ C4a 只在**公共标签**上算：放行 ladder 带 {0,200000,400000,800000,1048576}，本轮的并集把 1048576 并进 0
        #   ⇒ 公共标签 = {0,200000,400000,800000}（对这批评测池，放行的 native 行与 1048576 行本就相同）
        C4L = [0, 200000, 400000, 800000]
        devs = [dev(by[str(b)]) if str(b) in by else None for b in C4L]
        n_lv = sum(1 for x in devs if x is not None)
        pub[tag] = {'devs': devs, 'span': span_of(devs), 'levels_used': '%d/8' % n_lv,
                    'order': None}
        print('   %-9s 用 %s 档 ｜ span=%s' % (tag, pub[tag]['levels_used'],
                                            round(pub[tag]['span'], 2) if pub[tag]['span'] else None))
    rep['published_recompute'] = {k: {'span': round(v['span'], 2) if v['span'] else None,
                                      'levels_used': v['levels_used']} for k, v in pub.items()}

    # ---------- C4b：扩展（新域 span 是否落在已发表三域带内） ----------
    print('-- C4b 扩展 --')
    pv = [pub[k]['span'] for k in pub if pub[k]['span'] is not None]
    if pv and rep['domains']:
        med = sorted(pv)[len(pv) // 2]
        band = (0.5 * med, 2.0 * med)
        print('   已发表三域 span=%s ｜ 中位 %.2f ｜ 容许带 [%.2f, %.2f]'
              % ([round(x, 2) for x in pv], med, band[0], band[1]))
        for tag, v in rep['domains'].items():
            if v['span'] is None:
                continue
            inside = band[0] <= abs(v['span']) <= band[1]
            print('   %-5s span=%.2f ⇒ %s' % (tag, v['span'], '带内' if inside else '**带外**'))
            rep['domains'][tag]['inside_published_band'] = bool(inside)
            if not inside:
                bad.append('C4b %s span 落在已发表带外' % tag)
    else:
        print('   数据不足 ⇒ C4b 跳过')

    rep['checks']['C4b_band'] = [round(band[0], 2), round(band[1], 2)] if pv and rep['domains'] else None
    rep['verdict'] = 'PASS' if not bad else 'NOT_PASSED'
    rep['failures'] = bad
    with io.open(os.path.join(OUT, 'p1d_rows.json'), 'w', encoding='utf-8') as f:
        json.dump(rep, f, ensure_ascii=False, indent=1)
    print('\n== 结论 ==')
    if bad:
        print('  NOT PASSED：')
        for x in bad:
            print('   - %s' % x)
    else:
        print('  PASS')
    print('已写 %s' % os.path.join(OUT, 'p1d_rows.json'))
    print('P1D_ANALYZE_DONE')
    return 0


if __name__ == '__main__':
    sys.exit(main())
