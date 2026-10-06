#!/bin/bash
# A5-2 ext: external PID-file watchdog for the b1 (FP8) build.
# The published /root/a52/_pidfix.sh (md5 6aa39ec6b475a14aa67218baa935b726) is hardcoded to
# ports 8013/8012 and /root/a52/a52.pid, so it cannot maintain a52_run_v2.sh's b1 PID file
# (/root/a52/a52_b1.pid, port 8015). This is an equivalent, b1-scoped watchdog -- the frozen
# file is NOT modified. It only rewrites the runtime PID file from live /proc entries; it never
# starts/stops anything and never uses pkill.
set -u
PIDF=/root/a52/a52_b1.pid
PORT=8015
while true; do
  live=""
  for p in /proc/[0-9]*; do
    p=${p#/proc/}
    [ -r "/proc/$p/cmdline" ] || continue
    cl=$(tr '\0' ' ' < "/proc/$p/cmdline" 2>/dev/null)
    case "$cl" in *"--port $PORT"*) live="$live $p";; esac
  done
  [ -n "$live" ] && printf '%s\n' $live > "$PIDF"
  sleep 4
done
