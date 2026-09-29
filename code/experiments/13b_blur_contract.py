import os
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""13b_blur_contract.py — 决定性对照：模糊（歧义）是否才是弃权的触发条件

设计：与 12_abstain_causal.py 同网格，但叠加高斯模糊 σ ∈ {0, 1, 2, 4, 8} 像素。
     清晰点在 r=2px 时也不弃权（已验证 400/400），若模糊后出现弃权 → 歧义是触发条件。
用法: python13_abstain_blur.py <arm> [workers]
输出: /root/abstain_results/blur_<arm>.csv
"""
import base64, csv, io, json, os, queue, random, re, sys, threading, time
import urllib.request

API = os.environ.get('LOCAL_API', 'http://127.0.0.1:8000/v1/chat/completions')
MODEL = os.environ.get('SERVED_MODEL', 'qwen3-vl-32b-awq')
OUT = os.environ.get('ABSTAIN_OUT', '/root/blur_contract_results')
os.makedirs(OUT, exist_ok=True)

P = {
    'base': '请数出图片中的圆形数量，不要遗漏，不要重复，以JSON格式输出：{"count": 数量}，只输出JSON。',
    'over': ('请数出图片中的圆形数量。为避免漏数，请把所有可能存在的圆形都计入；宁可多算，不可漏算。'
             '以JSON格式输出：{"count": 数量}，只输出JSON。'),
    'under': ('请数出图片中的圆形数量。请只统计你能完全确认的圆形；宁可漏算，不可多算。'
              '以JSON格式输出：{"count": 数量}，只输出JSON。'),
    # ==== 以下由 A15 追加：契约臂（圆形版），与 probe_gen.py 的人数版本同构 ====
    'forbid0': ('请数出图片中的圆形数量，不要遗漏，不要重复。'
                '注意：**不要回答 0**；如果你认为可能是 0，请给出你最接近的估计值。'
                '以JSON格式输出：{"count": 数量}，只输出JSON。'),
    'choice': ('请从以下选项中选择最接近图片中圆形数量的选项：0, 100, 400, 800, 1600。'
               '以JSON格式输出：{"choice": 选项}，只输出JSON。'),
    'range': ('请估计图片中圆形数量的范围。'
              '以JSON格式输出：{"low": 下界, "high": 上界}，只输出JSON。'),
}
NS = [100, 400, 800]
RS = [2, 4, 8]
SIGMAS = [0.0, 1.0, 2.0, 4.0, 8.0]
PER_CELL = 15
W = H = 1024
_lock = threading.Lock()


def make_img(n, r, sigma, seed):
    from PIL import Image, ImageDraw, ImageFilter
    rng = random.Random(seed)
    im = Image.new('RGB', (W, H), (235, 235, 235))
    d = ImageDraw.Draw(im)
    k = int(n ** 0.5) + 1
    cell = W / k
    placed = 0
    for i in range(k):
        for j in range(k):
            if placed >= n:
                break
            cx = min(max(int((i + rng.uniform(0.2, 0.8)) * cell), r + 1), W - r - 2)
            cy = min(max(int((j + rng.uniform(0.2, 0.8)) * cell), r + 1), H - r - 2)
            d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(30, 60, 200))
            placed += 1
    if sigma > 0:
        im = im.filter(ImageFilter.GaussianBlur(radius=sigma))
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
    m = re.search(r'\{\s*(?:count|choice|计数|数量|选项)\s*[:：]\s*(\d+)', raw, re.I)
    if m:
        return int(m.group(1))
    m = re.search(r'-?\d+', raw.replace(',', ''))
    return int(m.group(0)) if m else None


def main():
    arm = sys.argv[1]
    workers = int(sys.argv[2]) if len(sys.argv) > 2 else 32
    out_csv = os.path.join(OUT, 'blur_%s.csv' % arm)
    done = set()
    if os.path.exists(out_csv):
        with open(out_csv, encoding='utf-8-sig', newline='') as f:
            for r in csv.DictReader(f):
                if r.get('parse_ok') == '1':
                    done.add(r['item'])
    cells = [(n, r, s, i) for n in NS for r in RS for s in SIGMAS for i in range(PER_CELL)]
    todo = [x for x in cells if ('n%d_r%d_s%.1f_%d' % x) not in done]
    print('[blur/%s] 单元=%d 待跑=%d model=%s' % (arm, len(cells), len(todo), MODEL), flush=True)
    fh = open(out_csv, 'a', encoding='utf-8-sig', newline='')
    wr = csv.writer(fh)
    if not os.path.exists(out_csv) or os.path.getsize(out_csv) == 0:
        wr.writerow(['item', 'n', 'r', 'sigma', 'pred', 'parse_ok', 'abstain', 'raw'])
    q = queue.Queue()
    for x in todo:
        q.put(x)
    st = {'n': 0, 't0': time.time(), 'abst': 0}

    def work():
        while True:
            try:
                n, r, s, i = q.get_nowait()
            except queue.Empty:
                return
            item = 'n%d_r%d_s%.1f_%d' % (n, r, s, i)
            im = make_img(n, r, s, abs(hash(item)) & 0xffff)
            try:
                raw = call(im, P[arm])
                pred = parse(raw)
                low = raw.lower()
                ab = 1 if (pred == 0 or any(k in low for k in
                           ['too many', '无法', '数不清', '难以', '众多', 'cannot'])) else 0
                with _lock:
                    wr.writerow([item, n, r, s, pred if pred is not None else '',
                                 1 if pred is not None else 0, ab, raw.replace('\n', ' ')[:80]])
                    fh.flush()
                    st['abst'] += ab
            except Exception as ex:
                with _lock:
                    wr.writerow([item, n, r, s, '', 0, 0, str(ex)[:60]]); fh.flush()
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
    print('[blur/%s] DONE' % arm, flush=True)


if __name__ == '__main__':
    main()
