#!/bin/bash
# 启动「补齐精度阶梯」下载（后台）
if pgrep -f 'h20_dl_extra' > /dev/null 2>&1; then echo "已在运行"; exit 0; fi
mkdir -p /root/logs
cd /root
setsid nohup bash /root/h20_dl_extra.sh < /dev/null > /root/logs/dl_extra_stdout.log 2>&1 &
echo "DL_EXTRA_LAUNCHED pid=$!"
