# -*- coding: utf-8 -*-
"""_dump_pp_sentences.py —— 把主稿里所有含 "N pp" 的完整句子（含前后各 120 字上下文）写成 txt。
只读产物：_pp_context_dump.txt。用途：人工为 A3 白名单分类。"""
import io
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')
EN = r'<WORKDIR>\PaperB\PaperB_英文稿_PR_20260919.md'
OUT = r'<WORKDIR>\PaperB\analysis\work\_pp_context_dump.txt'
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
