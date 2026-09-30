# -*- coding: utf-8 -*-
"""v7c 全量分析：把 6 个模型在 2 个新域（visdrone/aitod）上的结果并入全表，
并把"契约效应"从**臂级比例**升级为**条目级配对转移**（base 出零 → permit 弃答/改答）。

产出：code/analysis/out_v7c_report.md（可直接贴进证据文件）

纪律：
  · 结果 CSV 里 `raw` 含内嵌换行 ⇒ 用 csv 模块读，绝不用 wc -l / 行切分；
  · `reps>1` 会把重复行以 `item#rN` 追加在同一文件 ⇒ 一律丢弃含 `#r` 的行；
  · 判定只用 (pred, raw) 两个字段：pred 为空 = 未解析（弃答/格式失败），
    raw 里出现 abstain / cannot_judge / no_people 才算**契约给出的**弃答出口。
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
import glob
import io
import json
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')
D = RP('analysis', 'e2_newh20')
OUT = RP('analysis', 'work', 'out_v7c_report.md')
DOMS = ['st_a', 'st_b', 'ucf', 'visdrone', 'aitod', 'countbench']
DENSE = ['st_a', 'st_b', 'ucf']
AERIAL = ['visdrone', 'aitod']
ZARMS = ['base', 'permit', 'bestA', 'bestB', 'bestC', 'channel']
NZARMS = ['base', 'permit', 'channel']
L = []


def say(s=''):
    L.append(s)
    print(s)


def cls(r):
    """(pred, raw) → 结果类别。"""
    raw = str(r.get('raw') or '')
    rl = raw.lower()
    p = str(r.get('pred') or '').strip()
    if 'abstain' in rl:
        return 'abstain'
    if 'cannot_judge' in rl:
        return 'cannot_judge'
    if 'no_people' in rl:
        return 'no_people'
    if p == '':
        return 'unparsed'
    try:
        v = float(p)
    except ValueError:
        return 'unparsed'
    return 'zero' if v == 0 else 'nonzero'


def load(p):
    with io.open(p, encoding='utf-8-sig') as f:
        return [r for r in csv.DictReader(f) if '#r' not in str(r.get('item') or '')]


def parse(fn):
    pre = 'nonzero' if fn.startswith('nz__') else 'zero'
    if fn.startswith('nz__'):
        fn = fn[4:]
    if not fn.startswith('e1_'):
        return None
    body = fn[3:-4]
    for ds in sorted(DOMS, key=len, reverse=True):
        i = body.find('_' + ds + '_')
        if i > 0:
            return pre, body[:i], ds, body[i + len(ds) + 2:]
    return None


TAB = {}
for p in glob.glob(RP('analysis', 'e2_newh20', '*.csv')):
    k = parse(os.path.basename(p))
    if k:
        TAB[k] = p
MODELS = sorted(set(k[1] for k in TAB))

say('# v7c 全量分析（含新域 visdrone / aitod）')
say()
say('- 结果目录：`analysis/e2_newh20`（零池 %d 个模型标签；文件 %d 个）'
    % (len(MODELS), len(glob.glob(RP('analysis', 'e2_newh20', '*.csv')))))
say('- 零池臂：%s；非零池臂：%s' % (','.join(ZARMS), ','.join(NZARMS)))
say('- 类别判定：`pred` 空 = 未解析；`raw` 含 `abstain`/`cannot_judge`/`no_people` = 契约给出的弃答出口')
say()

# 汇总每个 (模型, 域, 臂) 的类别计数
AGG = {}


def cell(pool, model, ds, arm):
    p = TAB.get((pool, model, ds, arm))
    if not p:
        return None
    rows = load(p)
    if not rows:
        return None
    c = {}
    for r in rows:
        c[cls(r)] = c.get(cls(r), 0) + 1
    c['_n'] = len(rows)
    return c


# ---------- ① 零池：base 出零率 + 弃答出口 ----------
say('## ① 零池：base 臂出零率（复现 v6 结论）')
say()
hdr = ['模型'] + DOMS
say('| ' + ' | '.join(hdr) + ' |')
say('|' + '---|' * len(hdr))
for m in MODELS:
    row = [m]
    for ds in DOMS:
        c = cell('zero', m, ds, 'base')
        row.append('—' if not c else '%d/%d (%.0f%%)' % (c.get('zero', 0), c['_n'],
                                                        100.0 * c.get('zero', 0) / c['_n']))
    say('| ' + ' | '.join(row) + ' |')
say()
say('> countbench 零池因提问协议不符已作废，仅列数不入结论。')
say()

# ---------- ② 零池：契约效应（臂级） ----------
say('## ② 零池：各臂结果构成（出零 / 弃答出口 / 改答非零 / 未解析）')
say()
for ds in DOMS:
    say('### %s' % ds)
    say()
    say('| 模型 | 臂 | n | zero | abstain | cannot_judge | no_people | 非零 | 未解析 |')
    say('|---|---|---|---|---|---|---|---|---|')
    for m in MODELS:
        for a in ZARMS:
            c = cell('zero', m, ds, a)
            if not c:
                continue
            say('| %s | %s | %d | %d | %d | %d | %d | %d | %d |'
                % (m, a, c['_n'], c.get('zero', 0), c.get('abstain', 0),
                   c.get('cannot_judge', 0), c.get('no_people', 0),
                   c.get('nonzero', 0), c.get('unparsed', 0)))
    say()

# ---------- ③ 条目级配对转移：base 出零的条目在 permit / channel 上怎么了 ----------
say('## ③ 条目级配对转移（★ 核心证据，替代臂级比例的近似说法）')
say()
say('对同一批 item：取 base 臂 pred==0 的条目，看 permit / channel 臂把它们变成什么。')
say()
say('| 域 | 模型 | base 出零条目 | permit→弃答 | permit→改答非零 | permit→仍 0 | channel→弃答 | channel→改答非零 | channel→仍 0 |')
say('|---|---|---|---|---|---|---|---|---|')
PAIR = {}
for ds in DOMS:
    for m in MODELS:
        bp = TAB.get(('zero', m, ds, 'base'))
        if not bp:
            continue
        base = {r['item']: r for r in load(bp)}
        zitems = [k for k, r in base.items() if cls(r) == 'zero']
        if not zitems:
            continue
        rec = {'n_zero': len(zitems)}
        for a in ('permit', 'channel'):
            p = TAB.get(('zero', m, ds, a))
            if not p:
                continue
            d = {r['item']: r for r in load(p)}
            got = [cls(d[k]) for k in zitems if k in d]
            rec[a] = {
                'abstain': sum(1 for g in got if g in ('abstain', 'cannot_judge', 'no_people')),
                'nonzero': sum(1 for g in got if g == 'nonzero'),
                'zero': sum(1 for g in got if g == 'zero'),
                'n': len(got)}
        PAIR[(ds, m)] = rec
        f = lambda a, k: (str(rec[a][k]) if a in rec else '—')
        say('| %s | %s | %d | %s | %s | %s | %s | %s | %s |'
            % (ds, m, len(zitems), f('permit', 'abstain'), f('permit', 'nonzero'),
               f('permit', 'zero'), f('channel', 'abstain'), f('channel', 'nonzero'),
               f('channel', 'zero')))
say()

# ---------- ④ 域依赖：稠密 vs 航拍（把弃答出口的**覆盖率**作为统计量） ----------
say('## ④ 域依赖：给出弃答出口后，原出零条目的**转化率**（弃答+改答非零）')
say()
say('| 模型 | %s（稠密，均值） | %s（航拍，均值） | 差 |' % ('/'.join(DENSE), '/'.join(AERIAL)))
say('|---|---|---|---|')


def rate(rec, a):
    if a not in rec or not rec[a]['n']:
        return None
    return (rec[a]['abstain'] + rec[a]['nonzero']) / float(rec[a]['n'])


for m in MODELS:
    d = [rate(PAIR[(ds, m)], 'permit') for ds in DENSE if (ds, m) in PAIR]
    a_ = [rate(PAIR[(ds, m)], 'permit') for ds in AERIAL if (ds, m) in PAIR]
    d = [x for x in d if x is not None]
    a_ = [x for x in a_ if x is not None]
    if not d and not a_:
        continue
    ds_ = '%.3f' % (sum(d) / len(d)) if d else '—'
    as_ = '%.3f' % (sum(a_) / len(a_)) if a_ else '—'
    diff = ('%+.3f' % (sum(a_) / len(a_) - sum(d) / len(d))) if (d and a_) else '—'
    say('| %s | %s | %s | %s |' % (m, ds_, as_, diff))
say()

# ---------- ⑤ 非零池：弃答率（饱和性） ----------
say('## ⑤ 非零池：弃答率（corpus 给出非零，契约是否仍让模型弃答）')
say()
for pool_label, ds_list in (('稠密', DENSE), ('航拍', AERIAL)):
    say('### %s（%s）' % (pool_label, ','.join(ds_list)))
    say()
    say('| 模型 | ' + ' | '.join('%s %s' % (ds, a) for ds in ds_list for a in NZARMS) + ' |')
    say('|' + '---|' * (1 + len(ds_list) * len(NZARMS)))
    for m in MODELS:
        row = [m]
        for ds in ds_list:
            for a in NZARMS:
                c = cell('nonzero', m, ds, a)
                if not c:
                    row.append('—')
                    continue
                ab = c.get('abstain', 0) + c.get('cannot_judge', 0) + c.get('no_people', 0)
                row.append('%d/%d (%.0f%%)' % (ab, c['_n'], 100.0 * ab / c['_n']))
        say('| ' + ' | '.join(row) + ' |')
    say()

# ---------- ⑥ 成本 ----------
say('## ⑥ 新域单次运行的墙钟成本（来自 `logs_h20_v7c/exp_v7c.log`）')
say()
say('| 模型 | visdrone 零池 6 臂(n=150) | aitod 零池 6 臂 | visdrone 非零池 3 臂 | aitod 非零池 3 臂 | 合计 |')
say('|---|---|---|---|---|---|')
COST = {
    'qwen25vl-72b-awq': (1451, 583, 606, 104),
    'qwen3-vl-32b-fp8': (146, 116, 62, 27),
    'qwen3-vl-32b-awq8': (None, None, 131, 52),
    'qwen3-vl-32b-gptq': (188, 148, 95, 40),
    'qwen3-vl-8b-awq': (84, 62, 40, 17),
    'internvl25-8b-awq': (117, 72, 67, 21),
}
for m, v in COST.items():
    tot = sum(x for x in v if x)
    say('| %s | %s | %s | %s | %s | %d s |'
        % (m, *['—' if x is None else '%d s' % x for x in v], tot))
say()
say('> AWQ-8bit 的零池两域在 v6 已跑完（v7c 探针按 `item#arm` 键跳过），故无耗时记录；'
    '非零池为 v7c 新跑。')
say('> 72B 的 visdrone 零池一项即 1451 s，是 8B-AWQ（84 s）的 **17×**；'
    '全部 6 个模型 8 项合计 %d s ≈ %.1f h。'
    % (sum(sum(x for x in v if x) for v in COST.values()),
       sum(sum(x for x in v if x) for v in COST.values()) / 3600.0))

with io.open(OUT, 'w', encoding='utf-8') as f:
    f.write('\n'.join(L) + '\n')
print()
print('写出 %s（%d 行）' % (OUT, len(L)))
