#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""16_prompt_dose.py — 提示词强度"剂量-响应"曲线（7 档，从最宽松到最严格）

设计：把"弃权 ↔ 硬猜"做成连续可调控，量化"方向可控幅度 vs 提示强度"。
用法: python16_prompt_dose.py --ds st_a|ucf|visdrone [--workers 32]
输出: /root/dose_results/dose_<ds>.csv   （每图 7 档各一行）
"""
import argparse, base64, csv, io, json, os, re, sys, threading, queue, time
import urllib.request

API = os.environ.get('LOCAL_API', 'http://127.0.0.1:8000/v1/chat/completions')
MODEL = os.environ.get('SERVED_MODEL', 'qwen3-vl-32b-awq')
OUT = os.environ.get('DOSE_OUT', '/root/dose_results')
_lock = threading.Lock()
REFUSE = ['too many', '无法', '数不清', '难以', '众多', 'cannot']

# L1 最宽松 → L7 最严格
LEVELS = [
    ('L1_随便给', '图中大概有多少人？给个大致数字就行，以JSON格式输出：{"count": 数量}，只输出JSON。'),
    ('L2_只给数字', '图中有多少人？只输出一个阿拉伯数字。'),
    ('L3_可近似', '请估计图中的人数（允许近似），以JSON格式输出：{"count": 数量}，只输出JSON。'),
    ('L4_中性', '请数出图片中的人数（人群中的每个人头或人体），不要遗漏，不要重复，以JSON格式输出：{"count": 数量}，只输出JSON。'),
    ('L5_逐一点数', '请先逐一定位图中每个人头/人体，确认无重复无遗漏后再给出总人数，以JSON格式输出：{"count": 数量}，只输出JSON。'),
    ('L6_只算清晰', '请只统计你能清晰确认的人，不确定的不要计入，以JSON格式输出：{"count": 数量}，只输出JSON。'),
    ('L7_不确定就0', '请只统计你能 100% 确认的人；若无法确认，请在 count 中填 0。以JSON格式输出：{"count": 数量}，只输出JSON。'),
]


def load_items(ds):
    if ds == 'st_a':
        idir = '/root/dense/shanghaitech/images/part_A_test'
        gt = {}
        with open('/root/dense/shanghaitech/counts.csv', encoding='utf-8-sig') as f:
            for r in csv.DictReader(f):
                if r.get('part') == 'part_A' and r.get('split') == 'test':
                    gt[os.path.splitext(os.path.basename(r['file']))[0]] = int(r['count'])
        return idir, gt, '.jpg'
    if ds == 'ucf':
        idir = '/root/dense/ucf_qnrf/UCF-QNRF_ECCV18/Test'
        gt = {}
        with open('/root/dense/ucf_qnrf/counts.csv', encoding='utf-8-sig') as f:
            for r in csv.DictReader(f):
                if r['split'] == 'Test':
                    gt[os.path.splitext(os.path.basename(r['file']))[0]] = int(r['count'])
        return idir, gt, '.jpg'
    idir = '/root/aerial/visdrone/images'
    gt = {}
    with open('/root/aerial/gt_visdrone.csv', encoding='utf-8-sig') as f:
        for r in csv.DictReader(f):
            gt[r['item']] = int(r['gt'])
    return idir, gt, '.jpg'


def enc(path, max_pixels=1048576):
    from PIL import Image
    im = Image.open(path).convert('RGB')
    if im.size[0] * im.size[1] > max_pixels:
        s = (max_pixels / float(im.size[0] * im.size[1])) ** 0.5
        im = im.resize((max(1, int(im.size[0] * s)), max(1, int(im.size[1] * s))))
    b = io.BytesIO(); im.save(b, 'JPEG', quality=92)
    return base64.b64encode(b.getvalue()).decode()


def call(b64, prompt, timeout=180):
    payload = {'model': MODEL, 'messages': [{'role': 'user', 'content': [
        {'type': 'image_url', 'image_url': {'url': 'data:image/jpeg;base64,' + b64}},
        {'type': 'text', 'text': prompt}]}], 'temperature': 0.0, 'max_tokens': 64}
    req = urllib.request.Request(API, data=json.dumps(payload).encode(),
                                 headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())['choices'][0]['message']['content']


def parse(raw):
    m = re.search(r'\{\s*(?:count|计数|数量|人数)\s*[:：]\s*(\d+)', raw, re.I)
    if m:
        return int(m.group(1))
    m = re.search(r'-?\d+', raw.replace(',', ''))
    return int(m.group(0)) if m else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--ds', required=True, choices=['st_a', 'ucf', 'visdrone'])
    ap.add_argument('--workers', type=int, default=32)
    a = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    idir, gt, ext = load_items(a.ds)
    names = [n for n in sorted(gt) if os.path.exists(os.path.join(idir, n + ext))]
    out_csv = os.path.join(OUT, 'dose_%s.csv' % a.ds)
    done = set()
    if os.path.exists(out_csv):
        with open(out_csv, encoding='utf-8-sig', newline='') as f:
            for r in csv.DictReader(f):
                if r.get('parse_ok') == '1':
                    done.add((r['item'], r['level']))
    jobs = [(n, lv, pr) for n in names for lv, pr in LEVELS if (n, lv) not in done]
    print('[dose/%s] 图=%d 任务=%d model=%s' % (a.ds, len(names), len(jobs), MODEL), flush=True)
    fh = open(out_csv, 'a', encoding='utf-8-sig', newline='')
    wr = csv.writer(fh)
    if not os.path.exists(out_csv) or os.path.getsize(out_csv) == 0:
        wr.writerow(['item', 'level', 'gt', 'pred', 'parse_ok', 'zero', 'refuse', 'raw'])
    q = queue.Queue()
    for j in jobs:
        q.put(j)
    st = {'n': 0, 't0': time.time(), 'zero': 0}

    def work():
        while True:
            try:
                nm, lv, pr = q.get_nowait()
            except queue.Empty:
                return
            try:
                raw = call(enc(os.path.join(idir, nm + ext)), pr)
                pred = parse(raw)
                low = raw.lower()
                z = int(pred == 0) if pred is not None else 0
                with _lock:
                    wr.writerow([nm, lv, gt[nm], pred if pred is not None else '',
                                 1 if pred is not None else 0, z, 1 if any(k in low for k in REFUSE) else 0,
                                 raw.replace('\n', ' ')[:80]])
                    fh.flush()
                    st['zero'] += z
            except Exception as ex:
                with _lock:
                    wr.writerow([nm, lv, gt[nm], '', 0, 0, 0, str(ex)[:70]]); fh.flush()
            with _lock:
                st['n'] += 1
                if st['n'] % 200 == 0:
                    print('  %d/%d (%.2f img/s, zero=%d)' % (
                        st['n'], len(jobs), st['n'] / max(time.time() - st['t0'], 1e-9), st['zero']), flush=True)

    ts = [threading.Thread(target=work, daemon=True) for _ in range(max(1, a.workers))]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    fh.close()
    # 每档汇总
    import statistics
    print('[dose/%s] 汇总:' % a.ds)
    rows = list(csv.DictReader(open(out_csv, encoding='utf-8-sig')))
    for lv, _ in LEVELS:
        sub = [(int(float(r['gt'])), int(float(r['pred'])), int(r['zero'])) for r in rows
               if r['level'] == lv and r.get('parse_ok') == '1']
        if not sub:
            continue
        mg = sum(g for g, _, _ in sub) / len(sub)
        me = sum(p - g for g, p, _ in sub) / len(sub)
        z = 100.0 * sum(z for _, _, z in sub) / len(sub)
        print('   %-14s n=%d ME=%+.2f rho=%+.1f%% 零回答率=%.1f%%' % (lv, len(sub), me, 100 * me / mg, z), flush=True)


if __name__ == '__main__':
    main()
