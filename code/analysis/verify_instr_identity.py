# -*- coding: utf-8 -*-
"""verify_instr_identity.py — 核验 PaperB 新颖度各轮材料包的**评分指令段逐字一致**。

背景（必须写清楚，因为这里曾经差点出错）：
  各轮材料包开头那块 6,836 字符的文本里，**只有 `**Integrity.**` 一行**逐轮不同
  （它记录本轮 manuscript / supplementary 的 md5 和包自身声明），其余**评分相关文本逐字复用**。
  因此整块的 md5 逐轮不同（v1/r2 `6a1c58340206` → r3 `443c5ca5e61e` → r4 `ac12aa5a8962`
  → r5 `84f04400ef6e`），但这**不代表**评分口径变了——若只看整块 md5 就下结论，会得出
  "跨轮不可比"的错误结论；反之若手打一句"指令段逐字复用"而不核验，就是不可溯源的断言。
  本脚本把这件事变成**可核验的事实**：剥离 Integrity 行后逐包比对。

另注：六模型通用评审用的指令段是另一块 5,349 字符（md5 `d4002a4a53d9`），
      PaperB 各包在 Integrity 行里引用的正是这个值；本脚本会核对该自报值。
输出：各包剥离后字符数/md5，以及"是否全部一致"的判定；不一致则 exit 1。
"""
import hashlib
import io
import os
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')
R = r'<WORKDIR>\analysis\model_review'
MK_A = '【NOVELTY-ONLY FAST REVIEW'
MK_B = '===== 【Manuscript'
PACKS = [
    ('v1/r2', 'm4prime_novelty_paperB_v1.md'),
    ('r2', 'm4prime_novelty_paperB_r2_20260922.md'),
    ('r3', 'm4prime_novelty_paperB_r3_20260923.md'),
    ('r4', 'm4prime_novelty_paperB_r4_20260923.md'),
    ('r5', 'm4prime_novelty_paperB_r5_20260923.md'),
    # ★ 2026-09-23 第 6 轮（加入 §5.14/M.31 与 §1/§8.2 修正后的材料包）
    ('r6', 'm4prime_novelty_paperB_r6_20260923.md'),
    # ★ 2026-09-23 第 7/8 轮（框架 A/B；加入 M.35 回顾性重算）——补入以把
    #   "指令段逐字一致"的可核验范围延伸到最新一轮
    ('r7', 'm4prime_novelty_paperB_r7_20260923.md'),
    ('r8', 'm4prime_novelty_paperB_r8_20260923.md'),
]
REF_6MODEL = 'd4002a4a53d9'

seen = {}
bad = []
for tag, name in PACKS:
    p = os.path.join(R, name)
    t = io.open(p, encoding='utf-8').read()
    a, b = t.find(MK_A), t.find(MK_B)
    if a < 0 or b <= a:
        bad.append('%s 未找到指令段标记' % name)
        continue
    seg = t[a:b]
    stripped = '\n'.join(l for l in seg.splitlines() if not l.startswith('**Integrity.**'))
    h = hashlib.md5(stripped.encode('utf-8')).hexdigest()
    m = re.search(r'scoring instruction md5\s+[\x60\x27"]?([0-9a-f]{12})', seg)
    claim = m.group(1) if m else 'n/a'
    ok_claim = (claim == REF_6MODEL)
    print('%-6s %-46s 整块 %5d | 剥离 Integrity 后 %5d 字符 md5 %s | 自报六模型指令段 %s %s'
          % (tag, name, len(seg), len(stripped), h[:12], claim, '✓' if ok_claim else '✗'))
    if not ok_claim:
        bad.append('%s Integrity 自报的指令段 md5 不是 %s' % (name, REF_6MODEL))
    seen.setdefault(h, []).append(tag)

print()
if len(seen) == 1:
    h = list(seen)[0]
    print('判定：**一致** —— %d 个包剥离 Integrity 行后 md5 均为 %s ⇒ 跨轮评分口径逐字相同。'
          % (sum(len(v) for v in seen.values()), h[:12]))
else:
    print('判定：**不一致** —— 出现 %d 种不同的剥离后 md5：%s' % (len(seen), {k[:12]: v for k, v in seen.items()}))
    bad.append('剥离 Integrity 行后仍不一致')
if bad:
    print()
    for x in bad:
        print('  ✗ %s' % x)
    sys.exit(1)
print('（唯一逐轮变化的是 Integrity 行本身：本轮稿件与补充材料的 md5 —— 属预期变化。）')
