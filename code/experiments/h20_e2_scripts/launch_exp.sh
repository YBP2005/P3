#!/bin/bash
# 启动实验（先确保日志目录存在 —— 上一版就死在重定向上）
mkdir -p /root/logs /root/e1_results /root/e1_results_nonzero
if [ -f /root/exp.pid ] && kill -0 "$(cat /root/exp.pid)" 2>/dev/null; then
  echo "exp.sh 已在运行 pid=$(cat /root/exp.pid)"; exit 0
fi
cd /root
setsid nohup bash /root/exp.sh < /dev/null > /root/logs/exp.log 2>&1 &
echo $! > /root/exp.pid
echo "EXP_LAUNCHED pid=$!"
