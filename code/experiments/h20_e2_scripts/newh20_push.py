# -*- coding: utf-8 -*-
"""在新 H20 上运行：把结果 CSV 定期推送到 M机（M机 无卡仍在线，磁盘可用）。
动机：H20 随时可能被回收，结果必须落到第二处；M机 是我还能访问的稳定中转。
每 2 分钟推一次，只推新增/变化的文件。
"""
import os
import sys
import time

sys.stdout.reconfigure(encoding='utf-8')
import paramiko

M = ('cpod-1v4b5h1i96an-s1.podtcp.compshare.cn', 23654, 'root', '6q7QBV0F5z43Z21U')
RD = '/root/results_newh20'
# 零池与非零池探针的文件名完全相同，推到同一目录会互相覆盖 ⇒ 非零池加 nz__ 前缀
SRC = [('/root/e1_results', ''), ('/root/e1_results_nonzero', 'nz__')]
SEEN = {}


def conn():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(M[0], port=M[1], username=M[2], password=M[3], timeout=60,
              banner_timeout=60, auth_timeout=60, look_for_keys=False, allow_agent=False)
    return c


print('推送器启动 → M机:%s' % RD, flush=True)
errs = 0
while True:
    try:
        c = conn()
        sftp = c.open_sftp()
        try:
            sftp.mkdir(RD)
        except IOError:
            pass
        n_new = 0
        for d, prefix in SRC:
            if not os.path.isdir(d):
                continue
            for n in sorted(os.listdir(d)):
                if not n.endswith('.csv'):
                    continue
                ln = prefix + n
                lp = os.path.join(d, n)
                sz = os.path.getsize(lp)
                if SEEN.get(ln) == sz:
                    continue
                try:
                    sftp.put(lp, RD + '/' + ln)
                    SEEN[ln] = sz
                    n_new += 1
                    print('[%s] 推送 %-52s %7d B' % (time.strftime('%m-%d %H:%M:%S'), ln, sz),
                          flush=True)
                except Exception as ex:
                    print('  推送失败 %s: %s' % (n, str(ex)[:80]), flush=True)
        sftp.close()
        c.close()
        if n_new == 0:
            print('[%s] 无新文件' % time.strftime('%H:%M:%S'), flush=True)
        errs = 0
    except Exception as ex:
        errs += 1
        print('[%s] 推送出错(%d): %s' % (time.strftime('%H:%M:%S'), errs, type(ex).__name__),
              flush=True)
    time.sleep(120)
