#!/bin/bash
# p2_noise4.sh —— ① `--workers 4` 噪声底（v0563 盲审 5 家共同要求）。
#
# 与 p2_noise.sh 的差别（**每一处都要能说出理由**）：
#   · workers 1 → **4**：主探针就跑在 4 并发；原自测只在 1 并发下做，**不覆盖主探针条件**。
#   · 每源 10 → **全池（不限）**：池子就是冻结的 300 张（S-1 150 / S-2 150）。
#     ⇒ 项数从 20 提到 **300**，直接消掉"n=20 的 95% 单侧上界 ≈14%"这个指控。
#   · 重复 2 → **3**：两遍只能给一个"是否一致"，三遍才能给逐项一致率 + 跨遍离散度。
#   · 比对脚本换成新的 p2_noise3_cmp.py（**按源聚类**给区间；原脚本写死 2 遍）。
# 纪律照抄 p2_noise.sh：单卡串行、只杀自己的 SPID、有界孤儿回收、不调常驻 reaper。
set -u
PY=/usr/local/miniconda3/bin/python
export VLLM_USE_FLASHINFER_SAMPLER=0
L=/root/logs/p2_noise4.log
mkdir -p /root/logs
: > "$L"
say(){ echo "[$(date +%H:%M:%S)] $*" | tee -a "$L"; }

MID=Qwen3-VL-32B-Instruct
MPATH=/model/ModelScope/Qwen/Qwen3-VL-32B-Instruct
POOL=/root/p2/pool_all/pool_frozen_a800.csv
PORT=8006
REPS=3

BUSY_MEM=$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits -i 0 | tr -d ' ')
if [ "${BUSY_MEM:-0}" -gt 3000 ]; then say "!! 显存 ${BUSY_MEM} MiB ⇒ 先清卡"; exit 3; fi

say "=== 起服（与主探针同配置：--max-model-len 4096，不带 --gpu-memory-utilization）==="
CUDA_VISIBLE_DEVICES=0 nohup "$PY" -m vllm.entrypoints.openai.api_server \
  --model "$MPATH" --served-model-name "$MID" --port "$PORT" --max-model-len 4096 \
  > /root/logs/p2_noise4_serve.log 2>&1 &
SPID=$!
say "服务 PID=$SPID"
RDY=0
for i in $(seq 1 200); do
  if curl -s --max-time 3 "http://127.0.0.1:${PORT}/v1/models" | grep -q "$MID"; then RDY=1; break; fi
  if ! kill -0 "$SPID" 2>/dev/null; then say "!! 服务进程退出"; tail -30 /root/logs/p2_noise4_serve.log | tee -a "$L"; exit 4; fi
  sleep 5
done
[ "$RDY" = 1 ] && say "就绪（第 ${i} 次探测）" || { say "!! 未就绪"; exit 5; }

for R in $(seq 1 $REPS); do
  say "=== 重复 $R/$REPS：全池 300 张（S-1 150 + S-2 150）× base 臂 × workers=4 ==="
  rm -rf "/root/p2_noise4_rep$R"
  "$PY" -u /root/p2_probe.py --pool "$POOL" \
    --api "http://127.0.0.1:${PORT}/v1/chat/completions" --ak EMPTY \
    --models "$MID" --arms base --outd "/root/p2_noise4_rep$R" --workers 4 \
    2>&1 | tail -6 | tee -a "$L"
done

say "=== 停服 ==="
kill "$SPID" 2>/dev/null
for i in $(seq 1 20); do kill -0 "$SPID" 2>/dev/null || break; sleep 2; done
kill -9 "$SPID" 2>/dev/null
sleep 3
for pid in $(ps -eo pid,ppid,comm | awk '$2==1 && $3 ~ /^VLLM::EngineCor/ {print $1}'); do
  say "回收孤儿 EngineCore pid=$pid"; kill -9 "$pid" 2>/dev/null
done
sleep 3
say "显存 $(nvidia-smi --query-gpu=memory.used --format=csv,noheader -i 0)"

say "=== 比对（按源聚类）==="
"$PY" /root/p2_noise3_cmp.py 2>&1 | tee -a "$L"
say "=== DONE ==="
