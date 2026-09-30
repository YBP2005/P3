# -*- coding: utf-8 -*-
"""w0_pull_probes.py — 把 A800 上**正在使用**的探针原样拉到本地核对，并打印其关键结构。

为什么：写 W1 面板脚本前必须确认三件事——
  ① 本地复现包里的 19e/19f 与 A800 上在用的**是否逐字节相同**（md5）；
  ② 19f 的 OUTD / 尺度臂 / 池参数怎么传（决定驱动脚本怎么写）；
  ③ 19g 的 FSC 结构（决定 exemplar 臂怎么加）。
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
import hashlib
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from a800_conn import connect, sh  # noqa: E402

sys.stdout.reconfigure(encoding='utf-8')
HOST = ('<REDACTED-A800-HOST>', 23, 'root', '<REDACTED-A800-PASSWORD>')
HERE = os.path.dirname(os.path.abspath(__file__))
DST = os.path.join(HERE, 'a800_probes')
LOCAL = RP('repro_github', 'code', 'experiments')

PATTERNS = {
    '19f_argparse': r"grep -n 'OUTD\|add_argument\|imgsz\|pool\|system\|DS_DIRS' /root/19f_probe_ablation.py | head -34",
    '19g_struct': r"grep -n 'OUTD\|add_argument\|exemplar\|box\|arms\|fsc\|def \|P\[' /root/19g_probe_fsc.py | head -44",
    '19e_dirs': r"grep -n 'DS_DIRS\|def load_gt\|GT\|\.json' /root/19e_probe_multi.py | head -24",
    '19e_head': r"sed -n '1,45p' /root/19e_probe_multi.py",
    'fsc_dir': r"ls /root/fsc147 | head; echo ---; du -sh /root/fsc147; ls /root/fsc147/*.json 2>/dev/null | head",
    'corpus': r"ls -la /root/dense_results/; echo ---; head -2 /root/dense_results/vlm_st_a_base_whole.csv",
    'domains': r"for d in /root/dense /root/aerial; do echo \"## \$d\"; ls \$d | head -4; ls \$d | wc -l; done",
}


def main():
    c = connect(HOST)
    os.makedirs(DST, exist_ok=True)
    sf = c.open_sftp()
    print('=' * 90)
    print('① 探针拉取 + md5 对照（远端 vs 本地复现包）')
    print('=' * 90)
    for rem in ['/root/19e_probe_multi.py', '/root/19f_probe_ablation.py',
                '/root/19g_probe_fsc.py', '/root/19b_e1_probe.py']:
        base = os.path.basename(rem)
        lp = os.path.join(DST, base)
        sf.get(rem, lp)
        h_rem = hashlib.md5(open(lp, 'rb').read()).hexdigest()
        loc = os.path.join(RP('repro_github', 'code', 'experiments'), base if base != '19g_probe_fsc.py' else '19g_probe_fsc.py')
        note = ''
        if os.path.exists(loc):
            h_loc = hashlib.md5(open(loc, 'rb').read()).hexdigest()
            note = '本地 %s %s' % (h_loc[:12], '✓ 相同' if h_loc == h_rem else '✗ 不同')
        else:
            note = '本地**无**此文件（仅远端有）'
        print('%-28s %7d B  md5 %s  %s' % (base, os.path.getsize(lp), h_rem[:12], note))
    sf.close()

    for k, cmd in PATTERNS.items():
        print('\n' + '=' * 90)
        print('### ' + k)
        print('=' * 90)
        print(sh(c, cmd, t=180))
    c.close()


if __name__ == '__main__':
    main()
