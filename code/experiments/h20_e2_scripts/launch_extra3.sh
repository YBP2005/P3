#!/bin/bash
# 启动第三批：下载（带空间守卫）与 72B 实验（都在等前序完成）
mkdir -p /root/logs
if ! pgrep -f 'h20_dl_extra3' > /dev/null 2>&1; then
  cd /root
  setsid nohup bash /root/h20_dl_extra3.sh < /dev/null > /root/logs/dl_extra3_stdout.log 2>&1 &
  echo "DL_EXTRA3_LAUNCHED pid=$!"
else
  echo "下载3 已在运行"
fi
if ! pgrep -f 'h20_exp_extra3' > /dev/null 2>&1; then
  cd /root
  setsid nohup bash /root/h20_exp_extra3.sh < /dev/null > /root/logs/exp_extra3_stdout.log 2>&1 &
  echo "EXP_EXTRA3_LAUNCHED pid=$!"
else
  echo "实验3 已在运行"
fi
