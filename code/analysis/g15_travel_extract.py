# -*- coding: utf-8 -*-
"""g15_travel_extract.py —— 【G15 第一步】把每个旋钮**实际扫过的档位值**从原始记录里取出来。

只读：不写任何已有文件；输出打到 stdout（外加一个 json 到 work/ 下，文件名带 g15_ 前缀）。

背景：三位评审独立提出同一个未排除的替代解释——
  **"某个旋钮的跨度（span）也许只是该旋钮**允许的输出动程**（travel）的单调函数，不是模型行为的属性。"**
  他们举的证据：检测 τ 扫 0.02→0.90（≈45× 相对动程），像素预算只走 100%→15%（≈6.7×）；
  F.10 只排除了**档数**（等点数）与**端点**，从未排除**量程**。

要检验它，先得把"动程"定义清楚。本脚本只做**取证**：把每条阶梯**逐档的实际 setting**打出来，
让人看清"动程"到底能不能算、以及怎么算。
"""
import collections
import csv
import glob
import io
import json
import os
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
ROOT = r'<WORKDIR>\PaperB'
DATA = os.path.join(ROOT, 'analysis', 'data')
PM = os.path.join(DATA, 'pod_mirror')
E2 = os.path.join(ROOT, 'analysis', 'e2_newh20')

out = {}


def dump(title, levels):
    print('\n--- %s ---' % title)
    for lbl, rho in levels:
        print('    %-28s rho = %s' % (lbl, ('%.2f' % rho) if rho is not None else '—'))
    vals = []
    for lbl, _ in levels:
        try:
            vals.append(float(str(lbl).split('=')[-1]))
        except ValueError:
            pass
    if len(vals) >= 2:
        vals.sort()
        print('    ⇒ 档位值 %s ｜ min=%g max=%g ｜ max/min = %.3f ｜ max−min = %g ｜ 档数 %d'
              % (vals, vals[0], vals[-1], vals[-1] / vals[0] if vals[0] else float('nan'),
                 vals[-1] - vals[0], len(vals)))
    return vals


print('=' * 104)
print('【① 检测 τ】来源 analysis/data/threeway_curves_v2.csv（按 match 口径分开）')
print('=' * 104)
p = os.path.join(DATA, 'threeway_curves_v2.csv')
tau = {}
if os.path.exists(p):
    rows = list(csv.DictReader(io.open(p, encoding='utf-8-sig')))
    print('  列：%s' % list(rows[0].keys()))
    for para in sorted(set(r['paradigm'] for r in rows)):
        for knob in sorted(set(r['knob'] for r in rows if r['paradigm'] == para)):
            for mt in sorted(set((r.get('match') or '') for r in rows
                                 if r['paradigm'] == para and r['knob'] == knob)):
                sub = [r for r in rows if r['paradigm'] == para and r['knob'] == knob
                       and (r.get('match') or '') == mt]
                seq = sorted(((float(r['setting']), float(r['rho'])) for r in sub), key=lambda x: x[0])
                if len(seq) < 3:
                    continue
                key = '%s | %s | %s' % (para, knob, mt)
                dump(key, [('t=%g' % s, v) for s, v in seq])
                tau[key] = dict(n=len(seq), lo=seq[0][0], hi=seq[-1][0],
                                rho_lo=seq[0][1], rho_hi=seq[-1][1],
                                span=max(v for _, v in seq) - min(v for _, v in seq))
out['tau'] = tau

print()
print('=' * 104)
print('【② 密度回归输入尺度】来源 analysis/data/threeway_curves.csv')
print('=' * 104)
p = os.path.join(DATA, 'threeway_curves.csv')
dens = {}
if os.path.exists(p):
    rows = list(csv.DictReader(io.open(p, encoding='utf-8-sig')))
    print('  列：%s' % list(rows[0].keys()))
    for ds in sorted(set(r['domain'] for r in rows if r['paradigm'] == '密度回归')):
        for knob in sorted(set(r['knob'] for r in rows
                               if r['paradigm'] == '密度回归' and r['domain'] == ds)):
            seq = sorted(((float(r['setting']), float(r['rho'])) for r in rows
                          if r['paradigm'] == '密度回归' and r['domain'] == ds and r['knob'] == knob),
                         key=lambda x: x[0])
            if len(seq) < 3:
                continue
            key = 'density / %s / %s' % (ds, knob)
            dump(key, [('mult=%g' % s, v) for s, v in seq])
            dens[key] = dict(n=len(seq), lo=seq[0][0], hi=seq[-1][0],
                             span=max(v for _, v in seq) - min(v for _, v in seq))
out['density'] = dens

print()
print('=' * 104)
print('【③ 像素预算】来源 analysis/data/pod_mirror/res_ctrl__*/res_ctrl_*.csv 的 budget 列')
print('=' * 104)
bud = {}
for mdl in ('q32', 'ivl'):
    for f in sorted(glob.glob(os.path.join(PM, 'res_ctrl__%s' % mdl, 'res_ctrl_*.csv'))):
        ds = os.path.basename(f)[len('res_ctrl_'):-4]
        rr = list(csv.DictReader(io.open(f, encoding='utf-8-sig')))
        bs = sorted(set(r['budget'] for r in rr), key=lambda x: float(x))
        rho = {}
        for b in bs:
            dd = {}
            for r in rr:
                if r['budget'] != b or '#r' in str(r.get('item') or ''):
                    continue
                try:
                    gt, pr = float(r['gt']), float(r['pred'])
                except (TypeError, ValueError):
                    continue
                if pr >= 1e5 or gt <= 0:
                    continue
                dd[str(r['item'])] = (gt, pr)
            if dd:
                sg = sum(g for g, _ in dd.values())
                rho[b] = 100.0 * (sum(x for _, x in dd.values()) - sg) / sg
        key = 'pxbudget / %s / %s' % (mdl, ds)
        dump(key, [('budget=%s' % b, rho.get(b)) for b in bs])
        if len(bs) >= 2:
            bud[key] = dict(n=len(bs), lo=float(bs[0]), hi=float(bs[-1]),
                            span=max(rho.values()) - min(rho.values()))
out['pxbudget'] = bud

print()
print('=' * 104)
print('【④ 切块 tiling】来源 pod_mirror/tile_results/ 与 ivl_aerial_tile_results/ 的**文件名**')
print('=' * 104)
til = {}
for f in sorted(glob.glob(os.path.join(PM, 'tile_results', 'vlm_*base_tile*.csv'))):
    print('    %s' % os.path.basename(f))
for f in sorted(glob.glob(os.path.join(PM, 'ivl_aerial_tile_results', '*tile*.csv'))):
    print('    %s' % os.path.basename(f))
print('    ⇒ 切块档位是**档数**（文件名里的数字），不是某个连续量纲 ⇒ 动程须另立定义（见报告 §未核实）')

print()
print('=' * 104)
print('【⑤ 提示词族 / ⑥ 输出契约】—— 都是**类别型**，没有连续动程')
print('=' * 104)
pf = sorted(os.path.basename(x) for x in glob.glob(os.path.join(PM, 'dense_prompt_results', 'vlm_st_a_base_V*.csv')))
print('    提示词族：%s' % pf)
arms = sorted(os.path.basename(x) for x in glob.glob(os.path.join(E2, 'e1_qwen3-vl-32b-awq_st_a_*.csv')))
print('    输出契约：%s' % [a.split('st_a_')[1][:-4] for a in arms])

j = os.path.join(ROOT, 'analysis', 'work', 'g15_travel_extract.json')
io.open(j, 'w', encoding='utf-8').write(json.dumps(out, ensure_ascii=False, indent=1))
print('\n已写 %s' % j)
