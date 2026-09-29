#!/bin/bash
# A5 追加实验（第二批，一次对齐）—— 单卡串行，每阶段先清显存再起服。
#  阶段 A  InternVL3.5-8B：机制臂（enum / enumAbstain / locate，检验"门是 abstain 词位而非枚举要求"）
#                          + 模板变体（system 消息）
#  阶段 B  Phi-3.5-Vision：机制臂
#  阶段 C  LLaVA-OneVision：模板变体（该家族密集域解析率最低，看模板是否解释散文式拒答）
#  阶段 D  Gemma-3-12B **构建轴**：同一权重、换构建（先试在线 FP8，失败退 fp16），
#          看"密集域答 0 是否随构建出现"——这是把"构建特异"从 Qwen 血统拓到新血统的关键一格。
set -u
export BAILIAN_API=http://127.0.0.1:8000/v1/chat/completions
export DASHSCOPE_API_KEY=dummy
export VLLM_USE_FLASHINFER_SAMPLER=0
PY=/usr/local/miniconda3/bin/python
VLLM=/usr/local/miniconda3/bin/vllm
L=/root/logs/a5_extra2.log
mkdir -p /root/logs /root/e1_results /root/e1_results_ablate
say() { echo "[$(date +%H:%M:%S)] $*" >> "$L"; }

gpu_clear() {
  pkill -9 -i -f vllm 2>/dev/null
  pkill -9 -f resource_tracker 2>/dev/null
  sleep 3
  for i in $(seq 1 40); do
    used=$(nvidia-smi --query-gpu=memory.used --format=csv,noheader | tr -d ' MiB')
    [ "$used" -lt 500 ] && return 0
    sleep 3
  done
  say "  !! 显存未清空：${used} MiB"; return 1
}

# serve_up <name> <path> <tag> [extra vllm args...]
serve_up() {
  local N=$1 MP=$2 TAG=$3; shift 3
  gpu_clear || return 1
  setsid nohup $VLLM serve "$MP" --served-model-name "$N" --max-model-len 8192 \
    --limit-mm-per-prompt '{"image": 1}' --gpu-memory-utilization 0.85 --max-num-seqs 24 --port 8000 \
    "$@" </dev/null > "/root/logs/serve_${TAG}.log" 2>&1 &
  for i in $(seq 1 40); do
    sleep 15
    if curl -sf -m 5 -o /dev/null http://127.0.0.1:8000/v1/models; then say "  [$TAG] 起服就绪（$((i*15))s）"; return 0; fi
  done
  say "  [$TAG] !! 起服失败："; tail -6 "/root/logs/serve_${TAG}.log" | sed 's/^/      /' >> "$L"
  return 1
}

mech_arms() {  # mech_arms <name> <tag> <ds...>
  local N=$1 TAG=$2; shift 2
  for ds in "$@"; do
    say "== [$TAG] 机制臂 enum,enumAbstain,locate / $ds =="
    t0=$(date +%s)
    $PY /root/19e_probe_multi.py --model "$N" --arms enum,enumAbstain,locate \
        --ds "$ds" --n 150 --workers 8 --pool zero >> "$L" 2>&1
    say "   rc=$? 用时 $(( $(date +%s) - t0 ))s"
  done
}

sys_variant() {  # sys_variant <name> <tag> <ds...>
  local N=$1 TAG=$2; shift 2
  for ds in "$@"; do
    say "== [$TAG] 模板变体 sys / $ds =="
    t0=$(date +%s)
    $PY /root/19f_probe_ablation.py --model "$N" --arms base,permit,channel \
        --ds "$ds" --n 150 --workers 8 --pool zero \
        --system 'You are a careful visual counting assistant. Follow the requested output format exactly.' \
        --outdir /root/e1_results_ablate >> "$L" 2>&1
    say "   rc=$? 用时 $(( $(date +%s) - t0 ))s"
  done
}

say "########## A5 追加实验（第二批）开始 ##########"

# ---------- 阶段 A：InternVL3.5-8B ----------
say "---- 阶段 A：InternVL3.5-8B ----"
if serve_up InternVL3_5-8B /root/models/InternVL3_5-8B extra2_ivl --trust-remote-code; then
  mech_arms InternVL3_5-8B extra2_ivl st_a ucf visdrone
  sys_variant InternVL3_5-8B extra2_ivl st_a ucf
fi

# ---------- 阶段 B：Phi-3.5-Vision ----------
say "---- 阶段 B：Phi-3.5-Vision ----"
if serve_up Phi-3.5-vision-instruct /root/models/Phi-3.5-vision-instruct extra2_phi --trust-remote-code; then
  mech_arms Phi-3.5-vision-instruct extra2_phi st_a ucf visdrone
fi

# ---------- 阶段 C：LLaVA-OneVision ----------
say "---- 阶段 C：LLaVA-OneVision（模板变体）----"
if serve_up llava-onevision-qwen2-7b-ov /root/models/llava-onevision-qwen2-7b-ov extra2_lov; then
  sys_variant llava-onevision-qwen2-7b-ov extra2_lov st_a ucf
fi

# ---------- 阶段 D：构建轴（Gemma-3-12B，同权重换构建） ----------
say "---- 阶段 D：构建轴（Gemma-3-12B）----"
GMP=/model/ModelScope/LLM-Research/gemma-3-12b-it
BUILD=""
if serve_up gemma3-12b-fp8 "$GMP" extra2_gemma_fp8 --quantization fp8; then
  BUILD=fp8
  for ds in st_a ucf visdrone; do
    say "== [$BUILD] 零池 3 臂 / $ds =="
    t0=$(date +%s)
    $PY /root/19f_probe_ablation.py --model gemma3-12b-fp8 --arms base,permit,channel \
        --ds "$ds" --n 150 --workers 8 --pool zero --outdir /root/e1_results_build \
        --system '' >> "$L" 2>&1
    say "   rc=$? 用时 $(( $(date +%s) - t0 ))s"
  done
  # 把变体名统一标成 fp8（19f 默认写 native/sN，这里事后改名，避免与 bf16 主跑混淆）
  for f in /root/e1_results_build/*_native.csv; do [ -e "$f" ] && mv "$f" "${f%_native.csv}_fp8.csv"; done
elif serve_up gemma3-12b-fp16 "$GMP" extra2_gemma_fp16 --dtype float16; then
  BUILD=fp16
  for ds in st_a ucf visdrone; do
    say "== [$BUILD] 零池 3 臂 / $ds =="
    t0=$(date +%s)
    $PY /root/19f_probe_ablation.py --model gemma3-12b-fp16 --arms base,permit,channel \
        --ds "$ds" --n 150 --workers 8 --pool zero --outdir /root/e1_results_build >> "$L" 2>&1
    say "   rc=$? 用时 $(( $(date +%s) - t0 ))s"
  done
  for f in /root/e1_results_build/*_native.csv; do [ -e "$f" ] && mv "$f" "${f%_native.csv}_fp16.csv"; done
else
  say "  !! 构建轴起服全部失败（fp8 / fp16）"
fi

say "文件清点：主目录 $(ls /root/e1_results | wc -l)、ablate $(ls /root/e1_results_ablate | wc -l)、build $(ls /root/e1_results_build 2>/dev/null | wc -l)"
say "构建轴实际使用的构建：${BUILD:-无}"
say "########## A5 追加实验（第二批）结束 ##########"
echo "A5_EXTRA2_DONE" >> "$L"
