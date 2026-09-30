# -*- coding: utf-8 -*-
"""把正文里 28 处冗长的附录定位括注统一压成 `*(Numbers: X.Y.)*`。

动机：PR 官方限 20–35 页（含图表与参考文献），当前实测 35 页贴顶、零余量。
这些括注**只是定位符**（"本段逐格数字见附录 M.11"），不含任何主张或数字 ⇒
压缩它们不损失内容，却能把正文压回安全区。脚本先打印全部替换对，再落盘并复核词数。
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
import io
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')
P = RP('PaperB_英文稿_PR_20260919.md')
t = io.open(P, encoding='utf-8', newline='').read()

PAT = re.compile(r'\(\*[^*]{0,140}?Appendix\s+([A-Z](?:\.\d+)+)[^*]{0,80}?\*\)')


def rep(m):
    return '*(Numbers: %s.)*' % m.group(1)


hits = PAT.findall(t)
lines = list(t.splitlines(True))
for i, ln in enumerate(lines):
    for m in PAT.finditer(ln):
        print('L%-5d %-78s →  *(Numbers: %s.)*'
              % (i + 1, m.group(0).replace('\n', ' ')[:78], m.group(1)))
new = PAT.sub(rep, t)
print()
print('替换 %d 处（正则命中 %d）' % (new.count('*(Numbers:'), len(hits)))
assert new.count('*(Numbers:') == len(hits), '有括注未被替换'

if '--apply' in sys.argv:           # ★ 2026-09-30 v0610：默认**只读**，写回须显式 --apply
    io.open(P, 'w', encoding='utf-8', newline='').write(new)
    print('已写回：%d 处 *(Numbers: X.Y.)* → (Appendix X.Y)' % len(hits))
else:
    print('（dry run：%d 处 *(Numbers: X.Y.)* → (Appendix X.Y)，**未**写回主稿；加 --apply 才写）'
          % len(hits))


def wc(s):
    a = s[s.index('## Abstract'):]
    return len(re.findall(r'\S+', a))


print('正文（Abstract 之后）词数：%d → %d（省 %d）'
      % (wc(t), wc(new), wc(t) - wc(new)))
