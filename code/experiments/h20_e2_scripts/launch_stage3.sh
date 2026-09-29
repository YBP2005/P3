#!/bin/bash
# 启动第三阶段
if ps -eo cmd | grep -q '[n]ewh20_stage3'; then echo "第三阶段已在运行"; exit 0; fi
cd /root
setsid nohup bash /root/newh20_stage3.sh < /dev/null > /root/stage3_stdout.log 2>&1 &
echo "STAGE3_LAUNCHED pid=$!"
