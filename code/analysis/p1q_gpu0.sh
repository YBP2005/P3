#!/bin/bash
# p1q_gpu0.sh —— **GPU0 队列**：锚定阶梯（Phi / Qwen3-VL-8B）+ 同会话噪声底（base × 3 tag）。
# 每一项内部都会先 `wait_clear`，所以本脚本可以现在就发出去，它会排队等 GPU0 空出来。
# 队列结束后由外层再拉 P5 Phase 2（hidden states，transformers 直跑，不走 vLLM）。
set -u
Q=/root/p1x_run.sh
L=/root/logs/p1q_gpu0.log
say() { echo "[$(date +%H:%M:%S)][q0] $*" | tee -a "$L"; }

say "GPU0 队列开始（等显存回落中）"

# ① 锚定阶梯：Phi-3.5（base 13.5% / 提0 达 100% ⇒ 阶梯最有信息量的一族）
bash $Q 0 Phi-3.5-vision-instruct /root/models/Phi-3.5-vision-instruct 8003 0.30 8192 \
  "--trust_remote_code" /root/p1f_probe.py mention5,mention50,mention800 ""
say "① Phi 阶梯完成"

# ② 锚定阶梯：Qwen3-VL-8B
bash $Q 0 Qwen3-VL-8B-Instruct /model/ModelScope/Qwen/Qwen3-VL-8B-Instruct 8005 0.45 8192 \
  "" /root/p1f_probe.py mention5,mention50,mention800 ""
say "② 8B 阶梯完成"

# ③ 同会话噪声底：同一个服务会话内把 base 跑 3 遍（tag 区分，互不覆盖）
bash $Q 0 Qwen3-VL-8B-Instruct /model/ModelScope/Qwen/Qwen3-VL-8B-Instruct 8005 0.45 8192 \
  "" /root/p1d_probe.py base "rep1,rep2,rep3"
say "③ 同会话噪声底完成"

say "P1Q_GPU0_DONE"
