#!/bin/bash
# 重开 H20 后的启动：① 恢复 H20→M机 备份推送器；② 启动 v7c（等 v6 结束的闸门已满足，会立即开始）
set -u
mkdir -p /root/logs
PY=/usr/local/miniconda3/bin/python3

echo "=== ① 恢复备份推送器 ==="
PIDF=/root/push.pid
if [ -f "$PIDF" ] && kill -0 "$(cat "$PIDF")" 2>/dev/null; then
  echo "  推送器已在运行 pid=$(cat "$PIDF")"
else
  cd /root
  setsid nohup $PY -u /root/newh20_push.py < /dev/null > /root/push.log 2>&1 &
  echo $! > "$PIDF"
  echo "  推送器已启动 pid=$!"
fi

echo "=== ② 启动 v7c ==="
PIDF2=/root/exp_v7c.pid
if [ -f "$PIDF2" ] && kill -0 "$(cat "$PIDF2")" 2>/dev/null; then
  echo "  v7c 已在运行 pid=$(cat "$PIDF2")"
else
  rm -f /root/logs/exp_v7c.log
  cd /root
  setsid nohup bash /root/h20_exp_v7c.sh < /dev/null > /root/logs/exp_v7c_stdout.log 2>&1 &
  echo $! > "$PIDF2"
  echo "  v7c 已启动 pid=$!"
fi

sleep 20
echo "=== ③ 核实 ==="
/usr/local/miniconda3/bin/python3 - <<'PY'
import os, time
for p in sorted(os.listdir('/proc')):
    if not p.isdigit():
        continue
    try:
        cl = open('/proc/%s/cmdline' % p, 'rb').read().replace(b'\x00', b' ').decode('utf-8', 'replace').strip()
    except Exception:
        continue
    if any(t in cl for t in ('h20_exp_v7c', 'newh20_push', 'vllm serve', '19e_probe')):
        t0 = time.strftime('%H:%M:%S', time.localtime(os.stat('/proc/%s' % p).st_ctime))
        print('  %s pid=%-7s %s' % (t0, p, cl[:95]))
PY
echo "--- 推送器日志 ---"; tail -2 /root/push.log 2>/dev/null
echo "--- v7c 日志 ---"; tail -4 /root/logs/exp_v7c.log 2>/dev/null
echo "--- 结果计数 ---"
echo -n "  零池: "; ls /root/e1_results/ 2>/dev/null | wc -l
echo -n "  非零池: "; ls /root/e1_results_nonzero/ 2>/dev/null | wc -l
echo START_AFTER_REOPEN_DONE
