#!/bin/bash
# p5b_run.sh —— 补掉 P5a 的 **ucf 覆盖率缺口**（论文里挂着的"待补"）。
#
# 缺口事实（P3 侧 07:55 UTC 盘点）：
#   32B：283 行、ERR 102/103 全在 ucf ⇒ ucf 覆盖 78/180（原 maxlen 4096）
#   8B ：220 行、ERR=0（ERR 行已被 _p5a_fix_ucf.sh 的步骤②删掉）⇒ ucf 只剩 117/180，63 张缺失
#   全部 ERR 都是 `HTTP Error 400: Bad Request`（图像视觉 token 超过 maxlen）
# 上次失败的真正原因：`_p5a_fix_ucf.sh` 用 frac **0.45** 起 maxlen 16384 ——
#   KV 预算 = 0.45×80 − 权重 16.4 ≈ 19.6 GB，16384 上下文下不够 ⇒ 起服停在 "Using max model len 16384"。
#
# 本件的做法（三条都与已发表列**分开**，不覆盖任何既有文件）：
#   ① 用 **`--tag ml16384_<arm>`** 写**新文件** `p5a_<model>_ml16384_<arm>.csv`
#      （`p5a_probe.py` 里 `tag = A.tag or A.arm` 会**替换**臂名 ⇒ 三臂必须给三个不同 tag，
#        否则三臂会写进同一文件；这是个真陷阱，已在 `_p5a_state.py` 盘点时确认）
#   ② maxlen **16384**、frac **0.85**（整卡），把 180 张 ucf 零池项**全部**重跑一遍
#      ⇒ ucf 列在一**个** maxlen 下自洽；**不与 st_a 列并池**（st_a 仍是原 maxlen）
#   ③ 32B 用 frac 0.90 + `--max-num-seqs 4`（32B bf16 权重 ~64 GB，KV 余量小，只能低并发）
#
# 协议合规：显式 CUDA_VISIBLE_DEVICES / 只杀自己的 PID / **不用全局 pkill** /
#           起服前等显存回落 / 结束回收孤儿 EngineCore。
# 用法：bash p5b_run.sh <gpu> <model_key>     model_key ∈ {8b, 32b}
set -u
PY=/usr/local/miniconda3/bin/python
VLLM=/usr/local/miniconda3/bin/vllm
export VLLM_USE_FLASHINFER_SAMPLER=0
OUTD=/root/p5a_results
mkdir -p "$OUTD" /root/logs
GPU="${1:-0}"
KEY="${2:-8b}"
case "$KEY" in
  8b)  M=Qwen3-VL-8B-Instruct;  MP=/model/ModelScope/Qwen/Qwen3-VL-8B-Instruct;  PORT=8043; FRAC=0.85; SEQ=24 ;;
  32b) M=Qwen3-VL-32B-Instruct; MP=/model/ModelScope/Qwen/Qwen3-VL-32B-Instruct; PORT=8044; FRAC=0.90; SEQ=4 ;;
  *) echo "!! 未知 model_key $KEY"; exit 2 ;;
esac
L="/root/logs/p5b_${KEY}.log"
say() { echo "[$(date +%H:%M:%S)][p5b-$KEY] $*" | tee -a "$L"; }

wait_clear() {
  local i used
  for i in $(seq 1 120); do
    used=$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits -i "$GPU" | tr -d ' ')
    [ "${used:-99999}" -lt 2000 ] && { say "[GPU$GPU] 显存已回落（${used} MiB）"; return 0; }
    [ $((i % 12)) -eq 0 ] && say "[GPU$GPU] 等显存…（现 ${used} MiB）"
    sleep 10
  done
  say "[GPU$GPU] !! 等待超时"; return 1
}

say "== P5b ucf 全覆盖补跑：$M ｜ maxlen 16384 frac $FRAC max-num-seqs $SEQ ｜ GPU$GPU =="
wait_clear || exit 3
CUDA_VISIBLE_DEVICES="$GPU" nohup $VLLM serve "$MP" --served-model-name "$M" \
  --max-model-len 16384 --limit-mm-per-prompt '{"image": 1}' \
  --gpu-memory-utilization "$FRAC" --max-num-seqs "$SEQ" --port "$PORT" \
  </dev/null > "/root/logs/p5b_serve_${KEY}.log" 2>&1 &
SP=$!
ok=0
for i in $(seq 1 150); do
  sleep 8
  curl -sf -m 4 -o /dev/null "http://127.0.0.1:${PORT}/v1/models" && { ok=1; break; }
  if grep -qE "Engine core initialization failed|ValueError|ValidationError|No available memory|Bad Request" "/root/logs/p5b_serve_${KEY}.log" 2>/dev/null; then
    say "!! 起服报错"; break
  fi
  kill -0 "$SP" 2>/dev/null || { say "!! 进程已退出"; break; }
done
if [ "$ok" != "1" ]; then
  say "!! 未就绪（$((i*8))s），跳过"
  tail -n 8 "/root/logs/p5b_serve_${KEY}.log" | sed 's/^/    /'
  kill -9 "$SP" 2>/dev/null
  exit 4
fi
say "就绪（$((i*8))s）"
CP=""
for arm in base forbid0 permit; do
  nohup $PY /root/p5a_probe.py --model "$M" --arm "$arm" --domains ucf --n 0 \
    --api "http://127.0.0.1:${PORT}/v1/chat/completions" --outd "$OUTD" --workers 6 \
    --tag "ml16384_${arm}" \
    </dev/null >> "/root/logs/p5b_probe_${KEY}_${arm}.log" 2>&1 &
  CP="$CP $!"
done
wait $CP
for arm in base forbid0 permit; do
  f="$OUTD/p5a_${M}_ml16384_${arm}.csv"
  if [ -f "$f" ]; then
    n=$($PY -c "import csv,io,sys;print(sum(1 for _ in csv.DictReader(io.open(sys.argv[1],encoding='utf-8-sig',newline=''))))" "$f")
    e=$($PY -c "import csv,io,sys;print(sum(1 for r in csv.DictReader(io.open(sys.argv[1],encoding='utf-8-sig',newline='')) if str(r.get('raw','')).startswith('ERR:')))" "$f")
  else
    n="缺"; e="-"
  fi
  say "[$M/$arm] 行=$n ERR=$e"
done
kill -9 "$SP" 2>/dev/null
sleep 8
for p in $(ps -eo pid,ppid,comm | awk '$2==1 && $3 ~ /^VLLM::EngineCor/ {print $1}'); do
  say "回收孤儿 EngineCore pid=$p"; kill -9 "$p" 2>/dev/null
done
say "P5B_${KEY}_DONE"
