#!/bin/bash
# v7c：v7b 的最终版 ——
#   · **去掉 CountBench**（该域已因提问协议不符而作废，继续跑纯属浪费）
#   · 只跑 visdrone + aitod（真实有效的两个新域），n=150 分层抽样（所有模型同一批）
#   · 按价值排序：72B（规模）→ FP8 → AWQ-8bit → GPTQ → 8B-AWQ → InternVL2.5
#   · 结束后**主动把全部结果推送到 M机 并核对数量**（保证关机不丢数据）
set -u
export VLLM_USE_FLASHINFER_SAMPLER=0
export BAILIAN_API=http://127.0.0.1:8000/v1/chat/completions
export DASHSCOPE_API_KEY=dummy
PY=/root/vllm312/bin/python
VLLM=/root/vllm312/bin/vllm
L=/root/logs/exp_v7c.log
mkdir -p /root/logs /root/e1_results /root/e1_results_nonzero
say() { echo "[$(date +%H:%M:%S)] $*" | tee -a "$L"; }
N_NEW=150
DOMS="visdrone aitod"

gpu_clear() { for p in $(nvidia-smi --query-compute-apps=pid --format=csv,noheader 2>/dev/null | tr -d ' '); do [ -n "$p" ] && kill -9 "$p" 2>/dev/null; done; }
ready() { curl -s -f -m 5 -o /dev/null http://127.0.0.1:8000/v1/models; }
cnt_of() { ls "$1" 2>/dev/null | wc -l; }

serve() {
  local M=$1 N=$2 LG=$3 U=$4; shift 4
  local MMARG="${MM:-1}"
  [ -f "$M/config.json" ] || { say "  !! 权重不完整 $M"; return 1; }
  for attempt in 1 2; do
    pkill -9 -f 'vllm serve' 2>/dev/null; sleep 5; gpu_clear; sleep 5
    local EXTRA=""; [ "$attempt" = "2" ] && EXTRA="--attention-backend FLASH_ATTN"
    if [ "$MMARG" = "1" ]; then
      nohup $VLLM serve "$M" --served-model-name "$N" --max-model-len 8192 \
        --limit-mm-per-prompt '{"image": 1}' \
        --mm-processor-kwargs '{"max_pixels": 1048576, "min_pixels": 200704}' \
        --gpu-memory-utilization "$U" --max-num-seqs 24 --port 8000 $EXTRA "$@" > "$LG" 2>&1 &
    else
      nohup $VLLM serve "$M" --served-model-name "$N" --max-model-len 8192 \
        --limit-mm-per-prompt '{"image": 1}' \
        --gpu-memory-utilization "$U" --max-num-seqs 24 --port 8000 $EXTRA "$@" > "$LG" 2>&1 &
    fi
    local P=$! i
    for i in $(seq 1 48); do
      sleep 15
      kill -0 $P 2>/dev/null || { say "    $N 尝试$attempt 第 $((i*15))s 进程消失"; break; }
      ready && { say "    $N READY"; return 0; }
    done
    say "    $N 尝试$attempt 失败："; tail -4 "$LG" | sed 's/^/        /' | tee -a "$L"
  done
  say "  !! $N 起不来，跳过"; return 1
}
run() {
  local N=$1 DS=$2 A=$3 TAG=$4 POOL=$5 NN=$6 d dir b a t0 rc
  for d in $DS; do
    if [ "$POOL" = "nonzero" ]; then dir=/root/e1_results_nonzero; else dir=/root/e1_results; fi
    b=$(cnt_of "$dir")
    say "    跑 $N / $d / $A ($POOL, n=$NN)"
    t0=$(date +%s)
    $PY /root/19e_probe_multi.py --model "$N" --arms "$A" --ds "$d" --n "$NN" --workers 8 --pool "$POOL" \
      > "/root/logs/probe_${TAG}_${d}.log" 2>&1
    rc=$?
    a=$(cnt_of "$dir")
    say "      rc=$rc 文件 $b→$a 用时 $(( $(date +%s) - t0 ))s"
    [ "$a" -le "$b" ] && { say "      !! 未增长，日志尾："; tail -5 "/root/logs/probe_${TAG}_${d}.log" | sed 's/^/          /' | tee -a "$L"; }
  done
}

SIX=base,permit,bestA,bestB,bestC,channel
NZ=base,permit,channel

say "########## v7c 开始，等 v6 结束 $(date +%H:%M:%S) ##########"
while ! grep -q EXP_V6_DONE /root/logs/exp_v6.log 2>/dev/null; do say "  等 v6…"; sleep 300; done
say "v6 已结束"; sleep 30

block() {
  local D=$1 N=$2 LG=$3 U=$4 MMARG=$5; shift 5
  say "=== $N（新域 6 臂 + 非零池 3 臂，n=$N_NEW）==="
  MM=$MMARG serve "$D" "$N" "$LG" "$U" "$@" || return 1
  run "$N" "$DOMS" "$SIX" "v7c_${N}_new" zero "$N_NEW"
  run "$N" "$DOMS" "$NZ" "v7c_${N}_new_nz" nonzero "$N_NEW"
}

block /root/models/Qwen2.5-VL-72B-Instruct-AWQ   qwen25vl-72b-awq   /root/logs/v7c_72b.log   0.90 1
block /root/models/Qwen3-VL-32B-Instruct-FP8     qwen3-vl-32b-fp8   /root/logs/v7c_fp8.log   0.85 1
block /root/models/Qwen3-VL-32B-Instruct-AWQ-8bit qwen3-vl-32b-awq8 /root/logs/v7c_awq8.log  0.85 1
block /root/models/Qwen3-VL-32B-Instruct-GPTQ-W4 qwen3-vl-32b-gptq  /root/logs/v7c_gptq.log  0.75 1
block /root/models/Qwen3-VL-8B-Instruct-AWQ-4bit qwen3-vl-8b-awq    /root/logs/v7c_8bawq.log 0.75 1
block /root/models/InternVL2_5-8B-AWQ            internvl25-8b-awq  /root/logs/v7c_ivl.log   0.75 0 --trust-remote-code

# ===== 收尾：主动推送全部结果到 M机 并核对数量（保证关机不丢）=====
say "=== 收尾：推送全部结果到 M机 ==="
$PY -u /root/newh20_push.py > /root/logs/push_final.log 2>&1 &
sleep 120
pkill -f 'newh20_push.py' 2>/dev/null
say "  零池 $(cnt_of /root/e1_results) 个文件；非零池 $(cnt_of /root/e1_results_nonzero) 个文件"
say "M机 侧数量见 push_final.log"
grep -c '推送' /root/logs/push_final.log 2>/dev/null | sed 's/^/  本次推送条数: /' | tee -a "$L"
say "########## v7c 结束 $(date +%H:%M:%S) ##########"
echo EXP_V7C_DONE >> "$L"
echo ALL_EXPERIMENTS_DONE >> "$L"
