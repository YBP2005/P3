# -*- coding: utf-8 -*-
"""A5 附加统计：把"两类答 0"落在**可判定的量**上 —— 跨构建散布 vs 跨家族普遍性。

背景（E2 §11.2）："答 0"分两类 ——
  · 密集域那一类**绑定具体量化构建**（同一 32B 权重：AWQ-4bit 99% … GPTQ-W4 9%）；
  · 航拍域那一类**近乎普遍**（12 个条件里 11 个 62–99%）。
冻结判据 P2 用的是"密集率与航拍率之差 ≥30 pp"（配置级、单一构建可见）；
本脚本给出**更贴近主张**的量：
  S_dense = 同一家族内不同构建的密集域出零率极差（pp）
  S_aerial= 同一家族内不同构建的航拍域出零率极差（pp）
  U_aerial= 跨家族航拍出零率的分布（家族级，取每家族一配置）
判据（同样先写死，避免事后挑口径）：
  若 S_dense 显著大于 S_aerial（本脚本报差值与其无重叠的区间），
  且跨家族航拍出零率中位数 ≥50%，则"构建特异 / 域特异"两类可分。

用法：
    python a5_two_kinds.py <zero_dir> [<zero_dir2> ...]     # 可给多个目录（并集）
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
DOMS_DENSE = ['st_a', 'ucf']
DOMS_AERIAL = ['visdrone', 'aitod']
DS_ALL = ['st_a', 'st_b', 'ucf', 'visdrone', 'aitod', 'countbench']
ABSTAIN = ('abstain', 'cannot_judge', 'no_people')

# 家族归类：把"模型配置名"归到家族（用于跨构建散布）
FAMILY_RULES = [
    ('Qwen3-VL-32B', ['qwen3-vl-32b-awq', 'qwen3-vl-32b-awq8', 'qwen3-vl-32b-fp8',
                      'qwen3-vl-32b-bf16', 'qwen3-vl-32b-gptq']),
    ('Qwen3-VL-8B', ['qwen3-vl-8b-awq', 'qwen3-vl-8b-bf16']),
    ('Qwen3-VL-小尺寸', ['qwen3-vl-2b', 'qwen3-vl-4b', 'qwen3-vl-30b-a3b-fp8']),
    ('Qwen2.5-VL', ['qwen25vl-72b-awq', 'qwen25vl-7b-awq']),
    ('InternVL2.5', ['internvl25-8b-awq']),
    ('InternVL3.5', ['internvl35-38b-fp8', 'InternVL3_5-8B']),
    ('Gemma-3', ['gemma3-12b']),
    ('Phi-3.5-Vision', ['Phi-3.5-vision-instruct']),
    ('LLaVA-OneVision', ['llava-onevision-qwen2-7b-ov']),
]


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


def parse(fn):
    if not fn.startswith('e1_'):
        return None
    body = fn[3:-4]
    if body.startswith('nz_'):
        return None
    for ds in DS_ALL:
        i = body.find('_' + ds + '_')
        if i > 0:
            return body[:i], ds, body[i + len(ds) + 2:]
    return None


def fam_of(cfg):
    for fam, keys in FAMILY_RULES:
        for k in keys:
            if cfg == k or cfg.startswith(k):
                return fam
    return None


def main():
    dirs = sys.argv[1:] or [RP('analysis', 'e2_newh20')]
    tab = {}
    for d in dirs:
        for p in glob.glob(os.path.join(d, '*.csv')):
            k = parse(os.path.basename(p))
            if k and k[2] == 'base':
                tab.setdefault(k[0], {})[k[1]] = p
    cfg2fam = {}
    for cfg in sorted(tab):
        f = fam_of(cfg)
        if f:
            cfg2fam.setdefault(f, []).append(cfg)
    # 每配置：密集/航拍出零率（在跨配置交集子集上，保证可比）
    inter = {}
    for ds in DOMS_DENSE + DOMS_AERIAL:
        ss = [set(r['item'] for r in csv.DictReader(io.open(tab[c][ds], encoding='utf-8-sig')))
              for c in tab if ds in tab[c]]
        if ss:
            inter[ds] = set.intersection(*ss)
    rate = {}
    for cfg in tab:
        row = {}
        for grp, dss in (('dense', DOMS_DENSE), ('aerial', DOMS_AERIAL)):
            k = n = 0
            for ds in dss:
                if ds not in tab[cfg]:
                    continue
                rows = [r for r in csv.DictReader(io.open(tab[cfg][ds], encoding='utf-8-sig'))
                        if r['item'] in inter.get(ds, set())]
                n += len(rows)
                k += sum(1 for r in rows if cls(r) == 'zero')
            row[grp] = (k / float(n)) if n else None
        rate[cfg] = row
    print('== 配置级（密集域 / 航拍域 base 出零率，配对子集）==')
    print('%-30s %-14s %9s %9s' % ('配置', '家族', '密集', '航拍'))
    for cfg in sorted(rate):
        r = rate[cfg]
        f = lambda v: '—' if v is None else '%.3f' % v
        print('%-30s %-14s %9s %9s' % (cfg, fam_of(cfg) or '?',
                                       f(r['dense']), f(r['aerial'])))
    print()
    print('== 家族级：跨构建散布 ==')
    print('%-16s %6s %14s %14s %10s' % ('家族', '构建数', '密集极差(pp)', '航拍极差(pp)', 'S密-S航'))
    out = {}
    for fam, cfgs in sorted(cfg2fam.items()):
        ds_ = [rate[c]['dense'] for c in cfgs if rate[c]['dense'] is not None]
        as_ = [rate[c]['aerial'] for c in cfgs if rate[c]['aerial'] is not None]
        if len(cfgs) >= 2 and ds_ and as_:
            sd = (max(ds_) - min(ds_)) * 100
            sa = (max(as_) - min(as_)) * 100
            print('%-16s %6d %14.1f %14.1f %+10.1f' % (fam, len(cfgs), sd, sa, sd - sa))
            out[fam] = {'n_builds': len(cfgs), 'configs': cfgs,
                        'dense_spread_pp': sd, 'aerial_spread_pp': sa,
                        'dense_rates': ds_, 'aerial_rates': as_}
    # 跨家族普遍性：每家族取"官方/未量化优先"的一个配置
    PREF = {'Qwen3-VL-32B': 'qwen3-vl-32b-bf16', 'Qwen3-VL-8B': 'qwen3-vl-8b-bf16',
            'Qwen2.5-VL': 'qwen25vl-72b-awq', 'InternVL2.5': 'internvl25-8b-awq',
            'InternVL3.5': 'InternVL3_5-8B', 'Gemma-3': 'gemma3-12b',
            'Phi-3.5-Vision': 'Phi-3.5-vision-instruct',
            'LLaVA-OneVision': 'llava-onevision-qwen2-7b-ov'}
    print()
    print('== 跨家族普遍性（每家族一个配置；官方/未量化优先）==')
    aer = []
    for fam in sorted(cfg2fam):
        c = PREF.get(fam)
        if c is None or c not in rate:
            c = sorted(cfg2fam[fam])[0]
        v = rate[c]['aerial']
        dv = rate[c]['dense']
        print('%-16s %-30s 密集=%-7s 航拍=%s'
              % (fam, c, '—' if dv is None else '%.3f' % dv, '—' if v is None else '%.3f' % v))
        if v is not None:
            aer.append(v)
    if aer:
        aer.sort()
        mid = aer[len(aer) // 2] if len(aer) % 2 else (aer[len(aer) // 2 - 1] + aer[len(aer) // 2]) / 2
        print('航拍出零率：n=%d 最小=%.3f 中位=%.3f 最大=%.3f；≥0.50 的家族 %d/%d'
              % (len(aer), aer[0], mid, aer[-1], sum(1 for x in aer if x >= .5), len(aer)))
        out['_aerial_universality'] = {'n': len(aer), 'min': aer[0], 'median': mid,
                                       'max': aer[-1],
                                       'ge_50pct': sum(1 for x in aer if x >= .5)}
    with io.open(RP('analysis', 'work', 'a5_two_kinds.json'), 'w', encoding='utf-8') as f:
        f.write(json.dumps(out, ensure_ascii=False, indent=1))
    print('JSON -> a5_two_kinds.json')
    return 0


if __name__ == '__main__':
    sys.exit(main())
