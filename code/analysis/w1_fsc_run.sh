#!/bin/bash
# w1_fsc_run.sh — W1d：FSC-147 上的示例（少样本）臂，跑在**同一批新家族**上。
# 判据 P6（冻结）：≥5/6 家族的零率下降 < 20 pp（相对）⇒ 零不是"计数能力不足"。
# 与主面板同一仪器思路（提示词/解析器复用 19e），单卡串行；等回收序列结束再起。
set -u
export BAILIAN_API=http://127.0.0.1:8000/v1/chat/completions
export DASHSCOPE_API_KEY=dummy
export VLLM_USE_FLASHINFER_SAMPLER=0
PY=/usr/local/miniconda3/bin/python
VLLM=/usr/local/miniconda3/bin/vllm
L=/root/logs/w1_fsc.log
mkdir -p /root/w1_results/fsc /root/logs
say() { echo "[$(date +%H:%M:%S)] $*" | tee -a "$L"; }
gpu_clear() {
  pkill -9 -i -f vllm 2>/dev/null; pkill -9 -f resource_tracker 2>/dev/null; sleep 3
  for i in $(seq 1 40); do
    used=$(nvidia-smi --query-gpu=memory.used --format=csv,noheader | tr -d ' MiB')
    [ "$used" -lt 500 ] && return 0; sleep 3
  done
  say "  !! 显存未清空：${used} MiB"; return 1
}
serve_up() {
  local N=$1 MP=$2 TAG=$3; shift 3
  gpu_clear || return 1
  setsid nohup $VLLM serve "$MP" --served-model-name "$N" --max-model-len 4096 \
    --limit-mm-per-prompt '{"image": 1}' --gpu-memory-utilization 0.85 --max-num-seqs 16 --port 8000 \
    "$@" </dev/null > "/root/logs/serve_w1fsc_${TAG}.log" 2>&1 &
  for i in $(seq 1 60); do
    sleep 15
    curl -sf -m 5 -o /dev/null http://127.0.0.1:8000/v1/models && { say "  [$TAG] 起服就绪 $((i*15))s"; return 0; }
    grep -qiE "Engine core initialization failed|Traceback|is not supported" \
      "/root/logs/serve_w1fsc_${TAG}.log" 2>/dev/null && { say "  [$TAG] !! 起服报错"; return 1; }
  done
  say "  [$TAG] !! 起服超时"; return 1
}
run_one() {   # <served_name> <path> <tag> [extra]
  local N=$1 MP=$2 TAG=$3; shift 3
  [ -d "$MP" ] || { say "跳过 FSC $TAG：无权重 $MP"; return 0; }
  say "===== FSC 臂：$TAG（$N）====="
  serve_up "$N" "$MP" "$TAG" "$@" || { say "!! $TAG 起服失败，跳过 FSC"; gpu_clear; return 0; }
  $PY /root/w1_fsc_probe.py --model "$N" --arms base,permit,exemplar3,exemplar3permit --n 300 --workers 8 >> "$L" 2>&1
  say "  [$TAG] FSC 产物 $(ls /root/w1_results/fsc/fsc_${N}_* 2>/dev/null | wc -l) 个文件"
  gpu_clear
}

say "等待回收序列结束（W1_RECOVER_DONE）…"
for i in $(seq 1 300); do
  grep -q W1_RECOVER_DONE /root/logs/w1_recover.log 2>/dev/null && break
  sleep 60
done
say "开始 FSC 示例臂序列"

CM=/model/ModelScope
run_one gemma-4-31b-it      $CM/google/gemma-4-31B-it          gemma4_31b
run_one MiniCPM-V-4_5       /root/w1_models/minicpm-v-4_5      minicpmv45 --trust-remote-code
run_one Step3-VL-10B        $CM/stepfun-ai/Step3-VL-10B        step3vl10b --trust-remote-code
run_one deepseek-vl2-tiny   /root/w1_models/deepseek-vl2-tiny  dsvl2_tiny
run_one Idefics3-8B-Llama3  /root/w1_models/idefics3-8b        idefics3_8b
run_one Molmo-7B-D-0924     /root/w1_models/molmo-7b-d         molmo7b

say "########## W1d 结束 ##########"
ls /root/w1_results/fsc | wc -l >> "$L"
echo "W1_FSC_DONE" >> "$L"
