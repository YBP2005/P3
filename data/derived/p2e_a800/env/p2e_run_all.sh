#!/bin/bash
# p2e_run_all.sh —— P2-E 一键串起来（**任一步失败即停**，绝不带着未过的闸门往下跑）。
#
# 顺序与理由（不能换序）：
#   G0 自检：估计器必须逐档复现 §M.43 那四行 ⇒ 否则"我的 span 定义"与印值不同源，后面的数没意义
#   G1 约定：输入尺度约定必须与既有 CSRNet ladder 一致 ⇒ 否则两支口径之差会混进"缩放约定之差"
#   density：官方 DM-Count（st_a 182 × mult 五档；副口径六档 + short 四档）
#   detector：yolo11n 整幅 × imgsz 五档（τ 后处理）
#   analyze：出两行 + 六 knob 排序 + 判据
#
# 用法（在 **A800 上**）：bash /root/p3r8_p2e/p2e_run_all.sh
# 纪律：单卡；不机器级 pkill；绝不碰 /root/cvpr_exp；起跑前先确认卡空（另一侧的交接说明要求先打招呼）。
set -u
set -o pipefail   # ★ 否则 python ... | tee 会把失败步骤的退出码吞掉，P2E_ALL_DONE 会掩盖它
PY=/usr/local/miniconda3/bin/python
D=/root/p3r8_p2e/p2e
L=/root/logs/p2e.log
GPUID=${GPUID:-1}
# ★ 不导出 CUDA_VISIBLE_DEVICES：各子脚本自己用 --gpu $GPUID 设定（否则"父设 1、子设 0"会互相矛盾，
#   子进程可能落到另一张卡上）。
used=$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits -i "$GPUID" 2>/dev/null | tr -d ' ')
echo "[precheck] 目标 GPU$GPUID 已用 = ${used:-读不到} MiB（阈值 2000）" | tee -a "$L"
say(){ echo "[$(date +%F_%T)] $*" | tee -a "$L"; }

say "===== P2-E 启动（整幅；无平铺）====="
say "判据件 md5=$(md5sum $D/p2e_criteria_frozen.json | awk '{print $1}')"
say "GPU 现状：$(nvidia-smi --query-gpu=index,memory.used,utilization.gpu --format=csv,noheader | tr '\n' ' ')"

say "--- G0 自检（复现 §M.43 四行）---"
$PY -u $D/p2e_selfcheck_m43.py | tee -a "$L"
[ ${PIPESTATUS[0]} -eq 0 ] || { say "!! G0 未过 ⇒ 停手"; exit 2; }

say "--- G1 缩放约定锁定 ---"
$PY -u $D/p2e_protocol_check.py --ladder /root/p3r8_p2e/ref/csrsta_ladder_st_a.csv --sizes /root/p3r8_p2e/ref/det_st_a_test_yolo11n_whole.csv | tee -a "$L"
[ ${PIPESTATUS[0]} -eq 0 ] || { say "!! G1 未过 ⇒ 停手"; exit 3; }

say "--- density：官方 DM-Count × st_a（主五档 + 副口径）---"
$PY -u $D/p2e_density_run.py --gpu $GPUID --data st_a --protocol mult --values 0.5,0.75,1.0,1.25,1.5 | tee -a "$L" || exit 4
$PY -u $D/p2e_density_run.py --gpu $GPUID --data st_a --protocol mult --values 2.0 \
    --out $D/out/p2e_density_ladder_mult6.csv | tee -a "$L" || exit 4
$PY -u $D/p2e_density_run.py --gpu $GPUID --data st_a --protocol short --values 384,512,768,1024 \
    --out $D/out/p2e_density_ladder_short.csv | tee -a "$L" || exit 4

say "--- detector：yolo11n 整幅 × imgsz 五档 ---"
$PY -u $D/p2e_detector_run.py --gpu $GPUID --imgsz 640,896,1024,1280,1536 | tee -a "$L" || exit 5

say "--- analyze ---"
$PY -u $D/p2e_analyze.py | tee -a "$L" || exit 6

say "--- 产物 md5 ---"
for f in "$D"/out/*.csv "$D"/out/*.json "$D"/out/*.md; do
  [ -f "$f" ] || continue
  say "  $(md5sum "$f" | awk '{print $1}')  $(wc -l < "$f") 行  $f"
done
say "收尾 GPU = $(nvidia-smi --query-gpu=index,memory.used --format=csv,noheader 2>/dev/null | tr '\n' ' ')"
echo P2E_ALL_DONE >> "$L"
say "===== P2-E 结束 ====="
