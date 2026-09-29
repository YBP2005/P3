#!/bin/bash
# 精度阶梯扩展：exp.sh 跑完后自动执行
#   ① FP8 32B-Instruct 普查（官方 FP8，与 BF16/AWQ 同模型同引擎）
#   ② 腾空间：删掉已跑完的跨族/规模模型 → 下 GPTQ-W4 → GPTQ 普查
# 背景：/model 是只读挂载，只能放系统盘；故必须先腾空间。
set -u
export VLLM_USE_FLASHINFER_SAMPLER=0
export BAILIAN_API=http://127.0.0.1:8000/v1/chat/completions
export DASHSCOPE_API_KEY=dummy
PY=/root/vllm312/bin/python
VLLM=/root/vllm312/bin/vllm
L=/root/logs/exp_extra.log
mkdir -p /root/logs /root/e1_results /root/e1_results_nonzero
say() { echo "[$(date +%H:%M:%S)] $*" | tee -a "$L"; }

gpu_clear() {
  for p in $(nvidia-smi --query-compute-apps=pid --format=csv,noheader 2>/dev/null | tr -d ' '); do
    [ -n "$p" ] && kill -9 "$p" 2>/dev/null
  done
}
ready() { curl -s -f -m 5 -o /dev/null http://127.0.0.1:8000/v1/models; }

serve() {  # $1 model $2 name $3 log $4 util $5.. extra
  local M=$1 N=$2 LG=$3 U=$4; shift 4
  [ -d "$M" ] || { say "  !! 模型目录不存在: $M"; return 1; }
  pkill -9 -f 'vllm serve' 2>/dev/null; sleep 5; gpu_clear; sleep 5
  say "  起服务 $N（不带 attention-backend）"
  nohup $VLLM serve "$M" --served-model-name "$N" --max-model-len 8192 \
    --limit-mm-per-prompt '{"image": 1}' \
    --mm-processor-kwargs '{"max_pixels": 1048576, "min_pixels": 200704}' \
    --gpu-memory-utilization "$U" --max-num-seqs 24 --port 8000 "$@" > "$LG" 2>&1 &
  local P=$! i
  for i in $(seq 1 48); do
    sleep 15
    kill -0 $P 2>/dev/null || { say "    进程第 $((i*15))s 消失"; break; }
    ready && { say "    READY 显存 $(nvidia-smi --query-gpu=memory.used --format=csv,noheader)"; return 0; }
  done
  say "    失败 → 回退带 --attention-backend FLASH_ATTN"
  pkill -9 -f 'vllm serve' 2>/dev/null; sleep 5; gpu_clear; sleep 5
  nohup $VLLM serve "$M" --served-model-name "$N" --max-model-len 8192 \
    --limit-mm-per-prompt '{"image": 1}' \
    --mm-processor-kwargs '{"max_pixels": 1048576, "min_pixels": 200704}' \
    --gpu-memory-utilization "$U" --max-num-seqs 24 --port 8000 \
    --attention-backend FLASH_ATTN "$@" > "$LG" 2>&1 &
  P=$!
  for i in $(seq 1 48); do
    sleep 15
    kill -0 $P 2>/dev/null || { say "    回退后进程第 $((i*15))s 消失"; return 1; }
    ready && { say "    READY(回退)"; return 0; }
  done
  say "    !! 两种配置都起不来；日志尾："; tail -6 "$LG" | sed 's/^/        /' | tee -a "$L"
  return 1
}

run() {  # $1 探针 $2 模型名 $3 数据集 $4 臂 $5 标记
  local P=$1 N=$2 DS=$3 A=$4 TAG=$5 d before after rc
  for d in $DS; do
    case "$P" in
      19d*) before=$(ls /root/e1_results_nonzero/ 2>/dev/null | wc -l);;
      *)    before=$(ls /root/e1_results/ 2>/dev/null | wc -l);;
    esac
    say "    跑 $P / $N / $d / $A"
    $PY /root/$P --model "$N" --arms "$A" --ds "$d" --n 1000 --workers 8 \
      > "/root/logs/probe_${TAG}_${d}.log" 2>&1
    rc=$?
    case "$P" in
      19d*) after=$(ls /root/e1_results_nonzero/ 2>/dev/null | wc -l);;
      *)    after=$(ls /root/e1_results/ 2>/dev/null | wc -l);;
    esac
    say "      rc=$rc 文件 $before→$after"
    [ "$after" -le "$before" ] && { say "      !! 未产出，探针日志尾："; \
      tail -5 "/root/logs/probe_${TAG}_${d}.log" | sed 's/^/          /' | tee -a "$L"; }
  done
}

ALL=base,permit,bestA,bestB,bestC,channel
NZ=base,permit,channel

say "等 exp.sh 结束"
while ! grep -q EXP_ALL_DONE /root/logs/exp.log 2>/dev/null; do sleep 60; done
say "exp.sh 已结束"
sleep 30

# ============ ① FP8（官方）============
FP8DIR=/root/models/Qwen3-VL-32B-Instruct-FP8
if [ -f "$FP8DIR/config.json" ]; then
  say "=== FP8 普查 ==="
  if serve $FP8DIR qwen3-vl-32b-fp8 /root/logs/v_fp8.log 0.85; then
    run 19b_e1_probe.py qwen3-vl-32b-fp8 "st_a ucf" $ALL fp8
    run 19d_probe_nonzero.py qwen3-vl-32b-fp8 "st_a ucf" $NZ fp8nz
    run 19c_probe_paraphrase.py qwen3-vl-32b-fp8 "st_a ucf" permitB,permitC,channelB fp8para
  fi
else
  say "!! FP8 权重不完整，跳过（缺 config.json）"
fi

# ============ ② 补 GPTQ-W4 与 AWQ-8bit（构成 位宽×算法 的 2×2）============
# 注：系统盘已扩容到 182 GB，无需再删跨族模型腾空间。
say "=== 下 GPTQ-W4 与 AWQ-8bit ==="
$PY -u /root/h20_dl_model.py \
  LosCV29/Qwen3-VL-32B-Instruct-GPTQ-W4   /root/models/Qwen3-VL-32B-Instruct-GPTQ-W4 \
  cyankiwi/Qwen3-VL-32B-Instruct-AWQ-8bit /root/models/Qwen3-VL-32B-Instruct-AWQ-8bit \
  >> "$L" 2>&1
say "  下载结束"; df -h / | tail -1 | tee -a "$L"

GQ=/root/models/Qwen3-VL-32B-Instruct-GPTQ-W4
if [ -f "$GQ/config.json" ]; then
  say "=== GPTQ-W4 普查（分离『算法』变量：同为 4bit，不同算法）==="
  if serve $GQ qwen3-vl-32b-gptq /root/logs/v_gptq.log 0.75; then
    run 19b_e1_probe.py qwen3-vl-32b-gptq "st_a ucf" $ALL gptq
    run 19d_probe_nonzero.py qwen3-vl-32b-gptq "st_a ucf" $NZ gptqnz
  fi
else
  say "!! GPTQ 权重不完整，跳过"
fi

A8=/root/models/Qwen3-VL-32B-Instruct-AWQ-8bit
if [ -f "$A8/config.json" ]; then
  say "=== AWQ-8bit 普查（分离『位宽』变量：同为 AWQ，4bit vs 8bit）==="
  if serve $A8 qwen3-vl-32b-awq8 /root/logs/v_awq8bit.log 0.85; then
    run 19b_e1_probe.py qwen3-vl-32b-awq8 "st_a ucf" $ALL awq8bit
    run 19d_probe_nonzero.py qwen3-vl-32b-awq8 "st_a ucf" $NZ awq8bitnz
  fi
else
  say "!! AWQ-8bit 权重不完整，跳过"
fi

say "=== 扩展实验全部结束 $(date +%H:%M:%S) ==="
say "零池文件 $(ls /root/e1_results/ 2>/dev/null | wc -l)，非零池 $(ls /root/e1_results_nonzero/ 2>/dev/null | wc -l)"
echo EXP_EXTRA_DONE >> "$L"
