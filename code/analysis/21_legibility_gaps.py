#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""21_legibility_gaps.py — 补两处已确认的可确证性曲线缺口

## 缺口一：r 档位断档
已有合成刺激只有 r ∈ {4,16}（causal/blur，1024 画布）与 r ∈ {18,40}（occl），
中间空档且 r∈{18,40} 那套弃权率饱和在 97.5%、L 完全不分辨（见
PaperB_可确证性得分与个数可分性_20260912.md §3 证据四）。
本实验补 r ∈ {6,10,24,32}，把 {4,6,10,16,24,32} 连成一条连续阶梯。

## 缺口二：对比度未独立操纵（GLM 明确要求）
GLM 建议的 Legibility Score 含 contrast 项，但现有刺激只操纵了模糊 sigma，
模糊与对比度退化不可分离。本实验在**固定 sigma** 下独立操纵对比度：
把圆点颜色按 alpha 向背景色插值（alpha=1 为原色，越小越接近背景），
alpha ∈ {1.0, 0.55, 0.25}，与 sigma ∈ {0,2} 做叉乘，
从而把"模糊"与"对比度"两个分量分开。

画法逐字复用 12_abstain_causal.py（背景 (235,235,235)、圆点 (30,60,200)、
k=int(sqrt(n))+1 格抖动），画布固定 1024、n 固定 300（与既有 occl 设计同口径）。

用法: python21_legibility_gaps.py <arm> [workers]
输出: $LEG_OUT/legigap_<arm>.csv   (默认 /root/legigap_results)
"""
import base64, csv, io, json, math, os, queue, random, re, sys, threading, time
import urllib.request

API = os.environ.get('LOCAL_API', 'http://127.0.0.1:8000/v1/chat/completions')
MODEL = os.environ.get('SERVED_MODEL', 'qwen3-vl-32b-awq')
OUT = os.environ.get('LEG_OUT', '/root/legigap_results')
os.makedirs(OUT, exist_ok=True)

P = {
    'base': '请数出图片中的圆形数量，不要遗漏，不要重复，以JSON格式输出：{"count": 数量}，只输出JSON。',
    'over': ('请数出图片中的圆形数量。为避免漏数，请把所有可能存在的圆形都计入；宁可多算，不可漏算。'
             '以JSON格式输出：{"count": 数量}，只输出JSON。'),
    'under': ('请数出图片中的圆形数量。请只统计你能完全确认的圆形；宁可漏算，不可多算。'
              '以JSON格式输出：{"count": 数量}，只输出JSON。'),
}

S = 1024
N = 300
RS = [4, 6, 10, 16, 24, 32]          # px_per_obj = 4r² = 64…4096
ALPHAS = [1.0, 0.55, 0.25]           # 对比度：向背景插值的比例
SIGMAS = [0.0, 2.0]
REPS = 8
BG = (235, 235, 235)
DOT = (30, 60, 200)
_lock = threading.Lock()


def make_img(n, r, alpha, sigma, seed, s=1024):
    from PIL import Image, ImageDraw, ImageFilter
    rng = random.Random(seed)
    fill = tuple(int(round(BG[c] + alpha * (DOT[c] - BG[c]))) for c in range(3))
    im = Image.new('RGB', (s, s), BG)
    d = ImageDraw.Draw(im)
    k = int(n ** 0.5) + 1
    cell = s / k
    placed = 0
    for i in range(k):
        for j in range(k):
            if placed >= n:
                break
            cx = int((i + rng.uniform(0.2, 0.8)) * cell)
            cy = int((j + rng.uniform(0.2, 0.8)) * cell)
            cx = min(max(cx, r + 1), s - r - 2)
            cy = min(max(cy, r + 1), s - r - 2)
            d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=fill)
            placed += 1
    if sigma > 0:
        im = im.filter(ImageFilter.GaussianBlur(sigma))
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
    arm = sys.argv[1] if len(sys.argv) > 1 else 'base'
    workers = int(sys.argv[2]) if len(sys.argv) > 2 else 24
    out_csv = os.path.join(OUT, 'legigap_%s.csv' % arm)
    done = set()
    if os.path.exists(out_csv):
        with open(out_csv, encoding='utf-8-sig', newline='') as f:
            for row in csv.DictReader(f):
                if row.get('parse_ok') == '1':
                    done.add(row['item'])

    cells = [(r, a, sg, i) for r in RS for a in ALPHAS for sg in SIGMAS for i in range(REPS)]
    def key(r, a, sg, i):
        return 'r%d_a%03d_s%.1f_%d' % (r, int(a * 100), sg, i)
    todo = [c for c in cells if key(*c) not in done]
    print('[leg/%s] 单元=%d 待跑=%d model=%s' % (arm, len(cells), len(todo), MODEL), flush=True)

    fh = open(out_csv, 'a', encoding='utf-8-sig', newline='')
    wr = csv.writer(fh)
    if not os.path.exists(out_csv) or os.path.getsize(out_csv) == 0:
        wr.writerow(['item', 'n', 'r', 'px_per_obj', 'alpha', 'sigma', 'coverage',
                     'pred', 'parse_ok', 'abstain', 'refuse', 'raw', 'latency_s'])
    q = queue.Queue()
    for c in todo:
        q.put(c)
    st = {'n': 0, 't0': time.time(), 'abst': 0}

    def work():
        while True:
            try:
                r, a, sg, i = q.get_nowait()
            except queue.Empty:
                return
            item = key(r, a, sg, i)
            im = make_img(N, r, a, sg, hash(item) & 0xffff, S)
            px = (2 * r) ** 2
            cov = N * math.pi * r * r / float(S * S)
            t0 = time.time()
            try:
                raw = call(im, P[arm])
                pred = parse(raw)
                low = raw.lower()
                ref = any(k in low for k in
                          ['too many', '无法', '数不清', '难以', '众多', 'cannot', '不确定'])
                if pred is None:
                    row = [item, N, r, px, a, sg, '%.4f' % cov, '', 0, 0,
                           1 if ref else 0, raw.replace('\n', ' ')[:100],
                           '%.2f' % (time.time() - t0)]
                else:
                    abst = 1 if (pred == 0 or ref) else 0
                    row = [item, N, r, px, a, sg, '%.4f' % cov, pred, 1, abst, 0,
                           raw.replace('\n', ' ')[:100], '%.2f' % (time.time() - t0)]
                with _lock:
                    wr.writerow(row); fh.flush(); st['abst'] += row[9]
            except Exception as ex:
                with _lock:
                    wr.writerow([item, N, r, px, a, sg, '%.4f' % cov, '', 0, 0, 0,
                                 str(ex)[:100], '']); fh.flush()
            with _lock:
                st['n'] += 1
                if st['n'] % 40 == 0:
                    print('  %d/%d (%.2f img/s, abst=%d)' % (
                        st['n'], len(todo), st['n'] / max(time.time() - st['t0'], 1e-9),
                        st['abst']), flush=True)

    ts = [threading.Thread(target=work, daemon=True) for _ in range(max(1, workers))]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    fh.close()
    print('[leg/%s] DONE' % arm, flush=True)


if __name__ == '__main__':
    main()
