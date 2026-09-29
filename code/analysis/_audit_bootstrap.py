# -*- coding: utf-8 -*-
"""_audit_bootstrap.py —— 只读：审计主稿与补充材料里每一处 bootstrap 次数声称，打印上下文。
用途：核对 N,000× 是否与其来源脚本一致（本轮发现主稿 §4.3 的 3,000× 与细网格 run 的 4,000× 不符）。"""
import io
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')
D = r'<WORKDIR>\PaperB'
for name, p in (('EN ', D + r'\PaperB_英文稿_PR_20260919.md'),
                ('SUP', D + r'\PaperB_英文补充材料_PR_20260919.md')):
    t = io.open(p, encoding='utf-8', newline='').read()
    flat = re.sub(r'\s+', ' ', t)
    print('=' * 100)
    print('■ %s  文件词数 %d' % (name, len(re.findall(r"[A-Za-z][A-Za-z'\-]*", t))))
    for m in re.finditer(r'bootstrap', flat):
        a, b = max(0, m.start() - 130), m.start() + 130
        print('  ...%s...' % flat[a:b])
        print()
