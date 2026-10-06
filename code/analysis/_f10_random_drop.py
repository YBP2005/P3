# -*- coding: utf-8 -*-
"""_f10_random_drop.py —— F.10 的**随机删档**敏感性（回应 同一整改主题的多条预注册条款）。

## 为什么
上一轮我把 F.10 的跨口径事故改正后，明写了一件对自己不利的事：**等点数子采样的分位公式必取首尾两档**，
而极值本来就在端点 ⇒ 对这类阶梯"等点数"是**按构造的空操作**（保留率中位 1.00）。预注册条款因此说
"equal-count 保留端点，使'扫描密度不伪影'的证据不彻底"，并**具体要求**："在 F.10 补**随机删档** sensitivity"。

## 做法
对每条阶梯（按口径分开），从 n 档里**随机抽 k=4 档**（不放回，枚举或大样本随机），
算抽样子集的跨度与**全长跨度**之比，报：中位保留率、5–95 分位、最小保留率。
随机抽样**不保证保留端点** ⇒ 这才是对"扫描密度"的诚实扰动。
若随机删档下保留率仍接近 1，则"跨度不是扫描密度的函数"这一结论**有了真正的支撑**；
若明显下降，则要如实说明该结论只在"保留端点"的子类扰动下成立。

数据：`threeway_curves_v2.csv`（检测 τ，按 `match` 口径分开）与 `span_equalcount2.py` 的阶梯口径。
产物：`f10_random_drop_result.json`（+ .md5）。用法：python -u _f10_random_drop.py
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
import hashlib
import io
import itertools
import json
import os
import random
import statistics as st
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
W = os.path.dirname(os.path.abspath(__file__))
DATA = NR('analysis', 'data')
OUT = os.path.join(W, 'f10_random_drop_result.json')
K = 4
NDRAW = 2000
SEED = 20260924


def span(seq):
    v = [x[1] for x in seq]
    return max(v) - min(v)


def ladders(caliber):
    rows = list(csv.DictReader(io.open(NR('analysis', 'data', 'threeway_curves_v2.csv'),
                                       encoding='utf-8-sig')))
    out = collections.defaultdict(list)
    for r in rows:
        if caliber and r.get('match') != caliber:
            continue
        try:
            out[(r['paradigm'], r['knob'])].append((float(r['setting']), float(r['rho'])))
        except (TypeError, ValueError):
            pass
    for k in out:
        out[k].sort(key=lambda x: x[0])
    return out


def analyse(seq):
    n = len(seq)
    full = span(seq)
    if n <= K or full == 0:
        return None
    rnd = random.Random(SEED)
    idx_all = list(itertools.combinations(range(n), K))
    if len(idx_all) <= NDRAW:
        samples = idx_all                       # 组合数不大时**穷举**，比抽样更硬
        how = '穷举 C(%d,%d)=%d' % (n, K, len(idx_all))
    else:
        samples = [tuple(sorted(rnd.sample(range(n), K))) for _ in range(NDRAW)]
        how = '随机抽 %d 组' % NDRAW
    rets = [span([seq[i] for i in ix]) / full for ix in samples]
    rets.sort()
    return dict(n=n, full_span=round(full, 1), how=how,
                median=round(st.median(rets), 3),
                p05=round(rets[int(0.05 * len(rets))], 3),
                p95=round(rets[int(0.95 * len(rets))], 3),
                minimum=round(rets[0], 3),
                frac_ge_090=round(sum(1 for x in rets if x >= 0.90) / len(rets), 3))


def main():
    res = dict(purpose='F.10 随机删档敏感性（多条预注册要求）：随机抽 k=4 档，看跨度保留率',
               design='每条阶梯独立；组合数 ≤2000 时穷举，否则随机抽 2000 组；保留率 = 抽样跨度 / 全长跨度',
               k=K, per_caliber={})
    for cal in ('person', 'allclass'):
        L = ladders(cal)
        res['per_caliber'][cal] = {}
        print('\n' + '=' * 112)
        print('■ 口径 = %s：随机删档到 k=%d 后的跨度保留率' % (cal, K))
        print('=' * 112)
        print('%-34s %5s %10s %8s %8s %8s %8s  %s' % ('单元', '档数', '全长跨度', '中位', 'p05', 'p95', '最小', '≥0.90 占比'))
        for k in sorted(L):
            a = analyse(L[k])
            if not a:
                continue
            name = '%s / %s' % (k[0], k[1])
            res['per_caliber'][cal][name] = a
            print('%-34s %5d %10.1f %8.2f %8.2f %8.2f %8.2f  %.2f  （%s）'
                  % (name, a['n'], a['full_span'], a['median'], a['p05'], a['p95'], a['minimum'],
                     a['frac_ge_090'], a['how']))
    # 汇总：检测 τ 单元（域内 / COCO）的保留率
    s = {}
    for cal in res['per_caliber']:
        for tag, pred in (('in_domain', lambda n: '域内' in n), ('coco', lambda n: 'COCO' in n)):
            v = [x['median'] for n, x in res['per_caliber'][cal].items() if pred(n)]
            if v:
                s['%s_%s_median_retention' % (cal, tag)] = [round(min(v), 3), round(max(v), 3)]
    res['summary'] = s
    print('\n检测 τ 单元的中位保留率：')
    for k, v in s.items():
        print('  %-34s %s' % (k, v))
    io.open(OUT, 'w', encoding='utf-8', newline='\n').write(json.dumps(res, ensure_ascii=False, indent=2))
    h = hashlib.md5(io.open(OUT, 'rb').read()).hexdigest()
    io.open(OUT + '.md5', 'w', encoding='utf-8', newline='\n').write(
        '%s  %s  (_f10_random_drop.py)\n' % (h, os.path.basename(OUT)))
    print('\n已冻结 %s（md5 %s）' % (os.path.basename(OUT), h[:12]))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
