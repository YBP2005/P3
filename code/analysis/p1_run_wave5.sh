#!/bin/bash
# p1_run_wave5.sh —— 只跑 Qwen3-VL-32B（判据 H4 的锚格需要它）。
#
# 上一波失败的根因（写在这里以免重复）：32B 启服时报
#   "Free memory on device cuda:0 (43.37/79.44 GiB) on startup is less than desired
#    GPU memory utilization (0.85, 67.52 GiB)"
# —— 前一个实例的 `kill -9 $APIServer` 只杀了 API 进程，**EngineCore 子进程还占着 ~35 GB**，
#    而我只 sleep 4 s 就起了下一个。⇒ 本脚本用 gpu_clear()：pkill 全部 vllm 子进程 + **轮询到显存真正回落**才继续。
#
# 用法：bash p1_run_wave5.sh [每臂线程 默认6]
set -u
PY=/usr/local/miniconda3/bin/python
VLLM=/usr/local/miniconda3/bin/vllm
export VLLM_USE_FLASHINFER_SAMPLER=0
GRID=/root/p1_grid; OUTD=/root/p1_results; L=/root/logs/p1_run_wave5.log
W="${1:-6}"
say() { echo "[$(date +%H:%M:%S)] $*" | tee -a "$L"; }

gpu_clear() {
  pkill -9 -i -f vllm 2>/dev/null; pkill -9 -f resource_tracker 2>/dev/null
  for i in $(seq 1 60); do
    used=$(nvidia-smi --query-gpu=memory.used --format=csv,noheader | tr -d ' MiB')
    [ "$used" -lt 1000 ] && { say "  显存已清空：${used} MiB"; return 0; }
    sleep 3
  done
  say "  !! 显存未清空：${used} MiB"; return 1
}

N=Qwen3-VL-32B-Instruct; MP=/model/ModelScope/Qwen/Qwen3-VL-32B-Instruct
say "== wave5 开始（$N，0.85 / maxlen 4096）=="
gpu_clear || exit 3
nohup $VLLM serve "$MP" --served-model-name "$N" --max-model-len 4096 \
  --limit-mm-per-prompt '{"image": 1}' --gpu-memory-utilization 0.85 \
  --max-num-seqs 24 --port 8006 </dev/null > "/root/logs/serve_p1_${N}.log" 2>&1 &
SP=$!
ok=0
for i in $(seq 1 90); do
  sleep 10
  curl -sf -m 4 -o /dev/null "http://127.0.0.1:8006/v1/models" && { ok=1; break; }
  grep -qE "Engine core initialization failed|No available memory|less than desired|ValueError" "/root/logs/serve_p1_${N}.log" 2>/dev/null && {
    say "[$N] !! 起服失败："; grep -E "ValueError|RuntimeError" "/root/logs/serve_p1_${N}.log" | tail -1 | cut -c1-220 | sed 's/^/    /'; break; }
  kill -0 "$SP" 2>/dev/null || { say "[$N] !! 进程退出"; break; }
done
if [ "$ok" != "1" ]; then kill -9 "$SP" 2>/dev/null; gpu_clear; say "P1_wave5_FAILED"; exit 4; fi
say "[$N] 就绪（$((i*10)) s）｜显存 $(nvidia-smi --query-gpu=memory.used --format=csv,noheader)"

CP=""
for arm in base permit; do
  nohup $PY /root/p1_probe.py --grid "$GRID" --family "$N" --arm "$arm" \
    --model "$N" --api "http://127.0.0.1:8006/v1/chat/completions" \
    --outd "$OUTD" --workers "$W" --object circles \
    </dev/null >> "/root/logs/p1_probe_${N}_${arm}.log" 2>&1 &
  CP="$CP $!"
done
T0=$(date +%s)
while :; do
  sleep 30
  alive=0; for p in $CP; do kill -0 "$p" 2>/dev/null && alive=$((alive+1)); done
  now=$(( $(date +%s) - T0 ))
  say "  ${now}s 存活 $alive ｜ 显存 $(nvidia-smi --query-gpu=memory.used --format=csv,noheader)"
  [ "$alive" -eq 0 ] && break
  [ "$now" -ge 1800 ] && { say "  到时限，停止"; for p in $CP; do kill -9 "$p" 2>/dev/null; done; break; }
done
tail -n 2 "/root/logs/p1_probe_${N}_base.log"
tail -n 2 "/root/logs/p1_probe_${N}_permit.log"
gpu_clear
say "== wave5 结束 ｜ 显存 $(nvidia-smi --query-gpu=memory.used --format=csv,noheader) =="
say "P1_wave5_DONE"
