#!/bin/bash
# p1_run_wave2.sh —— 30 分钟窗口内的补跑：Phi-3.5-vision + gemma3-12b（**错峰起服**）。
#
# 为什么错峰：上一波三实例同时起服时，先起的实例先把显存预定掉，后起的实例
# 拿到的可用显存**小于它自己的份额** ⇒ 报 "No available memory for the cache blocks"（InternVL3.5）
# 或 "KV cache 2.94 GiB < 3.0 GiB needed"（gemma 在 0.40 份额下）。错峰后每个实例都拿到足额。
#
# 份额依据（实测/权重体积）：Phi-3.5 权重 8.3 G ⇒ 0.28（22.4 G）富余；gemma-3-12b BF16 权重 24.4 G
# 且 maxlen 8192 需 ~3 G KV ⇒ 0.50（40 G）稳。两者和 0.78（62 G），留足余量。
#
# 用法：bash p1_run_wave2.sh [每臂线程 默认6] [总时限秒 默认1320]
set -u
PY=/usr/local/miniconda3/bin/python
VLLM=/usr/local/miniconda3/bin/vllm
export VLLM_USE_FLASHINFER_SAMPLER=0
GRID=/root/p1_grid
OUTD=/root/p1_results
L=/root/logs/p1_run_wave2.log
W="${1:-6}"
DEADLINE="${2:-1320}"     # 22 分钟：留 8 分钟给拉取/分析/关机
say() { echo "[$(date +%H:%M:%S)] $*" | tee -a "$L"; }

$PY - <<'PY' || exit 2
import hashlib, io, sys
p='/root/p1_criteria_frozen.json'; m=p+'.md5'
want=io.open(m,encoding='utf-8').read().split()[0]
got=hashlib.md5(io.open(p,'rb').read()).hexdigest()
print('  判据 md5 %s %s' % (got[:12], 'OK' if got==want else '不一致 !!'))
sys.exit(0 if got==want else 2)
PY

pkill -9 -i -f vllm 2>/dev/null; pkill -9 -f resource_tracker 2>/dev/null; sleep 3
say "== wave2 开始 ｜ 显存 $(nvidia-smi --query-gpu=memory.used --format=csv,noheader) =="

start_one() {   # name path port frac maxlen extra
  local N="$1" MP="$2" P="$3" F="$4" ML="$5" E="$6"
  nohup $VLLM serve "$MP" --served-model-name "$N" --max-model-len "$ML" \
    --limit-mm-per-prompt '{"image": 1}' --gpu-memory-utilization "$F" \
    --max-num-seqs 24 --port "$P" $E </dev/null > "/root/logs/serve_p1_${N}.log" 2>&1 &
  echo $!
}
wait_ready() {  # name port pid
  local N="$1" P="$2" PID="$3"
  for i in $(seq 1 45); do
    sleep 8
    curl -sf -m 4 -o /dev/null "http://127.0.0.1:${P}/v1/models" && { say "[$N] 就绪（$((i*8)) s）"; return 0; }
    grep -qE "Engine core initialization failed|No available memory|ValueError" "/root/logs/serve_p1_${N}.log" 2>/dev/null && {
      say "[$N] !! 起服失败"; grep -E "ValueError" "/root/logs/serve_p1_${N}.log" | tail -2 | sed 's/^/    /'; return 1; }
    kill -0 "$PID" 2>/dev/null || { say "[$N] !! 进程退出"; return 1; }
  done
  say "[$N] !! 就绪超时"; return 1
}

PHI_N=Phi-3.5-vision-instruct; PHI_P=/root/models/Phi-3.5-vision-instruct
GEM_N=gemma3-12b;             GEM_P=/model/ModelScope/LLM-Research/gemma-3-12b-it

P1=$(start_one "$PHI_N" "$PHI_P" 8003 0.28 8192 "--trust_remote_code"); say "[$PHI_N] pid=$P1"
wait_ready "$PHI_N" 8003 "$P1" || say "[$PHI_N] 跳过"
P2=$(start_one "$GEM_N" "$GEM_P" 8001 0.50 8192 ""); say "[$GEM_N] pid=$P2"
wait_ready "$GEM_N" 8001 "$P2" || say "[$GEM_N] 跳过"
say "起服阶段结束 ｜ 显存 $(nvidia-smi --query-gpu=memory.used --format=csv,noheader)"

CP=""
for pair in "$PHI_N:8003" "$GEM_N:8001"; do
  N="${pair%%:*}"; P="${pair##*:}"
  curl -sf -m 4 -o /dev/null "http://127.0.0.1:${P}/v1/models" || { say "[$N] 未就绪，跳过采集"; continue; }
  for arm in base permit; do
    nohup $PY /root/p1_probe.py --grid "$GRID" --family "$N" --arm "$arm" \
      --model "$N" --api "http://127.0.0.1:${P}/v1/chat/completions" \
      --outd "$OUTD" --workers "$W" --object circles \
      </dev/null >> "/root/logs/p1_probe_${N}_${arm}.log" 2>&1 &
    CP="$CP $!"
  done
done
say "采集进程：$CP ｜ 时限 ${DEADLINE}s"

T0=$(date +%s)
while :; do
  sleep 20
  alive=0
  for p in $CP; do kill -0 "$p" 2>/dev/null && alive=$((alive+1)); done
  now=$(( $(date +%s) - T0 ))
  say "  ${now}s：存活采集进程 $alive ｜ 显存 $(nvidia-smi --query-gpu=memory.used --format=csv,noheader)"
  [ "$alive" -eq 0 ] && break
  if [ "$now" -ge "$DEADLINE" ]; then
    say "!! 到时限，停止采集（已写入的行保留，可续跑）"
    for p in $CP; do kill -9 "$p" 2>/dev/null; done
    break
  fi
done

for pair in "$PHI_N" "$GEM_N"; do
  for arm in base permit; do
    f="$OUTD/p1_${pair}_${arm}.csv"
    [ -f "$f" ] && say "  $pair/$arm：$($PY -c "import csv,io,sys; r=list(csv.DictReader(io.open(sys.argv[1],encoding='utf-8-sig',newline=''))); print('%d 唯一 item, zero=%d, parse_fail=%d' % (len(r), sum(1 for x in r if x.get('is_zero')=='1'), sum(1 for x in r if x.get('parse_ok')!='1')))" "$f")"
  done
done
pkill -9 -i -f vllm 2>/dev/null; pkill -9 -f resource_tracker 2>/dev/null; sleep 3
say "== wave2 结束 ｜ 显存 $(nvidia-smi --query-gpu=memory.used --format=csv,noheader) =="
say "P1_wave2_DONE"
