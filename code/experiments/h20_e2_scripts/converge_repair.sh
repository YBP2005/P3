#!/bin/bash
# 收敛补齐实例：全部杀掉 → 用 pidfile 启动器只起一个 → 用 /proc 核实恰好一个
echo "=== 杀全部 repair72b ==="
pkill -9 -f 'repair72b\.sh' 2>/dev/null && echo "  已发 SIGKILL" || echo "  （无）"
rm -f /root/repair72b.pid
sleep 5
echo "=== 核实已清空 ==="
/usr/local/miniconda3/bin/python3 - <<'PY'
import os
n = 0
for p in sorted(os.listdir('/proc')):
    if not p.isdigit():
        continue
    try:
        cl = open('/proc/%s/cmdline' % p, 'rb').read().replace(b'\x00', b' ').decode('utf-8', 'replace')
    except Exception:
        continue
    if 'repair72b' in cl:
        print('  残留 %s %s' % (p, cl.strip()[:90]))
        n += 1
print('  残留合计 %d' % n)
PY
echo "=== 只启动一个 ==="
bash /root/launch_repair72b.sh
sleep 10
echo "=== 核实数量 ==="
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
    if cl.endswith('bash /root/repair72b.sh'):
        print('  运行中 pid=%s' % p)
        n += 1
print('  repair72b 实例数 = %d（应为 1）' % n)
PY
echo "=== pidfile ==="; cat /root/repair72b.pid 2>/dev/null; echo
echo CONVERGE_DONE
