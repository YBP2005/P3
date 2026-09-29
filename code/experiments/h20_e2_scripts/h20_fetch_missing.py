# -*- coding: utf-8 -*-
"""在 H20 上运行：从 M机 定向取指定包（带 md5 校验），解包后删包。
与 newh20_fetch_packs.py 的区别：只取给定清单，不重下已有的包。
"""
import hashlib
import os
import subprocess
import sys
import time

sys.stdout.reconfigure(encoding='utf-8')
import paramiko

M = ('cpod-1v4b5h1i96an-s1.podtcp.compshare.cn', 23654, 'root', '6q7QBV0F5z43Z21U')
INC = '/root/incoming'
WANT = sys.argv[1:] if len(sys.argv) > 1 else ['vllm312.tar.gz', 'probes.tar.gz', 'models_ivl.tar']
DEST = {
    'models_ivl.tar': '/root/models',
    'vllm312.tar.gz': '/root',
    'probes.tar.gz': '/root',
    'dense.tar.gz': '/root',
    'meta.tar.gz': '/root',
    'models_awq32.tar': '/root/models',
    'models_awq8b.tar': '/root/models',
    'models_q25vl.tar': '/root/models',
}


def md5f(p):
    h = hashlib.md5()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 22), b''):
            h.update(b)
    return h.hexdigest()


os.makedirs(INC, exist_ok=True)
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(M[0], port=M[1], username=M[2], password=M[3], timeout=60,
          banner_timeout=60, auth_timeout=60, look_for_keys=False, allow_agent=False)
si, so, se = c.exec_command('cat /root/pack/MD5SUMS', timeout=300)
rmd5 = {}
for line in so.read().decode().splitlines():
    p = line.split()
    if len(p) == 2:
        rmd5[os.path.basename(p[1])] = p[0]
print('远端 md5 表 %d 项' % len(rmd5), flush=True)

sftp = c.open_sftp()
for n in WANT:
    rp, lp = '/root/pack/' + n, os.path.join(INC, n)
    want = rmd5.get(n)
    if not want:
        print('SKIP %s（远端无此包）' % n, flush=True)
        continue
    if os.path.exists(lp) and md5f(lp) == want:
        print('SKIP %-22s 本地已有且 md5 一致' % n, flush=True)
    else:
        rs = sftp.stat(rp)
        t0 = time.time()
        sftp.get(rp, lp)
        got = md5f(lp)
        ok = (got == want)
        print('%-6s %-22s %.2f GB  %.0fs  md5=%s' %
              ('OK' if ok else 'MD5!', n, os.path.getsize(lp) / 1e9, time.time() - t0, got[:12]),
              flush=True)
        if not ok:
            print('  !! md5 不符，保留待重传', flush=True)
            continue
    dest = DEST.get(n, '/root')
    os.makedirs(dest, exist_ok=True)
    r = subprocess.run(['tar', 'xf', lp, '-C', dest])
    print('  解包 → %s rc=%d' % (dest, r.returncode), flush=True)
    if r.returncode == 0:
        os.remove(lp)
        print('  已删包 %s' % n, flush=True)

# probes 包内含 probes/ 目录，取出到 /root
pd = '/root/probes'
if os.path.isdir(pd):
    for f in os.listdir(pd):
        subprocess.run(['cp', '-f', os.path.join(pd, f), '/root/'])
    print('已把 probes/ 内容放入 /root', flush=True)

sftp.close()
c.close()
print('FETCH_MISSING_DONE', flush=True)
