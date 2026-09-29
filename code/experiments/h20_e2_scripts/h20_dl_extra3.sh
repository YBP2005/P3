#!/bin/bash
# 第三批下载：等第二批（GPTQ-W4 + AWQ-8bit）结束后，下 Qwen2.5-VL-72B-AWQ。
# 带**空间守卫**：剩余空间不足就等待（等扩容），不会把盘写满。
PY=/usr/local/miniconda3/bin/python3
L=/root/logs/dl_extra3.log
say() { echo "[$(date +%H:%M:%S)] $*" | tee -a "$L"; }
free_gb() { df -BG / | tail -1 | awk '{gsub("G","",$4); print $4}'; }

# 目标：Qwen2.5-VL-72B-AWQ ≈ 43 GB；留 25 GB 余量 ⇒ 需要 ≥ 70 GB
NEED=70
say "等第二批下载结束"
while pgrep -f 'h20_dl_extra2' > /dev/null 2>&1; do sleep 30; done
say "第二批结束，剩余空间 $(free_gb) GB"

while [ "$(free_gb)" -lt "$NEED" ]; do
  say "空间不足（$(free_gb) GB < ${NEED} GB），等待扩容…"
  sleep 120
done
say "空间足够（$(free_gb) GB），开始下载 Qwen2.5-VL-72B-AWQ"

$PY -u /root/h20_dl_model.py \
  Qwen/Qwen2.5-VL-72B-Instruct-AWQ /root/models/Qwen2.5-VL-72B-Instruct-AWQ \
  >> "$L" 2>&1
say "下载结束"
du -sh /root/models/Qwen2.5-VL-72B-Instruct-AWQ 2>/dev/null | tee -a "$L"
df -h / | tail -1 | tee -a "$L"
echo DL_EXTRA3_DONE >> "$L"
