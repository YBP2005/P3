# -*- coding: utf-8 -*-
"""v7c 收尾：① 核对完成标记 ② 把 H20 日志拉回本地存档 ③ 释放 GPU（杀掉 vllm 计算进程）。

纪律：
  · 释放 GPU 用 `nvidia-smi --query-compute-apps=pid` 拿 pid 再 kill —— 不用 `pkill -f 'vllm serve'`
    （既有孤儿 EngineCore 占显存的老问题，也有 pkill 自匹配杀到自己 shell 的教训）；
  · 日志是"这次跑过"的存证（耗时/吞吐），必须与 CSV 一起落地，否则日后无法复算成本。
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
import time

sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import newh20 as H

DST = RP('analysis', 'e2_newh20', 'logs_h20_v7c')
os.makedirs(DST, exist_ok=True)

c = H.connect()
sftp = c.open_sftp()
try:
    print('=== 完成标记 ===')
    o, _ = H.run(c, "grep -h -E 'EXP_V6_DONE|EXP_V7C_DONE|ALL_EXPERIMENTS_DONE' "
                    "/root/logs/exp_v6.log /root/logs/exp_v7c.log 2>/dev/null | sort | uniq -c")
    print(o.strip() or '  （无）')
    print()
    print('=== 收尾段日志 ===')
    o, _ = H.run(c, 'tail -14 /root/logs/exp_v7c.log')
    print(o.rstrip())
    print()
    print('=== 拉取日志 ===')
    wanted = []
    for lp in ('/root/logs/exp_v7c.log', '/root/logs/exp_v6.log', '/root/logs/push_final.log',
               '/root/logs/push.log'):
        if os.path.exists(lp) or True:
            try:
                sftp.stat(lp)
                wanted.append(lp)
            except IOError:
                pass
    try:
        for n in sftp.listdir('/root/logs'):
            if n.startswith('probe_v7c') or n.startswith('probe_v6'):
                wanted.append('/root/logs/' + n)
    except IOError:
        pass
    got = 0
    for lp in wanted:
        local = os.path.join(RP('analysis', 'e2_newh20', 'logs_h20_v7c'), os.path.basename(lp))
        try:
            rs = sftp.stat(lp)
            if os.path.exists(local) and os.path.getsize(local) == rs.st_size:
                continue
            sftp.get(lp, local)
            os.utime(local, (rs.st_mtime, rs.st_mtime))
            got += 1
        except Exception as ex:
            print('  !! %s: %s' % (lp, type(ex).__name__))
    print('  日志目录 %s：本地共 %d 个文件（本次新拉 %d）'
          % (DST, len(os.listdir(DST)), got))
    print()
    print('=== 释放 GPU ===')
    o, _ = H.run(c, "nvidia-smi --query-compute-apps=pid,used_memory --format=csv,noheader")
    print('  当前计算进程: %s' % (o.strip() or '（无）'))
    o, _ = H.run(c, "nvidia-smi --query-compute-apps=pid --format=csv,noheader | tr -d ' ' | "
                    "xargs -r kill -9 2>/dev/null; sleep 8; "
                    "nvidia-smi --query-gpu=memory.used,utilization.gpu --format=csv,noheader; "
                    "nvidia-smi --query-compute-apps=pid,used_memory --format=csv,noheader | wc -l")
    print('  释放后 GPU(used,util) 与残留计算进程行数:')
    for ln in o.strip().splitlines():
        print('    ' + ln)
finally:
    sftp.close()
    c.close()
print()
print('FINISH_PACK_OK')
