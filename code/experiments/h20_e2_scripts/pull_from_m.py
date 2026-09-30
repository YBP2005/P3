# -*- coding: utf-8 -*-
"""在新 H20 上运行：从 M机 流式拉取全部资产。
做法：M机 端 `tar cf - -C <parent> <name>` 直接吐到 stdout，
      本机 `tar xf -` 直接从 stdin 解包 —— 两端都不需要额外的 tar 文件，
      也避开了 M机 系统盘只剩 20 GB 的限制。传完逐项核对文件数与字节数。
"""
import os
import subprocess
import sys
import time

sys.stdout.reconfigure(encoding='utf-8')
import paramiko

M = ('<REDACTED-POD-HOST>', 23654, 'root', '<REDACTED-POD-PASSWORD>')

# (远端父目录, 名称, 本地父目录)
ITEMS = [
    ('/root', '19b_e1_probe.py', '/root'),
    ('/root', '19c_probe_paraphrase.py', '/root'),
    ('/root', '19d_probe_nonzero.py', '/root'),
    ('/root', 'dense_results', '/root'),
    ('/root', 'dense', '/root'),
    ('/root', 'vllm312', '/root'),
    ('/root/models', 'Qwen3-VL-32B-Instruct-AWQ-4bit', '/root/models'),
    ('/root/models', 'Qwen3-VL-8B-Instruct-AWQ-4bit', '/root/models'),
    ('/root/models', 'Qwen2.5-VL-7B-Instruct-AWQ', '/root/models'),
    ('/root/models', 'InternVL2_5-8B-AWQ', '/root/models'),
]


def md5_local(path):
    h = __import__('hashlib').md5()
    with open(path, 'rb') as f:
        for b in iter(lambda: f.read(1 << 22), b''):
            h.update(b)
    return h.hexdigest()


def main():
    mc = paramiko.SSHClient()
    mc.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    mc.connect(M[0], port=M[1], username=M[2], password=M[3], timeout=60,
               banner_timeout=60, auth_timeout=60, look_for_keys=False, allow_agent=False)
    print('已连上 M机', flush=True)

    for parent, name, lparent in ITEMS:
        rp = parent + '/' + name
        # 远端大小（先量，用于事后核对）
        si, so, se = mc.exec_command('du -sb %s 2>/dev/null | cut -f1; '
                                     'find %s -type f 2>/dev/null | wc -l' % (rp, rp), timeout=600)
        info = so.read().decode().split()
        rb = int(info[0]) if info else -1
        rf = int(info[1]) if len(info) > 1 else -1
        os.makedirs(lparent, exist_ok=True)

        # 已存在且大小一致则跳过
        si, so, se = mc.exec_command('true', timeout=30)
        if os.path.exists(lparent + '/' + name):
            lb = int(subprocess.run(['du', '-sb', lparent + '/' + name],
                                    capture_output=True, text=True).stdout.split()[0])
            if lb == rb:
                print('SKIP %-40s 已一致 %.2f GB' % (name, rb / 1e9), flush=True)
                continue

        t0 = time.time()
        si, so, se = mc.exec_command("tar cf - -C '%s' '%s'" % (parent, name), timeout=86400)
        p = subprocess.Popen(['tar', 'xf', '-', '-C', lparent], stdin=subprocess.PIPE)
        n = 0
        last = 0
        try:
            while True:
                data = so.read(1 << 20)
                if not data:
                    break
                p.stdin.write(data)
                n += len(data)
                if n - last >= (1 << 30):
                    last = n
                    print('  %-40s %6.2f GB  %.0fs' % (name, n / 1e9, time.time() - t0), flush=True)
        except Exception as ex:
            print('  传输异常 %s: %s' % (name, ex), flush=True)
        p.stdin.close()
        p.wait()
        err = se.read().decode('utf-8', 'replace').strip()
        if err:
            print('  远端 stderr: %s' % err[-300:], flush=True)

        lb = int(subprocess.run(['du', '-sb', lparent + '/' + name],
                                capture_output=True, text=True).stdout.split()[0])
        lf = int(subprocess.run(['bash', '-c', 'find %s/%s -type f | wc -l' % (lparent, name)],
                                capture_output=True, text=True).stdout.strip())
        ok = (lb == rb)
        print('%s %-40s 远端 %.2fGB/%d 文件  本地 %.2fGB/%d 文件  %.0fs'
              % ('OK  ' if ok else 'SIZE!', name, rb / 1e9, rf, lb / 1e9, lf, time.time() - t0),
              flush=True)

    mc.close()
    print('PULL_ALL_DONE', flush=True)


main()
