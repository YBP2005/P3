#!/bin/bash
# 72B 权重补齐：等当前下载进程退出后，再跑一遍下载器（幂等：按大小跳过已完整的文件，
# 只补因瞬时网络失败而尺寸不符的分片）。日志里已出现
#   !! model-00001-of-00011.safetensors 期望 3979075232 实得 0
# 若不补，v4 起 72B 服务时会因缺分片而失败。
PY=/usr/local/miniconda3/bin/python3
L=/root/logs/dl_repair72b.log
say() { echo "[$(date +%H:%M:%S)] $*" | tee -a "$L"; }

say "等 72B 下载进程退出"
while pgrep -f 'h20_dl_model' > /dev/null 2>&1; do sleep 30; done
say "下载进程已退出，开始补齐校验"

for i in 1 2 3; do
  say "第 $i 轮补齐"
  $PY -u /root/h20_dl_model.py Qwen/Qwen2.5-VL-72B-Instruct-AWQ \
    /root/models/Qwen2.5-VL-72B-Instruct-AWQ >> "$L" 2>&1
  if grep -q 'Qwen2.5-VL-72B-Instruct-AWQ 成功' "$L" && ! grep -q '!!' "$L"; then
    say "  无失败项，补齐完成"; break
  fi
  sleep 10
done

# 复验：分片数与 index 是否一致
say "=== 分片复验 ==="
$PY - <<'PY' | tee -a "$L"
import json, os
d = '/root/models/Qwen2.5-VL-72B-Instruct-AWQ'
idx = os.path.join(d, 'model.safetensors.index.json')
if not os.path.exists(idx):
    print('  缺 index.json'); raise SystemExit
need = sorted(set(json.load(open(idx))['weight_map'].values()))
bad = []
for f in need:
    p = os.path.join(d, f)
    if not os.path.exists(p):
        bad.append((f, '缺失'))
print('  index 引用分片 %d 个' % len(need))
for f, why in bad:
    print('   !! %s %s' % (f, why))
if not bad:
    print('  => 全部分片就位')
PY
du -sh /root/models/Qwen2.5-VL-72B-Instruct-AWQ 2>/dev/null | tee -a "$L"
df -h / | tail -1 | tee -a "$L"
echo DL_REPAIR72B_DONE >> "$L"
