# -*- coding: utf-8 -*-
"""在 H20 上下载官方 FP8 权重。只用标准库 + curl，避免在这台机器上装 Python 包。
优先 ModelScope（国内更快），失败则回退 hf-mirror。
按清单逐文件下载、断点续传、逐文件核对大小，最后打印总账。
"""
import json
import os
import subprocess
import sys
import time
import urllib.request

sys.stdout.reconfigure(encoding='utf-8')

MODEL = 'Qwen/Qwen3-VL-32B-Instruct-FP8'
DEST = '/root/models/Qwen3-VL-32B-Instruct-FP8'
MS_BASE = 'https://www.modelscope.cn'
HF_BASE = 'https://hf-mirror.com'


def get(url, timeout=60):
    req = urllib.request.Request(url, headers={'User-Agent': 'curl/8'})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def ms_files():
    url = '%s/api/v1/models/%s/repo/files?Revision=master&Recursive=true' % (MS_BASE, MODEL)
    d = json.loads(get(url, 90))
    out = []
    for f in d.get('Data', {}).get('Files', []):
        if f.get('Type') == 'tree':
            continue
        p = f.get('Path', '')
        if p and not p.startswith('.'):
            out.append((p, int(f.get('Size') or 0)))
    return out


def hf_files():
    url = '%s/api/models/%s' % (HF_BASE, MODEL)
    d = json.loads(get(url, 90))
    return [(s['rfilename'], int(s.get('size') or 0)) for s in d.get('siblings', [])]


src = None
files = []
for name, fn, base in (('ModelScope', ms_files, MS_BASE), ('hf-mirror', hf_files, HF_BASE)):
    try:
        files = fn()
        if files:
            src, BASE = name, base
            print('源 %s 可用，共 %d 个文件，合计 %.2f GB'
                  % (name, len(files), sum(s for _, s in files) / 1e9), flush=True)
            break
    except Exception as ex:
        print('源 %s 取清单失败: %s' % (name, str(ex)[:120]), flush=True)

if not files:
    print('两个源都取不到清单，放弃')
    sys.exit(1)

# 优先下载权重分片，其余小文件最后
files.sort(key=lambda x: (0 if x[0].endswith('.safetensors') else 1, -x[1]))
os.makedirs(DEST, exist_ok=True)
t0 = time.time()
ok = bad = 0
total = sum(s for _, s in files)
done_bytes = 0

for path, size in files:
    lp = os.path.join(DEST, path)
    os.makedirs(os.path.dirname(lp), exist_ok=True) if '/' in path else None
    if os.path.exists(lp) and os.path.getsize(lp) == size:
        done_bytes += size
        ok += 1
        continue
    if src == 'ModelScope':
        url = '%s/models/%s/resolve/master/%s' % (MS_BASE, MODEL, path)
    else:
        url = '%s/%s/resolve/main/%s' % (HF_BASE, MODEL, path)
    r = subprocess.run(['curl', '-L', '-sS', '--retry', '4', '--retry-delay', '5',
                        '-C', '-', '-o', lp, url], capture_output=True, text=True)
    got = os.path.getsize(lp) if os.path.exists(lp) else 0
    if got == size:
        ok += 1
        done_bytes += size
        print('  OK  %-52s %8.1f MB' % (path, size / 1e6), flush=True)
    else:
        bad += 1
        print('  !!  %-52s 期望 %d 实得 %d  %s'
              % (path, size, got, (r.stderr or '')[:80]), flush=True)

print()
print('=== 下载结束：成功 %d，失败 %d，用时 %.0fs ===' % (ok, bad, time.time() - t0), flush=True)
print('总量 %.2f GB → %s' % (done_bytes / 1e9, DEST), flush=True)
subprocess.run(['du', '-sh', DEST])
subprocess.run(['df', '-h', '/'])
print('FP8_DOWNLOAD_DONE' if bad == 0 else 'FP8_DOWNLOAD_PARTIAL', flush=True)
