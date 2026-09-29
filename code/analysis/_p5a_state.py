# -*- coding: utf-8 -*-
"""_p5a_state.py —— P5a 现状盘点（只读）：覆盖率缺口、ERR 分布、上次 maxlen 16384 的失败原因。"""
import csv
import glob
import io
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')
OUTD = '/root/p5a_results'
print('=== 产物 ===')
for f in sorted(glob.glob(os.path.join(OUTD, '*.csv'))):
    rows = list(csv.DictReader(io.open(f, encoding='utf-8-sig', newline='')))
    err = [r for r in rows if str(r.get('raw', '')).startswith('ERR:')]
    dom = {}
    for r in rows:
        d = r.get('domain') or r.get('ds') or '?'
        dom[d] = dom.get(d, 0) + 1
    edom = {}
    for r in err:
        d = r.get('domain') or r.get('ds') or '?'
        edom[d] = edom.get(d, 0) + 1
    print('  %-40s 行=%-4d ERR=%-4d 域分布=%s ERR域=%s'
          % (os.path.basename(f), len(rows), len(err), dom, edom))
print()
print('=== ERR 文本样例（看是不是上下文超限）===')
for f in sorted(glob.glob(os.path.join(OUTD, '*.csv')))[:3]:
    rows = list(csv.DictReader(io.open(f, encoding='utf-8-sig', newline='')))
    err = [r for r in rows if str(r.get('raw', '')).startswith('ERR:')]
    if err:
        print('  %s:' % os.path.basename(f))
        for r in err[:2]:
            print('     %s | item=%s' % (str(r['raw'])[:120], r.get('item')))
        break
print()
print('=== 上次 maxlen=16384 起服日志尾部 ===')
p = '/root/logs/serve_p5a_Qwen3-VL-8B-Instruct_ml16384.log'
if os.path.exists(p):
    lines = io.open(p, encoding='utf-8', errors='replace').read().splitlines()
    for l in lines[-16:]:
        print('  ' + l[:160])
else:
    print('  无该日志')
print()
print('=== 探针接口 ===')
for p in ('/root/p5a_probe.py', '/root/p5a_criteria_frozen.json'):
    print('  %s %s' % (p, '存在' if os.path.exists(p) else '缺失'))
print('P5A_STATE_DONE')
