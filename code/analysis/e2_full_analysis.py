# -*- coding: utf-8 -*-
"""E2 全量分析（新 H20 数据）：一次算出论文要的全部对照表。

数据来源：本地同步目录（H20 → 本地每 2 分钟自动拉取）。
文件名形如 e1_<model>_<ds>_<arm>.csv；非零池探针（19d）输出到另一目录，
同步时加了 nz__ 前缀以示区分（两类探针文件名完全相同，不加前缀会互相覆盖）。

★ 关键陷阱（实测踩过）：reps>1 的探针把 item 写成 'name#r0/#r1/#r2' 并**追加到同名文件**，
  所以：
    - **主表必须剔除含 '#r' 的行**，否则样本量被重复行放大（st_a base 臂 103 行 → 混入后 412 行）；
    - 报告样本量时不能直接拿行数当样本量。

输出：
  A. 主表：每个 (模型, 数据集, 臂) 的 n / 出零数 / 显式弃答 / pred中位 / pred/gt中位
  B. 契约效应：base → permit/channel 的出零数与弃答数变化
  C. 反证对照：在语料本已作答的 item 上，permit/channel 的弃答率
  D. 换措辞一致性：原措辞 vs 换措辞臂
  E. 重复性：reps=3 的逐项一致率
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
import os
import statistics as st
import sys
from collections import defaultdict

sys.stdout.reconfigure(encoding='utf-8')

D_ALL = RP('analysis', 'e2_newh20')
NZ_PREFIX = 'nz__'

ZERO_ARMS = ['base', 'permit', 'bestA', 'bestB', 'bestC', 'channel']
PARA_ARMS = ['permitB', 'permitC', 'channelB']
NEW_ARMS = ['enum', 'enumAbstain', 'locate']      # §3.6(d) 因素分解用
NZ_ARMS = ['base', 'permit', 'channel']
DOMAINS = ['st_a', 'st_b', 'ucf', 'visdrone', 'aitod', 'countbench']
DENSE = ['st_a', 'st_b', 'ucf']
NEWDOM = ['visdrone', 'aitod', 'countbench']


def load(path):
    with open(path, encoding='utf-8-sig') as f:
        return list(csv.DictReader(f))


def load_single(path):
    """只取 reps=1 的行（主表用）。"""
    return [r for r in load(path) if '#r' not in str(r.get('item', ''))]


def load_reps(path):
    """只取 reps>1 的行（重复性分析用）。"""
    return [r for r in load(path) if '#r' in str(r.get('item', ''))]


def num(v):
    try:
        return float(str(v).strip())
    except Exception:
        return None


def is_abstain(row):
    blob = ' '.join(str(v or '') for k, v in row.items() if k not in ('pred', 'gt')).lower()
    return ('abstain' in blob) or ('cannot_judge' in blob) or ('no_people' in blob)


def summarize(rows):
    preds = [num(r.get('pred')) for r in rows]
    vals = [p for p in preds if p is not None]
    ratio = []
    for r in rows:
        p, g = num(r.get('pred')), num(r.get('gt'))
        if p is not None and g:
            ratio.append(p / g)
    return dict(
        n=len(rows),
        zero=sum(1 for p in preds if p == 0),
        abst=sum(1 for r in rows if is_abstain(r)),
        med=st.median(vals) if vals else None,
        medr=st.median(ratio) if ratio else None,
    )


def parse_name(fn):
    if not fn.startswith('e1_') or not fn.endswith('.csv'):
        return None
    body = fn[3:-4]
    for ds in sorted(DOMAINS, key=len, reverse=True):   # 长名优先，避免前缀误切
        tag = '_%s_' % ds
        i = body.find(tag)
        if i > 0:
            return body[:i], ds, body[i + len(tag):]
    return None


def collect(root):
    out = {}
    if not os.path.isdir(root):
        return out
    for p in sorted(glob.glob(os.path.join(root, '*.csv'))):
        fn = os.path.basename(p)
        pool = 'zero'
        if fn.startswith(NZ_PREFIX):
            pool, fn = 'nonzero', fn[len(NZ_PREFIX):]
        k = parse_name(fn)
        if k:
            out[(pool,) + k] = p
    return out


allf = collect(D_ALL)
zero = {k[1:]: v for k, v in allf.items() if k[0] == 'zero'}
nz = {k[1:]: v for k, v in allf.items() if k[0] == 'nonzero'}

print('发现：零池 %d 个文件，非零池 %d 个文件（目录 %s）' % (len(zero), len(nz), D_ALL))
models = sorted(set(k[0] for k in zero))
print('模型：%s' % models)
print()

print('=' * 112)
print('A. 主表（零池：语料 base 臂答 0 的 item；已剔除 reps>1 的重复行）')
print('=' * 112)
print('%-24s %-5s %-9s %5s %5s %6s %10s %12s' %
      ('模型', '数据集', '臂', 'n', '出零', '弃答', 'pred中位', 'pred/gt中位'))
for m in models:
    for ds in DOMAINS:
        for a in ZERO_ARMS + PARA_ARMS:
            k = (m, ds, a)
            if k not in zero:
                continue
            s = summarize(load_single(zero[k]))
            if s['n'] == 0:
                continue
            print('%-24s %-5s %-9s %5d %5d %6d %10s %12s' %
                  (m, ds, a, s['n'], s['zero'], s['abst'],
                   ('%.1f' % s['med']) if s['med'] is not None else '-',
                   ('%.3f' % s['medr']) if s['medr'] is not None else '-'))

print()
print('=' * 112)
print('B. 契约效应：base 的出零 → permit / channel 的出零（括号内为显式弃答数）')
print('=' * 112)
print('%-24s %-5s %20s %20s %20s' % ('模型', '数据集', 'base', 'permit', 'channel'))
for m in models:
    for ds in DOMAINS:
        cells = []
        for a in ('base', 'permit', 'channel'):
            k = (m, ds, a)
            if k in zero:
                s = summarize(load_single(zero[k]))
                if s['n']:
                    cells.append('%d零/%d弃 (n=%d)' % (s['zero'], s['abst'], s['n']))
                    continue
            cells.append('-')
        if any(c != '-' for c in cells):
            print('%-24s %-5s %20s %20s %20s' % (m, ds, *cells))

print()
print('=' * 112)
print('C. 反证对照（非零池：语料**本已给出数字**的 item）')
print('   若 permit/channel 在此弃答率也很高 ⇒ "契约释放潜在答案"的说法受威胁')
print('=' * 112)
print('%-24s %-5s %20s %20s %20s' % ('模型', '数据集', 'base', 'permit', 'channel'))
for m in sorted(set(k[0] for k in nz)):
    for ds in DOMAINS:
        cells = []
        for a in NZ_ARMS:
            k = (m, ds, a)
            if k in nz:
                s = summarize(load_single(nz[k]))
                if s['n']:
                    cells.append('%d零/%d弃 (n=%d)' % (s['zero'], s['abst'], s['n']))
                    continue
            cells.append('-')
        if any(c != '-' for c in cells):
            print('%-24s %-5s %20s %20s %20s' % (m, ds, *cells))

print()
print('=' * 112)
print('D. 换措辞一致性（固定响应词表，只改指令措辞）')
print('=' * 112)
for m in models:
    for ds in ('st_a', 'ucf'):
        line = []
        for a, b in (('permit', 'permitB'), ('permit', 'permitC'), ('channel', 'channelB')):
            ka, kb = (m, ds, a), (m, ds, b)
            if ka in zero and kb in zero:
                sa = summarize(load_single(zero[ka]))
                sb = summarize(load_single(zero[kb]))
                if sa['n'] and sb['n']:
                    line.append('%s→%s: 零 %d→%d, 弃 %d→%d'
                                % (a, b, sa['zero'], sb['zero'], sa['abst'], sb['abst']))
        if line:
            print('%-24s %-5s %s' % (m, ds, ' | '.join(line)))

print()
print('=' * 112)
print('E. 重复性（reps=3：同一 item 三次是否给出相同 pred）')
print('=' * 112)
for (m, ds, a), p in sorted(zero.items()):
    rows = load_reps(p)
    if not rows:
        continue
    by = defaultdict(list)
    for r in rows:
        it = str(r.get('item', ''))
        if '#r' in it:
            by[it.split('#r')[0]].append(num(r.get('pred')))
    if not by:
        continue
    agree = sum(1 for v in by.values() if len(set(v)) == 1)
    print('%-24s %-5s %-9s 三次完全一致 %d/%d (%.1f%%)'
          % (m, ds, a, agree, len(by), 100.0 * agree / len(by)))
