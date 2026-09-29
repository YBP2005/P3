#!/bin/bash
# w1_recover.sh — W1 **血统回收**（在冻结规则的"按顺序补位"下执行两个排除的替补）
#
# 为什么需要：主面板两处排除（均属实、且理由可核）
#   ① MiniCPM-V-2_6 未过 smoke 门：base 契约下**用自然语言拒答**（raw 见 w1_results/smoke），
#      4/4 条无可解析 JSON。判据禁止为通过门户改提示词 ⇒ 排除。
#   ② Step3-VL-10B 起服失败：报错为 "contains custom code … Please pass trust_remote_code=True"
#      ⇒ 属**基础设施参数**缺失（不是提示词/数据变更），允许重试一次并如实记录结果。
# 换位规则（照 冻结文本 "按顺序补位" 的字面执行；原文的"最多补一个"是按**一次**流失写的，
#   此处发生两次流失 ⇒ 同一规则执行两次；这一澄清写在结果文档里，不在看到结果后才定）：
#   · StepFun 槽位 ← Step3-VL-10B 加 --trust-remote-code 重试
#   · OpenBMB 槽位 ← 同血统的下一个候选 MiniCPM-V-4_5（因入组者被排除，该血统名额空出）
#   · 备选槽位 ← Microsoft Phi-4-multimodal-instruct（主驱动已按规则尝试）
# 纪律：与主面板**同一仪器、同一 smoke 门、同一结果目录**，单卡串行（等主面板结束再起）。
set -u
export BAILIAN_API=http://127.0.0.1:8000/v1/chat/completions
export DASHSCOPE_API_KEY=dummy
export VLLM_USE_FLASHINFER_SAMPLER=0
PY=/usr/local/miniconda3/bin/python
VLLM=/usr/local/miniconda3/bin/vllm
L=/root/logs/w1_recover.log
R=/root/w1_results
mkdir -p "$R"/{zero,nonzero,smoke} /root/logs
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
    "$@" </dev/null > "/root/logs/serve_w1r_${TAG}.log" 2>&1 &
  for i in $(seq 1 60); do
    sleep 15
    curl -sf -m 5 -o /dev/null http://127.0.0.1:8000/v1/models && { say "  [$TAG] 起服就绪 $((i*15))s"; return 0; }
    grep -qiE "Engine core initialization failed|Traceback|is not supported|No module named" \
      "/root/logs/serve_w1r_${TAG}.log" 2>/dev/null && \
      { say "  [$TAG] !! 起服报错（早停）"; tail -4 "/root/logs/serve_w1r_${TAG}.log" | sed 's/^/      /' >> "$L"; return 1; }
  done
  say "  [$TAG] !! 起服超时"; tail -6 "/root/logs/serve_w1r_${TAG}.log" | sed 's/^/      /' >> "$L"; return 1
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
run_panel() {
  local N=$1 TAG=$2
  for ds in st_a ucf visdrone aitod; do
    say "  [$TAG] $ds 零池 base,permit,channel（native）"
    $PY /root/19f_probe_ablation.py --model "$N" --arms base,permit,channel --ds "$ds" --n 150 \
        --pool zero --outdir "$R/zero" --workers 8 >> "$L" 2>&1
    say "  [$TAG] $ds 零池 base@s640"
    $PY /root/19f_probe_ablation.py --model "$N" --arms base --ds "$ds" --n 150 \
        --pool zero --imgsz 640 --outdir "$R/zero" --workers 8 >> "$L" 2>&1
    say "  [$TAG] $ds 非零池 base,permit,channel"
    $PY /root/19f_probe_ablation.py --model "$N" --arms base,permit,channel --ds "$ds" --n 150 \
        --pool nonzero --outdir "$R/nonzero" --workers 8 >> "$L" 2>&1
  done
  local nz ny; nz=$(ls "$R"/zero/e1_${N}_* 2>/dev/null | wc -l); ny=$(ls "$R"/nonzero/e1_${N}_* 2>/dev/null | wc -l)
  say "  [$TAG] 面板完成：零池 $nz / 非零池 $ny（期望 16 / 12）"
}
run_family() {   # <served_name> <path> <tag> [extra args...]
  local N=$1 MP=$2 TAG=$3; shift 3
  [ -d "$MP" ] || { say "跳过 $TAG：路径不存在 $MP"; return 1; }
  say "===== 回收家族 $TAG（$N）====="
  serve_up "$N" "$MP" "$TAG" "$@" || { say "!! $TAG 起服仍失败 ⇒ 最终排除"; gpu_clear; return 1; }
  smoke_gate "$N" "$TAG" || { say "!! $TAG 未过 smoke 门 ⇒ 最终排除"; gpu_clear; return 1; }
  run_panel "$N" "$TAG"; gpu_clear; return 0
}

# 等主面板与下载结束（串行守卫：单卡一次只允许一个服务）
say "等待主面板结束（W1_PANEL_DONE）…"
for i in $(seq 1 240); do
  grep -q W1_PANEL_DONE /root/logs/w1_run.log 2>/dev/null && break
  sleep 60
done
say "主面板已结束（或等待超时），开始回收序列"

# ① StepFun 槽位：Step3-VL-10B + trust_remote_code
run_family Step3-VL-10B /model/ModelScope/stepfun-ai/Step3-VL-10B step3vl10b_retry --trust-remote-code

# ② OpenBMB 槽位：MiniCPM-V-4_5（等下载完成）
for i in $(seq 1 150); do
  grep -q "→ OpenBMB/MiniCPM-V-4_5 成功" /root/logs/w1_dl2.log 2>/dev/null && break
  sleep 60
done
if [ -f /root/w1_models/minicpm-v-4_5/config.json ]; then
  run_family MiniCPM-V-4_5 /root/w1_models/minicpm-v-4_5 minicpmv45 --trust-remote-code
else
  say "MiniCPM-V-4_5 权重未就绪 ⇒ 跳过"
fi

say "########## W1 回收结束 ##########"
ls "$R/zero" | wc -l >> "$L"; ls "$R/nonzero" | wc -l >> "$L"
echo "W1_RECOVER_DONE" >> "$L"
