# -*- coding: utf-8 -*-
"""p1e_make.py —— 生成 **placebo100 探索臂** 的提示词 + 其（事前写死的）解释规则。

动机（来自 P1d 的中期读数，3 族已完成 base/forbid0/neutral0）：
  | family          | base  | forbid0 | neutral0 |
  | Qwen3-VL-32B    | 15.4% |  3.7% ↓ |  63.7% ↑↑ |
  | Qwen3-VL-8B     |  9.9% | 13.9% ↑ |  78.7% ↑↑ |
  ⇒ 「**提及 0 但允许**」把零率抬高 48–69 pp，而「**禁止 0**」的符号随血统变。
  ⇒ 需要区分两种解释：
     (i) **token 特异**：是"0"这个 token 被点亮（禁与不禁都只是次级调制）；
     (ii) **非特异**：任何"提到一个可能取值"的句子都会把模型推向给数（0 只是其中一支）。

placebo100 的构造（**单变量**）：把 neutral0 里被提及的数字从 `0` 换成 `100`，其余逐字节不动。
  neutral0 尾段：注意：**可能是 0**；如果你的判断确实是 0，请照实回答 0。
  placebo100尾段：注意：**可能是 100**；如果你的判断确实是 100，请照实回答 100。

**事前写死的解释规则**（在做任何 placebo 计算之前写进 p1e_criteria_frozen.json）：
  * 若 |Δzero(placebo100 − base)| ≤ 0.3 × |Δzero(neutral0 − base)|  ⇒ **token 特异**成立；
  * 若 ≥ 0.7 × ⇒ **非特异**成立（"提到一个取值"本身就够）；
  * 中间 ⇒ 部分特异，按实报；
  * 另报 Δ(答 100 的比例)：若非特异，"被推向的那个数"应随被提及的数而变。
  * 本块是**探索性**（第 4 条判据之外），**不得**用来改动 P1d 主判据的任何结论。
"""
import hashlib
import io
import json
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')
W = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(W, 'p1d_prompts.json')
OUT = os.path.join(W, 'p1e_prompts.json')
CRIT = os.path.join(W, 'p1e_criteria_frozen.json')


def md5_12(p):
    return hashlib.md5(io.open(p, 'rb').read()).hexdigest()[:12]


d = json.loads(io.open(SRC, encoding='utf-8').read())
neutral0 = d['arms']['neutral0']
OLD = '注意：**可能是 0**；如果你的判断确实是 0，请照实回答 0。'
NEW = '注意：**可能是 100**；如果你的判断确实是 100，请照实回答 100。'
if OLD not in neutral0:
    raise SystemExit('!! neutral0 的尾段与预期不符：%r' % neutral0[-80:])
placebo100 = neutral0.replace(OLD, NEW)
if neutral0.replace(OLD, '\x00') != placebo100.replace(NEW, '\x00'):
    raise SystemExit('!! placebo100 与 neutral0 除目标子句外还有差异 —— 拒绝（必须单变量）')

doc = {
    'why': 'P1d 中期读数显示 neutral0 大幅抬高零率、forbid0 符号随血统变 ⇒ 需区分 token 特异 vs 非特异',
    'source': os.path.basename(SRC),
    'source_md5': hashlib.md5(io.open(SRC, 'rb').read()).hexdigest(),
    'arms': {'placebo100': placebo100},
    'single_variable_check': 'placebo100 与 neutral0 仅被提及的数字不同（0 → 100），生成时已断言',
}
io.open(OUT, 'w', encoding='utf-8', newline='\n').write(
    json.dumps(doc, ensure_ascii=False, indent=1) + '\n')

crit = {
    'version': 'p1e-v1-exploratory',
    'status': '探索性（P1d 主判据之外）；不得用于修改 P1d 的任何结论',
    'arm': 'placebo100（= neutral0 把被提及的数字 0 换成 100，其余逐字节相同）',
    'reference': 'neutral0 与 base 的对比取 P1d 同会话产物（p1d_<family>_neutral0.csv / _base.csv）',
    'metrics': ['zero_rate', 'rate_of_answer_100'],
    'token_specific_if': '|Δzero(placebo100-base)| ≤ 0.3 × |Δzero(neutral0-base)|',
    'nonspecific_if': '|Δzero(placebo100-base)| ≥ 0.7 × |Δzero(neutral0-base)|',
    'else': '部分特异，按实报',
    'extra_prediction': '若非特异，placebo100 应把"被推向的数"改为 100（Δ答100 显著为正）',
    'n_perm': 0,
    'honesty': [
        '本块在看过 P1d 三族中期读数**之后**才设计 ⇒ 必须标为探索性，不能当作预注册验证',
        '只跑 P1d 里 neutral0 效应最大的家族，避免全量开销；结论只覆盖这些家族',
    ],
}
io.open(CRIT, 'w', encoding='utf-8', newline='\n').write(
    json.dumps(crit, ensure_ascii=False, indent=1) + '\n')

print('=== p1e（探索性）冻结链 ===')
print('  p1d_prompts.json md5-12 = %s' % md5_12(SRC))
print('  p1e_prompts.json md5-12 = %s' % md5_12(OUT))
print('  p1e_prompts.json FULL   = %s' % hashlib.md5(io.open(OUT, 'rb').read()).hexdigest())
print('  p1e_criteria_frozen md5-12 = %s' % md5_12(CRIT))
print('  [placebo100] %s' % placebo100)
print('  单变量断言：通过')
