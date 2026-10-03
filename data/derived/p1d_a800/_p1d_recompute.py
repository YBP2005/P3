# -*- coding: utf-8 -*-
"""_p1d_recompute.py —— P1-D 的**独立**复算（纯 CPU，只用本地已取回的件）。

补的是判定书 §9 里记的"留痕不完整"两项，外加一次全面独立复算：
  C1  66 格逐格行数（应各 250）与数据行合计（应 16,500）
  C5  逐格 parse_ok 率（判据：任一格 <95% 记 not evaluable）—— 判定书先前说"分析器未给结论"，此处核实
  C4a 用放行的 res_ctrl 三域 ladder（`analysis/data/pod_mirror/res_ctrl__q32/`）在**公共标签**
      {0,200000,400000,800000} 上重算 per-domain span，并做 **item 级 bootstrap（B=2000, seed 20261002）**：
      ① 三域 span 的 95% CI；② 三域 span **排序**在重抽中保持同一序的比例（即 ordering 的下界）。
  C4b 两新域 span 是否落在已发表三域 span 中位的 [0.5x, 2.0x] 带内。
口径：dev = 100*(Σpred−Σgt)/Σgt，**每档在自己档位的 item 上池化**（G0 实测锁定；不用交集口径）。
"""
import csv
import io
import json
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
P1D = os.path.join(HERE, '_a800_p1d')
REF = os.path.join(HERE, '_p1d_recompute', 'ref')
COMMON = ['0', '200000', '400000', '800000']
B = 2000
SEED = 20261002


def rows(p):
    with io.open(p, encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


def fnum(x):
    try:
        return float(str(x).strip())
    except Exception:
        return None


def dev(pairs):
    sg = sum(g for g, _ in pairs)
    return 100.0 * (sum(p for _, p in pairs) - sg) / sg if sg else None


def load_cells(dom):
    """→ {(budget:int): {item: (gt, pred)}}（P1-D 的 66 格，三起服合并）"""
    out = {}
    for fn in sorted(os.listdir(P1D)):
        if not (fn.startswith('P1D_%s_b' % dom) and fn.endswith('.csv')):
            continue
        b = fn.split('_b')[1].split('_')[0]
        d = out.setdefault(b, {})
        for r in rows(os.path.join(P1D, fn)):
            g, p = fnum(r.get('gt')), fnum(r.get('pred'))
            if g is not None and g > 0 and p is not None:
                d.setdefault(r['item'], (g, p))     # 三起服取首个（一致性另见逐格 md5）
    return out


def span_of(per_level):
    d = [dev(list(v.values())) for v in per_level.values() if v]
    return (max(d) - min(d)) if len(d) >= 2 else None


def main():
    res = {}
    # ---------- C1 + C5：逐格行数与 parse_ok ----------
    print('== C1 逐格行数 / C5 parse_ok 否决 ==')
    tot = 0
    low = []
    for fn in sorted(os.listdir(P1D)):
        if not (fn.startswith('P1D_') and fn.endswith('.csv')):
            continue
        rs = rows(os.path.join(P1D, fn))
        tot += len(rs)
        ok = sum(1 for r in rs if str(r.get('parse_ok', '')).strip() in ('1', '1.0'))
        rate = 100.0 * ok / len(rs) if rs else 0.0
        if len(rs) != 250 or rate < 95.0:
            low.append((fn, len(rs), round(rate, 2)))
    print('   格数=%d 数据行=%d ｜ 不合格格=%s' % (len([f for f in os.listdir(P1D) if f.startswith('P1D_')]),
                                                  tot, low if low else '0 格 ✓'))
    res['C1'] = {'cells': 66, 'rows': tot, 'bad_cells': low}
    res['C5_parse_ok_veto'] = {'bad': low, 'pass': not low}

    # ---------- C4a：放行三域 ladder 在公共标签上复算 + bootstrap ----------
    print('== C4a 复算闸门（公共标签 %s）==' % COMMON)
    pub = {}
    for d in ('st_a', 'ucf', 'visdrone'):
        p = os.path.join(REF, 'res_ctrl_%s.csv' % d)
        per = {}
        for r in rows(p):
            b = str(r.get('budget', '')).strip()
            if b not in COMMON:
                continue
            g, pr = fnum(r.get('gt')), fnum(r.get('pred'))
            if g is not None and g > 0 and pr is not None:
                per.setdefault(b, {})[r['item']] = (g, pr)
        pub[d] = per
        sp = span_of(per)
        print('   %-9s 档=%d ｜ 各档 dev=%s ｜ span=%.2f'
              % (d, len(per), [round(dev(list(v.values())), 2) for v in per.values()], sp))
    spans = {d: span_of(v) for d, v in pub.items()}
    order0 = sorted(spans, key=lambda k: spans[k])
    print('   点估计 span=%s ⇒ 升序 %s'
          % ({k: round(v, 2) for k, v in spans.items()}, order0))

    rng = random.Random(SEED)
    # ★ 配对重抽（正确做法）：**每域按 item 重抽一次**，同一批 item 用在它的全部档位上。
    #   先前那版是"逐档各自独立重抽"，会**打断档位之间的配对**、把方差抬高，
    #   所以两版都算、都报，差异本身是信息。
    common_items = {}
    for d, per in pub.items():
        sets = [set(v) for v in per.values()]
        common_items[d] = sorted(set.intersection(*sets)) if sets else []
        print('   %-9s 四档公共 item = %d' % (d, len(common_items[d])))

    def boot_once(paired):
        sp_b = {}
        for d, per in pub.items():
            if paired:
                keys = common_items[d]
                pick = [keys[rng.randrange(len(keys))] for _ in keys]
                sp_b[d] = span_of({b: {i: per[b][k] for i, k in enumerate(pick)} for b in per})
            else:
                per_b = {}
                for b, items in per.items():
                    keys = list(items)
                    pick = [keys[rng.randrange(len(keys))] for _ in keys]
                    per_b[b] = {i: items[k] for i, k in enumerate(pick)}
                sp_b[d] = span_of(per_b)
        return sp_b

    out_bs = {}
    for mode in ('paired', 'unpaired'):
        rng = random.Random(SEED)
        same = 0
        boots = {d: [] for d in pub}
        for _ in range(B):
            sp_b = boot_once(mode == 'paired')
            for d in pub:
                boots[d].append(sp_b[d])
            if sorted(sp_b, key=lambda k: sp_b[k]) == order0:
                same += 1
        out_bs[mode] = {'same_order': same / B, 'boots': boots}
        print('   [%s] bootstrap B=%d：三域升序保持同一序 %d/%d = %.3f'
              % (mode, B, same, B, same / B))
        for d in pub:
            v = sorted(x for x in boots[d] if x is not None)
            print('     %-9s span 95%%CI = [%.2f, %.2f]' % (d, v[int(0.025 * len(v))], v[int(0.975 * len(v)) - 1]))
    same_order = out_bs['paired']['same_order']
    boots = out_bs['paired']['boots']
    print('   ⇒ 主口径 = **配对重抽**：下界 %.3f（判据 ≥0.80 ⇒ %s）'
          % (same_order, 'PASS' if same_order >= 0.80 else '**FAIL**'))
    ci = {}
    for d in pub:
        v = sorted(x for x in boots[d] if x is not None)
        ci[d] = [round(v[int(0.025 * len(v))], 2), round(v[int(0.975 * len(v)) - 1], 2)]
    res['C4a'] = {'spans': {k: round(v, 3) for k, v in spans.items()},
                  'order_ascending': order0,
                  'common_items': {d: len(v) for d, v in common_items.items()},
                  'bootstrap_same_order_paired': out_bs['paired']['same_order'],
                  'bootstrap_same_order_unpaired': out_bs['unpaired']['same_order'],
                  'pass': bool(out_bs['paired']['same_order'] >= 0.80),
                  'B': B, 'seed': SEED,
                  'ci_paired': ci}

    # ---------- 两新域：独立复算 span ----------
    print('== 两新域：独立复算（11 档，池化） ==')
    for d in ('mtdc', 'gwhd'):
        cells = load_cells(d)
        dl = [dev(list(v.values())) for v in cells.values()]
        print('   %-6s 档=%d dev=[%s] span=%.2f'
              % (d, len(cells), ', '.join('%.2f' % x for x in dl), max(dl) - min(dl)))
        res.setdefault('domains', {})[d] = {'devs': [round(x, 2) for x in dl],
                                            'span': round(max(dl) - min(dl), 3)}

    # ---------- C4b ----------
    med = sorted(spans.values())[1]
    band = [0.5 * med, 2.0 * med]
    res['C4b'] = {'median': round(med, 2), 'band': [round(band[0], 2), round(band[1], 2)],
                  'inside': {d: bool(band[0] <= res['domains'][d]['span'] <= band[1])
                             for d in res['domains']}}
    print('== C4b == 中位=%.2f 带=[%.2f, %.2f] ｜ 落带内=%s'
          % (med, band[0], band[1], res['C4b']['inside']))

    out = os.path.join(HERE, '_p1d_recompute', 'recompute.json')
    with io.open(out, 'w', encoding='utf-8') as f:
        json.dump(res, f, ensure_ascii=False, indent=1)
    print('已写 %s' % out)
    print('P1D_RECOMPUTE_DONE')
    return 0


if __name__ == '__main__':
    sys.exit(main())
