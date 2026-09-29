#!/bin/bash
# A5 追加实验（复用消融留下的 gemma3-12b serve，避免重新加载 210 s）：
#  ① 机制对照：enum（要求逐项枚举，只给数字字段）/ enumAbstain（同样枚举 + 给 abstain 出口）/ locate
#     —— 检验 E2 的"门是 abstain 词位、不是枚举要求"这条机制在**新家族**上是否复现。
#  ② 尺度上探：imgsz=1536（与已做的 640、native 构成尺度阶梯）。
#  ③ 确定性：同一条件 reps=3（温度 0），落在**独立目录**，避免污染主数据。
set -u
export BAILIAN_API=http://127.0.0.1:8000/v1/chat/completions
export DASHSCOPE_API_KEY=dummy
PY=/usr/local/miniconda3/bin/python
N=gemma3-12b
L=/root/logs/a5_extra.log
mkdir -p /root/logs /root/e1_results_ablate /root/e1_results_reps
say() { echo "[$(date +%H:%M:%S)] $*" >> "$L"; }

say "########## A5 追加实验开始 ##########"
if ! curl -sf -m 5 -o /dev/null http://127.0.0.1:8000/v1/models; then
  say "  !! 复用失败：8000 端口没有服务，需先起服。中止。"; exit 1
fi
say "  复用现有 serve（$N）"

# ① 机制对照臂（用主仪器 19e，输出进主目录，臂名不冲突）
for ds in st_a ucf visdrone; do
  say "== 机制臂 enum,enumAbstain,locate / $ds 零池 =="
  t0=$(date +%s)
  $PY /root/19e_probe_multi.py --model "$N" --arms enum,enumAbstain,locate \
      --ds "$ds" --n 150 --workers 8 --pool zero >> "$L" 2>&1
  say "   rc=$? 用时 $(( $(date +%s) - t0 ))s"
done

# ② 尺度上探 1536
for ds in st_a ucf; do
  say "== 尺度 s1536 / $ds 零池 3 臂 =="
  t0=$(date +%s)
  $PY /root/19f_probe_ablation.py --model "$N" --arms base,permit,channel \
      --ds "$ds" --n 150 --workers 8 --pool zero --imgsz 1536 \
      --outdir /root/e1_results_ablate >> "$L" 2>&1
  say "   rc=$? 用时 $(( $(date +%s) - t0 ))s"
done

# ③ 确定性 reps=3（独立目录）
say "== 确定性 reps=3 / st_a 零池 base,permit =="
t0=$(date +%s)
$PY /root/19f_probe_ablation.py --model "$N" --arms base,permit --reps 3 \
    --ds st_a --n 60 --workers 8 --pool zero --outdir /root/e1_results_reps >> "$L" 2>&1
say "   rc=$? 用时 $(( $(date +%s) - t0 ))s"

say "追加完成：ablate $(ls /root/e1_results_ablate | wc -l) 个、reps $(ls /root/e1_results_reps | wc -l) 个"
say "########## A5 追加实验结束 ##########"
echo "A5_EXTRA_DONE" >> "$L"
