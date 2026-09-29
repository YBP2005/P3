#!/bin/bash
# 启动 v4（剩余全部实验）。先停掉 v3 的空等监视进程（它在等一个永远不会出现的标记，
# 因为 v2 已被停；v4 已把 72B 包含进来）。
mkdir -p /root/logs
if pgrep -f 'h20_exp_extra3' > /dev/null 2>&1; then
  pkill -9 -f 'h20_exp_extra3' && echo "已停 v3（空等标记，零损失）"
fi
sleep 3
if pgrep -f 'h20_exp_v4' > /dev/null 2>&1; then echo "v4 已在运行"; exit 0; fi
cd /root
setsid nohup bash /root/h20_exp_v4.sh < /dev/null > /root/logs/exp_v4_stdout.log 2>&1 &
echo "EXP_V4_LAUNCHED pid=$!"
