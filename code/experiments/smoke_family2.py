#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""smoke_family2.py — 第二族模型协议自检：能否按 {"count": N} 作答 + 弃权是否出现

用 3 类各 2 张真实图测（稀疏/中密/极密），确认：
  ① 服务可调用 ② JSON 可解析 ③ 密集图上是否出现"答 0"（弃权）现象
若密集图上答 0 → 说明弃权并非 Qwen 特有，P0 #1 的对照就有意义。
"""
import base64, csv, io, json, os, sys, time, urllib.request
from PIL import Image

API = 'http://127.0.0.1:8000/v1/chat/completions'
MODEL = os.environ.get('SERVED_MODEL', 'internvl25-8b-awq')
PROMPT = ('请数出图片中的人数（人群中的每个人头或人体），不要遗漏，不要重复，'
          '以JSON格式输出：{"count": 数量}，只输出JSON。')
R = os.environ.get('DATA_ROOT', '/root/dense')


def enc(path, max_pixels=1048576):
    im = Image.open(path).convert('RGB')
    if im.size[0] * im.size[1] > max_pixels:
        s = (max_pixels / float(im.size[0] * im.size[1])) ** 0.5
        im = im.resize((max(1, int(im.size[0] * s)), max(1, int(im.size[1] * s))))
    b = io.BytesIO(); im.save(b, 'JPEG', quality=92)
    return base64.b64encode(b.getvalue()).decode()


def call(b64, timeout=180):
    body = {'model': MODEL, 'messages': [{'role': 'user', 'content': [
        {'type': 'image_url', 'image_url': {'url': 'data:image/jpeg;base64,' + b64}},
        {'type': 'text', 'text': PROMPT}]}], 'temperature': 0.0, 'max_tokens': 64}
    req = urllib.request.Request(API, data=json.dumps(body).encode(),
                                 headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())['choices'][0]['message']['content']


def items(ds, k=2):
    out = []
    if ds == 'st_a':
        idir = os.path.join(R, 'shanghaitech', 'images', 'part_A_test')
        with open(os.path.join(R, 'shanghaitech', 'counts.csv'), encoding='utf-8-sig') as f:
            for r in csv.DictReader(f):
                if r.get('part') == 'part_A' and r.get('split') == 'test':
                    p = os.path.join(idir, os.path.basename(r['file']))
                    if os.path.exists(p):
                        out.append((os.path.basename(r['file']), p, int(r['count'])))
    elif ds == 'st_b':
        idir = os.path.join(R, 'shanghaitech', 'images', 'part_B_test')
        with open(os.path.join(R, 'shanghaitech', 'counts.csv'), encoding='utf-8-sig') as f:
            for r in csv.DictReader(f):
                if r.get('part') == 'part_B' and r.get('split') == 'test':
                    p = os.path.join(idir, os.path.basename(r['file']))
                    if os.path.exists(p):
                        out.append((os.path.basename(r['file']), p, int(r['count'])))
    out.sort(key=lambda x: x[2])
    return out[-k:] if out else []


print('MODEL =', MODEL)
for ds in ('st_b', 'st_a'):
    for nm, p, gt in items(ds, 2):
        t0 = time.time()
        try:
            raw = call(enc(p))
            print('  %-8s %-16s GT=%-5d 用时%4.1fs  回复=%r' % (ds, nm, gt, time.time() - t0, raw[:70]))
        except Exception as ex:
            print('  %-8s %-16s GT=%-5d 失败: %s' % (ds, nm, gt, str(ex)[:110]))
