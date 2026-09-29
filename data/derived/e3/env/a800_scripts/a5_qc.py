# -*- coding: utf-8 -*-
"""统计某家族各臂：行数、parse_ok、ERR 类型分布（用 csv 模块，避免多行 raw 干扰）。"""
import csv
import glob
import io
import os
import re
import sys
import collections

sys.stdout.reconfigure(encoding='utf-8')
pat = sys.argv[1] if len(sys.argv) > 1 else '/root/e1_results/e1_llava-onevision-qwen2-7b-ov_ucf_*.csv'
for p in sorted(glob.glob(pat)):
    rows = list(csv.DictReader(io.open(p, encoding='utf-8-sig')))
    items = set(r['item'] for r in rows)
    errs = collections.Counter()
    for r in rows:
        raw = r.get('raw') or ''
        if str(raw).startswith('ERR:'):
            errs[str(raw)[:70]] += 1
    z = sum(1 for r in rows if str(r.get('pred', '')).strip() in ('0', '0.0'))
    print('%-58s 行=%-5d 去重item=%-5d pred0=%-4d ERR=%d'
          % (os.path.basename(p), len(rows), len(items), z, sum(errs.values())))
    for k, v in errs.most_common(3):
        print('      %4d  %s' % (v, k))
