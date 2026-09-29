# -*- coding: utf-8 -*-
"""_f10_range_check.py —— 只读：从 f10_random_drop_result.json 复算"检测器 τ 六条阶梯"的中位保留率区间。"""
import io
import json
import sys

sys.stdout.reconfigure(encoding='utf-8')
d = json.loads(io.open(r'<WORKDIR>\PaperB\analysis\work\f10_random_drop_result.json',
                       encoding='utf-8').read())
for cal, v in d['per_caliber'].items():
    ms = {k: x['median'] for k, x in v.items()}
    in_dom = [x for k, x in ms.items() if '域内' in k]
    coco = [x for k, x in ms.items() if '域内' not in k]
    print('■ %-9s 六条中位: %s' % (cal, {k.split(' / ')[1]: x for k, x in ms.items()}))
    print('    全部区间 = %.2f–%.2f ｜ 域内 %.3f–%.3f ｜ COCO %.3f–%.3f'
          % (min(ms.values()), max(ms.values()), min(in_dom), max(in_dom), min(coco), max(coco)))
