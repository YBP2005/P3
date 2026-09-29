# -*- coding: utf-8 -*-
"""_parse_diag.py — 为什么 permit 臂全部解析失败？拿 CSV 原文直接喂 19e 的 parse()。

不得靠猜：这里逐字符打印 raw 的 repr、长度、以及正则匹配结果，并与"构造的同样字符串"对照。
"""
import csv
import importlib.util
import io
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')
spec = importlib.util.spec_from_file_location('p19e', '/root/19e_probe_multi.py')
E = importlib.util.module_from_spec(spec)
spec.loader.exec_module(E)

p = '/root/w1_results/hosted/gpt-5.6-luna__st_a__permit.csv'
rows = list(csv.DictReader(io.open(p, encoding='utf-8-sig')))
r = rows[0]
raw = r.get('raw')
print('CSV raw repr : %r' % raw)
print('CSV pred     : %r  parse_ok=%r' % (r.get('pred'), r.get('parse_ok')))
print('parse(raw)   : %r' % (E.parse(raw),))
print('len          : %d' % len(raw))
print('首 3 字符码点 : %s' % [hex(ord(c)) for c in raw[:3]])
pat = r'\{\s*(?:count|response|计数|数量|人数)\s*[:：]\s*"?(\d+|abstain|cannot_judge|no_people)'
print('正则直接匹配 : %r' % (re.search(pat, raw, re.I),))
built = '{"count":"abstain"}'
print('构造串匹配    : %r' % (re.search(pat, built, re.I),))
print('parse(构造串) : %r' % (E.parse(built),))
# 逐位置诊断：把 raw 拆成字符打印，找不可见字符
print('字符清单      : %s' % ' '.join('%s=%s' % (i, hex(ord(c))) for i, c in enumerate(raw[:24])))
