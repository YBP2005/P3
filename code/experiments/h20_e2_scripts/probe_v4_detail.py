# -*- coding: utf-8 -*-
"""细节排查：两模型分片逐文件大小 + vLLM 失败根因。"""
import json
import os

for d in ('/root/models/Qwen3-VL-32B-Instruct-AWQ-8bit',
          '/root/models/Qwen2.5-VL-72B-Instruct-AWQ'):
    print('=====', d)
    idx = os.path.join(d, 'model.safetensors.index.json')
    if os.path.exists(idx):
        need = sorted(set(json.load(open(idx))['weight_map'].values()))
        for f in need:
            p = os.path.join(d, f)
            if os.path.exists(p):
                print('  %-42s %14d  %.3f GB' % (f, os.path.getsize(p), os.path.getsize(p) / 1e9))
            else:
                print('  %-42s %14s' % (f, 'MISSING'))
    else:
        print('  no index.json')
    try:
        names = sorted(os.listdir(d))
        print('  --- all entries (%d): %s' % (len(names), ', '.join(names)))
    except Exception as ex:
        print('  listdir ERR', ex)
