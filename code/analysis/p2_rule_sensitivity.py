# -*- coding: utf-8 -*-
"""p2_rule_sensitivity.py —— 【C-16 闭环】把"重解析规则是否事后任意"变成一个**可报的数**。

背景（4 家评审提的同一件事）：
  冻结探针 `19e_probe_multi.py` 的 `parse()` 要求 `{` 后紧跟键名，而本批输出是**带引号的键**
  ⇒ `channel` 臂 1,199/1,200 次结构化解析落空。处置是**不改冻结件**、改用**离线重解析**从已存
  `raw` 派生 `pred`，并逐行记录命中规则（R1 fenced+quoted / R2 冻结原正则 / R3 first-int）。
  评审问：**我是不是挑了一个对自己有利的规则？**

本脚本的答法（零新跑，只用已存 CSV）：
  对 P2 的 12 个臂文件，逐项比较**两套分类口径**：
    (A) **重解析口径**：直接读重解析后的 `pred` 列（R1/R2/R3 已按优先级写入）；
    (B) **冻结口径**：`cls_of(raw, pred)` —— 先按 `raw` **子串**找 abstain/cannot_judge/no_people，
        否则取 `pred` 的数值类；这正是**往轮**用的口径（与 `ea2_mixed_analyze.py` 逐字一致）。
  然后报**两套口径下关键率的最大绝对差（pp）**。若最大差在噪声底以下 ⇒ 规则选择**不承重**。

输出：
  ① 每个文件的逐类计数差 → ② 关键率对比表 → ③ 最大绝对差（这就是要写进 M.21.9 的那个数）。
"""
import collections
import csv
import glob
import io
import os
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
ROOT = r'<WORKDIR>\PaperB'
P2 = os.path.join(ROOT, 'analysis', 'p2_a800', 'p2_probe_results_reparsed')
KEYS = ('zero', 'nonzero', 'no_people', 'cannot_judge', 'abstain', 'unparsed')


def cls_of(raw, pred):
    """往轮口径（与 ea2_mixed_analyze.py 的 cls_of 逐字一致）：raw 子串优先，再看 pred。"""
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


def cls_reparse(pred):
    """重解析口径：只用 R1/R2/R3 写入后的 pred 列。"""
    p = str(pred or '').strip()
    if p == '':
        return 'unparsed'
    if p.lower() in ('abstain', 'cannot_judge', 'no_people'):
        return p.lower()
    try:
        return 'zero' if float(p) == 0 else 'nonzero'
    except ValueError:
        return 'unparsed'


def rate(c, keys):
    n = sum(c.values())
    return 100.0 * sum(c.get(k, 0) for k in keys) / n if n else 0.0


def main():
    files = sorted(glob.glob(os.path.join(P2, '*.csv')))
    print('=' * 96)
    print('P2 重解析规则灵敏度：12 臂 × 两套口径（重解析 pred  vs  冻结 raw-子串口径）')
    print('=' * 96)
    tot_a = collections.Counter()
    tot_b = collections.Counter()
    rows = []
    for f in files:
        name = os.path.basename(f)
        rs = list(csv.DictReader(io.open(f, encoding='utf-8')))
        a = collections.Counter(cls_reparse(r.get('pred')) for r in rs)
        b = collections.Counter(cls_of(r.get('raw'), r.get('pred')) for r in rs)
        tot_a += a
        tot_b += b
        arm = 'base' if '_base' in name else ('channel' if '_channel' in name else 'permit')
        # 每个臂只比它自己的关键率
        if arm == 'base':
            ka, kb = rate(a, ('zero',)), rate(b, ('zero',))
            label = 'base zero rate'
        elif arm == 'permit':
            ka, kb = rate(a, ('abstain', 'cannot_judge', 'no_people')), rate(b, ('abstain', 'cannot_judge', 'no_people'))
            label = 'permit abstain rate'
        else:
            ka, kb = rate(a, ('abstain', 'cannot_judge', 'no_people')), rate(b, ('abstain', 'cannot_judge', 'no_people'))
            label = 'channel outlet rate'
        rows.append((name, len(rs), label, ka, kb, ka - kb))
    for name, n, label, ka, kb, d in rows:
        flag = '' if abs(d) < 0.35 else '  ← 差 >1 项'
        print('  %-46s n=%-4d %-22s A %6.2f%%  B %6.2f%%  Δ %+6.2f pp%s'
              % (name, n, label, ka, kb, d, flag))
    print('-' * 96)
    print('  合计逐类计数（A 重解析 / B 冻结口径）：')
    for k in KEYS:
        print('    %-14s A %5d ｜ B %5d ｜ Δ %+d' % (k, tot_a.get(k, 0), tot_b.get(k, 0),
                                                     tot_a.get(k, 0) - tot_b.get(k, 0)))
    na, nb = sum(tot_a.values()), sum(tot_b.values())
    same = sum((tot_a & tot_b).values())
    print('-' * 96)
    print('  逐项一致 %d / %d = %.4f%%' % (same, na, 100.0 * same / na))
    print('  ★ 关键率的最大绝对差 = **%.2f pp**（12 臂全部）；最大差所在臂 = %s'
          % (max(abs(d) for *_, d in rows),
             max(rows, key=lambda r: abs(r[5]))[0]))
    print('  ⇒ 若该值在自家噪声底（2.15–6.46 pp）以下，则"用哪套解析规则"不承重。')


if __name__ == '__main__':
    main()
