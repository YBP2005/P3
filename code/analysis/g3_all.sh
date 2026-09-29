#!/bin/bash
# g3_all.sh — G3（第三方协议外验）：四个家族**串行**起服，每个家族跑 2 域 × 300 项 × 3 臂。
# ⚠⚠ A800 已交会议侧：本脚本第一步就 pkill vllm 并独占显卡 ⇒ 默认**拒绝执行**。
#     确有权接管时才：ALLOW_GPU_TAKEOVER=1 bash /root/g3_all.sh
if [ "${ALLOW_GPU_TAKEOVER:-0}" != "1" ]; then
  echo "[g3] 拒绝执行：A800 已交会议侧。若确有权接管，请用 ALLOW_GPU_TAKEOVER=1 重跑。"
  echo "[g3] 当前占用：$(nvidia-smi --query-gpu=memory.used,utilization.gpu --format=csv,noheader | head -1)"
  exit 3
fi
OCC=$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits | head -1 | tr -d ' ')
if [ "$OCC" -ge 1000 ]; then echo "[g3] 拒绝执行：显存已占 ${OCC} MiB。"; exit 4; fi

# ★ 基础设施两则（2026-09-27 实测；都**不是我们的选择**，结果里已声明）：
#   ① PATH：ninja 在 conda bin，而 setsid+nohup 起的进程 PATH 里没有它 ⇒ FileNotFoundError: 'ninja'；
#   ② 本镜像**只有 gcc 没有 g++**（`cc1plus` 不存在），FlashInfer 采样算子缓存只剩 build.ninja
#      ⇒ 每次起服都尝试重编、每次必失败。关掉 FlashInfer 采样器即绕开编译（temperature 0 下取值不变）。
export PATH=/usr/local/miniconda3/bin:$PATH
export VLLM_USE_FLASHINFER_SAMPLER=0

PY=/usr/local/miniconda3/bin/python
VLLM=/usr/local/miniconda3/bin/vllm
PORT=8012
LOG=/root/g3.log
R=/root/g3_res
mkdir -p "$R"
say() { echo "[$(date +%H:%M:%S)] $*" | tee -a "$LOG"; }

# 只跑指定家族（逗号分隔）；空 = 全部。用于"某个家族起服失败后单独补跑"。
ONLY="${G3_ONLY:-}"
want() { [ -z "$ONLY" ] && return 0; case ",$ONLY," in *",$1,"*) return 0 ;; esac; return 1; }

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

# $1 路径 ｜ $2 served-name ｜ $3 mm-processor-kwargs（可空）
# ★ 2026-09-27 修：InternVL 的 image processor **不接受** `max_pixels/min_pixels`（实测 TypeError），
#   故按家族分派：Qwen 系带像素上限（与本稿语料同一套），InternVL 不带（与本稿 §M.19 的起服一致）。
serve() {
  gpu_clear || return 1
  if [ -n "$3" ]; then
    setsid nohup $VLLM serve "$1" --served-model-name "$2" \
      --max-model-len 8192 --gpu-memory-utilization 0.93 \
      --limit-mm-per-prompt '{"image": 1}' --mm-processor-kwargs "$3" \
      --trust-remote-code --port $PORT </dev/null > "/root/g3_serve_$2.log" 2>&1 &
  else
    setsid nohup $VLLM serve "$1" --served-model-name "$2" \
      --max-model-len 8192 --gpu-memory-utilization 0.93 \
      --limit-mm-per-prompt '{"image": 1}' \
      --trust-remote-code --port $PORT </dev/null > "/root/g3_serve_$2.log" 2>&1 &
  fi
  for i in $(seq 1 90); do
    sleep 10
    curl -sf -m 5 -o /dev/null "http://127.0.0.1:$PORT/v1/models" && { say "  起服就绪 $2（$((i*10))s）"; return 0; }
    grep -qiE "Engine core initialization failed|is not supported|No module named|Value error,|TypeError|unexpected keyword" \
      "/root/g3_serve_$2.log" 2>/dev/null && \
      { say "  !! $2 起服报错"; tail -3 "/root/g3_serve_$2.log" | sed 's/^/      /' >> "$LOG"; return 1; }
  done
  say "  !! $2 起服超时"; return 1
}

run_one() {  # $1 路径 ｜ $2 served-name ｜ $3 mm-kwargs
  say "===== 家族 $2 ====="
  if serve "$1" "$2" "$3"; then
    PORT=$PORT FAMILY="$2" $PY -u /root/g3_run.py
    say "  $2 完成"
  else
    say "  !! $2 跳过（起服失败）"
  fi
}

MMQ='"max_pixels": 1048576, "min_pixels": 3136'
say "########## G3 开始（4 家族 × 2 域 × 300 项 × 3 臂 = 7,200 次调用）ONLY=${ONLY:-全部} ##########"
want Qwen2.5-VL-3B-Instruct && run_one /model/ModelScope/Qwen/Qwen2.5-VL-3B-Instruct Qwen2.5-VL-3B-Instruct "{$MMQ}"
want Qwen3-VL-4B-Instruct   && run_one /model/ModelScope/Qwen/Qwen3-VL-4B-Instruct   Qwen3-VL-4B-Instruct   "{$MMQ}"
want Qwen3-VL-32B-Instruct  && run_one /model/ModelScope/Qwen/Qwen3-VL-32B-Instruct  Qwen3-VL-32B-Instruct  "{$MMQ}"
want InternVL3_5-8B         && run_one /root/models/InternVL3_5-8B                   InternVL3_5-8B        ""
say "########## G3 结束 ##########"
ls -l "$R" >> "$LOG"
gpu_clear
echo G3_ALL_DONE >> "$LOG"
