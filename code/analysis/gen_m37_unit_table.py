# -*- coding: utf-8 -*-
"""gen_m37_unit_table.py — 从冻结的 `equalcount36_result.json` **生成** M.37 的逐单元可复算表（防手打）。

盲审 #26（dsflash）："将 F.9 加一个可复算的 36-unit 版作为并列表"；#24（gpt6sol，阻塞）：
"用 M.37 逐项记录生成正文表"。于是把 36 个单元的 span / k=4 等点数 span 排成紧凑表，
放到 M.37（可复算集所在的那一节），并在表下写明冻结件与 md5。
输出：`_m37_unit_table.md`（供补丁脚本插入正文），并打印词数供预算核算。
"""
import hashlib
import io
import json
import os
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
W = r'<WORKDIR>\PaperB\analysis\work'
src = os.path.join(W, 'equalcount36_result.json')
d = json.loads(io.open(src, encoding='utf-8').read())
units = d['units']
h = hashlib.md5(io.open(src, 'rb').read()).hexdigest()

lines = ['| unit | span (all levels) | span (equal-count, k=4) |',
         '|---|---|---|']
for u in sorted(units, key=lambda x: -x['span']):
    eq4 = u.get('span_eq4')
    lines.append('| %s | %.1f | %s |' % (u['unit'], u['span'],
                                         ('%.1f' % eq4) if eq4 is not None else '—'))
table = '\n'.join(lines)
io.open(os.path.join(W, '_m37_unit_table.md'), 'w', encoding='utf-8', newline='\n').write(table + '\n')
n_words = len(table.split())
print('已生成 _m37_unit_table.md：%d 行、约 %d 词；冻结件 md5 %s' % (len(lines), n_words, h[:12]))
print('  头 6 行：')
for l in lines[:6]:
    print('   ', l[:120])
print('  尾 3 行：')
for l in lines[-3:]:
    print('   ', l[:120])
