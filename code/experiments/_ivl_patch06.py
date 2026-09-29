# -*- coding: utf-8 -*-
"""_ivl_patch06.py — 幂等修复 06 汇总段的空 pred 崩溃"""
import io, os, sys

path = '/root/06_dense_vlm.py'
bak = path + '.bak32b'
src = io.open(path, encoding='utf-8').read()

if not os.path.exists(bak):
    io.open(bak, 'w', encoding='utf-8').write(src)
    print('BACKUP_CREATED')

if '# IVL-FIX' in src:
    print('ALREADY_PATCHED')
    sys.exit(0)

OLD = """    with open(out_csv, encoding='utf-8-sig', newline='') as f:
        for r in csv.DictReader(f):
            if r.get('parse_ok') == '1':
                P_.append(int(float(r['pred']))); T_.append(int(float(r['gt'])))"""

NEW = """    with open(out_csv, encoding='utf-8-sig', newline='') as f:
        for r in csv.DictReader(f):
            if not (r.get('pred') or '').strip():   # IVL-FIX: 空 pred（文本格式漂移）跳过
                continue
            if r.get('parse_ok') == '1':
                P_.append(int(float(r['pred']))); T_.append(int(float(r['gt'])))"""

if OLD not in src:
    print('PATTERN_NOT_FOUND')
    print('--- 实际 line 185-195 ---')
    lines = src.split('\n')
    for i in range(183, min(196, len(lines))):
        print('%4d| %s' % (i + 1, lines[i]))
    sys.exit(2)

src = src.replace(OLD, NEW, 1)
io.open(path, 'w', encoding='utf-8').write(src)
print('PATCHED_OK')
