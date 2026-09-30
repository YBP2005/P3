# -*- coding: utf-8 -*-
"""w1_pagebudget.py — 量出正文各节的**真实词数**，为插入 §5.14 精确腾页。

为什么要量：本稿 35 页 / 11,384 词 ≈ 325 词/页（实测冻结值），新增 §5.14（约 650 词）≈ 2 页。
"感觉某节很长"不足以决定外迁哪一段；按词数排序才能一次腾够、避免反复重建 docx。
输出：按词数降序的节表 + §5.10–§5.13 的逐段词数（外迁候选）。
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
import os
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')
MAN = RP('PaperB_英文稿_PR_20260919.md')


def wc(t):
    return len(re.findall(r"[A-Za-z0-9][A-Za-z0-9'\-\.]*", t))


def main():
    txt = io.open(MAN, encoding='utf-8').read()
    lines = txt.splitlines()
    heads = [(i, l) for i, l in enumerate(lines) if re.match(r'^#{2,3} ', l)]
    secs = []
    for k, (i, l) in enumerate(heads):
        j = heads[k + 1][0] if k + 1 < len(heads) else len(lines)
        body = '\n'.join(lines[i + 1:j])
        secs.append((l.strip(), wc(body), j - i))
    print('总词数 %d（含图注/表注）' % sum(s[1] for s in secs))
    print()
    print('| 节 | 词数 | 行数 |')
    print('|---|---|---|')
    for l, w, n in secs:
        if w >= 250:
            print('| %s | %d | %d |' % (l[:70], w, n))
    print()
    print('## §5.10–§5.13 逐段词数（外迁候选）')
    for i, l in enumerate(lines):
        if re.match(r'^### 5\.1[0-3] ', l):
            j = next((k for k in range(i + 1, len(lines)) if re.match(r'^#{2,3} ', lines[k])), len(lines))
            print('\n### %s' % l.strip())
            for p in [x for x in lines[i + 1:j] if x.strip()]:
                print('  %4d 词 | %s' % (wc(p), p.strip()[:96]))
    return 0


if __name__ == '__main__':
    sys.exit(main())
