# -*- coding: utf-8 -*-
"""span_equalcount2.py —— 修正版：**按口径分开**重算"跨度是不是扫描网格/端点的函数"。

★★ 为什么有 2（原版保留不动，冻结 md5 `acb867f0f92dc08112ba4cf5ead16851`）
原版 `span_equalcount.py` 的 ① 段从 `analysis/data/threeway_curves_v2.csv` 取 ρ 建"检测 τ"阶梯时
**没有过滤 `match` 列**。而该 CSV 里**同一 (paradigm, knob, setting) 有两种口径各一行**
（`match=person` 与 `match=allclass`，见 `_verify_41_numbers.py` 与 §4.1 的口径更正）⇒ 阶梯实际是
**两种口径交错**，后果有三：

| 症状 | 原版（错） | 真值 |
|---|---|---|
| "档数" | 域内 **16**、COCO **32** | 域内 **8**、COCO **16**（被算成两倍） |
| "全长跨度" | 域内 593.7 pp | person **195.7** ／ allclass **508.4**（593.7 = 508.4 与 −86.3 **跨口径相减**） |
| "去端点" | 三个变体**恒等于**全长（hi=lo=full） | 交错序列使 max/min 分属不同口径，去掉任一档都不改变极值 |
| 等点数缩小倍率 | 域内 2.22–2.30×、COCO 4.94–9.96× | person **1.00×**（域内）/ **1.03–1.27×**（COCO）；allclass 1.00× / 1.04–1.36× |

⇒ 稿件 §7.3 那句"检测器 τ 的跨度在等点数下缩小 **2.2–2.3×**（域内）/ **5–10×**（零点样本 COCO）"
是**跨口径相减造出来的假象**；按口径分开后几乎没有缩小。等点数子采样保留了首尾两档
（分位公式必取 index 0 与 n−1），所以只要极值本来就在端点，跨度就**按构造不变**——
这也解释了为什么原版冻结件里 `shrink_eq_median` 本来就是 **1.00**。

## 本脚本做什么
与原版同样的六族阶梯、同样的 `k=4` 等点数、同样的去端点，但：
1. **检测 τ 阶梯按 `match` 分开**（person / allclass 各一套），并在代码里**硬断言**每条阶梯
   内部口径唯一（原版缺的正是这条结构性断言）；
2. 秩相关（Spearman）**在每个口径内部各算一遍**（把两种口径混进同一个 24 单元排序 = 又犯同一个错）；
3. 输出 `span_equalcount2_result.json`，同时把两种口径的 24 单元表、秩相关三元组、
   等点数保留率、去端点降幅、τ 缩小倍率全部打印出来；
4. `--reproduce-bug` 开关可用原逻辑复算一次，**证明本脚本确实复现出原版的错值**
   （不能复现，就说明我改的地方不是病根）。

用法：
    python -u span_equalcount2.py                    # 修正版（两种口径）
    python -u span_equalcount2.py --reproduce-bug    # 复算原版错值以验证病根
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
import collections
import csv
import glob
import io
import json
import os
import statistics as st
import sys

sys.stdout.reconfigure(encoding='utf-8')
ROOT = NR()
DATA = NR('analysis', 'data')
PM = RP('analysis', 'data', 'pod_mirror')
E2 = RP('analysis', 'e2_newh20')
OUT = RP('analysis', 'work', 'span_equalcount2_result.json')
ANOM = 1e5
REPRO_BUG = '--reproduce-bug' in sys.argv


def load_csv(p, pred_col='pred', gt_col='gt'):
    with io.open(p, encoding='utf-8-sig') as f:
        rows = [r for r in csv.DictReader(f) if '#r' not in str(r.get('item') or '')]
    out = {}
    for r in rows:
        it = str(r.get('item') or '')
        try:
            gt = float(r.get(gt_col) or '')
            pr = float(r.get(pred_col) or '')
        except (TypeError, ValueError):
            continue
        if pr >= ANOM or gt <= 0:
            continue
        out[it] = (gt, pr)
    return out


def pooled(items):
    sg = sum(g for g, _ in items.values())
    sp = sum(p for _, p in items.values())
    return 100.0 * (sp - sg) / sg if sg else None


def build(caliber):
    """caliber: 'person' | 'allclass' | None(=复现原版的混用)。返回 unit → [(label, rho)]。"""
    L = collections.OrderedDict()
    calibers_seen = collections.defaultdict(set)

    def add(unit, levels):
        keys = None
        for _, d in levels:
            keys = set(d) if keys is None else (keys & set(d))
        keys = sorted(keys)
        seq = []
        for lb, d in levels:
            r = pooled({k: d[k] for k in keys})
            if r is not None:
                seq.append((lb, r))
        if len(seq) >= 3:
            L[unit] = seq

    # ① 检测 τ —— ★ 修正点：按 match 取行
    p = NR('analysis', 'data', 'threeway_curves_v2.csv')
    if os.path.exists(p):
        rows = list(csv.DictReader(io.open(p, encoding='utf-8-sig')))
        for para in sorted(set(r['paradigm'] for r in rows)):
            for sz in sorted(set(r['knob'] for r in rows if r['paradigm'] == para)):
                sub = [r for r in rows if r['paradigm'] == para and r['knob'] == sz
                       and (caliber is None or r.get('match') == caliber)]
                calibers_seen['%s/%s' % (para, sz)] |= set(r.get('match') for r in sub)
                seq = sorted(((r['setting'], float(r['rho'])) for r in sub), key=lambda x: float(x[0]))
                if len(seq) >= 3:
                    L['%s / VisDrone / %s' % (para, sz)] = seq
        # ★ 结构性断言：一条阶梯只能有一种口径（原版缺这一条，才让交错通过）
        if caliber is not None:
            bad = {k: sorted(v) for k, v in calibers_seen.items() if len(v) > 1}
            assert not bad, '阶梯内混口径：%s' % bad
            assert all(len(v) == 1 for v in calibers_seen.values())

    # ② 密度回归输入尺度
    p = NR('analysis', 'data', 'threeway_curves.csv')
    if os.path.exists(p):
        rows = list(csv.DictReader(io.open(p, encoding='utf-8-sig')))
        for ds in sorted(set(r['domain'] for r in rows if r['paradigm'] == '密度回归')):
            for knob in sorted(set(r['knob'] for r in rows
                                   if r['paradigm'] == '密度回归' and r['domain'] == ds)):
                seq = [(r['setting'], float(r['rho'])) for r in rows
                       if r['paradigm'] == '密度回归' and r['domain'] == ds and r['knob'] == knob]
                if len(seq) >= 3:
                    L['density / %s / %s' % (ds, knob)] = seq
        for para in ('VLM·Qwen32B', 'VLM·InternVL8B'):
            for ds in sorted(set(r['domain'] for r in rows if r['paradigm'] == para)):
                seq = [(r['setting'], float(r['rho'])) for r in rows
                       if r['paradigm'] == para and r['domain'] == ds]
                if len(seq) >= 3:
                    L['pxbudget(threeway) / %s / %s' % (para.split('·')[1], ds)] = seq

    # ③ 像素预算（res_ctrl：逐图，可重算）
    for mdl in ('q32', 'ivl'):
        for f in sorted(glob.glob(os.path.join(RP('analysis', 'data', 'pod_mirror'), 'res_ctrl__%s' % mdl, 'res_ctrl_*.csv'))):
            ds = os.path.basename(f)[len('res_ctrl_'):-4]
            with io.open(f, encoding='utf-8-sig') as fh:
                rr = list(csv.DictReader(fh))
            levels = []
            for b in sorted(set(r['budget'] for r in rr), key=lambda x: float(x)):
                dd = {}
                for r in rr:
                    if r['budget'] != b or '#r' in str(r.get('item') or ''):
                        continue
                    try:
                        gt, pr = float(r['gt']), float(r['pred'])
                    except (TypeError, ValueError):
                        continue
                    if pr >= ANOM or gt <= 0:
                        continue
                    dd[str(r['item'])] = (gt, pr)
                levels.append(('budget=%s' % b, dd))
            add('pxbudget(res_ctrl) / %s / %s' % (mdl, ds), levels)

    # ④ 提示词族
    for ds in ('st_a', 'ucf', 'visdrone'):
        fs_ = sorted(glob.glob(os.path.join(RP('analysis', 'data', 'pod_mirror', 'dense_prompt_results'), 'vlm_%s_base_V*.csv' % ds)))
        if fs_:
            add('promptfamily / %s / base' % ds,
                [(os.path.basename(f).split('_V')[1][0], load_csv(f)) for f in fs_])
        fs_ = sorted(glob.glob(os.path.join(RP('analysis', 'data', 'pod_mirror', 'ivl_dense_prompt_results'), 'ivl_%s_base_V*.csv' % ds)))
        if fs_:
            add('promptfamily(ivl) / %s / base' % ds,
                [(os.path.basename(f).split('_V')[1][0], load_csv(f)) for f in fs_])

    # ⑤ 切块级别
    for ds in ('st_a', 'ucf', 'visdrone'):
        fs_ = sorted(glob.glob(os.path.join(RP('analysis', 'data', 'pod_mirror', 'tile_results'), 'vlm_%s_base_tile*.csv' % ds)))
        if fs_:
            add('tiling / %s / base' % ds,
                [(os.path.basename(f).split('tile')[1][0], load_csv(f)) for f in fs_])
        if ds == 'visdrone':
            fs_ = sorted(glob.glob(RP('analysis', 'data', 'pod_mirror', 'ivl_aerial_tile_results', 'ivl_*tile*.csv')))
            if fs_:
                add('tiling(ivl) / %s / base' % ds,
                    [(os.path.basename(f).split('tile')[1][0], load_csv(f)) for f in fs_])

    # ⑥ 输出契约
    for ds in ('st_a', 'ucf', 'visdrone', 'aitod'):
        levels = []
        for arm in ('base', 'permit', 'bestA', 'bestB', 'bestC', 'channel'):
            f = os.path.join(RP('analysis', 'e2_newh20'), 'e1_qwen3-vl-32b-awq_%s_%s.csv' % (ds, arm))
            if os.path.exists(f):
                levels.append((arm, load_csv(f)))
        if len(levels) >= 3:
            add('contract(E2) / q32awq / %s' % ds, levels)
    return L


def span(seq):
    v = [x[1] for x in seq]
    return max(v) - min(v)


def equalize(seq, k):
    """按分位位置降到 k 档。★ 注意：分位公式必取 index 0 与 n−1 ⇒ **首尾两档一定保留**，
    因此"等点数"对**极值落在端点**的阶梯是**按构造的空操作**（这正是 shrink 中位 = 1.00 的原因）。"""
    n = len(seq)
    if n <= k:
        return seq
    idx = sorted(set(int(round(i * (n - 1) / float(k - 1))) for i in range(k)))
    return [seq[i] for i in idx]


def spearman(a, b):
    def rank(x):
        s = sorted(range(len(x)), key=lambda i: x[i])
        r = [0.0] * len(x)
        i = 0
        while i < len(s):
            j = i
            while j + 1 < len(s) and x[s[j + 1]] == x[s[i]]:
                j += 1
            avg = (i + j) / 2.0 + 1
            for t in range(i, j + 1):
                r[s[t]] = avg
            i = j + 1
        return r
    ra, rb = rank(a), rank(b)
    n = len(a)
    ma, mb = sum(ra) / n, sum(rb) / n
    num = sum((ra[i] - ma) * (rb[i] - mb) for i in range(n))
    da = sum((ra[i] - ma) ** 2 for i in range(n)) ** 0.5
    db = sum((rb[i] - mb) ** 2 for i in range(n)) ** 0.5
    return num / (da * db) if da and db else float('nan')


def analyse(L, tag):
    units = sorted(L)
    kmin = min(len(L[u]) for u in units)
    rows = []
    for u in units:
        seq = L[u]
        rows.append(dict(unit=u, n=len(seq), span=span(seq), span_eq=span(equalize(seq, kmin)),
                         span_drop_high=span(seq[:-1]) if len(seq) > 3 else float('nan'),
                         span_drop_low=span(seq[1:]) if len(seq) > 3 else float('nan')))
    res = dict(units=rows, k_equal=kmin, caliber=tag)
    for key in ('span_eq', 'span_drop_high', 'span_drop_low'):
        sub = [(r['span'], r[key]) for r in rows if r[key] == r[key]]
        res['spearman_' + key] = spearman([a for a, _ in sub], [b for _, b in sub])
    res['shrink_eq_median'] = st.median([r['span_eq'] / r['span'] for r in rows if r['span']])
    res['drop_high_median'] = st.median([(r['span'] - r['span_drop_high']) / r['span'] for r in rows
                                         if r['span'] and r['span_drop_high'] == r['span_drop_high']])
    res['drop_low_median'] = st.median([(r['span'] - r['span_drop_low']) / r['span'] for r in rows
                                        if r['span'] and r['span_drop_low'] == r['span_drop_low']])
    for lab, pred in (('in_domain', lambda u: 'tau' in u and '域内' in u),
                      ('coco', lambda u: 'tau' in u and 'COCO' in u)):
        v = [r['span'] / r['span_eq'] for r in rows if pred(r['unit'])]
        if v:
            res['tau_shrink_' + lab] = [min(v), max(v)]
    return res


def main():
    print('=' * 100)
    print('span_equalcount2.py ｜ %s' % ('--reproduce-bug：复算原版错值' if REPRO_BUG else '修正版：按口径分开'))
    print('=' * 100)
    if REPRO_BUG:
        L = build(None)
        r = analyse(L, 'MIXED(原版行为)')
        print('  τ 档数：%s' % {u.split(' / ')[-1]: len(L[u]) for u in L if 'tau' in u})
        print('  τ 缩小倍率：域内 %.2f–%.2f ｜ COCO %.2f–%.2f'
              % (r['tau_shrink_in_domain'][0], r['tau_shrink_in_domain'][1],
                 r['tau_shrink_coco'][0], r['tau_shrink_coco'][1]))
        print('  （原版冻结件：域内 2.22–2.30、COCO 4.94–9.96 ⇒ 本脚本应复现出同一组数）')
        return 0

    ALL = {}
    for cal in ('person', 'allclass'):
        L = build(cal)
        r = analyse(L, cal)
        ALL[cal] = r
        print('\n' + '-' * 100)
        print('口径 = %s ｜ 单元 %d 个 ｜ 等点数目标 k = %d' % (cal, len(r['units']), r['k_equal']))
        print('-' * 100)
        print('%-46s %5s %10s %10s %10s %10s' % ('单元', '档数', '全长', '等k', '去高档', '去低档'))
        for x in r['units']:
            if 'tau' in x['unit']:
                print('%-46s %5d %10.1f %10.1f %10.1f %10.1f'
                      % (x['unit'], x['n'], x['span'], x['span_eq'], x['span_drop_high'], x['span_drop_low']))
        print('  Spearman(全长, 等点数) = %.3f ｜ (全长, 去高档) = %.3f ｜ (全长, 去低档) = %.3f'
              % (r['spearman_span_eq'], r['spearman_span_drop_high'], r['spearman_span_drop_low']))
        print('  等点数保留率中位 %.2f ｜ 去高档中位降幅 %.0f%% ｜ 去低档中位降幅 %.0f%%'
              % (r['shrink_eq_median'], 100 * r['drop_high_median'], 100 * r['drop_low_median']))
        print('  τ 缩小倍率：域内 %.2f–%.2f ｜ COCO %.2f–%.2f'
              % (r['tau_shrink_in_domain'][0], r['tau_shrink_in_domain'][1],
                 r['tau_shrink_coco'][0], r['tau_shrink_coco'][1]))

    # 非 τ 单元在两种口径下必须逐字相同（它们与 match 无关）—— 又一条结构性断言
    fa = {x['unit']: x['span'] for x in ALL['person']['units'] if 'tau' not in x['unit']}
    fb = {x['unit']: x['span'] for x in ALL['allclass']['units'] if 'tau' not in x['unit']}
    assert fa == fb, '非 τ 单元在两种口径下不同，说明口径维度泄漏到了别的阶梯'

    res = dict(person=ALL['person'], allclass=ALL['allclass'], k_equal=ALL['person']['k_equal'],
               note='由 span_equalcount2.py 生成；原版 span_equalcount.py（md5 '
                    'acb867f0f92dc08112ba4cf5ead16851）的检测 τ 阶梯未过滤 match 口径，跨口径相减，'
                    '故其"×2.2–2.3 / ×5–10 缩小"与"档数 16/32"为假象。')
    io.open(OUT, 'w', encoding='utf-8', newline='\n').write(json.dumps(res, ensure_ascii=False, indent=2))
    print('\n已冻结 %s' % OUT)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
