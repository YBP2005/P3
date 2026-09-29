#!/bin/bash
# p1q_gpu1.sh —— **GPU1 队列**：P5b 32B 的 ucf 全覆盖补跑 → 锚定阶梯（llava / gemma）。
# 每项内部先 `wait_clear`，可现在发出，排队等 GPU1 空出来（它此刻在跑 InternVL3.5 的 placebo100）。
set -u
Q=/root/p1x_run.sh
L=/root/logs/p1q_gpu1.log
say() { echo "[$(date +%H:%M:%S)][q1] $*" | tee -a "$L"; }

say "GPU1 队列开始（等显存回落中）"

# ① P5b：32B 的 ucf 全覆盖（maxlen 16384，frac 0.90，低并发）——自带起服/停服逻辑
bash /root/p5b_run.sh 1 32b
say "① P5b 32B 完成"

# ② 锚定阶梯：llava-onevision（P1d 里 neutral0=46.7%，有解析失败需单独看）
bash $Q 1 llava-onevision-qwen2-7b-ov /root/models/llava-onevision-qwen2-7b-ov 8004 0.26 8192 \
  "" /root/p1f_probe.py mention5,mention50,mention800 ""
say "② llava 阶梯完成"

# ③ 锚定阶梯：gemma3-12b（**阴性对照**：该族 base 零率恒 0，H_L4 用它）
bash $Q 1 gemma3-12b /model/ModelScope/LLM-Research/gemma-3-12b-it 8001 0.40 8192 \
  "" /root/p1f_probe.py mention5,mention50,mention800 ""
say "③ gemma 阶梯完成"

say "P1Q_GPU1_DONE"
