# -*- coding: utf-8 -*-
"""把本地脚本上传到 H20 并运行，回显输出。用法： python h20_run.py <本地文件> <远端文件名> [远端命令]
默认远端命令为 `python3 <远端文件名>`。"""
import io
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import newh20 as H

loc = sys.argv[1]
rem = sys.argv[2]
cmd = sys.argv[3] if len(sys.argv) > 3 else 'python3 /root/%s' % rem
sftp = None
c = H.connect()
try:
    sftp = c.open_sftp()
    sftp.put(loc, '/root/%s' % rem)
    print('uploaded %s -> /root/%s (%d B)' % (os.path.basename(loc), rem, os.path.getsize(loc)))
    o, e = H.run(c, cmd, timeout=600)
    print(o)
    if e.strip():
        print('--- stderr ---')
        print(e[-3000:])
finally:
    if sftp is not None:
        sftp.close()
    c.close()
