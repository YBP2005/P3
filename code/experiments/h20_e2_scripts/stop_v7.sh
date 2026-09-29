#!/bin/bash
# 按用户要求：不排 v7 系列，只让 v6 跑完。
# 停掉所有等待中的 v7/v7b/v7c（它们都只在 while 里空等，停掉零损失）。
echo "=== 停止等待中的 v7 系列 ==="
for pat in 'h20_exp_v7.sh' 'h20_exp_v7b.sh' 'h20_exp_v7c.sh'; do
  if pkill -9 -f "$pat" 2>/dev/null; then echo "  已停 $pat"; else echo "  （无 $pat）"; fi
done
rm -f /root/exp_v7.pid /root/exp_v7b.pid /root/exp_v7c.pid
sleep 4

echo
echo "=== 当前进程（/proc 直读）==="
/usr/local/miniconda3/bin/python3 - <<'PY'
import os, time
TG = ['h20_exp_v6.sh', 'h20_exp_v7', 'vllm serve', '19e_probe', 'newh20_push']
for p in sorted(os.listdir('/proc')):
    if not p.isdigit():
        continue
    try:
        cl = open('/proc/%s/cmdline' % p, 'rb').read().replace(b'\x00', b' ').decode('utf-8', 'replace').strip()
    except Exception:
        continue
    if any(t in cl for t in TG):
        try:
            t0 = time.strftime('%H:%M:%S', time.localtime(os.stat('/proc/%s' % p).st_ctime))
        except Exception:
            t0 = '?'
        print('  %s pid=%-7s %s' % (t0, p, cl[:98]))
PY

echo
echo "=== v6 当前位置 ==="
tail -5 /root/logs/exp_v6.log
echo
echo "=== 结果计数 ==="
echo -n "  零池: "; ls /root/e1_results/ 2>/dev/null | wc -l
echo -n "  非零池: "; ls /root/e1_results_nonzero/ 2>/dev/null | wc -l
echo
echo "=== 备份链路（H20→M机 推送器）==="
tail -3 /root/push.log 2>/dev/null
echo
echo "=== GPU / 磁盘 ==="
nvidia-smi --query-gpu=utilization.gpu,memory.used --format=csv,noheader
df -h / | tail -1
echo STOP_V7_DONE
