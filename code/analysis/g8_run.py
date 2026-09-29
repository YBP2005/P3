#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""g8_run.py — G8（UCF-QNRF 英文臂补完）的运行器。

冻结判据：/root/g8_criteria_frozen.json（启动时断言 md5；三条提示词逐字比对）。
仪器：`19f_probe_ablation.py`（md5 28e82b20a7f468680da11b2e9855cff9）与
      `20b_probe_lang.py`（md5 77385964ee28d6bf26b8a2a3dcca1975）**只读**，前者提供
      `parse`/`b64_of`/`call_img`，后者的 EN 表用于**逐字核对**。

用法：PORT=8011 ARMS=en:base,en:channel,cn:base python3 g8_run.py
输出：/root/g8_res/g8.csv（断点续跑：(arm,item) 已完成则跳过）
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

PROBE = '/root/19f_probe_ablation.py'
PROBE_MD5 = '28e82b20a7f468680da11b2e9855cff9'
LANG = '/root/20b_probe_lang.py'
LANG_MD5 = '77385964ee28d6bf26b8a2a3dcca1975'
CRIT = '/root/g8_criteria_frozen.json'
CRIT_MD5 = '1fded0d37282c093a323325fff90106a'
PORT = os.environ.get('PORT', '8011')
ARMS = [a for a in os.environ.get('ARMS', 'en:base,en:channel,cn:base').split(',') if a]
SRC = '/root/dense_results/vlm_ucf_base_whole.csv'
IMGDIR = '/root/dense/ucf_qnrf/UCF-QNRF_ECCV18/Test'
OUT = '/root/g8_res'
os.makedirs(OUT, exist_ok=True)
os.environ.setdefault('BAILIAN_API', 'http://127.0.0.1:%s/v1/chat/completions' % PORT)
os.environ.setdefault('DASHSCOPE_API_KEY', 'EMPTY')


def load_frozen(path, want):
    got = hashlib.md5(open(path, 'rb').read()).hexdigest()
    assert got == want, '%s md5 不符：%s' % (path, got)
    spec = importlib.util.spec_from_file_location(os.path.basename(path)[:-3], path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def main():
    M = load_frozen(PROBE, PROBE_MD5)
    L = load_frozen(LANG, LANG_MD5)
    b = open(CRIT, 'rb').read()
    got = hashlib.md5(b).hexdigest()
    assert got == CRIT_MD5, '冻结件 md5 变了：%s != %s' % (got, CRIT_MD5)
    J = json.loads(b.decode('utf-8'))
    # ★ 逐字核对：英文表与 20b 的 EN 表一致；中文表与 19f 的 P 表一致
    for a, p in J['prompts_verbatim'].items():
        lang, arm = a.split(':')
        ref = L.EN[arm] if lang == 'en' else M.P[arm]
        assert ref == p, '提示词 %s 与冻结件不一致' % a
    print('[g8] 冻结件 md5 OK：%s ｜ 三条提示词逐字一致 ｜ 端口 %s ｜ 臂 %s' % (got, PORT, ARMS),
          flush=True)

    rows = list(csv.DictReader(io.open(SRC, encoding='utf-8-sig')))
    items = []
    for r in rows:
        it = r['item'].strip()
        p = None
        for ext in ('.jpg', '.jpeg', '.png', '.JPG'):
            c = os.path.join(IMGDIR, it + ext)
            if os.path.exists(c):
                p = c
                break
        assert p is not None, '找不到图：%s' % it
        assert r.get('gt') not in ('', None), '缺 gt：%s' % it
        items.append((it, p, int(float(r['gt']))))
    assert len(items) == 334, '项数不是 334：%d' % len(items)
    print('[g8] 334 项全部解析到图与 gt（%s）' % IMGDIR, flush=True)

    out_csv = os.path.join(OUT, 'g8.csv')
    done = set()
    if os.path.exists(out_csv):
        for r in csv.DictReader(open(out_csv, encoding='utf-8-sig')):
            if (r.get('http_err') or '0') == '0' and (r.get('raw') or '') != '':
                done.add((r['arm'], r['item']))
    jobs = [(a, it, p, g) for a in ARMS for it, p, g in items if (a, it) not in done]
    new = not os.path.exists(out_csv) or os.path.getsize(out_csv) == 0
    fh = open(out_csv, 'a', encoding='utf-8-sig', newline='')
    wr = csv.writer(fh)
    if new:
        wr.writerow(['arm', 'item', 'gt', 'pred', 'parse_ok', 'abstain', 'http_err', 'raw'])
    print('[g8] 待跑 %d 项（已完成 %d）' % (len(jobs), len(done)), flush=True)
    if not jobs:
        fh.close(); return
    q = queue.Queue()
    for j in jobs:
        q.put(j)
    st = {'n': 0, 'tot': len(jobs), 't0': time.time(), 'e400': 0, 'bad': 0}
    lk = threading.Lock()
    from PIL import Image

    def work():
        while True:
            try:
                arm, it, path, g = q.get_nowait()
            except queue.Empty:
                return
            lang, an = arm.split(':')
            prompt = L.EN[an] if lang == 'en' else M.P[an]
            pred, ok, e400, raw = None, 0, 0, ''
            try:
                im = Image.open(path).convert('RGB')
                raw = M.call_img(M.b64_of(im), prompt, 'Qwen3-VL-32B-Instruct')
                pred = M.parse(raw)
                ok = 1 if pred is not None else 0
            except Exception as ex:
                raw = 'ERR %s' % str(ex)[:160]
                if '400' in str(ex)[:60]:
                    e400 = 1
            with lk:
                wr.writerow([arm, it, g, '' if pred is None else pred, ok,
                             1 if pred == 'abstain' else 0, e400, raw.replace('\n', ' ')[:300]])
                fh.flush()
                st['n'] += 1; st['e400'] += e400; st['bad'] += 0 if ok else 1
                if st['n'] % 100 == 0:
                    el = max(time.time() - st['t0'], 1e-9)
                    print('  %d/%d (%.2f/s bad=%d 400=%d)' % (st['n'], st['tot'], st['n'] / el,
                                                              st['bad'], st['e400']), flush=True)

    th = [threading.Thread(target=work, daemon=True) for _ in range(8)]
    for t in th:
        t.start()
    for t in th:
        t.join()
    fh.close()
    print('[g8] DONE n=%d unparsed=%d http400=%d' % (st['n'], st['bad'], st['e400']), flush=True)


if __name__ == '__main__':
    main()
