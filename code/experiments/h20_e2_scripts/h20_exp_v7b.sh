#!/bin/bash
# v7b：v7 的省时版 —— 三个新域改用 150 项**分层抽样**（探针的分层抽样是确定性的，
#      故所有模型看到的是**同一批 150 项**，跨模型仍严格可比），把成本降到约一半。
#      动机：VisDrone 全池 273 项 × 6 臂 ≈ 23 分钟/模型（原图分辨率高 ⇒ prefill 贵），
#      6 个模型就是 ~3 小时；抽样后可压到 ~1.2 小时。
#      密集域仍用全池（那里本来就便宜）。
set -u
export VLLM_USE_FLASHINFER_SAMPLER=0
export BAILIAN_API=http://127.0.0.1:8000/v1/chat/completions
export DASHSCOPE_API_KEY=dummy
PY=/root/vllm312/bin/python
VLLM=/root/vllm312/bin/vllm
L=/root/logs/exp_v7b.log
mkdir -p /root/logs /root/e1_results /root/e1_results_nonzero
say() { echo "[$(date +%H:%M:%S)] $*" | tee -a "$L"; }
N_NEW=150

gpu_clear() {
  for p in $(nvidia-smi --query-compute-apps=pid --format=csv,noheader 2>/dev/null | tr -d ' '); do
    [ -n "$p" ] && kill -9 "$p" 2>/dev/null
  done
}
ready() { curl -s -f -m 5 -o /dev/null http://127.0.0.1:8000/v1/models; }
usage_of() {
  $PY - "$1" <<'PYEOF'
import csv, glob, os, sys
d = sys.argv[1]; tot = 0
for p in sorted(glob.glob(os.path.join(d, '*.csv'))):
    try:
        with open(p, encoding='utf-8-sig') as f:
            for _ in csv.DictReader(f):
                tot += 1
    except Exception:
        pass
print(tot)
PYEOF
}
serve() {
  local M=$1 N=$2 LG=$3 U=$4; shift 4
  local MMARG="${MM:-1}"
  [ -f "$M/config.json" ] || { say "  !! 权重不完整 $M"; return 1; }
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
run() {  # $1 model $2 datasets $3 arms $4 tag $5 pool $6 n
  local N=$1 DS=$2 A=$3 TAG=$4 POOL=$5 NN=${6:-1000} d dir b a t0 rc
  for d in $DS; do
    if [ "$POOL" = "nonzero" ]; then dir=/root/e1_results_nonzero; else dir=/root/e1_results; fi
    b=$(usage_of "$dir")
    say "    跑 $N / $d / $A ($POOL, n=$NN)"
    t0=$(date +%s)
    $PY /root/19e_probe_multi.py --model "$N" --arms "$A" --ds "$d" --n "$NN" --workers 8 --pool "$POOL" \
      > "/root/logs/probe_${TAG}_${d}.log" 2>&1
    rc=$?
    a=$(usage_of "$dir")
    say "      rc=$rc 行数 $b→$a 用时 $(( $(date +%s) - t0 ))s"
    [ "$a" -le "$b" ] && { say "      !! 未增长，日志尾："; tail -5 "/root/logs/probe_${TAG}_${d}.log" | sed 's/^/          /' | tee -a "$L"; }
  done
}

SIX=base,permit,bestA,bestB,bestC,channel
NZ=base,permit,channel
NEWDOMS="visdrone aitod countbench"

say "########## v7b 开始，等 v6 结束 $(date +%H:%M:%S) ##########"
while ! grep -q EXP_V6_DONE /root/logs/exp_v6.log 2>/dev/null; do say "  等 v6…"; sleep 300; done
say "v6 已结束"; sleep 30

block() {
  local D=$1 N=$2 LG=$3 U=$4 MMARG=$5; shift 5
  say "=== $N（新域 6 臂 + 非零池 3 臂，n=$N_NEW）==="
  MM=$MMARG serve "$D" "$N" "$LG" "$U" "$@" || return 1
  run "$N" "$NEWDOMS" "$SIX" "v7b_${N}_new" zero "$N_NEW"
  run "$N" "$NEWDOMS" "$NZ" "v7b_${N}_new_nz" nonzero "$N_NEW"
}

# 先跑最有价值的：72B（规模）与 FP8（精度轴的另一端）
block /root/models/Qwen2.5-VL-72B-Instruct-AWQ   qwen25vl-72b-awq  /root/logs/v7b_72b.log   0.90 1
block /root/models/Qwen3-VL-32B-Instruct-FP8     qwen3-vl-32b-fp8  /root/logs/v7b_fp8.log   0.85 1
block /root/models/Qwen3-VL-32B-Instruct-AWQ-8bit qwen3-vl-32b-awq8 /root/logs/v7b_awq8.log 0.85 1
block /root/models/Qwen3-VL-32B-Instruct-GPTQ-W4 qwen3-vl-32b-gptq /root/logs/v7b_gptq.log  0.75 1
block /root/models/Qwen3-VL-8B-Instruct-AWQ-4bit qwen3-vl-8b-awq   /root/logs/v7b_8bawq.log 0.75 1
block /root/models/InternVL2_5-8B-AWQ            internvl25-8b-awq /root/logs/v7b_ivl.log   0.75 0 --trust-remote-code

say "########## v7b 结束 $(date +%H:%M:%S) ##########"
echo EXP_V7B_DONE >> "$L"
