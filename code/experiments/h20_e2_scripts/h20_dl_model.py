# -*- coding: utf-8 -*-
"""通用下载器（在 H20 上运行）：标准库 + curl，无 Python 包依赖。
用法： python3 h20_dl_model.py <model_id> <dest_dir> [model_id dest_dir ...]
逐个文件下载、断点续传、核对大小。优先 ModelScope，回退 hf-mirror。
"""
import json
import os
import subprocess
import sys
import time
import urllib.request

sys.stdout.reconfigure(encoding='utf-8')

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


def dl_one(model, dest):
    files, src, base = [], None, None
    for name, fn, b in (('ModelScope', list_ms, MS), ('hf-mirror', list_hf, HF)):
        try:
            files = fn(model)
            if files:
                src, base = name, b
                break
        except Exception as ex:
            print('  %s 取清单失败: %s' % (name, str(ex)[:90]), flush=True)
    if not files:
        print('!! %s 两个源都取不到清单' % model, flush=True)
        return False, 0

    total = sum(s for _, s in files)
    print('  [%s] %s：%d 文件 %.2f GB' % (src, model, len(files), total / 1e9), flush=True)
    files.sort(key=lambda x: (0 if x[0].endswith('.safetensors') else 1, -x[1]))
    os.makedirs(dest, exist_ok=True)
    t0 = time.time()

    def fetch(path, size):
        lp = os.path.join(dest, path)
        if os.path.exists(lp) and os.path.getsize(lp) == size:
            return True, 'skip'
        if src == 'ModelScope':
            url = '%s/models/%s/resolve/master/%s' % (MS, model, path)
        else:
            url = '%s/%s/resolve/main/%s' % (base, model, path)
        subprocess.run(['curl', '-L', '-sS', '--retry', '6', '--retry-delay', '5',
                        '--retry-all-errors', '-C', '-', '-o', lp, url],
                       capture_output=True, text=True)
        got = os.path.getsize(lp) if os.path.exists(lp) else 0
        return got == size, '%d/%d' % (got, size)

    # 主轮
    ok, bad_list, done = 0, [], 0
    for path, size in files:
        good, info = fetch(path, size)
        if good:
            ok += 1
            done += size
            if info != 'skip':
                print('    OK  %-50s %8.1f MB  (%.0fs)'
                      % (path, size / 1e6, time.time() - t0), flush=True)
        else:
            bad_list.append((path, size))
            print('    !!  %-50s %s' % (path, info), flush=True)

    # ★ 校验重试轮：瞬时网络失败会让 curl 留下**尺寸不符**的文件（本项目已发生三次：
    #   72B 的 model-00001 实得 0、AWQ-8bit 的 model-00003 实得 598MB/4902MB）。
    #   若不复核，模型加载时会因分片截断而失败。重试前**先删掉坏文件**，避免 curl -C -
    #   在损坏文件上续传造成更隐蔽的错误。
    for rnd in (1, 2):
        if not bad_list:
            break
        print('  --- 第 %d 轮补齐 %d 个不合格文件（先删坏文件）---' % (rnd, len(bad_list)), flush=True)
        still = []
        for path, size in bad_list:
            lp = os.path.join(dest, path)
            try:
                if os.path.exists(lp):
                    os.remove(lp)
            except Exception as ex:
                print('    删坏文件失败 %s: %s' % (path, ex), flush=True)
            good, info = fetch(path, size)
            if good:
                ok += 1
                done += size
                print('    OK(补) %-46s %8.1f MB' % (path, size / 1e6), flush=True)
            else:
                still.append((path, size))
                print('    !!  %-50s 仍不合格 %s' % (path, info), flush=True)
        bad_list = still
        time.sleep(5)

    print('  → %s 成功 %d 失败 %d  %.2f GB  %.0fs'
          % (model, ok, len(bad_list), done / 1e9, time.time() - t0), flush=True)
    for path, size in bad_list:
        print('     FAIL %s' % path, flush=True)
    return len(bad_list) == 0, done


JOBS = []
args = sys.argv[1:]
for i in range(0, len(args) - 1, 2):
    JOBS.append((args[i], args[i + 1]))
if not JOBS:
    print('用法: h20_dl_model.py <model_id> <dest_dir> [...]')
    sys.exit(1)

allok = True
for m, d in JOBS:
    good, _ = dl_one(m, d)
    allok &= good
subprocess.run(['df', '-h', '/', '/model'])
print('DL_ALL_DONE' if allok else 'DL_ALL_PARTIAL', flush=True)
