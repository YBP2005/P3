# -*- coding: utf-8 -*-
"""A5 消融报告：输入尺度（native / s640 / s1536）与模板（sys）对**契约效应**的影响，
外加 native 与主跑的一致性（复现性）。

读三个来源：
  · 主跑：analysis/e2xt_a800/zero/e1_<fam>_<ds>_<arm>.csv        （19e）
  · 消融：analysis/e2xt_a800/ablate/e1_<fam>_<ds>_<arm>_<variant>.csv （19f）
判据（先写死）：
  · 复现性：native vs 主跑，逐 item 的（类别）一致率 ≥95% 视为可复现；
  · 尺度中性：s640 / s1536 下 permit 的"仍答 0"比例与 native 之差 ≤5 pp；
  · 模板中性：sys 下同上；
  任何一条不满足，就照实写"契约效应是输入尺度/模板的函数"，不得含糊。
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
from collections import Counter

sys.stdout.reconfigure(encoding='utf-8')
MAIN = RP('analysis', 'e2xt_a800', 'zero')
FAM = sys.argv[1] if len(sys.argv) > 1 else 'gemma3-12b'
ABL = sys.argv[2] if len(sys.argv) > 2 else RP('analysis', 'e2xt_a800', 'ablate')
DOMS = sys.argv[3].split(',') if len(sys.argv) > 3 else ['st_a', 'ucf']
ABSTAIN = ('abstain', 'cannot_judge', 'no_people')
VARIANTS = ['native', 's640', 's1536', 'native_sys']


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


def load(p):
    if not os.path.exists(p):
        return None
    return {r['item']: (cls(r), str(r.get('pred') or '').strip())
            for r in csv.DictReader(io.open(p, encoding='utf-8-sig'))}


def variant_path(ds, arm, v):
    return os.path.join(ABL, 'e1_%s_%s_%s_%s.csv' % (FAM, ds, arm, v))


def show(ds, variants):
    print('--- %s ---' % ds)
    base_main = load(os.path.join(RP('analysis', 'e2xt_a800', 'zero'), 'e1_%s_%s_base.csv' % (FAM, ds)))
    if not base_main:
        print('  主跑缺 base')
        return
    zl = [k for k, v in base_main.items() if v[0] == 'zero']
    print('  主跑 base：n=%d 答0=%d（%.3f）' % (len(base_main), len(zl), len(zl) / float(len(base_main))))
    pm = load(os.path.join(RP('analysis', 'e2xt_a800', 'zero'), 'e1_%s_%s_permit.csv' % (FAM, ds)))
    if pm and zl:
        still = sum(1 for k in zl if pm.get(k, ('', ''))[0] == 'zero')
        print('  主跑 permit 仍答0：%d/%d（%.3f）' % (still, len(zl), still / float(len(zl))))
    for v in variants:
        b = load(variant_path(ds, 'base', v))
        p = load(variant_path(ds, 'permit', v))
        if not b:
            print('  %-8s 缺' % v)
            continue
        zv = [k for k, x in b.items() if x[0] == 'zero']
        rate = len(zv) / float(len(b))
        agree = sum(1 for k in set(b) & set(base_main) if b[k][0] == base_main[k][0])
        den = len(set(b) & set(base_main))
        still = sum(1 for k in zl if p and p.get(k, ('', ''))[0] == 'zero') if p else None
        print('  %-8s n=%-4d 答0=%-4d(%.3f)  与主跑类别一致=%.3f   permit 仍答0=%s/%d'
              % (v, len(b), len(zv), rate, agree / float(den) if den else float('nan'),
                 ('%d' % still) if still is not None else '缺', len(zl)))
    print()


for _ds in DOMS:
    show(_ds, VARIANTS)
print('家族=%s  消融目录=%s' % (FAM, ABL))

# 确定性：reps=3 目录
REP = RP('analysis', 'e2xt_a800', 'reps')
if os.path.isdir(REP):
    print('--- 确定性（reps=3，独立目录，st_a 前 60 项）---')
    for arm in ('base', 'permit'):
        p = os.path.join(RP('analysis', 'e2xt_a800', 'reps'), 'e1_%s_st_a_%s_native.csv' % (FAM, arm))
        if not os.path.exists(p):
            continue
        rows = list(csv.DictReader(io.open(p, encoding='utf-8-sig')))
        by = {}
        for r in rows:
            it = r['item'].split('#r')[0]
            by.setdefault(it, []).append(cls(r))
        full = sum(1 for k, v in by.items() if len(set(v)) == 1 and len(v) == 3)
        multi = {k: v for k, v in by.items() if len(v) == 3}
        print('  %-7s item=%d 三次全同=%d（%.3f）' % (arm, len(multi), full,
                                                      full / float(len(multi)) if multi else float('nan')))
        dis = [(k, v) for k, v in multi.items() if len(set(v)) > 1][:3]
        for k, v in dis:
            print('      不一致示例 %s -> %s' % (k, v))
