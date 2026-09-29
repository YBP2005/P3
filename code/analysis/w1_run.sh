#!/bin/bash
# w1_run.sh — W1 独立家族前瞻验证：**主面板驱动**（单卡串行：逐家族起服 → smoke 门 → 跑格 → 停服）
#
# 冻结判据：analysis/work/w1_prereg.json  md5 75eeca6fa68c9be65c2b569d4237d8df（2026-09-23 08:35:05）
#   本脚本**只执行、不判定**；判定由本地 w1_judge.py 按冻结口径做。
# 仪器：/root/19f_probe_ablation.py（md5 28e82b20a7f4，提示词/解析器逐字复用 19e）——**不改探针**。
#
# ★ 启动前修掉的三个 bug（写在这里，避免下一个人再踩）：
#   ① smoke 门原用 awk 数 `$5==1` 当 parse_ok——但 CSV 是 `item,gt,pred,parse_ok,raw,latency_s`，
#      parse_ok 是**第 4 列**；且 raw 字段含逗号/换行，awk 拆列必然错。改为用 csv 模块解析。
#   ② 等待权重就绪的条件会被"下到一半"的目录骗过（config.json 早就在）。改为以下载日志里
#      "→ <model_id> 成功 N 失败 0" 为准。
#   ③ 下载家族跑完不删盘 ⇒ 四个家族 68 GB 会撑爆 55 GB 余量。改为**该家族面板跑完后**才删权重，
#      并记日志（中断则不删，保证断点续跑不必重下）。
set -u
export BAILIAN_API=http://127.0.0.1:8000/v1/chat/completions
export DASHSCOPE_API_KEY=dummy
export VLLM_USE_FLASHINFER_SAMPLER=0
PY=/usr/local/miniconda3/bin/python
VLLM=/usr/local/miniconda3/bin/vllm
L=/root/logs/w1_run.log
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

serve_up() {           # serve_up <served_name> <path> <tag> [extra vllm args...]
  local N=$1 MP=$2 TAG=$3; shift 3
  gpu_clear || return 1
  setsid nohup $VLLM serve "$MP" --served-model-name "$N" --max-model-len 4096 \
    --limit-mm-per-prompt '{"image": 1}' --gpu-memory-utilization 0.85 --max-num-seqs 16 --port 8000 \
    "$@" </dev/null > "/root/logs/serve_w1_${TAG}.log" 2>&1 &
  for i in $(seq 1 60); do
    sleep 15
    curl -sf -m 5 -o /dev/null http://127.0.0.1:8000/v1/models && { say "  [$TAG] 起服就绪 $((i*15))s"; return 0; }
    grep -qiE "Engine core initialization failed|Traceback|is not supported|No module named" \
      "/root/logs/serve_w1_${TAG}.log" 2>/dev/null && \
      { say "  [$TAG] !! 起服报错（早停）"; tail -4 "/root/logs/serve_w1_${TAG}.log" | sed 's/^/      /' >> "$L"; return 1; }
  done
  say "  [$TAG] !! 起服超时"; tail -6 "/root/logs/serve_w1_${TAG}.log" | sed 's/^/      /' >> "$L"; return 1
}

# smoke 门：每家族 2 域各 2 条，只用 base 臂；**禁止**改提示词/换措辞（只允许因服务错误重试）
smoke_gate() {
  local N=$1 TAG=$2
  rm -f "$R/smoke/e1_${N}_st_a_base_native.csv" "$R/smoke/e1_${N}_visdrone_base_native.csv"
  $PY /root/19f_probe_ablation.py --model "$N" --arms base --ds st_a     --n 2 --outdir "$R/smoke" --workers 2 >> "$L" 2>&1
  $PY /root/19f_probe_ablation.py --model "$N" --arms base --ds visdrone --n 2 --outdir "$R/smoke" --workers 2 >> "$L" 2>&1
  local ok
  ok=$($PY /root/w1_smoke_count.py "$R/smoke/e1_${N}_st_a_base_native.csv" "$R/smoke/e1_${N}_visdrone_base_native.csv" 2>/dev/null | tail -1)
  say "  [$TAG] smoke：可解析 ${ok:-0} / 4 条"
  [ "${ok:-0}" -ge 1 ] && return 0 || return 1
}

run_panel() {
  local N=$1 TAG=$2
  for ds in st_a ucf visdrone aitod; do
    say "  [$TAG] $ds 零池 base,permit,channel（native）"
    $PY /root/19f_probe_ablation.py --model "$N" --arms base,permit,channel \
        --ds "$ds" --n 150 --pool zero --outdir "$R/zero" --workers 8 >> "$L" 2>&1
    say "  [$TAG] $ds 零池 base@s640（分辨率旋钮臂）"
    $PY /root/19f_probe_ablation.py --model "$N" --arms base \
        --ds "$ds" --n 150 --pool zero --imgsz 640 --outdir "$R/zero" --workers 8 >> "$L" 2>&1
    say "  [$TAG] $ds 非零池 base,permit,channel"
    $PY /root/19f_probe_ablation.py --model "$N" --arms base,permit,channel \
        --ds "$ds" --n 150 --pool nonzero --outdir "$R/nonzero" --workers 8 >> "$L" 2>&1
  done
  local nz ny
  nz=$(ls "$R"/zero/e1_${N}_* 2>/dev/null | wc -l); ny=$(ls "$R"/nonzero/e1_${N}_* 2>/dev/null | wc -l)
  say "  [$TAG] 面板完成：零池 $nz 个文件 / 非零池 $ny 个文件（期望 16 / 12）"
  [ "$nz" -ge 16 ] && [ "$ny" -ge 12 ]
}

run_family() {         # run_family <served_name> <path> <tag> <delete_weights:0|1> [extra args...]
  local N=$1 MP=$2 TAG=$3 DEL=$4; shift 4
  [ -d "$MP" ] || { say "跳过 $TAG：路径不存在 $MP"; return 1; }
  say "===== 家族 $TAG（$N）====="
  if ! serve_up "$N" "$MP" "$TAG" "$@"; then
    say "!! $TAG 起服失败（vLLM 0.29 载入不了该架构）⇒ 排除并记入 frame 表"; gpu_clear; return 1
  fi
  if ! smoke_gate "$N" "$TAG"; then
    say "!! $TAG 未过 smoke 门（base 臂产不出可解析 JSON）⇒ 排除；不调提示词、不改判据"; gpu_clear; return 1
  fi
  if run_panel "$N" "$TAG"; then
    gpu_clear
    if [ "$DEL" = "1" ]; then
      say "  释放磁盘：删除已跑完的下载权重 $MP"
      rm -rf "$MP"; df -h / | tail -1 >> "$L"
    fi
    return 0
  fi
  say "!! $TAG 面板未跑满（可能有格缺）；**保留权重**以便续跑"
  gpu_clear; return 1
}

wait_ready() {         # wait_ready <model_id> <path> —— 以下载日志的"成功"行为准
  local MID=$1 MP=$2 i sz
  for i in $(seq 1 150); do
    if grep -q "→ $MID 成功" /root/logs/w1_dl.log 2>/dev/null; then return 0; fi
    sleep 120
  done
  sz=$(du -sm "$MP" 2>/dev/null | cut -f1); say "等待超时：$MID（当前 ${sz:-0} MB）"; return 1
}

say "########## W1 主面板开始 ##########"
say "冻结判据 md5 75eeca6fa68c9be65c2b569d4237d8df；仪器 19f md5 28e82b20a7f4；本脚本不判定"
df -h / | tail -1 >> "$L"
CM=/model/ModelScope

# ① 本地镜像三家族（零下载先跑；载入失败即按 frame 表规则排除）
run_family MiniCPM-V-2_6  $CM/OpenBMB/MiniCPM-V-2_6    minicpmv26 0 --trust-remote-code
run_family Step3-VL-10B   $CM/stepfun-ai/Step3-VL-10B  step3vl10b 0
run_family gemma-4-31b-it $CM/google/gemma-4-31B-it    gemma4_31b 0
# gemma-4-31B（59.7 GB）若 bf16 起不来，按已实测可用的 W8A16 量化再试一次，并在服务名加 -int8 标注
if [ ! -f "$R/zero/e1_gemma-4-31b-it_st_a_base_native.csv" ]; then
  say "== gemma-4-31B bf16 未成功，改用 int8_per_channel_weight_only（W8A16，本机已实测可用）=="
  run_family gemma-4-31b-it-int8 $CM/google/gemma-4-31B-it gemma4_31b_int8 0 --quantization int8_per_channel_weight_only
fi

# ② 下载四家族：先等权重、跑完再删盘（Phi-4 仅在前六个家族不足时启用）
run_dl() {  # run_dl <model_id> <path> <served_name> <tag>
  wait_ready "$1" "$2" || return 0
  run_family "$3" "$2" "$4" 1
}
run_dl deepseek-ai/deepseek-vl2-tiny      /root/w1_models/deepseek-vl2-tiny dsvl2-tiny         dsvl2_tiny
run_dl HuggingFaceM4/Idefics3-8B-Llama3   /root/w1_models/idefics3-8b      Idefics3-8B-Llama3 idefics3_8b
run_dl allenai/Molmo-7B-D-0924            /root/w1_models/molmo-7b-d       Molmo-7B-D-0924    molmo7b

done_n=$(grep -c "面板完成" "$L" 2>/dev/null || echo 0)
if [ "${done_n:-0}" -lt 6 ]; then
  say "已完成家族 $done_n < 6 ⇒ 启用备选 Phi-4-multimodal（Microsoft）"
  run_dl microsoft/Phi-4-multimodal-instruct /root/w1_models/phi4-mm Phi-4-mm phi4mm
else
  say "已完成 $done_n 个家族 ⇒ 备选 Phi-4 不需要"
fi

say "########## W1 主面板结束 ##########"
say "零池 $(ls $R/zero | wc -l) 个；非零池 $(ls $R/nonzero | wc -l) 个；smoke $(ls $R/smoke | wc -l) 个"
df -h / | tail -1 >> "$L"
echo "W1_PANEL_DONE" >> "$L"
