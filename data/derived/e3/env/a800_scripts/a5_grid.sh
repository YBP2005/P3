#!/bin/bash
# A5 单家族全格：起服 -> 4 域 x (零池 6 臂 + 非零池 3 臂) x n=150
# 用法: bash /root/a5_grid.sh <served-name> <model-path> <tag> [额外的 vllm 参数...]
#   · InternVL 系列需要 --trust-remote-code
#   · Phi-3.5-vision 需要 --trust-remote-code
set -u
export BAILIAN_API=http://127.0.0.1:8000/v1/chat/completions
export DASHSCOPE_API_KEY=dummy
export VLLM_USE_FLASHINFER_SAMPLER=0
PY=/usr/local/miniconda3/bin/python
VLLM=/usr/local/miniconda3/bin/vllm
N=$1; MPATH=$2; TAG=$3; shift 3
EXTRA="$*"
L="/root/logs/a5_${TAG}.log"
mkdir -p /root/logs /root/e1_results /root/e1_results_nonzero
say() { echo "[$(date +%H:%M:%S)] $*" >> "$L"; }

gpu_clear() {
  # ★ 必须 -i（大小写不敏感）：进程名是 VLLM::EngineCore
  pkill -9 -i -f vllm 2>/dev/null
  pkill -9 -f resource_tracker 2>/dev/null
  sleep 3
  for p in $(ps -eo pid,cmd | grep -E "EngineCore" | grep -v grep | awk '{print $1}'); do kill -9 "$p" 2>/dev/null; done
  for i in $(seq 1 20); do
    used=$(nvidia-smi --query-gpu=memory.used --format=csv,noheader | tr -d ' MiB')
    [ "$used" -lt 500 ] && return 0
    sleep 3
  done
  say "  !! 显存未清空：${used} MiB"
}

say "########## A5 家族 ${TAG} 开始（$N；extra='$EXTRA'）##########"
gpu_clear
setsid nohup $VLLM serve "$MPATH" --served-model-name "$N" --max-model-len 8192 \
  --limit-mm-per-prompt '{"image": 1}' --gpu-memory-utilization 0.85 --max-num-seqs 24 --port 8000 \
  $EXTRA </dev/null > "/root/logs/serve_${TAG}.log" 2>&1 &
OK=0
for i in $(seq 1 40); do
  sleep 15
  if curl -sf -m 5 -o /dev/null http://127.0.0.1:8000/v1/models; then say "  起服就绪（$((i*15))s）"; OK=1; break; fi
done
if [ "$OK" != "1" ]; then say "  !! 起服失败，日志尾："; tail -12 "/root/logs/serve_${TAG}.log" | sed 's/^/      /' >> "$L"; exit 1; fi

for ds in st_a ucf visdrone aitod; do
  say "== $N / $ds 零池 6 臂 =="
  t0=$(date +%s)
  $PY /root/19e_probe_multi.py --model "$N" --arms base,permit,bestA,bestB,bestC,channel \
      --ds "$ds" --n 150 --workers 8 --pool zero >> "$L" 2>&1
  say "   rc=$? 用时 $(( $(date +%s) - t0 ))s"
  say "== $N / $ds 非零池 3 臂 =="
  t0=$(date +%s)
  $PY /root/19e_probe_multi.py --model "$N" --arms base,permit,channel \
      --ds "$ds" --n 150 --workers 8 --pool nonzero >> "$L" 2>&1
  say "   rc=$? 用时 $(( $(date +%s) - t0 ))s"
done
say "零池文件 $(ls /root/e1_results | wc -l) 个；非零池 $(ls /root/e1_results_nonzero | wc -l) 个"
say "########## A5 家族 ${TAG} 结束 ##########"
echo "A5_${TAG}_DONE" >> "$L"
