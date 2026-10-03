# -*- coding: utf-8 -*-
"""★★ [external-review] A5-实验 1 / §8.2 的正面回应：**"答 0 率"的方差里，构建占多少、域占多少？**

[external-review]的原话：
  "跨构建 × 跨语系的弃权率普查…判据是'答 0 份额'的构建内/构建间方差分解；
   预期构建效应在密集域占主导、域效应在航拍占主导；若构建间方差 ≥ 域间方差，标题须加
   configuration-specific 限定。"

设计（**平衡设计**，只用已发布的 E2 普查结果）：
  · 因子 A（构建）：Qwen3-VL-32B 的 5 个构建 — AWQ-4bit / AWQ-8bit / BF16 / FP8 / GPTQ-W4
    这是**同一份权重**的 5 种部署，因此构建效应不含"换了模型"的混淆。
  · 因子 B（域）：st_a / ucf / visdrone / aitod（5×4 = 20 格平衡）。
  · 因变量：零池 base 臂的**答 0 率（%）**——即语料答 0 的 item 中该构建仍答 0 的比例。
  · item 集合：同域内**跨构建完全一致**（抽样为固定种子；st_a/ucf 为全池，航拍取公共 150 子集），
    故格子间可直接比较。

输出：两因素方差分解（平方和占比）+ 分域/分构建的极差，并给出[external-review]要求的判定：
     "构建间方差是否 ≥ 域间方差"。
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
import glob
import json
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')
E2 = RP('analysis', 'e2_newh20')
OUT = RP('analysis', 'work', 'variance_decomp_result.json')

BUILDS = [('qwen3-vl-32b-awq', 'AWQ-4bit'), ('qwen3-vl-32b-awq8', 'AWQ-8bit'),
          ('qwen3-vl-32b-bf16', 'BF16'), ('qwen3-vl-32b-fp8', 'FP8'),
          ('qwen3-vl-32b-gptq', 'GPTQ-W4')]
DOMS = ['st_a', 'ucf', 'visdrone', 'aitod']
SUB = {}          # 域 → 允许的 item 集合（跨构建一致）


def items_of(model, ds, arm='base'):
    p = os.path.join(RP('analysis', 'e2_newh20'), 'e1_%s_%s_%s.csv' % (model, ds, arm))
    if not os.path.exists(p):
        return None
    with io.open(p, encoding='utf-8-sig') as f:
        return [r for r in csv.DictReader(f) if '#r' not in str(r.get('item') or '')]


# 1) 公共 item 集合：以「跑得最少的那个构建」的交集为准，保证 5×4 平衡
KEYS = {}
for ds in DOMS:
    sets = []
    for m, _ in BUILDS:
        rows = items_of(m, ds)
        if rows is not None:
            sets.append(set(r['item'] for r in rows))
    KEYS[ds] = set.intersection(*sets) if sets else set()

# 2) 答 0 率（在该公共子集上）
rate = {}
for m, label in BUILDS:
    for ds in DOMS:
        rows = items_of(m, ds)
        if rows is None:
            continue
        sub = [r for r in rows if r['item'] in KEYS[ds]]
        if not sub:
            continue
        z = sum(1 for r in sub if str(r.get('pred') or '').strip() in ('0', '0.0'))
        rate[(label, ds)] = 100.0 * z / len(sub)
        rate[('_n', ds)] = len(sub)

print('公共 item 子集大小：%s' % {ds: len(KEYS[ds]) for ds in DOMS})
print()
print('答 0 率（%%）—— 行=构建，列=域')
print('%-10s' % '' + ''.join('%12s' % ds for ds in DOMS))
for _, label in BUILDS:
    print('%-10s' % label + ''.join('%12.1f' % rate[(label, ds)] for ds in DOMS))

vals = [rate[(l, ds)] for _, l in BUILDS for ds in DOMS]
gm = sum(vals) / len(vals)
a, b = len(BUILDS), len(DOMS)

# 3) 两因素方差分解（平衡设计，无交互项的经典分解 + 交互残差）
grand = gm
SS_build = b * sum((sum(rate[(l, ds)] for ds in DOMS) / b - grand) ** 2 for _, l in BUILDS)
SS_domain = a * sum((sum(rate[(l, ds)] for _, l in BUILDS) / a - grand) ** 2 for ds in DOMS)
SS_total = sum((v - grand) ** 2 for v in vals)
SS_resid = SS_total - SS_build - SS_domain
print()
print('两因素方差分解（因变量 = 答 0 率 %%）：')
print('  构建（5 个部署，**同一份权重**）  SS=%9.1f  占 %5.1f%%' % (SS_build, 100 * SS_build / SS_total))
print('  域  （4 个域）                SS=%9.1f  占 %5.1f%%' % (SS_domain, 100 * SS_domain / SS_total))
print('  交互/残差                     SS=%9.1f  占 %5.1f%%' % (SS_resid, 100 * SS_resid / SS_total))

# 4) 分域看构建效应、分构建看域效应
print()
print('分域：跨构建极差（构建效应）      分构建：跨域极差（域效应）')
rows_out = []
for ds in DOMS:
    v = [rate[(l, ds)] for _, l in BUILDS]
    rows_out.append(('domain', ds, max(v) - min(v), max(v), min(v)))
    print('  %-9s 极差 %6.1f pp（%.1f → %.1f）' % (ds, max(v) - min(v), min(v), max(v)))
for _, label in BUILDS:
    v = [rate[(label, ds)] for ds in DOMS]
    print('  %-9s 极差 %6.1f pp（%.1f → %.1f）' % (label, max(v) - min(v), min(v), max(v)))

# 5) [external-review]要求的判定
dense = [rate[(l, ds)] for _, l in BUILDS for ds in ('st_a', 'ucf')]
aerial = [rate[(l, ds)] for _, l in BUILDS for ds in ('visdrone', 'aitod')]
sp_build_dense = max(dense) - min(dense)
sp_build_aerial = max(aerial) - min(aerial)
print()
print('判定（评审判据：构建间方差 ≥ 域间方差 ⇒ 标题须加 configuration-specific 限定）')
print('  构建占比 %.1f%% vs 域占比 %.1f%% ⇒ %s'
      % (100 * SS_build / SS_total, 100 * SS_domain / SS_total,
         '构建占主导（须加限定）' if SS_build >= SS_domain else '域占主导（限定可放宽）'))
print('  同一份 32B 权重、仅换部署：密集域内极差 %.1f pp，航拍域内极差 %.1f pp'
      % (sp_build_dense, sp_build_aerial))

res = dict(common_items={ds: len(KEYS[ds]) for ds in DOMS},
           rate={'%s|%s' % (l, ds): rate[(l, ds)] for _, l in BUILDS for ds in DOMS},
           SS=dict(build=SS_build, domain=SS_domain, resid=SS_resid, total=SS_total),
           share=dict(build=SS_build / SS_total, domain=SS_domain / SS_total,
                      resid=SS_resid / SS_total),
           spread_within_domain={ds: max(rate[(l, ds)] for _, l in BUILDS)
                                 - min(rate[(l, ds)] for _, l in BUILDS) for ds in DOMS},
           spread_within_build={l: max(rate[(l, ds)] for ds in DOMS)
                                - min(rate[(l, ds)] for ds in DOMS) for _, l in BUILDS},
           verdict='build-dominant' if SS_build >= SS_domain else 'domain-dominant')
io.open(OUT, 'w', encoding='utf-8', newline='\n').write(json.dumps(res, ensure_ascii=False, indent=2))
print()
print('已冻结 %s' % OUT)
