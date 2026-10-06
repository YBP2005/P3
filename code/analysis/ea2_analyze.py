# -*- coding: utf-8 -*-
"""ea2_analyze.py — **E2**（真零池 × 多构建 × 双语言 × 3 次服务）的分析器。

## 分类口径（与论文自身一致，**不是自创**）
`repro_github/code/analysis/a5_judge.py::cls()` 的 raw-match 顺序：先扫 `raw` 小写文本里的
`abstain` / `cannot_judge` / `no_people`，再退回 `pred`（空 ⇒ unparsed，0 ⇒ zero，否则 nonzero）。
本脚本逐字沿用该顺序 —— 这正是论文里所有率的算法（#46 已在出货代码里把它写成默认）。

## 报告什么（对应预注册条款的诉求）
  ① **通道构成**：真零图上每条臂各通道的占比（base 答 0 = 被压制的弃权；channel 的 no_people = 显式"没有人"）；
  ② **分层对照**：`z0easy`（低杂波）vs `z0hard`（高杂波）——机制检验（弃权由可辨性触发还是由"没有目标"触发）；
  ③ **语言对照**：同批图上的 CN vs EN；
  ④ **服务级噪声**：同一构建 3 次**服务启动**之间的极差（这是 E2 独有的维度）。

用法：python -u ea2_analyze.py [--root <default: data/derived/ea2/ in this package>] [--out <json>]
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
import argparse
import collections
import csv
import glob
import io
import json
import os
import re
import statistics as st
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
ROOT = RP('analysis', 'ea2_z0')
OUT = RP('analysis', 'work', 'ea2_z0_result.json')


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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', default=ROOT)
    ap.add_argument('--out', default=OUT)
    A = ap.parse_args()

    # 目录命名：<lang>_<tag>_s<serving>，例如 cn_ivl8b_s1 / en_q32_s3
    groups = collections.defaultdict(dict)     # (build, serving, lang, stratum, arm) -> {item: class}
    files = glob.glob(os.path.join(A.root, '*', '*.csv'))
    pat = re.compile(r'^(cn|en)_(.+)_s(\d)$')
    for f in files:
        d = os.path.basename(os.path.dirname(f))
        m = pat.match(d)
        if not m:
            continue
        lang, build, srv = m.group(1), m.group(2), int(m.group(3))
        b = os.path.basename(f)
        mm = re.match(r'^e1_(.+?)_(z0easy|z0hard)_(base|permit|channel|bestA|bestB|bestC)_(\w+)\.csv$', b)
        if not mm:
            continue
        model, stratum, arm = mm.group(1), mm.group(2), mm.group(3)
        rows = list(csv.DictReader(io.open(f, encoding='utf-8-sig', errors='replace')))
        groups[(build, srv, lang, stratum, arm)] = {r['item']: cls_of(r.get('raw'), r.get('pred'))
                                                    for r in rows}
    if not groups:
        sys.exit('!! 没读到任何 E2 产物（检查 <root>/<cn|en>_<build>_s<N>/*.csv 结构）')

    def dist(d):
        c = collections.Counter(d.values())
        n = len(d) or 1
        return {k: round(100.0 * c.get(k, 0) / n, 1) for k in
                ('zero', 'nonzero', 'no_people', 'cannot_judge', 'abstain', 'unparsed')}

    res = collections.defaultdict(dict)
    for (build, srv, lang, stratum, arm), d in sorted(groups.items()):
        res[build].setdefault('%s_s%d' % (lang, srv), {})['%s/%s' % (stratum, arm)] = \
            dict(n=len(d), pct=dist(d))

    print('=' * 108)
    print('■ E2 通道构成（%，按 构建 / 语言 / 服务 / 分层 / 臂）')
    print('=' * 108)
    for build in sorted(res):
        for tag in sorted(res[build]):
            for key in sorted(res[build][tag]):
                v = res[build][tag][key]
                p = v['pct']
                print('  %-12s %-8s %-18s n=%3d  no_people %5.1f | cannot_judge %5.1f | abstain %5.1f '
                      '| zero %5.1f | nonzero %5.1f | unparsed %5.1f'
                      % (build, tag, key, v['n'], p['no_people'], p['cannot_judge'], p['abstain'],
                         p['zero'], p['nonzero'], p['unparsed']))

    # 服务级噪声：同一 (build, lang, stratum, arm) 在 3 次服务之间的极差
    print('\n' + '=' * 108)
    print('■ 服务级噪声（同一构建同一条件下的 3 次服务间极差，pp）')
    print('=' * 108)
    noise = {}
    for build in sorted(res):
        langs = sorted({t.split('_')[0] for t in res[build]})
        for lang in langs:
            keys = sorted(res[build].get('%s_s1' % lang, {}))
            for key in keys:
                vals = {}
                for s in (1, 2, 3):
                    tag = '%s_s%d' % (lang, s)
                    if tag in res[build] and key in res[build][tag]:
                        vals[s] = res[build][tag][key]['pct']
                if len(vals) < 2:
                    continue
                rng = {k: round(max(v[k] for v in vals.values()) - min(v[k] for v in vals.values()), 1)
                       for k in ('no_people', 'zero')}
                noise['%s|%s|%s' % (build, lang, key)] = dict(per_serving={str(k): v for k, v in vals.items()},
                                                              range_pp=rng)
                print('  %-12s %-4s %-18s  no_people 极差 %4.1f pp | zero 极差 %4.1f pp'
                      % (build, lang, key, rng['no_people'], rng['zero']))

    out = dict(
        purpose='E2（盲审 #1）：真零池 × 多构建 × 双语言 × 3 次服务启动 —— 通道构成、分层/语言对照、服务级噪声',
        inputs=dict(root=A.root, n_files=len(files)),
        rule='raw-match：先扫 raw 小写文本的 abstain/cannot_judge/no_people，再退回 pred（同 a5_judge.cls()）',
        by_build=res, serving_noise=noise,
    )
    io.open(A.out, 'w', encoding='utf-8', newline='\n').write(json.dumps(out, ensure_ascii=False, indent=2))
    print('\n已写出 %s（%d 个条件）' % (A.out, len(noise)))


if __name__ == '__main__':
    main()
