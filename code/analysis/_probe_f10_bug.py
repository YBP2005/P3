# -*- coding: utf-8 -*-
"""_probe_f10_bug.py —— 先说清 F.10 的口径混用 bug 到底是什么、影响多大（不改任何冻结件）。

背景：`span_equalcount.py` 的 ① 段从 `threeway_curves_v2.csv` 取 ρ 建"检测 τ"阶梯时**没有过滤 `match`**，
而该 CSV 里**同一 (paradigm, knob, setting) 有两种口径的 ρ**（person / allclass）⇒ 阶梯实际是
**两种口径交错**，于是：
  · "档数"被算成 2 倍（域内 16、COCO 32，真值应为 8、16）；
  · "全长跨度"= max(allclass) − min(person)，**跨口径相减**；
  · 等点数子采样 / 去端点也都作用在交错序列上 ⇒ F.10 的 6 个检测行与 τ 缩小倍率全部受污染。

本探针把同一套阶梯**按口径拆开重算**，给出两张对照表（口径混用 vs 各自口径）。
"""
import csv, io, json, os, sys, collections
sys.stdout.reconfigure(encoding='utf-8')
DATA = r'<WORKDIR>\PaperB\analysis\data'
WORK = r'<WORKDIR>\PaperB\analysis\work'
ROWS = list(csv.DictReader(io.open(os.path.join(DATA, 'threeway_curves_v2.csv'), encoding='utf-8-sig')))


def span(seq):
    v = [x[1] for x in seq]
    return max(v) - min(v)


def equalize(seq, k):
    n = len(seq)
    if n <= k:
        return seq
    idx = sorted(set(int(round(i * (n - 1) / float(k - 1))) for i in range(k)))
    return [seq[i] for i in idx]


def ladders(caliber=None):
    out = collections.defaultdict(list)
    for r in ROWS:
        if caliber and r.get('match') != caliber:
            continue
        try:
            out[(r['paradigm'], r['knob'])].append((float(r['setting']), float(r['rho'])))
        except (TypeError, ValueError):
            pass
    for k in out:
        # ★ 必须**只按 setting 排**（稳定排序，同 τ 内保持 CSV 原序）——与原脚本逐字一致。
        #   我第一版写成 `out[k].sort()`（按 (setting, rho) 元组排），同 τ 内按 ρ 重排，
        #   于是等点数子采样取到的是**另一批下标**，复算不出冻结值 35.60 —— 复现失败正是这一处。
        out[k].sort(key=lambda x: x[0])
    return out


KMIX = ladders(None)
KP = ladders('person')
KA = ladders('allclass')
fz = {x['unit']: x for x in json.load(io.open(os.path.join(WORK, 'span_equalcount_result.json'),
                                              encoding='utf-8'))['units']}

print('%-34s %5s %5s %5s | %9s %9s | %9s %9s | %9s %9s' % (
    '单元', '混档', 'person', 'allclass', '混-全长', '冻结值', 'P-全长', 'P-等k(4)', 'A-全长', 'A-等k(4)'))
for k in sorted(KMIX):
    unit = '%s / VisDrone / %s' % (k[0], k[1])
    mix = KMIX[k]
    p, a = KP.get(k, []), KA.get(k, [])
    print('%-34s %5d %5d %5d | %9.1f %9.1f | %9.1f %9.1f | %9.1f %9.1f' % (
        unit, len(mix), len(p), len(a), span(mix), fz[unit]['span'],
        span(p), span(equalize(p, 4)), span(a), span(equalize(a, 4))))

print('\n=== τ 单元"等点数缩小倍率"（F.10/§7.3 那句 2.2–2.3× / 5–10× 的出处）===')
for tag, key in (('口径混用（冻结版）', None), ('person-matched', 'person'), ('allclass', 'allclass')):
    L = ladders(key)
    inn = [span(L[k]) / span(equalize(L[k], 4)) for k in L if '域内' in k[0]]
    coco = [span(L[k]) / span(equalize(L[k], 4)) for k in L if 'COCO' in k[0]]
    print('  %-18s 域内 %.2f–%.2f ｜ COCO %.2f–%.2f' % (tag, min(inn), max(inn), min(coco), max(coco)))
print('  （稿内现写：域内 2.2–2.3×、COCO 5–10×）')
