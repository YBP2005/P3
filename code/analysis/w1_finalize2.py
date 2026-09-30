# -*- coding: utf-8 -*-
"""w1_finalize2.py — 把 bundle 内容同步到判定器路径，并跑终版判定与两张表。

背景：tar 保留了 `w1_results/...` 前缀，而判定器读 `analysis/w1_a800/{zero,nonzero,fsc,hosted}`
（早期逐目录拉取时就是这个布局）。这里做一次同步，保证判定器读到的是**bundle 里已核对 md5 的那份**，
而不是可能过期的旧逐目录副本。
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
import shutil
import subprocess
import sys

sys.stdout.reconfigure(encoding='utf-8')
BASE = NR('analysis', 'w1_a800')
SRC = NR('analysis', 'w1_a800', 'w1_results')
HERE = os.path.dirname(os.path.abspath(__file__))


def sync():
    for d in ('zero', 'nonzero', 'fsc', 'hosted', 'smoke', 'hosted_smoke'):
        s = os.path.join(NR('analysis', 'w1_a800', 'w1_results'), d)
        if not os.path.isdir(s):
            continue
        t = os.path.join(NR('analysis', 'w1_a800'), d)
        os.makedirs(t, exist_ok=True)
        n = 0
        for f in os.listdir(s):
            sp = os.path.join(s, f)
            if os.path.isfile(sp):
                shutil.copy2(sp, os.path.join(t, f))
                n += 1
        print('  同步 %-14s %3d 个文件' % (d, n))


def main():
    print('① 同步 bundle → 判定器路径')
    sync()
    print('\n② 判定（按冻结判据机械执行）')
    r = subprocess.run([sys.executable, os.path.join(HERE, 'w1_judge.py')],
                       capture_output=True, text=True, encoding='utf-8', errors='replace')
    print(r.stdout or '')
    if r.returncode != 0:
        print('!! judge rc=%d\n%s' % (r.returncode, (r.stderr or '')[-2000:]))
    print('\n③ 生成 frame / 覆盖度表')
    r2 = subprocess.run([sys.executable, os.path.join(HERE, 'w1_frame_report.py')],
                        capture_output=True, text=True, encoding='utf-8', errors='replace')
    print(r2.stdout or '')
    if r2.returncode != 0:
        print('!! frame rc=%d\n%s' % (r2.returncode, (r2.stderr or '')[-1200:]))
    return 0


if __name__ == '__main__':
    sys.exit(main())
