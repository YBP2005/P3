# -*- coding: utf-8 -*-
"""生成 19c_probe_paraphrase.py：以 19b 为母本，**只增加臂与措辞**，
解析器、抽样、图像编码、结果列一律不动 —— 保证与语料/AWQ/BF16 可比。

新增三臂（响应词表与既有臂完全相同，只改指令措辞，故解析与弃答判定无需改动）：
  permitB  中文另一措辞，答 abstain
  permitC  英文措辞，答 abstain
  channelB 三态通道的另一措辞，答 cannot_judge / no_people
"""
import io
import os
import py_compile
import sys

sys.stdout.reconfigure(encoding='utf-8')

SRC = '/root/19b_e1_probe.py'
DST = '/root/19c_probe_paraphrase.py'
ANCHOR = 'DS_DIRS = {'

NEW = """# ===== 换措辞臂（只改指令措辞，响应词表与既有臂完全一致）=====
P['permitB'] = ('请报告这张图片中的人数。只有当你能够逐个确证每个个体时才给出数字；'
                '只要存在你无法确认的个体，请回答 abstain，而不要猜测。'
                '以JSON格式输出：{"count": 数量} 或 {"count": "abstain"}，只输出JSON。')
P['permitC'] = ('Count the people in this image. Give a number only if you can verify every '
                'individual; if any individual cannot be confirmed, answer abstain rather than '
                'guessing. Output only JSON: {"count": <number>} or {"count": "abstain"}.')
P['channelB'] = ('这张图里有多少人？如果你无法判断，请回答 cannot_judge；'
                 '如果画面中没有可辨认的个体，请回答 no_people；否则给出数字。'
                 '以JSON格式输出：{"response": ...}，只输出JSON。')

"""

src = io.open(SRC, encoding='utf-8', newline='').read()
assert ANCHOR in src, '找不到插入锚点 %s' % ANCHOR
assert "P['permitB']" not in src, '19b 里已有 permitB，锚点判断有误'
out = src.replace(ANCHOR, NEW + ANCHOR, 1)
io.open(DST, 'w', encoding='utf-8', newline='\n').write(out)
py_compile.compile(DST, doraise=True)

# 复验：除了新增的三臂，其余与 19b 必须逐字一致
import re
def arms(text):
    """同时收录字典体内的 'name':(...) 与字典外的 P['name']=(...) 两种写法。"""
    m = re.search(r'^P = \{(.*?)^\}', text, re.S | re.M)
    body = m.group(1)
    a = set(re.findall(r"'([A-Za-z0-9_]+)':\s*\(", body))
    b = set(re.findall(r"^P\['([A-Za-z0-9_]+)'\]\s*=", text, re.M))
    return sorted(a | b)

a_src, a_dst = arms(src), arms(out)
print('19b 原有臂 : %s' % a_src)
print('19c 全部臂 : %s' % a_dst)
print('新增       : %s' % sorted(set(a_dst) - set(a_src)))
assert set(a_dst) - set(a_src) == {'permitB', 'permitC', 'channelB'}, '新增臂与预期不符'
assert not (set(a_src) - set(a_dst)), '丢失了原有臂'
# 逐字一致校验：把新增块去掉后应与 19b 完全相同
back = out.replace(NEW, '', 1)
print('去掉新增块后与 19b 逐字一致: %s' % (back == src))
assert back == src
print('语法编译: 通过   大小 %d B' % os.path.getsize(DST))
print('MAKE_19C_OK')
