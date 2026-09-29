# -*- coding: utf-8 -*-
"""最终清点：按 CSV 解析器统计（不用 wc -l），并做按预期尺寸的独立校验。"""
import csv
import glob
import json
import os
import subprocess
import sys

DIRS = {'zero': '/root/e1_results', 'nonzero': '/root/e1_results_nonzero'}


def label_of(fn):
    b = os.path.basename(fn)
    if b.startswith('e1_'):
        b = b[3:]
    for cut in ('_st_a_', '_st_b_', '_ucf_'):
        if cut in b:
            b = b.split(cut)[0]
            break
    return b


print('===== 按 CSV 解析器统计（记录数 / 去重 item）=====')
for kind, d in DIRS.items():
    per = {}
    for p in sorted(glob.glob(os.path.join(d, '*.csv'))):
        lab = label_of(p)
        tot = 0
        items = set()
        try:
            with open(p, encoding='utf-8-sig', errors='replace') as f:
                for r in csv.DictReader(f):
                    tot += 1
                    it = str(r.get('item', ''))
                    items.add(it.split('#r')[0] if '#r' in it else it)
        except Exception as ex:
            print('  ERR', p, ex)
        a = per.setdefault(lab, [0, 0, 0])
        a[0] += 1
        a[1] += tot
        a[2] += len(items)
    print('--- %s (%s) ---' % (kind, d))
    grand = [0, 0, 0]
    for lab in sorted(per, key=lambda k: -per[k][1]):
        n, tot, uni = per[lab]
        grand[0] += n
        grand[1] += tot
        grand[2] += uni
        print('  %-24s 文件 %3d  记录 %6d  去重item %5d' % (lab, n, tot, uni))
    print('  %-24s 文件 %3d  记录 %6d  去重item(和) %5d' % ('[合计]', grand[0], grand[1], grand[2]))

print()
print('===== 独立尺寸校验（verify_model.py，按 hub 清单期望尺寸）=====')
for mid, dd in (('cyankiwi/Qwen3-VL-32B-Instruct-AWQ-8bit', '/root/models/Qwen3-VL-32B-Instruct-AWQ-8bit'),
                ('Qwen/Qwen2.5-VL-72B-Instruct-AWQ', '/root/models/Qwen2.5-VL-72B-Instruct-AWQ')):
    r = subprocess.run(['/usr/local/miniconda3/bin/python3', '/root/verify_model.py', mid, dd],
                       capture_output=True, text=True, timeout=300)
    print('  rc=%d' % r.returncode)
    sys.stdout.write(r.stdout)
    if r.stderr.strip():
        print('  stderr:', r.stderr.strip()[:400])

print()
print('===== 目录占用 =====')
for d in ('/root/models/Qwen3-VL-32B-Instruct-AWQ-8bit',
          '/root/models/Qwen2.5-VL-72B-Instruct-AWQ',
          '/root/e1_results', '/root/e1_results_nonzero'):
    t = 0
    for root, dirs, files in os.walk(d):
        for f in files:
            try:
                t += os.path.getsize(os.path.join(root, f))
            except Exception:
                pass
    print('  %-50s %.2f GB' % (d, t / 1e9))
