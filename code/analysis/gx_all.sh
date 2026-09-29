#!/bin/bash
# gx_all.sh — 收官批：G8b（另三格）→ placebo anchors → G10 同批效应 → G9b（新阈值重开的 L2）
# ⚠ A800 已交会议侧：默认**拒绝执行**；确有权接管才：ALLOW_GPU_TAKEOVER=1 bash /root/gx_all.sh
if [ "${ALLOW_GPU_TAKEOVER:-0}" != "1" ]; then
  echo "[gx] 拒绝执行。确有权接管才用 ALLOW_GPU_TAKEOVER=1。"
  echo "[gx] 当前占用：$(nvidia-smi --query-gpu=memory.used,utilization.gpu --format=csv,noheader | head -1)"
  exit 3
fi
OCC=$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits | head -1 | tr -d ' ')
if [ "$OCC" -ge 1000 ]; then echo "[gx] 拒绝执行：显存已占 ${OCC} MiB。"; exit 4; fi

export PATH=/usr/local/miniconda3/bin:$PATH
export VLLM_USE_FLASHINFER_SAMPLER=0

PY=/usr/local/miniconda3/bin/python
VLLM=/usr/local/miniconda3/bin/vllm
PORT=8013
LOG=/root/gx.log
R=/root/gx_res
mkdir -p "$R"
say() { echo "[$(date +%H:%M:%S)] $*" | tee -a "$LOG"; }
ONLY="${GX_ONLY:-}"
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

# $1 path ｜ $2 served-name ｜ $3 mm-kwargs（可空）
serve() {
  gpu_clear || return 1
  if [ -n "$3" ]; then
    setsid nohup $VLLM serve "$1" --served-model-name "$2" \
      --max-model-len 8192 --gpu-memory-utilization 0.93 \
      --limit-mm-per-prompt '{"image": 1}' --mm-processor-kwargs "$3" \
      --trust-remote-code --port $PORT </dev/null > "/root/gx_serve_$2.log" 2>&1 &
  else
    setsid nohup $VLLM serve "$1" --served-model-name "$2" \
      --max-model-len 8192 --gpu-memory-utilization 0.93 \
      --limit-mm-per-prompt '{"image": 1}' \
      --trust-remote-code --port $PORT </dev/null > "/root/gx_serve_$2.log" 2>&1 &
  fi
  for i in $(seq 1 90); do
    sleep 10
    curl -sf -m 5 -o /dev/null "http://127.0.0.1:$PORT/v1/models" && { say "  起服就绪 $2（$((i*10))s）"; return 0; }
    grep -qiE "Engine core initialization failed|is not supported|No module named|Value error,|TypeError|unexpected keyword" \
      "/root/gx_serve_$2.log" 2>/dev/null && { say "  !! $2 起服报错"; tail -3 "/root/gx_serve_$2.log" | sed 's/^/      /' >> "$LOG"; return 1; }
  done
  say "  !! $2 起服超时"; return 1
}

run_task() { PORT=$PORT TASK="$1" MODEL="$2" WORKERS="${3:-8}" $PY -u /root/gx_run.py; }
MMQ='"max_pixels": 1048576, "min_pixels": 3136'

say "########## 收官批开始 ONLY=${ONLY:-全部} ##########"

if want g8b; then
  say "===== G8b：另三格（英文/中文 base，同构建 BF16）====="
  if serve /model/ModelScope/Qwen/Qwen3-VL-32B-Instruct Qwen3-VL-32B-Instruct "{$MMQ}"; then
    run_task g8b Qwen3-VL-32B-Instruct; say "  g8b 完成"
  else say "  !! g8b 起服失败"; fi
fi

if want placebo; then
  say "===== placebo anchors（5/50/100/800）====="
  if serve /model/ModelScope/Qwen/Qwen3-VL-32B-Instruct Qwen3-VL-32B-Instruct "{$MMQ}"; then
    run_task placebo Qwen3-VL-32B-Instruct; say "  placebo 完成"
  else say "  !! placebo 起服失败"; fi
fi

if want g10mix; then
  say "===== G10：同批 vs 分侧（两个本机有同款权重的构建）====="
  for spec in "/root/models/InternVL3_5-8B|InternVL3_5-8B|" \
              "/model/ModelScope/LLM-Research/gemma-3-12b-it|gemma3-12b|"; do
    P=${spec%%|*}; rest=${spec#*|}; N=${rest%%|*}; K=${rest#*|}
    say "  ---- 构建 $N ----"
    if serve "$P" "$N" "$K"; then run_task g10mix "$N"; say "  $N 完成"; else say "  !! $N 起服失败"; fi
  done
fi

if want g9b; then
  gpu_clear || say "  !! 清显存失败（G9b 先要独占卡）"
  say "===== G9b：新阈值（15%）重开 —— 先闸门、后测量 ====="
  $PY -u /root/g9_guard.py --n 20 --tol 0.15 >> "$LOG" 2>&1
  if [ $? -ne 0 ]; then say "  !! G9b 闸门仍未过 ⇒ 仍报不可测"; else
    $PY -u /root/g9_hidden_l2.py >> "$LOG" 2>&1 && say "  G9b 测量完成"
  fi
fi

say "########## 收官批结束 ##########"
ls -l "$R" >> "$LOG"
gpu_clear
echo GX_ALL_DONE >> "$LOG"
