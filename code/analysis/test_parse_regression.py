# -*- coding: utf-8 -*-
"""回归自测：证明**旧整数正则**在一位小数评分表上会静默错读，而新正则不会。

不依赖真实产物：直接读合成产物（make_test_sheet.py 生成）。
判据：旧正则必须复现两个错读（`12.5/15`→`5/15`、`84.0`→`84`），否则说明自测没钉住问题；
      新正则必须逐维等于期望值，且总分/专项一致。
"""
import io
import os
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')

P = r'<WORKDIR>\PaperB\analysis\work\_test_review_dir\m4prime_review_dsflash_20990101_000000.md'
t = io.open(P, encoding='utf-8').read()

EXP = {'新颖性': (12.5, 15), '技术严谨': (11.5, 15), '实验充分': (13.5, 15),
       '评估公平': (8.5, 10), '可复现': (9.5, 10), '指标合理': (14.5, 15),
       '统计显著': (7.5, 10), '不确定度': (6.5, 10)}
EXP_TOTAL, EXP_SUB = 84.0, 28.5

fails = []

# ---- 旧写法（必须错） ----
old = {}
for k in EXP:
    mm = re.search(re.escape(k) + r'[^\n]{0,80}?(\d+)\s*/\s*(\d+)', t)
    if mm:
        old[k] = (int(mm.group(1)), int(mm.group(2)))
old_total = re.search(r'总分[^\d]{0,12}(\d{1,3})', t)
old_total = int(old_total.group(1)) if old_total else None
old_sub = re.search(r'(?:专项小计|专项)[^\d]{0,12}(\d{1,3})\s*/\s*35', t)
old_sub = int(old_sub.group(1)) if old_sub else None

print('— 旧整数正则（预期：错） —')
print('  新颖性 → %s   （期望 12.5/15，实际被读成 %s）' % (old.get('新颖性'), old.get('新颖性')))
print('  总分   → %s   （期望 84.0，实际被读成 %s）' % (old_total, old_total))
print('  专项   → %s   （期望 28.5）' % old_sub)
if old.get('新颖性') == (5, 15):
    print('  ✓ 已复现 "12.5/15 被读成 5/15" 的静默错读')
else:
    fails.append('旧正则未复现小数错读（自测未钉住问题）')
if old_total == 84:
    print('  ✓ 已复现 "84.0 被截成 84"')
else:
    fails.append('旧正则未复现总分截断')
if old_sub is None:
    print('  ✓ 已复现 "专项小计恒为 None"（标签含 6+7+8，旧 `[^\\d]{0,12}` 跨不过去）')
else:
    fails.append('旧正则居然读到了专项小计=%s' % old_sub)

# ---- 新写法（必须对） ----
NUM = r'(\d+(?:\.\d+)?)'
new = {}
for k in EXP:
    mm = re.search(re.escape(k) + r'[^\n]{0,80}?' + NUM + r'\s*/\s*' + NUM, t)
    if mm:
        new[k] = (float(mm.group(1)), float(mm.group(2)))
new_total = re.search(r'总分[^\d]{0,12}' + NUM, t)
new_total = float(new_total.group(1)) if new_total else None
new_sub = None
for line in t.splitlines():
    if '专项' in line and re.search(r'/\s*35', line):
        c = re.findall(NUM + r'\s*/\s*35', line)
        if c:
            new_sub = float(c[-1])
            break

print()
print('— 新一位小数正则（预期：对） —')
for k, (s, f) in EXP.items():
    got = new.get(k)
    ok = got == (s, f)
    print('  %-10s %s  %s' % (k, got, '✓' if ok else '✗ 期望 %s' % ((s, f),)))
    if not ok:
        fails.append('%s 解析错误: %s' % (k, got))
print('  总分 %s %s' % (new_total, '✓' if new_total == EXP_TOTAL else '✗'))
print('  专项 %s %s' % (new_sub, '✓' if new_sub == EXP_SUB else '✗'))
if new_total != EXP_TOTAL:
    fails.append('总分错误')
if new_sub != EXP_SUB:
    fails.append('专项错误')
s8 = round(sum(v[0] for v in new.values()), 1)
print('  8 维之和 %.1f vs 总分 %s → %s' % (s8, new_total, '自洽 ✓' if abs(s8 - new_total) <= 0.05 else '✗'))
if abs(s8 - new_total) > 0.05:
    fails.append('自洽核对不通过')

print()
if fails:
    print('REGRESSION_FAIL: ' + '; '.join(fails))
    sys.exit(1)
print('REGRESSION_OK：旧正则确实错读、新正则逐维正确且自洽。')
