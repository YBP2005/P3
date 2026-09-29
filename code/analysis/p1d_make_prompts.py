# -*- coding: utf-8 -*-
"""p1d_make_prompts.py —— 生成 P1 新增臂（`forbid0` / `neutral0`）的**人版**提示词冻结件。

为什么单独做一份、而不是直接改 `p1_probe.py`：
  `p1_probe.py` 是产出**已发表** §M.19.10 `base`/`permit` 结果的仪器，改它会让"这些脚本复现这些结果"
  这句话失效。所以新臂另起 `p1d_*`：老仪器一个字节不动。

链条（本脚本打印，记录在案）：
  ① `probe_gen.py` 的 md5 —— `forbid0` 的**唯一权威来源**（不手工转录，直接 import 取值）
  ② 本脚本产出的 `p1d_prompts.json` 的 md5 —— 新仪器启动时断言它
  ③ 圆点版只改**对象名词**：第一个句号之前的 `人数（人群中的每个人头或人体）` →
     `圆形数量（画面中的每一个圆点）`，**句号之后必须逐字节相同**（在 `p1d_probe.py` 里断言）

`neutral0` 是本研究新增的**诊断臂**，设计目的是把"禁止"与"提示词里出现 0 这个 token"分开：
  base      ：不提 0，不禁止
  neutral0  ：提到 0，且**允许**答 0
  forbid0   ：提到 0，且**禁止**答 0
  ⇒ `neutral0 − base` = 提及 0（带许可）的效应；`forbid0 − neutral0` = 在同样提及 0 的前提下，
    "禁止"这个动作本身的效应。三者共享同一 TASK/ENUM/FORMAT 骨架。
"""
import hashlib
import importlib.util
import io
import json
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')
W = os.path.dirname(os.path.abspath(__file__))
PAPER = os.path.dirname(os.path.dirname(W))
GEN = os.path.join(PAPER, 'analysis', 'pod_evidence', 'scripts', 'probe_gen.py')
OUT = os.path.join(W, 'p1d_prompts.json')

# probe_gen.py 的 md5 在首次生成时打印；这里不写死期望值（同一文件在不同副本里可能有换行差异），
# 但**必须**把实测值写进记录，且 p1d_probe.py 会断言 JSON 的 md5。
spec = importlib.util.spec_from_file_location('pg', GEN)
m = importlib.util.module_from_spec(spec)
os.environ.setdefault('PROBE_OUT', os.path.join(W, '_p1d_tmp'))
spec.loader.exec_module(m)
PG_MD5 = hashlib.md5(io.open(GEN, 'rb').read()).hexdigest()

forbid0 = m.PROMPTS['forbid0']

# neutral0：把 forbid0 的"禁止"子句换成"许可"子句，**其余逐字不动**。
#   原 forbid0 尾段：注意：**不要回答 0**；如果你认为可能是 0，请给出你最接近的估计值。
#   neutral0 尾段 ：注意：**可能是 0**；如果你的判断确实是 0，请照实回答 0。
OLD = '注意：**不要回答 0**；如果你认为可能是 0，请给出你最接近的估计值。'
NEW = '注意：**可能是 0**；如果你的判断确实是 0，请照实回答 0。'
if OLD not in forbid0:
    raise SystemExit('!! forbid0 的尾段与预期不符，probe_gen.py 可能已变：%r' % forbid0[-80:])
neutral0 = forbid0.replace(OLD, NEW)
if neutral0 == forbid0 or len(neutral0) == 0:
    raise SystemExit('!! neutral0 替换失败')
# 断言：除该子句外，neutral0 与 forbid0 的其余部分完全相同
a = forbid0.replace(OLD, '\x00')
b = neutral0.replace(NEW, '\x00')
if a != b:
    raise SystemExit('!! neutral0 与 forbid0 除目标子句外还有差异 —— 拒绝（必须单变量）')

doc = {
    'why': 'P1 新增臂（forbid0 / neutral0）的人版提示词；圆点版由 p1d_probe.py 按"只改对象名词"生成',
    'source_probe_gen': GEN.replace(PAPER, '.'),
    'source_probe_gen_md5': PG_MD5,
    'arms': {'forbid0': forbid0, 'neutral0': neutral0},
    'single_variable_check': 'neutral0 与 forbid0 仅目标子句不同（生成时已断言）',
}
io.open(OUT, 'w', encoding='utf-8', newline='\n').write(
    json.dumps(doc, ensure_ascii=False, indent=1) + '\n')
json_md5 = hashlib.md5(io.open(OUT, 'rb').read()).hexdigest()

print('=== p1d 提示词冻结链条 ===')
print('  ① probe_gen.py md5      = %s' % PG_MD5)
print('  ② p1d_prompts.json md5  = %s' % json_md5)
print()
for k in ('forbid0', 'neutral0'):
    print('  [%s] %s' % (k, doc['arms'][k]))
print()
print('  forge: forbid0 与 neutral0 的其余部分逐字相同 —— 已断言通过')
print('  已写 %s' % OUT)
