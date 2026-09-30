# -*- coding: utf-8 -*-
"""g2_analyze.py — 读 /root/g2_neutral0/*.csv（拉回本地后），**按冻结判据**出结论。

判据与阈值全部来自 `g_criteria_frozen.json`（md5 b9e8227d9aa332ce529976b34f1cb21b），
本脚本**只实现**、不新增判据。

口径（逐条照 J.1 / a5_report.py）：
  · gt 取自**同域语料池** CSV 的 gt 列（本实验产物里 gt 留空 ⇒ 按 item 连接）。
  · 分类：`raw` 含 abstain/cannot_judge/no_people ⇒ **弃答**；`pred` 空或非数 ⇒ **未解析**；
    `pred ≥ 1e5` ⇒ **异常**（剔除）；`pred == 0` ⇒ 零；否则非零。
  · 每个 (域 × 臂) 格：
        G  = Σgt（全部项）      G_N = Σgt（**作答**项）      P = Σpred（弃答项按 0 计）
        w  = G_N/G      ρ_total=(P−G)/G      ρ_answered=(P−G_N)/G_N
        **S = (G−G_N)/(G−P)**   —— 与命题 4 闭式 (1−w)/[1−w(1+ρ_answered)] 等价（脚本内互证）
    **S 有定义当且仅当 G−P > 0**（即 ρ_total<0）；否则**显式 undefined**，不填数。
  · 区间：答零率给 Wilson 95%；S 给 **2,000 次 item 级 bootstrap** 的 95% 分位。

用法：python -u g2_analyze.py [--dir <本地目录>] [--pool <语料池目录>]
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
import argparse
import csv
import io
import json
import math
import os
import random
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
LOCAL = NR()
# 语料池的**权威副本**：直接从 A800 的 /root/dense_results/ 拉回（与 item 集的定义同源）。
# 本机另有两处历史副本（`analysis/e1_5090/corpus/`、`analysis/data/pod_mirror/dense_results/`），
# 已实测 st_a 的 md5 与之一致（ff69abb8457c…），故用哪一处都不影响。
POOL = RP('analysis', 'g2_neutral0', 'pool')
SRC = {'st_a': 'vlm_st_a_base_whole.csv', 'ucf': 'vlm_ucf_base_whole.csv',
       'visdrone': 'vlm_visdrone_base_whole.csv', 'aitod': 'vlm_aitod_base_whole.csv'}
ARMS = ['cn-base', 'cn-neutral0', 'en-base', 'en-neutral0', 'en-neutral0em']
ANOM = 1e5


def wilson(k, n, z=1.959963985):
    if n == 0:
        return (float('nan'), float('nan'))
    p = k / float(n)
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return ((c - h) / d, (c + h) / d)


def cls(raw, pred):
    """与 a5_report.py::cls() 同口径：raw 关键词优先，再看 pred。"""
    r = (raw or '').lower()
    for k in ('abstain', 'cannot_judge', 'no_people'):
        if k in r:
            return k
    p = str(pred or '').strip()
    if p == '':
        return 'unparsed'
    try:
        v = float(p)
    except ValueError:
        return 'unparsed'
    if v >= ANOM:
        return 'anomaly'
    return 'zero' if v == 0 else 'nonzero'


def load_pool(ds):
    p = os.path.join(RP('analysis', 'g2_neutral0', 'pool'), SRC[ds])
    gt = {}
    with io.open(p, encoding='utf-8-sig', newline='') as f:
        for r in csv.DictReader(f):
            gt[r['item']] = float(r['gt'])
    return gt


def cell_stats(rows):
    """rows: [(gt, cls, pred)]  ⇒ dict；含闭式互证。

    ★ 关键口径（本稿的定义，不是通用定义）：**答 0 就是弃答**（这正是本稿的论点：
    模型拒答时写出字面 0）。所以命题 4 的分解里
        作答集 = `pred ≠ 0` 的项（cls == 'nonzero'）
        弃答集 = `pred == 0` 的项 **加** 显式拒答的项
        未解析 = 单列，不进任一侧（并报出它的条数）
    ⇒ `G_N = Σgt（仅 nonzero）`、`P = Σpred（仅 nonzero；其余按 0 计入 G 的分母）`。
    这与 J.1 印出的数一致：ShanghaiTech-A 的 `w = 0.2359`，即只有约四分之一的 gt 落在作答集上。
    """
    n = len(rows)
    G = sum(g for g, c, v in rows)
    P = sum(v for g, c, v in rows if c == 'nonzero')
    GN = sum(g for g, c, v in rows if c == 'nonzero')
    ans = sum(1 for g, c, v in rows if c == 'nonzero')
    z = sum(1 for g, c, v in rows if c == 'zero')
    ref = sum(1 for g, c, v in rows if c in ('abstain', 'cannot_judge', 'no_people'))
    unp = sum(1 for g, c, v in rows if c == 'unparsed')
    d = dict(n=n, G=G, P=P, GN=GN, answered=ans, zero=z, refusal=ref, unparsed=unp,
             zero_rate=100.0 * z / n if n else float('nan'),
             w=GN / G if G else float('nan'),
             rho_total=100.0 * (P - G) / G if G else float('nan'),
             rho_ans=100.0 * (P - GN) / GN if GN else float('nan'))
    if G - P > 0 and GN > 0:
        d['S'] = 100.0 * (G - GN) / (G - P)
        w = GN / G
        d['S_closed'] = 100.0 * (1 - w) / (1 - w * (1 + (P - GN) / GN))
    else:
        d['S'] = None
        d['S_closed'] = None
    return d


def boot_S(rows, draws=2000, seed=20260926):
    rng = random.Random(seed)
    vals, undef = [], 0
    n = len(rows)
    for _ in range(draws):
        s = [rows[rng.randrange(n)] for _ in range(n)]
        d = cell_stats(s)
        if d['S'] is None:
            undef += 1
        else:
            vals.append(d['S'])
    if not vals:
        return (None, None, 100.0 * undef / draws)
    vals.sort()
    lo = vals[int(0.025 * len(vals))]
    hi = vals[min(len(vals) - 1, int(0.975 * len(vals)))]
    return (lo, hi, 100.0 * undef / draws)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dir', default=RP('analysis', 'g2_neutral0'))
    A = ap.parse_args()
    crit = json.load(io.open(RP('analysis', 'work', 'g_criteria_frozen.json'),
                             encoding='utf-8'))
    print('冻结判据：%s（%d 条）' % (crit['round'], len(crit['criteria_fixed_in_advance'])))

    res = {}
    for ds in SRC:
        gt = load_pool(ds)
        for arm in ARMS:
            p = os.path.join(A.dir, '%s__%s.csv' % (ds, arm))
            if not os.path.exists(p):
                continue
            rows = []
            n_all = n_err = n_nopred = 0
            with io.open(p, encoding='utf-8', newline='') as f:
                for r in csv.DictReader(f):
                    g = gt.get(r['item'])
                    if g is None:
                        continue
                    n_all += 1
                    raw = r.get('raw') or ''
                    if raw.startswith('ERR:HTTP Error 400'):
                        n_err += 1            # ★ 上下文超限（M.39 已披露的基础设施限制），不是模型行为
                    elif not str(r.get('pred') or '').strip() and not any(
                            w in raw.lower() for w in ('abstain', 'cannot_judge', 'no_people')):
                        n_nopred += 1
                    c = cls(raw, r.get('pred'))
                    # ★ **没有可用结果的项整条剔除**，不得算作弃答：M.39 的纪律是"报为未测而不填补"。
                    #   若把 HTTP 400 / 空 pred 留在格内，它们的 gt 会进 G 却既无 pred 也不进作答集，
                    #   于是被伪装成"弃答"，把 ρ_total 与 S 一起拉偏。
                    if c in ('anomaly', 'unparsed'):
                        continue
                    v = 0.0
                    if c in ('zero', 'nonzero'):
                        v = float(str(r["pred"]).strip())
                    rows.append((g, c, v))
            d = cell_stats(rows)
            d['n_all'] = n_all
            d['n_http400'] = n_err
            d['n_nopred'] = n_nopred
            lo, hi = wilson(d['zero'], d['n'])
            d['zero_ci'] = [100 * lo, 100 * hi]
            d['S_ci'] = boot_S(rows)
            res['%s|%s' % (ds, arm)] = d

    hdr = '%-6s %-13s %6s %6s %7s %8s %7s %7s %7s %9s %8s %14s' % (
        '域', '臂', '尝试', '可用', 'HTTP400', '答零%', '弃答', 'w', 'ρ_tot%', 'S%', 'S 抽到undef', 'S 95% CI')
    print(); print(hdr); print('-' * len(hdr))
    for ds in SRC:
        for arm in ARMS:
            d = res.get('%s|%s' % (ds, arm))
            if not d:
                continue
            sci = d['S_ci']
            cistr = ('[%.1f, %.1f]' % (sci[0], sci[1])) if sci[0] is not None else 'undefined'
            print('%-6s %-13s %6d %6d %7d %8.1f %7d %7.3f %7.1f %9s %7s %14s' % (
                ds, arm, d['n_all'], d['n'], d['n_http400'], d['zero_rate'], d['refusal'], d['w'],
                d['rho_total'], ('%.1f' % d['S']) if d['S'] is not None else 'undef',
                ('%.0f%%' % sci[2]) if sci[0] is not None else '—', cistr))

    # 闭式互证
    bad = [(k, d['S'], d['S_closed']) for k, d in res.items()
           if d['S'] is not None and abs(d['S'] - d['S_closed']) > 1e-9]
    print()
    print('闭式互证（S vs (1−w)/[1−w(1+ρ_ans)]）：%s' % ('全部一致 ✓' if not bad else '不一致 %r' % bad[:3]))

    # ---- 冻结判据 C1..C5 ----
    print()
    print('=' * 96)
    print('冻结判据逐条')
    print('=' * 96)
    und = [k for k, d in res.items() if d['S'] is None]
    oor = [k for k, d in res.items() if d['S'] is not None and not (-1e-9 <= d['S'] <= 100 + 1e-9)]
    print('C1 S 保持为份额：undefined %d 格 %s ｜ 越界 %d 格 %s ⇒ %s'
          % (len(und), und or '—', len(oor), oor or '—',
             'PASS' if not oor else 'FAIL'))

    def rate(ds, arm):
        d = res.get('%s|%s' % (ds, arm))
        return d['zero_rate'] if d else None

    print()
    print('C3 被点名的数字机制（Δ = neutral0 − 同语言 base，pp；阈值 ≥+10 pp，需 ≥3/4 域）')
    c3 = {}
    for lang, base, treat in (('cn', 'cn-base', 'cn-neutral0'), ('en', 'en-base', 'en-neutral0')):
        ok = 0
        for ds in SRC:
            b, t = rate(ds, base), rate(ds, treat)
            if b is None or t is None:
                continue
            c3['%s|%s' % (ds, lang)] = t - b
            if t - b >= 10:
                ok += 1
        print('  %s：%s ⇒ %d/4 通过' % (lang,
              ' '.join('%s %+.1f' % (ds, c3.get('%s|%s' % (ds, lang), float('nan'))) for ds in SRC), ok))

    print()
    print('C4 机制的跨语言一致性（δ = Δ(en) − Δ(cn)，pp；阈值 |δ| ≤ 20 pp，需 ≥3/4 域）')
    ok = 0
    for ds in SRC:
        a, b = c3.get('%s|cn' % ds), c3.get('%s|en' % ds)
        if a is None or b is None:
            continue
        d = b - a
        flag = 'OK' if abs(d) <= 20 else '**超**'
        if abs(d) <= 20:
            ok += 1
        print('  %-9s Δcn %+7.1f ｜ Δen %+7.1f ｜ δ %+7.1f  %s' % (ds, a, b, d, flag))
    print('  ⇒ %d/4 通过' % ok)

    print()
    print('C5 渲染敏感性（δe = Δ(en-neutral0em) − Δ(en-neutral0)，pp；阈值 |δe| ≤ 20 pp，需 ≥3/4 域）')
    ok = 0
    for ds in SRC:
        b = rate(ds, 'en-base')
        e1, e2 = rate(ds, 'en-neutral0'), rate(ds, 'en-neutral0em')
        if None in (b, e1, e2):
            continue
        d = (e2 - b) - (e1 - b)
        if abs(d) <= 20:
            ok += 1
        print('  %-9s δe %+7.1f  %s' % (ds, d, 'OK' if abs(d) <= 20 else '**超**'))
    print('  ⇒ %d/4 通过' % ok)

    with io.open(os.path.join(A.dir, '_g2_result.json'), 'w', encoding='utf-8') as f:
        f.write(json.dumps(res, ensure_ascii=False, indent=1))
    print('\nJSON -> %s' % os.path.join(A.dir, '_g2_result.json'))


if __name__ == '__main__':
    main()
