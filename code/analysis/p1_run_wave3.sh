#!/bin/bash
# p1_run_wave3.sh —— 重开机后的补跑：**三个实例并行、错峰起服**（gemma3-12b + InternVL3_5-8B + Phi-3.5-vision）。
#
# 目标：把 P1 预注册的三条"新家族"跑全（llava 已在上一波跑完 675/675），从而让 H1/H2 可评。
# 显存预算（实测权重 + 每实例留 ≥3 GiB KV/激活）：gemma 0.44(35.2G) + InternVL3.5 0.28(22.4G)
#   + Phi-3.5 0.20(16.0G) = 0.92（73.6G）⇒ 尽量占满，同时每个实例都拿得到足额份额。
# 为什么错峰：上一波同时起服时后起的实例拿到的是"被别人预定过"的显存，报
#   "No available memory for the cache blocks" / "KV cache 2.94 < 3.0 GiB needed"。
# 断点续跑：探针按 item 跳过已写入行（上一波 16:33 已落地的 Phi/gemma 部分行会保留）。
#
# 用法：bash p1_run_wave3.sh [每臂线程 默认6] [总时限秒 默认1500]
set -u
PY=/usr/local/miniconda3/bin/python
VLLM=/usr/local/miniconda3/bin/vllm
export VLLM_USE_FLASHINFER_SAMPLER=0
GRID=/root/p1_grid
OUTD=/root/p1_results
L=/root/logs/p1_run_wave3.log
W="${1:-6}"
DEADLINE="${2:-1500}"
say() { echo "[$(date +%H:%M:%S)] $*" | tee -a "$L"; }

$PY - <<'PY' || exit 2
import hashlib, io, sys
p='/root/p1_criteria_frozen.json'; m=p+'.md5'
want=io.open(m,encoding='utf-8').read().split()[0]
got=hashlib.md5(io.open(p,'rb').read()).hexdigest()
print('  判据 md5 %s %s' % (got[:12], 'OK' if got==want else '不一致 !!'))
sys.exit(0 if got==want else 2)
PY
[ -f "$GRID/manifest.csv" ] || { say "!! 缺网格"; exit 2; }

pkill -9 -i -f vllm 2>/dev/null; pkill -9 -f resource_tracker 2>/dev/null; sleep 3
say "== wave3 开始 ｜ 显存 $(nvidia-smi --query-gpu=memory.used --format=csv,noheader) ｜ 线程 $W ｜ 时限 ${DEADLINE}s =="

start_one() { nohup $VLLM serve "$2" --served-model-name "$1" --max-model-len "$5" \
    --limit-mm-per-prompt '{"image": 1}' --gpu-memory-utilization "$4" \
    --max-num-seqs 24 --port "$3" $6 </dev/null > "/root/logs/serve_p1_$1.log" 2>&1 & echo $!; }
wait_ready() {
  local N="$1" P="$2" PID="$3"
  for i in $(seq 1 40); do
    sleep 8
    curl -sf -m 4 -o /dev/null "http://127.0.0.1:${P}/v1/models" && { say "[$N] 就绪（$((i*8)) s）"; return 0; }
    grep -qE "Engine core initialization failed|No available memory|ValidationError" "/root/logs/serve_p1_${N}.log" 2>/dev/null && {
      say "[$N] !! 起服失败："; grep -E "ValueError|ValidationError" "/root/logs/serve_p1_${N}.log" | tail -1 | cut -c1-200 | sed 's/^/    /'; return 1; }
    kill -0 "$PID" 2>/dev/null || { say "[$N] !! 进程退出"; return 1; }
  done
  say "[$N] !! 就绪超时"; return 1
}

GEM_N=gemma3-12b;             GEM_P=/model/ModelScope/LLM-Research/gemma-3-12b-it
IVL_N=InternVL3_5-8B;         IVL_P=/root/models/InternVL3_5-8B
PHI_N=Phi-3.5-vision-instruct; PHI_P=/root/models/Phi-3.5-vision-instruct

say "① 起 gemma3-12b（0.44）"; P1=$(start_one "$GEM_N" "$GEM_P" 8001 0.44 8192 "");       wait_ready "$GEM_N" 8001 "$P1" || true
say "② 起 InternVL3_5-8B（0.28）"; P2=$(start_one "$IVL_N" "$IVL_P" 8002 0.28 8192 "--trust_remote_code"); wait_ready "$IVL_N" 8002 "$P2" || true
say "③ 起 Phi-3.5-vision（0.20）"; P3=$(start_one "$PHI_N" "$PHI_P" 8003 0.20 8192 "--trust_remote_code"); wait_ready "$PHI_N" 8003 "$P3" || true
say "起服阶段结束 ｜ 显存 $(nvidia-smi --query-gpu=memory.used --format=csv,noheader)"

CP=""
for pair in "$GEM_N:8001" "$IVL_N:8002" "$PHI_N:8003"; do
  N="${pair%%:*}"; P="${pair##*:}"
  curl -sf -m 4 -o /dev/null "http://127.0.0.1:${P}/v1/models" || { say "[$N] 未就绪，跳过"; continue; }
  for arm in base permit; do
    nohup $PY /root/p1_probe.py --grid "$GRID" --family "$N" --arm "$arm" \
      --model "$N" --api "http://127.0.0.1:${P}/v1/chat/completions" \
      --outd "$OUTD" --workers "$W" --object circles \
      </dev/null >> "/root/logs/p1_probe_${N}_${arm}.log" 2>&1 &
    CP="$CP $!"
  done
done
say "采集进程：$CP"

T0=$(date +%s)
while :; do
  sleep 30
  alive=0; for p in $CP; do kill -0 "$p" 2>/dev/null && alive=$((alive+1)); done
  now=$(( $(date +%s) - T0 ))
  say "  ${now}s：存活 $alive ｜ 显存 $(nvidia-smi --query-gpu=memory.used --format=csv,noheader)"
  [ "$alive" -eq 0 ] && break
  if [ "$now" -ge "$DEADLINE" ]; then say "!! 到时限，停止采集（已写入行保留）"; for p in $CP; do kill -9 "$p" 2>/dev/null; done; break; fi
done

$PY - <<'PY' | tee -a "$L"
import csv, io, os
OUTD='/root/p1_results'
for f in sorted(os.listdir(OUTD)):
    if not f.endswith('.csv'): continue
    rows=list(csv.DictReader(io.open(os.path.join(OUTD,f),encoding='utf-8-sig',newline='')))
    z=sum(1 for x in rows if x.get('is_zero')=='1'); pf=sum(1 for x in rows if x.get('parse_ok')!='1')
    print('  %-52s 唯一item=%3d  zero=%3d  parse_fail=%3d' % (f, len(rows), z, pf))
PY
pkill -9 -i -f vllm 2>/dev/null; pkill -9 -f resource_tracker 2>/dev/null; sleep 3
say "== wave3 结束 ｜ 显存 $(nvidia-smi --query-gpu=memory.used --format=csv,noheader) =="
say "P1_wave3_DONE"
