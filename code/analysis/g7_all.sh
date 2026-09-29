#!/bin/bash
# g7_all.sh — G7 服务栈因子实验：五次起服 + 七个配置，全部串行，日志落 /root/g7.log
# ⚠⚠ 本脚本第一步就会 pkill vllm 并独占显卡。2026-09-27 起 **A800 已交会议侧** ⇒
#     除非确知卡是空的、且**有权**接管，否则不要跑。默认拒绝执行，需显式放行：
#       ALLOW_GPU_TAKEOVER=1 bash /root/g7_all.sh
if [ "${ALLOW_GPU_TAKEOVER:-0}" != "1" ]; then
  echo "[g7] 拒绝执行：A800 已交会议侧。若确有权接管，请用 ALLOW_GPU_TAKEOVER=1 重跑。"
  echo "[g7] 当前占用：$(nvidia-smi --query-gpu=memory.used,utilization.gpu --format=csv,noheader | head -1)"
  exit 3
fi
OCC=$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits | head -1 | tr -d ' ')
if [ "$OCC" -ge 1000 ]; then
  echo "[g7] 拒绝执行：显存已占 ${OCC} MiB（可能有人在用）。"
  exit 4
fi
# ★ 基础设施两则（2026-09-27 实测；都**不是我们的选择**，结果里已声明）：
#   ① PATH：ninja 在 conda bin，而 setsid+nohup 起的进程 PATH 里没有它 ⇒ FileNotFoundError: 'ninja'；
#   ② 本镜像只有 gcc 没有 g++（cc1plus 不存在），FlashInfer 采样算子缓存只剩 build.ninja
#      ⇒ 每次起服都重编、每次必失败。关掉 FlashInfer 采样器即绕开（temperature 0 下取值不变）。
export PATH=/usr/local/miniconda3/bin:$PATH
export VLLM_USE_FLASHINFER_SAMPLER=0
PY=/usr/local/miniconda3/bin/python
VLLM=/usr/local/miniconda3/bin/vllm
MODEL=/model/ModelScope/Qwen/Qwen3-VL-32B-Instruct
PORT=8010
LOG=/root/g7.log
R=/root/g7_res
mkdir -p "$R"

say() { echo "[$(date +%H:%M:%S)] $*" | tee -a "$LOG"; }

gpu_clear() {
  pkill -9 -i -f vllm 2>/dev/null; pkill -9 -f resource_tracker 2>/dev/null; sleep 5
  for i in $(seq 1 60); do
    u=$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits 2>/dev/null | tr -d ' ')
    [ -n "$u" ] && [ "$u" -lt 500 ] && return 0
    sleep 5
  done
  say "  !! 显存未清空：${u} MiB"; return 1
}

serve() {   # $1 = max-model-len, $2 = tag
  gpu_clear || return 1
  setsid nohup $VLLM serve "$MODEL" --served-model-name Qwen3-VL-32B-Instruct \
    --max-model-len "$1" --gpu-memory-utilization 0.93 \
    --limit-mm-per-prompt '{"image": 1}' \
    --mm-processor-kwargs '{"max_pixels": 1048576, "min_pixels": 3136}' \
    --port $PORT </dev/null > "/root/g7_serve_$2.log" 2>&1 &
  for i in $(seq 1 90); do
    sleep 10
    curl -sf -m 5 -o /dev/null "http://127.0.0.1:$PORT/v1/models" && { say "  起服就绪 $2（$((i*10))s, maxlen=$1）"; return 0; }
    grep -qiE "Engine core initialization failed|is not supported|No module named|Value error," \
      "/root/g7_serve_$2.log" 2>/dev/null && { say "  !! $2 起服报错"; tail -4 "/root/g7_serve_$2.log" | sed 's/^/      /' >> "$LOG"; return 1; }
  done
  say "  !! $2 起服超时"; return 1
}

run() { PORT=$PORT CONFIG="$1" WORKERS="$2" SYSTEM="$3" $PY -u /root/g7_run.py; }

say "########## G7 开始 ##########"
if serve 8192 R_s1; then
  run R_s1 8 0; run F3_sys 8 1; run F4_w1 1 0
else
  say "!! R_s1 起服失败，后续全部跳过"
fi
serve 8192 R_s2 && run R_s2 8 0
serve 8192 R_s3 && run R_s3 8 0
serve 4096 F2_4096 && run F2_4096 8 0
serve 16384 F2_16384 && run F2_16384 8 0
say "########## G7 结束 ##########"
ls -l "$R" | sed 's/^/  /' >> "$LOG"
gpu_clear
echo G7_ALL_DONE >> "$LOG"
