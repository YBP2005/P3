# -*- coding: utf-8 -*-
"""w1_unpack.py — 拉取并解包 w1_bundle.tar.gz（单文件传输 + md5 核对 + 解包到本地分析目录）。"""


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
import io
import os
import sys
import tarfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from a800_conn import connect  # noqa: E402

sys.stdout.reconfigure(encoding='utf-8')
HOST = ('<REDACTED-A800-HOST>', 23, 'root', '<REDACTED-A800-PASSWORD>')
DST = NR('analysis', 'w1_a800')
LOCAL_TAR = NR('analysis', 'w1_a800', 'w1_bundle.tar.gz')


def main():
    os.makedirs(DST, exist_ok=True)
    c = connect(HOST)
    sf = c.open_sftp()
    sf.get('/root/w1_bundle.tar.gz', LOCAL_TAR)
    sf.close()
    c.close()
    h = hashlib.md5(io.open(LOCAL_TAR, 'rb').read()).hexdigest()
    print('本地 md5 %s（远端为 25308f6fbbbb7b8e1a780de501b36e0c）' % h)
    if h[:12] != '25308f6fbbbb':
        print('!! md5 不一致，停止解包（可能拉到半截）')
        return 1
    with tarfile.open(LOCAL_TAR, 'r:gz') as t:
        names = t.getnames()
        t.extractall(DST)
    print('解包 %d 个成员 → %s' % (len(names), DST))
    for d in ('w1_results/zero', 'w1_results/nonzero', 'w1_results/fsc', 'w1_results/hosted', 'logs'):
        p = os.path.join(NR('analysis', 'w1_a800'), d)
        n = len(os.listdir(p)) if os.path.isdir(p) else -1
        print('  %-24s %d 个文件' % (d, n))
    return 0


if __name__ == '__main__':
    sys.exit(main())
