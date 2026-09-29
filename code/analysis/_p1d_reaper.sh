#!/bin/bash
# _p1d_reaper.sh —— 回收"孤儿 VLLM::EngineCore"（否则显存会被永久占住）。
#
# 为什么需要它（实测踩坑，必记）：
#   `p1d_run.sh` / `p1d_run2.sh` 在一族跑完后用 `kill -9 "$SPID"` 停服，`$SPID` 是 `vllm serve` **父进程**。
#   父进程被 -9 杀掉后，它的子进程 `VLLM::EngineCore` **不会被一起杀**，而是被 init 收养（PPID=1），
#   继续持有整份显存（实测：gemma 留 34.7 GB、32B 留 70.9 GB）。端口已 down、`pgrep 'vllm serve'` 也看不到它，
#   所以"服务停了"的日志是**假象**，下一族的 `wait_clear` 会一直等到超时。
#
# 判据（安全）：**PPID == 1 的 `VLLM::EngineCore`** 必然是被遗弃的（它的服务已经不在了）。
#   绝不碰 PPID 指向活着的 `vllm serve` 的引擎——那是在正常服务中的进程。
set -u
L=/root/logs/p1d_reaper.log
echo "[reaper] 启动 $(date +%H:%M:%S)" >> "$L"
while true; do
  for pid in $(ps -eo pid,ppid,comm | awk '$2==1 && $3 ~ /^VLLM::EngineCor/ {print $1}'); do
    echo "[reaper] $(date +%H:%M:%S) 回收孤儿 EngineCore pid=$pid" >> "$L"
    kill -9 "$pid" 2>/dev/null
  done
  sleep 15
done
