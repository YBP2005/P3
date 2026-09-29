#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""dl_model.py — 在 5090 上下载 HF 模型（tree API 取清单 → aria2c 8 连接）

用法: python3 dl_model.py <repo> <local_name> [hf-mirror|huggingface]
说明: /api/models/<repo> 单模型端点需 UA，但 /api/models/<repo>/tree/main 可直接用；
      resolve/main/<file> 直链可达（已实测 http=200）。
"""
import json, os, subprocess, sys, urllib.request

repo = sys.argv[1]
local = sys.argv[2]
host = sys.argv[3] if len(sys.argv) > 3 else 'hf-mirror.com'
DEST = '/root/models/' + local
os.makedirs(DEST, exist_ok=True)

# ★ 该镜像的 API 按 User-Agent 过滤：Python-urllib 会被 403，必须伪装浏览器 UA
UA = {'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 '
                    '(KHTML, like Gecko) Chrome/120.0 Safari/537.36'}
req = urllib.request.Request('https://%s/api/models/%s/tree/main' % (host, repo), headers=UA)
with urllib.request.urlopen(req, timeout=40) as r:
    tree = json.loads(r.read().decode())
files = [t for t in tree if t.get('type') == 'file']
print('[dl] %s: %d 个文件, 合计 %.2f GB' % (
    repo, len(files), sum(f.get('size', 0) for f in files) / 1e9))

lst = '/root/models/_%s.aria2.txt' % local
with open(lst, 'w') as fh:
    for f in files:
        fh.write('https://%s/%s/resolve/main/%s\n  dir=%s/\n  out=%s\n'
                 % (host, repo, f['path'], DEST, f['path']))
print('[dl] 清单 %s' % lst)

r = subprocess.run(['aria2c', '-x', '8', '-s', '8', '-k', '1M', '-j', '3',
                    '--check-certificate=false', '--console-log-level=warn',
                    '--summary-interval=15', '-i', lst], capture_output=True, text=True)
print(r.stdout[-3000:] if r.stdout else '')
print(r.stderr[-1500:] if r.stderr else '')
tot = sum(os.path.getsize(os.path.join(dp, f))
          for dp, _, fs in os.walk(DEST) for f in fs)
print('[dl] 完成：%s 共 %.2f GB' % (DEST, tot / 1e9))
