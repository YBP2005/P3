# -*- coding: utf-8 -*-
"""按**hub 清单里的期望尺寸**逐文件校验本地权重（运行于 H20）。
用法：python3 verify_model.py <model_id> <dest_dir>
退出码 0 = 全部尺寸正确；1 = 有缺失/尺寸不符。
⚠ 关键：不能只看"文件是否存在/是否 0 字节" —— 截断文件（如 598MB/4902MB）会漏过。
"""
import json
import os
import sys
import urllib.request

MS = 'https://www.modelscope.cn'
HF = 'https://hf-mirror.com'


def get(url, timeout=90):
    req = urllib.request.Request(url, headers={'User-Agent': 'curl/8'})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def list_ms(model):
    d = json.loads(get('%s/api/v1/models/%s/repo/files?Revision=master&Recursive=true' % (MS, model)))
    out = []
    for f in d.get('Data', {}).get('Files', []):
        if f.get('Type') == 'tree':
            continue
        p = f.get('Path', '')
        if p and not p.startswith('.'):
            out.append((p, int(f.get('Size') or 0)))
    return out


def list_hf(model):
    d = json.loads(get('%s/api/models/%s/tree/main?recursive=true' % (HF, model)))
    return [(f['path'], int(f.get('size') or 0)) for f in d if f.get('type') == 'file']


def main():
    model, dest = sys.argv[1], sys.argv[2]
    files, src = [], None
    for name, fn in (('ModelScope', list_ms), ('hf-mirror', list_hf)):
        try:
            files = fn(model)
            if files:
                src = name
                break
        except Exception as ex:
            print('  %s 取清单失败: %s' % (name, str(ex)[:80]))
    if not files:
        print('  两个源都取不到清单'); return 2

    bad = []
    for path, size in files:
        lp = os.path.join(dest, path)
        got = os.path.getsize(lp) if os.path.exists(lp) else -1
        if got != size:
            bad.append((path, size, got))
    print('  [%s] %s：%d 个文件，尺寸不符 %d 个' % (src, model, len(files), len(bad)))
    for path, size, got in bad:
        print('     !! %-52s 期望 %d 实得 %d' % (path, size, got))
    return 1 if bad else 0


sys.exit(main())
