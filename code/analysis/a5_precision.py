# -*- coding: utf-8 -*-
"""核对 A5 四个新家族的权重来源与精度（"去掉 4bit 特例"这一句的事实依据）。"""
import glob
import json
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')
MS = [
    ('gemma3-12b', '/model/ModelScope/LLM-Research/gemma-3-12b-it'),
    ('InternVL3_5-8B', '/root/models/InternVL3_5-8B'),
    ('Phi-3.5-vision-instruct', '/root/models/Phi-3.5-vision-instruct'),
    ('llava-onevision-qwen2-7b-ov', '/root/models/llava-onevision-qwen2-7b-ov'),
]
for k, p in MS:
    try:
        c = json.load(open(p + '/config.json'))
    except Exception as e:
        print('%-28s config 读不到：%s' % (k, e))
        continue
    st = glob.glob(p + '/*.safetensors')
    sz = sum(os.path.getsize(x) for x in st) / 1e9
    print('%-28s torch_dtype=%-10s quant=%-28s files=%-3d %.1f GB'
          % (k, c.get('torch_dtype'), str(c.get('quantization_config'))[:28], len(st), sz))
