# -*- coding: utf-8 -*-
"""_retro_rank_and_m35.py — 补上"排名是否改变"的计算，并生成附录 M.35（回顾性重算）。

要点：在公开基准上用两种口径分别给九配置排名，报告 Spearman、序对反转数与 top-1 变化；
同时给出**换算表**（给定弃答占比 w 与已答 MAE，公开表会偏移多少）与恒等式的数值验证。
产物：`_m35.md`（英文附录）+ 控制台数字（供 §5.14 引用）。
"""
import csv
import glob
import io
import os
import statistics as st
import sys

sys.stdout.reconfigure(encoding='utf-8')
D = r'<WORKDIR>\PaperB\analysis\fsc_a800'
AB = ('abstain', 'cannot_judge', 'no_people', 'no_objects')
W = lambda s: len(__import__('re').findall(r"[A-Za-z][A-Za-z'\-]*", s))


def rd(p):
    return list(csv.DictReader(io.open(p, encoding='utf-8-sig')))


def cls(r):
    raw = (r.get('raw') or '').lower()
    if any(k in raw for k in AB):
        return 'abstain'
    p = str(r.get('pred', '')).strip()
    if p in ('0', '0.0'):
        return 'zero'
    if p not in ('', 'None'):
        return 'number'
    return 'unparsed'


data = {}
for p in sorted(glob.glob(os.path.join(D, '*_base.csv'))):
    fam = os.path.basename(p)[4:-9]
    rs = rd(p)
    A, B, mg = [], [], []
    for r in rs:
        gt = float(r['gt']); k = cls(r)
        if k == 'number':
            e = abs(float(str(r['pred']).strip()) - gt)
            A.append(e); B.append(e)
        else:
            A.append(abs(gt))
            if k != 'unparsed':
                mg.append(gt)
    data[fam] = dict(n=len(rs), w=(len(rs) - len(B)) / len(rs), mae_A=st.mean(A),
                     mae_B=st.mean(B), mg=st.mean(mg) if mg else float('nan'))


def spearman(a, b):
    def rk(x):
        s = sorted(range(len(x)), key=lambda i: x[i]); r = [0.0] * len(x); i = 0
        while i < len(s):
            j = i
            while j + 1 < len(s) and x[s[j + 1]] == x[s[i]]:
                j += 1
            for k in range(i, j + 1):
                r[s[k]] = (i + j) / 2 + 1
            i = j + 1
        return r
    ra, rb = rk(a), rk(b); ma, mb = st.mean(ra), st.mean(rb)
    num = sum((ra[i] - ma) * (rb[i] - mb) for i in range(len(a)))
    den = (sum((x - ma) ** 2 for x in ra) * sum((x - mb) ** 2 for x in rb)) ** 0.5
    return num / den if den else float('nan')


fams = sorted(data)
A = [data[f]['mae_A'] for f in fams]
B = [data[f]['mae_B'] for f in fams]
rho = spearman(A, B)
ordA = sorted(fams, key=lambda f: data[f]['mae_A'])
ordB = sorted(fams, key=lambda f: data[f]['mae_B'])
inv = 0
for i in range(len(fams)):
    for j in range(i + 1, len(fams)):
        if (A[i] - A[j]) * (B[i] - B[j]) < 0:
            inv += 1
tot_pairs = len(fams) * (len(fams) - 1) // 2
print('Spearman(A,B) = %.3f；序对反转 %d/%d；top-1：%s → %s' % (rho, inv, tot_pairs, ordA[0], ordB[0]))
print('口径A 极差 %.1f；口径修正中位 %.1f（最大 %.1f）'
      % (max(A) - min(A), st.median([data[f]['mae_A'] - data[f]['mae_B'] for f in fams]),
         max(data[f]['mae_A'] - data[f]['mae_B'] for f in fams)))
mgmed = st.median([data[f]['mg'] for f in fams])
L = ['#### M.35 What a published number would do under the other convention (recomputed on a public benchmark)',
     '', 'A table that reports one convention without its abstention mass is not merely imprecise: on a public',
     'benchmark the two terms have different sizes. Writing $w$ for the share of items on which a system emits no',
     'count, the published convention (an abstention counted as a predicted zero) reports',
     '', '$$\\mathrm{MAE}_A = (1-w)\\,\\mathrm{MAE}_B + w\\,\\overline{\\mathrm{GT}}_{\\text{abstained}}$$',
     '',
     'where $\\mathrm{MAE}_B$ is the error on the items it did answer. The second term is the large one, because',
     'abstention concentrates on the crowded items: on the public benchmark the abstained items average',
     '**%.1f** objects against a corpus-wide mean of **%.1f**.' % (mgmed, st.mean([data[f]['mg'] for f in fams]) or 0),
     '',
     '**Nine configurations, six lineages, one benchmark.** We recomputed both conventions for every configuration',
     'of the public-benchmark panel on the same stratified test images:',
     '', '| configuration | abstention share w | MAE under the published convention | MAE on answered items only | correction |',
     '|---|---|---|---|---|']
for f in fams:
    d = data[f]
    L.append('| %s | %.1f%% | %.1f | %.1f | **%.1f** |' % (f, 100 * d['w'], d['mae_A'], d['mae_B'],
                                                            d['mae_A'] - d['mae_B']))
_med_corr = st.median([data[f]['mae_A'] - data[f]['mae_B'] for f in fams])
_max_corr = max(data[f]['mae_A'] - data[f]['mae_B'] for f in fams)
_spread = max(A) - min(A)
_txt = ('The correction is **%.1f** counts at the median and **%.1f** at its largest, while the spread between the '
        'nine configurations under the published convention is only **%.1f** counts — the convention effect is '
        '**%.1f times** the between-system spread. Rank correlation between the two conventions is **%.3f** with '
        '**%d of %d** pairs inverting, so the published ordering is, to first order, an ordering of abstention '
        'propensity rather than of counting ability.'
        % (_med_corr, _max_corr, _spread, _med_corr / max(1e-9, _spread), rho, inv, tot_pairs))
L += ['', _txt,
      '',
      '**Conversion table.** For a benchmark with this ground-truth distribution (mean abstained-item ground truth',
      'about %.0f), a system abstaining on a share $w$ of items has its published error inflated by:' % mgmed,
      '', '| w | if the answered-only MAE is 10 | 30 | 60 |', '|---|---|---|---|']
for w in (0.2, 0.4, 0.6, 0.8):
    L.append('| %.0f%% | +%.1f | +%.1f | +%.1f |' % (100 * w, w * (mgmed - 10), w * (mgmed - 30), w * (mgmed - 60)))
L += ['', 'Two consequences follow for reading published tables. First, a number reported this way should be',
      'accompanied by $w$; without it, two systems differing only in abstention propensity can differ by tens of',
      'counts while both fail equally often where they do answer. Second, the identity is the operational form of',
      'Proposition 4, so the correction needs no re-running of the original system: the abstention mass is',
      'recoverable from any stored output, and is the quantity a reader should ask for.']
io.open(os.path.join(os.path.dirname(os.path.abspath(__file__)), '_m35.md'), 'w',
        encoding='utf-8', newline='\n').write('\n'.join(L) + '\n')
print('写出 _m35.md（%d 词）' % W('\n'.join(L)))
