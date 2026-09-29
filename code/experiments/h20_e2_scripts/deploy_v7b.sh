#!/bin/bash
# 用 v7b 替换空等的 v7（v7 尚未做任何事，停掉零损失）
mkdir -p /root/logs
if pgrep -f 'h20_exp_v7\.sh' > /dev/null 2>&1; then
  pkill -9 -f 'h20_exp_v7\.sh' && echo "已停 v7（空等，零损失）"
fi
rm -f /root/exp_v7.pid
sleep 3
PIDF=/root/exp_v7b.pid
if [ -f "$PIDF" ] && kill -0 "$(cat "$PIDF")" 2>/dev/null; then
  echo "v7b 已在运行 pid=$(cat "$PIDF")"; exit 0
fi
cd /root
setsid nohup bash /root/h20_exp_v7b.sh < /dev/null > /root/logs/exp_v7b_stdout.log 2>&1 &
echo $! > "$PIDF"
echo "EXP_V7B_LAUNCHED pid=$!"
sleep 8
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
    if cl.endswith('bash /root/h20_exp_v7b.sh') or cl.endswith('bash /root/h20_exp_v7.sh') or cl.endswith('bash /root/h20_exp_v6.sh'):
        print('  运行中 pid=%s %s' % (p, cl)); n += 1
print('  实例数 = %d（v6 一个 + v7b 一个 = 2）' % n)
PY
