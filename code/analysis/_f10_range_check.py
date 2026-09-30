# -*- coding: utf-8 -*-
"""_f10_range_check.py —— 只读：从 f10_random_drop_result.json 复算"检测器 τ 六条阶梯"的中位保留率区间。"""


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
d = json.loads(io.open(RP('analysis', 'work', 'f10_random_drop_result.json'),
                       encoding='utf-8').read())
for cal, v in d['per_caliber'].items():
    ms = {k: x['median'] for k, x in v.items()}
    in_dom = [x for k, x in ms.items() if '域内' in k]
    coco = [x for k, x in ms.items() if '域内' not in k]
    print('■ %-9s 六条中位: %s' % (cal, {k.split(' / ')[1]: x for k, x in ms.items()}))
    print('    全部区间 = %.2f–%.2f ｜ 域内 %.3f–%.3f ｜ COCO %.3f–%.3f'
          % (min(ms.values()), max(ms.values()), min(in_dom), max(in_dom), min(coco), max(coco)))
