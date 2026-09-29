#!/bin/bash
# FSC-147 机制臂补充：在已完成的 base/permit 之上，加跑 channel 与 enumAbstain 两臂
# 目的：解释"Qwen3-VL-32B 在 FSC 上 permit 仍答 0（251/277）"这一反例——
#       是"模型拒绝给出口"，还是"这个出口措辞在该域不奏效"（channel 提供三选一出口）。
set -u
export BAILIAN_API=http://127.0.0.1:8000/v1/chat/completions
export DASHSCOPE_API_KEY=dummy
export VLLM_USE_FLASHINFER_SAMPLER=0
PY=/usr/local/miniconda3/bin/python
VLLM=/usr/local/miniconda3/bin/vllm
L=/root/logs/a5_fsc2.log
say() { echo "[$(date +%H:%M:%S)] $*" >> "$L"; }
say "########## FSC 机制臂开始 ##########"

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
    --limit-mm-per-prompt '{"image": 1}' --gpu-memory-utilization 0.85 --max-num-seqs 24 --port 8000 \
    "$@" </dev/null > "/root/logs/serve_fsc2_${TAG}.log" 2>&1 &
  for i in $(seq 1 40); do
    sleep 15
    curl -sf -m 5 -o /dev/null http://127.0.0.1:8000/v1/models && { say "  [$TAG] 起服就绪（$((i*15))s）"; return 0; }
  done
  say "  [$TAG] !! 起服失败"; tail -5 "/root/logs/serve_fsc2_${TAG}.log" | sed 's/^/      /' >> "$L"; return 1
}
run_arms() {
  local N=$1 TAG=$2
  say "== [$TAG] channel,enumAbstain =="
  local t0=$(date +%s)
  $PY /root/19g_probe_fsc.py --model "$N" --arms channel,enumAbstain --n 300 --workers 8 >> "$L" 2>&1
  say "   rc=$? 用时 $(( $(date +%s) - t0 ))s"
}

if serve_up gemma3-12b /model/ModelScope/LLM-Research/gemma-3-12b-it fsc2_gemma; then run_arms gemma3-12b fsc2_gemma; fi
if serve_up InternVL3_5-8B /root/models/InternVL3_5-8B fsc2_ivl --trust-remote-code; then run_arms InternVL3_5-8B fsc2_ivl; fi
if serve_up Phi-3.5-vision-instruct /root/models/Phi-3.5-vision-instruct fsc2_phi --trust-remote-code; then run_arms Phi-3.5-vision-instruct fsc2_phi; fi
if serve_up llava-onevision-qwen2-7b-ov /root/models/llava-onevision-qwen2-7b-ov fsc2_lov; then run_arms llava-onevision-qwen2-7b-ov fsc2_lov; fi
if serve_up Qwen3-VL-32B-Instruct /model/ModelScope/Qwen/Qwen3-VL-32B-Instruct fsc2_q32; then run_arms Qwen3-VL-32B-Instruct fsc2_q32; fi

say "文件清点：$(ls /root/fsc_results | wc -l) 个"
say "########## FSC 机制臂结束 ##########"
echo "FSC2_DONE" >> "$L"
