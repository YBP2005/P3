#!/bin/bash
# 扩满用：下载新模型（与 GPU 实验并行，不占用 GPU）。
# 顺序执行以免互相抢带宽；下载器含校验重试轮。
PY=/usr/local/miniconda3/bin/python3
L=/root/logs/dl_v5.log
say() { echo "[$(date +%H:%M:%S)] $*" | tee -a "$L"; }

say "开始下载新模型（4B / 2B / 30B-A3B-FP8 / InternVL3.5-38B-FP8）"
$PY -u /root/h20_dl_model.py \
  Qwen/Qwen3-VL-4B-Instruct            /root/models/Qwen3-VL-4B-Instruct \
  Qwen/Qwen3-VL-2B-Instruct            /root/models/Qwen3-VL-2B-Instruct \
  Qwen/Qwen3-VL-30B-A3B-Instruct-FP8   /root/models/Qwen3-VL-30B-A3B-Instruct-FP8 \
  brandonbeiler/InternVL3_5-38B-FP8-Dynamic /root/models/InternVL3_5-38B-FP8-Dynamic \
  >> "$L" 2>&1
say "下载结束"
du -sh /root/models/* 2>/dev/null | tee -a "$L"
df -h / | tail -1 | tee -a "$L"
echo DL_V5_DONE >> "$L"
