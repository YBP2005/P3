#!/bin/bash
# 统一补齐：等所有下载进程退出后，把 AWQ-8bit 与 72B 都复核到"分片齐全"。
# 依赖已改进的下载器（内含校验重试轮）。
# 目的：避免 v4 以为权重就绪、起服务时因缺分片失败而白白跳过一个实验格。
PY=/usr/local/miniconda3/bin/python3
L=/root/logs/repair_all.log
say() { echo "[$(date +%H:%M:%S)] $*" | tee -a "$L"; }

verify() {  # $1 = 模型目录；校验 index 引用的分片是否齐全
  $PY - "$1" <<'PYEOF' | tee -a "$L"
import json, os, sys
d = sys.argv[1]
idx = os.path.join(d, 'model.safetensors.index.json')
if not os.path.exists(idx):
    print('   %s: 缺 index.json' % d); raise SystemExit(1)
need = sorted(set(json.load(open(idx))['weight_map'].values()))
miss = [f for f in need if not os.path.exists(os.path.join(d, f))
        or os.path.getsize(os.path.join(d, f)) == 0]
print('   %s: index 引用 %d 个分片，缺失/空 %d 个' % (os.path.basename(d), len(need), len(miss)))
for f in miss:
    print('      !! %s' % f)
raise SystemExit(1 if miss else 0)
PYEOF
}

say "等全部下载进程退出"
while pgrep -f 'h20_dl_model' > /dev/null 2>&1; do sleep 30; done
say "下载进程已全部退出，开始复核"

A8=/root/models/Qwen3-VL-32B-Instruct-AWQ-8bit
M72=/root/models/Qwen2.5-VL-72B-Instruct-AWQ

for rnd in 1 2 3; do
  say "=== 第 $rnd 轮 ==="
  say "复核 AWQ-8bit:"; verify "$A8" && A8OK=1 || A8OK=0
  say "复核 72B:";      verify "$M72" && M72OK=1 || M72OK=0
  if [ "${A8OK:-0}" = "1" ] && [ "${M72OK:-0}" = "1" ]; then
    say "两者分片均已齐全，结束复核"; break
  fi
  [ "${A8OK:-0}" = "0" ] && { say "补齐 AWQ-8bit"; \
    $PY -u /root/h20_dl_model.py cyankiwi/Qwen3-VL-32B-Instruct-AWQ-8bit "$A8" >> "$L" 2>&1; }
  [ "${M72OK:-0}" = "0" ] && { say "补齐 72B"; \
    $PY -u /root/h20_dl_model.py Qwen/Qwen2.5-VL-72B-Instruct-AWQ "$M72" >> "$L" 2>&1; }
done

say "=== 最终复核 ==="
verify "$A8"; verify "$M72"
df -h / | tail -1 | tee -a "$L"
echo REPAIR_ALL_DONE >> "$L"
