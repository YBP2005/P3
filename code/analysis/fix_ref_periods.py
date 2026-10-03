#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""fix_ref_periods.py — strip the duplicated sentence period after DOIs/URLs in the references.

Charge ([external-review] #23, CONFIRMED): references 1, 2, 14, 18, 19, 31-33, 35-37, 41, 42, 45, 46 end with
".." because the DOI string already carries the reference-terminating period.  15 entries.

This script asserts that exactly those 15 lines match, so it cannot silently rewrite something else.

Usage: python fix_ref_periods.py [--check]
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

MAIN = RP('PaperB_英文稿_PR_20260919.md')
EXPECT = [1, 2, 14, 18, 19, 31, 32, 33, 35, 36, 37, 41, 42, 45, 46]

text = io.open(MAIN, encoding='utf-8', newline='').read()
lines = text.split('\n')

# The reference list runs from the first "1. <Author>" after the References heading to the last entry.
start = next(i for i, l in enumerate(lines) if l.startswith('## References'))
end = next(i for i in range(start, len(lines)) if lines[i].startswith('## ') and i > start)
nums, new = [], list(lines)
for i in range(start, end):
    m = re.match(r'^(\d+)\.\s', lines[i])
    if not m:
        continue
    if lines[i].rstrip().endswith('..'):
        nums.append(int(m.group(1)))
        new[i] = lines[i].rstrip()[:-1]

if '--check' in sys.argv:
    ok = nums == EXPECT
    print('double-period entries: %s' % nums)
    print('CHECK: %s' % ('PASS' if ok else 'FAIL'))
    raise SystemExit(0 if ok else 1)

if nums != EXPECT:
    print('ABORT: found %s, expected %s' % (nums, EXPECT))
    raise SystemExit(1)

if '--apply' in sys.argv:           # ★ 2026-09-30 v0610：默认**只读**，写回须显式 --apply
    io.open(MAIN, 'w', encoding='utf-8', newline='').write('\n'.join(new))
    print('stripped the duplicated period on %d reference entries: %s' % (len(nums), nums))
else:
    print('（dry run：将剥离 %d 条参考文献的多余句点 %s，**未**写回主稿；加 --apply 才写）'
          % (len(nums), nums))
