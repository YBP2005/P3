#!/bin/bash
# 统一补齐 v2 —— 修掉 v1 的两个 bug：
#   bug1: 校验只查"缺失/0字节"，漏过**截断文件**（AWQ-8bit 的 model-00003 是 598MB/4902MB）
#   bug2: `verify | tee` 让管道返回 tee 的退出码(0)，导致判定恒为"齐全"，循环第 1 轮就退出、
#         从未调用下载器（日志里出现"两者分片均已齐全"而 72B 明明缺一个分片）
# v2 做法：用 verify_model.py（按 hub 清单的期望尺寸逐文件比对），
#          **先把输出写文件、再 cat**，绝不把判定用的退出码丢进管道。
PY=/usr/local/miniconda3/bin/python3
L=/root/logs/repair_all2.log
say() { echo "[$(date +%H:%M:%S)] $*" | tee -a "$L"; }

A8_ID='cyankiwi/Qwen3-VL-32B-Instruct-AWQ-8bit'
A8_DIR=/root/models/Qwen3-VL-32B-Instruct-AWQ-8bit
M72_ID='Qwen/Qwen2.5-VL-72B-Instruct-AWQ'
M72_DIR=/root/models/Qwen2.5-VL-72B-Instruct-AWQ

check() {  # $1 model_id $2 dir → 退出码即结论；输出另存文件再打印
  local OUT=/root/logs/_verify.tmp
  $PY /root/verify_model.py "$1" "$2" > "$OUT" 2>&1
  local RC=$?
  cat "$OUT" >> "$L"
  cat "$OUT"
  return $RC
}

say "等其它下载进程退出"
while pgrep -f 'h20_dl_model' > /dev/null 2>&1; do sleep 20; done
say "开始复核（按期望尺寸）"

for rnd in 1 2 3; do
  say "=== 第 $rnd 轮 ==="
  check "$A8_ID" "$A8_DIR"; A8RC=$?
  check "$M72_ID" "$M72_DIR"; M72RC=$?
  say "  本轮结论：AWQ-8bit rc=$A8RC，72B rc=$M72RC（0=尺寸全对）"
  if [ "$A8RC" = "0" ] && [ "$M72RC" = "0" ]; then
    say "两者尺寸全部正确，补齐完成"
    break
  fi
  if [ "$A8RC" != "0" ]; then
    say "补齐 AWQ-8bit（下载器含校验重试轮，会先删坏文件）"
    $PY -u /root/h20_dl_model.py "$A8_ID" "$A8_DIR" >> "$L" 2>&1
  fi
  if [ "$M72RC" != "0" ]; then
    say "补齐 72B"
    $PY -u /root/h20_dl_model.py "$M72_ID" "$M72_DIR" >> "$L" 2>&1
  fi
done

say "=== 最终复核 ==="
check "$A8_ID" "$A8_DIR"; A8RC=$?
check "$M72_ID" "$M72_DIR"; M72RC=$?
say "  最终：AWQ-8bit rc=$A8RC，72B rc=$M72RC"
df -h / | tail -1 | tee -a "$L"
if [ "$A8RC" = "0" ] && [ "$M72RC" = "0" ]; then
  echo REPAIR_ALL2_OK >> "$L"
else
  echo REPAIR_ALL2_INCOMPLETE >> "$L"
fi
