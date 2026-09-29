#!/bin/bash
# after_ea2_run.sh —— 等 E2 跑完再跑 E1（两者都要独占 GPU 与 8000 端口，不能并行）。
#
# ★ 为什么改成"无限等 + 超时**不**启动"：上一版等待上限 90 分钟，超时后**仍然**启动 E1；
#   而 E1 的 gpu_clear 会 `pkill -9 -f vllm` —— 那会**打断还在跑的 E2**（服务被杀、当次服务作废）。
#   E2 剩 3 个构建（llavaov/gemma12b/q32），90 分钟根本不够 ⇒ 旧逻辑是"必然互相踩"的定时炸弹。
#   现在：最多等 6 小时；超时只记日志并退出，绝不启动 E1（宁可不跑，不可踩坏）。
set -u
L=/root/logs/after_ea2.log
mkdir -p /root/logs
say() { echo "[$(date +%H:%M:%S)] $*" | tee -a "$L"; }
say "等待 E2 完成（标记 E2_PANEL_DONE）；上限 6 小时，超时**不**启动 E1"
for i in $(seq 1 1440); do
  if grep -q "E2_PANEL_DONE" /root/logs/ea2_run.log 2>/dev/null; then
    say "E2 已完成（第 $((i*15))s 检测到）⇒ 启动 E1（384/256/768up × 6 臂）"
    bash /root/fscres_run.sh >> "$L" 2>&1
    say "E1 结束（退出码 $?）"
    exit 0
  fi
  sleep 15
done
say "!! 等待 E2 超时（6 小时）⇒ **不**启动 E1（避免杀掉 E2 的服务）。请人工确认 E2 状态后手动运行 fscres_run.sh。"
exit 1
