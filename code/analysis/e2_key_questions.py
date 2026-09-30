# -*- coding: utf-8 -*-
"""聚焦输出：① 新域上 permit/channel 是否仍饱和；② 新臂（enum/enumAbstain/locate）结果。"""


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
import statistics as st
import sys

sys.stdout.reconfigure(encoding='utf-8')

D = RP('analysis', 'e2_newh20')
DOMAINS = ['st_a', 'st_b', 'ucf', 'visdrone', 'aitod', 'countbench']
NZ = 'nz__'


def load(p):
    with open(p, encoding='utf-8-sig') as f:
        return [r for r in csv.DictReader(f) if '#r' not in str(r.get('item', ''))]


def num(v):
    try:
        return float(str(v).strip())
    except Exception:
        return None


def abstain(r):
    b = ' '.join(str(v or '') for k, v in r.items() if k not in ('pred', 'gt')).lower()
    return ('abstain' in b) or ('cannot_judge' in b) or ('no_people' in b)


def find(model, ds, arm, pool='zero'):
    pre = NZ if pool == 'nonzero' else ''
    p = os.path.join(RP('analysis', 'e2_newh20'), '%se1_%s_%s_%s.csv' % (pre, model, ds, arm))
    return p if os.path.exists(p) else None


def stat(model, ds, arm, pool='zero'):
    p = find(model, ds, arm, pool)
    if not p:
        return None
    rows = load(p)
    if not rows:
        return None
    return dict(n=len(rows),
                zero=sum(1 for r in rows if num(r.get('pred')) == 0),
                ab=sum(1 for r in rows if abstain(r)))


print('=' * 104)
print('① 契约效应 × 域（零池）：base 出零 → permit / channel 的出零与弃答')
print('=' * 104)
MODELS = sorted(set(os.path.basename(p)[3:].split('_')[0] for p in glob.glob(RP('analysis', 'e2_newh20', '*.csv'))))
for m in ['qwen3-vl-32b-awq', 'qwen3-vl-32b-bf16', 'qwen3-vl-32b-fp8',
          'qwen3-vl-32b-gptq', 'qwen25vl-72b-awq', 'internvl25-8b-awq']:
    for ds in DOMAINS:
        cells = []
        for a in ('base', 'permit', 'channel'):
            s = stat(m, ds, a)
            cells.append('%d零/%d弃(n=%d)' % (s['zero'], s['ab'], s['n']) if s else '-')
        if any(c != '-' for c in cells):
            print('  %-20s %-11s base=%-18s permit=%-18s channel=%-18s' % (m, ds, *cells))

print()
print('=' * 104)
print('② ★ 饱和检验：permit 臂在【非零池】上的弃答率（=弃答是否选择性）')
print('   若各域都接近 100% ⇒ 弃答是饱和的通道切换（与可确证性无关）')
print('=' * 104)
print('  %-20s %-11s %-22s %-22s' % ('模型', '域', 'permit 非零池', 'channel 非零池'))
for m in ['qwen3-vl-32b-awq', 'qwen3-vl-32b-bf16', 'qwen25vl-72b-awq', 'internvl25-8b-awq']:
    for ds in DOMAINS:
        cells = []
        for a in ('permit', 'channel'):
            s = stat(m, ds, a, 'nonzero')
            cells.append('%d弃/%d(%.0f%%)' % (s['ab'], s['n'], 100.0 * s['ab'] / s['n']) if s else '-')
        if any(c != '-' for c in cells):
            print('  %-20s %-11s %-22s %-22s' % (m, ds, *cells))

print()
print('=' * 104)
print('③ ★ §3.6(d) 因素分解：枚举要求（enum/locate）vs 弃答可选（enumAbstain）')
print('=' * 104)
print('  %-20s %-11s %-16s %-16s %-16s' % ('模型', '域', 'enum(无弃答)', 'enumAbstain', 'locate(无弃答)'))
for m in ['qwen3-vl-32b-awq', 'qwen3-vl-32b-bf16']:
    for ds in DOMAINS:
        cells = []
        for a in ('enum', 'enumAbstain', 'locate'):
            s = stat(m, ds, a)
            cells.append('%d零/%d弃(n=%d)' % (s['zero'], s['ab'], s['n']) if s else '-')
        if any(c != '-' for c in cells):
            print('  %-20s %-11s %-16s %-16s %-16s' % (m, ds, *cells))
