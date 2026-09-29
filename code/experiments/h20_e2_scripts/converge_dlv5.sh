#!/bin/bash
# 收敛 dl_v5 到恰好一个实例 + 用**尺寸精确**校验核实 AWQ-8bit 与 72B
echo "=== ① 当前下载实例 ==="
/usr/local/miniconda3/bin/python3 - <<'PY'
import os, time
n = 0
for p in sorted(os.listdir('/proc')):
    if not p.isdigit():
        continue
    try:
        cl = open('/proc/%s/cmdline' % p, 'rb').read().replace(b'\x00', b' ').decode('utf-8', 'replace').strip()
    except Exception:
        continue
    if 'h20_dl_model' in cl or 'h20_dl_v5' in cl:
        try:
            t0 = time.strftime('%H:%M:%S', time.localtime(os.stat('/proc/%s' % p).st_ctime))
        except Exception:
            t0 = '?'
        print('  %s pid=%-7s %s' % (t0, p, cl[:95]))
        n += 1
print('  合计 %d' % n)
PY

echo
echo "=== ② 只保留最早的一个 dl_v5（连同其子进程），其余杀掉 ==="
# 找最早启动的 h20_dl_v5.sh 的 pid
KEEP=$(ls -td /proc/[0-9]* 2>/dev/null | while read d; do
  p=${d#/proc/}
  cl=$(tr '\0' ' ' < "$d/cmdline" 2>/dev/null)
  case "$cl" in *h20_dl_v5.sh*) echo "$p $(stat -c %Y "$d" 2>/dev/null)";; esac
done | sort -k2 -n | head -1 | awk '{print $1}')
echo "  保留 dl_v5 pid=$KEEP"
/usr/local/miniconda3/bin/python3 - "$KEEP" <<'PY'
import os, signal, sys, time
keep = sys.argv[1].strip()
# 杀掉除 keep 之外的所有 h20_dl_v5.sh 与 h20_dl_model.py
for p in sorted(os.listdir('/proc')):
    if not p.isdigit() or p == keep:
        continue
    try:
        cl = open('/proc/%s/cmdline' % p, 'rb').read().replace(b'\x00', b' ').decode('utf-8', 'replace')
    except Exception:
        continue
    if 'h20_dl_v5.sh' in cl or 'h20_dl_model' in cl:
        try:
            os.kill(int(p), signal.SIGKILL)
            print('  已杀 pid=%s %s' % (p, cl.strip()[:80]))
        except Exception as ex:
            print('  杀 %s 失败 %s' % (p, ex))
        time.sleep(0.3)
PY
sleep 5
echo "=== ③ 收敛后实例 ==="
/usr/local/miniconda3/bin/python3 - <<'PY'
import os
n = 0
for p in sorted(os.listdir('/proc')):
    if not p.isdigit():
        continue
    try:
        cl = open('/proc/%s/cmdline' % p, 'rb').read().replace(b'\x00', b' ').decode('utf-8', 'replace').strip()
    except Exception:
        continue
    if 'h20_dl_model' in cl or 'h20_dl_v5' in cl:
        print('  pid=%-7s %s' % (p, cl[:95]))
        n += 1
print('  合计 %d（应为 1 个 shell + 至多 1 个 python）' % n)
PY

echo
echo "=== ④ 尺寸精确校验（弱校验会漏掉截断文件）==="
/usr/local/miniconda3/bin/python3 /root/verify_model.py cyankiwi/Qwen3-VL-32B-Instruct-AWQ-8bit /root/models/Qwen3-VL-32B-Instruct-AWQ-8bit; echo "  AWQ-8bit rc=$?"
/usr/local/miniconda3/bin/python3 /root/verify_model.py Qwen/Qwen2.5-VL-72B-Instruct-AWQ /root/models/Qwen2.5-VL-72B-Instruct-AWQ; echo "  72B rc=$?"
echo DIGANOSE_DONE
