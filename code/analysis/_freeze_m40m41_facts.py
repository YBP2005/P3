# -*- coding: utf-8 -*-
"""_freeze_m40m41_facts.py — 把 M.40/M.41 用到的**设计常数**从机器与原始产物冻结成一份 JSON。

为什么需要：表里的率由分析器生成（已有冻结件），但**那些常数**——发布件 6,146 张 / 短边 384 /
长边 384–1918、真零池 306 张 / 分层 153、每档 300 张、54 格、60 条件、359 个产物文件——
此前只存在于"我在会话里说过"。按本库纪律（**能算就不要抄**），它们应当同样是**冻结、可复算**的。
本脚本只读机器与本地冻结件，产出 `m40m41_facts.json` + `.md5`。
"""
import hashlib
import io
import json
import os
import sys
import time

sys.path.insert(0, r'<WORKDIR>\PaperB\analysis\work')
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from rsh import connect, HOST  # noqa

W = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(W, 'm40m41_facts.json')

# ── ① 远端：只读清点（发布件条目、池、三档目录、产物文件数）──────────────────
REMOTE = r'''
/usr/local/miniconda3/bin/python - <<'PY'
import io, json, os, zipfile
from PIL import Image
R = {}
# 发布件：逐条目读尺寸
z = zipfile.ZipFile('/root/fsc147_orig.zip')
imgs = [n for n in z.namelist() if n.lower().endswith(('.jpg', '.jpeg', '.png'))]
sz = []
for n in imgs:
    with z.open(n) as fh:
        with Image.open(fh) as im:
            sz.append(im.size)
R['release'] = dict(entries=len(imgs), bytes=os.path.getsize('/root/fsc147_orig.zip'),
                    short_min=min(min(s) for s in sz), short_max=max(min(s) for s in sz),
                    long_min=min(max(s) for s in sz), long_max=max(max(s) for s in sz),
                    short_is_384=sum(1 for s in sz if min(s) == 384))
# 本批 300 张样本
ids = [x.strip() for x in io.open('/root/fsc147/sample_test_ids.txt') if x.strip()]
ss = []
for i in ids:
    with Image.open(os.path.join('/root/fsc147/images', i)) as im:
        ss.append(im.size)
ss_sorted = sorted(max(s) for s in ss)
R['sample'] = dict(n=len(ids), short_min=min(min(s) for s in ss), short_max=max(min(s) for s in ss),
                   long_min=ss_sorted[0], long_max=ss_sorted[-1],
                   long_median=ss_sorted[len(ss_sorted)//2])
# 真零池
R['pool'] = dict(gt_rows=sum(1 for _ in io.open('/root/z0/gt_z0.csv')),
                 images=len(os.listdir('/root/z0/images')))
# 三档目录 + E1/E2 产物文件数
for t in ('sc384', 'sc256', 'sc768'):
    d = '/root/w1_results/fsc_' + t
    R.setdefault('fsc_dirs', {})[t] = len([f for f in os.listdir(d)]) if os.path.isdir(d) else 0
R['e2_product_files'] = sum(len(os.listdir(p)) for p in
                            ['/root/' + d for d in os.listdir('/root')
                             if d.startswith('z0_results') and os.path.isdir('/root/' + d)])
print(json.dumps(R))
PY
'''


def sh(c, cmd, t=600):
    return __import__('rsh').sh(c, cmd, t=t)


c = connect(HOST)
raw = sh(c, REMOTE, t=900)
c.close()
line = [l for l in raw.splitlines() if l.strip().startswith('{')]
assert line, '远端清点没返回 JSON：\n%s' % raw[-1500:]
facts = json.loads(line[-1])
facts['_source'] = dict(script='_freeze_m40m41_facts.py', remote_host=HOST,
                        frozen_at=time.strftime('%Y-%m-%d %H:%M:%S'))
print(json.dumps(facts, ensure_ascii=False, indent=2))
io.open(OUT, 'w', encoding='utf-8', newline='\n').write(json.dumps(facts, ensure_ascii=False, indent=2))
h = hashlib.md5(io.open(OUT, 'rb').read()).hexdigest()
io.open(OUT + '.md5', 'w', encoding='utf-8', newline='\n').write(
    '%s  %s  (_freeze_m40m41_facts.py)\n' % (h, os.path.basename(OUT)))
print('\n已写出 %s（md5 %s）' % (os.path.basename(OUT), h[:12]))
