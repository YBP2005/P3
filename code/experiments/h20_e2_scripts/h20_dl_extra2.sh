#!/bin/bash
# 提前启动 GPTQ-W4 与 AWQ-8bit 的下载：等 FP8 下完后自动接上（避免抢带宽）
PY=/usr/local/miniconda3/bin/python3
L=/root/logs/dl_extra2.log
say() { echo "[$(date +%H:%M:%S)] $*" | tee -a "$L"; }

say "等 FP8 下载结束"
while pgrep -f 'h20_dl_fp8' > /dev/null 2>&1; do sleep 30; done
say "FP8 下载结束，空间：$(df -h / | tail -1)"

say "开始下载 GPTQ-W4 与 AWQ-8bit（到系统盘，已扩容）"
$PY -u /root/h20_dl_model.py \
  LosCV29/Qwen3-VL-32B-Instruct-GPTQ-W4   /root/models/Qwen3-VL-32B-Instruct-GPTQ-W4 \
  cyankiwi/Qwen3-VL-32B-Instruct-AWQ-8bit /root/models/Qwen3-VL-32B-Instruct-AWQ-8bit \
  >> "$L" 2>&1
say "下载结束"
du -sh /root/models/* 2>/dev/null | tee -a "$L"
df -h / | tail -1 | tee -a "$L"
echo DL_EXTRA2_DONE >> "$L"
