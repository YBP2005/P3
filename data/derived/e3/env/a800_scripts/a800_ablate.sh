#!/bin/bash
# A5 消融：输入尺度 + 模板中性化（对应 A5 方案 §2.4）
# 用**独立仪器** 19f_probe_ablation.py（由 19e 派生，见 make_19f.py），不碰 19e 字节。
# 家族：Gemma-3-12B（只读缓存，无需下载）；域：st_a + ucf；池：零池；臂：base,permit,channel
# 三个变体：
#   native —— 与主实验同条件（正面复现性检查：应与 A5 主跑逐 item 一致）
#   s640   —— 最长边缩放到 640（输入尺度中性化）
#   sys    —— 额外插一条 system 消息（模板中性化）
set -u
export BAILIAN_API=http://127.0.0.1:8000/v1/chat/completions
export DASHSCOPE_API_KEY=dummy
export VLLM_USE_FLASHINFER_SAMPLER=0
PY=/usr/local/miniconda3/bin/python
VLLM=/usr/local/miniconda3/bin/vllm
MPATH=/model/ModelScope/LLM-Research/gemma-3-12b-it
N=gemma3-12b
L=/root/logs/a5_ablation.log
OUT=/root/e1_results_ablate
mkdir -p /root/logs $OUT
say() { echo "[$(date +%H:%M:%S)] $*" >> "$L"; }

gpu_clear() {
  pkill -9 -i -f vllm 2>/dev/null
  pkill -9 -f resource_tracker 2>/dev/null
  sleep 3
  for i in $(seq 1 30); do
    used=$(nvidia-smi --query-gpu=memory.used --format=csv,noheader | tr -d ' MiB')
    [ "$used" -lt 500 ] && return 0
    sleep 3
  done
  say "  !! 显存未清空：${used} MiB"
}

say "########## A5 消融开始（$N @ $MPATH）##########"
gpu_clear
setsid nohup $VLLM serve "$MPATH" --served-model-name "$N" --max-model-len 8192 \
  --limit-mm-per-prompt '{"image": 1}' --gpu-memory-utilization 0.85 --max-num-seqs 24 --port 8000 \
  </dev/null > "/root/logs/serve_ablation.log" 2>&1 &
OK=0
for i in $(seq 1 40); do
  sleep 15
  if curl -sf -m 5 -o /dev/null http://127.0.0.1:8000/v1/models; then say "  起服就绪（$((i*15))s）"; OK=1; break; fi
done
if [ "$OK" != "1" ]; then say "  !! 起服失败"; tail -12 /root/logs/serve_ablation.log >> "$L"; exit 1; fi

run() {  # run <variant-args...>
  local tag="$1"; shift
  for ds in st_a ucf; do
    say "== 变体 $tag / $ds 零池 3 臂 =="
    t0=$(date +%s)
    $PY /root/19f_probe_ablation.py --model "$N" --arms base,permit,channel \
        --ds "$ds" --n 150 --workers 8 --pool zero --outdir $OUT "$@" >> "$L" 2>&1
    say "   rc=$? 用时 $(( $(date +%s) - t0 ))s"
  done
}

run native
run s640   --imgsz 640
run sys    --system 'You are a careful visual counting assistant. Follow the requested output format exactly.'

say "消融文件 $(ls $OUT | wc -l) 个"
say "########## A5 消融结束 ##########"
echo "A5_ABLATION_DONE" >> "$L"
