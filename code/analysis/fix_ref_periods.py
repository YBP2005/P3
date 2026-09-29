#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""fix_ref_periods.py — strip the duplicated sentence period after DOIs/URLs in the references.

Charge (`grok47` #23, CONFIRMED): references 1, 2, 14, 18, 19, 31-33, 35-37, 41, 42, 45, 46 end with
".." because the DOI string already carries the reference-terminating period.  15 entries.

This script asserts that exactly those 15 lines match, so it cannot silently rewrite something else.

Usage: python fix_ref_periods.py [--check]
"""
import io
import re
import sys

MAIN = r'<WORKDIR>\PaperB\PaperB_英文稿_PR_20260919.md'
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

io.open(MAIN, 'w', encoding='utf-8', newline='').write('\n'.join(new))
print('stripped the duplicated period on %d reference entries: %s' % (len(nums), nums))
