#!/bin/bash
# B1 公开基准实验：FSC-147（300 张分层抽样测试图）× 5 配置 × base+permit 两臂
# 每条记录都是"同一批 item"，故可跨配置比较；口径（弃权当 0 / 只算已答）由分析脚本处理。
# 单卡串行：每配置先清显存再起服。
set -u
export BAILIAN_API=http://127.0.0.1:8000/v1/chat/completions
export DASHSCOPE_API_KEY=dummy
export VLLM_USE_FLASHINFER_SAMPLER=0
PY=/usr/local/miniconda3/bin/python
VLLM=/usr/local/miniconda3/bin/vllm
L=/root/logs/a5_fsc.log
mkdir -p /root/logs /root/fsc_results
say() { echo "[$(date +%H:%M:%S)] $*" >> "$L"; }

gpu_clear() {
  pkill -9 -i -f vllm 2>/dev/null; pkill -9 -f resource_tracker 2>/dev/null; sleep 3
  for i in $(seq 1 40); do
    used=$(nvidia-smi --query-gpu=memory.used --format=csv,noheader | tr -d ' MiB')
    [ "$used" -lt 500 ] && return 0; sleep 3
  done
  say "  !! 显存未清空：${used} MiB"; return 1
}

# serve_up <served-name> <path> <tag> [extra...]
serve_up() {
  local N=$1 MP=$2 TAG=$3; shift 3
  gpu_clear || return 1
  setsid nohup $VLLM serve "$MP" --served-model-name "$N" --max-model-len 4096 \
    --limit-mm-per-prompt '{"image": 1}' --gpu-memory-utilization 0.85 --max-num-seqs 24 --port 8000 \
    "$@" </dev/null > "/root/logs/serve_fsc_${TAG}.log" 2>&1 &
  for i in $(seq 1 40); do
    sleep 15
    curl -sf -m 5 -o /dev/null http://127.0.0.1:8000/v1/models && { say "  [$TAG] 起服就绪（$((i*15))s）"; return 0; }
  done
  say "  [$TAG] !! 起服失败"; tail -5 "/root/logs/serve_fsc_${TAG}.log" | sed 's/^/      /' >> "$L"; return 1
}

run_cfg() {  # run_cfg <served-name> <tag>
  local N=$1 TAG=$2
  say "== [$TAG] FSC-147 base+permit 两臂 =="
  local t0=$(date +%s)
  $PY /root/19g_probe_fsc.py --model "$N" --arms base,permit --n 300 --workers 8 >> "$L" 2>&1
  say "   rc=$? 用时 $(( $(date +%s) - t0 ))s"
}

say "########## B1 FSC-147 开始 ##########"
if [ ! -s /root/fsc147/sample_test_ids.txt ]; then say "  !! 缺抽样清单，先跑下载脚本"; exit 1; fi

# ① Gemma-3-12B（只读缓存，零下载）
if serve_up gemma3-12b /model/ModelScope/LLM-Research/gemma-3-12b-it fsc_gemma; then run_cfg gemma3-12b fsc_gemma; fi
# ② InternVL3.5-8B
if serve_up InternVL3_5-8B /root/models/InternVL3_5-8B fsc_ivl --trust-remote-code; then run_cfg InternVL3_5-8B fsc_ivl; fi
# ③ Phi-3.5-Vision
if serve_up Phi-3.5-vision-instruct /root/models/Phi-3.5-vision-instruct fsc_phi --trust-remote-code; then run_cfg Phi-3.5-vision-instruct fsc_phi; fi
# ④ LLaVA-OneVision-7B
if serve_up llava-onevision-qwen2-7b-ov /root/models/llava-onevision-qwen2-7b-ov fsc_lov; then run_cfg llava-onevision-qwen2-7b-ov fsc_lov; fi
# ⑤ Qwen3-VL-32B-Instruct（只读缓存）
if serve_up Qwen3-VL-32B-Instruct /model/ModelScope/Qwen/Qwen3-VL-32B-Instruct fsc_q32; then run_cfg Qwen3-VL-32B-Instruct fsc_q32; fi

say "文件清点：$(ls /root/fsc_results | wc -l) 个"
say "########## B1 FSC-147 结束 ##########"
echo "B1_FSC_DONE" >> "$L"
