#!/bin/bash
# w1_fsc_late.sh — 补齐**被删权重家族**的 FSC 示例臂（当前是 idefics3-8b）。
#
# 起因：普查跑完时驱动 `rm -rf` 删掉了 idefics3 的权重（守卫是后加的），FSC 段因此拿不到它。
# 处置：本段在 recover2 之后重下该家族并只跑 FSC 四臂（普查数据已在，无需重跑）。
# 纪律：与其余各段同仪器、同判据、单卡串行。
set -u
export BAILIAN_API=http://127.0.0.1:8000/v1/chat/completions
export DASHSCOPE_API_KEY=dummy
export VLLM_USE_FLASHINFER_SAMPLER=0
PY=/usr/local/miniconda3/bin/python
VLLM=/usr/local/miniconda3/bin/vllm
L=/root/logs/w1_fsc_late.log
R=/root/w1_results
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
    "$@" </dev/null > "/root/logs/serve_w1fl_${TAG}.log" 2>&1 &
  for i in $(seq 1 60); do
    sleep 15
    curl -sf -m 5 -o /dev/null http://127.0.0.1:8000/v1/models && { say "  [$TAG] 起服就绪 $((i*15))s"; return 0; }
  done
  say "  [$TAG] !! 起服超时"; return 1
}

say "等待 recover2 结束（W1_RECOVER2_DONE）…"
for i in $(seq 1 300); do
  grep -q W1_RECOVER2_DONE /root/logs/w1_recover2.log 2>/dev/null && break
  sleep 60
done

# 需要补 FSC 的家族：普查已跑满但 FSC 四臂不全
need_fsc() {   # <served_name>
  local N=$1
  [ "$(ls $R/fsc/fsc_${N}_* 2>/dev/null | wc -l)" -lt 4 ]
}

# ① 重下 idefics3-8b（若权重已不在）
if [ ! -f /root/w1_models/idefics3-8b/config.json ]; then
  say "重下 Idefics3-8B（普查已完成，本次只为 FSC 四臂）"
  $PY /root/w1_dl_model.py HuggingFaceM4/Idefics3-8B-Llama3 /root/w1_models/idefics3-8b >> "$L" 2>&1
fi
if [ -f /root/w1_models/idefics3-8b/config.json ] && need_fsc Idefics3-8B-Llama3; then
  if serve_up Idefics3-8B-Llama3 /root/w1_models/idefics3-8b idefics3_8b; then
    $PY /root/w1_fsc_probe.py --model Idefics3-8B-Llama3 --arms base,permit,exemplar3,exemplar3permit --n 300 --workers 8 >> "$L" 2>&1
    say "Idefics3 FSC 产物 $(ls $R/fsc/fsc_Idefics3-8B-Llama3_* 2>/dev/null | wc -l)/4"
  fi
  gpu_clear
fi

# ② 其它家族：凡普查有数据但 FSC 不足 4 臂、且权重还在的，一并补
for spec in "gemma-4-31b-it:/model/ModelScope/google/gemma-4-31B-it:gemma4_31b:" \
            "MiniCPM-V-4_5:/root/w1_models/minicpm-v-4_5:minicpmv45:--trust-remote-code" \
            "Step3-VL-10B:/model/ModelScope/stepfun-ai/Step3-VL-10B:step3vl10b:--trust-remote-code" \
            "Molmo-7B-D-0924:/root/w1_models/molmo-7b-d:molmo7b:" \
            "deepseek-vl2-tiny:/root/w1_models/deepseek-vl2-tiny:dsvl2_tiny:--trust-remote-code" \
            "Phi-4-mm:/root/w1_models/phi4-mm:phi4mm:--trust-remote-code"; do
  N=${spec%%:*}; rest=${spec#*:}; MP=${rest%%:*}; rest=${rest#*:}; TAG=${rest%%:*}; EXTRA=${rest#*:}
  [ -d "$MP" ] || continue
  need_fsc "$N" || continue
  [ "$(ls $R/zero/e1_${N}_* 2>/dev/null | wc -l)" -ge 16 ] || continue      # 普查没跑满的不在此补
  say "补 FSC：$N"
  if serve_up "$N" "$MP" "$TAG" $EXTRA; then
    $PY /root/w1_fsc_probe.py --model "$N" --arms base,permit,exemplar3,exemplar3permit --n 300 --workers 8 >> "$L" 2>&1
  fi
  gpu_clear
done

say "########## FSC 补齐结束 ##########"
ls $R/fsc | wc -l >> "$L"
echo "W1_FSC_LATE_DONE" >> "$L"
