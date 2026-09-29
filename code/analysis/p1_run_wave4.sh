#!/bin/bash
# p1_run_wave4.sh —— 锚家族（判据里的 H4 那一格需要 Qwen3-VL-32B）。
#
# 顺序（两者都要单独占卡，无法并行——63 GiB 的 BF16 权重只装得下一个）：
#   ① Qwen3-VL-8B-Instruct  0.45（32 GB；权重 ~17 G，KV 富余）
#   ② Qwen3-VL-32B-Instruct 0.85 + maxlen 4096（记录里明确：BF16 63 G 需限长 4096 才起得来）
#      ★ H4 的已发表锚值就取这个家族的 σ=8 ∧ n=800 格（G.2 原文：该格 base 答零率 100%）。
#      ★ 但 maxlen 与参考栈不同（4096 vs 8192）⇒ 若 H4 不过，必须把"限长"列为可能原因之一，
#        这正是判据里写好的那句"若不过 ⇒ 不并表，只同批内比"。
#
# 用法：bash p1_run_wave4.sh [每臂线程 默认6] [总时限秒 默认1800]
set -u
PY=/usr/local/miniconda3/bin/python
VLLM=/usr/local/miniconda3/bin/vllm
export VLLM_USE_FLASHINFER_SAMPLER=0
GRID=/root/p1_grid; OUTD=/root/p1_results; L=/root/logs/p1_run_wave4.log
W="${1:-6}"; DEADLINE="${2:-1800}"
say() { echo "[$(date +%H:%M:%S)] $*" | tee -a "$L"; }

pkill -9 -i -f vllm 2>/dev/null; pkill -9 -f resource_tracker 2>/dev/null; sleep 3
say "== wave4 开始 ｜ 显存 $(nvidia-smi --query-gpu=memory.used --format=csv,noheader) =="

run_family() {   # name path port frac maxlen extra budget_s
  local N="$1" MP="$2" P="$3" F="$4" ML="$5" E="$6" BUD="$7"
  say "[$N] 起服 port=$P frac=$F maxlen=$ML"
  nohup $VLLM serve "$MP" --served-model-name "$N" --max-model-len "$ML" \
    --limit-mm-per-prompt '{"image": 1}' --gpu-memory-utilization "$F" \
    --max-num-seqs 24 --port "$P" $E </dev/null > "/root/logs/serve_p1_${N}.log" 2>&1 &
  local SP=$! ok=0
  for i in $(seq 1 60); do
    sleep 10
    curl -sf -m 4 -o /dev/null "http://127.0.0.1:${P}/v1/models" && { ok=1; break; }
    grep -qE "Engine core initialization failed|No available memory|ValidationError" "/root/logs/serve_p1_${N}.log" 2>/dev/null && {
      say "[$N] !! 起服失败"; grep -E "ValueError|ValidationError" "/root/logs/serve_p1_${N}.log" | tail -1 | cut -c1-200 | sed 's/^/    /'; break; }
    kill -0 "$SP" 2>/dev/null || { say "[$N] !! 进程退出"; break; }
  done
  if [ "$ok" != "1" ]; then kill -9 "$SP" 2>/dev/null; say "[$N] 跳过"; return 1; fi
  say "[$N] 就绪（$((i*10)) s）｜显存 $(nvidia-smi --query-gpu=memory.used --format=csv,noheader)"
  local CP=""
  for arm in base permit; do
    nohup $PY /root/p1_probe.py --grid "$GRID" --family "$N" --arm "$arm" \
      --model "$N" --api "http://127.0.0.1:${P}/v1/chat/completions" \
      --outd "$OUTD" --workers "$W" --object circles \
      </dev/null >> "/root/logs/p1_probe_${N}_${arm}.log" 2>&1 &
    CP="$CP $!"
  done
  local T0=$(date +%s)
  while :; do
    sleep 30
    local alive=0; for p in $CP; do kill -0 "$p" 2>/dev/null && alive=$((alive+1)); done
    local now=$(( $(date +%s) - T0 ))
    say "  [$N] ${now}s 存活 $alive ｜ 显存 $(nvidia-smi --query-gpu=memory.used --format=csv,noheader)"
    [ "$alive" -eq 0 ] && break
    [ "$now" -ge "$BUD" ] && { say "  [$N] !! 到时限，停止（已写入行保留）"; for p in $CP; do kill -9 "$p" 2>/dev/null; done; break; }
  done
  kill -9 "$SP" 2>/dev/null; sleep 4
  say "[$N] 完成并停服"
}

run_family Qwen3-VL-8B-Instruct  /model/ModelScope/Qwen/Qwen3-VL-8B-Instruct  8005 0.45 8192 "" 900 || true
run_family Qwen3-VL-32B-Instruct /model/ModelScope/Qwen/Qwen3-VL-32B-Instruct 8006 0.85 4096 "" 1200 || true

$PY - <<'PY' | tee -a "$L"
import csv, io, os
for f in sorted(os.listdir('/root/p1_results')):
    if not f.endswith('.csv'): continue
    rows=list(csv.DictReader(io.open('/root/p1_results/'+f,encoding='utf-8-sig',newline='')))
    z=sum(1 for x in rows if x.get('is_zero')=='1')
    print('  %-52s 唯一item=%3d zero=%3d' % (f, len(rows), z))
PY
pkill -9 -i -f vllm 2>/dev/null; pkill -9 -f resource_tracker 2>/dev/null; sleep 3
say "== wave4 结束 ｜ 显存 $(nvidia-smi --query-gpu=memory.used --format=csv,noheader) =="
say "P1_wave4_DONE"
