# -*- coding: utf-8 -*-
"""g15_levels.py —— 【G15 第二步】逐族列出**阶梯的实际档位集合**（动程取证）。

与 `g15_travel_extract.py` 的分工：那支看的是 `threeway_curves*.csv`（ρ 汇总表），
这一支看的是**构造 M.37 那 36 个单元时真正读的 AUX 逐图/逐档文件**
（`eb2_equalcount36.py` L68–L130 指明的那批），因此是本报告"动程"的唯一权威来源。

只读，不改任何已有文件。
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
import collections
import csv
import glob
import io
import os
import re
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
ROOT = NR()
DATA = NR('analysis', 'data')
PM = RP('analysis', 'data', 'pod_mirror')
W = NR('@shared', 'work')          # ★ 与 eb2_equalcount36.py L23 同源：dm_ladder.csv 在这里
B = NR('@shared', 'work', 'b_harvest_20260917')


def load(p):
    return list(csv.DictReader(io.open(p, encoding='utf-8-sig', errors='replace')))


def show(title, path, dimcols):
    print('\n--- %s' % title)
    print('    文件：%s' % path)
    if not os.path.exists(path):
        print('    **不存在**')
        return None
    rows = load(path)
    print('    行数 %d ｜ 列 %s' % (len(rows), list(rows[0].keys())))
    if not rows:
        return None
    vals = collections.defaultdict(set)
    for r in rows:
        for c in dimcols:
            if c in r and r[c] not in (None, ''):
                vals[c].add(str(r[c]).strip())

    def srt(s):
        try:
            return (0, float(s))
        except ValueError:
            return (1, str(s))
    for c in dimcols:
        v = sorted(vals.get(c, []), key=srt)
        if not v:
            continue
        line = '      %-8s %d 档：%s' % (c, len(v), v if len(v) <= 20 else v[:20] + ['…'])
        print(line)
        nums = []
        for x in v:
            try:
                nums.append(float(x))
            except ValueError:
                pass
        if len(nums) >= 2:
            nums.sort()
            r = (nums[-1] / nums[0]) if nums[0] else float('nan')
            print('      %-8s ⇒ min=%g max=%g ｜ max/min = %s ｜ max−min = %g'
                  % ('', nums[0], nums[-1], ('%.3f' % r) if nums[0] else 'undefined(min=0)',
                     nums[-1] - nums[0]))
    return {c: sorted(vals.get(c, []), key=srt) for c in dimcols}


print('=' * 104)
print('【A】检测 τ 的三条阶梯（M.37 的 det 单元就是从这里建的）')
print('=' * 104)
show('det·in-domain/VisDrone', RP('analysis', 'data', 'pod_mirror', 'A', 'det_yolo_ladder_visdrone_det.csv'), ['tau', 'imgsz'])
show('det·zero-shot COCO', RP('analysis', 'data', 'pod_mirror', 'A', 'det_yolo_ladder_yolo12n.csv'), ['tau', 'imgsz'])
bbbc = None
for cand in (NR('@shared', 'work', 'b_harvest_20260917', 'bbbc_eval', 'ladder.csv'),
             NR('analysis', 'data', 'bbbc_eval', 'ladder.csv'),
             RP('analysis', 'data', 'pod_mirror', 'bbbc_eval', 'ladder.csv')):
    if os.path.exists(cand):
        bbbc = cand
if bbbc:
    show('det·in-domain(micro)/BBBC005', bbbc, ['tau', 'imgsz'])
else:
    print('\n--- det·in-domain(micro)/BBBC005: **未找到 ladder.csv**（下面用 glob 找）')
    for g in glob.glob(NR('analysis', 'data', '**', '*bbbc*'), recursive=True)[:10]:
        print('    %s' % g)

print()
print('=' * 104)
print('【B】密度回归：official DM-Count / CSRNet')
print('=' * 104)
show('density·official DM-Count（work/dm_ladder.csv）', NR('@shared', 'work', 'dm_ladder.csv'),
     ['dataset', 'protocol', 'value'])
show('density·CSRNet / st_a', RP('analysis', 'data', 'pod_mirror', 'A', 'csrsta_ladder_st_a.csv'), ['protocol', 'value'])
show('density·CSRNet / ucf', RP('analysis', 'data', 'pod_mirror', 'A', 'csrucf_ladder_ucf.csv'), ['protocol', 'value'])

print()
print('=' * 104)
print('【C】VLM 像素预算（res_ctrl）：budget 列')
print('=' * 104)
seen = set()
for mdl in ('q32', 'ivl'):
    for f in sorted(glob.glob(os.path.join(RP('analysis', 'data', 'pod_mirror'), 'res_ctrl__%s' % mdl, 'res_ctrl_*.csv'))):
        ds = os.path.basename(f)[len('res_ctrl_'):-4]
        rows = load(f)
        bs = sorted({float(r['budget']) for r in rows})
        if (mdl, ds) not in seen:
            print('    %-6s %-10s budget 档位（%d）：%s' % (mdl, ds, len(bs), bs))
            seen.add((mdl, ds))
print('    ⇒ 全部单元共用同一组 5 档；最小档 = 0 ⇒ **相对动程按比例定义时不可用**（见报告）。')

print()
print('=' * 104)
print('【D】VLM 切块：档位标签是 "whole"/"tile<N>"（N = 切块网格边长）')
print('=' * 104)
for sub in ('tile_results', 'b2__out_32b_ctile', 'b2__out_8b_ctile'):
    d = os.path.join(RP('analysis', 'data', 'pod_mirror'), sub)
    if not os.path.isdir(d):
        print('    %-22s **目录不存在**' % sub)
        continue
    lv = collections.defaultdict(set)
    for f in sorted(os.listdir(d)):
        m = re.match(r'^vlm_([a-z0-9]+)_(base|over|under|[a-z0-9]+)_(whole|tile\d+)\.csv$', f)
        if m:
            lv[(m.group(1), m.group(2))].add(m.group(3))
    print('    %s：目录存在；组数 %d' % (sub, len(lv)))
    agg = collections.defaultdict(set)
    for k, v in lv.items():
        agg[k[1]] |= v
    for arm, v in sorted(agg.items()):
        print('       arm=%-8s 档位 %s' % (arm, sorted(v)))

print()
print('=' * 104)
print('【E】VLM 输出契约：arm 列（类别型）')
print('=' * 104)
for mdl in ('ivl', 'q32'):
    p = os.path.join(RP('analysis', 'data', 'pod_mirror'), 'b2__out_%s' % mdl, 'E1.csv')
    if os.path.exists(p):
        rows = load(p)
        print('    %-4s arms（%d）：%s' % (mdl, len({r['arm'] for r in rows}), sorted({r['arm'] for r in rows})))
    else:
        print('    %-4s **%s 不存在**' % (mdl, p))

print()
print('=' * 104)
print('【F】VLM 提示词族：V1..V5（类别型）')
print('=' * 104)
for sub in ('dense_prompt_results', 'ivl_dense_prompt_results'):
    d = os.path.join(RP('analysis', 'data', 'pod_mirror'), sub)
    if not os.path.isdir(d):
        print('    %-28s **目录不存在**' % sub)
        continue
    g = collections.defaultdict(set)
    for f in sorted(os.listdir(d)):
        m = re.match(r'^([a-z0-9]+)_(base|over|under)_(V\d+)_([a-z_]+)\.csv$', f)
        if m:
            g[(m.group(1), m.group(2), m.group(4))].add(m.group(3))
    print('    %s：组数 %d' % (sub, len(g)))
    seenv = set()
    for k, v in sorted(g.items()):
        if k[1:] not in seenv:
            print('       dom/arm/…=%-32s 提示词档位 %s' % (str(k[1:]), sorted(v)))
            seenv.add(k[1:])
