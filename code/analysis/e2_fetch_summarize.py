# -*- coding: utf-8 -*-
"""拉取 M机 E2 的 8 个 CSV 到本地并出对照表（含完整性检查）。"""
import csv
import io
import os
import re
import statistics
import sys

sys.stdout.reconfigure(encoding='utf-8')
import paramiko

M = ('cpod-1v4b5h1i96an-s1.podtcp.compshare.cn', 23654, 'root', '6q7QBV0F5z43Z21U')
LOCAL = r'<WORKDIR>\PaperB\analysis\e2_5090'
ABST = ('abstain', 'cannot_judge', 'no_people')

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(M[0], port=M[1], username=M[2], password=M[3], timeout=40,
          banner_timeout=40, auth_timeout=40, look_for_keys=False, allow_agent=False)
try:
    si, so, se = c.exec_command('tail -3 /root/logs/e2_run.log; ls /root/e1_results/*qwen3-vl-32b-awq* 2>/dev/null', timeout=120)
    print('=== 队列状态 ==='); print(so.read().decode('utf-8', 'replace').rstrip())
    os.makedirs(LOCAL, exist_ok=True)
    sf = c.open_sftp()
    got = []
    for f in sf.listdir('/root/e1_results'):
        if 'qwen3-vl-32b-awq' in f and f.endswith('.csv'):
            sf.get('/root/e1_results/' + f, os.path.join(LOCAL, f)); got.append(f)
    sf.close()
    print('\n拉取 %d 个 CSV -> %s' % (len(got), LOCAL))
finally:
    c.close()

print('\n%-46s %4s %5s %6s %8s %9s %6s' % ('cell', 'n', 'zero', 'abst', 'medP/G', 'dev%', 'ERR'))
rows = []
for f in sorted(os.listdir(LOCAL)):
    if not f.endswith('.csv'):
        continue
    rr = list(csv.DictReader(io.open(os.path.join(LOCAL, f), encoding='utf-8-sig')))
    nums = []; gts = []; z = 0; ab = 0; err = 0
    for r in rr:
        raw = r.get('raw') or ''
        if raw.startswith('ERR'):
            err += 1; continue
        try:
            v = float(r['pred'])
        except Exception:
            v = None
        if v is None:
            if any(t in raw.lower() for t in ABST):
                ab += 1
            continue
        nums.append(v); gts.append(float(r['gt']))
        if v == 0:
            z += 1
    med = statistics.median([v / g for v, g in zip(nums, gts) if g > 0]) if nums else None
    dev = (sum(nums) - sum(gts)) / sum(gts) * 100 if nums else None
    rows.append((f, len(rr), z, ab, med, dev, err))
    print('%-46s %4d %5d %6d %8s %9s %6d' % (f.replace('e1_qwen3-vl-32b-awq_', '')[:46], len(rr), z, ab,
          '%.3f' % med if med is not None else '—', '%.1f' % dev if dev is not None else '—', err))
print('\n（abst = 显式弃权计数；medP/G 与 dev 仅在有数值作答时计算）')
