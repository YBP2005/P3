import os
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""12_abstain_causal.py — 弃权机制的因果实验（合成图，控制"每目标像素数"与"目标数"）

设计：在固定 1024×1024 画布上放置 N 个半径 r 的圆点（r 决定每目标像素数），
      网格 N ∈ {50,100,200,400,800} × r ∈ {2,4,8,16}，每格 20 张 → 400 张/臂
      再对每张用 base/over/under 三臂提问 → 得到 弃权率(N, r) 二维图谱
判据：若弃权率主要由 r（每目标像素数）决定而与 N 弱相关 → 证实"像素不足"机制

用法: python12_abstain_causal.py <arm> [workers]
输出: /root/abstain_results/causal_<arm>.csv
"""
import base64, csv, io, json, os, queue, random, re, sys, threading, time
import urllib.request

API = os.environ.get('LOCAL_API', 'http://127.0.0.1:8000/v1/chat/completions')
MODEL = os.environ.get('SERVED_MODEL', 'qwen3-vl-32b-awq')
OUT = os.environ.get('ABSTAIN_OUT', '/root/abstain_results')
os.makedirs(OUT, exist_ok=True)
random.seed(20260911)

P = {
    'base': '请数出图片中的圆形数量，不要遗漏，不要重复，以JSON格式输出：{"count": 数量}，只输出JSON。',
    'over': ('请数出图片中的圆形数量。为避免漏数，请把所有可能存在的圆形都计入；宁可多算，不可漏算。'
             '以JSON格式输出：{"count": 数量}，只输出JSON。'),
    'under': ('请数出图片中的圆形数量。请只统计你能完全确认的圆形；宁可漏算，不可多算。'
              '以JSON格式输出：{"count": 数量}，只输出JSON。'),
}
NS = [50, 100, 200, 400, 800]
RS = [2, 4, 8, 16]
PER_CELL = 20
W = H = 1024
_lock = threading.Lock()


def make_img(n, r, seed):
    from PIL import Image, ImageDraw
    rng = random.Random(seed)
    im = Image.new('RGB', (W, H), (235, 235, 235))
    d = ImageDraw.Draw(im)
    # 网格抖动放置，减少重叠
    k = int(n ** 0.5) + 1
    cell = W / k
    placed = 0
    for i in range(k):
        for j in range(k):
            if placed >= n:
                break
            cx = int((i + rng.uniform(0.2, 0.8)) * cell)
            cy = int((j + rng.uniform(0.2, 0.8)) * cell)
            cx = min(max(cx, r + 1), W - r - 2)
            cy = min(max(cy, r + 1), H - r - 2)
            d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(30, 60, 200))
            placed += 1
    return im


def call(im, prompt, timeout=180):
    b = io.BytesIO(); im.save(b, 'JPEG', quality=95)
    url = 'data:image/jpeg;base64,' + base64.b64encode(b.getvalue()).decode()
    payload = {'model': MODEL, 'messages': [{'role': 'user', 'content': [
        {'type': 'image_url', 'image_url': {'url': url}},
        {'type': 'text', 'text': prompt}]}], 'temperature': 0.0, 'max_tokens': 64}
    req = urllib.request.Request(API, data=json.dumps(payload).encode(),
                                 headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())['choices'][0]['message']['content']


def parse(raw):
    m = re.search(r'\{\s*(?:count|计数|数量)\s*[:：]\s*(\d+)', raw, re.I)
    if m:
        return int(m.group(1))
    m = re.search(r'-?\d+', raw.replace(',', ''))
    return int(m.group(0)) if m else None


def main():
    arm = sys.argv[1]
    workers = int(sys.argv[2]) if len(sys.argv) > 2 else 32
    out_csv = os.path.join(OUT, 'causal_%s.csv' % arm)
    done = set()
    if os.path.exists(out_csv):
        with open(out_csv, encoding='utf-8-sig', newline='') as f:
            for r in csv.DictReader(f):
                if r.get('parse_ok') == '1':
                    done.add(r['item'])
    cells = [(n, r, i) for n in NS for r in RS for i in range(PER_CELL)]
    todo = [(n, r, i) for (n, r, i) in cells
            if ('n%d_r%d_%d' % (n, r, i)) not in done]
    print('[causal/%s] 单元=%d 待跑=%d model=%s' % (arm, len(cells), len(todo), MODEL), flush=True)
    fh = open(out_csv, 'a', encoding='utf-8-sig', newline='')
    wr = csv.writer(fh)
    if not os.path.exists(out_csv) or os.path.getsize(out_csv) == 0:
        wr.writerow(['item', 'n', 'r', 'px_per_obj', 'pred', 'parse_ok', 'abstain', 'raw', 'latency_s'])
    q = queue.Queue()
    for x in todo:
        q.put(x)
    st = {'n': 0, 't0': time.time(), 'abst': 0}

    def work():
        while True:
            try:
                n, r, i = q.get_nowait()
            except queue.Empty:
                return
            item = 'n%d_r%d_%d' % (n, r, i)
            im = make_img(n, r, hash(item) & 0xffff)
            px_per_obj = (2 * r) ** 2
            t0 = time.time()
            try:
                raw = call(im, P[arm])
                pred = parse(raw)
                low = raw.lower()
                abst = 1 if (pred == 0 or any(k in low for k in
                             ['too many', '无法', '数不清', '难以', '众多', 'cannot'])) else 0
                with _lock:
                    wr.writerow([item, n, r, px_per_obj, pred if pred is not None else '',
                                 1 if pred is not None else 0, abst,
                                 raw.replace('\n', ' ')[:80], '%.2f' % (time.time() - t0)])
                    fh.flush()
                    st['abst'] += abst
            except Exception as ex:
                with _lock:
                    wr.writerow([item, n, r, px_per_obj, '', 0, 0, str(ex)[:80], '']); fh.flush()
            with _lock:
                st['n'] += 1
                if st['n'] % 50 == 0:
                    print('  %d/%d (%.2f img/s, abst=%d)' % (
                        st['n'], len(todo), st['n'] / max(time.time() - st['t0'], 1e-9), st['abst']), flush=True)

    ts = [threading.Thread(target=work, daemon=True) for _ in range(max(1, workers))]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    fh.close()
    print('[causal/%s] DONE' % arm, flush=True)


if __name__ == '__main__':
    main()
