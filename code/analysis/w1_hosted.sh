#!/bin/bash
# w1_hosted.sh — W2 闭源/托管端点的驱动（零 GPU）。
# ★ 关键：环境变量必须与调用**同一个 shell**。此前我把 export 与 python 分成两行交给
#   逐行执行的通道，结果 export 丢失、探针仍打默认 DashScope 端点 ⇒ 全体 401（白等 3 分钟）。
#   故一切写进本脚本一次执行。
set -u
export BAILIAN_API=https://api.ofox.io/v1/chat/completions
export DASHSCOPE_API_KEY=<REDACTED-API-KEY>
PY=/usr/local/miniconda3/bin/python
L=/root/logs/w1_hosted.log
mkdir -p /root/w1_results/hosted /root/logs
say() { echo "[$(date +%H:%M:%S)] $*" | tee -a "$L"; }

say "端点=$BAILIAN_API"
say "########## ① 冒烟门：每模型 2 条（base 臂）##########"
$PY /root/w1_hosted_probe.py --smoke --arms base --domains st_a --workers 2 >> "$L" 2>&1
say "冒烟结果："
for f in /root/w1_results/hosted/*__st_a__base.csv; do
  [ -f "$f" ] || continue
  ok=$($PY - "$f" <<'PYX'
import csv, io, sys
rows = list(csv.DictReader(io.open(sys.argv[1], encoding='utf-8-sig')))
print(sum(1 for r in rows if str(r.get('parse_ok','')).strip() == '1'))
PYX
)
  say "  $(basename $f)：可解析 $ok"
done

say "########## ② 正跑：st_a + ucf 零池，arms base,permit ##########"
$PY /root/w1_hosted_probe.py --arms base,permit --domains st_a,ucf --n 150 --workers 4 >> "$L" 2>&1
say "产物：$(ls /root/w1_results/hosted | wc -l) 个文件"
echo "W1_HOSTED_DONE" >> "$L"
say "########## W2 结束 ##########"
