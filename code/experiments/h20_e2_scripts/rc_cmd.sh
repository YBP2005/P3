date -u
echo "--- v6 日志尾 ---"
tail -n 8 /root/logs/exp_v6.log
echo "--- df ---"
df -h / | tail -1
echo "--- 相关进程 ---"
/usr/local/miniconda3/bin/python3 - <<'PYEOF'
import os
for p in sorted(os.listdir('/proc')):
    if not p.isdigit():
        continue
    try:
        cl = open('/proc/%s/cmdline' % p, 'rb').read().replace(b'\x00', b' ').decode('utf-8', 'replace').strip()
    except Exception:
        continue
    if 'exp_v' in cl or 'dl_model' in cl or 'vllm' in cl or 'probe' in cl:
        print(p, cl[:120])
PYEOF
echo "--- 结果文件数 ---"
echo -n "e1_results: "; ls /root/e1_results/ | wc -l
echo -n "e1_results_nonzero: "; ls /root/e1_results_nonzero/ | wc -l
