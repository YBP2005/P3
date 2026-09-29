# -*- coding: utf-8 -*-
"""新 H20 结果实时同步：每 2 分钟把结果 CSV 拉到本地。
动机：已经因关机丢过一次全池普查数据（老 H20），不能再依赖"任务结束后再拉"。
按远端 mtime+大小判断变化；把远端 mtime 写回本地，便于下次比对。
"""
import os
import sys
import time

sys.stdout.reconfigure(encoding='utf-8')
import paramiko

HOST, PORT, USER, PW = '117.50.80.219', 23, 'root', '10T534269iNDPdqu'
DST = r'<WORKDIR>\PaperB\analysis\e2_newh20'
os.makedirs(DST, exist_ok=True)
# 关键：零池与非零池探针写出的文件名完全相同（只是输出目录不同），
# 拉到同一目录会互相覆盖 ⇒ 非零池一律加 nz__ 前缀区分。
WATCH = [('/root/e1_results', ''), ('/root/e1_results_nonzero', 'nz__')]
LAST = {}


def conn():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, port=PORT, username=USER, password=PW, timeout=45,
              banner_timeout=45, auth_timeout=45, look_for_keys=False, allow_agent=False)
    return c


print('同步器启动，目标目录 %s' % DST, flush=True)
errs = 0
while True:
    try:
        c = conn()
        sftp = c.open_sftp()
        n_new = 0
        for d, prefix in WATCH:
            try:
                names = sftp.listdir(d)
            except IOError:
                continue
            for n in names:
                if not n.endswith('.csv'):
                    continue
                ln = prefix + n
                rp = d + '/' + n
                lp = os.path.join(DST, ln)
                try:
                    rs = sftp.stat(rp)
                except IOError:
                    continue
                same = (os.path.exists(lp) and os.path.getsize(lp) == rs.st_size
                        and LAST.get(ln) == (rs.st_size, int(rs.st_mtime)))
                if same:
                    continue
                sftp.get(rp, lp)
                os.utime(lp, (rs.st_mtime, rs.st_mtime))
                LAST[ln] = (rs.st_size, int(rs.st_mtime))
                n_new += 1
                print('[%s] 同步 %-52s %7d B' % (time.strftime('%m-%d %H:%M:%S'), ln,
                                                 os.path.getsize(lp)), flush=True)
        sftp.close()
        c.close()
        if n_new == 0:
            print('[%s] 无新文件（本地共 %d 个）' % (time.strftime('%H:%M:%S'),
                                                 len(os.listdir(DST))), flush=True)
        errs = 0
    except Exception as ex:
        errs += 1
        print('[%s] 同步出错(%d): %s' % (time.strftime('%H:%M:%S'), errs, type(ex).__name__),
              flush=True)
    time.sleep(120)
