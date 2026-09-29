# -*- coding: utf-8 -*-
"""核验 §11 里引用的每一个数字（凡引数字必须可核验）。

方式：从结果 CSV **重算**，与 §11 中写死的期望值逐条断言。
任一不符即退出码非 0 —— 不允许"看起来对"就过。
"""
import csv
import io
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')
D = r'<WORKDIR>\PaperB\analysis\e2_newh20'
FAIL = []


def load(rel):
    p = os.path.join(D, rel)
    if not os.path.exists(p):
        return None
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


def tally(model, ds, arm, pool=''):
    pre = 'nz__' if pool == 'nonzero' else ''
    rows = load('%se1_%s_%s_%s.csv' % (pre, model, ds, arm))
    if rows is None:
        return None
    c = {}
    for r in rows:
        k = cls(r)
        c[k] = c.get(k, 0) + 1
    c['_n'] = len(rows)
    return c


def ck(label, got, want):
    ok = (got == want)
    print('  %-58s %-22s %s' % (label, str(got), '✓' if ok else '✗ 期望 %s' % (want,)))
    if not ok:
        FAIL.append('%s: got %s want %s' % (label, got, want))


# ---- 11.1 公共 150 子集：先取 72B 的 item 集合，再对全池模型取子集 ----
SUB = {}
for ds in ('visdrone', 'aitod'):
    SUB[ds] = set(r['item'] for r in load('e1_qwen25vl-72b-awq_%s_base.csv' % ds))
ck('公共子集 visdrone 大小', len(SUB['visdrone']), 150)
ck('公共子集 aitod 大小', len(SUB['aitod']), 150)


def zero_rate_sub(model, ds):
    rows = [r for r in load('e1_%s_%s_base.csv' % (model, ds)) if r['item'] in SUB[ds]]
    z = sum(1 for r in rows if cls(r) == 'zero')
    return z, len(rows)


print()
print('11.1 航拍零池出零率（公共 150）')
for m, ds, want in (
        ('qwen3-vl-32b-awq', 'visdrone', (149, 150)),
        ('qwen3-vl-32b-awq', 'aitod', (146, 150)),
        ('qwen3-vl-32b-gptq', 'visdrone', (145, 150)),
        ('qwen3-vl-32b-gptq', 'aitod', (133, 150)),
        ('qwen25vl-72b-awq', 'visdrone', (121, 150)),
        ('qwen25vl-72b-awq', 'aitod', (93, 150)),
        ('qwen3-vl-2b', 'visdrone', (123, 150)),
        ('qwen3-vl-2b', 'aitod', (100, 150)),
        ('qwen3-vl-8b-awq', 'visdrone', (136, 150)),
        ('qwen3-vl-8b-awq', 'aitod', (119, 150)),
        ('internvl25-8b-awq', 'visdrone', (128, 150)),
        ('internvl25-8b-awq', 'aitod', (102, 150)),
        ('internvl35-38b-fp8', 'visdrone', (130, 150)),
        ('internvl35-38b-fp8', 'aitod', (104, 150)),
        ('qwen3-vl-30b-a3b-fp8', 'visdrone', (23, 150)),
        ('qwen3-vl-30b-a3b-fp8', 'aitod', (10, 150)),
):
    ck('%s / %s' % (m, ds), zero_rate_sub(m, ds), want)

print()
print('11.2 MoE 未解析率（全池）')
for m, ds, want in (('qwen3-vl-30b-a3b-fp8', 'aitod', (33, 154)),
                    ('qwen3-vl-30b-a3b-fp8', 'visdrone', (47, 273))):
    c = tally(m, ds, 'base')
    ck('%s / %s 未解析' % (m, ds), (c.get('unparsed', 0), c['_n']), want)

print()
print('11.2 密集域 st_a 出零率（全池 103）')
for m, want in (('qwen3-vl-32b-awq', (102, 103)), ('qwen3-vl-32b-fp8', (82, 103)),
                ('qwen3-vl-32b-awq8', (67, 103)), ('qwen3-vl-32b-bf16', (64, 103)),
                ('qwen3-vl-32b-gptq', (9, 103)), ('qwen25vl-72b-awq', (0, 103)),
                ('qwen3-vl-2b', (0, 103)), ('qwen3-vl-8b-awq', (0, 103)),
                ('qwen3-vl-30b-a3b-fp8', (0, 103)), ('internvl25-8b-awq', (0, 103)),
                ('qwen3-vl-4b', (24, 103))):
    c = tally(m, 'st_a', 'base')
    ck('%s / st_a' % m, (c.get('zero', 0), c['_n']), want)

print()
print('11.3 条目级配对（base 出零 → permit/channel 仍答 0）')


def paired(model, ds, arm):
    base = load('e1_%s_%s_base.csv' % (model, ds))
    oth = load('e1_%s_%s_%s.csv' % (model, ds, arm))
    if base is None or oth is None:
        return None
    z = [r['item'] for r in base if cls(r) == 'zero']
    d = {r['item']: r for r in oth}
    got = [cls(d[k]) for k in z if k in d]
    return (len(z), sum(1 for g in got if g == 'zero'),
            sum(1 for g in got if g in ('abstain', 'cannot_judge', 'no_people')),
            sum(1 for g in got if g == 'nonzero'))


for m, ds, want in (('qwen3-vl-32b-awq', 'st_a', (102, 0, 102, 0)),
                    ('qwen3-vl-32b-fp8', 'st_a', (82, 0, 82, 0)),
                    ('qwen3-vl-32b-awq8', 'ucf', (125, 0, 125, 0)),
                    ('qwen25vl-72b-awq', 'visdrone', (121, 0, 121, 0)),
                    ('qwen3-vl-32b-gptq', 'visdrone', (145, 0, 145, 0)),
                    ('qwen3-vl-8b-awq', 'visdrone', (136, 0, 136, 0)),
                    ('internvl25-8b-awq', 'visdrone', (128, 0, 128, 0)),
                    ('qwen3-vl-32b-awq', 'aitod', (149, 1, 148, 0)),
                    ('qwen3-vl-2b', 'visdrone', (194, 108, 34, 52)),
                    ('qwen3-vl-2b', 'aitod', (101, 42, 48, 11))):
    ck('%s / %s permit' % (m, ds), paired(m, ds, 'permit'), want)

for m, ds, want in (('qwen3-vl-2b', 'visdrone', (194, 0, 194, 0)),
                    ('qwen3-vl-2b', 'aitod', (101, 0, 101, 0)),
                    ('qwen3-vl-32b-awq', 'aitod', (149, 0, 149, 0))):
    ck('%s / %s channel' % (m, ds), paired(m, ds, 'channel'), want)

print()
print('11.3 ★全 52 个（模型 × 域）格的汇总')
DOMS = ['st_a', 'st_b', 'ucf', 'visdrone', 'aitod']
MODELS = sorted(set(f.split('_')[1] for f in os.listdir(D)
                    if f.startswith('e1_') and '_st_a_base.csv' in f))
p_ok = p_tot = c_ok = c_tot = 0
p_exc = []
c_exc = []
for m in MODELS:
    for ds in DOMS:
        a = paired(m, ds, 'permit')
        if a:
            p_tot += 1
            if a[1] == 0:
                p_ok += 1
            else:
                p_exc.append('%s/%s(%d)' % (m, ds, a[1]))
        b = paired(m, ds, 'channel')
        if b:
            c_tot += 1
            if b[1] == 0:
                c_ok += 1
            else:
                c_exc.append('%s/%s(%d)' % (m, ds, b[1]))
ck('permit 把"仍答 0"清零的格子数 / 总格子数', (p_ok, p_tot), (46, 52))
print('      例外 %d 格：%s' % (len(p_exc), p_exc or '无'))
ck('例外中"只剩 1 条"的格数', sum(1 for x in p_exc if x.endswith('(1)')), 4)
ck('例外中 2B 航拍两格的残留', sorted(x for x in p_exc if x.startswith('qwen3-vl-2b')),
   ['qwen3-vl-2b/aitod(42)', 'qwen3-vl-2b/visdrone(108)'])
ck('channel 把"仍答 0"清零的格子数 / 总格子数', (c_ok, c_tot), (52, 52))
print('      例外：%s' % (c_exc or '无'))

print()
print('11.4 bestA vs permit（VisDrone 零池出零数，全池）')
for m, want in (('qwen25vl-72b-awq', {'base': 121, 'bestA': 121, 'permit': 0}),
                ('qwen3-vl-4b', {'base': 232, 'bestA': 235, 'permit': 0}),
                ('qwen3-vl-32b-awq', {'base': 268, 'bestA': 166, 'permit': 0})):
    for arm, w in want.items():
        c = tally(m, 'visdrone', arm)
        ck('%s / visdrone / %s 零' % (m, arm), c.get('zero', 0), w)

print()
print('11.5 channel 相对 permit（航拍非零池弃答率）')
for m, ds, want in (('qwen25vl-72b-awq', 'visdrone', (106, 127, 58, 127)),
                    ('qwen25vl-72b-awq', 'aitod', (45, 72, 17, 72)),
                    ('qwen3-vl-8b-awq', 'visdrone', (118, 127, 124, 127)),
                    ('qwen3-vl-8b-awq', 'aitod', (65, 72, 71, 72)),
                    ('qwen3-vl-32b-gptq', 'aitod', (26, 72, 46, 72)),
                    ('internvl25-8b-awq', 'visdrone', (102, 127, 124, 127))):
    a = tally(m, ds, 'permit', pool='nonzero')
    b = tally(m, ds, 'channel', pool='nonzero')
    fa = a.get('abstain', 0) + a.get('cannot_judge', 0) + a.get('no_people', 0)
    fb = b.get('abstain', 0) + b.get('cannot_judge', 0) + b.get('no_people', 0)
    ck('%s / %s permit+channel' % (m, ds), (fa, a['_n'], fb, b['_n']), want)

print()
print('11.5(b) 航拍非零池 permit 弃答率的散布')
vals = []
for m in MODELS:
    for ds in ('visdrone', 'aitod'):
        a = tally(m, ds, 'permit', pool='nonzero')
        if a:
            vals.append(round(100.0 * (a.get('abstain', 0) + a.get('cannot_judge', 0)
                                       + a.get('no_people', 0)) / a['_n']))
ck('散布区间 (min, max, 格数)', (min(vals), max(vals), len(vals)), (36, 93, 16))

print()
print('M.18.2 三新臂（enum / locate / enumAbstain）')


def arm_tally(model, ds, arm):
    c = tally(model, ds, arm)
    if c is None:
        return None
    ab = c.get('abstain', 0) + c.get('cannot_judge', 0) + c.get('no_people', 0)
    return (c.get('zero', 0), ab, c.get('unparsed', 0), c['_n'])


for m, ds, want in (
        ('qwen3-vl-32b-awq', 'st_a', {'base': (102, 0), 'enum': (92, 0), 'locate': (99, 0),
                                      'enumAbstain': (0, 103), 'permit': (0, 103)}),
        ('qwen3-vl-32b-awq', 'ucf', {'base': (166, 0), 'enum': (159, 0), 'locate': (155, 0),
                                     'enumAbstain': (0, 180), 'permit': (0, 180)}),
        ('qwen3-vl-32b-awq', 'visdrone', {'base': (268, 0), 'enum': (258, 0), 'locate': (263, 0),
                                          'enumAbstain': (4, 268), 'permit': (0, 273)}),
        ('qwen3-vl-32b-awq', 'aitod', {'base': (149, 0), 'enum': (136, 0), 'locate': (136, 0),
                                       'enumAbstain': (15, 133), 'permit': (1, 152)}),
        ('qwen3-vl-32b-bf16', 'st_a', {'base': (64, 0), 'enum': (103, 0), 'locate': (86, 0),
                                       'enumAbstain': (0, 103), 'permit': (0, 103)}),
        ('qwen3-vl-32b-bf16', 'ucf', {'base': (120, 0), 'enum': (180, 0), 'locate': (119, 0),
                                      'enumAbstain': (0, 180), 'permit': (0, 180)}),
        ('qwen3-vl-32b-bf16', 'visdrone', {'base': (254, 0), 'enum': (254, 0), 'locate': (262, 0),
                                           'enumAbstain': (4, 266), 'permit': (0, 273)}),
        ('qwen3-vl-32b-bf16', 'aitod', {'base': (143, 0), 'enum': (137, 0), 'locate': (143, 0),
                                        'enumAbstain': (19, 129), 'permit': (1, 152)})):
    for arm, (wz, wab) in want.items():
        c = tally(m, ds, arm)
        ck('%s / %s / %s (零,弃答)' % (m[-8:], ds, arm),
           (c.get('zero', 0), c.get('abstain', 0) + c.get('cannot_judge', 0) + c.get('no_people', 0)),
           (wz, wab))

print()
print('M.18.5 饱和边界')
DENSE = []
for m in MODELS:
    for ds in ('st_a', 'st_b', 'ucf'):
        a = tally(m, ds, 'permit', pool='nonzero')
        if a:
            ab = a.get('abstain', 0) + a.get('cannot_judge', 0) + a.get('no_people', 0)
            DENSE.append((100.0 * ab / a['_n'], '%s/%s' % (m, ds)))
ex = sorted(x[1] for x in DENSE if x[0] < 88.0)
ck('稠密域低于 88% 的格（应仅 2B 两格）', ex, ['qwen3-vl-2b/st_a', 'qwen3-vl-2b/ucf'])
n_ok = sum(1 for x in DENSE if x[0] >= 88.0)
ck('稠密域落在 88.6–100% 的格数 / 总格数', (n_ok, len(DENSE)), (28, 30))
ck('稠密域最低值（除 2B）≈88.6', round(min(x[0] for x in DENSE if x[0] >= 88.0), 1), 88.6)
ck('稠密域最高值', round(max(x[0] for x in DENSE), 1), 100.0)
for m, ds, want in (('qwen3-vl-2b', 'st_a', 24), ('qwen3-vl-2b', 'ucf', 3)):
    a = tally(m, ds, 'permit', pool='nonzero')
    ab = a.get('abstain', 0) + a.get('cannot_judge', 0) + a.get('no_people', 0)
    ck('2B / %s permit 弃答%%' % ds, round(100.0 * ab / a['_n']), want)

print()
print('M.18.7 成本（从 exp_v7c.log 直接解析）')
import re as _re
lg = os.path.join(D, 'logs_h20_v7c', 'exp_v7c.log')
txt = io.open(lg, encoding='utf-8', errors='replace').read()
EXP = {('qwen25vl-72b-awq', 'visdrone', 'zero'): 1451, ('qwen25vl-72b-awq', 'aitod', 'zero'): 583,
       ('qwen25vl-72b-awq', 'visdrone', 'nonzero'): 606, ('qwen25vl-72b-awq', 'aitod', 'nonzero'): 104,
       ('qwen3-vl-32b-fp8', 'visdrone', 'zero'): 146, ('qwen3-vl-32b-fp8', 'aitod', 'zero'): 116,
       ('qwen3-vl-32b-gptq', 'visdrone', 'zero'): 188, ('qwen3-vl-32b-gptq', 'aitod', 'zero'): 148,
       ('qwen3-vl-8b-awq', 'visdrone', 'zero'): 84, ('qwen3-vl-8b-awq', 'aitod', 'zero'): 62,
       ('internvl25-8b-awq', 'visdrone', 'zero'): 117, ('internvl25-8b-awq', 'aitod', 'zero'): 72}
cur = None
got = {}
for ln in txt.splitlines():
    mm = _re.search(r'跑 (\S+) / (\S+) / \S+ \((zero|nonzero), n=\d+\)', ln)
    if mm:
        cur = (mm.group(1), mm.group(2), mm.group(3))
        continue
    mm = _re.search(r'rc=0 .*用时 (\d+)s', ln)
    if mm and cur:
        got[cur] = int(mm.group(1))
        cur = None
for k, v in sorted(EXP.items()):
    ck('耗时 %s/%s/%s' % k, got.get(k), v)

print()
print('§7.7 普查侧旁证：禁零臂的中位 pred/gt（零池）')
import statistics as _st


def med_ratio(model, ds, arm):
    rows = load('e1_%s_%s_%s.csv' % (model, ds, arm))
    if rows is None:
        return None
    vals = []
    for r in rows:
        try:
            p, g = float(str(r.get('pred') or '').strip()), float(str(r.get('gt') or '').strip())
        except ValueError:
            continue
        if g > 0:
            vals.append(p / g)
    return round(_st.median(vals), 3) if vals else None


for m, ds, want in (('qwen3-vl-32b-awq', 'st_a', {'base': 0.0, 'bestA': 6.281, 'bestB': 5.155, 'bestC': 4.854}),
                    ('qwen3-vl-32b-awq', 'ucf', {'bestA': 5.168, 'bestB': 4.487, 'bestC': 4.045}),
                    ('qwen3-vl-32b-awq', 'visdrone', {'bestA': 0.0, 'bestB': 0.25, 'bestC': 0.469}),
                    ('qwen3-vl-32b-awq', 'aitod', {'bestA': 0.062, 'bestB': 0.5, 'bestC': 0.833}),
                    ('qwen3-vl-32b-bf16', 'st_a', {'bestA': 5.365, 'bestB': 4.5, 'bestC': 4.027}),
                    ('qwen3-vl-32b-bf16', 'ucf', {'bestA': 4.921, 'bestB': 3.949, 'bestC': 3.458}),
                    ('qwen3-vl-32b-bf16', 'visdrone', {'bestB': 0.333, 'bestC': 0.5}),
                    ('qwen3-vl-32b-bf16', 'aitod', {'bestA': 0.171, 'bestB': 0.511, 'bestC': 0.662})):
    for arm, w in want.items():
        ck('中位比 %s / %s / %s' % (m[-8:], ds, arm), med_ratio(m, ds, arm), w)

print()
if FAIL:
    print('VERIFY_S11_FAIL: %d 条不符' % len(FAIL))
    for f in FAIL:
        print('   ' + f)
    sys.exit(1)
print('VERIFY_S11_OK：§11 引用的数字全部与结果 CSV 一致。')
