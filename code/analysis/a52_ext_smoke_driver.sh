#!/bin/bash
# A5-2 ext: generic serve+smoke driver (one build at a time, single GPU).
# Records engine load time, then runs the frozen-stimulus smoke, then stops the
# server BY PID after verifying /proc/<pid>/cmdline. Never uses pkill/pgrep.
#
# env: SRV=serve script  PORT=  SERVED=  TAG=  [GMEM_UTIL=]
set -u
set -o pipefail
export PATH=/usr/local/miniconda3/bin:$PATH
export VLLM_USE_FLASHINFER_SAMPLER=0
PY=/usr/local/miniconda3/bin/python

SRV=${SRV:?}
PORT=${PORT:?}
SERVED=${SERVED:?}
TAG=${TAG:?}
GMEM_UTIL=${GMEM_UTIL:-}
OUT=/root/a52_ext_smoke
mkdir -p "$OUT"
LOG=$OUT/serve_${TAG}_${PORT}.log
PIDF=$OUT/${TAG}.pid

say(){ echo "[$(date +%F_%T)] $*"; }

pids_with_port(){   # $1 = port ; read-only /proc scan, no pgrep/pkill
  local port="$1" p
  for p in /proc/[0-9]*; do
    p=${p#/proc/}
    [ -r "/proc/$p/cmdline" ] || continue
    if tr '\0' ' ' < "/proc/$p/cmdline" 2>/dev/null | grep -q -- "--port $port"; then echo "$p"; fi
  done
  return 0
}
gpu_used(){ nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits -i 0 2>/dev/null | tr -d ' \r'; }

say "=== driver TAG=$TAG PORT=$PORT SRV=$SRV ==="
say "serve md5 = $(md5sum "$SRV" | awk '{print $1}')"

busy=$(pids_with_port "$PORT")
[ -n "$busy" ] && { say "!! ABORT: port $PORT already served by PID(s): $busy"; exit 3; }
u=$(gpu_used)
[ "${u:-0}" -gt 2000 ] && { say "!! ABORT: GPU busy ${u} MiB > 2000 MiB"; exit 3; }
say "pre-check OK: port free, gpu=${u} MiB"

T0=$(date +%s.%N)
CUDA_VISIBLE_DEVICES=0 nohup bash "$SRV" > "$LOG" 2>&1 < /dev/null &
LPID=$!
say "launched serve launcher pid=$LPID -> $LOG"

SPID=""
for i in $(seq 1 90); do
  SPID=$(pids_with_port "$PORT")
  [ -n "$SPID" ] && break
  sleep 2
done
if [ -z "$SPID" ]; then say "!! ABORT: no listener on $PORT after 180 s"; tail -40 "$LOG"; exit 4; fi
echo "$SPID" > "$PIDF"
say "serve PID=$SPID cmdline-check: $(tr '\0' ' ' < /proc/$SPID/cmdline | cut -c1-120)"

OK=0
for i in $(seq 1 900); do
  code=$(curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:$PORT/health" 2>/dev/null || true)
  [ "$code" = "200" ] && { OK=1; break; }
  # bail out early if the process died
  [ -d "/proc/$SPID" ] || { say "!! serve process $SPID died"; break; }
  sleep 2
done
T1=$(date +%s.%N)
LOAD_S=$(awk -v a="$T0" -v b="$T1" 'BEGIN{printf "%.1f", b-a}')
say "HEALTH_OK=$OK LOAD_S=$LOAD_S"
if [ "$OK" != "1" ]; then say "!! ABORT: /health never 200"; tail -60 "$LOG"; exit 5; fi

PORT="$PORT" SERVED="$SERVED" OUTDIR="$OUT" TAG="$TAG" LOAD_S="$LOAD_S" \
  "$PY" /root/a52_ext_smoke.py
RC=$?
say "smoke rc=$RC"

# ---- stop server: BY PID ONLY, after verifying cmdline ----
if [ -n "$SPID" ] && [ -r "/proc/$SPID/cmdline" ]; then
  c=$(tr '\0' ' ' < "/proc/$SPID/cmdline")
  case "$c" in
    *"--port $PORT"*) say "stopping PID=$SPID (cmdline verified) via SIGTERM"; kill -TERM "$SPID" ;;
    *) say "!! REFUSE to kill PID=$SPID: cmdline does not show --port $PORT" ;;
  esac
else
  say "PID $SPID already gone"
fi
for i in $(seq 1 300); do
  u=$(gpu_used)
  [ "${u:-9999}" -le 300 ] && { say "GPU back to ${u} MiB after $((i*2)) s"; break; }
  sleep 2
done
say "final gpu_used=$(gpu_used) MiB | leftover port pids: $(pids_with_port "$PORT" | tr '\n' ' ')"
rm -f "$PIDF"
say "DRIVER_DONE $TAG rc=$RC load_s=$LOAD_S"
exit $RC
