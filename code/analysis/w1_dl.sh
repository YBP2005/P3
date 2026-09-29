#!/bin/bash
# w1_dl.sh — W1 独立家族前瞻验证：**下载阶段**（不占 GPU，可与写方案/判据并行）
#
# 抽样框（W0 实测，见 w0_frame_final.json）：
#   本地已有且未用过：MiniCPM-V-2.6(OpenBMB) / Step3-VL-10B(StepFun) / gemma-4-31B-it(Google)
#   需下载：Idefics3-8B-Llama3(HuggingFace) / deepseek-vl2-tiny(DeepSeek) /
#           Molmo-7B-D-0924(AllenAI) / Phi-4-multimodal-instruct(Microsoft，备选)
# 纪律：逐个下、下了就核对尺寸；单个家族跑完即删（磁盘只有 72 GB 余量）。
set -u
PY=/usr/local/miniconda3/bin/python
L=/root/logs/w1_dl.log
mkdir -p /root/logs /root/w1_models
say() { echo "[$(date +%H:%M:%S)] $*" >> "$L"; }

say "########## W1 下载开始 ##########"
df -h / | tail -1 >> "$L"

# 先下小的两个（6.8 + 16.9 GB），可立刻开始 smoke/跑；大的 Molmo(32 GB) 放最后
$PY /root/w1_dl_model.py deepseek-ai/deepseek-vl2-tiny        /root/w1_models/deepseek-vl2-tiny    >> "$L" 2>&1
say "deepseek-vl2-tiny rc=$? ; $(du -sh /root/w1_models/deepseek-vl2-tiny 2>/dev/null | cut -f1)"
df -h / | tail -1 >> "$L"

$PY /root/w1_dl_model.py HuggingFaceM4/Idefics3-8B-Llama3      /root/w1_models/idefics3-8b         >> "$L" 2>&1
say "idefics3 rc=$? ; $(du -sh /root/w1_models/idefics3-8b 2>/dev/null | cut -f1)"
df -h / | tail -1 >> "$L"

$PY /root/w1_dl_model.py allenai/Molmo-7B-D-0924               /root/w1_models/molmo-7b-d          >> "$L" 2>&1
say "molmo rc=$? ; $(du -sh /root/w1_models/molmo-7b-d 2>/dev/null | cut -f1)"
df -h / | tail -1 >> "$L"

$PY /root/w1_dl_model.py microsoft/Phi-4-multimodal-instruct   /root/w1_models/phi4-mm            >> "$L" 2>&1
say "phi4-mm rc=$? ; $(du -sh /root/w1_models/phi4-mm 2>/dev/null | cut -f1)"

say "########## W1 下载结束 ##########"
df -h / | tail -1 >> "$L"
echo "W1_DL_DONE" >> "$L"
