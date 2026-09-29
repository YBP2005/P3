# -*- coding: utf-8 -*-
"""在新 H20 上运行：等 M机 打包完成 → 逐个 SFTP 取包 → 校验 md5 → 解包 → 删包。
单文件流传输（用户经验：打包传大文件很快）。
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

# 包名 -> 解包目标目录
DEST = {
    'models_awq32.tar': '/root/models',
    'models_awq8b.tar': '/root/models',
    'models_q25vl.tar': '/root/models',
    'models_ivl.tar': '/root/models',
    'vllm312.tar.gz': '/root',
    'dense.tar.gz': '/root',
    'meta.tar.gz': '/root',
    'probes.tar.gz': '/root',
}


def md5f(p):
    h = hashlib.md5()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 22), b''):
            h.update(b)
    return h.hexdigest()


def main():
    os.makedirs(INC, exist_ok=True)
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(M[0], port=M[1], username=M[2], password=M[3], timeout=60,
              banner_timeout=60, auth_timeout=60, look_for_keys=False, allow_agent=False)
    print('已连上 M机', flush=True)

    # 等打包完成（用 grep -q：只看退出码，避免 -c 在无匹配时同时输出 0 造成假阳性）
    t0 = time.time()
    while time.time() - t0 < 3 * 3600:
        si, so, se = c.exec_command('grep -q PACK_ALL_DONE /root/pack.log 2>/dev/null', timeout=120)
        rc = so.channel.recv_exit_status()
        if rc == 0:
            print('M机 打包完成', flush=True)
            break
        si, so, se = c.exec_command('ls /root/pack/ 2>/dev/null | tr "\\n" " "', timeout=120)
        print('  等打包… 已有: %s' % so.read().decode().strip()[:160], flush=True)
        time.sleep(60)

    # 远端 md5
    si, so, se = c.exec_command('cat /root/pack/MD5SUMS 2>/dev/null', timeout=300)
    rmd5 = {}
    for line in so.read().decode().splitlines():
        parts = line.split()
        if len(parts) == 2:
            rmd5[os.path.basename(parts[1])] = parts[0]
    print('远端 md5 表：%d 项' % len(rmd5), flush=True)

    si, so, se = c.exec_command('ls /root/pack/*.tar /root/pack/*.tar.gz 2>/dev/null', timeout=300)
    names = [os.path.basename(x) for x in so.read().decode().split() if x.strip()]
    print('待取 %d 个包：%s' % (len(names), names), flush=True)

    sftp = c.open_sftp()
    for n in names:
        lp = os.path.join(INC, n)
        want = rmd5.get(n)
        # 已传且校验通过则跳过
        if os.path.exists(lp) and want and md5f(lp) == want:
            print('SKIP %-22s md5 已一致' % n, flush=True)
        else:
            rs = sftp.stat('/root/pack/' + n)
            t = time.time()
            sftp.get('/root/pack/' + n, lp)
            got = md5f(lp)
            ok = (got == want) if want else (os.path.getsize(lp) == rs.st_size)
            print('%-6s %-22s %.2f GB  %.0fs  md5=%s'
                  % ('OK' if ok else 'MD5!', n, os.path.getsize(lp) / 1e9, time.time() - t, got[:12]),
                  flush=True)
            if not ok:
                print('  !! md5 不符，保留待重传（期望 %s）' % want, flush=True)
                continue

        # 解包
        dest = DEST.get(n)
        if dest:
            os.makedirs(dest, exist_ok=True)
            cmd = ['tar', 'xf', lp, '-C', dest]
            r = subprocess.run(cmd)
            print('  解包 → %s rc=%d' % (dest, r.returncode), flush=True)
            if r.returncode == 0:
                os.remove(lp)
                print('  已删包 %s' % n, flush=True)
    sftp.close()
    c.close()

    # probes 包内是 probes/ 目录，取出到 /root
    pd = '/root/probes'
    if os.path.isdir(pd):
        for f in os.listdir(pd):
            subprocess.run(['cp', '-f', os.path.join(pd, f), '/root/'])
        print('已把 probes/ 内文件放到 /root', flush=True)

    print('FETCH_ALL_DONE', flush=True)


main()
