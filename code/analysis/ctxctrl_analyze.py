# -*- coding: utf-8 -*-
"""ctxctrl_analyze.py（远端）—— S1 服务栈对照（max-model-len 4096 vs 8192）的汇总器。

## 回答的问题
M.41 的"同分辨率重复"里 12 格中 9 格两批一致到 ≤0.5 pp，唯一大分歧是
**Phi-3.5-vision-instruct / `enumAbstain` 的弃权率：12.7%（8192）vs 48.7%（4096）= 36.0 pp**。
预注册要求：**复跑 4096/8192 各 3 次，报均值与极差**。本器把三件事分开：

  ① **同一上下文内的运行噪声**（3 次全新起服的极差）——分辨率下限；
  ② **上下文之间的差**（4096 均值 vs 8192 均值）——可归因于服务配置的部分；
  ③ **与两个历史件的关系**：冻结面板 `/root/fsc_results`（4096）与 E1 的 384 列 `/root/w1_results/fsc_sc384`（8192）。
     ⇒ 若"新 4096 均值"贴近冻结面板、"新 8192 均值"贴近 E1 列，则 36 pp 是**服务配置的属性**；
       若两者都贴近其中一侧，则原分歧更像**批次/端点噪声**，M.41 的归属说法需要改。

## 口径
分类**逐字复用**论文自身的 raw-match 顺序（与 `fsc_res_analyze.py` / `a5_judge.cls()` 同源）：
先扫 raw 文本的 `abstain` / `cannot_judge` / `no_people`，再退回 `pred`（0 → zero，非 0 → nonzero，空 → unparsed）。
**不写第二套解析**——本器与冻结分析器同源，故与论文数字可比。

产物：`/root/w1_results/ctxctrl_result.json`
用法：python -u ctxctrl_analyze.py [--root /root/w1_results]
"""
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
ARMS = ('base', 'permit', 'channel', 'enumAbstain')
BUILDS = ('Phi-3.5-vision-instruct', 'InternVL3_5-8B', 'gemma3-12b')
CTXS = ('4096', '8192')
STARTS = ('1', '2', '3')


def cls_of(raw, pred):
    """★ 与 `fsc_res_analyze.py` / `a5_judge.cls()` **同源**（逐字同一顺序），不得另立口径。"""
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


def read(f):
    d = {}
    for r in csv.DictReader(io.open(f, encoding='utf-8-sig', errors='replace')):
        it = str(r.get('item') or '')
        if '#' in it:
            continue
        d[it] = cls_of(r.get('raw'), r.get('pred'))
    return d


def rates(path):
    """一个臂文件的六率。返回 None 表示该文件不存在/为空。"""
    if not os.path.exists(path):
        return None
    d = read(path)
    if not d:
        return None
    c = collections.Counter(d.values())
    n = len(d)
    return dict(n=n, **{k: round(100.0 * c.get(k, 0) / n, 1)
                        for k in ('zero', 'abstain', 'cannot_judge', 'no_people', 'nonzero', 'unparsed')})


def rng(vals):
    return [round(min(vals), 1), round(max(vals), 1)] if vals else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', default='/root/w1_results')
    A = ap.parse_args()
    out = dict(purpose='S1：服务栈对照（max-model-len 4096 vs 8192），回答 M.41 的 36.0 pp 归属问题',
               design='3 构建 × 2 上下文 × 3 次全新起服 × 4 臂 × 300 张（同 FSC-147 冻结样本、同 384 px、同探针）',
               caliber='raw-match（与 fsc_res_analyze.py / a5_judge.cls() 同源）',
               per_start={}, across_starts={}, history={}, headline=[])

    # ── 本轮 18 次起服 ────────────────────────────────────────────────────
    for b in BUILDS:
        for ctx in CTXS:
            for k in STARTS:
                d = os.path.join(A.root, 'ctxctrl_%s_ml%s_s%s' % (
                    {'Phi-3.5-vision-instruct': 'phi35', 'InternVL3_5-8B': 'ivl8b',
                     'gemma3-12b': 'gemma12b'}[b], ctx, k))
                for arm in ARMS:
                    r = rates(os.path.join(d, 'fsc_%s_%s.csv' % (b, arm)))
                    if r:
                        out['per_start']['%s|%s|%s|%s' % (b, ctx, arm, k)] = r
    # 3 次起服的均值与极差
    for b in BUILDS:
        for ctx in CTXS:
            for arm in ARMS:
                rs = [out['per_start']['%s|%s|%s|%s' % (b, ctx, arm, k)]
                      for k in STARTS if '%s|%s|%s|%s' % (b, ctx, arm, k) in out['per_start']]
                if not rs:
                    continue
                rec = dict(n_starts=len(rs), n=rs[0]['n'])
                for key in ('zero', 'abstain', 'cannot_judge', 'no_people', 'unparsed'):
                    v = [x[key] for x in rs]
                    rec[key] = round(st.mean(v), 1)
                    rec[key + '_range'] = rng(v)
                    rec[key + '_vals'] = v
                out['across_starts']['%s|%s|%s' % (b, ctx, arm)] = rec

    # ── 两个历史件 ───────────────────────────────────────────────────────
    for tag, dirn in (('frozen_panel_ml4096', '/root/fsc_results'),
                      ('e1_sweep384_ml8192', os.path.join(A.root, 'fsc_sc384'))):
        for b in BUILDS:
            for arm in ARMS:
                r = rates(os.path.join(dirn, 'fsc_%s_%s.csv' % (b, arm)))
                if r:
                    out['history']['%s|%s|%s' % (tag, b, arm)] = r

    # ── 主表：逐 (构建, 臂) 把四个来源并排 ────────────────────────────────
    print('=' * 118)
    print('■ S1 服务栈对照：`--max-model-len` 4096 vs 8192（每格 3 次全新起服；同 300 图 / 同 384 px / 同探针）')
    print('=' * 118)
    print('%-26s %-14s %-22s %-22s %-16s %-16s' % (
        '构建', '臂', '本轮 4096（均值[极差]）', '本轮 8192（均值[极差]）', '冻结面板(4096)', 'E1列(8192)'))
    for b in BUILDS:
        for arm in ARMS:
            a4 = out['across_starts'].get('%s|4096|%s' % (b, arm))
            a8 = out['across_starts'].get('%s|8192|%s' % (b, arm))
            h4 = out['history'].get('frozen_panel_ml4096|%s|%s' % (b, arm))
            h8 = out['history'].get('e1_sweep384_ml8192|%s|%s' % (b, arm))
            f = lambda x: ('%5.1f [%s]' % (x['abstain'], '–'.join(str(v) for v in x['abstain_range']))) if x else '—'
            print('%-26s %-14s %-22s %-22s %-16s %-16s' % (
                b, arm, f(a4), f(a8),
                ('%5.1f' % h4['abstain']) if h4 else '—',
                ('%5.1f' % h8['abstain']) if h8 else '—'))

    print('\n■ 关键格：Phi-3.5-vision-instruct / `enumAbstain` 的**弃权率**（36.0 pp 分歧所在）')
    for ctx in CTXS:
        x = out['across_starts'].get('Phi-3.5-vision-instruct|%s|enumAbstain' % ctx)
        if x:
            print('  本轮 ctx=%s：均值 %5.1f%%  三次 %s  极差 %.1f pp'
                  % (ctx, x['abstain'], x['abstain_vals'], x['abstain_range'][1] - x['abstain_range'][0]))
    h4 = out['history'].get('frozen_panel_ml4096|Phi-3.5-vision-instruct|enumAbstain')
    h8 = out['history'].get('e1_sweep384_ml8192|Phi-3.5-vision-instruct|enumAbstain')
    print('  历史：冻结面板(4096) %s ；E1 列(8192) %s' % (h4['abstain'] if h4 else '—', h8['abstain'] if h8 else '—'))

    a4 = out['across_starts'].get('Phi-3.5-vision-instruct|4096|enumAbstain')
    a8 = out['across_starts'].get('Phi-3.5-vision-instruct|8192|enumAbstain')
    if a4 and a8:
        d_ctx = abs(a4['abstain'] - a8['abstain'])
        r4 = a4['abstain_range'][1] - a4['abstain_range'][0]
        r8 = a8['abstain_range'][1] - a8['abstain_range'][0]
        verdict = ('服务配置（上下文长度）可解释' if d_ctx > max(r4, r8)
                   else '两次起服噪声已足以解释（上下文长度不是唯一原因）')
        out['verdict'] = dict(delta_ctx_pp=round(d_ctx, 1), range_4096_pp=round(r4, 1),
                              range_8192_pp=round(r8, 1), reading=verdict)
        print('\n■ 判定：4096 与 8192 的弃权率差 **%.1f pp**；同上下文内 3 次起服极差 4096 %.1f pp / 8192 %.1f pp'
              % (d_ctx, r4, r8))
        print('  ⇒ %s' % verdict)

    # 复现性总览：与历史件比（同上下文应当最接近）
    print('\n■ 与历史件的差（同上下文的那一对应当最小）')
    for ctx, htag in (('4096', 'frozen_panel_ml4096'), ('8192', 'e1_sweep384_ml8192')):
        ds = []
        for b in BUILDS:
            for arm in ARMS:
                a = out['across_starts'].get('%s|%s|%s' % (b, ctx, arm))
                h = out['history'].get('%s|%s|%s' % (htag, b, arm))
                if a and h:
                    ds.append((b, arm, round(a['abstain'] - h['abstain'], 1)))
        if ds:
            print('  ctx=%s vs %s：' % (ctx, htag))
            for b, arm, d in ds:
                print('    %-26s %-14s %+6.1f pp' % (b, arm, d))

    p = os.path.join(A.root, 'ctxctrl_result.json')
    io.open(p, 'w', encoding='utf-8', newline='\n').write(json.dumps(out, ensure_ascii=False, indent=2))
    print('\n已写出 %s' % p)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
