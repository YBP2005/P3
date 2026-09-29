#!/bin/bash
# g9_all.sh — G9（倒数第二层 L2 范数）：**先过污染闸门，再跑**。
# ⚠⚠ A800 已交会议侧：本脚本第一步就独占显卡 ⇒ 默认**拒绝执行**。
#     确有权接管时才：ALLOW_GPU_TAKEOVER=1 bash /root/g9_all.sh
if [ "${ALLOW_GPU_TAKEOVER:-0}" != "1" ]; then
  echo "[g9] 拒绝执行：A800 已交会议侧。若确有权接管，请用 ALLOW_GPU_TAKEOVER=1 重跑。"
  echo "[g9] 当前占用：$(nvidia-smi --query-gpu=memory.used,utilization.gpu --format=csv,noheader | head -1)"
  exit 3
fi
OCC=$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits | head -1 | tr -d ' ')
if [ "$OCC" -ge 1000 ]; then echo "[g9] 拒绝执行：显存已占 ${OCC} MiB。"; exit 4; fi

# ★ PATH：vLLM 在 CUDA-graph/编译那一步会 `Popen('ninja')`，setsid+nohup 起的进程 PATH 里
#   没有 conda 的 bin ⇒ 实测 FileNotFoundError。这里显式补上。
# ★ 基础设施两则（2026-09-27 实测；都**不是我们的选择**，结果里已声明）：
#   ① PATH：ninja 在 conda bin，而 setsid+nohup 起的进程 PATH 里没有它 ⇒ FileNotFoundError: 'ninja'；
#   ② 本镜像**只有 gcc 没有 g++**（`cc1plus` 不存在），而 FlashInfer 采样算子缓存只剩 build.ninja
#      ⇒ 每次起服都尝试重编、每次必失败（`gcc: fatal error: cannot execute 'cc1plus'`）。
#      关掉 FlashInfer 采样器即绕开编译，改用原生 PyTorch 采样器（temperature 0 下取值不变）。
export PATH=/usr/local/miniconda3/bin:$PATH
export VLLM_USE_FLASHINFER_SAMPLER=0


PY=/usr/local/miniconda3/bin/python
LOG=/root/g9.log
mkdir -p /root/g9_res
say() { echo "[$(date +%H:%M:%S)] $*" | tee -a "$LOG"; }

say "########## G9 开始（先闸门、后测量）##########"

# ★ 先**烟测**（2 项 × 3 臂）：这一步抓的是**我自己的代码缺陷**（API 名、张量形状），
#   与污染闸门是两件事 —— 烟测失败 ⇒ 退出码 5，**不得**当成不可测的结论。
 -u /root/g9_hidden_l2.py --smoke 2 >> "" 2>&1
if [ 0 -ne 0 ]; then say "!! 烟测失败（自伤性缺陷，不是污染证据）⇒ 停下修代码，不出任何结论"; exit 5; fi
$PY -u /root/g9_guard.py --n 20 >> "$LOG" 2>&1
rc=$?
if [ $rc -ne 0 ]; then
  say "!! 污染闸门未过（rc=$rc）⇒ 按预注册规则：G9 报为**不可测**，不跑测量、不发布 L2 结论。"
  echo G9_NOT_MEASURABLE >> "$LOG"; exit $rc
fi
say "闸门通过 ⇒ 跑测量"
$PY -u /root/g9_hidden_l2.py >> "$LOG" 2>&1
say "########## G9 结束 ##########"
echo G9_ALL_DONE >> "$LOG"
