#!/bin/bash
# 启动 GPTQ/AWQ-8bit 下载（后台，会先等 FP8 下完）
if pgrep -f 'h20_dl_extra2' > /dev/null 2>&1; then echo "已在运行"; exit 0; fi
mkdir -p /root/logs
cd /root
setsid nohup bash /root/h20_dl_extra2.sh < /dev/null > /root/logs/dl_extra2_stdout.log 2>&1 &
echo "DL_EXTRA2_LAUNCHED pid=$!"
