set -u
L=/root/logs/p1d.log
C3=/root/logs/p1d_cp3.txt
rm -f "$C3"
# ★ 只认"成功路径的结束标记"：P1D_ALL_DONE。**不**匹配 P1D_ABORT*（15:05:11 那次正确拒跑已把
#   P1D_ABORT_GPU_BUSY 写进日志，用 ^P1D_ABORT 会立刻假阳性退出——第一次的 waiter 就是这样早退的）。
for i in $(seq 1 300); do
  if grep -qx 'P1D_ALL_DONE' "$L" 2>/dev/null; then break; fi
  sleep 60
done
{
  echo "== 检查点③ $(date +%F_%T) =="
  echo "结束标记: $(grep -x 'P1D_ALL_DONE' "$L" | tail -1)   ｜ abort 行(可能含旧拒跑): $(grep -c '^P1D_ABORT' "$L")"
  echo "CSV 件数: $(ls /root/p1d/res/P1D_*.csv 2>/dev/null | wc -l) / 66"
  echo "总数据行: $(cat /root/p1d/res/P1D_*.csv 2>/dev/null | wc -l)"
  echo "COUNT_LOW 告警: $(grep -c 'P1D_COUNT_LOW' "$L")"
  echo "起服就绪/收服次数: $(grep -c '就绪' "$L") / $(grep -c '已收服' "$L")"
  echo "GPU: $(nvidia-smi --query-gpu=index,memory.used --format=csv,noheader | tr '\n' ' ')"
  echo "--- 各起服段用时 ---"
  grep -E '===== 起服|已收服' "$L" | tail -8
  echo "--- md5 ---"
  md5sum /root/p1d/res/P1D_*.csv 2>/dev/null
  md5sum /root/p1d/_p1d_criteria_frozen.json
} > "$C3" 2>&1
echo CP3_WRITTEN
