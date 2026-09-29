# -*- coding: utf-8 -*-
"""生成 19d_probe_nonzero.py：反证对照探针。
以 19b 为母本，**只改两处**：
  ① 抽样池从「语料 base 臂 pred==0」反转为「pred!=0」（语料本来给出了数字的 item）；
  ② OUTD 改为 /root/e1_results_nonzero（避免与零池结果同名互相覆盖）。
其余（提示词、解析、图像编码、列结构、抽样步长）逐字不动。
用途：检验「允许弃答的契约」是否只是让模型一律弃答 —— 若在语料本已作答的 item 上
      permit/channel 也大量弃答，则"契约释放潜在答案"的说法不成立。
"""
import io
import os
import py_compile
import sys

sys.stdout.reconfigure(encoding='utf-8')

SRC = '/root/19b_e1_probe.py'
DST = '/root/19d_probe_nonzero.py'

R1 = [("OUTD = '/root/e1_results'", "OUTD = '/root/e1_results_nonzero'"),
      ("if str(r.get('pred', '')).strip() in ('0', '0.0') and r.get('item') in gt:",
       "if str(r.get('pred', '')).strip() not in ('0', '0.0') and r.get('item') in gt:"),
      ("    # 取 base 臂 **pred==0** 的 item",
       "    # 取 base 臂 **pred!=0** 的 item（反证对照：语料本已给出数字的 item）")]

src = io.open(SRC, encoding='utf-8', newline='').read()
out = src
for a, b in R1:
    assert out.count(a) == 1, '锚点出现 %d 次，不唯一: %r' % (out.count(a), a[:60])
    out = out.replace(a, b, 1)

io.open(DST, 'w', encoding='utf-8', newline='\n').write(out)
py_compile.compile(DST, doraise=True)

# 复验：把三处改动逐一还原后必须与 19b 逐字一致
back = out
for a, b in R1:
    back = back.replace(b, a, 1)
print('还原后与 19b 逐字一致 : %s' % (back == src))
assert back == src
print('OUTD      : %s' % [l for l in out.splitlines() if l.startswith('OUTD')][0])
print('抽样条件  : %s' % [l.strip() for l in out.splitlines() if 'not in (\'0\'' in l][0])
# 确认提示词与 19b 完全一致
import re
def prompts(t):
    m = re.search(r'^P = \{(.*?)^\}', t, re.S | re.M)
    return m.group(1)
print('提示词与 19b 一致 : %s' % (prompts(out) == prompts(src)))
assert prompts(out) == prompts(src)
print('语法编译: 通过   大小 %d B' % os.path.getsize(DST))
print('MAKE_19D_OK')
