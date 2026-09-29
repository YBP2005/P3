# -*- coding: utf-8 -*-
"""路线 A 第三刀：把 §7.5 / §7.8 / §7.10 三节**逐字迁入附录 M.26**，正文只留标题 + 一句指针。
（三节合计约 1 100 字符；正文 36 页、硬上限 35。）
"""
import io
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')
EN = r'<WORKDIR>\PaperB\PaperB_英文稿_PR_20260919.md'
SUP = r'<WORKDIR>\PaperB\PaperB_英文补充材料_PR_20260919.md'
en = io.open(EN, encoding='utf-8', newline='').read()

SECS = ['### 7.5 Saturation slope: a same-lineage scale difference, verified two ways',
        '### 7.8 The quantitative structure of relative deviation',
        '### 7.10 An independent endorsement of enumeration over regression']
moved = []
for k in SECS:
    i = en.index(k)
    m = re.search(r'\n(?=### 7\.\d+ )', en[i + 5:])
    j = i + 5 + m.start() if m else len(en)
    body = en[i + len(k):j].strip('\n')
    moved.append((k, body))
    keep = k + '\n\n*(Moved verbatim to Appendix M.26; the pointer to its frozen numbers is unchanged.)*\n\n'
    en = en[:i] + keep + en[j:]

appendix = ('\n---\n\n### M.26 Three short §7 results, moved verbatim (7.5, 7.8, 7.10)\n\n'
            'Their conclusions are cited in the main text where they bear on an argument; the bodies are '
            'reproduced here so that no wording is lost in the move.\n\n')
for k, body in moved:
    appendix += '#### ' + k[4:] + '\n\n' + body + '\n\n'
io.open(SUP, 'a', encoding='utf-8', newline='\n').write(appendix)
io.open(EN + '.bak_pre_m26', 'w', encoding='utf-8', newline='').write(en)
io.open(EN, 'w', encoding='utf-8', newline='').write(en)
print('已迁移 %d 节 → M.26（%d 字符）' % (len(moved), len(appendix)))
print('正文总字符：%d' % len(en))
