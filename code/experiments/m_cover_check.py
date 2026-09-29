#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""查 M 机两文件的条件/trial 覆盖（避免内联 python 的多语句语法问题）"""
import json, os, collections, sys
sys.stdout.reconfigure(encoding='utf-8')
for p in ['/root/nd_full_32b.jsonl', '/root/nd_full_8b.jsonl']:
    print('== %s' % os.path.basename(p))
    if not os.path.exists(p):
        print('   不存在'); continue
    o = [json.loads(l) for l in open(p, encoding='utf-8') if l.strip()]
    t = collections.defaultdict(set)
    n = collections.Counter()
    for x in o:
        t[x['cond']].add(x['trial'])
        n[x['cond']] += 1
    print('   总记录 %d' % len(o))
    for k in sorted(t):
        print('   %-22s trials=%-28s 记录=%d' % (k, sorted(t[k]), n[k]))
print('\n/vdall 图片数: %d' % len([f for f in os.listdir('/root/vdall') if f.endswith('.jpg')]))
