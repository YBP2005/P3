#!/bin/bash
# A5 追加实验（第四批）：**构建轴**的强回退链 —— 目标是"同一新家族、换构建，密集域答 0 是否出现"。
# 已有事实：Gemma-3-12B BF16 密集域答 0 = 0.000（A5 主跑）；在线 FP8 在 A800(sm_80) 上引擎起不来。
# 本批依次尝试（谁能起来就用谁，起不来就如实记"未取到"）：
#   ① bitsandbytes NF4 4bit（先 pip 安装）
#   ② --quantization int8_per_channel_weight_only（Ampere 上的 W8A16 在线权重量化）
#   ③ --quantization fp8_per_channel
# 每个成功构建都跑 st_a / ucf / visdrone 零池 3 臂，落在 /root/e1_results_build。
set -u
export BAILIAN_API=http://127.0.0.1:8000/v1/chat/completions
export DASHSCOPE_API_KEY=dummy
export VLLM_USE_FLASHINFER_SAMPLER=0
PY=/usr/local/miniconda3/bin/python
VLLM=/usr/local/miniconda3/bin/vllm
GMP=/model/ModelScope/LLM-Research/gemma-3-12b-it
L=/root/logs/a5_extra4.log
mkdir -p /root/logs /root/e1_results_build
say() { echo "[$(date +%H:%M:%S)] $*" >> "$L"; }

say "########## A5 追加实验（第四批：构建轴）开始（先等第三批）##########"
for i in $(seq 1 160); do
  if grep -q A5_EXTRA3_DONE /root/logs/a5_extra3.log 2>/dev/null; then say "  第三批已完成"; break; fi
  sleep 30
done
grep -q A5_EXTRA3_DONE /root/logs/a5_extra3.log 2>/dev/null || say "  !! 等第三批超时，仍继续"

gpu_clear() {
  pkill -9 -i -f vllm 2>/dev/null; pkill -9 -f resource_tracker 2>/dev/null; sleep 3
  for i in $(seq 1 40); do
    used=$(nvidia-smi --query-gpu=memory.used --format=csv,noheader | tr -d ' MiB')
    [ "$used" -lt 500 ] && return 0; sleep 3
  done
  say "  !! 显存未清空：${used} MiB"; return 1
}

# try_build <tag> <served-name> [vllm args...]  成功返回 0 并保持服务在跑
try_build() {
  local TAG=$1 N=$2; shift 2
  gpu_clear || return 1
  setsid nohup $VLLM serve "$GMP" --served-model-name "$N" --max-model-len 8192 \
    --limit-mm-per-prompt '{"image": 1}' --gpu-memory-utilization 0.85 --max-num-seqs 24 --port 8000 \
    "$@" </dev/null > "/root/logs/serve_${TAG}.log" 2>&1 &
  for i in $(seq 1 24); do
    sleep 15
    curl -sf -m 5 -o /dev/null http://127.0.0.1:8000/v1/models && { say "  [$TAG] 起服就绪（$((i*15))s）"; return 0; }
  done
  say "  [$TAG] 起服失败，日志尾："; tail -4 "/root/logs/serve_${TAG}.log" | cut -c1-150 | sed 's/^/      /' >> "$L"
  pkill -9 -i -f vllm 2>/dev/null
  return 1
}

run_build() {  # run_build <served-name> <variant-label>
  local N=$1 V=$2
  for ds in st_a ucf visdrone; do
    say "  [$V/$ds] 零池 3 臂"
    t0=$(date +%s)
    $PY /root/19f_probe_ablation.py --model "$N" --arms base,permit,channel \
        --ds "$ds" --n 150 --workers 8 --pool zero --outdir /root/e1_results_build >> "$L" 2>&1
    say "     rc=$? 用时 $(( $(date +%s) - t0 ))s"
    for f in /root/e1_results_build/*_native.csv; do
      [ -e "$f" ] && mv "$f" "${f%_native.csv}_${V}.csv"
    done
  done
}

USED=""
# ① bitsandbytes NF4
say "---- 尝试 ① bitsandbytes NF4 4bit ----"
$PY -m pip install -q bitsandbytes >> "$L" 2>&1 && say "  bitsandbytes 安装完成" || say "  bitsandbytes 安装失败"
if try_build extra4_bnb gemma3-12b-nf4 --quantization bitsandbytes --load-format bitsandbytes; then
  USED=nf4; run_build gemma3-12b-nf4 nf4
fi
# ② int8 weight-only
if [ -z "$USED" ]; then
  say "---- 尝试 ② int8_per_channel_weight_only ----"
  if try_build extra4_i8 gemma3-12b-int8 --quantization int8_per_channel_weight_only; then
    USED=int8; run_build gemma3-12b-int8 int8
  fi
fi
# ③ fp8_per_channel
if [ -z "$USED" ]; then
  say "---- 尝试 ③ fp8_per_channel ----"
  if try_build extra4_fp8c gemma3-12b-fp8c --quantization fp8_per_channel; then
    USED=fp8c; run_build gemma3-12b-fp8c fp8c
  fi
fi

say "构建轴实际取到：${USED:-（未取到，需如实记为局限）}"
say "build 目录文件数：$(ls /root/e1_results_build 2>/dev/null | wc -l)"
say "########## A5 追加实验（第四批）结束 ##########"
echo "A5_EXTRA4_DONE" >> "$L"
