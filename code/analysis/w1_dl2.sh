#!/bin/bash
# w1_dl2.sh — 血统回收所需的补充下载（OpenBMB 槽位：MiniCPM-V-4_5，17.4 GB）
# 与主下载（w1_dl.sh）并行只占网络，不占 GPU；日志单独一份，供 w1_recover.sh 判就绪。
set -u
PY=/usr/local/miniconda3/bin/python
L=/root/logs/w1_dl2.log
mkdir -p /root/logs /root/w1_models
echo "[$(date +%H:%M:%S)] 开始下载 MiniCPM-V-4_5" >> "$L"
$PY /root/w1_dl_model.py OpenBMB/MiniCPM-V-4_5 /root/w1_models/minicpm-v-4_5 >> "$L" 2>&1
echo "[$(date +%H:%M:%S)] 结束 rc=$? ; $(du -sh /root/w1_models/minicpm-v-4_5 2>/dev/null | cut -f1)" >> "$L"
df -h / | tail -1 >> "$L"
