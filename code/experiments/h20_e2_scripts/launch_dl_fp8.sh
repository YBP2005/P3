#!/bin/bash
# 启动 FP8 权重下载（后台）
if pgrep -f 'h20_dl_fp8' > /dev/null 2>&1; then echo "下载已在运行"; exit 0; fi
mkdir -p /root/logs
cd /root
setsid nohup /usr/local/miniconda3/bin/python3 -u /root/h20_dl_fp8.py \
  < /dev/null > /root/logs/dl_fp8.log 2>&1 &
echo "FP8_DL_LAUNCHED pid=$!"
