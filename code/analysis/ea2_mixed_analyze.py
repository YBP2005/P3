# -*- coding: utf-8 -*-
"""ea2_mixed_analyze.py — E2 的**非零对照侧**：用已冻结的普查三臂结果算"gt>0 项目"上的通道构成，
与 E2 的真零池（gt=0）并列，回答预注册条款的"**混合真零／非零**图像"这一条。

数据：`/root/e1_results`（123 份，已拉回 `analysis/e1_results_census/`）——与 E1/E3 同一支探针、同一批构建。
口径：raw-match（同 `a5_judge.cls()`）；**只统计 gt>0 的项目**（真零侧由 Z0 的 gt=0 单独报告）。
产物：`analysis/work/ea2_mixed_result.json`（+ .md5）
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
import hashlib
import io
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
CEN = RP('analysis', 'e1_results_census')
OUT = RP('analysis', 'work', 'ea2_mixed_result.json')
BUILDS = ['InternVL3_5-8B', 'Phi-3.5-vision-instruct', 'llava-onevision-qwen2-7b-ov',
          'gemma3-12b', 'Qwen3-VL-32B-Instruct']
DENSE, AERIAL = ('st_a', 'ucf'), ('visdrone', 'aitod')


def cls_of(raw, pred):
    r = (raw or '').lower()
    for k in ('abstain', 'cannot_judge', 'no_people'):
        if k in r:
            return k
    p = (pred or '').strip()
    if p == '':
        return 'unparsed'
    try:
        return 'zero' if float(p) == 0 else 'nonzero'
    except ValueError:
        return 'unparsed'


def dist(d):
    c = collections.Counter(d.values())
    n = len(d) or 1
    return {k: round(100.0 * c.get(k, 0) / n, 1) for k in
            ('zero', 'nonzero', 'no_people', 'cannot_judge', 'abstain', 'unparsed')}


rows = collections.defaultdict(dict)     # build -> (domain, arm) -> {item: class}
for f in glob.glob(RP('analysis', 'e1_results_census', '*.csv')):
    m = re.match(r'^e1_(.+?)_([a-z_]+)_(base|permit|channel|enum|best[ABC])\.csv$', os.path.basename(f))
    if not m:
        continue
    model, dom, arm = m.group(1), m.group(2), m.group(3)
    if model not in BUILDS:
        continue
    d = {}
    for r in csv.DictReader(io.open(f, encoding='utf-8-sig', errors='replace')):
        try:
            gt = float(r.get('gt') or 'nan')
        except ValueError:
            continue
        if not (gt > 0):                 # ★ 只留 gt>0 ⇒ 这就是"非零对照"侧
            continue
        if '#' in str(r.get('item') or ''):
            continue
        d[r['item']] = cls_of(r.get('raw'), r.get('pred'))
    if d:
        rows[model][(dom, arm)] = d

res = {}
print('=' * 112)
print('■ 非零项目（gt>0）上的通道构成（%，普查三臂结果，raw-match 口径）')
print('=' * 112)
for model in BUILDS:
    if model not in rows:
        print('  %-30s （无该构建的普查结果）' % model)
        continue
    per = {}
    for zone, doms in (('dense', DENSE), ('aerial', AERIAL)):
        for arm in ('base', 'permit', 'channel'):
            merged = {}
            for dom in doms:
                merged.update(rows[model].get((dom, arm), {}))
            if merged:
                per['%s/%s' % (zone, arm)] = dict(n=len(merged), pct=dist(merged))
    res[model] = per
    for k in sorted(per):
        p = per[k]['pct']
        print('  %-30s %-16s n=%5d  zero %5.1f | no_people %5.1f | cannot_judge %5.1f | abstain %5.1f '
              '| nonzero %5.1f | unparsed %5.1f'
              % (model, k, per[k]['n'], p['zero'], p['no_people'], p['cannot_judge'], p['abstain'],
                 p['nonzero'], p['unparsed']))

out = dict(
    purpose='E2 的非零对照侧：gt>0 项目上的通道构成（供与 Z0 真零池并列，回答"混合真零/非零"）',
    inputs=dict(census=os.path.basename(CEN), n_files=len(glob.glob(RP('analysis', 'e1_results_census', '*.csv'))),
                builds=BUILDS),
    rule='raw-match（同 a5_judge.cls()）；仅统计 gt>0 的项目',
    by_build=res,
)
io.open(OUT, 'w', encoding='utf-8', newline='\n').write(json.dumps(out, ensure_ascii=False, indent=2))
h = hashlib.md5(io.open(OUT, 'rb').read()).hexdigest()
io.open(OUT + '.md5', 'w', encoding='utf-8', newline='\n').write(
    '%s  %s  (ea2_mixed_analyze.py)\n' % (h, os.path.basename(OUT)))
print('\n已写出 %s（md5 %s）' % (os.path.basename(OUT), h[:12]))
