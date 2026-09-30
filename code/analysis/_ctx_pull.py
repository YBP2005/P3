# -*- coding: utf-8 -*-
"""_ctx_pull.py —— 把 S1 的 18 个产物目录 + 冻结结果拉回本地（目录级递归，sftp 直传）。

为什么另写：`rsh.py --get` 只处理**目录下一层**的文件，而这里要拉 18 个目录 + 单个 json，
且需要**校验 md5**（远端算一遍、本地算一遍，比对）。故直接用 a800_conn 的 sftp。

用法：python -u _ctx_pull.py
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
import io
import os
import stat
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from a800_conn import connect, sh  # noqa: E402

sys.stdout.reconfigure(encoding='utf-8')
HOST = ('<REDACTED-A800-HOST>', 23, 'root', '<REDACTED-A800-PASSWORD>')
REM = '/root/w1_results'
LOC = NR('analysis', 'ctxctrl')
EXTRA = ['ctxctrl_result.json']          # 单文件（非目录）
MD5 = lambda p: hashlib.md5(io.open(p, 'rb').read()).hexdigest()


def main():
    c = connect(HOST)
    sf = c.open_sftp()
    os.makedirs(LOC, exist_ok=True)
    dirs = [d for d in sorted(sf.listdir(REM)) if d.startswith('ctxctrl_') and
            stat.S_ISDIR(sf.stat(REM + '/' + d).st_mode)]
    print('远端 %d 个产节目录' % len(dirs))
    n_file = 0
    for d in dirs:
        ld = os.path.join(NR('analysis', 'ctxctrl'), d)
        os.makedirs(ld, exist_ok=True)
        for f in sorted(sf.listdir(REM + '/' + d)):
            if f.startswith('.'):
                continue
            sf.get(REM + '/' + d + '/' + f, os.path.join(ld, f))
            n_file += 1
    for f in EXTRA:
        try:
            sf.get(REM + '/' + f, os.path.join(NR('analysis', 'ctxctrl'), f))
            n_file += 1
        except Exception as ex:
            print('  !! %s 拉取失败：%s' % (f, str(ex)[:80]))
    print('拉回 %d 个文件 → %s' % (n_file, LOC))

    # 行数/大小一致性：本地 vs 远端
    print('\n本地逐目录检查（行数应各为 4 个臂文件）：')
    bad = 0
    for d in dirs:
        ld = os.path.join(NR('analysis', 'ctxctrl'), d)
        fs = sorted(os.listdir(ld))
        sizes = sum(os.path.getsize(os.path.join(ld, f)) for f in fs)
        print('  %-34s %d 文件 %9d B' % (d, len(fs), sizes))
        if len(fs) != 4:
            bad += 1
    print('\n臂文件数不是 4 的目录：%d' % bad)

    # md5 双向核对（远端算出清单，本地逐条比对）
    out = sh(c, "cd %s && md5sum ctxctrl_*/fsc_*.csv ctxctrl_result.json" % REM, t=180)
    lines = [l.split() for l in out.splitlines() if '  ' in l]
    mism = []
    for h, p in lines:
        lp = os.path.join(NR('analysis', 'ctxctrl'), p.replace('/', os.sep))
        if not os.path.exists(lp):
            mism.append((p, '本地缺失'))
        elif MD5(lp) != h:
            mism.append((p, 'md5 不一致'))
    print('远端清单 %d 条；不一致 %d 条 %s' % (len(lines), len(mism), mism[:5]))
    c.close()
    return 1 if mism else 0


if __name__ == '__main__':
    raise SystemExit(main())
