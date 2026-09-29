#!/bin/bash
# 停旧补齐（v1 有 bug 且已完成）、只起一个 v2
pkill -9 -f 'repair_all\.sh' 2>/dev/null && echo "  已停 v1 补齐" || echo "  （无 v1）"
rm -f /root/repair_all.pid /root/repair_all2.pid
sleep 4
mkdir -p /root/logs
cd /root
setsid nohup bash /root/repair_all2.sh < /dev/null > /root/logs/repair_all2_stdout.log 2>&1 &
echo $! > /root/repair_all2.pid
echo "REPAIR_ALL2_LAUNCHED pid=$!"
sleep 12
/usr/local/miniconda3/bin/python3 - <<'PY'
import os
n = 0
for p in sorted(os.listdir('/proc')):
    if not p.isdigit():
        continue
    try:
        cl = open('/proc/%s/cmdline' % p, 'rb').read().replace(b'\x00', b' ').decode('utf-8', 'replace').strip()
    except Exception:
        continue
    if cl.endswith('bash /root/repair_all2.sh') or cl.endswith('bash /root/repair_all.sh'):
        print('  运行中 pid=%s %s' % (p, cl)); n += 1
print('  补齐实例数 = %d（应为 1）' % n)
PY
