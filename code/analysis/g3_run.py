#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""g3_run.py — G3（第三方可复跑的协议外验）的运行器。

冻结判据：/root/g3_criteria_frozen.json（启动时断言 md5；三臂提示词逐字比对；
TallyQA 的"最小改写"模板逐字比对）。
仪器：`19f_probe_ablation.py`（md5 28e82b20a7f468680da11b2e9855cff9）由 importlib 载入，
      `parse()` / `b64_of()` / `call_img()` **逐字复用**；英文契约句取自 `20b_probe_lang.py`
      （md5 77385964ee28d6bf26b8a2a3dcca1975），其 md5 亦断言。

用法：PORT=8012 FAMILY=Qwen2.5-VL-3B-Instruct python3 g3_run.py
输出：/root/g3_res/g3_<FAMILY>.csv（断点续跑：(family,domain,item,arm) 已完成则跳过）
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
CRIT = '/root/g3_criteria_frozen.json'
CRIT_MD5 = '4a0b57073515698911775374c554d472'
PORT = os.environ.get('PORT', '8012')
FAMILY = os.environ.get('FAMILY', '')
N_ITEM = 300
JHU_IMG = '/root/g3_corpora/jhu/images'
JHU_LAB = '/root/g3_corpora/jhu/image_labels.txt'
TQ = '/root/g3_corpora/tallyqa/tallyQA_short.parquet'
OUT = '/root/g3_res'
ARMS = ['base', 'permit', 'channel']
os.makedirs(OUT, exist_ok=True)
os.environ.setdefault('BAILIAN_API', 'http://127.0.0.1:%s/v1/chat/completions' % PORT)
os.environ.setdefault('DASHSCOPE_API_KEY', 'EMPTY')


def load(path, want):
    got = hashlib.md5(open(path, 'rb').read()).hexdigest()
    assert got == want, '%s md5 不符：%s' % (path, got)
    spec = importlib.util.spec_from_file_location(os.path.basename(path)[:-3], path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def jhu_items():
    rows = [l.strip().split(',') for l in io.open(JHU_LAB, encoding='utf-8') if l.strip()]
    gt = {r[0]: int(r[1]) for r in rows if len(r) >= 2 and r[1].isdigit()}
    out = []
    for f in sorted(os.listdir(JHU_IMG)):
        if not f.lower().endswith(('.jpg', '.jpeg', '.png')):
            continue
        key = os.path.splitext(f)[0]
        if key in gt:
            out.append((key, os.path.join(JHU_IMG, f), gt[key]))
    return out[:N_ITEM]


def tq_items():
    import pandas as pd
    from PIL import Image
    df = pd.read_parquet(TQ)
    out = []
    for i in range(len(df)):
        g = str(df['groundtruth'].iloc[i]).strip()
        if not g.lstrip('-').isdigit():
            continue
        q = str(df['question'].iloc[i]).strip()
        raw = df['image'].iloc[i]
        b = raw.get('bytes') if isinstance(raw, dict) else raw
        if b is None:
            continue
        out.append((i, b, int(g), q))
        if len(out) >= N_ITEM:
            break
    return out


def main():
    M = load(PROBE, PROBE_MD5)
    L = load(LANG, LANG_MD5)
    b = open(CRIT, 'rb').read()
    got = hashlib.md5(b).hexdigest()
    assert got == CRIT_MD5, '冻结件 md5 变了：%s != %s' % (got, CRIT_MD5)
    J = json.loads(b.decode('utf-8'))
    for a, p in J['prompts_verbatim'].items():
        assert M.P[a] == p, '中文臂 %s 与冻结件不一致' % a
    for _a in ARMS:
        _tpl = J['tallyqa_arm_adaptation_★']['templates'][_a]
        _want = '{q} ' + L.EN[_a].split('. ', 1)[1]
        assert _tpl == _want, 'EN %s 的契约句与冻结件不同源' % _a
    print('[g3] 冻结件 md5 OK：%s ｜ family=%s ｜ port=%s' % (got, FAMILY, PORT), flush=True)
    assert FAMILY, '必须给 FAMILY'

    jh = jhu_items()
    tq = tq_items()
    print('[g3] JHU 项 %d ｜ TallyQA 项 %d' % (len(jh), len(tq)), flush=True)
    jobs = [('jhu', it, {'path': p}, g, a, None) for it, p, g in jh for a in ARMS]
    jobs += [('tallyqa', str(i), {'bytes': bb}, g, a, q) for i, bb, g, q in tq for a in ARMS]

    out_csv = os.path.join(OUT, 'g3_%s.csv' % FAMILY.replace('/', '_'))
    done = set()
    if os.path.exists(out_csv):
        for r in csv.DictReader(open(out_csv, encoding='utf-8-sig')):
            if (r.get('http_err') or '0') == '0' and (r.get('raw') or '') != '':
                done.add((r['domain'], r['item'], r['arm']))
    jobs = [j for j in jobs if (j[0], j[1], j[4]) not in done]
    new = not os.path.exists(out_csv) or os.path.getsize(out_csv) == 0
    fh = open(out_csv, 'a', encoding='utf-8-sig', newline='')
    wr = csv.writer(fh)
    if new:
        wr.writerow(['family', 'domain', 'item', 'arm', 'gt', 'pred', 'parse_ok', 'abstain',
                     'http_err', 'raw'])
    print('[g3/%s] 待跑 %d 项（已完成 %d）' % (FAMILY, len(jobs), len(done)), flush=True)
    if not jobs:
        fh.close(); return
    q_ = queue.Queue()
    for j in jobs:
        q_.put(j)
    st = {'n': 0, 'tot': len(jobs), 't0': time.time(), 'bad': 0, 'e': 0}
    lk = threading.Lock()
    from PIL import Image

    def work():
        while True:
            try:
                dom, it, src, g, arm, question = q_.get_nowait()
            except queue.Empty:
                return
            pred, ok, err, raw = None, 0, 0, ''
            try:
                if 'path' in src:
                    im = Image.open(src['path']).convert('RGB')
                else:
                    im = Image.open(io.BytesIO(src['bytes'])).convert('RGB')
                prompt = M.P[arm] if dom == 'jhu' else (
                    J['tallyqa_arm_adaptation_★']['templates'][arm].replace('{q}', question))
                raw = M.call_img(M.b64_of(im), prompt, FAMILY)
                pred = M.parse(raw)
                ok = 1 if pred is not None else 0
            except Exception as ex:
                raw = 'ERR %s' % str(ex)[:160]
                if '400' in str(ex)[:60]:
                    err = 1
            with lk:
                wr.writerow([FAMILY, dom, it, arm, g, '' if pred is None else pred, ok,
                             1 if pred == 'abstain' else 0, err, raw.replace('\n', ' ')[:300]])
                fh.flush()
                st['n'] += 1; st['bad'] += 0 if ok else 1; st['e'] += err
                if st['n'] % 200 == 0:
                    el = max(time.time() - st['t0'], 1e-9)
                    print('  %d/%d (%.2f/s bad=%d err=%d)' % (st['n'], st['tot'], st['n'] / el,
                                                              st['bad'], st['e']), flush=True)

    th = [threading.Thread(target=work, daemon=True) for _ in range(8)]
    for t in th:
        t.start()
    for t in th:
        t.join()
    fh.close()
    print('[g3/%s] DONE n=%d unparsed=%d err=%d' % (FAMILY, st['n'], st['bad'], st['e']), flush=True)


if __name__ == '__main__':
    main()
