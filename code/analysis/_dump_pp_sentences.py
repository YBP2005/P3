# -*- coding: utf-8 -*-
"""_dump_pp_sentences.py —— 把主稿里所有含 "N pp" 的完整句子（含前后各 120 字上下文）写成 txt。
只读产物：_pp_context_dump.txt。用途：人工为 A3 白名单分类。"""


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
EN = RP('PaperB_英文稿_PR_20260919.md')
OUT = RP('analysis', 'work', '_pp_context_dump.txt')
CALIBER = ('person-matched', 'all-detections', 'all-class', 'pooled', 'per-item', 'per image',
           'base arm', 'base contract', 'equal-count', 'random', 'caliber', 'sensitivity',
           'specificity', 'GT-weighted', 'unweighted', 'shared', 'per-unit', 'median', 'channel',
           'contract')

en = io.open(EN, encoding='utf-8', newline='').read()
flat = re.sub(r'\s+', ' ', en)
sents = re.split(r'(?<=[.!?])\s+', flat)
out = []
k = 0
for s in sents:
    if not re.search(r'\d[\d.,]*\s*pp\b', s):
        continue
    k += 1
    has = any(c.lower() in s.lower() for c in CALIBER)
    out.append('=' * 100)
    out.append('#%02d  %s  len=%d' % (k, 'CALIBRATED' if has else 'UNLABELED', len(s)))
    out.append(s.strip())
    out.append('')
io.open(OUT, 'w', encoding='utf-8', newline='\n').write('\n'.join(out))
print('sentences=%d  written=%s' % (k, OUT))
