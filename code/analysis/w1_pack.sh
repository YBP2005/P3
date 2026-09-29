#!/bin/bash
# w1_pack.sh — 流水线结束后自动打包：一次拉取即可，避免逐目录 SFTP 与"半截状态"。
#
# 为什么预置：本地可能断网，恢复后逐目录拉取既慢又容易只拉到一部分。
#   本脚本在远端等 W1_RECOVER3_DONE，然后把 **全部产物 + 全部日志 + 判据 + 脚本** 打成一个 tar，
#   并打印 md5 与大小；恢复后只需拉这一个文件并核对 md5 即可确认完整性。
set -u
L=/root/logs/w1_pack.log
say() { echo "[$(date +%H:%M:%S)] $*" | tee -a "$L"; }

say "等待 W1_RECOVER3_DONE …"
for i in $(seq 1 300); do
  grep -q W1_RECOVER3_DONE /root/logs/w1_recover3.log 2>/dev/null && break
  sleep 60
done
say "流水线已结束（或等待超时）⇒ 开始打包"

# 收尾前把最后可能残留的服务清掉并确认显存归零（本轮所有服务都应由各段自行 gpu_clear）
pkill -9 -i -f vllm 2>/dev/null; pkill -9 -f resource_tracker 2>/dev/null; sleep 3
say "GPU 现值：$(nvidia-smi --query-gpu=memory.used --format=csv,noheader)"

cd /root
tar --exclude='*.part' -czf /root/w1_bundle.tar.gz \
  w1_results logs/w1_*.log w1_prereg.json w1_prereg.md5 \
  w1_run.sh w1_recover.sh w1_recover2.sh w1_recover3.sh w1_fsc_run.sh w1_fsc_late.sh \
  w1_guard.sh w1_hosted.sh w1_hosted_probe.py w1_fsc_probe.py w1_smoke_count.py w1_dl.sh w1_dl2.sh \
  2>/dev/null
say "打包完成：$(du -h /root/w1_bundle.tar.gz | cut -f1)  $(md5sum /root/w1_bundle.tar.gz | cut -d' ' -f1)"
say "产物计数：zero=$(ls /root/w1_results/zero | wc -l) nonzero=$(ls /root/w1_results/nonzero | wc -l) fsc=$(ls /root/w1_results/fsc 2>/dev/null | wc -l) hosted=$(ls /root/w1_results/hosted 2>/dev/null | wc -l)"
echo "W1_PACK_DONE" >> "$L"
