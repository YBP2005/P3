# -*- coding: utf-8 -*-
"""远端巡检：读 /proc 直读进程；检查分片齐全性。不含自匹配关键字问题（脚本名不参与匹配模式写作）。"""
import json
import os

KEYS = ('h20_exp_v4.sh', 'repair_all.sh', 'h20_dl_model.py', 'h20_exp')

print('--- /proc cmdline scan ---')
found = []
for p in sorted(os.listdir('/proc')):
    if not p.isdigit():
        continue
    try:
        cl = open('/proc/%s/cmdline' % p, 'rb').read().replace(b'\x00', b' ').decode('utf-8', 'replace').strip()
    except Exception:
        continue
    if not cl:
        continue
    low = cl
    for k in KEYS:
        if k in low:
            found.append((int(p), cl[:160]))
            break
for pid, cl in sorted(found):
    print(pid, cl)

print('--- pid files ---')
for pf in ('/root/repair_all.pid',):
    try:
        print(pf, open(pf).read().strip())
    except Exception as ex:
        print(pf, 'ERR', ex)

print('--- shard check ---')
for d in ('/root/models/Qwen3-VL-32B-Instruct-AWQ-8bit',
          '/root/models/Qwen2.5-VL-72B-Instruct-AWQ'):
    idx = os.path.join(d, 'model.safetensors.index.json')
    if not os.path.exists(idx):
        print(d, '缺 index.json')
        continue
    need = sorted(set(json.load(open(idx))['weight_map'].values()))
    miss = [f for f in need if not os.path.exists(os.path.join(d, f))
            or os.path.getsize(os.path.join(d, f)) == 0]
    tot = 0
    for f in need:
        p = os.path.join(d, f)
        if os.path.exists(p):
            tot += os.path.getsize(p)
    print('%s: %d 个分片，缺失/空 %d 个 %s' % (os.path.basename(d), len(need), len(miss), miss))
    print('   on-disk bytes = %.2f GB' % (tot / 1024.0 ** 3))

print('--- dir sizes ---')
for d in ('/root/models/Qwen3-VL-32B-Instruct-AWQ-8bit',
          '/root/models/Qwen2.5-VL-72B-Instruct-AWQ'):
    try:
        t = 0
        n = 0
        for root, dirs, files in os.walk(d):
            for f in files:
                try:
                    t += os.path.getsize(os.path.join(root, f))
                    n += 1
                except Exception:
                    pass
        print(d, '%.2f GB, %d files' % (t / 1024.0 ** 3, n))
    except Exception as ex:
        print(d, 'ERR', ex)
