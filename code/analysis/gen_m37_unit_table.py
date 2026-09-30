# -*- coding: utf-8 -*-
"""gen_m37_unit_table.py — 从冻结的 `equalcount36_result.json` **生成** M.37 的逐单元可复算表（防手打）。

盲审 #26（dsflash）："将 F.9 加一个可复算的 36-unit 版作为并列表"；#24（gpt6sol，阻塞）：
"用 M.37 逐项记录生成正文表"。于是把 36 个单元的 span / k=4 等点数 span 排成紧凑表，
放到 M.37（可复算集所在的那一节），并在表下写明冻结件与 md5。
输出：`_m37_unit_table.md`（供补丁脚本插入正文），并打印词数供预算核算。
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
import hashlib
import io
import json
import os
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
W = RP('analysis', 'work')
src = RP('analysis', 'work', 'equalcount36_result.json')
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
io.open(RP('analysis', 'work', '_m37_unit_table.md'), 'w', encoding='utf-8', newline='\n').write(table + '\n')
n_words = len(table.split())
print('已生成 _m37_unit_table.md：%d 行、约 %d 词；冻结件 md5 %s' % (len(lines), n_words, h[:12]))
print('  头 6 行：')
for l in lines[:6]:
    print('   ', l[:120])
print('  尾 3 行：')
for l in lines[-3:]:
    print('   ', l[:120])
