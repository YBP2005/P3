# -*- coding: utf-8 -*-
"""取 vLLM 失败根因 + AWQ 下载段落细节。只读。"""
import re

print('===== v_awq8bit.log 关键错误上下文 =====')
try:
    lines = open('/root/logs/v_awq8bit.log', encoding='utf-8', errors='replace').read().splitlines()
except Exception as ex:
    lines = []
    print('ERR', ex)
pat = re.compile(r'(Error|error|Traceback|safetensors|unexpected|corrupt|truncat|not a valid|EOF|No such file|missing|FileNotFound|ValueError|RuntimeError|Exception)')
hits = [i for i, l in enumerate(lines) if pat.search(l)]
print('total lines', len(lines), 'hit lines', len(hits))
shown = set()
for i in hits[:80]:
    for j in range(max(0, i - 1), min(len(lines), i + 2)):
        if j in shown:
            continue
        shown.add(j)
        print('%5d| %s' % (j + 1, lines[j][:220]))

print()
print('===== v_awq8bit.log 头 40 行 =====')
for i, l in enumerate(lines[:40]):
    print('%5d| %s' % (i + 1, l[:220]))

print()
print('===== exp_v4.log 下载段（行 28-60）=====')
try:
    e = open('/root/logs/exp_v4.log', encoding='utf-8', errors='replace').read().splitlines()
    for i in range(27, min(len(e), 60)):
        print('%5d| %s' % (i + 1, e[i][:220]))
except Exception as ex:
    print('ERR', ex)
