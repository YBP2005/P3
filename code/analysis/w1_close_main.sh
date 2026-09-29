#!/bin/bash
# w1_close_main.sh — 主面板**如实收尾**并解除后续队列的等待。
#
# 为什么需要：
#   ① 备选家族 Phi-4-multimodal 的**关键适配器在镜像上取不到**——`vision-lora/adapter_model.safetensors`
#      （922 MB）与 `vision-lora`/`speech-lora` 的 tokenizer/adapter 配置两轮重试后仍是 0 字节。
#      缺 vision-lora 的 Phi-4-mm 不是可用的**视觉**受试，故弃用（理由写入 frame 表）。
#   ② 主驱动的等待条件是"下载器打印成功行"，而下载器因上述失败**永不打印** ⇒ 会白等最长 5 小时，
#      把回收队列一起卡住。本脚本结束这个等待。
# 诚实性：本脚本**不伪造下载器的成功**，而是向 w1_run.log 追加自述行（说明这是收尾脚本写入、
#   以及为什么），再写 W1_PANEL_DONE 解除后续队列等待。已完成家族的产物不动、不删。
set -u
L=/root/logs/w1_run.log
C=/root/logs/w1_close_main.log
R=/root/w1_results
mkdir -p "$R"
say() { echo "[$(date +%H:%M:%S)] $*" | tee -a "$C" | tee -a "$L"; }

say "===== 主面板收尾（w1_close_main.sh）====="

# ① 停掉已无望的 Phi-4 下载与卡在等待中的主驱动
pkill -f "w1_dl_model.py microsoft/Phi-4" 2>/dev/null && say "已停止 Phi-4 下载进程" || say "Phi-4 下载进程已不在"
pkill -f "bash /root/w1_run.sh" 2>/dev/null && say "已停止等待中的主驱动" || say "主驱动已不在"
sleep 3
pkill -f "curl .*phi4-mm" 2>/dev/null

# ② 盘点主面板实际成果（不删任何产物）
say "主面板家族产物盘点（零池文件数 / 非零池文件数）："
for f in $(ls "$R/zero" 2>/dev/null | sed -E 's/^e1_(.+)_(st_a|ucf|visdrone|aitod)_.*$/\1/' | sort -u); do
  z=$(ls "$R"/zero/e1_${f}_* 2>/dev/null | wc -l); n=$(ls "$R"/nonzero/e1_${f}_* 2>/dev/null | wc -l)
  say "  $f  零池 $z / 非零池 $n"
done

# ③ 如实记录弃用理由
say "备选 Phi-4-multimodal-instruct 弃用：vision-lora(738MB)/speech-lora(922MB) 适配器与相关配置在 ModelScope 两轮重试后仍为 0 字节 ⇒ 缺视觉适配器，不构成可用视觉受试。"
say "后续由回收队列补齐：Step3-VL-10B(trust_remote_code) / MiniCPM-V-4_5 / deepseek-vl2-tiny(timm) / Molmo-7B-D(trust_remote_code)。"

# ④ 解除等待（写清来源）
say "W1_PANEL_DONE（由 w1_close_main.sh 写入：主面板已收尾，非下载器信号）"
