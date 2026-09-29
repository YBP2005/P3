#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""pod 端：向本地 vLLM 发一个带图的多模态请求并打印回答。
用法: python q_vlm.py <model> <prompt_file> <img1> [img2 ...]
"""
import sys, json, base64, urllib.request

model = sys.argv[1]
prompt = open(sys.argv[2], encoding='utf-8').read()
imgs = sys.argv[3:]

content = [{"type": "text", "text": prompt}]
for p in imgs:
    b = base64.b64encode(open(p, 'rb').read()).decode()
    content.append({"type": "image_url",
                    "image_url": {"url": "data:image/png;base64," + b}})

body = json.dumps({
    "model": model,
    "messages": [{"role": "user", "content": content}],
    "max_tokens": 1200,
    "temperature": 0.0,
}).encode()

req = urllib.request.Request("http://127.0.0.1:8000/v1/chat/completions",
                             data=body, headers={"Content-Type": "application/json"})
try:
    r = json.load(urllib.request.urlopen(req, timeout=600))
    print("=== MODEL:", r.get("model"))
    print(r["choices"][0]["message"]["content"])
except Exception as e:
    print("=== ERROR:", type(e).__name__, e)
    try:
        print(e.read().decode()[:800])
    except Exception:
        pass
