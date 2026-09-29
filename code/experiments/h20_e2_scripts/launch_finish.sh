#!/bin/bash
# 启动 finish.sh（启动器方式；脚本自身命令行干净）
if [ -f /root/finish.pid ] && kill -0 "$(cat /root/finish.pid)" 2>/dev/null; then
  echo "finish.sh 已在运行 pid=$(cat /root/finish.pid)"
  exit 0
fi
rm -f /root/finish.log
cd /root
setsid nohup bash /root/finish.sh < /dev/null > /root/finish_stdout.log 2>&1 &
echo $! > /root/finish.pid
echo "FINISH_LAUNCHED pid=$!"
