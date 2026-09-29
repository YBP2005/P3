
import io, os, sys
script, old, new = sys.argv[1], sys.argv[2], sys.argv[3]
path = '/root/' + script
bak = path + '.bak32b'
src = io.open(path, encoding='utf-8').read()
if not os.path.exists(bak):
    io.open(bak, 'w', encoding='utf-8').write(src)
    print('BACKUP_CREATED %s' % bak)
else:
    print('BACKUP_EXISTS %s' % bak)
n = src.count(old)
print('OCCURRENCES_IN_CURRENT=%d' % n)
if n == 0:
    if new in src:
        print('ALREADY_PATCHED')
        sys.exit(0)
    print('PATCH_FAIL: pattern not found')
    sys.exit(2)
src2 = src.replace(old, new, 1)
# 若 os 未导入则补上
if 'import os' not in src2 and 'import argparse, base64' not in src2:
    lines = src2.split('\n')
    for i, l in enumerate(lines):
        if l.startswith('import ') or l.startswith('from '):
            continue
        lines.insert(i, 'import os')
        break
    src2 = '\n'.join(lines)
io.open(path, 'w', encoding='utf-8').write(src2)
print('PATCHED_OK')
