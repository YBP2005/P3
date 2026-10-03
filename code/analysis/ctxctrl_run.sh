#!/bin/bash
# ctxctrl_run.sh —— **服务栈对照实验（S1）**：`--max-model-len` 4096 vs 8192。
#
# ## 为什么做这一项（[external-review][round]的三家共同要求）
# M.41 的"同分辨率重复"里，12 个可比格中 9 格两批一致到 **≤0.5 pp**，唯一大分歧是
# **Phi-3.5-vision-instruct / `enumAbstain` 的弃权率：12.7%（本批 8192）vs 48.7%（冻结面板 4096）
# = 36.0 pp**。两批其余设置逐字相同（temperature 0、128 输出 token、一图一提示、24 并发、同提示词模块、
# 同 300 张图），差别只有起服上下文长度。[external-review]要求：**复跑 4096/8192 各 3 次，报告均值与极差**，
# 把这 36 pp 归属清楚（是服务配置的属性，还是同配置下的运行噪声）。
#
# ## 设计（对照而非相关）
#   3 构建 × 2 上下文 × **3 次全新起服** × 4 个可比臂 × 300 张冻结样本 = **18 次起服 / 14,400 次调用**
#   构建：Phi-3.5-vision-instruct（分歧所在）、InternVL3_5-8B、gemma3-12b（两个对照）
#   臂  ：base / permit / channel / enumAbstain  ← 与冻结 384 面板**逐字同题**的四臂
#   其它：同 `/root/fsc147`（短边 384 发布件）、同 `sample_test_ids.txt`（md5 d7d30474dc8357e2）、
#         同探针（importlib 自 `/root/19e_probe_multi.py`，md5 03edb14c98ff，零改动）
#   ⇒ 唯一被操纵的变量是 `--max-model-len`；**每次起服都 gpu_clear + 全新进程**，服务级噪声才可估。
#
# ## 顺序（部分结果也要是结论）
#   先 phi35 两个上下文各 1 次（最早的可用答案），再补齐它的第 2/3 次（≥均值/极差），
#   最后两个对照构建。任何时刻中断，已落地的都是**结论本身**而不是半张基线。
#
# ## 纪律
#   冻结件（`/root/fsc_results`、`/root/w1_results/fsc_sc*`、`w1_fsc_probe_384.py`、`19e_probe_multi.py`）
#   **一律不动**；本脚本只写 `/root/w1_results/ctxctrl_*`。每臂文件按行可续跑（已完成的行会跳过），
#   因此重跑本脚本不会重复计费，也不会写坏已有行。
#   起服前先确认 E2/E1 的日志标记在位（避免 pkill 踩掉别人正在用的服务）。
set -u
export BAILIAN_API=http://127.0.0.1:8000/v1/chat/completions
export DASHSCOPE_API_KEY=dummy
export VLLM_USE_FLASHINFER_SAMPLER=0
PY=/usr/local/miniconda3/bin/python
VLLM=/usr/local/miniconda3/bin/vllm
L=/root/logs/ctxctrl_run.log
ARMS=base,permit,channel,enumAbstain
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

# serve_up <served-name> <model-path> <tag> <maxlen> [extra vllm args...]
serve_up() {
  local N=$1 MP=$2 TAG=$3 ML=$4; shift 4
  gpu_clear || return 1
  setsid nohup $VLLM serve "$MP" --served-model-name "$N" --max-model-len "$ML" \
    --limit-mm-per-prompt '{"image": 1}' --gpu-memory-utilization 0.85 --max-num-seqs 24 --port 8000 \
    "$@" </dev/null > "/root/logs/serve_ctxctrl_${TAG}_ml${ML}.log" 2>&1 &
  for i in $(seq 1 80); do
    sleep 15
    curl -sf -m 5 -o /dev/null http://127.0.0.1:8000/v1/models && { say "  [$TAG ml$ML] 起服就绪 $((i*15))s"; return 0; }
    grep -qiE "Engine core initialization failed|is not supported|No module named|Value error," \
      "/root/logs/serve_ctxctrl_${TAG}_ml${ML}.log" 2>/dev/null && { say "  [$TAG ml$ML] !! 起服报错"; return 1; }
  done
  say "  [$TAG ml$ML] !! 起服超时"; return 1
}

# one <served-name> <model-path> <tag> <maxlen> <start-index> [extra]
one() {
  local N=$1 MP=$2 TAG=$3 ML=$4 K=$5; shift 5
  local OUTD=/root/w1_results/ctxctrl_${TAG}_ml${ML}_s${K}
  say "--- ctxctrl $TAG ｜ ctx=$ML ｜ start=$K ｜ $OUTD"
  serve_up "$N" "$MP" "$TAG" "$ML" "$@" || { say "!! $TAG ml$ML 起服失败"; gpu_clear; return 1; }
  $PY /root/ctxctrl_probe.py --model "$N" --arms "$ARMS" --n 300 --workers 8 --outd "$OUTD" >> "$L" 2>&1
  say "  完成：$(ls "$OUTD" 2>/dev/null | wc -l) 个臂文件"
  gpu_clear
}

say "########## S1 服务栈对照：max-model-len 4096 vs 8192 × 3 次全新起服 ##########"
say "① 前置：探针与样本 md5"
md5sum /root/ctxctrl_probe.py /root/19e_probe_multi.py /root/fsc147/sample_test_ids.txt | tee -a "$L"
say "  图像：$(ls /root/fsc147/images 2>/dev/null | wc -l) 张；样本：$(wc -l < /root/fsc147/sample_test_ids.txt) 行"
# 前置守卫：E2/E1 必须已完成（避免 pkill 踩坏别人正在用的服务）
for mk in E2_PANEL_DONE FSC_RES_DONE; do
  grep -q "$mk" /root/logs/*.log 2>/dev/null || say "  !! 未见 $mk 标记（若确有并发任务，请不要跑本脚本）"
done
say "  GPU：$(nvidia-smi --query-gpu=name,memory.used --format=csv,noheader)"

PHI_N=Phi-3.5-vision-instruct ; PHI_P=/root/models/Phi-3.5-vision-instruct
IVL_N=InternVL3_5-8B         ; IVL_P=/root/models/InternVL3_5-8B
GEM_N=gemma3-12b             ; GEM_P=/model/ModelScope/LLM-Research/gemma-3-12b-it

# ② Phi-3.5：两个上下文各 1 次（最早可用答案）
one "$PHI_N" "$PHI_P" phi35 4096 1 --trust-remote-code
one "$PHI_N" "$PHI_P" phi35 8192 1 --trust-remote-code
# ③ Phi-3.5：补齐两次重复（均值/极差要三取）
one "$PHI_N" "$PHI_P" phi35 4096 2 --trust-remote-code
one "$PHI_N" "$PHI_P" phi35 8192 2 --trust-remote-code
one "$PHI_N" "$PHI_P" phi35 4096 3 --trust-remote-code
one "$PHI_N" "$PHI_P" phi35 8192 3 --trust-remote-code
# ④ 两个对照构建（同设计，各自 3 次）
for K in 1 2 3; do
  one "$IVL_N" "$IVL_P" ivl8b 4096 $K --trust-remote-code
  one "$IVL_N" "$IVL_P" ivl8b 8192 $K --trust-remote-code
done
for K in 1 2 3; do
  one "$GEM_N" "$GEM_P" gemma12b 4096 $K
  one "$GEM_N" "$GEM_P" gemma12b 8192 $K
done

say "########## S1 主跑完成，开始汇总 ##########"
$PY /root/ctxctrl_analyze.py >> "$L" 2>&1
say "########## S1 完成 ##########"
say "CTXCTRL_DONE"
