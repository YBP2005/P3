# -*- coding: utf-8 -*-
"""ivl_probe.py — 直接探针：InternVL 在密集/稀疏图上的原始文本应答形态
（只打少量请求，验证"弃权是文本表达"这一口径）
"""
import base64, io, json, os, sys, urllib.request
from PIL import Image

API = os.environ.get('LOCAL_API', 'http://127.0.0.1:8000/v1/chat/completions')
MODEL = os.environ.get('SERVED_MODEL', 'internvl25-8b-awq')
PR = ('请数出图片中的人数（人群中的每个人头或人体），不要遗漏，不要重复，'
      '以JSON格式输出：{"count": 数量}，只输出JSON。')


def enc(path, max_pixels=1048576):
    im = Image.open(path).convert('RGB')
    if im.size[0] * im.size[1] > max_pixels:
        s = (max_pixels / float(im.size[0] * im.size[1])) ** 0.5
        im = im.resize((max(1, int(im.size[0] * s)), max(1, int(im.size[1] * s))))
    b = io.BytesIO()
    im.save(b, 'JPEG', quality=92)
    return base64.b64encode(b.getvalue()).decode()


def call(b64, prompt=PR):
    body = {'model': MODEL, 'temperature': 0, 'max_tokens': 256,
            'messages': [{'role': 'user', 'content': [
                {'type': 'image_url', 'image_url': {'url': 'data:image/jpeg;base64,' + b64}},
                {'type': 'text', 'text': prompt}]}]}
    req = urllib.request.Request(API, data=json.dumps(body).encode(),
                                 headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=180) as r:
        return json.loads(r.read())['choices'][0]['message']['content']


CASES = []
for nm, gt in [('IMG_1', 172), ('IMG_10', 502), ('IMG_2', 246), ('IMG_3', 379)]:
    CASES.append(('st_a', '/root/dense/shanghaitech/images/part_A_test/%s.jpg' % nm, gt))
for nm, gt in [('IMG_1', 13), ('IMG_2', 15), ('IMG_3', 11)]:
    CASES.append(('st_b', '/root/dense/shanghaitech/images/part_B_test/%s.jpg' % nm, gt))

print(json.dumps({'model': MODEL, 'api': API}, ensure_ascii=False))
for ds, p, gt in CASES:
    if not os.path.exists(p):
        print('%-5s %-50s MISSING' % (ds, p))
        continue
    try:
        raw = call(enc(p))
    except Exception as e:
        raw = 'ERR %r' % (e,)
    print('%-5s gt=%-5d %s' % (ds, gt, json.dumps(raw, ensure_ascii=False)))
    sys.stdout.flush()
