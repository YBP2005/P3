#!/bin/bash
# ea2_run.sh —— **E2**：真零池 × {≥4 构建} × {中/英} × {3 次服务启动} × 三臂。
#
# 对应[external-review]条目 #1（[external-review]，实验充分性 [Δ]，NEW_DATA）：
#   "≥300 张独立核实的混合真零／非零图像，≥4 构建、双语言、3 次服务启动"。
#
# 与 E-A（ea_run.sh）的关系（**可比性纪律**）：
#   · 仪器**同一支**：/root/19f_probe_ablation.py（md5 28e82b20a7f4…，**不改**）；CN 臂走 20a_probe_truezero.py，
#     EN 臂走 20b_probe_lang.py，两者都 importlib 复用同一 P/parse/call_img；
#   · 起服参数**逐字对齐 E3/E-A**（否则与 D0 对照不可比）；
#   · 真零池由 ea_build_z0.py 冻结（UCF-QNRF 头部标注 ⇒ 窗口内零头点 ⇒ gt=0，两层 easy/hard）。
#
# "3 次服务启动"= 每个构建**重启三次**，每次跑完 CN+EN 两语言的全部臂 ⇒ 这才是"服务栈噪声"的对照。
# "双语言"= 同批图上的语义等价英译（20b 的冻结 EN 提示表）。
# "混合真零/非零"= 真零池在本脚本内跑；非零对照直接复用已冻结的 `/root/e1_results`（同一批构建、同一探针）。
set -u
export BAILIAN_API=http://127.0.0.1:8000/v1/chat/completions
export DASHSCOPE_API_KEY=dummy
export VLLM_USE_FLASHINFER_SAMPLER=0
PY=/usr/local/miniconda3/bin/python
VLLM=/usr/local/miniconda3/bin/vllm
L=/root/logs/ea2_run.log
mkdir -p /root/logs
say() { echo "[$(date +%H:%M:%S)] $*" | tee -a "$L"; }

gpu_clear() {
  pkill -9 -i -f vllm 2>/dev/null; pkill -9 -f resource_tracker 2>/dev/null; sleep 3
  for i in $(seq 1 40); do
    used=$(nvidia-smi --query-gpu=memory.used --format=csv,noheader | tr -d ' MiB')
    [ "$used" -lt 500 ] && return 0; sleep 3
  done
  say "  !! 显存未清空：${used} MiB"; return 1
}

serve_up() {   # serve_up <served_name> <path> <tag> [extra...]
  local N=$1 MP=$2 TAG=$3; shift 3
  gpu_clear || return 1
  setsid nohup $VLLM serve "$MP" --served-model-name "$N" --max-model-len 8192 \
    --limit-mm-per-prompt '{"image": 1}' --gpu-memory-utilization 0.85 --max-num-seqs 24 --port 8000 \
    "$@" </dev/null > "/root/logs/serve_ea2_${TAG}.log" 2>&1 &
  for i in $(seq 1 80); do
    sleep 15
    curl -sf -m 5 -o /dev/null http://127.0.0.1:8000/v1/models && { say "  [$TAG] 起服就绪 $((i*15))s"; return 0; }
    grep -qiE "Engine core initialization failed|is not supported|No module named|Value error," \
      "/root/logs/serve_ea2_${TAG}.log" 2>/dev/null && \
      { say "  [$TAG] !! 起服报错（早停）"; tail -4 "/root/logs/serve_ea2_${TAG}.log" | sed 's/^/      /' >> "$L"; return 1; }
  done
  say "  [$TAG] !! 起服超时"; tail -5 "/root/logs/serve_ea2_${TAG}.log" | sed 's/^/      /' >> "$L"; return 1
}

run_lang() {   # run_lang <served_name> <outdir_tag>
  local N=$1 SRV=$2
  for ds in z0easy z0hard; do
    say "    [$SRV] CN $ds × base,permit,channel"
    $PY /root/20a_probe_truezero.py --model "$N" --arms base,permit,channel --ds "$ds" \
        --outdir "/root/z0_results_${SRV}" --workers 8 >> "$L" 2>&1
    say "    [$SRV] EN $ds × base,permit,channel"
    $PY /root/20b_probe_lang.py --model "$N" --pool "$ds" --arms base,permit,channel \
        --outdir "/root/z0_results_en_${SRV}" --workers 8 >> "$L" 2>&1
  done
}

run_build() {  # run_build <served_name> <path> <tag> [extra...]
  local N=$1 MP=$2 TAG=$3; shift 3
  [ -e "$MP" ] || { say "跳过 $TAG：路径不存在 $MP"; return 1; }
  say "===== E2 构建 $TAG（$N）====="
  for s in 1 2 3; do
    if ! serve_up "$N" "$MP" "${TAG}_s${s}" "$@"; then
      say "!! $TAG 第 $s 次起服失败 ⇒ 记入 frame（该构建该次不补）"; gpu_clear; continue
    fi
    run_lang "$N" "${TAG}_s${s}"
    say "  [$TAG] 第 $s 次服务完成"
  done
  gpu_clear && say "  [$TAG] 构建完成"
}

say "########## E2 开始：真零池 × 5 构建 × 双语言 × 3 次服务 ##########"
df -h / | tail -1 >> "$L"

# ① 真零池（若已存在则跳过；构造器是 CPU 脚本，内容由 UCF-QNRF 标注决定，可复算）
if [ ! -f /root/z0/gt_z0.csv ]; then
  say "① 构造真零池 ea_build_z0.py"
  $PY /root/ea_build_z0.py >> "$L" 2>&1 || { say "!! 池构造失败，终止"; exit 1; }
fi
say "① 池就绪：$(wc -l < /root/z0/gt_z0.csv) 行"

# ② 五次服务：小模型先跑（结果先落地），32B 放最后
run_build InternVL3_5-8B            /root/models/InternVL3_5-8B                    ivl8b   --trust-remote-code
run_build Phi-3.5-vision-instruct   /root/models/Phi-3.5-vision-instruct           phi35   --trust-remote-code
run_build llava-onevision-qwen2-7b-ov /root/models/llava-onevision-qwen2-7b-ov     llavaov
run_build gemma3-12b                /model/ModelScope/LLM-Research/gemma-3-12b-it  gemma12b
run_build Qwen3-VL-32B-Instruct     /model/ModelScope/Qwen/Qwen3-VL-32B-Instruct   q32 \
          --max-model-len 4096 --max-num-seqs 8

say "########## E2 完成 ##########"
ls /root/z0_results_* /root/z0_results_en_* 2>/dev/null | wc -l | sed 's/^/  产物文件数：/' >> "$L"
say "E2_PANEL_DONE"
