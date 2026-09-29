# -*- coding: utf-8 -*-
"""p1f_make.py —— 锚定阶梯（改版方案 B）：把"被提及的值"做成一条曲线 + 事前写死解释规则。

动机（P1d/P1e 已测）：
  Phi-3.5：base 13.5% → neutral0（提 0）**100%** → placebo100（提 100）**0%**
  Qwen3-VL-8B：9.9% → 78.7% → 0.0%
  Qwen3-VL-32B：15.4% → 63.7% → 0.0%
  两个提示词只差被提及的那个数字，零率摆动可达 100 pp ⇒ 提示词里"点名的值"像是被抄走了。

本件做**阶梯**：把被提及的值铺成 {0, 5, 50, 100, 800}（全部为"允许"句式，只有数字在变），
  其中 0（=neutral0）与 100（=placebo100）**已有**，只需新增 **5 / 50 / 800** 三臂。
模板（逐字节固定，只有数字位可变）：
  注意：**可能是 V**；如果你的判断确实是 V，请照实回答 V。

事前写死的判据（在做任何阶梯计算之前）：
  H_L1 **零率随锚递减**：zero_rate 对被提及值 {0,5,50,100,800} 的 Spearman ρ ≤ **−0.8**（每族）。
       理由：锚越远离 0，模型越不该答 0。
  H_L2 **捕获**：`rate(答案 == v | 提及 v) ≥ rate(答案 == v | 提及 v')` 对 v' ∈ {相邻锚} 成立。
       即被提及的那个值自己应当是被捕获得最厉害的一个。
  H_L3 **整条答案分布随锚平移**：答案的**中位数**对被提及值的 Spearman ρ ≥ **+0.8**（每族）。
       若成立，"锚定"不只是零率的局部现象，而是整条输出被拉走。
  H_L4（阴性对照）**gemma3-12b**（该族在本网格上 base 零率恒 0）应几乎不动 ⇒
       锚定效应需要"该族本来就会答 0"这个前提；若 gemma 也被拉动，说明锚定更强、需改口径。
"""
import hashlib
import io
import json
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')
W = os.path.dirname(os.path.abspath(__file__))
D_SRC = os.path.join(W, 'p1d_prompts.json')
OUT = os.path.join(W, 'p1f_prompts.json')
CRIT = os.path.join(W, 'p1f_criteria_frozen.json')
TMPL = '注意：**可能是 %s**；如果你的判断确实是 %s，请照实回答 %s。'


def md5_12(p):
    return hashlib.md5(io.open(p, 'rb').read()).hexdigest()[:12]


d = json.loads(io.open(D_SRC, encoding='utf-8').read())
neutral0 = d['arms']['neutral0']
OLD = TMPL % ('0', '0', '0')
if OLD not in neutral0:
    raise SystemExit('!! neutral0 尾段与模板不符：%r' % neutral0[-90:])

arms = {}
for v in ('5', '50', '800'):
    a = neutral0.replace(OLD, TMPL % (v, v, v))
    if neutral0.replace(OLD, '\x00') != a.replace(TMPL % (v, v, v), '\x00'):
        raise SystemExit('!! mention%s 与 neutral0 除数字外还有差异 —— 拒绝（必须单变量）' % v)
    arms['mention' + v] = a

doc = {
    'why': 'P1d/P1e 显示被提及的值被"抄走"（Phi：提 0 → 100% 零率；提 100 → 0%）⇒ 做成阶梯量化',
    'source': os.path.basename(D_SRC), 'source_md5': hashlib.md5(io.open(D_SRC, 'rb').read()).hexdigest(),
    'template': TMPL, 'arms': arms,
    'ladder_reuse': {'0': 'neutral0（已测，在 p1d_prompts.json）', '100': 'placebo100（已测，在 p1e_prompts.json）'},
    'single_variable_check': '三臂与 neutral0 仅被提及的数字不同（生成时逐个断言）',
}
io.open(OUT, 'w', encoding='utf-8', newline='\n').write(json.dumps(doc, ensure_ascii=False, indent=1) + '\n')

crit = {
    'version': 'p1f-v1',
    'ladder': [0, 5, 50, 100, 800],
    'arms_new': sorted(arms), 'arms_reused': ['neutral0(anchor=0)', 'placebo100(anchor=100)'],
    'families': ['Phi-3.5-vision-instruct', 'Qwen3-VL-8B-Instruct', 'llava-onevision-qwen2-7b-ov',
                 'gemma3-12b'],
    'H_L1': dict(metric='zero_rate vs anchor', stat='spearman', rho_max=-0.8,
                 rule='zero_rate 随锚递减：ρ ≤ -0.8（每族，5 个锚点）'),
    'H_L2': dict(metric='rate(answer == v | mention v)', rule='被提及值自身被捕获最多（≥ 相邻锚）'),
    'H_L3': dict(metric='median(answer) vs anchor', stat='spearman', rho_min=0.8,
                 rule='整条答案分布随锚平移：ρ ≥ +0.8（每族）'),
    'H_L4': dict(family='gemma3-12b', rule='阴性对照：该族 base 零率恒 0，预期几乎不动；若被拉动需改口径'),
    'analysis_note': '台阶只有 5 点，Spearman 的 p 值不具说服力 ⇒ 只报 ρ 与逐点率，不做显著性宣称',
    'honesty': [
        '阶梯设计在看过 0 与 100 两点之后 ⇒ 属**探索性**延伸，不当作预注册验证',
        '四族并非都跑全阶梯：gemma 作阴性对照，llava 含解析失败需单独处理',
    ],
}
io.open(CRIT, 'w', encoding='utf-8', newline='\n').write(json.dumps(crit, ensure_ascii=False, indent=1) + '\n')

print('=== p1f 锚定阶梯冻结链 ===')
print('  p1d_prompts.json md5-12 = %s' % md5_12(D_SRC))
print('  p1f_prompts.json md5-12 = %s' % md5_12(OUT))
print('  p1f_prompts.json FULL   = %s' % hashlib.md5(io.open(OUT, 'rb').read()).hexdigest())
print('  p1f_criteria_frozen md5-12 = %s' % md5_12(CRIT))
for k, v in arms.items():
    print('  [%s] %s' % (k, v))
print('  单变量断言：三臂逐个通过')
