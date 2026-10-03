# -*- coding: utf-8 -*-
"""核对**引用编号 ↔ 参考文献条目**是否对得上：正文首次出现 [n] 的句子 vs 参考表第 n 条。

为什么必须机器核对：编号是按"首次出现顺序"重排过的，重排脚本一旦漏改某处，
就会出现"摘要说 DM-Count [1]，而 [1] 是 MCNN"这类**指向错人**的错误 —— [external-review]一眼能看出来。
判据：逐号打印"正文首次引用处（含前后 90 字）"与"参考表该条目的作者/标题"，由人比对语义。
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

i = t.index('## References')
body, refs_txt = t[:i], t[i:]
# ★ 判据范围必须**含摘要**：PR 的编号规则是"按正文首次出现顺序"，而本稿的 [1][2] 首次出现在摘要末句
#   （"DM-Count [1] … vs P2PNet [2]"）。早先版把范围切在 '## 1. Introduction' 之后，
#   于是把只在摘要出现的 [2] 误报成"正文未引用"——判据范围错了，不是稿子错了。
body_wo = body[body.index('## Abstract'):]

refs = {}
for m in re.finditer(r'(?m)^(\d+)\.\s+(.*)$', refs_txt):
    refs[int(m.group(1))] = m.group(2)

# 正文每个 [n] 的首次出现位置与其上下文
first = {}
for m in re.finditer(r'\[(\d+(?:\s*,\s*\d+)*)\]', body_wo):
    for n in re.findall(r'\d+', m.group(1)):
        n = int(n)
        if n not in first:
            first[n] = (m.start(), body_wo[max(0, m.start() - 90):m.end() + 90].replace('\n', ' '))

bad = []
print('%-5s %-58s %s' % ('[n]', '参考表条目（截断）', '正文首次引用上下文（截断）'))
for n in sorted(refs):
    ctx = first.get(n)
    entry = refs[n][:66]
    print('%-5s %-58s %s' % ('[%d]' % n, entry, (ctx[1][:120] if ctx else '**正文未引用**')))
    if ctx is None:
        bad.append(n)

# 关键词一致性：条目里的姓氏是否出现在首次引用的上下文里（弱判据，只用于提示人工复核）
print()
print('弱判据（姓氏字母是否出现在该处上下文；不出现则人工复核）：')
for n in sorted(first):
    if n not in refs:
        continue
    surname = refs[n].split(',')[0].strip()
    surname = re.sub(r'^\[dataset\]\s*', '', surname)
    ctx = first[n][1]
    if surname and surname.lower() not in ctx.lower():
        print('  [%d] 首次引用处未出现姓氏 %-14s → 需人工确认是否指错人' % (n, surname))
    else:
        print('  [%d] 姓氏 %-16s 出现 ✓' % (n, surname))
print()
seq = [n for n, _ in sorted(first.items(), key=lambda kv: kv[1][0])]
print('首次出现顺序：%s' % seq)
print('是否单调递增（= 参考文献按首次出现顺序编号）：%s'
      % ('是 ✓' if seq == sorted(seq) else '否 ✗ —— 需重排编号或调换条目'))
print()
if bad:
    print('UNREFERENCED_IN_BODY: %s' % bad)
else:
    print('全部条目都在正文（含摘要）出现 ✓')
if seq != sorted(seq):
    raise SystemExit(1)
