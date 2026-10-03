#!/bin/bash
# p1n_run.sh —— P1-D 编排（**只在拿到明确的卡模式与 go 之后才允许执行**）。
#
# 顺序：GPU 预检 → 3 次全新起服 ×（8 档 × 2 域 × 250 项）→ 收工核验
# 纪律：**只用指定的一张卡**（GPUID，默认 1）；GPU 预检 >2000 MiB 就拒绝开跑、不抢卡；
#       **绝不机器级 pkill**，只杀本脚本 PID 文件里的、且 /proc/<pid>/cmdline 含 --port 8013 的进程；
#       **绝不进 /root/cvpr_exp**；每步的退出码都要能传出来（set -o pipefail，上一轮 `| tee` 吞过码）。
#
# 用法（**等 go**）：GPUID=1 bash /root/p1n/p1n_run.sh
set -u
set -o pipefail
export PATH=/usr/local/miniconda3/bin:$PATH
export VLLM_USE_FLASHINFER_SAMPLER=0
PY=/usr/local/miniconda3/bin/python
GPUID=${GPUID:-1}
D=/root/p1n
RES=$D/res
L=/root/logs/p1n.log
PIDF=/root/p1n.pid
SRV=/root/pf_serve_awq4bit_8013.sh
PROBE=$D/p1n_probe.py
SERVED=Qwen3-VL-32B-Instruct-AWQ
API=http://127.0.0.1:8013/v1/chat/completions
BUDGETS="0 104856 145698 200000 202447 281300 390867 400000 543118 754655 800000"
DOMAINS="mtdc gwhd"
mkdir -p "$RES" /root/logs
say(){ echo "[$(date +%F_%T)] $*" | tee -a "$L"; }

say "===== P1-D 启动（单卡 GPU$GPUID；8 档 × 2 域 × 250 项 × 3 起服 = 12,000 次）====="
say "判据件 md5=$(md5sum $D/_p1n_criteria_frozen.json | awk '{print $1}')"
say "探针 md5=$(md5sum $PROBE | awk '{print $1}') ｜ 起服脚本 md5=$(md5sum $SRV | awk '{print $1}')"

used=$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits -i "$GPUID" 2>/dev/null | tr -d ' ')
say "GPU$GPUID 已用 = ${used:-<读不到>} MiB（阈值 2000）"
[ -z "$used" ] && { say "!! 读不到 GPU$GPUID ⇒ 拒绝开跑"; echo P1N_ABORT_BAD_GPU >> "$L"; exit 7; }
[ "$used" -gt 2000 ] && { say "!! GPU$GPUID 非空（${used} MiB）⇒ 不抢卡，停手"; echo P1N_ABORT_GPU_BUSY >> "$L"; exit 6; }

kill_own(){
  if [ -f "$PIDF" ]; then
    for p in $(cat "$PIDF"); do
      if tr '\0' ' ' < /proc/$p/cmdline 2>/dev/null | grep -q -- '--port 8013'; then
        kill "$p" 2>/dev/null; say "已终止本脚本服务 pid=$p（已校验 --port 8013）"
      else
        say "跳过 pid=$p（命令行不含 --port 8013）"
      fi
    done
    rm -f "$PIDF"; sleep 8
  fi
}
kill_own

for S in 1 2 3; do
  say "===== 起服 $S / 3 ====="
  kill_own
  CUDA_VISIBLE_DEVICES=$GPUID GMEM_UTIL=0.85 setsid nohup bash "$SRV" > /root/logs/p1n_serve_s${S}.log 2>&1 < /dev/null &
  sleep 20
  pgrep -f -- '--port 8013' > "$PIDF" 2>/dev/null
  ok=0
  for i in $(seq 1 90); do
    sleep 10
    curl -sS -m 5 http://127.0.0.1:8013/v1/models 2>/dev/null | grep -q "$SERVED" && { ok=1; break; }
  done
  if [ $ok -ne 1 ]; then
    say "!! 起服 $S 未就绪 ⇒ 停手（真 exit）"
    tail -20 /root/logs/p1n_serve_s${S}.log 2>/dev/null | sed 's/^/    LOG: /' | tee -a "$L"
    kill_own; echo P1N_ABORT_SERVE >> "$L"; exit 4
  fi
  say "起服 $S 就绪（等待 $((i*10))s）"
  say "  [起服$S] GPU = $(nvidia-smi --query-gpu=index,memory.used --format=csv,noheader | tr '\n' ' ')"

  for dom in $DOMAINS; do
    case $dom in
      mtdc) IMG=/root/mtdc/images ;;   # 直接用原目录，不复制
      gwhd) IMG=/root/p1d/data/gwhd/images ;;
    esac
    for b in $BUDGETS; do
      OUT=$RES/P1N_${dom}_b${b}_s${S}.csv
      say "开跑 start$S $dom b=$b（期望 250 行）"
      $PY -u $PROBE --api $API --model $SERVED --items /root/p1d/data/sample_${dom}.csv \
          --domain $dom --budget $b --start $S --imgdir "$IMG" --out "$OUT" --workers 4 >> "$L" 2>&1
      rc=$?
      [ $rc -ne 0 ] && { say "!! 探针退出码 $rc（$dom b=$b s$S）⇒ 停手"; echo "P1N_ABORT_PROBE_RC rc=$rc" >> "$L"; exit 5; }
      n=$($PY - "$OUT" <<'EOF'
import csv, io, sys
try: print(len(list(csv.DictReader(io.open(sys.argv[1], encoding='utf-8-sig', newline='')))))
except Exception: print(0)
EOF
)
      say "  结束 $dom b=$b -> ${n:-0} 行"
      [ "${n:-0}" -lt 238 ] && { say "  !! 偏少（<95% of 250）"; echo "P1N_COUNT_LOW_${dom}_b${b}_s${S}" >> "$L"; }
    done
  done
  kill_own
  say "起服 $S 已收服；GPU 现 = $(nvidia-smi --query-gpu=index,memory.used --format=csv,noheader | tr '\n' ' ')"
done

say "--- 产物 ---"
for f in "$RES"/P1N_*.csv; do
  [ -f "$f" ] || continue
  say "  $(md5sum "$f" | awk '{print $1}')  $(wc -l < "$f") 行  $f"
done
say "收尾 GPU = $(nvidia-smi --query-gpu=index,memory.used --format=csv,noheader | tr '\n' ' ')"
echo P1N_ALL_DONE >> "$L"
say "===== P1-D 结束（12,000 次）====="
