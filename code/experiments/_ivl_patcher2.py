# -*- coding: utf-8 -*-
"""_ivl_patcher2.py — 读配置补丁：每行 script<TAB>old<TAB>new"""
import io, os, sys
cfg = io.open(sys.argv[1], encoding='utf-8').read().split('\n')
for line in cfg:
    line = line.rstrip('\r')
    if not line.strip() or line.startswith('#'):
        continue
    script, old, new = line.split('\t')
    path = '/root/' + script
    bak = path + '.bak32b'
    src = io.open(path, encoding='utf-8').read()
    if not os.path.exists(bak):
        io.open(bak, 'w', encoding='utf-8').write(src)
        print('%s: BACKUP_CREATED' % script)
    else:
        print('%s: BACKUP_EXISTS' % script)
    if new in src:
        print('%s: ALREADY_PATCHED' % script)
        continue
    n = src.count(old)
    if n == 0:
        print('%s: PATCH_FAIL pattern_not_found' % script)
        continue
    src2 = src.replace(old, new, 1)
    if 'import os' not in src2:
        lines = src2.split('\n')
        for i, l in enumerate(lines):
            if l.startswith('import ') or l.startswith('from '):
                continue
            lines.insert(i, 'import os')
            break
        src2 = '\n'.join(lines)
        print('%s: injected import os' % script)
    io.open(path, 'w', encoding='utf-8').write(src2)
    print('%s: PATCHED_OK (occurrences=%d)' % (script, n))
