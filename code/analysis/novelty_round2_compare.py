# -*- coding: utf-8 -*-
"""[round]vs [round]新颖度[external-review]对比（**同一把尺子、材料不同**）。

三件事：
  ① 分数对比：逐模型 + 聚合（min/median/mean）+ 档位（50/75 边界）；
  ② [round]意见的**主题归并**（关键词自动打标，标出"需人工确认"的条目）；
  ③ ★ **跨轮主题存活**：[round]的主题在[round]是否仍被提及——这才是"改稿是否落地"的判据，
     并列出**[round]新出现**的意见（= 下一轮的工作项）。
判据口径（先写死）：
  · 某主题"已落地" = [round]**没有任何**模型再就它提出意见；
  · 分数比较只在**同模型**之间做（跨模型可比≠有效），聚合值仅作参考。
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
import io
import json
import os
import statistics as st
import sys

sys.stdout.reconfigure(encoding='utf-8')
D = NR('analysis', 'model_review')
J1 = NR('analysis', 'model_review', 'novelty_paperB1_result.json')
J2 = NR('analysis', 'model_review', 'novelty_paperB2_result.json')

# 主题关键词（用于自动打标；只作初筛，最终以人工确认的映射为准）
THEME_KW = [
    ('A 证据范围', ['lineage', 'family', 'families', 'closed-source', 'proprietary', 'pre-regist',
                    'domain', 'corpus', 'scale of evidence', 'more models', 'generaliz']),
    ('B 机制被先行占位', ['prior work', 'already established', 'not novel mechanism', 'mechanism',
                          'reporting stage', 'fundamental']),
    ('C 契约门控', ['contract', 'abstention token', 'confound', 'engine', 'saturat', 'quadrant',
                    'input concept', 'single-variable']),
    ('D 方向/恒等式', ['identity', 'tautolog', 'definitional', 'no magnitude', 'negative result',
                       'spectrum', 'ordering']),
    ('E 可辨性代理', ['legibility', 'proxy', 'deployab', 'selector', 'annotation', 'diagnostic']),
    ('F 阶梯＝已知自由度', ['knob', 'ladder', 'grid density', 'detector threshold', 'known degree']),
]


def tag(reason):
    r = reason.lower()
    hits = [(name, sum(1 for k in kws if k in r)) for name, kws in THEME_KW]
    hits = [h for h in hits if h[1] > 0]
    hits.sort(key=lambda x: -x[1])
    if not hits:
        return '?（需人工归类）'
    if len(hits) > 1 and hits[0][1] == hits[1][1]:
        return '%s / %s（并列，需人工）' % (hits[0][0], hits[1][0])
    return hits[0][0]


d1 = json.load(io.open(J1, encoding='utf-8'))
print('=' * 100)
print('① 分数对比（同模型可比；聚合仅参考）')
print('=' * 100)
print('%-12s %10s %10s %8s   %s' % ('模型', '先前', '本次', 'Δ', '本次 0–10'))
rows2 = {}
if os.path.exists(J2):
    d2 = json.load(io.open(J2, encoding='utf-8'))
    rows2 = d2.get('models', {})
    for m in d1['models']:
        s1 = d1['models'][m]['score']
        r2 = rows2.get(m) or {}
        s2 = r2.get('score')
        print('%-12s %10s %10s %8s   %s'
              % (m, ('%.1f' % s1) if s1 is not None else '—',
                 ('%.1f' % s2) if s2 is not None else '—',
                 ('%+.1f' % (s2 - s1)) if (s1 is not None and s2 is not None) else '—',
                 r2.get('score_10', '—')))
    a1 = [v['score'] for v in d1['models'].values() if v['score'] is not None]
    a2 = [v['score'] for v in rows2.values() if v.get('score') is not None]
    if a1 and a2:
        f = lambda a: (min(a), st.median(a), sum(a) / len(a))
        m1, m2 = f(a1), f(a2)
        print('%-12s %10s %10s %8s' % ('min', '%.1f' % m1[0], '%.1f' % m2[0], '%+.1f' % (m2[0] - m1[0])))
        print('%-12s %10s %10s %8s' % ('median', '%.1f' % m1[1], '%.1f' % m2[1], '%+.1f' % (m2[1] - m1[1])))
        print('%-12s %10s %10s %8s' % ('mean', '%.1f' % m1[2], '%.1f' % m2[2], '%+.1f' % (m2[2] - m1[2])))
        print('档位：第1轮 min %.1f、第2轮 min %.1f（50–74 档下限 50；75 档下限 75）' % (m1[0], m2[0]))
else:
    print('（第 2 轮结果 JSON 尚未生成：%s）' % J2)

print()
print('=' * 100)
print('② 本次意见逐条（自动主题打标，需人工确认）')
print('=' * 100)
tot2 = 0.0
n2 = 0
for m, rec in rows2.items():
    for it in rec.get('deductions', []):
        tot2 += it['pts']
        n2 += 1
        print('%-11s %6.1f %-10s %-18s %s'
              % (m, it['pts'], it['cls'], tag(it['reason']), it['reason'][:80].replace('\n', ' ')))
print('本次合计 −%.1f（%d 条）；先前合计 −%.1f（23 条）' % (tot2, n2, sum(100 - r['score'] for r in d1['models'].values())))

print()
print('=' * 100)
print('③ 跨轮主题存活（先前主题是否仍被提及）')
print('=' * 100)
if rows2:
    themes2 = {}
    for m, rec in rows2.items():
        for it in rec.get('deductions', []):
            t = tag(it['reason'])
            themes2.setdefault(t, []).append((m, it['pts']))
    for t in sorted(themes2, key=lambda x: -sum(p for _, p in themes2[x])):
        v = themes2[t]
        print('  %-22s 仍被扣：%d 条 / −%.1f（%s）'
              % (t, len(v), sum(p for _, p in v), ', '.join('%s %.1f' % x for x in v)))
    print()
    print('  判据：某主题在本次**无任何**意见 ⇒ 记为"已落地"。')
