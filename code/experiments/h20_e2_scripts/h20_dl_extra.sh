#!/bin/bash
# 下载精度阶梯缺的两格（GPTQ-W4 / AWQ-8bit）到 /model（13TB 空间），避免撑爆系统盘。
# 排在 FP8 下载之后顺序执行，避免抢带宽。
PY=/usr/local/miniconda3/bin/python3
L=/root/logs/dl_extra.log
say() { echo "[$(date +%H:%M:%S)] $*" | tee -a "$L"; }

say "等 FP8 下载结束（若还在跑）"
while pgrep -f 'h20_dl_fp8' > /dev/null 2>&1; do sleep 30; done
say "FP8 下载已结束"

mkdir -p /model/quants
say "开始下载 GPTQ-W4 与 AWQ-8bit"
$PY -u /root/h20_dl_model.py \
  LosCV29/Qwen3-VL-32B-Instruct-GPTQ-W4   /model/quants/Qwen3-VL-32B-Instruct-GPTQ-W4 \
  cyankiwi/Qwen3-VL-32B-Instruct-AWQ-8bit /model/quants/Qwen3-VL-32B-Instruct-AWQ-8bit \
  >> "$L" 2>&1
say "下载结束"
ls -d /model/quants/* 2>/dev/null | sed 's/^/  /' | tee -a "$L"
du -sh /model/quants/* 2>/dev/null | tee -a "$L"
echo DL_EXTRA_DONE >> "$L"
