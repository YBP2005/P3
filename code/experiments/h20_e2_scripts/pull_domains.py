# -*- coding: utf-8 -*-
"""在 H20 上运行：从 M机 流式拉取非密集域数据（aerial / countbench）与对应的语料 base 结果。
用流式 tar（M机 端 tar cf - → 本机 tar xf -），双方都不占额外磁盘。
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
    ('/root', 'aerial', '/root'),                                  # visdrone + aitod 图像与 GT
    ('/root/ext', 'countbench', '/root/ext'),                      # 自然图计数 + counts.csv
    ('/root/aerial_results', 'aer_visdrone_base.csv', '/root/corpus_new'),
    ('/root/aerial_results', 'aer_aitod_base.csv', '/root/corpus_new'),
    ('/root/ext_results', 'ext_countbench_base.csv', '/root/corpus_new'),
]

mc = paramiko.SSHClient()
mc.set_missing_host_key_policy(paramiko.AutoAddPolicy())
mc.connect(M[0], port=M[1], username=M[2], password=M[3], timeout=60,
           banner_timeout=60, auth_timeout=60, look_for_keys=False, allow_agent=False)
print('已连上 M机', flush=True)

for parent, name, lparent in ITEMS:
    rp = parent + '/' + name
    si, so, se = mc.exec_command('du -sb %s 2>/dev/null | cut -f1' % rp, timeout=600)
    rb = so.read().decode().strip()
    os.makedirs(lparent, exist_ok=True)
    t0 = time.time()
    si, so, se = mc.exec_command("tar cf - -C '%s' '%s'" % (parent, name), timeout=86400)
    p = subprocess.Popen(['tar', 'xf', '-', '-C', lparent], stdin=subprocess.PIPE)
    n = 0
    try:
        while True:
            data = so.read(1 << 20)
            if not data:
                break
            p.stdin.write(data)
            n += len(data)
    except Exception as ex:
        print('  传输异常 %s: %s' % (name, ex), flush=True)
    p.stdin.close()
    p.wait()
    err = se.read().decode('utf-8', 'replace').strip()
    if err:
        print('  远端 stderr: %s' % err[-200:], flush=True)
    print('  OK %-26s 远端 %s B  实收 %.2f MB  %.0fs'
          % (name, rb, n / 1e6, time.time() - t0), flush=True)

mc.close()
print('--- 落地检查 ---')
subprocess.run('ls -la /root/aerial /root/ext/countbench /root/corpus_new 2>/dev/null; '
               'du -sh /root/aerial /root/ext /root/corpus_new; df -h / | tail -1', shell=True)
print('PULL_DOMAINS_DONE', flush=True)
