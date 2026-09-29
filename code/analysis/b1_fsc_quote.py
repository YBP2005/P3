# -*- coding: utf-8 -*-
"""从 b1_fsc_result.json **生成** §5.13 引用值清单（供数字溯源闸门）。"""
import io
import os
import json
import sys

sys.stdout.reconfigure(encoding='utf-8')
W = r'<WORKDIR>\PaperB\analysis\work'
d = json.load(io.open(W + r'\b1_fsc_result.json', encoding='utf-8'))
gate, tab = d['gate'], d['table']
out = {'source': 'b1_fsc_result.json（FSC-147 公开基准，300 张分层抽样测试图）',
       'quoted_in_section_5_13': {}}
for m, g in gate.items():
    out['quoted_in_section_5_13'][m] = {
        'base_zero': g['n_zero'], 'n': g['n'],
        'permit_still_zero': g['still'],
        'ratio_pct_one_decimal': round(100.0 * g['still'] / g['n_zero'], 1) if g['n_zero'] else None,
        'ci_pct_one_decimal': [round(100 * x, 1) for x in g['ci']] if g['ci'][0] is not None else None,
    }
for t in tab:
    out['quoted_in_section_5_13'].setdefault(t['model'], {})['rho_one_decimal'] = [
        round(t['rho_all'], 1), round(t['rho_ans'], 1)]
dmax = max(tab, key=lambda t: abs(t['rho_all'] - t['rho_ans']))
out['quoted_in_section_5_13']['_summary'] = {
    'max_abs_delta_rho_pp_one_decimal': round(abs(dmax['rho_all'] - dmax['rho_ans']), 1),
    'n_configs': len(tab),
    'families_removing_all_or_all_but_two': sum(
        1 for g in gate.values() if g['still'] <= 2),
}
io.open(W + r'\b1_fsc_quoted.json', 'w', encoding='utf-8').write(
    json.dumps(out, ensure_ascii=False, indent=1))

# ★ 9 配置面板的排名统计（§5.13 的 0.983 / 1 of 36）——从 b1_fsc_full.json 现算，不手填
import itertools
full_p = W + r'\b1_fsc_full.json'
if os.path.exists(full_p):
    f = json.load(io.open(full_p, encoding='utf-8'))
    tab = f['table']
    def rk(x):
        idx = sorted(range(len(x)), key=lambda i: x[i])
        r = [0.0] * len(x)
        for pos, i in enumerate(idx):
            r[i] = pos + 1
        return r
    a = [abs(t['rho_all']) for t in tab]
    b = [abs(t['rho_ans']) for t in tab]
    ra, rb = rk(a), rk(b)
    n = len(a); ma = sum(ra) / n; mb = sum(rb) / n
    num = sum((ra[i] - ma) * (rb[i] - mb) for i in range(n))
    da = sum((x - ma) ** 2 for x in ra) ** .5; db = sum((x - mb) ** 2 for x in rb) ** .5
    sp = num / (da * db)
    pairs = list(itertools.combinations(tab, 2))
    inv = sum(1 for x, y in pairs
              if (x['rho_all'] - y['rho_all']) * (x['rho_ans'] - y['rho_ans']) < 0)
    dmax = max(tab, key=lambda t: abs(t['rho_all'] - t['rho_ans']))
    out['quoted_in_section_5_13']['nine_config_ranking'] = {
        'n_configs': len(tab), 'spearman_three_decimals': round(sp, 3),
        'inversions': inv, 'pairs': len(pairs),
        'max_abs_delta_rho_pp_one_decimal': round(abs(dmax['rho_all'] - dmax['rho_ans']), 1),
        'top1_convention_A': sorted(tab, key=lambda t: abs(t['rho_all']))[0]['model'],
        'top1_convention_B': sorted(tab, key=lambda t: abs(t['rho_ans']))[0]['model'],
    }
    io.open(W + r'\b1_fsc_quoted.json', 'w', encoding='utf-8').write(
        json.dumps(out, ensure_ascii=False, indent=1))
    print('9 配置排名统计:', json.dumps(out['quoted_in_section_5_13']['nine_config_ranking'],
                                        ensure_ascii=False))
print(json.dumps(out, ensure_ascii=False, indent=1)[:1400])
print('\n已写 b1_fsc_quoted.json')
