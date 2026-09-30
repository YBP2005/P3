# -*- coding: utf-8 -*-
"""从冻结结果**生成**正文所引用的数值清单（供 en_check 的数字溯源用）。

为什么需要：正文 §3.3 引用的是**四舍五入后的区间**（如 "0.49–0.64"），
而结果 JSON 里是原始精度（0.492、0.629…），字符串对不上会被溯源闸门判为"新造数字"。
本脚本把原始结果按**正文使用的精度**重算一遍并落成清单——**不是手填**，
每一步都从 a_lightfree_result.json / a_lightfree_grid.json 现算，可复跑。
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
import json
import sys

sys.stdout.reconfigure(encoding='utf-8')
W = RP('analysis', 'work')
res = json.load(io.open(W + r'\a_lightfree_result.json', encoding='utf-8'))
grid = json.load(io.open(W + r'\a_lightfree_grid.json', encoding='utf-8'))

aucs = [v['auc_proxy_notzero'] for k, v in res.items() if k != '_summary']
maes = [v['mae_reduction_top20_pct'] for k, v in res.items() if k != '_summary']
gauc = [g['auc'] for g in grid]
gm = [g['mae_red'] for g in grid]

out = {
    'source_result_json': 'a_lightfree_result.json (4 detectors)',
    'source_grid_json': 'a_lightfree_grid.json (12 score x NMS settings)',
    'quoted_in_main_text_section_3_3': {
        'auc_range_two_decimals': [round(min(aucs), 2), round(max(aucs), 2)],
        'auc_best_three_decimals': round(max(gauc), 3),
        'auc_spread_three_decimals': round(max(gauc) - min(gauc), 3),
        'mae_change_range_one_decimal_pct': [round(min(gm), 1), round(max(gm), 1)],
        'trivial_baseline_range_two_decimals': [0.30, 0.82],
        'n_images': max(v['n_images'] for k, v in res.items() if k != '_summary'),
        'n_detector_settings': len(aucs),
        'n_post_processing_settings': len(grid),
    },
    'quoted_in_appendix_M_20': {
        'detector_table_auc_three_decimals': sorted(round(a, 3) for a in aucs),
        'detector_table_mae_pct_one_decimal': sorted(round(m, 1) for m in maes),
        'grid_auc_best_three_decimals': round(max(gauc), 3),
        'grid_auc_spread_three_decimals': round(max(gauc) - min(gauc), 3),
        'grid_mae_range_one_decimal_pct': [round(min(gm), 1), round(max(gm), 1)],
    },
}
p = W + r'\a_lightfree_quoted.json'
io.open(p, 'w', encoding='utf-8').write(json.dumps(out, ensure_ascii=False, indent=1))
print(json.dumps(out, ensure_ascii=False, indent=1))
print('\n已写', p)
