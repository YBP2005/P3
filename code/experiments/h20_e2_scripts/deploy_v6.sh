#!/bin/bash
# 部署并启动 v6（pidfile 守卫，避免重复实例）
PIDF=/root/exp_v6.pid
if [ -f "$PIDF" ] && kill -0 "$(cat "$PIDF")" 2>/dev/null; then
  echo "v6 已在运行 pid=$(cat "$PIDF")"; exit 0
fi
mkdir -p /root/logs
cd /root
setsid nohup bash /root/h20_exp_v6.sh < /dev/null > /root/logs/exp_v6_stdout.log 2>&1 &
echo $! > "$PIDF"
echo "EXP_V6_LAUNCHED pid=$!"
sleep 10
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
    if cl.endswith('bash /root/h20_exp_v6.sh'):
        print('  运行中 pid=%s' % p); n += 1
print('  v6 实例数 = %d（应为 1）' % n)
PY
