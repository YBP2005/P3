#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""08_ext_vlm.py — 外部效度三数据集（5090 自建栈，三臂）

数据集: countbench | tallyqa | fsc147
用法: python08_ext_vlm.py --dataset countbench [--sample N] [--workers 32] [--out-dir /root/ext_results]
"""
import argparse, base64, csv, io, json, os, random, re, sys, threading, queue, time
import urllib.request

API = os.environ.get('LOCAL_API', 'http://127.0.0.1:8000/v1/chat/completions')
MODEL = os.environ.get('SERVED_MODEL', 'qwen3-vl-32b-awq')
ROOT = '/root/ext'
_lock = threading.Lock()

ARMS = ['base', 'over', 'under']


def build_prompt(arm, obj, question=None):
    if question:
        steer = {'base': '',
                 'over': '为避免漏数，请把所有可能出现的目标都计入（含被遮挡、模糊、只露出部分的）；宁可多算，不可漏算。',
                 'under': '请只统计你能完全确认的目标（轮廓清晰、无遮挡）；宁可漏算，不可多算。'}[arm]
        return '%s %s只输出一个阿拉伯数字，不要输出其他内容。' % (question.rstrip('?？'), steer)
    if arm == 'base':
        return '请数出图片中%s，不要遗漏，不要重复。以JSON格式输出：{"count": 数量}，只输出JSON。' % obj
    if arm == 'over':
        return ('请数出图片中%s。为避免漏数，请把所有可能存在的目标都计入'
                '（包括被遮挡、距离较远、画面模糊、只露出部分的个体）；宁可多算，不可漏算。'
                '以JSON格式输出：{"count": 数量}，只输出JSON。' % obj)
    return ('请数出图片中%s。请只统计你能完全确认的目标（轮廓清晰、无遮挡、可明确判断的个体）；'
            '宁可漏算，不可多算。以JSON格式输出：{"count": 数量}，只输出JSON。' % obj)


OBJ = {'countbench': '的目标数量', 'tallyqa': '的目标数量', 'fsc147': '的目标数量'}


def load_items(ds, sample=0, seed=20260910):
    items = []
    if ds == 'countbench':
        base = os.path.join(ROOT, 'countbench')
        for r in csv.DictReader(open(os.path.join(base, 'counts.csv'), encoding='utf-8-sig')):
            p = os.path.join(base, 'images', r['file'])
            if os.path.exists(p):
                items.append((r['file'], p, int(float(r['number'])), None))
    elif ds == 'tallyqa':
        base = os.path.join(ROOT, 'tallyqa')
        for r in csv.DictReader(open(os.path.join(base, 'qa.csv'), encoding='utf-8-sig')):
            p = os.path.join(base, 'images', r['file'])
            if os.path.exists(p):
                items.append((r['file'], p, int(float(r['groundtruth'])), r['question']))
    elif ds == 'fsc147':
        base = os.path.join(ROOT, 'fsc147')
        j = json.load(open(os.path.join(base, 'annotation_FSC147_384.json')))
        for k, v in j.items():
            fn = os.path.basename(k)
            p = os.path.join(base, 'images_384_VarV2', fn if fn.lower().endswith(('.jpg', '.png')) else fn + '.jpg')
            if os.path.exists(p):
                items.append((fn, p, len(v.get('points', [])), None))
    if sample and len(items) > sample:
        rng = random.Random(seed)
        bins = {}
        for it in items:
            g = it[2]
            key = 0 if g <= 1 else (1 if g <= 2 else (2 if g <= 5 else (3 if g <= 20 else (4 if g <= 100 else 5))))
            bins.setdefault(key, []).append(it)
        per = max(1, sample // max(1, len(bins)))
        picked = []
        for k in sorted(bins):
            v = bins[k][:]; rng.shuffle(v); picked += v[:per]
        rng.shuffle(picked)
        items = picked[:sample]
    return items


def enc(path):
    data = open(path, 'rb').read()
    if len(data) > 8 * 1024 * 1024:
        from PIL import Image
        im = Image.open(path).convert('RGB')
        w, h = im.size
        s = min(1.0, 2048 / max(w, h))
        im = im.resize((int(w * s), int(h * s)))
        b = io.BytesIO(); im.save(b, 'JPEG', quality=85); data = b.getvalue()
    return 'data:image/jpeg;base64,' + base64.b64encode(data).decode()


def call(path, prompt, timeout=180):
    payload = {'model': MODEL, 'messages': [{'role': 'user', 'content': [
        {'type': 'image_url', 'image_url': {'url': enc(path)}},
        {'type': 'text', 'text': prompt}]}], 'temperature': 0.0, 'max_tokens': 64}
    req = urllib.request.Request(API, data=json.dumps(payload).encode(),
                                 headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())['choices'][0]['message']['content']


def parse(raw):
    m = re.search(r'\{[^{}]*?(?:count|计数|数量|人数)\s*[:：]\s*(\d+)', raw, re.I)
    if m:
        return int(m.group(1))
    m = re.search(r'-?\d+\.?\d*', raw.replace(',', ''))
    try:
        return int(round(float(m.group(0)))) if m else None
    except Exception:
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dataset', required=True, choices=list(OBJ))
    ap.add_argument('--sample', type=int, default=0)
    ap.add_argument('--workers', type=int, default=32)
    ap.add_argument('--out-dir', default='/root/ext_results')
    a = ap.parse_args()
    os.makedirs(a.out_dir, exist_ok=True)
    items = load_items(a.dataset, a.sample)
    print('[ext:%s] %d 条 × %d 臂' % (a.dataset, len(items), len(ARMS)), flush=True)

    for arm in ARMS:
        out_csv = os.path.join(a.out_dir, 'ext_%s_%s.csv' % (a.dataset, arm))
        done = set()
        if os.path.exists(out_csv):
            with open(out_csv, encoding='utf-8-sig', newline='') as f:
                for r in csv.DictReader(f):
                    if r.get('parse_ok') == '1':
                        done.add(r['item'])
        todo = [x for x in items if x[0] not in done]
        exists = os.path.exists(out_csv)
        fh = open(out_csv, 'a', encoding='utf-8-sig', newline='')
        wr = csv.writer(fh)
        if not exists:
            wr.writerow(['item', 'gt', 'pred', 'parse_ok', 'abstain', 'raw', 'latency_s'])
        q = queue.Queue()
        for x in todo:
            q.put(x)
        st = {'n': 0, 't0': time.time(), 'abst': 0}

        def work():
            while True:
                try:
                    it = q.get_nowait()
                except queue.Empty:
                    return
                iid, path, gt, question = it
                prompt = build_prompt(arm, OBJ[a.dataset], question)
                t0 = time.time()
                try:
                    raw = call(path, prompt)
                    pred = parse(raw)
                    low = raw.lower()
                    abst = 1 if (pred == 0 or any(k in low for k in ['too many', '无法', '数不清', '难以', '众多'])) else 0
                    with _lock:
                        wr.writerow([iid, gt, pred if pred is not None else '',
                                     1 if pred is not None else 0, abst,
                                     raw.replace('\n', ' ')[:120], '%.2f' % (time.time() - t0)])
                        fh.flush()
                        st['abst'] += abst
                except Exception as ex:
                    with _lock:
                        wr.writerow([iid, gt, '', 0, 0, str(ex)[:100], '']); fh.flush()
                with _lock:
                    st['n'] += 1
        ts = [threading.Thread(target=work, daemon=True) for _ in range(max(1, a.workers))]
        for t in ts:
            t.start()
        for t in ts:
            t.join()
        fh.close()
        P_, T_ = [], []
        with open(out_csv, encoding='utf-8-sig', newline='') as f:
            for r in csv.DictReader(f):
                if r.get('parse_ok') == '1':
                    P_.append(int(float(r['pred']))); T_.append(int(float(r['gt'])))
        if P_:
            e = [p - g for p, g in zip(P_, T_)]
            mg = sum(T_) / len(T_)
            ok = [(p, g) for p, g in zip(P_, T_) if p != 0]
            me_k = sum(p - g for p, g in ok) / max(1, len(ok))
            mg_k = sum(g for _, g in ok) / max(1, len(ok))
            print('[ext:%s/%s] n=%d MAE=%.3f ME=%+.3f rho=%+.1f%% 零值率=%.1f%% | 排除后 ME=%+.3f rho=%+.1f%%' % (
                a.dataset, arm, len(e), sum(abs(x) for x in e) / len(e), sum(e) / len(e),
                100 * sum(e) / len(e) / mg, 100.0 * sum(1 for x in e if x == 0) / len(e),
                me_k, 100 * me_k / mg_k if mg_k else float('nan')), flush=True)


if __name__ == '__main__':
    main()
