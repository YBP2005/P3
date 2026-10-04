# -*- coding: utf-8 -*-
"""theme_decompose.py — 把新颖度在册条目的 D1 意见**按主题**分解，用于跨轮对比。

为什么要有这个脚本：上一版的主题表是人工目测归类出来的，跨轮再目测一次就会得到
"看起来在缩小的主题"——这正是本项目已经吃过一次的亏（自证式比较）。所以这里把
分类口径**写成显式关键词规则**，对第 4、5 两轮**同一份代码**执行，并且：
  · 每条意见都必须被归类；无法归类 → UNCLASSIFIED 并显式报出（不静默丢弃）；
  · 命中多个主题时按**优先级顺序**取唯一归属，并把命中的关键词一起打印，便于人工复核；
  · 主题总额必须等于 D1 意见总额（脚本内 assert）。

主题定义（与上一版记录中的 A–F 同名，但口径以本文件为准）：
  D_IDENTITIES   命题/对偶口径"只是算术恒等式、只是记账"——即 D 主题
  F_SPECTRUM_NEG 方向谱/量级律撤回/机制未解释/阴性结果——即 F 主题
  E_PROXY        可见性代理、无标注替代、检测框不可恢复
  A_COVERAGE     语料谱系单一、缺闭源/少样本族、构建特异性（外推性问题）
  C_RELABEL      "已知现象的重分解/近同义反复/提示消融"（不含"只是算术"）
  B_INCREMENT    未给出新的计数专门机理/原理（与 E、C 都不重叠时）
用法：python theme_decompose.py R4 R5   （参数为轮次号，读 novelty_paperB<n>_result.json）
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
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')
D = NR('analysis', 'model_review')
MODELS = ['dsflash', 'dspro', 'grok46', 'glm53flash']

# 顺序即优先级：越具体的主题越靠前。
# ★ 2026-09-23 修正（本轮自查抓到，必须记下来）：原先把 D_IDENTITIES 排在 F 之前，
#   结果 在册条目上一版那条 在册条目（原文 "Directional-span spectrum is implementation×domain×protocol,
#   with magnitude law withdrawn (Prop. 3) … Would need a portable predictor of span size"）
#   因为句中出现了 "(Prop. 3)" 而被归到 D，**掩盖了"谱系投诉仍在"这一事实**，
#   从而把"F 主题下降"算得过大（−28.0 → −15.0）。这类"分类器优先级制造出来的结论"
#   正是本项目要防的自证。现在：F 先于 D；并且对每条意见**同时报告全部命中主题**（见 also 列），
#   主归属只用于求和，重叠情况一律显式打印。
THEMES = [
    ('F_SPECTRUM_NEG', r'spectrum|magnitude law|negative result|knob|threshold|NMS|'
                       r'mechanis|descriptive|operating[- ]point|scale ladder|predictor of span'),
    ('D_IDENTITIES', r'proposition|\bprop\.|identit|arithmetic|bookkeeping|tautolog|'
                     r'pooled[- ]vs[- ]per[- ]image|pooling'),
    ('E_PROXY', r'legibilit|proxy|median[- ]visible|annotation[- ]free|annotation box|'
                r'detector box|AUC 0\.4|visible[- ]pixel'),
    ('A_COVERAGE', r'lineage|corpus|proprietar|few[- ]shot|closed[- ]model|population|'
                   r'build-specific|family|coverage|generalise across|beyond the measured'),
    ('C_RELABEL', r're-?decomposition|re-?decompos|near[- ]tautological|already known|'
                  r'already observe|prompt[- ]ablation|selective prediction|instruction[- ]following|'
                  r'imported|reuses? ideas|echo established'),
    ('B_INCREMENT', r'no new underlying mechanism|not distinguishable|'
                    r'new counting-specific principle|no new .{0,20}principle|algorithmic principle'),
]
NAMES = {
    'D_IDENTITIES': 'D 对偶口径/命题=算术恒等式',
    'F_SPECTRUM_NEG': 'F 方向谱/量级律/机制未解释',
    'E_PROXY': 'E 可见性代理与无标注替代',
    'A_COVERAGE': 'A 语料谱系与外推范围',
    'C_RELABEL': 'C 已知现象的重分解/近同义反复',
    'B_INCREMENT': 'B 无计数专门新机理',
    'UNCLASSIFIED': '未归类（需人工指定）',
}


def classify(text):
    """返回 (主归属, 主命中词, 其余命中主题列表)。主归属用于求和；其余命中一并报出。"""
    t = text.lower()
    hits = [(name, re.search(pat, t)) for name, pat in THEMES]
    hits = [(n, m) for n, m in hits if m]
    if not hits:
        return 'UNCLASSIFIED', '', []
    return hits[0][0], hits[0][1].group(0), [n for n, _ in hits[1:]]


def load(round_tag):
    tag = round_tag[1:] if round_tag.upper().startswith('R') else round_tag
    p = os.path.join(NR('analysis', 'model_review'), 'novelty_paperB%s_result.json' % tag)
    with io.open(p, encoding='utf-8') as f:
        return json.load(f)


report = {}
for tag in sys.argv[1:]:
    d = load(tag)
    per = {k: {'pts': 0.0, 'items': 0, 'models': set()} for k in NAMES}
    detail = []
    total = 0.0
    for m in MODELS:
        r = d['models'].get(m)
        if not r:
            continue
        for x in r['deductions']:
            theme, hit, also = classify(x['reason'])
            per[theme]['pts'] += x['pts']
            per[theme]['items'] += 1
            per[theme]['models'].add(m)
            total += x['pts']
            detail.append((m, theme, x['pts'], hit, x['cls'], x['reason'], also))
    report[tag] = dict(per=per, total=round(total, 1), detail=detail, scores=d.get('scores'))
    # 总额校验：主题合计必须等于 D1 总额（否则说明有意见未被计入）
    s = round(sum(v['pts'] for v in per.values()), 1)
    assert abs(s - total) < 1e-6, '%s 主题合计 %.1f ≠ D1 总额 %.1f' % (tag, s, total)

print('## 主题分解（同一分类器机械套用；每条意见必有归属）')
print()
order = [k for k in NAMES if k != 'UNCLASSIFIED'] + ['UNCLASSIFIED']
print('### 口径一：**模型层面覆盖率**（任一主题命中即计入，多标签 ∪ —— 对优先级稳健，推荐用于结论）')
print()
print('| 主题 | %s | %s | Δ 家数 |' % tuple('**%s**' % t for t in sys.argv[1:]))
print('|---|---|---|---|')
union = {}
for tag in sys.argv[1:]:
    u = {k: {'models': set(), 'items': 0, 'pts': 0.0} for k in NAMES}
    for m, theme, pts, hit, cls, reason, also in report[tag]['detail']:
        for k in [theme] + also:
            u[k]['models'].add(m)
            u[k]['items'] += 1
            u[k]['pts'] += pts
    union[tag] = u
for k in order:
    cells = []
    for tag in sys.argv[1:]:
        v = union[tag][k]
        cells.append('**%d/4 家**（%d 条，−%.1f）' % (len(v['models']), v['items'], round(v['pts'], 1)))
    if len(sys.argv) == 3:
        a = len(union[sys.argv[1]][k]['models'])
        b = len(union[sys.argv[2]][k]['models'])
        dl = ('**%+d 家**' % (b - a)) if a != b else ('0 家（仍 %d/4）' % b)
    else:
        dl = '—'
    print('| %s | %s | %s | %s |' % (NAMES[k], cells[0], cells[1] if len(cells) > 1 else '—', dl))
print()
print('（口径一的分数列会**互相重叠**，不可相加；只有"家数"列是干净的。'
      '要加总请用口径二。）')
print()
print('### 口径二：**单标签总额**（主归属求和，可与 D1 总额对齐；重叠条目按优先级归一方 ⇒ 依赖优先级顺序）')
print()
print('| 主题 | %s | %s | Δ |' % tuple('**%s**' % t for t in sys.argv[1:]))
print('|---|---|---|---|')
order = [k for k in NAMES if k != 'UNCLASSIFIED'] + ['UNCLASSIFIED']
uncls = []
for k in order:
    cells = []
    for tag in sys.argv[1:]:
        v = report[tag]['per'][k]
        cells.append('−%.1f（%d 条，%d/4 模型）' % (round(v['pts'], 1), v['items'], len(v['models'])))
        if k == 'UNCLASSIFIED' and v['items']:
            uncls += [(tag, x) for x in report[tag]['detail'] if x[1] == 'UNCLASSIFIED']
    if len(sys.argv) == 3:
        a = report[sys.argv[1]]['per'][k]['pts']
        b = report[sys.argv[2]]['per'][k]['pts']
        dl = '**%+.1f**' % (b - a)
    else:
        dl = '—'
    print('| %s | %s | %s | %s |' % (NAMES[k], cells[0], cells[1] if len(cells) > 1 else '—', dl))
print('| **合计** | %s | %s | %s |'
      % ('−%.1f' % report[sys.argv[1]]['total'],
         '−%.1f' % report[sys.argv[2]]['total'] if len(sys.argv) > 2 else '—',
         '**%+.1f**' % (report[sys.argv[2]]['total'] - report[sys.argv[1]]['total']) if len(sys.argv) > 2 else '—'))
print()
if uncls:
    print('**未归类条目（需人工指定，未被静默丢弃）**')
    for tag, (m, theme, pts, hit, cls, reason, also) in uncls:
        print('- `%s`/`%s` −%.1f [%s]：%s' % (tag, m, pts, cls, reason[:160]))
else:
    print('未归类条目：0 条（全部意见均已归属主题）。')
print()
overlap = [(tag, x) for tag in sys.argv[1:] for x in report[tag]['detail'] if x[6]]
print('**同时命中多个主题的条目（主归属只用于求和，重叠在此显式列出，共 %d 条）**' % len(overlap))
if not overlap:
    print('- 无。')
for tag, (m, theme, pts, hit, cls, reason, also) in overlap:
    print('- `%s`/`%s` −%.1f：主 **%s**（命中 `%s`），另命中 %s'
          % (tag, m, pts, theme, hit, '/'.join(also)))
print()
print('**逐条归属（含命中关键词，便于人工复核）**')
for tag in sys.argv[1:]:
    print()
    print('### %s（分数 %s；D1 总额 −%.1f）'
          % (tag, '/'.join('%.1f' % s for s in (report[tag]['scores'] or [])), report[tag]['total']))
    for m, theme, pts, hit, cls, reason, also in report[tag]['detail']:
        tail = ('（另命中 %s）' % '/'.join(also)) if also else ''
        print('- `%s` −%.1f [%s] → **%s**（命中 `%s`）%s'
              % (m, pts, cls, theme, hit, tail))
