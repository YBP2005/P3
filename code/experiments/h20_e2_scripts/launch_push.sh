#!/bin/bash
# 启动结果推送器（H20 → M机 中转）
if ps -eo cmd | grep -q '[n]ewh20_push'; then echo "推送器已在运行"; exit 0; fi
cd /root
setsid nohup /usr/local/miniconda3/bin/python3 -u /root/newh20_push.py \
  < /dev/null > /root/push.log 2>&1 &
echo "PUSH_LAUNCHED pid=$!"
