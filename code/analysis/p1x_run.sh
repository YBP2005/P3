#!/bin/bash
# p1x_run.sh —— **通用**的"起服 → 跑若干臂 → 停服"驱动（P1d/P1e/P1f/P1g 共用）。
#
# 为什么做成通用件：后面还有锚定阶梯（3 臂 × 4 族）与同会话噪声底（base × 3 个 tag）要跑，
# 每个都复制一份起服/停服/看门狗逻辑必然会各自漂移。这里只写一次。
#
# 用法：
#   bash p1x_run.sh <GPU> <NAME> <MP> <PORT> <FRAC> <MAXLEN> <EXTRA> <PROBE> <ARMS> <TAGS>
#     GPU     0|1
#     EXTRA   传给 vllm serve 的附加参数（可为空字符串；--trust_remote_code 等）
#     PROBE   要调的探针脚本，如 /root/p1f_probe.py
#     ARMS    逗号分隔的臂名
#     TAGS    逗号分隔的 tag；**空** ⇒ 每个臂跑一次、不带 tag；
#             非空 ⇒ 对每个 tag × 每个臂各跑一次（**同一个服务会话内并发**）
#             典型用法：ARMS=base TAGS=rep1,rep2,rep3 ⇒ 同会话 3 次重复（噪声底）
#
# 协议合规：显式 CUDA_VISIBLE_DEVICES / 只杀自己的 PID / 不用全局 pkill /
#           起服前等显存回落 / 结束时回收孤儿 VLLM::EngineCore。
set -u
PY=/usr/local/miniconda3/bin/python
VLLM=/usr/local/miniconda3/bin/vllm
export VLLM_USE_FLASHINFER_SAMPLER=0
export P1_FROZEN=/root/19e_probe_multi.py
OUTD="${P1X_OUTD:-/root/p1d_results}"
WORKERS="${P1X_WORKERS:-8}"
GRID=/root/p1_grid

GPU="$1"; NAME="$2"; MP="$3"; PORT="$4"; FRAC="$5"; ML="$6"; EXTRA="$7"; PROBE="$8"; ARMS="$9"; TAGS="${10:-}"
L="/root/logs/p1x_${NAME}.log"
say() { echo "[$(date +%H:%M:%S)][$NAME] $*" | tee -a "$L"; }
mkdir -p "$OUTD" /root/logs

wait_clear() {
  local i used
  for i in $(seq 1 120); do
    used=$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits -i "$GPU" | tr -d ' ')
    [ "${used:-99999}" -lt 2000 ] && { say "[GPU$GPU] 显存已回落（${used} MiB）"; return 0; }
    [ $((i % 12)) -eq 0 ] && say "[GPU$GPU] 等显存…（现 ${used} MiB）"
    sleep 10
  done
  say "[GPU$GPU] !! 等显存超时"; return 1
}
reap() {
  local p
  for p in $(ps -eo pid,ppid,comm | awk '$2==1 && $3 ~ /^VLLM::EngineCor/ {print $1}'); do
    say "回收孤儿 EngineCore pid=$p"; kill -9 "$p" 2>/dev/null
  done
}

say "== 起服 $NAME ｜ GPU$GPU port=$PORT frac=$FRAC maxlen=$ML extra='$EXTRA' ｜ 探针 $PROBE =="
wait_clear || exit 3
[ -d "$MP" ] || { say "!! 权重目录不存在：$MP"; exit 3; }
CUDA_VISIBLE_DEVICES="$GPU" nohup $VLLM serve "$MP" --served-model-name "$NAME" \
  --max-model-len "$ML" --limit-mm-per-prompt '{"image": 1}' \
  --gpu-memory-utilization "$FRAC" --max-num-seqs 24 --port "$PORT" $EXTRA \
  </dev/null > "/root/logs/p1x_serve_${NAME}.log" 2>&1 &
SP=$!
ok=0
for i in $(seq 1 150); do
  sleep 8
  curl -sf -m 4 -o /dev/null "http://127.0.0.1:${PORT}/v1/models" && { ok=1; break; }
  if grep -qE "Engine core initialization failed|ValueError|ValidationError|No available memory" "/root/logs/p1x_serve_${NAME}.log" 2>/dev/null; then
    say "!! 起服报错"; break; fi
  kill -0 "$SP" 2>/dev/null || { say "!! 进程已退出"; break; }
done
if [ "$ok" != "1" ]; then
  say "!! 未就绪（$((i*8))s），跳过"; tail -n 8 "/root/logs/p1x_serve_${NAME}.log" | sed 's/^/    /'
  kill -9 "$SP" 2>/dev/null; exit 4
fi
say "就绪（$((i*8))s）"

CP=""
if [ -z "$TAGS" ]; then
  for arm in ${ARMS//,/ }; do
    nohup $PY "$PROBE" --grid "$GRID" --family "$NAME" --arm "$arm" --model "$NAME" \
      --api "http://127.0.0.1:${PORT}/v1/chat/completions" --outd "$OUTD" --workers "$WORKERS" \
      </dev/null >> "/root/logs/p1x_probe_${NAME}_${arm}.log" 2>&1 &
    CP="$CP $!"
  done
else
  for tag in ${TAGS//,/ }; do
    for arm in ${ARMS//,/ }; do
      nohup $PY "$PROBE" --grid "$GRID" --family "$NAME" --arm "$arm" --model "$NAME" \
        --api "http://127.0.0.1:${PORT}/v1/chat/completions" --outd "$OUTD" --workers "$WORKERS" \
        --tag "$tag" \
        </dev/null >> "/root/logs/p1x_probe_${NAME}_${arm}_${tag}.log" 2>&1 &
      CP="$CP $!"
    done
  done
fi
wait $CP

for arm in ${ARMS//,/ }; do
  if [ -z "$TAGS" ]; then
    f="$OUTD/p1d_${NAME}_${arm}.csv"
    if [ -f "$f" ]; then
      n=$($PY -c "import csv,io,sys;print(sum(1 for _ in csv.DictReader(io.open(sys.argv[1],encoding='utf-8-sig',newline=''))))" "$f")
    else n="缺"; fi
    say "[$NAME/$arm] 行=$n"
  else
    for tag in ${TAGS//,/ }; do
      f="$OUTD/p1d_${tag}_${NAME}_${arm}.csv"
      if [ -f "$f" ]; then
        n=$($PY -c "import csv,io,sys;print(sum(1 for _ in csv.DictReader(io.open(sys.argv[1],encoding='utf-8-sig',newline=''))))" "$f")
      else n="缺"; fi
      say "[$NAME/$arm/$tag] 行=$n"
    done
  fi
done
kill -9 "$SP" 2>/dev/null
sleep 8
reap
say "P1X_${NAME}_DONE"
