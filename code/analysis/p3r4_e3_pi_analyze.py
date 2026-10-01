# -*- coding: utf-8 -*-
"""p3r4_e3_pi_analyze.py —— E-3（π 过 0.5）分析：在 π = n2/(n1+n2) = 300/526 = 0.5703 的**已知真零基率混合语料**上，
逐 构建×启动 格算 §M.21.10 的恒等式与迁移检验。

【量（逐字取 §M.21.10 与 `_p3r4_A800实验方案_20260930.md §E-3` 的口径）】
  n1 = census 项（gt>0）= 226；n2 = 真零项 = 300；π = n2/(n1+n2) = 0.5703
  answered zero        ：pred == 0（只取 parse_ok=1 的行）
  q   = 答零率（全混合语料，分母 = parse_ok 的项数）
  p   = 答零率（真零子集，分母 = 真零里 parse_ok 的项数）        ← "自池 p"
  precision_obs = 真零中答零的项 / 全语料答零的项 = P(genuine zero | answered zero)
  恒等式：precision_obs ≈ p·π/q
【预注册判据】
  ① |precision_obs − p·π/q| ≤ **0.59 pp** 的格数
  ② **迁移检验**：p 改由**不相交**真零子集测（本轮**不可做**：300 个真零全用于构造 ⇒ 记 n/a + 原因）
  ③ 该 π 格上 precision_obs 的 **Wilson 95% 区间**与宽度、以及 N（答零项数，即 precision 的分母）
用法：python3 p3r4_e3_pi_analyze.py <manifest> <csv_dir> [tag1 tag2 ...]
  ★ 放行包内可直接重跑：
    python3 p3r4_e3_pi_analyze.py \
      data/derived/p3r4_a800/pf_items_pi0570.json data/derived/p3r4_a800
"""
import csv
import io
import json
import math
import os
import sys

ANOM = 1e5


def wilson(k, n, z=1.959963984540054):
    if n == 0:
        return (float('nan'), float('nan'))
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return ((c - h) / d, (c + h) / d)


def load_csv(path):
    with io.open(path, encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


def cell(rows, truezero_items):
    """返回该格的全部中间量与判据值。"""
    n_rows = len(rows)
    ok = [r for r in rows if str(r.get('parse_ok') or '').strip() == '1']
    dz = 0
    for r in ok:
        s = str(r.get('pred') or '').strip()
        if s == '':
            continue
        try:
            v = float(s)
        except Exception:
            continue
        if v >= ANOM:
            continue
        if v == 0:
            dz += 1
    n_ok = len(ok)
    z_ok = [r for r in ok if str(r.get('item') or '').strip() in truezero_items]
    z_true = 0
    for r in z_ok:
        s = str(r.get('pred') or '').strip()
        try:
            v = float(s)
        except Exception:
            continue
        if v == 0:
            z_true += 1
    n2_ok = len(z_ok)
    p = (z_true / n2_ok) if n2_ok else float('nan')          # 自池 p：真零子集上的答零率
    q = (dz / n_ok) if n_ok else float('nan')                # 全语料答零率
    prec = (z_true / dz) if dz else float('nan')             # P(genuine zero | answered zero)
    pi = None
    # ★ 附加诊断（**非预注册判据**）：只用 parse_ok 子集时，真零占比 π_eff 与名义 π 可能不同；
    #   恒等式在 parse_ok 子集上应以 π_eff 为基率。差 = 差异化的"不解析"构成效应。
    n1_ok = n_ok - n2_ok
    pi_eff = (n2_ok / n_ok) if n_ok else float('nan')
    return dict(n_rows=n_rows, n_ok=n_ok, parse=(n_ok / n_rows if n_rows else float('nan')),
                n_truezero=n2_ok, n_truezero_zero=z_true, n_answered_zero=dz,
                n_census_ok=n1_ok, pi_eff=pi_eff,
                p=p, q=q, precision=prec, pi=pi)


def main():
    man_p, csv_dir = sys.argv[1], sys.argv[2]
    tags = sys.argv[3:] or ['gemma3_12b', 'phi35', 'internvl8b', 'llavaov']
    man = json.load(io.open(man_p, encoding='utf-8'))
    tz = {str(x['item']).strip() for x in man['items_truezero']}
    n1, n2 = man['n1'], man['n2']
    pi = n2 / float(n1 + n2)
    print('清单 %s' % man_p)
    print('n1(census,gt>0)=%d  n2(true zero)=%d  π = %d/%d = **%.4f**' % (n1, n2, n2, n1 + n2, pi))
    print('items_zero=%d（探针按 --pool zero 跑全量）  真零键数=%d\n' % (len(man['items_zero']), len(tz)))

    print('| 构建 | 启动 | parse_ok | p(自池真零) | q(全语料答零) | precision_obs | p·π/q | 残差(pp) | ①≤0.59pp | N(precision分母) | Wilson95(precision) | 宽度(pp) | **π_eff** | **残差(π_eff)(pp)** |')
    print('|---|---|---|---|---|---|---|---|---|---|---|---|---|---|')
    pass1 = pass_n = 0
    rows_out = []
    for t in tags:
        for s in (1, 2, 3):
            path = os.path.join(csv_dir, 'E3_%s_start%d.csv' % (t, s))
            if not os.path.exists(path):
                print('| %s | %d | *缺产物* | | | | | | | | | | | |' % (t, s))
                continue
            d = cell(load_csv(path), tz)
            pred = d['p'] * pi / d['q'] if (d['q'] and d['q'] > 0) else float('nan')
            res = (d['precision'] - pred) * 100 if pred == pred and d['precision'] == d['precision'] else float('nan')
            # ★ 诊断（非预注册）：用 parse_ok 子集自身的基率 π_eff
            pred_eff = d['p'] * d['pi_eff'] / d['q'] if (d['q'] and d['q'] > 0) else float('nan')
            res_eff = (d['precision'] - pred_eff) * 100 if pred_eff == pred_eff and d['precision'] == d['precision'] else float('nan')
            lo, hi = wilson(d['n_truezero_zero'], d['n_answered_zero'])
            ok1 = abs(res) <= 0.59
            pass1 += 1 if ok1 else 0
            pass_n += 1
            print('| %s | %d | %d/%d=%.1f%% | %.2f%% | %.2f%% | %.4f | %.4f | %+.2f | %s | %d | [%.2f%%, %.2f%%] | %.2f | %.4f | %+.2f |'
                  % (t, s, d['n_ok'], d['n_rows'], 100 * d['parse'], 100 * d['p'], 100 * d['q'],
                     d['precision'], pred, res, '✅' if ok1 else '❌', d['n_answered_zero'],
                     100 * lo, 100 * hi, 100 * (hi - lo), d['pi_eff'], res_eff))
            rows_out.append(dict(tag=t, start=s, pi_nom=pi, **d, pred=pred, residual_pp=res,
                                 pred_eff=pred_eff, residual_eff_pp=res_eff,
                                 wilson=[lo, hi], width_pp=100 * (hi - lo), c1=ok1))
    print('\n**判据①（恒等式 ≤ 0.59 pp，名义 π）**：%d/%d 格满足' % (pass1, pass_n))
    lowp = [r for r in rows_out if r['parse'] < 0.95]
    if lowp:
        print('★ **parse_ok < 95%% 的格**（按本轮既有的 P0-1 闸门口径应记**不可评**，不得改报 FAIL）：')
        for r in lowp:
            print('    %s start%d：parse_ok %.1f%%（%d/%d）｜真零里 parse_ok %d，census 里 parse_ok %d'
                  % (r['tag'], r['start'], 100 * r['parse'], r['n_ok'], r['n_rows'],
                     r['n_truezero'], r['n_census_ok']))
        print('    ⇒ 这三个未过格里，**未解析项高度偏向真零侧**（真零 300 中仅 %d/%d 解析成功，census 226 中 %d 解析成功）'
              % (lowp[0]['n_truezero'], n2, lowp[0]['n_census_ok']))
        print('    ★ 诊断（**非预注册判据，只解释机制**）：恒等式若改用 **parse_ok 子集自身的基率 π_eff**，'
              '同三格残差变为 %s pp ⇒ 名义 π 的偏差**全部**来自"差异化的不解析"改变了已解析子集的真零占比。'
              % ', '.join('%+.2f' % r['residual_eff_pp'] for r in lowp))
    if rows_out:
        ws = [r['width_pp'] for r in rows_out]
        print('**判据③**：单 π 水平 ⇒ 12 格的 precision Wilson 宽度 min %.2f pp / max %.2f pp；'
              '答零项数（precision 分母）min %d / max %d'
              % (min(ws), max(ws), min(r['n_answered_zero'] for r in rows_out),
                 max(r['n_answered_zero'] for r in rows_out)))
        print('   ★ 预注册里"N_2 = 最低 π 格的答零数"在本设计里对应**唯一的 π=%.4f**，故上表 N 即该量；'
              '本轮**没有**多 π 水平，不得把它与 §M.21.10 的 N_2=12 混为一谈。' % pi)
        print('**判据②（迁移检验）**：**n/a —— 本轮不可做**。300 个真零**全部**用于构造混合语料，'
              '不存在"不相交的真零子集"来独立测 p；如实记 n/a + 原因，不静默略过。')
        out = os.path.join(csv_dir, 'E3_cells.json')
        with io.open(out, 'w', encoding='utf-8') as f:
            f.write(json.dumps(dict(pi=pi, n1=n1, n2=n2, cells=rows_out), ensure_ascii=False, indent=1))
        print('逐格明细写出：%s' % out)


if __name__ == '__main__':
    main()
