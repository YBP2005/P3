#!/bin/bash
# 用 v7c 替换空等的 v7b（v7b 尚未做任何事，停掉零损失）
mkdir -p /root/logs
pkill -9 -f 'h20_exp_v7b\.sh' 2>/dev/null && echo "已停 v7b（空等，零损失）" || echo "（无 v7b）"
rm -f /root/exp_v7b.pid /root/exp_v7.pid
sleep 3
PIDF=/root/exp_v7c.pid
if [ -f "$PIDF" ] && kill -0 "$(cat "$PIDF")" 2>/dev/null; then
  echo "v7c 已在运行 pid=$(cat "$PIDF")"; exit 0
fi
cd /root
setsid nohup bash /root/h20_exp_v7c.sh < /dev/null > /root/logs/exp_v7c_stdout.log 2>&1 &
echo $! > "$PIDF"
echo "EXP_V7C_LAUNCHED pid=$!"
sleep 8
echo "=== 核实实例 ==="
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
    for tag in ('h20_exp_v6.sh', 'h20_exp_v7c.sh', 'h20_exp_v7b.sh'):
        if cl.endswith('bash /root/' + tag):
            print('  运行中 pid=%s %s' % (p, cl)); n += 1
print('  实例数 = %d（应为 2：v6 + v7c）' % n)
PY
echo "=== 推送器是否活着（数据安全网）==="
tail -2 /root/push.log 2>/dev/null
