# -*- coding: utf-8 -*-
"""从 convention_rank_result.json **生成** §5.12 所引用的数值清单（供数字溯源闸门）。

正文引用的是"两口径的差"（如 48.2 pp），而结果 JSON 里存的是两个绝对值（−48.69 / −0.47…），
字面对不上会被判为"新造数字"。本脚本按正文使用的精度重算并落盘——**不是手填**，可复跑。
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
import io
import itertools
import json
import sys

sys.stdout.reconfigure(encoding='utf-8')
W = RP('analysis', 'work')
d = json.load(io.open(W + r'\convention_rank_result.json', encoding='utf-8'))
out = {'source': 'convention_rank_result.json（域内共同 item 交集上算）',
       'per_domain': {}, 'quoted_in_section_5_12': {}}
inv_total = 0
pair_total = 0
for ds, u in d['units'].items():
    rows = u['rows']
    dmax = max(rows, key=lambda r: abs(r['rho_all'] - r['rho_ans']))
    inv = sum(1 for a, b in itertools.combinations(rows, 2)
              if (a['rho_all'] - b['rho_all']) * (a['rho_ans'] - b['rho_ans']) < 0)
    pairs = len(rows) * (len(rows) - 1) // 2
    inv_total += inv
    pair_total += pairs
    out['per_domain'][ds] = {
        'n_config': len(rows), 'common_n': rows[0]['n'],
        'spearman_three_decimals': round(u['spearman'], 3),
        'max_abs_delta_rho_pp_one_decimal': round(abs(dmax['rho_all'] - dmax['rho_ans']), 1),
        'max_delta_config': dmax['cfg'],
        'inversions': inv, 'pairs': pairs,
    }
out['quoted_in_section_5_12'] = {
    'spearman_range_three_decimals': [
        min(v['spearman_three_decimals'] for v in out['per_domain'].values()),
        max(v['spearman_three_decimals'] for v in out['per_domain'].values())],
    'max_abs_delta_rho_pp_one_decimal_overall': max(
        v['max_abs_delta_rho_pp_one_decimal'] for v in out['per_domain'].values()),
    'inversions_dense': sum(out['per_domain'][k]['inversions'] for k in ('st_a', 'ucf')),
    'pairs_dense': sum(out['per_domain'][k]['pairs'] for k in ('st_a', 'ucf')),
    'inversions_all': inv_total, 'pairs_all': pair_total,
    'common_n': {k: out['per_domain'][k]['common_n'] for k in out['per_domain']},
    'n_config': {k: out['per_domain'][k]['n_config'] for k in out['per_domain']},
}
io.open(W + r'\convention_rank_quoted.json', 'w', encoding='utf-8').write(
    json.dumps(out, ensure_ascii=False, indent=1))
print(json.dumps(out['per_domain'], ensure_ascii=False, indent=1))
print(json.dumps(out['quoted_in_section_5_12'], ensure_ascii=False, indent=1))
print('已写 convention_rank_quoted.json')
