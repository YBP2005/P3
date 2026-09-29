# -*- coding: utf-8 -*-
"""全套重跑（顺序即依赖）：实测分页 → 收尾/派生件同步 → 五项校验。
任何一步 rc!=0 就打印完整输出并停止（不掩盖失败）。
"""
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding='utf-8')
W = r'<WORKDIR>\PaperB\analysis\work'
STEPS = ['remeasure.py', 'en_finalize3.py', 'en_check.py', 'verify_objective.py',
         'cite_guard.py', 'identity_guard.py', 'a26_new_anchors.py', 'final_acceptance.py', 'pack_framing.py']

fails = []
for s in STEPS:
    p = os.path.join(W, s)
    r = subprocess.run([sys.executable, p], capture_output=True, text=True,
                       encoding='utf-8', errors='replace', cwd=W, timeout=1800)
    tail = (r.stdout or '').rstrip().split('\n')
    print('=' * 100)
    print('### %s  rc=%d' % (s, r.returncode))
    print('=' * 100)
    show = tail if r.returncode != 0 else tail[-14:]
    for l in show:
        print('   ' + l)
    if r.returncode != 0:
        if r.stderr:
            print('   --- stderr ---')
            for l in (r.stderr or '').rstrip().split('\n')[:25]:
                print('   ' + l)
        fails.append(s)

print()
print('#' * 100)
if fails:
    print('失败步骤：%s' % fails)
    sys.exit(1)
print('全套通过：%s' % STEPS)
