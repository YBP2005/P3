#!/bin/bash
# 精度阶梯扩展 v2：exp.sh 跑完后自动执行。
#   ① FP8 32B-Instruct 普查（官方 FP8，与 BF16/AWQ 同模型同引擎）
#   ② 下 GPTQ-W4 与 AWQ-8bit → 各自普查（构成 位宽×算法 2×2）
#
# v2 修复（v1 的缺陷）：
#   · v1 用「文件个数」判断是否产出，而 reps=3 与普查**写同名文件并按 item 去重追加**，
#     导致文件数不变、行数却增长 ⇒ 误报"未产出"。v2 改为同时看**总行数**与**去重后的
#     item 数**（去掉 #rN 后缀），这才是正确的量。
set -u
export VLLM_USE_FLASHINFER_SAMPLER=0
export BAILIAN_API=http://127.0.0.1:8000/v1/chat/completions
export DASHSCOPE_API_KEY=dummy
PY=/root/vllm312/bin/python
VLLM=/root/vllm312/bin/vllm
L=/root/logs/exp_extra2.log
mkdir -p /root/logs /root/e1_results /root/e1_results_nonzero
say() { echo "[$(date +%H:%M:%S)] $*" | tee -a "$L"; }

gpu_clear() {
  for p in $(nvidia-smi --query-compute-apps=pid --format=csv,noheader 2>/dev/null | tr -d ' '); do
    [ -n "$p" ] && kill -9 "$p" 2>/dev/null
  done
}
ready() { curl -s -f -m 5 -o /dev/null http://127.0.0.1:8000/v1/models; }

# 目录用量 = 「总行数(去表头) / 去重 item 数」，跨全部 CSV 统计
usage_of() {  # $1 = 目录
  $PY - "$1" <<'PYEOF'
import csv, glob, os, sys
d = sys.argv[1]
tot = 0
items = set()
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

# ============ ② 补 GPTQ-W4 与 AWQ-8bit ============
say "=== 下 GPTQ-W4 与 AWQ-8bit ==="
$PY -u /root/h20_dl_model.py \
  LosCV29/Qwen3-VL-32B-Instruct-GPTQ-W4   /root/models/Qwen3-VL-32B-Instruct-GPTQ-W4 \
  cyankiwi/Qwen3-VL-32B-Instruct-AWQ-8bit /root/models/Qwen3-VL-32B-Instruct-AWQ-8bit \
  >> "$L" 2>&1
say "  下载结束"; df -h / | tail -1 | tee -a "$L"

GQ=/root/models/Qwen3-VL-32B-Instruct-GPTQ-W4
if [ -f "$GQ/config.json" ]; then
  say "=== GPTQ-W4 普查（分离『算法』：同为 4bit，不同算法）==="
  if serve $GQ qwen3-vl-32b-gptq /root/logs/v_gptq.log 0.75; then
    run 19b_e1_probe.py qwen3-vl-32b-gptq "st_a ucf" $ALL gptq
    run 19d_probe_nonzero.py qwen3-vl-32b-gptq "st_a ucf" $NZ gptqnz
  fi
else
  say "!! GPTQ 权重不完整，跳过"
fi

A8=/root/models/Qwen3-VL-32B-Instruct-AWQ-8bit
if [ -f "$A8/config.json" ]; then
  say "=== AWQ-8bit 普查（分离『位宽』：同为 AWQ，4bit vs 8bit）==="
  if serve $A8 qwen3-vl-32b-awq8 /root/logs/v_awq8bit.log 0.85; then
    run 19b_e1_probe.py qwen3-vl-32b-awq8 "st_a ucf" $ALL awq8bit
    run 19d_probe_nonzero.py qwen3-vl-32b-awq8 "st_a ucf" $NZ awq8bitnz
  fi
else
  say "!! AWQ-8bit 权重不完整，跳过"
fi

read FT FU <<< "$(usage_of /root/e1_results)"
read NT NU <<< "$(usage_of /root/e1_results_nonzero)"
say "=== 扩展实验全部结束 $(date +%H:%M:%S) ==="
say "  零池：总行数 $FT，去重 item $FU"
say "  非零池：总行数 $NT，去重 item $NU"
echo EXP_EXTRA2_DONE >> "$L"
