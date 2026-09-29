#!/bin/bash
# p1_run_parallel.sh —— P1 受控版采集：**单卡多实例并行**（A800-80GB），每家族独立子壳，
# 一个家族起不来不拖住别的家族。产物 /root/p1_results/p1_<family>_<arm>.csv。
#
# 为什么多实例：用户口径"实验要并行、尽量多占 GPU 与显存"。每实例用 `--gpu-memory-utilization`
# 预定自己的显存；实例内 `--max-model-len / --max-num-seqs` 与 E2/E3 参考栈一致（S1 已证明
# maxlen 会移动率，故不动它）——并行靠"多实例 + 多客户端线程"，不靠改实例参数。
#
# 2026-09-24 首跑的三处修正（都记在这里，避免下次再踩）：
#   ① InternVL3.5 / Phi-3.5 **必须** `--trust_remote_code`（否则 pydantic 校验直接拒绝）；
#   ② llava-onevision 的 0.18 份额小于其权重（15.07 GiB 实测）⇒ "No available memory for the
#      cache blocks"，实测线上是 0.26；llava 的 checkpoint 15.07 GiB、加载要 75 s；
#   ③ 原来"等 4/4 就绪才开始采集"会被任一失败实例拖死 ⇒ 改成**每家族各自 wait-then-collect**。
#
# 用法：bash p1_run_parallel.sh [wave1|wave2|wave3] [workers_per_arm]
set -u
PY=/usr/local/miniconda3/bin/python
VLLM=/usr/local/miniconda3/bin/vllm
export VLLM_USE_FLASHINFER_SAMPLER=0
GRID=/root/p1_grid
OUTD=/root/p1_results
mkdir -p "$OUTD" /root/logs
L=/root/logs/p1_run_parallel.log
PROFILE="${1:-wave1}"
W="${2:-8}"
ARMS="base,permit"
say() { echo "[$(date +%H:%M:%S)] $*" | tee -a "$L"; }

$PY - <<'PY' || exit 2
import hashlib, io, sys
p='/root/p1_criteria_frozen.json'; m=p+'.md5'
want=io.open(m,encoding='utf-8').read().split()[0]
got=hashlib.md5(io.open(p,'rb').read()).hexdigest()
print('  判据 md5 %s %s' % (got[:12], 'OK' if got==want else '与旁车不一致 !!'))
sys.exit(0 if got==want else 2)
PY
[ -f "$GRID/manifest.csv" ] || { say "!! 缺 $GRID/manifest.csv"; exit 2; }

# 家族|模型路径|端口|显存比例|maxlen|附加参数
case "$PROFILE" in
  wave1)
    FAMS="gemma3-12b|/model/ModelScope/LLM-Research/gemma-3-12b-it|8001|0.40|8192|
InternVL3_5-8B|/root/models/InternVL3_5-8B|8002|0.28|8192|--trust_remote_code
llava-onevision-qwen2-7b-ov|/root/models/llava-onevision-qwen2-7b-ov|8004|0.26|8192|" ;;
  wave2)
    FAMS="Phi-3.5-vision-instruct|/root/models/Phi-3.5-vision-instruct|8003|0.30|8192|--trust_remote_code
Qwen3-VL-8B-Instruct|/model/ModelScope/Qwen/Qwen3-VL-8B-Instruct|8005|0.45|8192|" ;;
  wave3)
    FAMS="Qwen3-VL-32B-Instruct|/model/ModelScope/Qwen/Qwen3-VL-32B-Instruct|8006|0.85|4096|" ;;
  *) say "!! 未知 profile $PROFILE"; exit 2 ;;
esac

pkill -9 -i -f vllm 2>/dev/null; pkill -9 -f resource_tracker 2>/dev/null; sleep 3
for i in $(seq 1 40); do
  used=$(nvidia-smi --query-gpu=memory.used --format=csv,noheader | tr -d ' MiB')
  [ "$used" -lt 800 ] && break; sleep 3
done
say "== $PROFILE 开始 ｜ 清场后显存 $(nvidia-smi --query-gpu=memory.used --format=csv,noheader) ｜ 网格 675 项 =="

# 每个家族一个子壳：起服 → 等就绪 → 跑两臂 → 停自己的服务 → 写标记
family_job() {
  local NAME="$1" MP="$2" PORT="$3" FRAC="$4" ML="$5" EXTRA="$6"
  local LOG="/root/logs/serve_p1_${NAME}.log"
  local SPID=""
  say "[$NAME] 起服 port=$PORT frac=$FRAC maxlen=$ML extra='$EXTRA'"
  nohup $VLLM serve "$MP" --served-model-name "$NAME" --max-model-len "$ML" \
    --limit-mm-per-prompt '{"image": 1}' --gpu-memory-utilization "$FRAC" \
    --max-num-seqs 24 --port "$PORT" $EXTRA </dev/null > "$LOG" 2>&1 &
  SPID=$!
  local ok=0
  for i in $(seq 1 100); do
    sleep 8
    if curl -sf -m 4 -o /dev/null "http://127.0.0.1:${PORT}/v1/models"; then ok=1; break; fi
    if grep -qE "Engine core initialization failed|ValueError|ValidationError|No available memory" "$LOG" 2>/dev/null; then
      say "[$NAME] !! 起服失败（见 $LOG）"; break
    fi
    kill -0 "$SPID" 2>/dev/null || { say "[$NAME] !! 进程已退出"; break; }
  done
  if [ "$ok" != "1" ]; then
    say "[$NAME] !! 未就绪，跳过该家族（其他家族不受影响）"; tail -n 6 "$LOG" | sed 's/^/    /'
    kill -9 "$SPID" 2>/dev/null; return 1
  fi
  say "[$NAME] 就绪（$((i*8)) s）｜显存 $(nvidia-smi --query-gpu=memory.used --format=csv,noheader)"
  local cp=""
  for arm in ${ARMS//,/ }; do
    nohup $PY /root/p1_probe.py --grid "$GRID" --family "$NAME" --arm "$arm" \
      --model "$NAME" --api "http://127.0.0.1:${PORT}/v1/chat/completions" \
      --outd "$OUTD" --workers "$W" --object circles \
      </dev/null >> "/root/logs/p1_probe_${NAME}_${arm}.log" 2>&1 &
    cp="$cp $!"
  done
  wait $cp
  for arm in ${ARMS//,/ }; do
    local f="$OUTD/p1_${NAME}_${arm}.csv"
    if [ -f "$f" ]; then say "[$NAME/$arm] $(($(wc -l < "$f")-1)) 行"; else say "[$NAME/$arm] !! 无产物"; fi
  done
  kill -9 "$SPID" 2>/dev/null
  sleep 3
  say "[$NAME] 完成并已停服 ｜ 显存 $(nvidia-smi --query-gpu=memory.used --format=csv,noheader)"
  return 0
}

JPIDS=""
while IFS='|' read -r NAME MP PORT FRAC ML EXTRA; do
  [ -z "$NAME" ] && continue
  family_job "$NAME" "$MP" "$PORT" "$FRAC" "$ML" "${EXTRA:-}" &
  JPIDS="$JPIDS $!"
done <<< "$FAMS"
wait $JPIDS
pkill -9 -i -f vllm 2>/dev/null; pkill -9 -f resource_tracker 2>/dev/null; sleep 3
say "== $PROFILE 结束 ｜ 最终显存 $(nvidia-smi --query-gpu=memory.used --format=csv,noheader) =="
say "P1_${PROFILE}_DONE"
