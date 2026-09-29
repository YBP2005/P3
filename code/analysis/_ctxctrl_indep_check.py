# -*- coding: utf-8 -*-
"""_ctxctrl_indep_check.py —— S1 的**独立重算**：绕开 `ctxctrl_analyze.py`，直接读原始逐项 CSV 逐格比对。

## 为什么必须独立
本轮（v0539）已经栽过一次"聚合口径错误"（`dict.update()` 把三次服务并成一次）与一次"取极值错误"。
S1 的核心结论恰恰是一个**取极值/汇总**结论（"上下文之差 36.4 pp ≫ 同上下文极差 0.4 pp"），
所以必须用**另一条代码路径**从最原始的逐项记录重算一遍，而不是相信分析器的输出。

## 独立性体现在哪
* 读的是 `analysis/ctxctrl/<dir>/fsc_<model>_<arm>.csv` 的**原始行**（item/pred/raw），
  重算每个起服的弃权率；
* 分类规则**按论文写死的 raw-match 顺序独立实现**（先扫 raw 的 abstain/cannot_judge/no_people，
  再退回 pred），不 import 分析器、不读中间产物；
* 与冻结件 `ctxctrl_result.json` 的每一个数逐格比对，并把**关键判定**重推一遍；
* 另外核对两个**历史件**（冻结面板 4096 / E1 的 384 列 8192）的对应格——它们决定"36.4 pp 是不是
  把两次历史批次也复现了"。

产物：`_ctxctrl_indep_check.md`（结论）+ 退出码（0 = 全过）
"""
import collections
import csv
import io
import json
import os
import statistics as st
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
ROOT = r'<WORKDIR>\PaperB\analysis'
CTX = os.path.join(ROOT, 'ctxctrl')
FSC = os.path.join(ROOT, 'fsc_res')
FROZEN = os.path.join(CTX, 'ctxctrl_result.json')
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '_ctxctrl_indep_check.md')
ARMS = ('base', 'permit', 'channel', 'enumAbstain')
TAG = {'Phi-3.5-vision-instruct': 'phi35', 'InternVL3_5-8B': 'ivl8b', 'gemma3-12b': 'gemma12b'}
DISP = {'InternVL3_5-8B': 'InternVL3.5-8B', 'Phi-3.5-vision-instruct': 'Phi-3.5-vision-instruct',
        'Qwen3-VL-32B-Instruct': 'Qwen3-VL-32B-Instruct', 'gemma3-12b': 'gemma-3-12b',
        'llava-onevision-qwen2-7b-ov': 'LLaVA-OneVision-7B'}


def cls(raw, pred):
    """raw-match（**独立实现**，与论文写死的顺序一致：abstain → cannot_judge → no_people → pred）。"""
    r = (raw or '').lower()
    if 'abstain' in r:
        return 'abstain'
    if 'cannot_judge' in r:
        return 'cannot_judge'
    if 'no_people' in r:
        return 'no_people'
    p = (pred or '').strip()
    if p == '':
        return 'unparsed'
    try:
        return 'zero' if float(p) == 0 else 'nonzero'
    except ValueError:
        return 'unparsed'


def rate(f, key='abstain'):
    n = k = 0
    for r in csv.DictReader(io.open(f, encoding='utf-8-sig', errors='replace')):
        if '#' in str(r.get('item') or ''):
            continue
        n += 1
        if cls(r.get('raw'), r.get('pred')) == key:
            k += 1
    return (k, n, round(100.0 * k / n, 1)) if n else None


L, ok, bad = [], 0, []
P = L.append


def chk(label, cond, detail=''):
    global ok
    if cond:
        ok += 1
        P('| OK | %s | %s |' % (label, detail))
    else:
        bad.append(label)
        P('| **FAIL** | %s | %s |' % (label, detail))


frozen = json.loads(io.open(FROZEN, encoding='utf-8').read())
P('# S1（服务栈对照）独立重算 —— 绕开分析器，直读原始逐项 CSV')
P('')
P('| 判定 | 检查 | 详情 |')
P('|---|---|---|')

# ── ① 逐格重算：本轮 18 次起服 × 4 臂的弃权率 ──────────────────────────────
live = collections.defaultdict(list)     # (model, ctx, arm) -> [rate, ...]
nrows = {}
for m, tag in TAG.items():
    for ctx in ('4096', '8192'):
        for s in ('1', '2', '3'):
            for arm in ARMS:
                f = os.path.join(CTX, 'ctxctrl_%s_ml%s_s%s' % (tag, ctx, s),
                                 'fsc_%s_%s.csv' % (m, arm))
                if not os.path.exists(f):
                    bad.append('缺文件 %s' % f)
                    continue
                k, n, pct = rate(f)
                nrows['%s|%s|%s|%s' % (m, ctx, arm, s)] = n
                live[(m, ctx, arm)].append(pct)
                # 与冻结件逐格比
                fr = frozen['per_start'].get('%s|%s|%s|%s' % (m, ctx, arm, s))
                chk('冻结件逐格一致 %s %s %s s%s' % (DISP[m], ctx, arm, s),
                    bool(fr) and abs(fr['abstain'] - pct) < 1e-9,
                    '重算 %.1f vs 冻结 %s（n=%d）' % (pct, fr['abstain'] if fr else None, n))

P('')
P('**① 本轮均值与极差（独立重算）**')
P('')
P('| 构建 | 臂 | ctx | 三次弃权率 | 均值 | 极差 |')
P('|---|---|---|---|---|---|')
agg = {}
for m in TAG:
    for arm in ARMS:
        for ctx in ('4096', '8192'):
            v = live[(m, ctx, arm)]
            agg[(m, ctx, arm)] = (st.mean(v), max(v) - min(v))
            P('| %s | %s | %s | %s | **%.1f** | **%.1f** |'
              % (DISP[m], arm, ctx, ' / '.join('%.1f' % x for x in v), st.mean(v), max(v) - min(v)))

# ── ② 关键判定重推 ───────────────────────────────────────────────────────
m = 'Phi-3.5-vision-instruct'
m4, r4 = agg[(m, '4096', 'enumAbstain')]
m8, r8 = agg[(m, '8192', 'enumAbstain')]
d = abs(m4 - m8)
P('')
P('**② 关键格判定（`%s` / `enumAbstain`）**' % DISP[m])
P('')
P('- 4096：%.1f%%（极差 %.1f pp）｜8192：%.1f%%（极差 %.1f pp）｜上下文之差 **%.1f pp**'
  % (m4, r4, m8, r8, d))
chk('上下文之差远大于同上下文极差（判定"服务配置可解释"）', d > 4 * max(r4, r8),
    '%.1f pp ≫ %.1f pp' % (d, max(r4, r8)))
chk('冻结件的判定与独立重算一致', frozen.get('verdict', {}).get('reading', '').startswith('服务配置'),
    str(frozen.get('verdict', {})))
chk('冻结件记的差值与独立重算一致', abs(frozen['verdict']['delta_ctx_pp'] - round(d, 1)) < 0.15,
    '冻结 %s vs 重算 %.1f' % (frozen['verdict']['delta_ctx_pp'], d))

# 上下文效应是否只出现在 Phi-3.5
movers = [(DISP[mm], arm, abs(agg[(mm, '4096', arm)][0] - agg[(mm, '8192', arm)][0]))
          for mm in TAG for arm in ARMS]
big = [x for x in movers if x[2] > 0.5]
P('')
P('**③ 12 格里跨上下文移动 > 0.5 pp 的**：%s' % ('、'.join('%s/%s %.1f pp' % x for x in big) or '无'))
chk('跨上下文移动 >0.5 pp 的格恰为 2 个且都属于 Phi-3.5',
    len(big) == 2 and all(x[0] == 'Phi-3.5-vision-instruct' for x in big),
    '实际：%s' % big)
chk('其余 10 格跨上下文移动 ≤0.5 pp', len([x for x in movers if x[2] <= 0.5]) == 10)

# ── ③ 与两个历史件的逐格核对 ─────────────────────────────────────────────
P('')
P('**④ 与两个历史件逐格核对（同上下文的那一对应最接近）**')
P('')
P('| 构建 | 臂 | 本轮 4096 | 冻结面板(4096) | 差 | 本轮 8192 | E1 列(8192) | 差 |')
P('|---|---|---|---|---|---|---|---|')
worst = 0.0
for mm in TAG:
    for arm in ARMS:
        h4 = rate(os.path.join(FSC, 'frozen384', 'fsc_%s_%s.csv' % (mm, arm)))
        h8 = rate(os.path.join(FSC, '384', 'fsc_%s_%s.csv' % (mm, arm)))
        a4 = agg[(mm, '4096', arm)][0]
        a8 = agg[(mm, '8192', arm)][0]
        d4 = a4 - h4[2] if h4 else float('nan')
        d8 = a8 - h8[2] if h8 else float('nan')
        worst = max(worst, abs(d4), abs(d8))
        P('| %s | %s | %.1f | %s | %+.1f | %.1f | %s | %+.1f |'
          % (DISP[mm], arm, a4, h4[2] if h4 else '—', d4, a8, h8[2] if h8 else '—', d8))
chk('与两个历史件逐格差 ≤1.0 pp（24 格）', worst <= 1.0, '最大 |差| = %.1f pp' % worst)

# ── ④ 完整性 ─────────────────────────────────────────────────────────────
ns = sorted(set(nrows.values()))
chk('每个臂文件的行数一致（同一批样本）', len(ns) == 1, '行数取值集合 %s' % ns)
# ★ 我第一版把期望写成 299（来自 `wc -l sample_test_ids.txt`），实测是 **300**：
#   `wc -l` 数的是**换行符**，末行无换行时会少算一行 ⇒ 样本是 300 条，与探针 `--n 300` 一致。
#   这正是"用行数当规模"的老坑（同 2026-09-24 早先那次 `ls | wc -l` 误判文件数）⇒ 断言按实测 300 写死，
#   并把"样本规模"与"文件行数"两件事分开陈述。
chk('样本规模 = 300（探针 --n 300；与冻结面板同一批）', ns == [300], str(ns))

P('')
P('**独立重算：%d 项通过 ｜ %d 项失败**%s' % (ok, len(bad), '' if not bad else '（%s）' % '；'.join(bad[:5])))
io.open(OUT, 'w', encoding='utf-8', newline='\n').write('\n'.join(L) + '\n')

# ★ 把**独立重算得到的**数字冻结下来（而不是把分析器的输出转抄一遍）：
#   论文 M.41 将引用 48.8 / 12.4 / 0.3 / 0.4 / 36.4 / 4.6 / 最大历史差 这些值，
#   它们必须能在冻结件里查到 ⇒ 冻结这里，并让 `anchor_m40m41.py` 进取值宇宙。
import hashlib
freeze = dict(purpose='S1 服务栈对照的独立重算（绕开 ctxctrl_analyze.py 直读原始逐项 CSV）',
              method='raw-match 分类在本脚本内独立实现；每个 (构建×上下文×臂) 重算 3 次起服的弃权率',
              across={}, history={}, movers={}, sample_n=ns[0] if len(ns) == 1 else None)
# ★ 调用总数**由数据数出来**，不是手写的：文件数 × 每文件行数。
#   我此前在记录与 M.41 里手写"14,400 次调用"，被锚点门禁当场拦下（该数未登记）——真值见下。
freeze['n_arm_files'] = len(nrows)
freeze['total_calls'] = sum(nrows.values())
for (mm, ctx, arm), (mean, rge) in sorted(agg.items()):
    freeze['across']['%s|%s|%s' % (mm, ctx, arm)] = dict(mean=round(mean, 2), range_pp=round(rge, 2),
                                                         vals=live[(mm, ctx, arm)])
freeze['movers'] = {'%s|%s' % (x[0], x[1]): round(x[2], 2) for x in movers}
fre_hd = {}
for mm in TAG:
    for arm in ARMS:
        h4 = rate(os.path.join(FSC, 'frozen384', 'fsc_%s_%s.csv' % (mm, arm)))
        h8 = rate(os.path.join(FSC, '384', 'fsc_%s_%s.csv' % (mm, arm)))
        if h4:
            fre_hd['%s|%s|4096' % (mm, arm)] = dict(hist=h4[2], live=round(agg[(mm, '4096', arm)][0], 1),
                                                   diff=round(agg[(mm, '4096', arm)][0] - h4[2], 2))
        if h8:
            fre_hd['%s|%s|8192' % (mm, arm)] = dict(hist=h8[2], live=round(agg[(mm, '8192', arm)][0], 1),
                                                   diff=round(agg[(mm, '8192', arm)][0] - h8[2], 2))
freeze['history'] = fre_hd
freeze['history_max_abs_diff_pp'] = round(max(abs(v['diff']) for v in fre_hd.values()), 2)
freeze['key_cell'] = dict(build='Phi-3.5-vision-instruct', arm='enumAbstain',
                          mean_4096=round(m4, 2), range_4096_pp=round(r4, 2),
                          mean_8192=round(m8, 2), range_8192_pp=round(r8, 2),
                          delta_ctx_pp=round(d, 2),
                          verdict=('服务配置（上下文长度）可解释' if d > 4 * max(r4, r8) else '运行噪声可解释'))
freeze['max_within_context_range_pp'] = round(max(v[1] for v in agg.values()), 2)
FZ = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ctxctrl_indep_result.json')
io.open(FZ, 'w', encoding='utf-8', newline='\n').write(json.dumps(freeze, ensure_ascii=False, indent=2))
h = hashlib.md5(io.open(FZ, 'rb').read()).hexdigest()
io.open(FZ + '.md5', 'w', encoding='utf-8', newline='\n').write('%s  %s  (_ctxctrl_indep_check.py)\n'
                                                              % (h, os.path.basename(FZ)))
print('已冻结独立重算件 %s（md5 %s）' % (os.path.basename(FZ), h[:12]))
print('\n'.join(L[-24:]))
print('\n已写出 %s' % OUT)
print('独立重算：%d 通过 ｜ %d 失败' % (ok, len(bad)))
sys.exit(1 if bad else 0)
