# -*- coding: utf-8 -*-
"""_p1d_status.py —— P1d 只读进度：各臂已落盘行数 + 实时零率/弃答率 + 吞吐。"""
import csv
import glob
import io
import os
import sys
import time

sys.stdout.reconfigure(encoding='utf-8')
OUTD = '/root/p1d_results'
print('=== 产物进度（%s）===' % time.strftime('%H:%M:%S'))
files = sorted(glob.glob(os.path.join(OUTD, '*.csv')))
if not files:
    print('  （尚无文件）')
for f in files:
    rows = list(csv.DictReader(io.open(f, encoding='utf-8-sig')))
    it = {str(r['item']) for r in rows}
    z = sum(1 for r in rows if str(r.get('is_zero', '')).strip() == '1')
    a = sum(1 for r in rows if str(r.get('abstain', '')).strip() == '1')
    pf = sum(1 for r in rows if str(r.get('parse_ok', '')).strip() != '1')
    print('  %-46s %4d/675  zero=%-4d abst=%-4d pf=%-3d'
          % (os.path.basename(f)[4:-4], len(it), z, a, pf))

print()
print('=== 探针日志尾部（吞吐）===')
for f in sorted(glob.glob('/root/logs/p1d_probe_*.log')):
    lines = [l.rstrip() for l in io.open(f, encoding='utf-8', errors='replace') if 'it/s' in l]
    if lines:
        print('  %-46s %s' % (os.path.basename(f)[10:-4], lines[-1].strip()[:70]))
print()
print('STATUS_DONE')
