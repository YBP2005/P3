#!/bin/bash
# dl_v5 的 pidfile 启动器（避免 pgrep 自匹配；也可安全重复调用）
PIDF=/root/dl_v5.pid
if [ -f "$PIDF" ] && kill -0 "$(cat "$PIDF")" 2>/dev/null; then
  echo "dl_v5 已在运行 pid=$(cat "$PIDF")"
  exit 0
fi
mkdir -p /root/logs
cd /root
setsid nohup bash /root/h20_dl_v5.sh < /dev/null > /root/logs/dl_v5_stdout.log 2>&1 &
echo $! > "$PIDF"
echo "DL_V5_LAUNCHED pid=$!"
