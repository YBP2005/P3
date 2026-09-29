# -*- coding: utf-8 -*-
"""远端进程/文件检查器（运行于 H20）。
设计要点：本脚本以 `python3 /root/chk.py` 方式调用，其自身命令行**不含**任何被搜索的
字符串，故从结构上排除了 ps|grep / pgrep -f 的自匹配问题 —— 这是今天反复踩坑的根因。
"""
import os
import sys
import time

sys.stdout.reconfigure(encoding='utf-8')

TGTS = ['newh20_push.py', 'newh20_fetch_packs.py', 'newh20_chain.sh',
        'newh20_stage3.sh', 'exp.sh', 'vllm serve', '19b_e1_probe', '19c_probe', '19d_probe',
        'queue.py', 'run_all.sh']

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
            st = os.stat('/proc/%s' % p)
            start = time.strftime('%H:%M:%S', time.localtime(st.st_ctime))
        except Exception:
            start = '?'
        found.append((p, start, cl[:110]))
if found:
    for p, start, cl in found:
        print('  pid=%-6s 起于 %s  %s' % (p, start, cl))
else:
    print('  （无）')
print('  合计 %d 个' % len(found))

print()
print('=== 关键日志的更新时间与尾部 ===')
for lg, n in (('/root/push.log', 4), ('/root/fetch.log', 3), ('/root/fetch2.log', 6),
              ('/root/chain.log', 6), ('/root/stage3.log', 6), ('/root/logs/exp.log', 8)):
    if os.path.exists(lg):
        age = time.time() - os.path.getmtime(lg)
        print('-- %s（%.0f 秒前更新，%d 字节）--' % (lg, age, os.path.getsize(lg)))
        try:
            with open(lg, encoding='utf-8', errors='replace') as f:
                for ln in f.read().splitlines()[-n:]:
                    print('    ' + ln[:150])
        except Exception as ex:
            print('    读取失败: %s' % ex)
    else:
        print('-- %s（不存在）--' % lg)

print()
print('=== GPU ===')
os.system('nvidia-smi --query-gpu=memory.used,utilization.gpu --format=csv,noheader')
print('=== 磁盘 ===')
os.system('df -h / | tail -1')
print('=== 结果文件数 ===')
for d in ('/root/e1_results', '/root/e1_results_nonzero'):
    n = len([x for x in os.listdir(d)]) if os.path.isdir(d) else 0
    print('  %s: %d' % (d, n))
    if n:
        for x in sorted(os.listdir(d))[:60]:
            print('      %s (%d B)' % (x, os.path.getsize(os.path.join(d, x))))
