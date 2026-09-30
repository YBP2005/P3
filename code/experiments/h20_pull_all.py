# -*- coding: utf-8 -*-
"""H20 结果**直连一次性全量拉取**（不经 M机 中继），并做数量核对。

动机：v7c 收尾脚本会把结果推 M机，但中继是"尽力而为"；关机的唯一硬前提是
      **本地已完整持有远端全部结果**。故本脚本直接 SFTP 全量拉，并对
      "远端文件数 == 本地文件数 + 本次新拉数" 做断言，绝不靠日志推断。
"""


# ── 复现包统一根：`_repro_root.py`（与本文件同目录）──────────────────────────────
# RP(*parts) = 作者树相对路径 -> 绝对路径（作者树上原样；放行树上查前缀映射表）；
# NR(*parts) = **未随包发布**的作者侧路径（放行树上落到 _NOT_RELEASED/，使失败可见）。
try:
    from _repro_root import resolve as RP, not_released as NR
except ImportError:                      # 只拷走单个脚本时：就地反推仓库根，无前缀映射表
    import os as _o
    _r = _o.environ.get('PAPERB_ROOT') or _o.path.dirname(_o.path.dirname(_o.path.abspath(__file__)))
    RP = lambda *p: _o.path.join(_r, *p)
    NR = lambda *p: _o.path.join(_r, '_NOT_RELEASED', *p)
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import newh20 as H

DST = RP('analysis', 'e2_newh20')
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
            lp = os.path.join(RP('analysis', 'e2_newh20'), prefix + n)
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
            lp = os.path.join(RP('analysis', 'e2_newh20'), prefix + n)
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
