#!/bin/bash
# 自动接续：
#  ① 等当前那轮接收结束（避免两个实例抢同一批 incoming 文件）
#  ② 等 M机 打包完成（PACK_ALL_DONE）
#  ③ 再跑一次接收，补齐剩余包（此时 MD5SUMS 已存在，会逐包校验 md5）
#  ④ 生成 19c / 19d 探针（M机 上没有这两个，必须在本地生成）
set -u
PY=/usr/local/miniconda3/bin/python3
echo "[$(date +%H:%M:%S)] 接续器启动" >> /root/chain.log

while ps -eo cmd | grep -q '[n]ewh20_fetch_packs'; do sleep 30; done
echo "[$(date +%H:%M:%S)] 上一轮接收已结束" >> /root/chain.log

$PY -u /root/newh20_fetch_packs.py >> /root/fetch2.log 2>&1
echo "[$(date +%H:%M:%S)] 第二轮接收结束 rc=$?" >> /root/chain.log

$PY /root/h20_make_19c.py > /root/gen.log 2>&1
echo "[$(date +%H:%M:%S)] 19c 生成 rc=$?" >> /root/chain.log
$PY /root/h20_make_19d.py >> /root/gen.log 2>&1
echo "[$(date +%H:%M:%S)] 19d 生成 rc=$?" >> /root/chain.log

echo "[$(date +%H:%M:%S)] === 接续全部完成 ===" >> /root/chain.log
echo CHAIN_ALL_DONE >> /root/chain.log
