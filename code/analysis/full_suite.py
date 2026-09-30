# -*- coding: utf-8 -*-
"""全套重跑（顺序即依赖）：实测分页 → 收尾/派生件同步 → 五项校验。
任何一步 rc!=0 就打印完整输出并停止（不掩盖失败）。
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
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding='utf-8')
W = RP('analysis', 'work')
STEPS = ['remeasure.py', 'en_finalize3.py', 'en_check.py', 'verify_objective.py',
         'cite_guard.py', 'identity_guard.py', 'a26_new_anchors.py', 'final_acceptance.py', 'pack_framing.py']

fails = []
for s in STEPS:
    p = os.path.join(RP('analysis', 'work'), s)
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
