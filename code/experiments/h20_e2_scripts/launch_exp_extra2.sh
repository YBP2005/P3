#!/bin/bash
# 用 v2 替换空等的 v1 扩展实验脚本（v1 尚未做任何事，停掉零损失）
mkdir -p /root/logs
if pgrep -f 'h20_exp_extra\.sh' > /dev/null 2>&1; then
  pkill -9 -f 'h20_exp_extra\.sh'
  echo "已停掉 v1（只在空等标记，无损失）"
fi
sleep 3
if pgrep -f 'h20_exp_extra2\.sh' > /dev/null 2>&1; then
  echo "v2 已在运行"
  exit 0
fi
cd /root
setsid nohup bash /root/h20_exp_extra2.sh < /dev/null > /root/logs/exp_extra2_stdout.log 2>&1 &
echo "EXP_EXTRA2_LAUNCHED pid=$!"
