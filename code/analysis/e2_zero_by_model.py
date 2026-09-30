# -*- coding: utf-8 -*-
"""按模型列出 base 臂在零池上的出零率（规模/精度/族 × 出零现象）。"""


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
import csv
import glob
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')
D = RP('analysis', 'e2_newh20')
DENSE = ['st_a', 'ucf']


def num(v):
    try:
        return float(str(v).strip())
    except Exception:
        return None


def load(p):
    with open(p, encoding='utf-8-sig') as f:
        return [r for r in csv.DictReader(f) if '#r' not in str(r.get('item', ''))]


def rate(model, ds):
    p = os.path.join(RP('analysis', 'e2_newh20'), 'e1_%s_%s_base.csv' % (model, ds))
    if not os.path.exists(p):
        return None
    rows = load(p)
    if not rows:
        return None
    z = sum(1 for r in rows if num(r.get('pred')) == 0)
    return z, len(rows)


models = sorted(set(os.path.basename(p)[3:].split('_st_')[0].split('_ucf')[0].split('_visdrone')[0].split('_aitod')[0]
                    for p in glob.glob(RP('analysis', 'e2_newh20', 'e1_*.csv'))))
models = [m for m in models if m.endswith('base') is False]
models = sorted(set(m[:-1] if m.endswith('_') else m for m in models))

print('%-26s %-16s %-16s' % ('模型', 'st_a base 出零', 'ucf base 出零'))
print('-' * 62)
for m in models:
    cells = []
    for ds in DENSE:
        r = rate(m, ds)
        cells.append('%d/%d (%.0f%%)' % (r[0], r[1], 100.0 * r[0] / r[1]) if r else '-')
    if any(c != '-' for c in cells):
        print('%-26s %-16s %-16s' % (m, *cells))
