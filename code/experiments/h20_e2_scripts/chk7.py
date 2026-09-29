# -*- coding: utf-8 -*-
"""H20 v7c 进度检查器（运行于 H20，`python3 /root/chk7.py`）。

设计要点（沿用今天定下的规矩）：
  · 判活**只读 /proc/<pid>/cmdline**，绝不用 `ps|grep` / `pgrep -f`（会自匹配自己）；
  · 本脚本自身命令行不含任何被搜索字符串（以文件名调用），从结构上排除自匹配；
  · CSV 不做 `wc -l`（`raw` 字段含内嵌换行），只数**文件个数**。
"""
import os
import sys
import time

sys.stdout.reconfigure(encoding='utf-8')

TGTS = ['19e_probe_multi.py', 'vllm serve', 'h20_exp_v7c.sh', 'newh20_push.py',
        'h20_dl_model.py', 'h20_verify_model.py']
LOGS = ['/root/logs/exp_v7c.log', '/root/logs/exp_v6.log', '/root/logs/push_final.log',
        '/root/logs/push.log']
ZD = '/root/e1_results'
NZD = '/root/e1_results_nonzero'

print('当前时间: %s' % time.strftime('%m-%d %H:%M:%S'))
print()
print('=== 相关进程（读 /proc，无自匹配）===')
found = []
for p in sorted(os.listdir('/proc')):
    if not p.isdigit():
        continue
    try:
        with open('/proc/%s/cmdline' % p, 'rb') as f:
            cl = f.read().replace(b'\x00', b' ').decode('utf-8', 'replace').strip()
    except Exception:
        continue
    if any(t in cl for t in TGTS):
        try:
            start = time.strftime('%H:%M:%S', time.localtime(os.stat('/proc/%s' % p).st_ctime))
        except Exception:
            start = '?'
        found.append((p, start, cl[:120]))
for p, start, cl in found:
    print('  pid=%-6s 起于 %s  %s' % (p, start, cl))
print('  合计 %d 个' % len(found))

print()
print('=== 日志尾部 ===')
for lg in LOGS:
    if not os.path.exists(lg):
        print('-- %s（不存在）--' % lg)
        continue
    age = time.time() - os.path.getmtime(lg)
    print('-- %s（%.0f 秒前更新，%d B）--' % (lg, age, os.path.getsize(lg)))
    with open(lg, encoding='utf-8', errors='replace') as f:
        for ln in f.read().splitlines()[-14:]:
            print('    ' + ln[:160])

print()
print('=== 最近一次 probe 日志（各臂尾部 rc/汇总）===')
ld = '/root/logs'
if os.path.isdir(ld):
    pl = [os.path.join(ld, x) for x in os.listdir(ld) if x.startswith('probe_v7c')]
    pl.sort(key=lambda p: os.path.getmtime(p), reverse=True)
    for p in pl[:4]:
        print('-- %s（%.0f 秒前）--' % (os.path.basename(p), time.time() - os.path.getmtime(p)))
        with open(p, encoding='utf-8', errors='replace') as f:
            for ln in f.read().splitlines()[-6:]:
                print('    ' + ln[:160])

print()
print('=== 结果文件计数（只数文件，不用 wc -l）===')
for d in (ZD, NZD):
    n = len(os.listdir(d)) if os.path.isdir(d) else 0
    print('  %s: %d 个文件' % (d, n))
print('=== GPU ===')
os.system('nvidia-smi --query-gpu=memory.used,memory.total,utilization.gpu --format=csv,noheader')
print('=== 磁盘 ===')
os.system('df -h / | tail -1')
print('=== 完成标记 ===')
for mk in ('EXP_V6_DONE', 'EXP_V7C_DONE', 'ALL_EXPERIMENTS_DONE'):
    hit = False
    for lg in ('/root/logs/exp_v7c.log', '/root/logs/exp_v6.log'):
        if os.path.exists(lg):
            with open(lg, encoding='utf-8', errors='replace') as f:
                if mk in f.read():
                    hit = True
    print('  %s: %s' % (mk, '已出现' if hit else '未出现'))
