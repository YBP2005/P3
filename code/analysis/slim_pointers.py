# -*- coding: utf-8 -*-
"""把正文里 28 处冗长的附录定位括注统一压成 `*(Numbers: X.Y.)*`。

动机：PR 官方限 20–35 页（含图表与参考文献），当前实测 35 页贴顶、零余量。
这些括注**只是定位符**（"本段逐格数字见附录 M.11"），不含任何主张或数字 ⇒
压缩它们不损失内容，却能把正文压回安全区。脚本先打印全部替换对，再落盘并复核词数。
"""
import io
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')
P = r'<WORKDIR>\PaperB\PaperB_英文稿_PR_20260919.md'
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

io.open(P, 'w', encoding='utf-8', newline='').write(new)


def wc(s):
    a = s[s.index('## Abstract'):]
    return len(re.findall(r'\S+', a))


print('正文（Abstract 之后）词数：%d → %d（省 %d）'
      % (wc(t), wc(new), wc(t) - wc(new)))
