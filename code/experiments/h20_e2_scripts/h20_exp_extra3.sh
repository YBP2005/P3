#!/bin/bash
# 精度阶梯扩展 v3：等 v2 结束后跑 72B 级规模检验。
#   Qwen2.5-VL-72B-Instruct-AWQ（43 GB 权重，5090 明确装不下）
#   —— 回答"契约效应在 72B 规模是否仍成立"
#   ⚠ 注意：它是**上一代**（Qwen2.5-VL vs 我们的 Qwen3-VL）⇒ 这是"代际+规模"混合变量，
#      论文里只能表述为"更大规模的另一个家族"，不得当作干净的规模阶梯。
set -u
export VLLM_USE_FLASHINFER_SAMPLER=0
export BAILIAN_API=http://127.0.0.1:8000/v1/chat/completions
export DASHSCOPE_API_KEY=dummy
PY=/root/vllm312/bin/python
VLLM=/root/vllm312/bin/vllm
L=/root/logs/exp_extra3.log
mkdir -p /root/logs /root/e1_results /root/e1_results_nonzero
say() { echo "[$(date +%H:%M:%S)] $*" | tee -a "$L"; }

gpu_clear() {
  for p in $(nvidia-smi --query-compute-apps=pid --format=csv,noheader 2>/dev/null | tr -d ' '); do
    [ -n "$p" ] && kill -9 "$p" 2>/dev/null
  done
}
ready() { curl -s -f -m 5 -o /dev/null http://127.0.0.1:8000/v1/models; }

usage_of() {  # $1 = 目录 → "总行数 去重item数"
  $PY - "$1" <<'PYEOF'
import csv, glob, os, sys
d = sys.argv[1]; tot = 0; items = set()
for p in sorted(glob.glob(os.path.join(d, '*.csv'))):
    try:
        with open(p, encoding='utf-8-sig') as f:
            for r in csv.DictReader(f):
                tot += 1
                it = str(r.get('item', ''))
                items.add(it.split('#r')[0] if '#r' in it else it)
    except Exception:
        pass
print('%d %d' % (tot, len(items)))
PYEOF
}

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
  for i in $(seq 1 60); do
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
  for i in $(seq 1 60); do
    sleep 15
    kill -0 $P 2>/dev/null || { say "    回退后进程第 $((i*15))s 消失"; return 1; }
    ready && { say "    READY(回退)"; return 0; }
  done
  say "    !! 两种配置都起不来；日志尾："; tail -8 "$LG" | sed 's/^/        /' | tee -a "$L"
  return 1
}

run() {  # $1 探针 $2 模型名 $3 数据集 $4 臂 $5 标记
  local P=$1 N=$2 DS=$3 A=$4 TAG=$5 d dir b_tot b_uni a_tot a_uni t0 rc
  for d in $DS; do
    case "$P" in
      19d*) dir=/root/e1_results_nonzero;;
      *)    dir=/root/e1_results;;
    esac
    read b_tot b_uni <<< "$(usage_of "$dir")"
    say "    跑 $P / $N / $d / $A"
    t0=$(date +%s)
    $PY /root/$P --model "$N" --arms "$A" --ds "$d" --n 1000 --workers 8 \
      > "/root/logs/probe_${TAG}_${d}.log" 2>&1
    rc=$?
    read a_tot a_uni <<< "$(usage_of "$dir")"
    say "      rc=$rc 行数 $b_tot→$a_tot 去重item $b_uni→$a_uni 用时 $(( $(date +%s) - t0 ))s"
    if [ "$a_tot" -le "$b_tot" ] && [ "$a_uni" -le "$b_uni" ]; then
      say "      !! 行数与去重 item 数都未增长，探针日志尾："
      tail -5 "/root/logs/probe_${TAG}_${d}.log" | sed 's/^/          /' | tee -a "$L"
    fi
  done
}

ALL=base,permit,bestA,bestB,bestC,channel
NZ=base,permit,channel

say "等第二批扩展实验结束（EXP_EXTRA2_DONE）"
while ! grep -q EXP_EXTRA2_DONE /root/logs/exp_extra2.log 2>/dev/null; do sleep 60; done
say "v2 已结束"
sleep 30

M72=/root/models/Qwen2.5-VL-72B-Instruct-AWQ
if [ -f "$M72/config.json" ]; then
  say "=== Qwen2.5-VL-72B-AWQ 规模检验（6 臂零池 + 3 臂反证对照）==="
  if serve $M72 qwen25vl-72b-awq /root/logs/v_72b.log 0.90; then
    run 19b_e1_probe.py qwen25vl-72b-awq "st_a ucf" $ALL q25vl72b
    run 19d_probe_nonzero.py qwen25vl-72b-awq "st_a ucf" $NZ q25vl72bnz
    run 19c_probe_paraphrase.py qwen25vl-72b-awq "st_a ucf" permitB,permitC,channelB q25vl72bpara
  fi
else
  say "!! 72B 权重不完整，跳过"
fi

read FT FU <<< "$(usage_of /root/e1_results)"
read NT NU <<< "$(usage_of /root/e1_results_nonzero)"
say "=== v3 结束 $(date +%H:%M:%S) ==="
say "  零池：总行数 $FT，去重 item $FU"
say "  非零池：总行数 $NT，去重 item $NU"
echo EXP_EXTRA3_DONE >> "$L"
