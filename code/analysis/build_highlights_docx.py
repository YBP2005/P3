# -*- coding: utf-8 -*-
"""生成 PR 要求的 Highlights（.docx）：3–5 条，**每条 ≤85 字符**（含空格），硬断言。

每条都必须能在正文里找到对应主张（脚本里逐条注明出处），不允许写真话但无处可查的漂亮句子。
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
import sys

sys.stdout.reconfigure(encoding='utf-8')
from docx import Document
from docx.shared import Pt

ROOT = NR()
OUT = NR('PaperB_Highlights.docx')
LIMIT = 85

ITEMS = [
    ('Abstention, not underestimation, drives 82-94% of the dense-scene under-count.', '§5.5 / Abstract'),
    ('An answered zero is a suppressed abstention: one token removes it, 46 of 52 cells.', '§5.7 census / M.18.3'),
    ('Dense-scene zeros are build-specific: 9% vs 99% for two builds of one checkpoint.', '§5.7 / M.18.4'),
    ('Aerial-scene zeros are domain-specific: 11 of 12 configurations give 62-99%.', 'M.18.4'),
    ('Contract-stated abstention saturates in dense scenes, and stays selective in aerial.', '§3.6(d) / M.18.5'),
]

bad = [t for t, _ in ITEMS if len(t) > LIMIT]
for t, src in ITEMS:
    print('%3d 字符  %s   [%s]' % (len(t), t, src))
assert 3 <= len(ITEMS) <= 5, '条数必须为 3–5'
assert not bad, '超出 %d 字符：%s' % (LIMIT, bad)

doc = Document()
st = doc.styles['Normal']
st.font.name = 'Times New Roman'
st.font.size = Pt(12)
for t, _ in ITEMS:
    p = doc.add_paragraph(t, style='List Bullet')
    p.paragraph_format.space_after = Pt(6)
doc.save(OUT)
print()
print('写出 %s（%d B，%d 条，最长 %d 字符 ≤ %d）'
      % (OUT, os.path.getsize(OUT), len(ITEMS), max(len(t) for t, _ in ITEMS), LIMIT))
