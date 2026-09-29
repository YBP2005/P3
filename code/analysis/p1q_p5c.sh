#!/bin/bash
# p1q_p5c.sh —— 排在 GPU0 队列之后跑 **P5 Phase 2（hidden states）**。
# 先做 2 项冒烟（验证 transformers 载入/生成/教师强制/取位置都对），再做全量 σ=8 的 135 项。
# 只有当 GPU0 队列写完 P1Q_GPU0_DONE 才起跑，避免与 vLLM 抢显存。
set -u
PY=/usr/local/miniconda3/bin/python
L=/root/logs/p1q_p5c.log
say() { echo "[$(date +%H:%M:%S)][p5c] $*" | tee -a "$L"; }

say "等 GPU0 队列结束…"
for i in $(seq 1 480); do
  grep -q P1Q_GPU0_DONE /root/logs/p1q_gpu0.log 2>/dev/null && break
  sleep 15
done
grep -q P1Q_GPU0_DONE /root/logs/p1q_gpu0.log 2>/dev/null \
  && say "GPU0 队列已结束" || say "!! 等待超时，仍然尝试（wait_clear 会兜住）"

# 等显存回落
for i in $(seq 1 120); do
  used=$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits -i 0 | tr -d ' ')
  [ "${used:-99999}" -lt 3000 ] && { say "GPU0 显存已回落（${used} MiB）"; break; }
  sleep 10
done

say "① 冒烟：σ=8 取 2 项"
$PY /root/p5c_hidden.py --sigma 8 --limit 2 --out /root/p5c_smoke.jsonl --device 0 \
  >> /root/logs/p5c_smoke.log 2>&1
if ! grep -q 'DONE' /root/logs/p5c_smoke.log 2>/dev/null; then
  say "!! 冒烟失败，见 /root/logs/p5c_smoke.log"; tail -n 12 /root/logs/p5c_smoke.log | sed 's/^/    /'
  exit 4
fi
say "① 冒烟通过"

say "② 全量：σ=8 的 135 项 × 3 臂"
$PY /root/p5c_hidden.py --sigma 8 --out /root/p5c_results.jsonl --device 0 \
  >> /root/logs/p5c_full.log 2>&1
n=$($PY -c "import io;print(sum(1 for _ in io.open('/root/p5c_results.jsonl',encoding='utf-8')))" 2>/dev/null || echo 0)
say "② 全量结束：$n 行 → /root/p5c_results.jsonl"
for p in $(ps -eo pid,ppid,comm | awk '$2==1 && $3 ~ /^VLLM::EngineCor/ {print $1}'); do
  say "回收孤儿 EngineCore pid=$p"; kill -9 "$p" 2>/dev/null
done
say "P5C_DONE"
