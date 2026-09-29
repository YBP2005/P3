#!/bin/bash
# w1_recover3.sh — W1 第四段：Molmo-7B-D 的 `trust_remote_code` 重试（普查 + FSC 一次做完）
#
# 根因（实测自 serve 日志）：`The repository ... contains custom code which must be executed ...
#   Please pass the argument trust_remote_code=True` —— 与 Step3-VL-10B 同一类**基础设施参数**缺失，
#   不是模型能力问题（vLLM 注册表里确有 MolmoForCausalLM）。权重已被 w1_guard.sh 保护在
#   /root/w1_keep/molmo-7b-d（软链法，实测 rm -rf 只删链接）。
# 串行：等 FSC 补齐段结束再起；单卡一次只允许一个服务。
set -u
export BAILIAN_API=http://127.0.0.1:8000/v1/chat/completions
export DASHSCOPE_API_KEY=dummy
export VLLM_USE_FLASHINFER_SAMPLER=0
PY=/usr/local/miniconda3/bin/python
VLLM=/usr/local/miniconda3/bin/vllm
L=/root/logs/w1_recover3.log
R=/root/w1_results
mkdir -p "$R"/{zero,nonzero,smoke,fsc} /root/logs
say() { echo "[$(date +%H:%M:%S)] $*" | tee -a "$L"; }
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
    "$@" </dev/null > "/root/logs/serve_w1r3_${TAG}.log" 2>&1 &
  for i in $(seq 1 60); do
    sleep 15
    curl -sf -m 5 -o /dev/null http://127.0.0.1:8000/v1/models && { say "  [$TAG] 起服就绪 $((i*15))s"; return 0; }
    grep -qiE "Engine core initialization failed|Traceback|is not supported" "/root/logs/serve_w1r3_${TAG}.log" 2>/dev/null && \
      { say "  [$TAG] !! 起服报错（早停）"; grep -E "ERROR|Error" "/root/logs/serve_w1r3_${TAG}.log" | tail -3 | sed 's/^/      /' >> "$L"; return 1; }
  done
  say "  [$TAG] !! 起服超时"; return 1
}

say "等待 FSC 补齐段结束（W1_FSC_LATE_DONE）…"
for i in $(seq 1 300); do
  grep -q W1_FSC_LATE_DONE /root/logs/w1_fsc_late.log 2>/dev/null && break
  sleep 60
done
say "开始 Molmo 重试"

MP=/root/w1_models/molmo-7b-d
N=Molmo-7B-D-0924
if [ -d "$MP" ] && serve_up "$N" "$MP" molmo7b_retry --trust-remote-code; then
  rm -f "$R/smoke/e1_${N}_st_a_base_native.csv" "$R/smoke/e1_${N}_visdrone_base_native.csv"
  $PY /root/19f_probe_ablation.py --model "$N" --arms base --ds st_a     --n 2 --outdir "$R/smoke" --workers 2 >> "$L" 2>&1
  $PY /root/19f_probe_ablation.py --model "$N" --arms base --ds visdrone --n 2 --outdir "$R/smoke" --workers 2 >> "$L" 2>&1
  ok=$($PY /root/w1_smoke_count.py "$R/smoke/e1_${N}_st_a_base_native.csv" "$R/smoke/e1_${N}_visdrone_base_native.csv" 2>/dev/null | tail -1)
  say "  smoke：可解析 ${ok:-0} / 4 条"
  if [ "${ok:-0}" -ge 1 ]; then
    for ds in st_a ucf visdrone aitod; do
      $PY /root/19f_probe_ablation.py --model "$N" --arms base,permit,channel --ds "$ds" --n 150 --pool zero --outdir "$R/zero" --workers 8 >> "$L" 2>&1
      $PY /root/19f_probe_ablation.py --model "$N" --arms base --ds "$ds" --n 150 --pool zero --imgsz 640 --outdir "$R/zero" --workers 8 >> "$L" 2>&1
      $PY /root/19f_probe_ablation.py --model "$N" --arms base,permit,channel --ds "$ds" --n 150 --pool nonzero --outdir "$R/nonzero" --workers 8 >> "$L" 2>&1
      say "    [$N] $ds 完成"
    done
    $PY /root/w1_fsc_probe.py --model "$N" --arms base,permit,exemplar3,exemplar3permit --n 300 --workers 8 >> "$L" 2>&1
    say "  [$N] 普查 $(ls $R/zero/e1_${N}_* 2>/dev/null | wc -l)/16 + $(ls $R/nonzero/e1_${N}_* 2>/dev/null | wc -l)/12；FSC $(ls $R/fsc/fsc_${N}_* 2>/dev/null | wc -l)/4"
  else
    say "!! Molmo 未过 smoke 门 ⇒ 最终排除"
  fi
  gpu_clear
else
  say "!! Molmo 起服仍失败 ⇒ 最终排除（理由写入 frame 表）"
fi

say "########## 第四段结束 ##########"
echo "W1_RECOVER3_DONE" >> "$L"
