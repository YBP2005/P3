#!/bin/bash
# 启动接续器
if ps -eo cmd | grep -q '[n]ewh20_chain'; then echo "接续器已在运行"; exit 0; fi
cd /root
setsid nohup bash /root/newh20_chain.sh < /dev/null > /root/chain_stdout.log 2>&1 &
echo "CHAIN_LAUNCHED pid=$!"
