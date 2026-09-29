#!/bin/bash
# H20 彻底清场。以 `bash /root/killall.sh` 方式调用 —— 脚本自身命令行不含任何
# 被匹配的字符串，故 pkill -f 不会杀掉承载自己的 shell（这一坑今天踩了多次）。
echo "=== 清场前（/proc 直读）==="
/usr/local/miniconda3/bin/python3 - <<'PY'
import os
TG = ['newh20_chain', 'newh20_stage3', 'newh20_fetch_packs', 'newh20_push',
      'fetch_missing', 'finish.sh', 'vllm serve', 'exp.sh', 'queue.py']
n = 0
for p in sorted(os.listdir('/proc')):
    if not p.isdigit():
        continue
    try:
        cl = open('/proc/%s/cmdline' % p, 'rb').read().replace(b'\x00', b' ').decode('utf-8', 'replace')
    except Exception:
        continue
    if any(t in cl for t in TG):
        print('  pid=%s %s' % (p, cl.strip()[:100]))
        n += 1
print('  合计 %d' % n)
PY

echo "=== 执行清除 ==="
for pat in newh20_chain newh20_stage3 newh20_fetch_packs newh20_push fetch_missing finish.sh exp.sh; do
  pkill -9 -f "$pat" 2>/dev/null && echo "  已杀 $pat"
done
pkill -9 -f 'vllm serve' 2>/dev/null && echo "  已杀 vllm serve"
sleep 6
for p in $(nvidia-smi --query-compute-apps=pid --format=csv,noheader 2>/dev/null | tr -d ' '); do
  [ -n "$p" ] && { kill -9 "$p" 2>/dev/null; echo "  已杀显存孤儿 $p"; }
done
sleep 5

echo "=== 清场后（/proc 直读，应为 0）==="
/usr/local/miniconda3/bin/python3 - <<'PY'
import os
TG = ['newh20_chain', 'newh20_stage3', 'newh20_fetch_packs', 'newh20_push',
      'fetch_missing', 'finish.sh', 'vllm serve', 'exp.sh', 'queue.py']
n = 0
for p in sorted(os.listdir('/proc')):
    if not p.isdigit():
        continue
    try:
        cl = open('/proc/%s/cmdline' % p, 'rb').read().replace(b'\x00', b' ').decode('utf-8', 'replace')
    except Exception:
        continue
    if any(t in cl for t in TG):
        print('  残留 pid=%s %s' % (p, cl.strip()[:100]))
        n += 1
print('  残留合计 %d' % n)
PY
echo "=== 显存 ==="
nvidia-smi --query-gpu=memory.used --format=csv,noheader
echo KILLALL_DONE
