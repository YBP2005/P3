#!/bin/bash
# p1b_run.sh —— P1b（模板轴）：3 家族 × 2 模板 × 2 臂 × σ=8 的 135 项 = 1,620 次调用。
# 三实例错峰并行（Phi-3.5 0.24 + LLaVA 0.22 + Qwen3-VL-8B 0.32 = 0.78，留足余量）。
# 判据必须先冻结（p1b_criteria_frozen.json + 旁车 md5 一致）。四个格子（模板 × 臂）各自一个进程。
# 用法：bash p1b_run.sh [每臂线程 默认6]
set -u
PY=/usr/local/miniconda3/bin/python
VLLM=/usr/local/miniconda3/bin/vllm
export VLLM_USE_FLASHINFER_SAMPLER=0
GRID=/root/p1_grid; OUTD=/root/p1b_results; L=/root/logs/p1b_run.log
W="${1:-6}"
SYS='You are a careful visual counting assistant. Follow the requested output format exactly.'
say() { echo "[$(date +%H:%M:%S)] $*" | tee -a "$L"; }

$PY - <<'PYEOF' || exit 2
import hashlib, io, sys
p='/root/p1b_criteria_frozen.json'; m=p+'.md5'
want=io.open(m,encoding='utf-8').read().split()[0]
got=hashlib.md5(io.open(p,'rb').read()).hexdigest()
print('  P1b 判据 md5 %s %s' % (got[:12], 'OK' if got==want else '与旁车不一致 !!'))
sys.exit(0 if got==want else 2)
PYEOF

mkdir -p "$OUTD" /root/logs
pkill -9 -i -f vllm 2>/dev/null; pkill -9 -f resource_tracker 2>/dev/null; sleep 3
for i in $(seq 1 40); do
  used=$(nvidia-smi --query-gpu=memory.used --format=csv,noheader | tr -d ' MiB')
  [ "$used" -lt 800 ] && break; sleep 3
done
say "== P1b 开始 ｜ 显存 $(nvidia-smi --query-gpu=memory.used --format=csv,noheader) ｜ 线程 $W =="

start_one() { nohup $VLLM serve "$2" --served-model-name "$1" --max-model-len "$5" \
    --limit-mm-per-prompt '{"image": 1}' --gpu-memory-utilization "$4" \
    --max-num-seqs 24 --port "$3" $6 </dev/null > "/root/logs/serve_p1b_$1.log" 2>&1 & echo $!; }
wait_ready() {
  local N="$1" P="$2" PID="$3"
  for i in $(seq 1 40); do
    sleep 8
    curl -sf -m 4 -o /dev/null "http://127.0.0.1:${P}/v1/models" && { say "[$N] 就绪（$((i*8)) s）"; return 0; }
    grep -qE "Engine core initialization failed|No available memory|ValidationError" "/root/logs/serve_p1b_${N}.log" 2>/dev/null && {
      say "[$N] !! 起服失败"; grep -E "ValueError|ValidationError" "/root/logs/serve_p1b_${N}.log" | tail -1 | cut -c1-180 | sed 's/^/    /'; return 1; }
    kill -0 "$PID" 2>/dev/null || { say "[$N] !! 进程退出"; return 1; }
  done
  say "[$N] !! 就绪超时"; return 1
}

PHI_N=Phi-3.5-vision-instruct; PHI_P=/root/models/Phi-3.5-vision-instruct
LLV_N=llava-onevision-qwen2-7b-ov; LLV_P=/root/models/llava-onevision-qwen2-7b-ov
QW8_N=Qwen3-VL-8B-Instruct; QW8_P=/model/ModelScope/Qwen/Qwen3-VL-8B-Instruct

say "① Phi-3.5（0.24）"; P1=$(start_one "$PHI_N" "$PHI_P" 8013 0.24 8192 "--trust_remote_code"); wait_ready "$PHI_N" 8013 "$P1" || true
say "② LLaVA-OV（0.22）"; P2=$(start_one "$LLV_N" "$LLV_P" 8014 0.22 8192 "");                    wait_ready "$LLV_N" 8014 "$P2" || true
say "③ Qwen3-VL-8B（0.32）"; P3=$(start_one "$QW8_N" "$QW8_P" 8015 0.32 8192 "");                 wait_ready "$QW8_N" 8015 "$P3" || true
say "起服阶段结束 ｜ 显存 $(nvidia-smi --query-gpu=memory.used --format=csv,noheader)"

CP=""
for pair in "$PHI_N:8013" "$LLV_N:8014" "$QW8_N:8015"; do
  N="${pair%%:*}"; P="${pair##*:}"
  curl -sf -m 4 -o /dev/null "http://127.0.0.1:${P}/v1/models" || { say "[$N] 未就绪，跳过"; continue; }
  # 四个格子：native(空 system) / sys × base / permit
  for tpl in native sys; do
    SARG=""; TAG="native"
    [ "$tpl" = "sys" ] && { SARG="$SYS"; TAG="sys"; }
    for arm in base permit; do
      if [ "$tpl" = "native" ]; then
        nohup $PY /root/p1_probe.py --grid "$GRID" --family "$N" --arm "$arm" --model "$N" \
          --api "http://127.0.0.1:${P}/v1/chat/completions" --outd "$OUTD" --workers "$W" \
          --object circles --only-sigma 8 --tag native \
          </dev/null >> "/root/logs/p1b_${N}_${TAG}_${arm}.log" 2>&1 &
      else
        nohup $PY /root/p1_probe.py --grid "$GRID" --family "$N" --arm "$arm" --model "$N" \
          --api "http://127.0.0.1:${P}/v1/chat/completions" --outd "$OUTD" --workers "$W" \
          --object circles --only-sigma 8 --tag sys --system "$SARG" \
          </dev/null >> "/root/logs/p1b_${N}_${TAG}_${arm}.log" 2>&1 &
      fi
      CP="$CP $!"
    done
  done
done
say "采集进程：$CP"

T0=$(date +%s)
while :; do
  sleep 30
  alive=0; for p in $CP; do kill -0 "$p" 2>/dev/null && alive=$((alive+1)); done
  now=$(( $(date +%s) - T0 ))
  say "  ${now}s 存活 $alive ｜ 显存 $(nvidia-smi --query-gpu=memory.used --format=csv,noheader)"
  [ "$alive" -eq 0 ] && break
  [ "$now" -ge 1500 ] && { say "  到时限，停止（已写入行保留）"; for p in $CP; do kill -9 "$p" 2>/dev/null; done; break; }
done
pkill -9 -i -f vllm 2>/dev/null; pkill -9 -f resource_tracker 2>/dev/null; sleep 3
say "== P1b 结束 ｜ 显存 $(nvidia-smi --query-gpu=memory.used --format=csv,noheader) =="
say "P1b_DONE"
