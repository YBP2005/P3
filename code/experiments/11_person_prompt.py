import os
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""11_person_prompt.py — 原版口径实验：用"数出图中人数"的提示词打 person(class 0) 目标

意义：清洗版只保留"头部"目标（helmet / head+blur_head），原版的 class 0 = person（整人）
     被丢弃。本实验检验**目标定义（头部 vs 整人）是否改变 VLM 的方向结论**。

图像集：清洗版 12066 + 仅原版有的 306 张 = 12372
GT：原版 class 0（person）
用法：python11_person_prompt.py <base|over|under> [workers]
输出：/root/person_results/person_<arm>.csv
"""
import base64, csv, io, json, os, queue, re, sys, threading, time
import urllib.request

API = os.environ.get('LOCAL_API', 'http://127.0.0.1:8000/v1/chat/completions')
MODEL = os.environ.get('SERVED_MODEL', 'qwen3-vl-32b-awq')
IMG_DIRS = ['/root/sfchd_full/images', '/root/orig_eval/extra_images']
GT_CSV = '/root/orig_eval/gt_original.csv'
OUT_DIR = os.environ.get('PERSON_OUT', '/root/person_results')
os.makedirs(OUT_DIR, exist_ok=True)

PROMPTS = {
    'base': ('请数出图片中的人员数量（每个人，包括被遮挡或只露出部分身体的人），不要遗漏，不要重复，'
             '以JSON格式输出：{"count": 数量}，只输出JSON。'),
    'over': ('请数出图片中的人员数量。为避免漏数，请把所有可能存在的人员都计入'
             '（包括被遮挡、距离较远、画面模糊、只露出部分身体的人）；宁可多算，不可漏算。'
             '以JSON格式输出：{"count": 数量}，只输出JSON。'),
    'under': ('请数出图片中的人员数量。请只统计你能完全确认的人员'
              '（轮廓清晰、无遮挡、可明确判断的个体）；宁可漏算，不可多算。'
              '以JSON格式输出：{"count": 数量}，只输出JSON。'),
}
_lock = threading.Lock()


def find_img(stem):
    for d in IMG_DIRS:
        for ext in ('.jpg', '.png'):
            p = os.path.join(d, stem + ext)
            if os.path.exists(p):
                return p
    return None


def enc(path, limit):
    data = open(path, 'rb').read()
    if len(data) > limit:
        from PIL import Image
        im = Image.open(path).convert('RGB')
        w, h = im.size
        s = min(1.0, 2048 / max(w, h))
        im = im.resize((int(w * s), int(h * s)))
        b = io.BytesIO(); im.save(b, 'JPEG', quality=85); data = b.getvalue()
    return 'data:image/jpeg;base64,' + base64.b64encode(data).decode()


def call(path, prompt, timeout=180):
    payload = {'model': MODEL, 'messages': [{'role': 'user', 'content': [
        {'type': 'image_url', 'image_url': {'url': enc(path, 8 * 1024 * 1024)}},
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
    arm = sys.argv[1]
    workers = int(sys.argv[2]) if len(sys.argv) > 2 else 32
    gt = {}
    with open(GT_CSV, encoding='utf-8-sig') as f:
        for r in csv.DictReader(f):
            gt[r['item']] = int(r['person'])
    names = [n for n in sorted(gt) if find_img(n)]
    out_csv = os.path.join(OUT_DIR, 'person_%s.csv' % arm)
    done = set()
    if os.path.exists(out_csv):
        with open(out_csv, encoding='utf-8-sig', newline='') as f:
            for r in csv.DictReader(f):
                if r.get('parse_ok') == '1':
                    done.add(r['item'])
    todo = [x for x in names if x not in done]
    print('[person/%s] total=%d done=%d todo=%d model=%s' % (arm, len(names), len(done), len(todo), MODEL), flush=True)
    fh = open(out_csv, 'a', encoding='utf-8-sig', newline='')
    wr = csv.writer(fh)
    if not os.path.exists(out_csv) or os.path.getsize(out_csv) == 0:
        wr.writerow(['item', 'gt', 'pred', 'parse_ok', 'abstain', 'raw', 'latency_s'])
    q = queue.Queue()
    for x in todo:
        q.put(x)
    st = {'n': 0, 'fail': 0, 'abst': 0, 't0': time.time()}

    def work():
        while True:
            try:
                nm = q.get_nowait()
            except queue.Empty:
                return
            p = find_img(nm)
            if p is None:
                continue
            t0 = time.time()
            try:
                raw = call(p, PROMPTS[arm])
                pred = parse(raw)
                low = raw.lower()
                abst = 1 if (pred == 0 or any(k in low for k in ['too many', '无法', '数不清', '难以', '众多'])) else 0
                with _lock:
                    wr.writerow([nm, gt[nm], pred if pred is not None else '',
                                 1 if pred is not None else 0, abst, raw.replace('\n', ' ')[:120],
                                 '%.2f' % (time.time() - t0)])
                    fh.flush()
                    st['abst'] += abst
            except Exception as ex:
                with _lock:
                    st['fail'] += 1
                    wr.writerow([nm, gt[nm], '', 0, 0, str(ex)[:100], '']); fh.flush()
            with _lock:
                st['n'] += 1
                if st['n'] % 1000 == 0:
                    el = time.time() - st['t0']
                    print('[person/%s] %d/%d (%.2f img/s) fail=%d abst=%d' % (
                        arm, st['n'], len(todo), st['n'] / max(el, 1e-9), st['fail'], st['abst']), flush=True)

    ts = [threading.Thread(target=work, daemon=True) for _ in range(max(1, workers))]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    fh.close()
    P_, T_, A_ = [], [], 0
    with open(out_csv, encoding='utf-8-sig', newline='') as f:
        for r in csv.DictReader(f):
            if r.get('parse_ok') == '1':
                P_.append(int(float(r['pred']))); T_.append(int(float(r['gt'])))
                A_ += int(float(r.get('abstain') or 0))
    if P_:
        e = [p - g for p, g in zip(P_, T_)]
        mg = sum(T_) / len(T_)
        keep = [(p, g) for p, g in zip(P_, T_) if p != 0]
        print('[person/%s] n=%d MAE=%.4f ME=%+.4f rho=%+.1f%% EM=%.4f P(over)=%.4f | 弃权率=%.2f%% | 排除后 ME=%+.4f' % (
            arm, len(e), sum(abs(x) for x in e) / len(e), sum(e) / len(e),
            100 * sum(e) / len(e) / mg, sum(1 for x in e if abs(x) < 0.5) / len(e),
            sum(1 for x in e if x > 0) / len(e), 100.0 * A_ / len(P_),
            sum(p - g for p, g in keep) / max(1, len(keep))), flush=True)


if __name__ == '__main__':
    main()
