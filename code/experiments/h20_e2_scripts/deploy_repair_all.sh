#!/bin/bash
# 部署并启动统一补齐：先停掉旧的 repair72b（避免两个补齐脚本并发写同一批文件）
PIDF=/root/repair_all.pid
echo "=== 停旧补齐 ==="
pkill -9 -f 'repair72b\.sh' 2>/dev/null && echo "  已停 repair72b" || echo "  （无 repair72b）"
rm -f /root/repair72b.pid
sleep 4

if [ -f "$PIDF" ] && kill -0 "$(cat "$PIDF")" 2>/dev/null; then
  echo "补齐已在运行 pid=$(cat "$PIDF")"; exit 0
fi
mkdir -p /root/logs
cd /root
setsid nohup bash /root/repair_all.sh < /dev/null > /root/logs/repair_all_stdout.log 2>&1 &
echo $! > "$PIDF"
echo "REPAIR_ALL_LAUNCHED pid=$!"
sleep 8
echo "=== 核实 ==="
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
    if cl.endswith('bash /root/repair_all.sh') or cl.endswith('bash /root/repair72b.sh'):
        print('  运行中 pid=%s  %s' % (p, cl))
        n += 1
print('  补齐实例数 = %d（应为 1）' % n)
PY
echo DEPLOY_REPAIR_ALL_DONE
