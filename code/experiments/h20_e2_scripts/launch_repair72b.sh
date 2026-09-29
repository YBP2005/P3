#!/bin/bash
# 启动 72B 补齐（pidfile 守卫：不依赖 pgrep，故不可能自匹配）
PIDF=/root/repair72b.pid
if [ -f "$PIDF" ] && kill -0 "$(cat "$PIDF")" 2>/dev/null; then
  echo "补齐已在运行 pid=$(cat "$PIDF")"
  exit 0
fi
mkdir -p /root/logs
cd /root
setsid nohup bash /root/repair72b.sh < /dev/null > /root/logs/repair72b_stdout.log 2>&1 &
echo $! > "$PIDF"
echo "REPAIR_LAUNCHED pid=$!"
