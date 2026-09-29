#!/bin/bash
# g8_all.sh — G8（UCF-QNRF 英文臂补完）：按**预注册的 max-model-len 阶梯**起服，取第一个 0 个 HTTP 400 的档。
# ⚠⚠ A800 已交会议侧：本脚本第一步就 pkill vllm 并独占显卡 ⇒ 默认**拒绝执行**。
#     确有权接管时才：ALLOW_GPU_TAKEOVER=1 bash /root/g8_all.sh
if [ "${ALLOW_GPU_TAKEOVER:-0}" != "1" ]; then
  echo "[g8] 拒绝执行：A800 已交会议侧。若确有权接管，请用 ALLOW_GPU_TAKEOVER=1 重跑。"
  echo "[g8] 当前占用：$(nvidia-smi --query-gpu=memory.used,utilization.gpu --format=csv,noheader | head -1)"
  exit 3
fi
OCC=$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits | head -1 | tr -d ' ')
if [ "$OCC" -ge 1000 ]; then echo "[g8] 拒绝执行：显存已占 ${OCC} MiB。"; exit 4; fi

# ★ PATH：vLLM 在 CUDA-graph/编译那一步会 `Popen('ninja')`，而 setsid+nohup 起的进程
#   PATH 里没有 conda 的 bin ⇒ 实测 `FileNotFoundError: 'ninja'`（ninja 其实装在
#   /usr/local/miniconda3/bin/ninja）。这里显式补上。
# ★ 基础设施两则（2026-09-27 实测；都**不是我们的选择**，结果里已声明）：
#   ① PATH：ninja 在 conda bin，而 setsid+nohup 起的进程 PATH 里没有它 ⇒ FileNotFoundError: 'ninja'；
#   ② 本镜像**只有 gcc 没有 g++**（`cc1plus` 不存在），而 FlashInfer 采样算子缓存只剩 build.ninja
#      ⇒ 每次起服都尝试重编、每次必失败（`gcc: fatal error: cannot execute 'cc1plus'`）。
#      关掉 FlashInfer 采样器即绕开编译，改用原生 PyTorch 采样器（temperature 0 下取值不变）。
export PATH=/usr/local/miniconda3/bin:$PATH
export VLLM_USE_FLASHINFER_SAMPLER=0

PY=/usr/local/miniconda3/bin/python
VLLM=/usr/local/miniconda3/bin/vllm
MODEL=/model/ModelScope/Qwen/Qwen3-VL-32B-Instruct
PORT=8011
LOG=/root/g8.log
R=/root/g8_res
mkdir -p "$R"
say() { echo "[$(date +%H:%M:%S)] $*" | tee -a "$LOG"; }

gpu_clear() {
  pkill -9 -i -f vllm 2>/dev/null
  pkill -9 -f 'VLLM::EngineCore' 2>/dev/null
  pkill -9 -f resource_tracker 2>/dev/null
  sleep 5
  for i in $(seq 1 60); do
    u=$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits | tr -d ' ')
    n=$(nvidia-smi --query-compute-apps=pid --format=csv,noheader | wc -l)
    [ -n "$u" ] && [ "$u" -lt 500 ] && [ "$n" -eq 0 ] && return 0
    pkill -9 -f 'VLLM::EngineCore' 2>/dev/null
    sleep 5
  done
  say "  !! 显存未清空：${u} MiB"; return 1
}

serve() {  # $1 = max-model-len
  gpu_clear || return 1
  setsid nohup $VLLM serve "$MODEL" --served-model-name Qwen3-VL-32B-Instruct \
    --max-model-len "$1" --gpu-memory-utilization 0.93 \
    --limit-mm-per-prompt '{"image": 1}' \
    --mm-processor-kwargs '{"max_pixels": 1048576, "min_pixels": 3136}' \
    --port $PORT </dev/null > "/root/g8_serve_$1.log" 2>&1 &
  for i in $(seq 1 120); do
    sleep 10
    curl -sf -m 5 -o /dev/null "http://127.0.0.1:$PORT/v1/models" && { say "  起服就绪 maxlen=$1（$((i*10))s）"; return 0; }
    grep -qiE "Engine core initialization failed|is not supported|No module named|Value error," \
      "/root/g8_serve_$1.log" 2>/dev/null && { say "  !! maxlen=$1 起服报错"; tail -4 "/root/g8_serve_$1.log" >> "$LOG"; return 1; }
  done
  say "  !! maxlen=$1 起服超时"; return 1
}

say "########## G8 开始（预注册阶梯删去 65536：见下）##########"
# ★ 预注册阶梯原为 16384 → 32768 → 65536。**实测 65536 在本卡不可行**，且原因**与所要测的量无关**：
#   vLLM 报 "KV cache 需 16.0 GiB 而可用 8.11 GiB，按其估算最大模型长度 = 33216"。
#   这是显存约束、不是 HTTP 400 的结果 ⇒ 按 [16384, 32768] 跑，并把这一条作为**声明的偏差**记入结果件。
for ML in 16384 32768; do
  if serve "$ML"; then
    PORT=$PORT ARMS=en:base,en:channel,cn:base $PY -u /root/g8_run.py
    n400=$(awk -F, 'NR>1 && $7=="1"' "$R/g8.csv" 2>/dev/null | wc -l)
    say "  maxlen=$ML 跑完：HTTP 400 = $n400"
    if [ "$n400" -eq 0 ]; then say "  ⇒ 该档 0 个 400，按预注册规则**停止**（不再试更高档）"; break; fi
    say "  ⇒ 仍有 400，按阶梯继续下一档"
  else
    say "  !! maxlen=$ML 起服失败，继续下一档"
  fi
done
say "########## G8 结束 ##########"
ls -l "$R" >> "$LOG"
gpu_clear
echo G8_ALL_DONE >> "$LOG"
