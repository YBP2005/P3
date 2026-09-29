#!/bin/bash
# FSC-147 面板扩展：在已有 5 配置（Gemma-3-12B / InternVL3.5-8B / Phi-3.5-V / LLaVA-OV-7B / Qwen3-VL-32B）
# 之上再加 4 个只读缓存里的配置，形成 **9 配置 / 6 血统**的公开基准面板：
#   Qwen3-VL-8B、Qwen3-VL-4B、Qwen3-VL-30B-A3B(MoE)、Qwen2.5-VL-3B
# 臂：base + permit（与主实验同臂），n=300，与既有配置**同一批 item**。
set -u
export BAILIAN_API=http://127.0.0.1:8000/v1/chat/completions
export DASHSCOPE_API_KEY=dummy
export VLLM_USE_FLASHINFER_SAMPLER=0
PY=/usr/local/miniconda3/bin/python
VLLM=/usr/local/miniconda3/bin/vllm
L=/root/logs/a5_fsc3.log
say() { echo "[$(date +%H:%M:%S)] $*" >> "$L"; }

say "########## FSC 面板扩展开始（等机制臂结束）##########"
for i in $(seq 1 120); do
  grep -q FSC2_DONE /root/logs/a5_fsc2.log 2>/dev/null && { say "  机制臂已完成，开始扩展"; break; }
  sleep 30
done

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
    "$@" </dev/null > "/root/logs/serve_fsc3_${TAG}.log" 2>&1 &
  for i in $(seq 1 40); do
    sleep 15
    curl -sf -m 5 -o /dev/null http://127.0.0.1:8000/v1/models && { say "  [$TAG] 起服就绪（$((i*15))s）"; return 0; }
  done
  say "  [$TAG] !! 起服失败"; tail -5 "/root/logs/serve_fsc3_${TAG}.log" | sed 's/^/      /' >> "$L"; return 1
}
run_cfg() {
  local N=$1 TAG=$2 t0=$(date +%s)
  $PY /root/19g_probe_fsc.py --model "$N" --arms base,permit --n 300 --workers 8 >> "$L" 2>&1
  say "  [$TAG] rc=$? 用时 $(( $(date +%s) - t0 ))s"
}

CM=/model/ModelScope/Qwen
if serve_up Qwen3-VL-8B-Instruct   $CM/Qwen3-VL-8B-Instruct   fsc3_q8;  then run_cfg Qwen3-VL-8B-Instruct fsc3_q8; fi
if serve_up Qwen3-VL-4B-Instruct   $CM/Qwen3-VL-4B-Instruct   fsc3_q4;  then run_cfg Qwen3-VL-4B-Instruct fsc3_q4; fi
if serve_up Qwen3-VL-30B-A3B-Instruct $CM/Qwen3-VL-30B-A3B-Instruct fsc3_q30m; then run_cfg Qwen3-VL-30B-A3B-Instruct fsc3_q30m; fi
if serve_up Qwen2.5-VL-3B-Instruct $CM/Qwen2.5-VL-3B-Instruct fsc3_q253; then run_cfg Qwen2.5-VL-3B-Instruct fsc3_q253; fi

say "文件清点：$(ls /root/fsc_results | wc -l) 个"
say "########## FSC 面板扩展结束 ##########"
echo "FSC3_DONE" >> "$L"
