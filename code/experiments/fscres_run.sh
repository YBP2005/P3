#!/bin/bash
# fscres_run.sh —— **E1（三分辨率 × 六臂）**：FSC-147 的分辨率敏感性。
#
# 事实基础（已在 A800 上**逐张**核验，含直接读官方包）：
#   FSC-147 官方发布件 `images_384_VarV2` 的 6146 张图 **短边恒为 384**（占比 100%），
#   **长边在 384–1918 之间随长宽比变化**（本批 300 张样本：长边 384–1229，中位 514，长宽比 1.00–3.20）。
#   ⇒ "384"是**短边约束**（决定线性尺度），不是统一画布。README 的 Drive 链接给的就是这一包（1.53 GB，
#   已逐条目读过尺寸）；第三方镜像同样是这套。**原始分辨率无官方下载点**。
#   ⇒ "另一分辨率"只能在可用方向上做，且必须用**统一直线缩放**（对每张图同一个比例，长宽比逐像素不变）：
#     · 384 px：发布分辨率（短边 384）；本批次用**同一脚本**重测一次，并与冻结面板交叉核对；
#     · 256 px：短边 256 ⇒ scale 0.6667，面积 0.444×（信息只减不增 → 干净的"更低分辨率"点）；
#     · 768 px：短边 768 ⇒ scale 2.0000，面积 4.000×（**同一信息、更大画布**，如实标注 upsampled）。
#   ★ 上一版按**最长边**归一是错的：高长宽比图上短边会被压到 384 以下（384×1229 → 240×768，面积 0.391），
#     "768 = 上采样"对部分图是假的，分辨率对比被长宽比污染。故改用 `fsc_build_sc.py`（短边口径，
#     逐图记录 src/dst 与实测面积比，实测/标称 = 0.9987–1.0013）。旧目录已删除，避免混用。
#
# 设计（为什么这样比）：三个分辨率用**同一族探针**测量，脚本之间**只差 FSC/OUTD 两个常量**，
#   探针本体（提示词 P、parse()、b64_of()、call_img()）全部 importlib 自冻结的 `/root/19e_probe_multi.py`
#   （md5 03edb14c98ff，零改动）；同一 300 张冻结样本（`sample_test_ids.txt`）；同一 6 臂：
#     base / permit / channel / enumAbstain  ← 19e 的 P（与冻结 384 面板 /root/fsc_results 逐字同题）
#     exemplar3 / exemplar3permit          ← 本库新增的两臂（w1_prereg.json 冻结提示词）
#   ⇒ 4 臂可与**冻结面板**直接对照（交叉核对），另 2 臂把"示例条件"的分辨率敏感性也测出来。
#
# 纪律：冻结的 `w1_fsc_probe.py`、`19e_probe_multi.py`、`19g_probe_fsc.py`、`/root/fsc_results`
#   **一律不动**；本脚本只写 `/root/w1_results/fsc147v2_{384,256,768up}` 三个新目录。
#   任一行不通即整段拒绝继续（探针按行可续跑：已完成的行会跳过）。
set -u
export BAILIAN_API=http://127.0.0.1:8000/v1/chat/completions
export DASHSCOPE_API_KEY=dummy
export VLLM_USE_FLASHINFER_SAMPLER=0
PY=/usr/local/miniconda3/bin/python
VLLM=/usr/local/miniconda3/bin/vllm
L=/root/logs/fscres_run.log
ARMS=base,permit,channel,enumAbstain,exemplar3,exemplar3permit
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
serve_up() {
  local N=$1 MP=$2 TAG=$3; shift 3
  gpu_clear || return 1
  setsid nohup $VLLM serve "$MP" --served-model-name "$N" --max-model-len 8192 \
    --limit-mm-per-prompt '{"image": 1}' --gpu-memory-utilization 0.85 --max-num-seqs 24 --port 8000 \
    "$@" </dev/null > "/root/logs/serve_fscres_${TAG}.log" 2>&1 &
  for i in $(seq 1 80); do
    sleep 15
    curl -sf -m 5 -o /dev/null http://127.0.0.1:8000/v1/models && { say "  [$TAG] 起服就绪 $((i*15))s"; return 0; }
    grep -qiE "Engine core initialization failed|is not supported|No module named|Value error," \
      "/root/logs/serve_fscres_${TAG}.log" 2>/dev/null && { say "  [$TAG] !! 起服报错"; return 1; }
  done
  say "  [$TAG] !! 起服超时"; return 1
}

say "########## E1：FSC-147 分辨率敏感性 384 / 256 / 768up × 6 臂 ##########"

# ⓪ 前置守卫：**E2 未完成不得启动**。E1 起服前会 `pkill -9 -f vllm`，若与 E2 并发，
#   会直接杀掉 E2 正在用的服务（该次服务作废）。宁可拒跑，不可踩坏。
if ! grep -q "E2_PANEL_DONE" /root/logs/ea2_run.log 2>/dev/null; then
  say "!! 未见 E2_PANEL_DONE 标记 ⇒ 拒绝启动 E1（避免杀掉 E2 的服务）。"
  exit 2
fi

# ① 前置件：三个图像目录各须自带 annotation 与样本清单（探针按 FSC 目录读它们）
for d in /root/fsc147 /root/fsc147_sc256 /root/fsc147_sc768; do
  for f in annotation_FSC147_384.json sample_test_ids.txt; do
    [ -f "$d/$f" ] || say "  !! 缺 $d/$f ⇒ 探针会读不到标注"
  done
done
say "① 图像：384=$(ls /root/fsc147/images 2>/dev/null | wc -l) 张（短边384）；256=$(ls /root/fsc147_sc256/images 2>/dev/null | wc -l) 张（短边256）；768=$(ls /root/fsc147_sc768/images 2>/dev/null | wc -l) 张（短边768）"

# ② 三个分辨率 × 同一模型同一次服务（同批权重、同批显存条件）
run_build() {
  local N=$1 MP=$2 TAG=$3; shift 3
  say "===== E1 模型 $TAG（$N）====="
  serve_up "$N" "$MP" "$TAG" "$@" || { say "!! $TAG 起服失败"; gpu_clear; return 1; }
  # ★ 顺序刻意如此：**先 256 与 768**（与冻结 384 面板的对比——即评审要的"另一分辨率"——最早落地），
  #   **本批次 384 重测放最后**（它只是"同题不同脚本批次"的附加核对）。这样万一要提前关机/
  #   收工，已经拿到的就是**结论本身**，而不是"只测了个基线"。探针按臂文件可续跑，中断不丢已有行。
  for R in 256 768 384; do
    say "  [$TAG] $R px × $ARMS"
    $PY "/root/w1_fsc_probe_$R.py" --model "$N" --arms "$ARMS" --n 300 --workers 8 >> "$L" 2>&1
    say "  [$TAG] $R px 完成：$(ls /root/w1_results/fsc_sc$R 2>/dev/null | wc -l) 个臂文件"
  done
  gpu_clear && say "  [$TAG] 完成"
}

run_build InternVL3_5-8B          /root/models/InternVL3_5-8B                       ivl8b --trust-remote-code
run_build Phi-3.5-vision-instruct /root/models/Phi-3.5-vision-instruct              phi35 --trust-remote-code
run_build gemma3-12b              /model/ModelScope/LLM-Research/gemma-3-12b-it     gemma12b

say "########## E1 主跑完成，开始质检 ##########"
$PY /root/fsc_res_qc.py >> "$L" 2>&1
say "########## E1 完成 ##########"
say "FSC_RES_DONE"
