# -*- coding: utf-8 -*-
"""_p1d_results.py —— 汇总已完成项的结果：锚定阶梯（P1f）、同会话噪声底（P1g）、ucf 补跑（P5b）。"""
import collections
import csv
import glob
import io
import os
import re
import statistics as st
import sys

sys.stdout.reconfigure(encoding='utf-8')
OUTD = '/root/p1d_results'
ANCHOR = {'neutral0': 0, 'mention5': 5, 'mention50': 50, 'placebo100': 100, 'mention800': 800}
FAMS = ['Phi-3.5-vision-instruct', 'Qwen3-VL-8B-Instruct', 'llava-onevision-qwen2-7b-ov', 'gemma3-12b',
        'Qwen3-VL-32B-Instruct', 'InternVL3_5-8B']


def load(f):
    if not os.path.exists(f):
        return None
    return list(csv.DictReader(io.open(f, encoding='utf-8-sig', newline='')))


print('=== ① 锚定阶梯：zero% 与答案中位数 vs 被提及的值 ===')
print('  %-30s %s' % ('family', '  '.join('%-14s' % ('anchor=%d' % ANCHOR[a]) for a in
                                          ('neutral0', 'mention5', 'mention50', 'placebo100', 'mention800'))))
for fam in FAMS:
    cells = []
    for arm in ('neutral0', 'mention5', 'mention50', 'placebo100', 'mention800'):
        rows = load(os.path.join(OUTD, 'p1d_%s_%s.csv' % (fam, arm)))
        if not rows:
            cells.append('%-14s' % '—')
            continue
        z = sum(1 for r in rows if str(r.get('is_zero', '')).strip() == '1')
        vals = [int(r['pred']) for r in rows if str(r.get('pred', '')).strip().isdigit()]
        med = st.median(vals) if vals else float('nan')
        cells.append('%-14s' % ('%5.1f%%/%-6.0f' % (100.0 * z / len(rows), med)))
    print('  %-30s %s' % (fam[:30], '  '.join(cells)))
print('  （每格格式：zero% / 答案中位数）')

print()
print('=== ② 同会话噪声底（同一服务会话内 base 跑 3 遍）===')
base = load(os.path.join(OUTD, 'p1d_Qwen3-VL-8B-Instruct_base.csv'))          # P1d 主会话
reps = {t: load(os.path.join(OUTD, 'p1d_%s_Qwen3-VL-8B-Instruct_base.csv' % t))
        for t in ('rep1', 'rep2', 'rep3')}
if base:
    def zc(rows):
        return sum(1 for r in rows if str(r.get('is_zero', '')).strip() == '1')
    print('  P1d 主会话 base      : n=%d zero=%d (%.3f%%)' % (len(base), zc(base), 100.0 * zc(base) / len(base)))
for t, rows in reps.items():
    if rows:
        print('  %-20s: n=%d zero=%d (%.3f%%)' % (t, len(rows), zc(rows), 100.0 * zc(rows) / len(rows)))
if all(reps.values()):
    for a, b in (('rep1', 'rep2'), ('rep1', 'rep3'), ('rep2', 'rep3')):
        ra = {r['item']: r for r in reps[a]}
        rb = {r['item']: r for r in reps[b]}
        common = sorted(set(ra) & set(rb))
        same = sum(1 for i in common if str(ra[i].get('raw')) == str(rb[i].get('raw')))
        dz = sum(1 for i in common if str(ra[i].get('is_zero')) == '1') - \
            sum(1 for i in common if str(rb[i].get('is_zero')) == '1')
        print('  %s vs %s：共同 %d 项 ｜ raw 逐字相同 %d/%d (%.1f%%) ｜ Δzero %+d (%.3f pp)'
              % (a, b, len(common), same, len(common), 100.0 * same / len(common),
                 dz, 100.0 * dz / len(common)))
    # 同会话 vs 跨会话
    rb = {r['item']: r for r in reps['rep1']}
    rr = {r['item']: r for r in base}
    common = sorted(set(rb) & set(rr))
    same = sum(1 for i in common if str(rb[i].get('raw')) == str(rr[i].get('raw')))
    dz = sum(1 for i in common if str(rb[i].get('is_zero')) == '1') - \
        sum(1 for i in common if str(rr[i].get('is_zero')) == '1')
    print('  rep1 vs P1d主会话（**跨会话**）：共同 %d 项 ｜ raw 逐字相同 %d/%d (%.1f%%) ｜ Δzero %+d (%.3f pp)'
          % (len(common), same, len(common), 100.0 * same / len(common), dz, 100.0 * dz / len(common)))

print()
print('=== ③ P5b：ucf 全覆盖补跑（maxlen 16384）===')
for m in ('Qwen3-VL-8B-Instruct', 'Qwen3-VL-32B-Instruct'):
    for arm in ('base', 'forbid0', 'permit'):
        f = '/root/p5a_results/p5a_%s_ml16384_%s.csv' % (m, arm)
        rows = load(f)
        if not rows:
            print('  %-26s %-8s 缺' % (m, arm))
            continue
        err = [r for r in rows if str(r.get('raw', '')).startswith('ERR:')]
        print('  %-26s %-8s 行=%d ERR=%d ｜ ERR 样例=%s'
              % (m, arm, len(rows), len(err), (str(err[0]['raw'])[:40] if err else '无')))
print('RESULT_DONE')
