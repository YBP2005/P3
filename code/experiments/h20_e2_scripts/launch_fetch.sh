#!/bin/bash
# 启动接收脚本（启动器方式，避免 exec_command 通道挂住）
if ps -eo cmd | grep -q '[n]ewh20_fetch_packs'; then
  echo "接收脚本已在运行"
  exit 0
fi
rm -f /root/fetch.log
cd /root
setsid nohup /usr/local/miniconda3/bin/python3 -u /root/newh20_fetch_packs.py \
  < /dev/null > /root/fetch.log 2>&1 &
echo "FETCH_LAUNCHED pid=$!"
