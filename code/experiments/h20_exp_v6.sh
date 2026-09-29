#!/bin/bash
# 扩满 v6：等 v4 结束后接上，把"该做的"一次做完。
#
# 覆盖四件事：
#   ① 新臂（enum / enumAbstain / locate）在密集域 st_a+ucf 上跑 ⇒ 检验主稿 §3.6(d)
#   ② 9 臂 × 三个新域（visdrone 航拍 / aitod 航拍微小 / countbench 自然图）⇐ 机制检验
#   ③ 补 v4 被跳过的 AWQ-8bit 32B 普查（其分片已修好并通过尺寸精确校验）
#   ④ 新模型（4B / 2B / 30B-A3B-FP8 / InternVL3.5-38B-FP8）的零池普查（若已下载完）
#
# 与 19b/19d 的可比性：19e 默认 --pool zero 且 OUTD 与 19b 相同；原有提示词/解析/抽样一字未改
# （生成器带"逐字还原"断言）。6 臂的结果与既有数据同格式、同目录、可直接并表。
set -u
export VLLM_USE_FLASHINFER_SAMPLER=0
export BAILIAN_API=http://127.0.0.1:8000/v1/chat/completions
export DASHSCOPE_API_KEY=dummy
PY=/root/vllm312/bin/python
VLLM=/root/vllm312/bin/vllm
L=/root/logs/exp_v6.log
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

serve() {  # $1 model $2 name $3 log $4 util ; MM=0 时不传 mm-processor-kwargs（InternVL 系）
  local M=$1 N=$2 LG=$3 U=$4; shift 4
  local MMARG="${MM:-1}"
  [ -d "$M" ] || { say "  !! 模型目录不存在: $M"; return 1; }
  for attempt in 1 2; do
    pkill -9 -f 'vllm serve' 2>/dev/null; sleep 5; gpu_clear; sleep 5
    local EXTRA=""
    [ "$attempt" = "2" ] && EXTRA="--attention-backend FLASH_ATTN"
    if [ "$MMARG" = "1" ]; then
      say "  起服务 $N（尝试$attempt）"
      nohup $VLLM serve "$M" --served-model-name "$N" --max-model-len 8192 \
        --limit-mm-per-prompt '{"image": 1}' \
        --mm-processor-kwargs '{"max_pixels": 1048576, "min_pixels": 200704}' \
        --gpu-memory-utilization "$U" --max-num-seqs 24 --port 8000 $EXTRA "$@" > "$LG" 2>&1 &
    else
      say "  起服务 $N（尝试$attempt，**不传 mm-processor-kwargs**）"
      nohup $VLLM serve "$M" --served-model-name "$N" --max-model-len 8192 \
        --limit-mm-per-prompt '{"image": 1}' \
        --gpu-memory-utilization "$U" --max-num-seqs 24 --port 8000 $EXTRA "$@" > "$LG" 2>&1 &
    fi
    local P=$! i
    for i in $(seq 1 48); do
      sleep 15
      kill -0 $P 2>/dev/null || { say "    尝试$attempt 第 $((i*15))s 进程消失"; break; }
      ready && { say "    尝试$attempt READY 显存 $(nvidia-smi --query-gpu=memory.used --format=csv,noheader)"; return 0; }
    done
    say "    尝试$attempt 失败，日志尾："; tail -5 "$LG" | sed 's/^/        /' | tee -a "$L"
  done
  say "  !! $N 两次尝试都起不来"
  return 1
}

run() {  # $1 探针 $2 模型名 $3 数据集 $4 臂 $5 标记 [$6 pool]
  local P=$1 N=$2 DS=$3 A=$4 TAG=$5 POOL=${6:-zero}
  local d dir b_tot b_uni a_tot a_uni t0 rc
  for d in $DS; do
    if [ "$POOL" = "nonzero" ]; then dir=/root/e1_results_nonzero; else dir=/root/e1_results; fi
    read b_tot b_uni <<< "$(usage_of "$dir")"
    say "    跑 $P($POOL) / $N / $d / $A"
    t0=$(date +%s)
    $PY /root/$P --model "$N" --arms "$A" --ds "$d" --n 1000 --workers 8 --pool "$POOL" \
      > "/root/logs/probe_${TAG}_${d}.log" 2>&1
    rc=$?
    read a_tot a_uni <<< "$(usage_of "$dir")"
    say "      rc=$rc 行数 $b_tot→$a_tot 去重item $b_uni→$a_uni 用时 $(( $(date +%s) - t0 ))s"
    if [ "$a_tot" -le "$b_tot" ] && [ "$a_uni" -le "$b_uni" ]; then
      say "      !! 两项都未增长，探针日志尾："
      tail -6 "/root/logs/probe_${TAG}_${d}.log" | sed 's/^/          /' | tee -a "$L"
    fi
  done
}

SIX=base,permit,bestA,bestB,bestC,channel
NINE=base,permit,bestA,bestB,bestC,channel,enum,enumAbstain,locate
NZ=base,permit,channel
NEWDOMS="visdrone aitod countbench"

say "########## v6 开始，等 v4 结束 $(date +%H:%M:%S) ##########"
while ! grep -q EXP_V4_DONE /root/logs/exp_v4.log 2>/dev/null; do
  say "  等 v4…"; sleep 300
done
say "v4 已结束"
sleep 30

# ================= ① AWQ-32B：新臂 + 新域 =================
if serve /root/models/Qwen3-VL-32B-Instruct-AWQ-4bit qwen3-vl-32b-awq /root/logs/v6_awq32.log 0.75; then
  say "=== ① AWQ-32B 新臂（§3.6(d) 检验）==="
  run 19e_probe_multi.py qwen3-vl-32b-awq "st_a ucf" "$NINE" v6a_awq32_dense
  say "=== ② AWQ-32B 三个新域（零池 9 臂 + 非零池 3 臂）==="
  run 19e_probe_multi.py qwen3-vl-32b-awq "$NEWDOMS" "$NINE" v6a_awq32_newdom
  run 19e_probe_multi.py qwen3-vl-32b-awq "$NEWDOMS" "$NZ" v6a_awq32_newdom_nz nonzero
fi

# ================= ② BF16-32B：同上 =================
if serve /model/ModelScope/Qwen/Qwen3-VL-32B-Instruct qwen3-vl-32b-bf16 /root/logs/v6_bf32.log 0.90; then
  say "=== ③ BF16-32B 新臂 ==="
  run 19e_probe_multi.py qwen3-vl-32b-bf16 "st_a ucf" "$NINE" v6b_bf32_dense
  say "=== ④ BF16-32B 三个新域 ==="
  run 19e_probe_multi.py qwen3-vl-32b-bf16 "$NEWDOMS" "$NINE" v6b_bf32_newdom
  run 19e_probe_multi.py qwen3-vl-32b-bf16 "$NEWDOMS" "$NZ" v6b_bf32_newdom_nz nonzero
fi

# ================= ③ 补 v4 跳过的 AWQ-8bit =================
A8=/root/models/Qwen3-VL-32B-Instruct-AWQ-8bit
if [ -f "$A8/config.json" ]; then
  say "=== ⑤ 补 AWQ-8bit 32B 普查（v4 因分片截断跳过；现已修好）==="
  if serve "$A8" qwen3-vl-32b-awq8 /root/logs/v6_awq8bit.log 0.85; then
    run 19e_probe_multi.py qwen3-vl-32b-awq8 "st_a ucf" "$SIX" v6_awq8bit
    run 19e_probe_multi.py qwen3-vl-32b-awq8 "st_a ucf" "$NZ" v6_awq8bit_nz nonzero
    run 19e_probe_multi.py qwen3-vl-32b-awq8 "$NEWDOMS" "$SIX" v6_awq8bit_newdom
  fi
fi

# ================= ④ 新模型 =================
add_model() {  # $1 dir $2 name $3 log $4 util $5 mmflag(1/0) $6.. extra
  local D=$1 N=$2 LG=$3 U=$4 MMARG=$5; shift 5
  [ -d "$D" ] || { say "  （跳过 $N：目录不存在）"; return 1; }
  [ -f "$D/config.json" ] || { say "  （跳过 $N：权重不完整）"; return 1; }
  say "=== $N 普查 ==="
  MM=$MMARG serve "$D" "$N" "$LG" "$U" "$@" || return 1
  run 19e_probe_multi.py "$N" "st_a ucf" "$SIX" "v6_$N"
  run 19e_probe_multi.py "$N" "$NEWDOMS" "$SIX" "v6_${N}_newdom"
  run 19e_probe_multi.py "$N" "st_a ucf" "$NZ" "v6_${N}_nz" nonzero
}

add_model /root/models/Qwen3-VL-4B-Instruct qwen3-vl-4b /root/logs/v6_4b.log 0.75 1
add_model /root/models/Qwen3-VL-2B-Instruct qwen3-vl-2b /root/logs/v6_2b.log 0.75 1
add_model /root/models/Qwen3-VL-30B-A3B-Instruct-FP8 qwen3-vl-30b-a3b-fp8 /root/logs/v6_30b.log 0.85 1
add_model /root/models/InternVL3_5-38B-FP8-Dynamic internvl35-38b-fp8 /root/logs/v6_ivl35.log 0.85 0 --trust-remote-code

read FT FU <<< "$(usage_of /root/e1_results)"
read NT NU <<< "$(usage_of /root/e1_results_nonzero)"
say "########## v6 结束 $(date +%H:%M:%S) ##########"
say "  零池：总行数 $FT，去重 item $FU"
say "  非零池：总行数 $NT，去重 item $NU"
say "--- 各模型标签文件数 ---"
ls /root/e1_results/ 2>/dev/null | sed 's/^e1_//; s/_st_[ab]_.*//; s/_ucf_.*//; s/_visdrone_.*//; s/_aitod_.*//; s/_countbench_.*//' | sort | uniq -c | tee -a "$L"
echo EXP_V6_DONE >> "$L"
