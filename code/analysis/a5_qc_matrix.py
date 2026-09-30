# -*- coding: utf-8 -*-
"""A5 质检矩阵：7 家族 × 4 域（base 臂、零池）的答案类别分布 + 解析率 + ERR。

类别判定与 a5_report.py 同源（abstain 词 > 数字 0/非零 > unparsed）。
用途：写 M.19 之前先确认"某家族几乎不出零"不是解析坏掉造成的。
用法：python a5_qc_matrix.py [merged_dir] [nonzero_dir]
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
import csv
import io
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')
D = sys.argv[1] if len(sys.argv) > 1 else RP('analysis', 'e2xt_a800', 'merged')
DNZ = sys.argv[2] if len(sys.argv) > 2 else RP('analysis', 'e2xt_a800', 'nonzero')
DS = ['st_a', 'ucf', 'visdrone', 'aitod']
ABSTAIN = ('abstain', 'cannot_judge', 'no_people')
FAMS = ['gemma3-12b', 'InternVL3_5-8B', 'Phi-3.5-vision-instruct',
        'llava-onevision-qwen2-7b-ov', 'qwen3-vl-32b-awq', 'qwen25vl-72b-awq',
        'internvl25-8b-awq']


def cls(r):
    raw = str(r.get('raw') or '').lower()
    p = str(r.get('pred') or '').strip()
    for k in ABSTAIN:
        if k in raw:
            return k
    if p == '':
        return 'unparsed'
    try:
        return 'zero' if float(p) == 0 else 'nonzero'
    except ValueError:
        return 'unparsed'


def table(d, suffix=''):
    print('== %s ==' % (d + suffix))
    print('%-26s %-9s %5s %5s %5s %5s %6s %5s %5s' %
          ('家族', '域', 'n', 'zero', 'nz', 'unprs', 'ERR', '0率', '解析率'))
    for f in FAMS:
        for ds in DS:
            p = os.path.join(d, 'e1_%s_%s_base%s.csv' % (f, ds, suffix))
            if not os.path.exists(p):
                continue
            rows = list(csv.DictReader(io.open(p, encoding='utf-8-sig')))
            if not rows:
                continue
            c = {}
            err = 0
            for r in rows:
                k = cls(r)
                if str(r.get('raw') or '').startswith('ERR:'):
                    err += 1
                c[k] = c.get(k, 0) + 1
            n = len(rows)
            ok = sum(1 for r in rows if str(r.get('parse_ok')) == '1')
            print('%-26s %-9s %5d %5d %5d %5d %6d %5.3f %5.3f'
                  % (f, ds, n, c.get('zero', 0), c.get('nonzero', 0),
                     c.get('unparsed', 0), err, c.get('zero', 0) / float(n), ok / float(n)))
    print()


table(D)
if os.path.isdir(DNZ):
    table(DNZ)
