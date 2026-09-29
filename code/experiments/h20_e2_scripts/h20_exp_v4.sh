#!/bin/bash
# 剩余实验 v4（合并 v2/v3 的内容，修掉三处缺陷）：
#   · FP8 32B  —— 之前因缺 g++（cc1plus）失败；现已安装 g++
#   · GPTQ-W4 32B
#   · AWQ-8bit 32B（先重下一次，之前被两个并发下载实例互相破坏）
#   · InternVL2.5-8B-AWQ —— 之前整组失败：它不接受 --mm-processor-kwargs 的 max_pixels，
#                           死在图像处理器构造函数里 ⇒ 本脚本对它**不传 mm-processor-kwargs**
#   · Qwen2.5-VL-72B-AWQ（等 dl_extra3 下完）
# 产出检查用「总行数 + 去重 item 数」双判据（不要数文件个数）。
set -u
export VLLM_USE_FLASHINFER_SAMPLER=0
export BAILIAN_API=http://127.0.0.1:8000/v1/chat/completions
export DASHSCOPE_API_KEY=dummy
PY=/root/vllm312/bin/python
VLLM=/root/vllm312/bin/vllm
L=/root/logs/exp_v4.log
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

serve() {  # $1 model $2 name $3 log $4 util ; 环境变量 MM=0 时不传 mm-processor-kwargs
  local M=$1 N=$2 LG=$3 U=$4; shift 4
  local MMARG="${MM:-1}"
  [ -d "$M" ] || { say "  !! 模型目录不存在: $M"; return 1; }
  for attempt in 1 2; do
    pkill -9 -f 'vllm serve' 2>/dev/null; sleep 5; gpu_clear; sleep 5
    local EXTRA=""
    [ "$attempt" = "2" ] && EXTRA="--attention-backend FLASH_ATTN"
    if [ "$MMARG" = "1" ]; then
      say "  起服务 $N（尝试$attempt，mm-kwargs=有）"
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
    say "    尝试$attempt 失败，日志尾："; tail -6 "$LG" | sed 's/^/        /' | tee -a "$L"
  done
  say "  !! $N 两次尝试都起不来"
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
      say "      !! 两项都未增长，探针日志尾："
      tail -6 "/root/logs/probe_${TAG}_${d}.log" | sed 's/^/          /' | tee -a "$L"
    fi
  done
}

ALL=base,permit,bestA,bestB,bestC,channel
NZ=base,permit,channel

say "########## v4 开始 $(date +%H:%M:%S) ##########"

# ========== ① FP8（官方，g++ 已装）==========
if [ -f /root/models/Qwen3-VL-32B-Instruct-FP8/config.json ]; then
  say "=== FP8 32B ==="
  if serve /root/models/Qwen3-VL-32B-Instruct-FP8 qwen3-vl-32b-fp8 /root/logs/v_fp8.log 0.85; then
    run 19b_e1_probe.py qwen3-vl-32b-fp8 "st_a ucf" $ALL fp8
    run 19d_probe_nonzero.py qwen3-vl-32b-fp8 "st_a ucf" $NZ fp8nz
    run 19c_probe_paraphrase.py qwen3-vl-32b-fp8 "st_a ucf" permitB,permitC,channelB fp8para
  fi
fi

# ========== ② GPTQ-W4 ==========
if [ -f /root/models/Qwen3-VL-32B-Instruct-GPTQ-W4/config.json ]; then
  say "=== GPTQ-W4 32B ==="
  if serve /root/models/Qwen3-VL-32B-Instruct-GPTQ-W4 qwen3-vl-32b-gptq /root/logs/v_gptq.log 0.75; then
    run 19b_e1_probe.py qwen3-vl-32b-gptq "st_a ucf" $ALL gptq
    run 19d_probe_nonzero.py qwen3-vl-32b-gptq "st_a ucf" $NZ gptqnz
  fi
fi

# ========== ③ AWQ-8bit（先重下一次）==========
A8=/root/models/Qwen3-VL-32B-Instruct-AWQ-8bit
if [ ! -f "$A8/config.json" ]; then
  say "=== 重下 AWQ-8bit（之前被并发下载破坏，已删除）==="
  $PY -u /root/h20_dl_model.py cyankiwi/Qwen3-VL-32B-Instruct-AWQ-8bit "$A8" >> "$L" 2>&1
  say "  下载结束：$(du -sh "$A8" 2>/dev/null | cut -f1)"
fi
if [ -f "$A8/config.json" ]; then
  say "=== AWQ-8bit 32B ==="
  if serve "$A8" qwen3-vl-32b-awq8 /root/logs/v_awq8bit.log 0.85; then
    run 19b_e1_probe.py qwen3-vl-32b-awq8 "st_a ucf" $ALL awq8bit
    run 19d_probe_nonzero.py qwen3-vl-32b-awq8 "st_a ucf" $NZ awq8bitnz
  fi
fi

# ========== ④ InternVL 重跑（不传 mm-processor-kwargs）==========
IVL=/root/models/InternVL2_5-8B-AWQ
if [ -d "$IVL" ]; then
  say "=== InternVL2.5-8B-AWQ 重跑（修正图像处理器参数）==="
  MM=0 serve "$IVL" internvl25-8b-awq /root/logs/v_ivl.log 0.75 --trust-remote-code \
    && { run 19b_e1_probe.py internvl25-8b-awq "st_a ucf" $ALL ivl
         run 19d_probe_nonzero.py internvl25-8b-awq "st_a ucf st_b" $NZ ivlnz; }
fi

# ========== ⑤ Qwen2.5-VL-72B-AWQ（等下载）==========
M72=/root/models/Qwen2.5-VL-72B-Instruct-AWQ
say "=== 等 72B 权重（最多 90 分钟）==="
for i in $(seq 1 90); do
  [ -f "$M72/config.json" ] && break
  sleep 60
done
if [ -f "$M72/config.json" ]; then
  say "=== Qwen2.5-VL-72B-AWQ（规模检验；代际+规模混合变量）==="
  if serve "$M72" qwen25vl-72b-awq /root/logs/v_72b.log 0.90; then
    run 19b_e1_probe.py qwen25vl-72b-awq "st_a ucf" $ALL q25vl72b
    run 19d_probe_nonzero.py qwen25vl-72b-awq "st_a ucf" $NZ q25vl72bnz
    run 19c_probe_paraphrase.py qwen25vl-72b-awq "st_a ucf" permitB,permitC,channelB q25vl72bpara
  fi
else
  say "!! 72B 权重超时未就绪，跳过"
fi

read FT FU <<< "$(usage_of /root/e1_results)"
read NT NU <<< "$(usage_of /root/e1_results_nonzero)"
say "########## v4 结束 $(date +%H:%M:%S) ##########"
say "  零池：总行数 $FT，去重 item $FU"
say "  非零池：总行数 $NT，去重 item $NU"
echo EXP_V4_DONE >> "$L"
