#!/bin/bash
# v7：把「域 × 模型」网格补齐 —— 三个新域在其余模型上各跑 6 臂零池 + 3 臂非零池。
# 等 v6 结束（EXP_V6_DONE）后自动接上；每个模型只起一次服务。
# 目的：让「域 × 精度」与「域 × 族/规模」两个交叉都完整。
set -u
export VLLM_USE_FLASHINFER_SAMPLER=0
export BAILIAN_API=http://127.0.0.1:8000/v1/chat/completions
export DASHSCOPE_API_KEY=dummy
PY=/root/vllm312/bin/python
VLLM=/root/vllm312/bin/vllm
L=/root/logs/exp_v7.log
mkdir -p /root/logs /root/e1_results /root/e1_results_nonzero
say() { echo "[$(date +%H:%M:%S)] $*" | tee -a "$L"; }

gpu_clear() {
  for p in $(nvidia-smi --query-compute-apps=pid --format=csv,noheader 2>/dev/null | tr -d ' '); do
    [ -n "$p" ] && kill -9 "$p" 2>/dev/null
  done
}
ready() { curl -s -f -m 5 -o /dev/null http://127.0.0.1:8000/v1/models; }

usage_of() {
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

serve() {  # $1 model $2 name $3 log $4 util ; MM=0 时不传 mm-processor-kwargs
  local M=$1 N=$2 LG=$3 U=$4; shift 4
  local MMARG="${MM:-1}"
  [ -d "$M" ] || { say "  !! 目录不存在: $M"; return 1; }
  for attempt in 1 2; do
    pkill -9 -f 'vllm serve' 2>/dev/null; sleep 5; gpu_clear; sleep 5
    local EXTRA=""
    [ "$attempt" = "2" ] && EXTRA="--attention-backend FLASH_ATTN"
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
      ready && { say "    $N 尝试$attempt READY"; return 0; }
    done
    say "    $N 尝试$attempt 失败："; tail -4 "$LG" | sed 's/^/        /' | tee -a "$L"
  done
  say "  !! $N 起不来，跳过"
  return 1
}

run() {  # $1 model $2 datasets $3 arms $4 tag $5 pool
  local N=$1 DS=$2 A=$3 TAG=$4 POOL=$5 d dir b_tot b_uni a_tot a_uni t0 rc
  for d in $DS; do
    if [ "$POOL" = "nonzero" ]; then dir=/root/e1_results_nonzero; else dir=/root/e1_results; fi
    read b_tot b_uni <<< "$(usage_of "$dir")"
    say "    跑 $N / $d / $A ($POOL)"
    t0=$(date +%s)
    $PY /root/19e_probe_multi.py --model "$N" --arms "$A" --ds "$d" --n 1000 --workers 8 --pool "$POOL" \
      > "/root/logs/probe_${TAG}_${d}.log" 2>&1
    rc=$?
    read a_tot a_uni <<< "$(usage_of "$dir")"
    say "      rc=$rc 行数 $b_tot→$a_tot 用时 $(( $(date +%s) - t0 ))s"
    if [ "$a_tot" -le "$b_tot" ]; then
      say "      !! 未增长，日志尾："; tail -5 "/root/logs/probe_${TAG}_${d}.log" | sed 's/^/          /' | tee -a "$L"
    fi
  done
}

SIX=base,permit,bestA,bestB,bestC,channel
NZ=base,permit,channel
NEWDOMS="visdrone aitod countbench"

say "########## v7 开始，等 v6 结束 $(date +%H:%M:%S) ##########"
while ! grep -q EXP_V6_DONE /root/logs/exp_v6.log 2>/dev/null; do
  say "  等 v6…"; sleep 300
done
say "v6 已结束"
sleep 30

block() {  # $1 dir $2 name $3 log $4 util $5 mmflag $6.. extra
  local D=$1 N=$2 LG=$3 U=$4 MMARG=$5; shift 5
  [ -f "$D/config.json" ] || { say "  （跳过 $N：权重不完整）"; return 1; }
  say "=== $N ==="
  MM=$MMARG serve "$D" "$N" "$LG" "$U" "$@" || return 1
  run "$N" "$NEWDOMS" "$SIX" "v7_${N}_new" zero
  run "$N" "$NEWDOMS" "$NZ" "v7_${N}_new_nz" nonzero
}

block /root/models/Qwen3-VL-32B-Instruct-FP8          qwen3-vl-32b-fp8     /root/logs/v7_fp8.log    0.85 1
block /root/models/Qwen3-VL-32B-Instruct-GPTQ-W4      qwen3-vl-32b-gptq    /root/logs/v7_gptq.log   0.75 1
block /root/models/Qwen3-VL-32B-Instruct-AWQ-8bit     qwen3-vl-32b-awq8    /root/logs/v7_awq8.log   0.85 1
block /root/models/Qwen3-VL-8B-Instruct-AWQ-4bit      qwen3-vl-8b-awq      /root/logs/v7_8bawq.log  0.75 1
block /root/models/InternVL2_5-8B-AWQ                 internvl25-8b-awq    /root/logs/v7_ivl.log    0.75 0 --trust-remote-code
block /root/models/Qwen2.5-VL-72B-Instruct-AWQ        qwen25vl-72b-awq     /root/logs/v7_72b.log    0.90 1

read FT FU <<< "$(usage_of /root/e1_results)"
read NT NU <<< "$(usage_of /root/e1_results_nonzero)"
say "########## v7 结束 $(date +%H:%M:%S) ##########"
say "  零池：总行数 $FT，去重 item $FU"
say "  非零池：总行数 $NT，去重 item $NU"
echo EXP_V7_DONE >> "$L"
