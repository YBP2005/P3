#!/bin/bash
# w1_recover2.sh — W1 第三段：**环境修复后的重试**（deepseek-vl2-tiny 等）
#
# 根因（实测自 serve 日志，非猜测）：
#   deepseek-vl2-tiny 起服失败 = `ModuleNotFoundError: No module named 'timm'`
#     ⇒ 纯环境缺包；vLLM 注册表里**有** `DeepseekVLV2ForCausalLM`。装包后重试属基础设施修复，
#       不改提示词、不改判据（与 trust_remote_code 同类）。
#   同时确认 vLLM 0.29 支持：StepVLForConditionalGeneration / MiniCPMV / Idefics3ForConditionalGeneration
#     / MolmoForCausalLM / Phi4MMForCausalLM —— 即其余失败都不是"模型不被支持"。
#
# 本段做三件事：① 装 timm；② deepseek-vl2-tiny 补跑（smoke 门 → 普查面板 → FSC 示例臂）；
#   ③ 若 Phi-4-mm 的普查格缺失则同样补跑。全部等 FSC 段结束后再起（单卡串行）。
set -u
export BAILIAN_API=http://127.0.0.1:8000/v1/chat/completions
export DASHSCOPE_API_KEY=dummy
export VLLM_USE_FLASHINFER_SAMPLER=0
PY=/usr/local/miniconda3/bin/python
VLLM=/usr/local/miniconda3/bin/vllm
L=/root/logs/w1_recover2.log
R=/root/w1_results
mkdir -p "$R"/{zero,nonzero,smoke,fsc} /root/logs
say() { echo "[$(date +%H:%M:%S)] $*" | tee -a "$L"; }

say "########## ① 安装 timm（deepseek-vl2 缺的包）##########"
$PY -m pip install -q timm >> "$L" 2>&1
say "timm 版本：$($PY -c 'import timm;print(timm.__version__)' 2>&1 | tail -1)"

gpu_clear() {
  pkill -9 -i -f vllm 2>/dev/null; pkill -9 -f resource_tracker 2>/dev/null; sleep 3
  for i in $(seq 1 40); do
    used=$(nvidia-smi --query-gpu=memory.used --format=csv,noheader | tr -d ' MiB')
    [ "$used" -lt 500 ] && return 0; sleep 3
  done
  say "  !! 显存未清空：${used} MiB"; return 1
}
serve_up() {
  local N=$1 MP=$2 TAG=$3; shift 3
  gpu_clear || return 1
  setsid nohup $VLLM serve "$MP" --served-model-name "$N" --max-model-len 4096 \
    --limit-mm-per-prompt '{"image": 1}' --gpu-memory-utilization 0.85 --max-num-seqs 16 --port 8000 \
    "$@" </dev/null > "/root/logs/serve_w1r2_${TAG}.log" 2>&1 &
  for i in $(seq 1 60); do
    sleep 15
    curl -sf -m 5 -o /dev/null http://127.0.0.1:8000/v1/models && { say "  [$TAG] 起服就绪 $((i*15))s"; return 0; }
    grep -qiE "Engine core initialization failed|Traceback|is not supported" \
      "/root/logs/serve_w1r2_${TAG}.log" 2>/dev/null && \
      { say "  [$TAG] !! 起服报错（早停）"; grep -E "ERROR|Error" "/root/logs/serve_w1r2_${TAG}.log" | tail -3 | sed 's/^/      /' >> "$L"; return 1; }
  done
  say "  [$TAG] !! 起服超时"; return 1
}
smoke_gate() {
  local N=$1 TAG=$2
  rm -f "$R/smoke/e1_${N}_st_a_base_native.csv" "$R/smoke/e1_${N}_visdrone_base_native.csv"
  $PY /root/19f_probe_ablation.py --model "$N" --arms base --ds st_a     --n 2 --outdir "$R/smoke" --workers 2 >> "$L" 2>&1
  $PY /root/19f_probe_ablation.py --model "$N" --arms base --ds visdrone --n 2 --outdir "$R/smoke" --workers 2 >> "$L" 2>&1
  local ok; ok=$($PY /root/w1_smoke_count.py "$R/smoke/e1_${N}_st_a_base_native.csv" "$R/smoke/e1_${N}_visdrone_base_native.csv" 2>/dev/null | tail -1)
  say "  [$TAG] smoke：可解析 ${ok:-0} / 4 条"
  [ "${ok:-0}" -ge 1 ] && return 0 || return 1
}
run_panel_and_fsc() {
  local N=$1 TAG=$2
  for ds in st_a ucf visdrone aitod; do
    $PY /root/19f_probe_ablation.py --model "$N" --arms base,permit,channel --ds "$ds" --n 150 \
        --pool zero --outdir "$R/zero" --workers 8 >> "$L" 2>&1
    $PY /root/19f_probe_ablation.py --model "$N" --arms base --ds "$ds" --n 150 \
        --pool zero --imgsz 640 --outdir "$R/zero" --workers 8 >> "$L" 2>&1
    $PY /root/19f_probe_ablation.py --model "$N" --arms base,permit,channel --ds "$ds" --n 150 \
        --pool nonzero --outdir "$R/nonzero" --workers 8 >> "$L" 2>&1
    say "    [$TAG] $ds 完成"
  done
  $PY /root/w1_fsc_probe.py --model "$N" --arms base,permit,exemplar3,exemplar3permit --n 300 --workers 8 >> "$L" 2>&1
  say "  [$TAG] 普查 $(ls $R/zero/e1_${N}_* 2>/dev/null | wc -l)/16 + $(ls $R/nonzero/e1_${N}_* 2>/dev/null | wc -l)/12；FSC $(ls $R/fsc/fsc_${N}_* 2>/dev/null | wc -l)/4"
}
run_family() {
  local N=$1 MP=$2 TAG=$3; shift 3
  [ -d "$MP" ] || { say "跳过 $TAG：无权重"; return 1; }
  say "===== 重试家族 $TAG（$N）====="
  serve_up "$N" "$MP" "$TAG" "$@" || { say "!! $TAG 起服仍失败 ⇒ 最终排除（理由写入 frame 表）"; gpu_clear; return 1; }
  smoke_gate "$N" "$TAG" || { say "!! $TAG 未过 smoke 门 ⇒ 最终排除"; gpu_clear; return 1; }
  run_panel_and_fsc "$N" "$TAG"; gpu_clear; return 0
}

say "等待 FSC 段结束（W1_FSC_DONE）…"
for i in $(seq 1 300); do
  grep -q W1_FSC_DONE /root/logs/w1_fsc.log 2>/dev/null && break
  sleep 60
done
say "开始环境修复后的重试"

# deepseek-vl2-tiny：装 timm 后重试（普查 + FSC 一次做完，避免再排一轮）
run_family deepseek-vl2-tiny /root/w1_models/deepseek-vl2-tiny  dsvl2_tiny  --trust-remote-code

# Phi-4-mm：若普查格缺失则补（它由主驱动的备选分支启动，可能因同因失败）
if [ "$(ls $R/zero/e1_Phi-4-mm_* 2>/dev/null | wc -l)" -lt 16 ]; then
  if [ -f /root/w1_models/phi4-mm/config.json ]; then
    say "Phi-4-mm 普查格不足 ⇒ 重试（--trust-remote-code）"
    run_family Phi-4-mm /root/w1_models/phi4-mm phi4mm_retry --trust-remote-code
  else
    say "Phi-4-mm 权重未就绪 ⇒ 跳过"
  fi
else
  say "Phi-4-mm 已跑满 ⇒ 无需重试"
fi

say "########## 重试段结束 ##########"
echo "W1_RECOVER2_DONE" >> "$L"
