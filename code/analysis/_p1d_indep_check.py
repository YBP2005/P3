# -*- coding: utf-8 -*-
"""_p1d_indep_check.py —— P1d/P1e/P1f/P5c 的**独立复算**（直读原始产物，另写一套实现）。

纪律：不复用任何分析器的函数，只读它们的产物 JSON 做比对。实现差异（故意）：
  · 用 `csv.reader` 按列名索引的**另一种**解析（不靠 DictReader 的键）；
  · 零率按 **(分子, 分母)** 直接累加，不去引用任何中间 dict；
  · P5c 的 p0 / L* / cos 从 **JSONL 逐项**重算（不读 p5c_hidden 写的 summary 文件）——
    这同时校验了"summary 与逐项记录一致"。
输出：逐项 ✓/✗，任一不符 exit 1。
"""
import csv
import io
import json
import math
import os
import statistics as st
import sys

sys.stdout.reconfigure(encoding='utf-8')
OUTD = '/root/p1d_results'
FAMS = ['Phi-3.5-vision-instruct', 'Qwen3-VL-8B-Instruct', 'llava-onevision-qwen2-7b-ov',
        'gemma3-12b', 'Qwen3-VL-32B-Instruct', 'InternVL3_5-8B']
LAD = [('neutral0', 0), ('mention5', 5), ('mention50', 50), ('placebo100', 100), ('mention800', 800)]
bad = 0


def raw_rows(path):
    """另一种解析：Reader + 手工列索引。"""
    with io.open(path, encoding='utf-8-sig', newline='') as f:
        rd = csv.reader(f)
        hdr = next(rd)
        i_item, i_pred = hdr.index('item'), hdr.index('pred')
        i_zero, i_ok = hdr.index('is_zero'), hdr.index('parse_ok')
        out = []
        for r in rd:
            if not r or len(r) < len(hdr):
                continue
            out.append((r[i_item], r[i_pred], r[i_zero], r[i_ok]))
        return out


def stats(fam, arm):
    p = os.path.join(OUTD, 'p1d_%s_%s.csv' % (fam, arm))
    if not os.path.exists(p):
        return None
    rs = raw_rows(p)
    n = len(rs)
    z = sum(1 for _, _, zz, _ in rs if str(zz).strip() == '1')
    vals = []
    for _, pr, _, _ in rs:
        s = str(pr).strip()
        if s.lstrip('-').isdigit():
            vals.append(int(s))
    return dict(n=n, z=z, zero=z / n, med=(st.median(vals) if vals else None))


print('=== ① H_A2p：forbid0 − base 的 Δzero（6 族）===')
R = json.loads(io.open('/root/p1df_result.json', encoding='utf-8').read())
okn = 0
for f in FAMS:
    b, x = stats(f, 'base'), stats(f, 'forbid0')
    if not b or not x:
        continue
    d = (x['zero'] - b['zero']) * 100
    w = R['H_A2p']['per_family'].get(f)
    good = w is not None and abs(d - w) < 0.06
    okn += good
    print('  %-30s Δ %+7.2f（主 %+7.2f） %s' % (f[:30], d, w if w is not None else float('nan'),
                                              '✓' if good else '✗'))
bad += (okn != 6)
npass = sum(1 for f in FAMS if (stats(f, 'forbid0')['zero'] - stats(f, 'base')['zero']) * 100 <= -10.0)
print('  独立判定：达标 %d/6 ⇒ %s（主脚本 %s）'
      % (npass, 'FAIL' if npass < 3 else 'PASS', 'PASS' if R['H_A2p']['passed'] else 'FAIL'))
bad += (npass >= 3) != R['H_A2p']['passed']

print('\n=== ② H_N0：P1d base vs 已发表 base（跨会话）===')
okn = 0
for f in FAMS:
    new = stats(f, 'base')
    old = raw_rows('/root/p1_results/p1_%s_base.csv' % f)
    zo = sum(1 for _, _, zz, _ in old if str(zz).strip() == '1')
    d = (new['zero'] - zo / len(old)) * 100
    w = next((x['delta_pp'] for x in R['H_N0'] if x['family'] == f), None)
    good = w is not None and abs(d - w) < 0.06
    okn += good
    print('  %-30s Δ %+6.2f（主 %+6.2f） %s' % (f[:30], d, w if w is not None else float('nan'),
                                              '✓' if good else '✗'))
bad += (okn != 6)

print('\n=== ③ P1f 阶梯：逐点零率与中位数 ===')
okn = tot = 0
for f in FAMS:
    pts = []
    for arm, a in LAD:
        s = stats(f, arm)
        if s:
            pts.append((a, s))
    if len(pts) < 3:
        continue
    w = R['P1f'].get(f)
    for a, s in pts:
        ww = next((p for p in w['points'] if p['anchor'] == a), None)
        good = ww and abs(s['zero'] * 100 - ww['zero_pct']) < 0.06 and \
            (s['med'] == ww['median'] or (s['med'] is None and ww['median'] is None))
        tot += 1
        okn += bool(good)
        if not good:
            print('  ✗ %s anchor=%d 独立 %.2f%%/%s vs 主 %.2f%%/%s'
                  % (f[:24], a, s['zero'] * 100, s['med'], ww['zero_pct'], ww['median']))
print('  逐点比对 %d/%d 一致' % (okn, tot))
bad += (okn != tot)

print('\n=== ④ P5c：从逐项 JSONL 重算 p0 / L* / cos（不读 summary）===')
import torch  # noqa: E402
S = json.loads(io.open('/root/p5c_results2_summary.json', encoding='utf-8').read())
rows = [json.loads(l) for l in io.open('/root/p5c_results2.jsonl', encoding='utf-8')]
accp0 = {'base': [], 'forbid0': [], 'neutral0': []}
cosf = cosn = None
sumf = sumn = None
k = 0
for r in rows:
    for a in accp0:
        if r['arms'].get(a, {}).get('p0') is not None:
            accp0[a].append(r['arms'][a]['p0'])
    if r['arms']['base'].get('answer') == 0:
        # ★ base 臂的 `cos_vs_base` 是"与自己的余弦"= 恒 1.0，**不能**拿它当分层曲线；
        #   要读 forbid0 臂的那一列（这正是与 summary 同源的定义）。第一版这里写错，
        #   于是 L* 永远找不到、报 None —— 独立复算连自己的 bug 一起抓出来了。
        cf = r['arms'].get('forbid0', {}).get('cos_vs_base')
        if cf is None:
            continue
        if cosf is None:
            L = len(cf)
            cosf, cosn = [0.0] * L, [0.0] * L
            sumf, sumn = [0.0] * L, [0.0] * L
        for i, v in enumerate(cf):
            cosf[i] += v
        for i, v in enumerate(r['arms']['neutral0']['cos_vs_base']):
            cosn[i] += v
        k += 1
print('  base-zero 计数：独立 %d vs summary %d %s' % (k, S['n_base_zero'], '✓' if k == S['n_base_zero'] else '✗'))
bad += (k != S['n_base_zero'])
p0i = {a: (sum(v) / len(v)) for a, v in accp0.items()}
okp = all(abs(p0i[a] - S['p0_mean'][a]) < 1e-9 for a in p0i)
print('  p0 均值：独立 %s' % {a: round(v, 4) for a, v in p0i.items()})
print('          summary %s  %s' % ({a: round(S['p0_mean'][a], 4) for a in p0i}, '✓' if okp else '✗'))
bad += (not okp)
Lf = None
for i, v in enumerate(cosf):
    if v / k < 0.99:
        Lf = i
        break
print('  L*(forbid0)：独立 %s vs summary %s %s' % (Lf, S['Lstar_forbid0'],
                                              '✓' if Lf == S['Lstar_forbid0'] else '✗'))
bad += (Lf != S['Lstar_forbid0'])
print('  n_layer：独立 %d vs summary %d' % (len(cosf), S['n_layer']))
bad += (len(cosf) != S['n_layer'])

print('\n%s（%d 处不符）' % ('INDEP_OK' if bad == 0 else 'INDEP_FAIL', bad))
raise SystemExit(1 if bad else 0)
