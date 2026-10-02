#!/bin/bash
# pf_p0a_run.sh —— P0-A：InternVL3.5-38B-BF16 的**英文臂**与**缺失的契约臂**（TP=2，三次 fresh start）
#
# 【预注册】/root/p0a/_p0a_criteria_frozen.json（跑前落盘并记 md5）
# 【判据格 = 5 个】cn_permit / cn_channel / en_base / en_permit / en_channel × 池 zero(253)+nonzero(229)
#   ⇒ 3 起服 × 5 格 × 482 = **7,230 次**（与判据件一致）
# 【额外阳性对照】cn_base（**不在判据格里**，只跑 start1）：包装器对同一 482 清单、同一提示词
#   （p0.BASE_PROMPT）、同一路径 ⇒ 应与 B1 主臂 `B1_zero/nonzero_start1.csv` **逐项一致**。
#   这条不参与任何判定，只用来证明"包装器 == B1 那轮的仪器"。
# 【服务配置】逐条沿用 M.19.17/B1：TP=2 / 端口 8021 / gmem 0.60 / max-model-len 8192 /
#   max-num-seqs 24 / limit-mm-per-prompt '{"image":1}' / trust-remote-code / 不传 mm-processor-kwargs /
#   VLLM_USE_FLASHINFER_SAMPLER=0 / **workers=4**。
# 【安全起停】绝不机器级 pkill；只清本脚本 PID 文件里的 pid，且逐个校验 `/proc/<pid>/cmdline` 含 `--port 8021`（NUL 安全）。
set -u
export PATH=/usr/local/miniconda3/bin:$PATH
TARGET_GPUS=${TARGET_GPUS:-0,1}
export CUDA_VISIBLE_DEVICES=$TARGET_GPUS
export VLLM_USE_FLASHINFER_SAMPLER=0
export GMEM_UTIL=${GMEM_UTIL:-0.60}
PY=/usr/local/miniconda3/bin/python
L=/root/logs/pf_p0a.log
R=/root/p0a
PIDF=/root/pf_p0a.pid
SRV=/root/pf_serve_b1_tp2_8021.sh
PROBE=$R/pf_p0a_probe.py
MAN=/root/pf_pilot/pf_items_dense482.json
SERVED=InternVL3_5-38B-BF16
API=http://127.0.0.1:8021/v1/chat/completions
ARMS="cn_permit cn_channel en_base en_permit en_channel"
mkdir -p /root/logs "$R"
say(){ echo "[$(date +%F_%T)] $*" | tee -a "$L"; }
rows(){ $PY - "$1" <<'EOF'
import csv, io, sys
try: print(len(list(csv.DictReader(io.open(sys.argv[1], encoding='utf-8-sig', newline='')))))
except Exception: print(0)
EOF
}

say "===== P0-A 启动（TP=2 / 端口 8021 / 5 格 × 2 池 × 3 起服 = 7,230 次 + 阳性对照 482）====="
say "判据件 md5=$(md5sum $R/_p0a_criteria_frozen.json 2>/dev/null | awk '{print $1}')"
say "包装器 md5=$(md5sum $PROBE | awk '{print $1}') ｜ 起服脚本 md5=$(md5sum $SRV | awk '{print $1}') ｜ 清单 md5=$(md5sum $MAN | awk '{print $1}')"
say "臂=$ARMS ｜ TARGET_GPUS=$TARGET_GPUS ｜ GMEM_UTIL=$GMEM_UTIL ｜ workers=4"

for g in $(echo "$TARGET_GPUS" | tr ',' ' '); do
  used=$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits -i "$g" 2>/dev/null | tr -d ' ')
  say "GPU${g} 已用 = ${used:-<读不到>} MiB（阈值 2000 MiB）"
  [ -z "$used" ] && { say "!! 读不到 GPU${g} ⇒ 拒绝开跑"; echo PF_P0A_ABORT_BAD_GPU >> "$L"; exit 7; }
  [ "$used" -gt 2000 ] && { say "!! GPU${g} 非空（${used} MiB）⇒ 拒绝开跑、不抢卡"; echo PF_P0A_ABORT_GPU_BUSY >> "$L"; exit 6; }
done

kill_own(){
  if [ -f "$PIDF" ]; then
    for p in $(cat "$PIDF"); do
      if tr '\0' ' ' < /proc/$p/cmdline 2>/dev/null | grep -q -- '--port 8021'; then
        kill "$p" 2>/dev/null; say "已终止本脚本服务 pid=$p（已校验 --port 8021）"
      else
        say "跳过 pid=$p（命令行不含 --port 8021）"
      fi
    done
    rm -f "$PIDF"; sleep 10
  fi
}
kill_own

for S in 1 2 3; do
  say "===== 启动 $S / 3 ====="
  kill_own
  CUDA_VISIBLE_DEVICES=$TARGET_GPUS GMEM_UTIL=$GMEM_UTIL setsid nohup bash "$SRV" \
      > /root/logs/pf_serve_p0a_s${S}.log 2>&1 < /dev/null &
  sleep 20
  pgrep -f -- '--port 8021' > "$PIDF" 2>/dev/null
  say "服务已起 pid=$(cat $PIDF 2>/dev/null | tr '\n' ' ')"
  ok=0
  for i in $(seq 1 100); do
    sleep 10
    curl -sS -m 5 http://127.0.0.1:8021/v1/models 2>/dev/null | grep -q "$SERVED" && { ok=1; break; }
  done
  if [ $ok -ne 1 ]; then
    say "!! 启动 $S 未就绪 ⇒ 停手（真 exit）"
    tail -20 /root/logs/pf_serve_p0a_s${S}.log 2>/dev/null | sed 's/^/    LOG: /' | tee -a "$L"
    kill_own; echo PF_P0A_ABORT_SERVE >> "$L"; exit 4
  fi
  say "启动 $S 就绪（等待 $((i*10))s）"
  grep -a 'Model loading took\|Available KV cache memory\|Maximum concurrency for' \
      /root/logs/pf_serve_p0a_s${S}.log 2>/dev/null | tail -3 | sed 's/^/      /' | tee -a "$L"
  say "  [启动$S] GPU = $(nvidia-smi --query-gpu=index,memory.used --format=csv,noheader | tr '\n' ' ')"

  for arm in $ARMS; do
    for pool in zero nonzero; do
      OUT=$R/P0A_${arm}_${pool}_start${S}.csv
      exp=253; [ "$pool" = nonzero ] && exp=229
      say "开跑 start$S $arm/$pool（期望 $exp 行）"
      $PY -u $PROBE --api $API --model $SERVED --manifest $MAN --pool $pool \
          --arm $arm --start $S --out "$OUT" --workers 4 >> "$L" 2>&1
      N=$(rows "$OUT")
      say "  结束 $arm/$pool -> ${N:-0} 行"
      [ "${N:-0}" -lt $((exp * 95 / 100)) ] && { say "  !! 偏少（<95%）"; echo "PF_P0A_COUNT_LOW_${arm}_${pool}_s${S}" >> "$L"; }
    done
  done

  if [ "$S" = 1 ]; then
    say "--- 阳性对照：cn_base（不在判据格里，仅 start1）---"
    for pool in zero nonzero; do
      OUT=$R/P0A_cn_base_${pool}_start1.csv
      exp=253; [ "$pool" = nonzero ] && exp=229
      $PY -u $PROBE --api $API --model $SERVED --manifest $MAN --pool $pool \
          --arm cn_base --start 1 --out "$OUT" --workers 4 >> "$L" 2>&1
      say "  对照 $arm/$pool -> $(rows "$OUT") 行（期望 $exp）"
    done
  fi

  kill_own
  say "启动 $S 已收服；GPU 现 = $(nvidia-smi --query-gpu=index,memory.used --format=csv,noheader | tr '\n' ' ')"
done

say "--- 产物 ---"
for f in "$R"/P0A_*.csv; do
  [ -f "$f" ] || continue
  say "  $(md5sum "$f" | awk '{print $1}')  $(wc -l < "$f") 行  $f"
done
say "收尾 GPU = $(nvidia-smi --query-gpu=index,memory.used --format=csv,noheader | tr '\n' ' ')"
echo PF_P0A_ALL_DONE >> "$L"
say "===== P0-A 结束（7,230 次 + 482 次对照）====="
