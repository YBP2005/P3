#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""g7_run.py — G7（服务栈因子实验）的运行器。

冻结判据：/root/g7_criteria_frozen.json（启动时断言 md5；提示词逐字比对）。
仪器：`19f_probe_ablation.py`（md5 28e82b20a7f468680da11b2e9855cff9）由 importlib 载入，
      `P` / `b64_of()` / `call_img()` / `parse()` **逐字复用**，不复制实现。
服务：本机 vLLM（PORT 环境变量），LOCAL_API 由本脚本依据 PORT 拼出并**在执行 import 前**写入环境。

用法：
    PORT=8010 CONFIG=R_s1 WORKERS=8 SYSTEM=0 python3 g7_run.py
输出：/root/g7_res/g7_<CONFIG>.csv（断点续跑：(config,ds,arm,item) 已完成则跳过）
"""
import csv
import hashlib
import importlib.util
import io
import json
import os
import queue
import sys
import threading
import time

FROZEN = '/root/19f_probe_ablation.py'
FROZEN_MD5 = '28e82b20a7f468680da11b2e9855cff9'
CRIT = '/root/g7_criteria_frozen.json'
CRIT_MD5 = '700598c23627e9def04506d1e14dbd18'
PORT = os.environ.get('PORT', '8010')
CONFIG = os.environ.get('CONFIG', 'R_s1')
WORKERS = int(os.environ.get('WORKERS', '8'))
SYSTEM = int(os.environ.get('SYSTEM', '0'))
NITEM = 100
OUT = '/root/g7_res'
IMGDIR = {'st_a': '/root/dense/shanghaitech/images/part_A_test',
          'visdrone': '/root/aerial/visdrone/images'}
GT = {'st_a': '/root/dense/shanghaitech/counts.csv', 'visdrone': '/root/aerial/gt_visdrone.csv'}
ARMS = ['base', 'permit', 'channel']
os.makedirs(OUT, exist_ok=True)
os.environ.setdefault('BAILIAN_API', 'http://127.0.0.1:%s/v1/chat/completions' % PORT)
os.environ.setdefault('DASHSCOPE_API_KEY', 'EMPTY')


def load_frozen_probe():
    got = hashlib.md5(open(FROZEN, 'rb').read()).hexdigest()
    assert got == FROZEN_MD5, '冻结探针 md5 不符：%s' % got
    spec = importlib.util.spec_from_file_location('frozen19f', FROZEN)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    assert 'http://127.0.0.1:%s/' % PORT in m.API, '探针的 API 没指到本机端口：%s' % m.API
    return m


def check_criteria(M):
    b = open(CRIT, 'rb').read()
    got = hashlib.md5(b).hexdigest()
    assert got == CRIT_MD5, '冻结件 md5 变了：%s != %s' % (got, CRIT_MD5)
    j = json.loads(b.decode('utf-8'))
    for a, p in sorted(j['prompts_verbatim'].items()):
        assert M.P[a] == p, '提示词 %s 与冻结件不一致' % a
    assert j['design']['arms'] == ARMS
    assert j['design']['item_set'].startswith('每域取')
    print('[g7] 冻结件 md5 OK：%s ｜ 三臂提示词逐字一致 ｜ config=%s workers=%d system=%d port=%s'
          % (got, CONFIG, WORKERS, SYSTEM, PORT), flush=True)
    return j


def items(ds):
    """每域取文件名排序后的前 NITEM 项（确定性）。"""
    import glob
    fs = sorted(glob.glob(os.path.join(IMGDIR[ds], '*')))
    fs = [f for f in fs if os.path.splitext(f)[1].lower() in ('.jpg', '.jpeg', '.png', '.bmp')]
    return fs[:NITEM]


def gtmap(ds):
    out = {}
    with open(GT[ds], encoding='utf-8-sig') as f:
        for r in csv.DictReader(f):
            if ds == 'st_a':
                if r.get('part') != 'part_A' or r.get('split') != 'test':
                    continue
                out[os.path.basename(r['file'])] = int(r['count'])
            else:
                out[r['item']] = int(r['gt'])
                # ★ 2026-09-27 修：VisDrone 的 GT 键是**不带扩展名的 stem**，而图名带 .jpg
                #   ⇒ 只按全名索引会让该域**一项都配不上**（实测 visdrone 0 项、st_a 300 项）。
                out[os.path.splitext(r['item'])[0]] = int(r['gt'])
    return out


def main():
    M = load_frozen_probe()
    J = check_criteria(M)
    sysmsg = J['design']['system_message'] if SYSTEM else ''
    from PIL import Image
    jobs = []
    for ds in ('st_a', 'visdrone'):
        gm = gtmap(ds)
        for f in items(ds):
            b = os.path.basename(f)
            g = gm.get(b, gm.get(os.path.splitext(b)[0]))
            if g is None:
                print('  ⚠ 无 GT：%s/%s' % (ds, b), flush=True)
                continue
            for arm in ARMS:
                jobs.append((ds, b, f, g, arm))
    out_csv = os.path.join(OUT, 'g7_%s.csv' % CONFIG)
    done = set()
    if os.path.exists(out_csv):
        for r in csv.DictReader(open(out_csv, encoding='utf-8-sig')):
            if (r.get('http_err') or '0') == '0' and (r.get('raw') or '') != '':
                done.add((r['ds'], r['item'], r['arm']))
    jobs = [j for j in jobs if (j[0], j[1], j[4]) not in done]
    new = not os.path.exists(out_csv) or os.path.getsize(out_csv) == 0
    fh = open(out_csv, 'a', encoding='utf-8-sig', newline='')
    wr = csv.writer(fh)
    if new:
        wr.writerow(['config', 'ds', 'item', 'arm', 'gt', 'pred', 'parse_ok', 'abstain',
                     'http_err', 'raw'])
    print('[g7/%s] 待跑 %d 项（已完成 %d）｜ domain×arm = %d' % (CONFIG, len(jobs), len(done),
                                                            len(jobs) and 6), flush=True)
    if not jobs:
        fh.close(); return
    q = queue.Queue()
    for j in jobs:
        q.put(j)
    st = {'n': 0, 't0': time.time(), 'e400': 0, 'bad': 0}
    lk = threading.Lock()

    def work():
        while True:
            try:
                ds, b, f, g, arm = q.get_nowait()
            except queue.Empty:
                return
            raw, ok, e400 = '', 0, 0
            try:
                im = Image.open(f).convert('RGB')
                raw = M.call_img(M.b64_of(im), M.P[arm], 'Qwen3-VL-32B-Instruct', system=sysmsg)
                pred = M.parse(raw)
                ok = 1 if pred is not None else 0
            except Exception as ex:
                pred = None
                s = str(ex)
                if 'HTTP Error 400' in s or '400' in s[:40]:
                    e400 = 1
                raw = 'ERR %s' % s[:120]
            with lk:
                wr.writerow([CONFIG, ds, b, arm, g,
                             '' if pred is None else pred, ok,
                             1 if pred == 'abstain' else 0, e400, raw.replace('\n', ' ')[:300]])
                fh.flush()
                st['n'] += 1
                st['e400'] += e400
                st['bad'] += 0 if ok else 1
                if st['n'] % 100 == 0:
                    el = max(time.time() - st['t0'], 1e-9)
                    print('  %d/%d (%.2f/s bad=%d 400=%d eta=%.0fmin)'
                          % (st['n'], len(jobs), st['n'] / el, st['bad'], st['e400'],
                             (len(jobs) - st['n']) / max(st['n'] / el, 1e-9) / 60), flush=True)

    th = [threading.Thread(target=work, daemon=True) for _ in range(WORKERS)]
    for t in th:
        t.start()
    for t in th:
        t.join()
    fh.close()
    print('[g7/%s] DONE n=%d unparsed=%d http400=%d' % (CONFIG, st['n'], st['bad'], st['e400']),
          flush=True)


if __name__ == '__main__':
    main()
