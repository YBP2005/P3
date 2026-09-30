# -*- coding: utf-8 -*-
"""可比性核对 + 生成 §11 所需的两张表：
① 零池：全池率 vs **公共 150 子集**率（因为一部分模型跑了全池 273，其余抽样 150）
② 非零池航拍：permit / channel 弃答率的跨模型散布（8 个条件）

结论前置：抽样是**固定种子**的，所有 n=150 的模型拿到**同一批 item**，
且与全池的交集恰为 150 ⇒ 跨模型比较可用公共子集做同口径。
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
D = RP('analysis', 'e2_newh20')
OUT = RP('analysis', 'work', 'out_v7c_subset.md')
L = []


def say(s=''):
    L.append(s)
    print(s)


def load(p):
    with io.open(p, encoding='utf-8-sig') as f:
        return [r for r in csv.DictReader(f) if '#r' not in str(r.get('item') or '')]


def cls(r):
    raw = str(r.get('raw') or '').lower()
    p = str(r.get('pred') or '').strip()
    if 'abstain' in raw:
        return 'abstain'
    if 'cannot_judge' in raw:
        return 'cannot_judge'
    if 'no_people' in raw:
        return 'no_people'
    if p == '':
        return 'unparsed'
    try:
        return 'zero' if float(p) == 0 else 'nonzero'
    except ValueError:
        return 'unparsed'


def path(model, ds, arm, pool=''):
    pre = 'nz__' if pool == 'nonzero' else ''
    return os.path.join(RP('analysis', 'e2_newh20'), '%se1_%s_%s_%s.csv' % (pre, model, ds, arm))


def rates(model, ds, arm, pool='', subset=None):
    p = path(model, ds, arm, pool)
    if not os.path.exists(p):
        return None
    rows = load(p)
    if subset is not None:
        rows = [r for r in rows if r['item'] in subset]
    if not rows:
        return None
    c = {}
    for r in rows:
        k = cls(r)
        c[k] = c.get(k, 0) + 1
    c['_n'] = len(rows)
    return c


# 公共子集：以抽样模型（72B）的 visdrone 零池 item 集合为准
SUB = {}
for ds in ('visdrone', 'aitod'):
    SUB[ds] = set(r['item'] for r in load(path('qwen25vl-72b-awq', ds, 'base')))
    say('公共子集 %s：%d 个 item（取自 72B 的抽样，固定种子）' % (ds, len(SUB[ds])))
say()

MODELS = sorted(set(f.split('_')[1] for f in os.listdir(D)
                    if f.startswith('e1_') and '_visdrone_base.csv' in f))
say('## ① 航拍零池 base 出零率的**同口径**读数（公共 150 子集）')
say()
say('| 条件 | VisDrone 全池 | VisDrone 公共150 | AI-TOD 全池 | AI-TOD 公共150 |')
say('|---|---|---|---|---|')
for m in MODELS:
    cells = []
    for ds in ('visdrone', 'aitod'):
        full = rates(m, ds, 'base')
        sub = rates(m, ds, 'base', subset=SUB[ds])
        for c in (full, sub):
            if c is None:
                cells.append('—')
            else:
                cells.append('%d/%d (%.0f%%)' % (c.get('zero', 0), c['_n'],
                                                 100.0 * c.get('zero', 0) / c['_n']))
    say('| %s | %s |' % (m, ' | '.join(cells)))
say()
say('> 同口径（公共 150）下两列可直接比较；全池列仅对同跑全池的模型之间可比。')
say()

say('## ② 航拍非零池：permit / channel 弃答率（全普查，跨模型同 item）')
say()
say('| 条件 | VisDrone permit | VisDrone channel | AI-TOD permit | AI-TOD channel |')
say('|---|---|---|---|---|')
PER = []
for m in MODELS:
    cells = []
    for ds in ('visdrone', 'aitod'):
        for arm in ('permit', 'channel'):
            c = rates(m, ds, arm, pool='nonzero')
            if c is None:
                cells.append('—')
                continue
            ab = c.get('abstain', 0) + c.get('cannot_judge', 0) + c.get('no_people', 0)
            cells.append('%d/%d (%.0f%%)' % (ab, c['_n'], 100.0 * ab / c['_n']))
            if arm == 'permit':
                PER.append(100.0 * ab / c['_n'])
    say('| %s | %s |' % (m, ' | '.join(cells)))
say()
say('> permit 弃答率在航拍非零池的散布：**%.0f%% – %.0f%%**（%d 个条件）'
    % (min(PER), max(PER), len(PER)))
say()

# 72B 的 channel 反向
say('## ③ channel 相对 permit 的增量（航拍非零池）')
say()
say('| 条件 | VisDrone permit→channel | AI-TOD permit→channel |')
say('|---|---|---|')
for m in MODELS:
    cells = []
    for ds in ('visdrone', 'aitod'):
        a = rates(m, ds, 'permit', pool='nonzero')
        b = rates(m, ds, 'channel', pool='nonzero')
        if not a or not b:
            cells.append('—')
            continue
        fa = (a.get('abstain', 0) + a.get('cannot_judge', 0) + a.get('no_people', 0)) / float(a['_n'])
        fb = (b.get('abstain', 0) + b.get('cannot_judge', 0) + b.get('no_people', 0)) / float(b['_n'])
        cells.append('%.0f%% → %.0f%% (%+.0f pp)' % (100 * fa, 100 * fb, 100 * (fb - fa)))
    say('| %s | %s |' % (m, ' | '.join(cells)))

with io.open(OUT, 'w', encoding='utf-8') as f:
    f.write('\n'.join(L) + '\n')
print()
print('写出 %s' % OUT)
