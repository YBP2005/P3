# -*- coding: utf-8 -*-
"""_f7_trunc_span.py —— **固定分位数截尾后的跨度**（回应 [external-review][external-review] 的 [Δ]）。

## 为什么
它的原话："补充基于**固定分位数（如 10%–90%）截断**后的标准化跨度分析。"
本文已有 F.8 的"端点跨度 54–80% 来自单个最极端档"这一事实，但**没有把"截掉两端固定分位"后的跨度
与端点跨度并排**。这正是"跨度是不是端点/量程的函数"的直接检验：若截掉两端 10% 后跨度大幅缩水，
那么**幅度**确实由极端档位驱动。

## 做法
对每个单元（与 A44/F.10 同一套定义，**直接 import `a44_split16.build()`**），取 **ISO 保序校准**后的
逐档 ρ 序列，算四种跨度：
  · 端点跨度（= 现用定义）
  · **mid80**：去掉两端各 10% 的档位后的极差（即要求固定分位数截尾）
  · **mid60**：去掉两端各 20%
  · 平均 |ρ|（面积型代理，对极端档不敏感）
并给出 mid80/endpoint 与 mid60/endpoint 的比值分布。
产物：`f7_trunc_span_result.json`（+ .md5）。用法：python -u _f7_trunc_span.py
"""
import hashlib
import importlib.util
import io
import json
import os
import statistics as st
import sys

import numpy as np

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
W = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(W, 'f7_trunc_span_result.json')

spec = importlib.util.spec_from_file_location('s16', os.path.join(W, 'a44_split16.py'))
s16 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(s16)           # 有 __main__ 守卫，import 不会跑主流程


def spans(rhos):
    v = np.sort(np.array(rhos, float))
    n = len(v)
    d = dict(endpoint=float(v[-1] - v[0]), mean_abs=float(np.mean(np.abs(v))), n=int(n))
    d['mid80'] = float(np.ptp(v[max(0, int(round(n * 0.1))):n - int(round(n * 0.1))])) if n >= 5 else d['endpoint']
    d['mid60'] = float(np.ptp(v[max(0, int(round(n * 0.2))):n - int(round(n * 0.2))])) if n >= 5 else d['endpoint']
    return d


def main():
    res = dict(purpose='固定分位数截尾后的跨度（[external-review][external-review]',
               design='ISO 保序校准后的逐档 ρ；mid80/mid60 = 去掉两端各 10%/20% 档位后的极差', units=[])
    print('=' * 116)
    print('■ 固定分位数截尾跨度（ISO 保序校准；与 A44/F.10 同一套单元定义）')
    print('=' * 116)
    print('%-32s %5s %10s %10s %10s %8s %8s %9s' %
          ('单元', '档位', '端点跨度', 'mid80', 'mid60', '80/端点', '60/端点', '平均|ρ|'))
    for lab, kind, unit in s16.build(False):
        r = s16.run_unit(unit, s16.SEED)['rho_iso']
        s = spans(r)
        rec = dict(lab=lab, kind=kind, **{k: round(v, 1) if isinstance(v, float) else v for k, v in s.items()})
        rec['ratio80'] = round(s['mid80'] / s['endpoint'], 3) if s['endpoint'] else None
        rec['ratio60'] = round(s['mid60'] / s['endpoint'], 3) if s['endpoint'] else None
        res['units'].append(rec)
        print('%-32s %5d %10.1f %10.1f %10.1f %8.2f %8.2f %9.1f' %
              (lab, s['n'], s['endpoint'], s['mid80'], s['mid60'], rec['ratio80'], rec['ratio60'], s['mean_abs']))
    r80 = sorted(x['ratio80'] for x in res['units'] if x['ratio80'] is not None)
    r60 = sorted(x['ratio60'] for x in res['units'] if x['ratio60'] is not None)
    n_unchanged80 = sum(1 for x in r80 if x >= 0.999)
    # ★ 按"档位数"分组才是可读的：4–5 档的单元里"去掉 10%"本身就是空操作
    fine = [x for x in res['units'] if x['n'] >= 10 and x['ratio80'] is not None]
    coarse = [x for x in res['units'] if x['n'] < 10 and x['ratio80'] is not None]
    res['summary'] = dict(
        median_ratio80=round(st.median(r80), 3), min_ratio80=round(r80[0], 3),
        median_ratio60=round(st.median(r60), 3), min_ratio60=round(r60[0], 3),
        n_units=len(r80), n_unchanged_at_80=n_unchanged80,
        n_shrunk_below_060_at_80=sum(1 for x in r80 if x < 0.60),
        fine_grid=dict(n=len(fine), median_ratio80=round(st.median([x['ratio80'] for x in fine]), 3),
                       lo80=round(min(x['ratio80'] for x in fine), 3),
                       hi80=round(max(x['ratio80'] for x in fine), 3),
                       median_ratio60=round(st.median([x['ratio60'] for x in fine]), 3)),
        coarse_grid=dict(n=len(coarse), median_ratio80=round(st.median([x['ratio80'] for x in coarse]), 3)))
    print('\n截尾 10%%：中位保留 %.2f ｜ 最小 %.2f ｜ 完全不变（≥0.999）%d/%d ｜ 缩到 <0.60 的 %d 个'
          % (res['summary']['median_ratio80'], res['summary']['min_ratio80'], n_unchanged80,
             len(r80), res['summary']['n_shrunk_below_060_at_80']))
    print('  ★ 分组看才有意义——**细网格单元（≥10 档）**：中位保留 %.2f，区间 [%.2f, %.2f]（截尾 20%% 时中位 %.2f）'
          % (res['summary']['fine_grid']['median_ratio80'], res['summary']['fine_grid']['lo80'],
             res['summary']['fine_grid']['hi80'], res['summary']['fine_grid']['median_ratio60']))
    print('    **粗网格单元（4–5 档）**：中位保留 %.2f（"去掉 10%%"对这些单元本身就是空操作）'
          % res['summary']['coarse_grid']['median_ratio80'])
    io.open(OUT, 'w', encoding='utf-8', newline='\n').write(json.dumps(res, ensure_ascii=False, indent=2))
    h = hashlib.md5(io.open(OUT, 'rb').read()).hexdigest()
    io.open(OUT + '.md5', 'w', encoding='utf-8', newline='\n').write(
        '%s  %s  (_f7_trunc_span.py)\n' % (h, os.path.basename(OUT)))
    print('\n已冻结 %s（md5 %s）' % (os.path.basename(OUT), h[:12]))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
