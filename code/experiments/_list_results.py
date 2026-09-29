#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""_list_results.py — 在 5090 上枚举所有结果文件（size, path），避免 find -printf 兼容性问题"""
import os
out = []
for root, dirs, files in os.walk('/root'):
    # 跳过数据集/模型/权重目录，避免噪音
    skip = ('/root/dense', '/root/ext', '/root/aerial/', '/root/models', '/root/vllm312',
            '/root/sfchd_full', '/root/orig_eval/', '/root/.cache', '/root/miniconda3')
    if any(root.startswith(s) for s in skip):
        continue
    depth = root.count('/')
    if depth > 3:
        continue
    for f in files:
        if f.endswith(('.csv', '.npz')):
            p = os.path.join(root, f)
            try:
                out.append((os.path.getsize(p), p))
            except OSError:
                pass
for sz, p in sorted(out, key=lambda x: x[1]):
    print('%d\t%s' % (sz, p))
