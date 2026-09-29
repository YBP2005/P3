# -*- coding: utf-8 -*-
"""H20 结果**直连一次性全量拉取**（不经 M机 中继），并做数量核对。

动机：v7c 收尾脚本会把结果推 M机，但中继是"尽力而为"；关机的唯一硬前提是
      **本地已完整持有远端全部结果**。故本脚本直接 SFTP 全量拉，并对
      "远端文件数 == 本地文件数 + 本次新拉数" 做断言，绝不靠日志推断。
"""
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import newh20 as H

DST = r'<WORKDIR>\PaperB\analysis\e2_newh20'
os.makedirs(DST, exist_ok=True)
WATCH = [('/root/e1_results', ''), ('/root/e1_results_nonzero', 'nz__')]

c = H.connect()
sftp = c.open_sftp()
try:
    total_new = 0
    total_remote = 0
    for d, prefix in WATCH:
        names = sorted(x for x in sftp.listdir(d) if x.endswith('.csv'))
        total_remote += len(names)
        n_new = 0
        bad = []
        for n in names:
            rp = d + '/' + n
            lp = os.path.join(DST, prefix + n)
            rs = sftp.stat(rp)
            if os.path.exists(lp) and os.path.getsize(lp) == rs.st_size:
                continue
            try:
                sftp.get(rp, lp)
            except Exception as ex:
                bad.append((n, type(ex).__name__))
                continue
            if os.path.getsize(lp) != rs.st_size:
                bad.append((n, 'size mismatch %d!=%d' % (os.path.getsize(lp), rs.st_size)))
                continue
            os.utime(lp, (rs.st_mtime, rs.st_mtime))
            n_new += 1
        total_new += n_new
        print('%-28s 远端 %3d 个，新拉 %2d 个，失败 %d 个' % (d, len(names), n_new, len(bad)))
        for b in bad:
            print('      !! %s' % (b,))
    print()
    print('远端合计 %d 个；本次新拉 %d 个' % (total_remote, total_new))
    # 本地应持有全部（含此前 ckpt/e1 等其它批次的同目录文件，故只断言"不少"）
    miss = []
    for d, prefix in WATCH:
        names = [x for x in sftp.listdir(d) if x.endswith('.csv')]
        for n in names:
            lp = os.path.join(DST, prefix + n)
            if not (os.path.exists(lp) and os.path.getsize(lp) == sftp.stat(d + '/' + n).st_size):
                miss.append(prefix + n)
    if miss:
        print('MISSING_IN_LOCAL %d: %s' % (len(miss), miss[:20]))
        sys.exit(2)
    print('本地核对：远端每一个 CSV 在本地都存在且大小一致 ✓')
    # v7c 两域专项核对
    for dom in ('visdrone', 'aitod'):
        z = [x for x in os.listdir(DST) if dom in x and not x.startswith('nz__')]
        nz = [x for x in os.listdir(DST) if dom in x and x.startswith('nz__')]
        print('  %-9s 零池 %3d 个 / 非零池 %3d 个' % (dom, len(z), len(nz)))
    print('PULL_OK')
finally:
    sftp.close()
    c.close()
