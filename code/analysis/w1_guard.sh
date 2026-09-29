#!/bin/bash
# w1_guard.sh — 权重防删守卫（软链法）。
#
# 背景（本次真实损失）：驱动的收尾会 `rm -rf` 已跑完家族的下载权重。我原先只给 deepseek-vl2 做了
# 软链保护，结果 **idefics3-8b（16 GB）在普查跑完被删**，导致它后面的 FSC 示例臂（W1d）还得重下。
# 现在对尚未跑完的下载家族全部加保护：
#   把目录 mv 到 /root/w1_keep/<name>，再在原位置留**软链**。
#   实测 `rm -rf <symlink>` 只删链接、不删目标（已在本机验证 TARGET_SURVIVED）⇒ 权重活下来。
set -u
L=/root/logs/w1_guard.log
say() { echo "[$(date +%H:%M:%S)] $*" | tee -a "$L"; }
mkdir -p /root/w1_keep

guard() {   # guard <model_id> <path>
  local MID=$1 MP=$2 i nm
  nm=$(basename "$MP")
  for i in $(seq 1 300); do
    if grep -q "→ $MID 成功" /root/logs/w1_dl.log /root/logs/w1_dl2.log 2>/dev/null; then
      if [ -d "$MP" ] && [ ! -L "$MP" ]; then
        mv "$MP" "/root/w1_keep/$nm" 2>/dev/null && ln -s "/root/w1_keep/$nm" "$MP" \
          && say "已保护：$MP -> /root/w1_keep/$nm（$(du -sh /root/w1_keep/$nm 2>/dev/null | cut -f1)）" \
          || say "!! 保护 $MP 失败"
      fi
      return 0
    fi
    sleep 30
  done
  say "等待超时：$MID"
}

guard allenai/Molmo-7B-D-0924          /root/w1_models/molmo-7b-d
guard OpenBMB/MiniCPM-V-4_5            /root/w1_models/minicpm-v-4_5
guard microsoft/Phi-4-multimodal-instruct /root/w1_models/phi4-mm
say "守卫结束"
echo "W1_GUARD_DONE" >> "$L"
