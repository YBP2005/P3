# -*- coding: utf-8 -*-
"""w1_quote.py — 生成 W1/W2 的**引值文件** `w1_quoted.json`：正文与附录里要引用的每个数字的出处。

为什么要它：`en_check.py` 的 [F] 段要求正文里每个数字 token 都出现在"数字权威"文本里。
本脚本把 W1/W2 的所有可引用数字**从产物现算**并写成 JSON（再登记为权威），
从而满足"不得手打数字"的纪律——手打的数字是不可溯源的断言。

实现上直接 import `w1_judge`（复用它的 read_csv/is_zero/is_abstain/stats 与 P1–P6 判定），
避免两套分类逻辑不一致（本项目已因"同一缺陷修三处"吃过亏）。
"""
import json
import os
import statistics as st
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import w1_judge as J  # noqa: E402

sys.stdout.reconfigure(encoding='utf-8')
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'w1_quoted.json')
A800 = J.A800
AB = ('abstain', 'cannot_judge', 'no_people', 'no_objects')
CAP = 1e5


def pct(x, nd=1):
    return None if x is None else round(100.0 * x, nd)


def cls(r):
    raw = (r.get('raw') or '').lower()
    if any(k in raw for k in AB):
        return 'abstain'
    p = str(r.get('pred', '')).strip()
    if p in ('0', '0.0'):
        return 'zero'
    if p not in ('', 'None'):
        try:
            return 'number' if abs(float(p)) < CAP else 'unparsed'
        except ValueError:
            return 'unparsed'
    return 'unparsed'


def rates(rows):
    c = {}
    for r in rows:
        c[cls(r)] = c.get(cls(r), 0) + 1
    n = len(rows)
    return {k: round(100.0 * v / n, 1) for k, v in c.items()}


def mae_med(fam, ds, arm='base', conv='A'):
    rows = J.read_csv(os.path.join(A800, 'zero', 'e1_%s_%s_%s_native.csv' % (fam, ds, arm)))
    if not rows:
        return None, None
    errs, rels = [], []
    for r in rows:
        gt = float(r['gt']); p = str(r.get('pred', '')).strip()
        if p in ('', 'None') or any(k in (r.get('raw') or '').lower() for k in AB):
            if conv == 'A':
                errs.append(abs(gt))
            continue
        try:
            v = float(p)
        except ValueError:
            if conv == 'A':
                errs.append(abs(gt))
            continue
        if abs(v) >= CAP:
            continue
        errs.append(abs(v - gt)); rels.append(abs(v - gt) / gt)
    return (st.mean(errs) if errs else None), (st.median(rels) if rels else None)


def main():
    fams, cells = J.collect()
    R = {}
    R['panel'] = dict(families=len(fams), list=fams,
                      lineages=6, qwen_families=0,
                      domains=4, zero_cells=len(os.listdir(os.path.join(A800, 'zero'))),
                      nonzero_cells=len(os.listdir(os.path.join(A800, 'nonzero'))),
                      fsc_cells=len(os.listdir(os.path.join(A800, 'fsc'))),
                      hosted_cells=len(os.listdir(os.path.join(A800, 'hosted'))))
    P1 = J.p1(fams, cells)
    R['P1'] = dict(k=P1['k'], n=P1['n_families'], cells_ok=P1['cells_ok_total'],
                   cells_total=P1['cells_total'],
                   per_family={r['fam']: pct(r['resid'], 2) for r in P1['per_family']},
                   wilson_hi={r['fam']: pct(r['wilson_hi'], 2) for r in P1['per_family']},
                   unparsed_base={r['fam']: pct(r['unparsed_base']) for r in P1['per_family']},
                   ratio_pass=P1['ratio_pass'])
    P2 = J.p2(fams, cells)
    R['P2'] = dict(n_qualify=P2['n_qualify'], n_ok=P2['n_ok'], frac=pct(P2['frac'], 0),
                   dense_mean=P2['dense_mean'], aerial_mean=P2['aerial_mean'], gap=P2['gap'])
    P3 = J.p3(fams, cells)
    R['P3'] = dict(s2_domain=round(P3['s2_domain'], 4), s2_family=round(P3['s2_family'], 4),
                   ratio=round(P3['s2_domain'] / P3['s2_family'], 1),
                   diff=round(P3['diff'], 4),
                   boot_ci=[round(P3['boot_ci'][0], 4), round(P3['boot_ci'][1], 4)],
                   pass_=P3['pass_'])
    P4 = J.p4(fams, cells)
    R['P4'] = dict(per_domain={d: dict(spearman=round(v['spearman'], 3), top1_A=v['top1_A'],
                                       top1_B=v['top1_B'], top1_same=v['top1_same'])
                               for d, v in P4['per_domain'].items()},
                   top1_same=P4['top1_same'], top1_total=P4['top1_total'],
                   a_pass=P4['a_pass'], b_pass=P4['b_pass'])
    P5 = J.p5()
    if P5.get('evaluable'):
        R['P5'] = dict(per_model={s['tag']: dict(base_zero_pct=pct(s['base_w'], 1),
                                                permit_resid_pct=pct(s['permit_w'], 2),
                                                trunc_pct=pct(s['trunc_frac'], 2))
                                  for s in P5['per_model']},
                       a_pass=P5['a_pass'], b_pass=P5['b_pass'], k=P5['k_permit'], n=P5['n_eval'])
    P6 = J.p6(fams)
    if P6.get('evaluable'):
        R['P6'] = dict(per_family={r['fam']: dict(base_zero_pct=pct(r['w_base'], 1),
                                                 exemplar_zero_pct=pct(r['w_exemplar'], 1),
                                                 drop_pp=round(r['drop_pp'], 1))
                                   for r in P6['per_family']},
                       k=P6['k'], n=P6['n'], pass_=P6['pass_'])
    # 行为分布（托管端点）
    beh = {}
    import glob
    for p in sorted(glob.glob(os.path.join(A800, 'hosted', '*.csv'))):
        tag, ds, arm = os.path.basename(p)[:-4].split('__')
        beh.setdefault(tag, {})[arm] = rates(J.read_csv(p) or [])
    R['hosted_behaviour_pct'] = beh
    # FSC 示例臂：零率 + 精度
    ex = {}
    for f in fams:
        b = J.read_csv(os.path.join(A800, 'fsc', 'fsc_%s_base.csv' % f))
        e = J.read_csv(os.path.join(A800, 'fsc', 'fsc_%s_exemplar3.csv' % f))
        if b and e:
            _, rb = None, None
            rb = rates(b).get('zero', 0.0)
            re_ = rates(e).get('zero', 0.0)
            ex[f] = dict(base_zero_pct=rb, exemplar_zero_pct=re_, drop_pp=round(rb - re_, 1))
    R['fsc_exemplar_pct'] = ex
    # 逐域残留（供 §5.14/M.31 的表）
    dom = {}
    for f in fams:
        dom[f] = {}
        for ds in J.DOMS:
            b = J.read_csv(os.path.join(A800, 'zero', 'e1_%s_%s_base_native.csv' % (f, ds)))
            p = J.read_csv(os.path.join(A800, 'zero', 'e1_%s_%s_permit_native.csv' % (f, ds)))
            if b and p:
                dom[f][ds] = dict(base_zero_pct=rates(b).get('zero', 0.0),
                                  permit_zero_pct=rates(p).get('zero', 0.0),
                                  permit_abstain_pct=rates(p).get('abstain', 0.0),
                                  base_unparsed_pct=rates(b).get('unparsed', 0.0))
    R['domain_table_pct'] = dom
    # 同 item 精度对比（托管 vs 开源）：**交集 253 条 + 卫生规则（pred<1e5）**，
    # 与 `_hosted_vs_open3.py` 的口径一致；只对"给了数字"的 item 计分（这是"它们给的数字准不准"的直接答案）。
    ser = {}
    for f in fams:
        rows = []
        for ds in ('st_a', 'ucf'):
            rows += J.read_csv(os.path.join(A800, 'zero', 'e1_%s_%s_base_native.csv' % (f, ds))) or []
        ser[f] = {r['item']: r for r in rows}
    for tag in ('gemini-3.8-flash', 'gpt-5.6-luna', 'grok-4.6'):
        rows = []
        for ds in ('st_a', 'ucf'):
            rows += J.read_csv(os.path.join(A800, 'hosted', '%s__%s__base.csv' % (tag, ds))) or []
        ser['hosted:' + tag] = {r['item']: r for r in rows}
    keys = None
    for v in ser.values():
        keys = set(v) if keys is None else (keys & set(v))
    keys = sorted(keys or [])
    acc = {}
    for name, d in ser.items():
        rels, z = [], 0
        for k in keys:
            r = d[k]
            if str(r.get('pred', '')).strip() in ('0', '0.0'):
                z += 1
            try:
                v = float(str(r.get('pred', '')).strip())
            except ValueError:
                continue
            if abs(v) >= CAP:
                continue
            rels.append(abs(v - float(r['gt'])) / float(r['gt']))
        acc[name] = dict(common_items=len(keys), n_numeric=len(rels),
                         median_rel_pct=(round(100 * st.median(rels), 1) if rels else None),
                         zero_pct=round(100.0 * z / len(keys), 1) if keys else None)
    R['same_item_accuracy'] = acc
    # 示例臂的**精度**（零率之外的另一半证据）：口径 A —— 对**全部 item** 计算，0 视为"预测 0"，
    # 未解析项无法计分故跳过（这一口径与 §5.12 的口径 A 一致，且避免"只对少数给了数字的 item 比较"的幸存偏差）。
    exa = {}
    for f in fams:
        row = {}
        for arm in ('base', 'exemplar3'):
            rows = J.read_csv(os.path.join(A800, 'fsc', 'fsc_%s_%s.csv' % (f, arm)))
            if not rows:
                continue
            errs = []          # (绝对误差, gt) 逐项配对
            nums = []          # 只在"给了数字"时的相对误差
            for r in rows:
                p = str(r.get('pred', '')).strip()
                gt = float(r['gt'])
                if p in ('0', '0.0'):
                    errs.append((abs(gt), gt))                # 口径 A：答 0 记为预测 0
                    continue
                try:
                    v = float(p)
                except ValueError:
                    continue
                if abs(v) >= CAP:
                    continue
                errs.append((abs(v - gt), gt)); nums.append(abs(v - gt) / gt)
            # ★ 2026-09-23 修：原先在推导式里用了**循环外泄漏的 gt**，把相对误差全按最后一项的 gt 算 ⇒ 数字错乱。
            #   现改为逐项配对 (误差, gt)。
            row[arm + '_convA_mae'] = round(st.mean([e for e, _ in errs]), 1) if errs else None
            row[arm + '_convA_median_rel_pct'] = (round(100 * st.median([e / g for e, g in errs]), 1)
                                                 if errs else None)
            row[arm + '_numeric_only_median_rel_pct'] = round(100 * st.median(nums), 1) if nums else None
            row[arm + '_n_scored'] = len(errs)
            row[arm + '_n_numeric'] = len(nums)
        if row:
            exa[f] = row
    R['fsc_exemplar_accuracy_pct'] = exa
    # 两个旋钮的最大幅度（pp）：合同旋钮 = base − permit；分辨率旋钮 = |base@native − base@s640|
    dc, dr = [], []
    for f in fams:
        for ds in J.DOMS:
            b = J.read_csv(os.path.join(A800, 'zero', 'e1_%s_%s_base_native.csv' % (f, ds)))
            p = J.read_csv(os.path.join(A800, 'zero', 'e1_%s_%s_permit_native.csv' % (f, ds)))
            r640 = J.read_csv(os.path.join(A800, 'zero', 'e1_%s_%s_base_s640.csv' % (f, ds)))
            if not (b and p and r640):
                continue
            wb = rates(b).get('zero', 0.0); wp = rates(p).get('zero', 0.0); wr = rates(r640).get('zero', 0.0)
            dc.append(wb - wp); dr.append(abs(wb - wr))
    R['knob_amplitudes_pp'] = dict(contract_max=round(max(dc), 1) if dc else None,
                                   contract_median=round(st.median(dc), 1) if dc else None,
                                   resolution_max=round(max(dr), 1) if dr else None,
                                   resolution_median=round(st.median(dr), 1) if dr else None,
                                   n_cells=len(dc))
    with open(OUT, 'w', encoding='utf-8', newline='\n') as fh:
        json.dump(R, fh, ensure_ascii=False, indent=2, sort_keys=True)
    print('写出 %s' % OUT)
    # 供撰写时直接取用的关键 token 摘要
    body = open(OUT, encoding='utf-8').read()
    import re
    toks = sorted(set(re.findall(r'\d+(?:[.,]\d+)*', body)))
    print('引值文件内数字 token 共 %d 个（覆盖正文将引用的全部数字）' % len(toks))
    print('P1 残留：%s' % R['P1']['per_family'])
    print('P3 方差：%s / %s（%s×），CI %s' % (R['P3']['s2_domain'], R['P3']['s2_family'],
                                            R['P3']['ratio'], R['P3']['boot_ci']))
    print('P2：合格 %s 个，满足 %s 个 = %s%%' % (R['P2']['n_qualify'], R['P2']['n_ok'], R['P2']['frac']))
    print('P6：%s' % R['P6']['per_family'])
    return 0


if __name__ == '__main__':
    sys.exit(main())
