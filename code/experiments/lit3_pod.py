#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""lit3_pod.py — 第三轮文献检索（在 pod 上跑，pod 有 HF 外网）
针对本文最新主张，查"是否已有人做过"。输出紧凑摘要 + JSON。
"""
import json, time, urllib.parse, urllib.request

Q = {
 'A1': 'mode collapse vision language model counting',
 'A2': 'modal count bias object counting regression to the mode',
 'B1': 'effective resolution pixel budget vision language model counting',
 'B2': 'image preprocessing minimum pixels artifact multimodal evaluation',
 'C1': 'blob detection legibility selective prediction counting',
 'C2': 'risk coverage selective prediction object counting',
 'C3': 'conformal prediction object counting',
 'D1': 'abstention counting vision language model refuses to count',
 'D2': 'refusal channel differs across model families multimodal',
 'D3': 'data uncertainty versus model uncertainty decomposition counting',
 'E1': 'subitizing approximate number sense vision language model',
 'E2': 'cell counting vision language model microscopy benchmark',
 'E3': 'video object counting temporal consistency',
 'F1': 'sharpness image quality predicts model error',
 'F2': 'crowd counting domain shift aerial versus ground',
}


def api(url, timeout=45):
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


hits = {}
for k, q in Q.items():
    u = 'https://huggingface.co/api/papers/search?q=' + urllib.parse.quote(q) + '&limit=25'
    try:
        d = api(u)
    except Exception as e:
        print('[%s] FAIL %s %s' % (k, type(e).__name__, e)); time.sleep(2); continue
    items = d if isinstance(d, list) else d.get('papers', d.get('results', []))
    hits[k] = items
    print('\n[%s] %s -> %d' % (k, q, len(items)))
    for p in items[:8]:
        pid = p.get('id') or p.get('paper', {}).get('id', '?')
        t = (p.get('title') or p.get('paper', {}).get('title') or '')[:92]
        dt = str(p.get('publishedAt') or p.get('paper', {}).get('publishedAt') or '')[:10]
        print('   %-18s %s %s' % (pid, dt, t))
    time.sleep(1)
json.dump(hits, open('/root/lit3_raw.json', 'w', encoding='utf-8'), ensure_ascii=False)
print('\n合计 %d 条 -> /root/lit3_raw.json' % sum(len(v) for v in hits.values()))
