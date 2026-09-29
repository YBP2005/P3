#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""_hf_probe.py — 在 5090 上查候选第二族 VLM 的文件与体积（hf-mirror / HF API）"""
import json, sys, urllib.request

CANDS = [
    'OpenGVLab/InternVL2_5-8B-AWQ',
    'OpenGVLab/InternVL2_5-8B',
    'OpenGVLab/InternVL3-8B',
    'llava-hf/llava-onevision-qwen2-7b-ov-hf',
    'Qwen/Qwen2.5-VL-7B-Instruct-AWQ',
    'Qwen/Qwen2.5-VL-7B-Instruct',
    'openbmb/MiniCPM-V-2_6',
]
BASE = 'https://hf-mirror.com/api/models/'


def size_of(repo, fn):
    try:
        req = urllib.request.Request(repo + '/resolve/main/' + fn, method='HEAD')
        with urllib.request.urlopen(req, timeout=25) as r:
            return int(r.headers.get('Content-Length') or 0)
    except Exception:
        return -1


for repo in CANDS:
    print('=== %s ===' % repo)
    try:
        with urllib.request.urlopen(BASE + repo, timeout=30) as r:
            d = json.loads(r.read().decode())
        sib = [s['rfilename'] for s in d.get('siblings', [])]
    except Exception as ex:
        print('  查询失败: %s' % str(ex)[:110])
        continue
    st = [x for x in sib if x.endswith('.safetensors')]
    py = [x for x in sib if x.endswith('.py')]
    print('  文件数=%d  safetensors=%d  .py(需 trust_remote_code)=%d  config=%s' % (
        len(sib), len(st), len(py), 'config.json' in sib))
    tot = 0
    for x in st[:12]:
        s = size_of(BASE.replace('/api/models/', '') + repo, x)
        if s > 0:
            tot += s
    if tot:
        print('  前 %d 个权重合计 %.1f GB' % (min(12, len(st)), tot / 1e9))
    for x in sib[:10]:
        print('    ' + x)
