#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""20_decouple_count.py — 判决性实验：把"目标个数"与"拥挤/覆盖率"解耦

## 要回答的问题
昨天（P1 #5 可确证性得分）发现：现有全部数据里，"个数 n"与"覆盖率/拥挤"或
"图像面积"机械共线，**不可识别**。因此在现有数据上无法判定弃权究竟响应
"数量本身"还是响应"数量所导致的每实例可确证性"。

## 设计（两条腿，唯一差别是画布是否随 n 同缩放）
用 1024 画布上的网格抖动圆点（与 12_abstain_causal.py 逐字相同的画法：
背景 (235,235,235)、圆点 (30,60,200)、k=int(sqrt(n))+1 格抖动），
固定 r=8（故 px_per_obj=(2r)²=256 恒定），n ∈ {200,400,800}：

- **腿 A（固定画布，对照臂）**：S=1024 恒定 → 覆盖率 ∝ n（3.8% → 7.7% → 15.3%）
  这是原设计的行为，n 与拥挤同时变。
- **腿 B（同缩放画布，解耦臂）**：S(n) = 512·sqrt(n/200) → 512 / 724 / 1024
  此时 px_per_obj 与**覆盖率同时恒定**（15.3%），只有 n 在变。

## 判据
- 若腿 A 的弃权率随 n 上升、而**腿 B 不上升** → 弃权由**拥挤**驱动，与"个数"无关，
  论文"弃权率与个数无关"可在控制可确证性后成立（需改写为条件性表述）。
- 若腿 B 的弃权率**仍随 n 上升** → 存在独立的计数负荷效应，论文必须承认双因素。

## 服务端重采样约束（重要）
32B 的 vLLM 设了 --mm-processor-kwargs max_pixels=1048576(=1024²)、min_pixels=200704(≈448²)。
故本设计把画布限制在 [512, 1024] 内，**绝不会触发服务端缩放**，px_per_obj 在特征上真实恒定。
（InternVL 侧未设 max_pixels，同样安全。）

用法: python20_decouple_count.py <arm> [workers]
输出: $DEC_OUT/decouple_<arm>.csv   (默认 /root/decouple_results)
"""
import base64, csv, io, json, math, os, queue, random, re, sys, threading, time
import urllib.request

API = os.environ.get('LOCAL_API', 'http://127.0.0.1:8000/v1/chat/completions')
MODEL = os.environ.get('SERVED_MODEL', 'qwen3-vl-32b-awq')
OUT = os.environ.get('DEC_OUT', '/root/decouple_results')
os.makedirs(OUT, exist_ok=True)

P = {
    'base': '请数出图片中的圆形数量，不要遗漏，不要重复，以JSON格式输出：{"count": 数量}，只输出JSON。',
    'over': ('请数出图片中的圆形数量。为避免漏数，请把所有可能存在的圆形都计入；宁可多算，不可漏算。'
             '以JSON格式输出：{"count": 数量}，只输出JSON。'),
    'under': ('请数出图片中的圆形数量。请只统计你能完全确认的圆形；宁可漏算，不可多算。'
              '以JSON格式输出：{"count": 数量}，只输出JSON。'),
}

R = 8                      # 半径固定 → px_per_obj = 256 恒定
NS = [200, 400, 800]
REPS = 20
BG = (235, 235, 235)
DOT = (30, 60, 200)
_lock = threading.Lock()


def side_for(leg, n):
    """腿 A 固定 1024；腿 B 按 sqrt(n) 缩放，使覆盖率恒定在 n=200 时的值"""
    if leg == 'fixed':
        return 1024
    s = 512.0 * math.sqrt(n / 200.0)
    return int(round(s / 8.0) * 8)


def make_img(n, r, seed, S):
    """与 12_abstain_causal.py 完全相同的画法，仅把画布边长参数化"""
    from PIL import Image, ImageDraw
    rng = random.Random(seed)
    im = Image.new('RGB', (S, S), BG)
    d = ImageDraw.Draw(im)
    k = int(n ** 0.5) + 1
    cell = S / k
    placed = 0
    for i in range(k):
        for j in range(k):
            if placed >= n:
                break
            cx = int((i + rng.uniform(0.2, 0.8)) * cell)
            cy = int((j + rng.uniform(0.2, 0.8)) * cell)
            cx = min(max(cx, r + 1), S - r - 2)
            cy = min(max(cy, r + 1), S - r - 2)
            d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=DOT)
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
    arm = sys.argv[1] if len(sys.argv) > 1 else 'base'
    workers = int(sys.argv[2]) if len(sys.argv) > 2 else 24
    out_csv = os.path.join(OUT, 'decouple_%s.csv' % arm)
    done = set()
    if os.path.exists(out_csv):
        with open(out_csv, encoding='utf-8-sig', newline='') as f:
            for row in csv.DictReader(f):
                if row.get('parse_ok') == '1':
                    done.add(row['item'])

    cells = []
    for leg in ('fixed', 'scaled'):
        for n in NS:
            for i in range(REPS):
                S = side_for(leg, n)
                cells.append((leg, n, i, S))
    todo = [c for c in cells if ('%s_n%d_%d' % (c[0], c[1], c[2])) not in done]
    print('[dec/%s] 单元=%d 待跑=%d model=%s' % (arm, len(cells), len(todo), MODEL), flush=True)

    fh = open(out_csv, 'a', encoding='utf-8-sig', newline='')
    wr = csv.writer(fh)
    if not os.path.exists(out_csv) or os.path.getsize(out_csv) == 0:
        wr.writerow(['item', 'leg', 'n', 'r', 'canvas', 'px_per_obj', 'coverage',
                     'pred', 'parse_ok', 'abstain', 'refuse', 'raw', 'latency_s'])
    q = queue.Queue()
    for c in todo:
        q.put(c)
    st = {'n': 0, 't0': time.time(), 'abst': 0}

    def work():
        while True:
            try:
                leg, n, i, S = q.get_nowait()
            except queue.Empty:
                return
            item = '%s_n%d_%d' % (leg, n, i)
            im = make_img(n, R, hash(item) & 0xffff, S)
            px_per_obj = (2 * R) ** 2
            cov = n * math.pi * R * R / float(S * S)
            t0 = time.time()
            try:
                raw = call(im, P[arm])
                pred = parse(raw)
                low = raw.lower()
                refine = any(k in low for k in
                             ['too many', '无法', '数不清', '难以', '众多', 'cannot', '不确定'])
                if pred is None:
                    wr_row = [item, leg, n, R, S, px_per_obj, '%.4f' % cov, '',
                              0, 0, 1 if refine else 0, raw.replace('\n', ' ')[:100],
                              '%.2f' % (time.time() - t0)]
                else:
                    abst = 1 if (pred == 0 or refine) else 0
                    wr_row = [item, leg, n, R, S, px_per_obj, '%.4f' % cov, pred,
                              1, abst, 0, raw.replace('\n', ' ')[:100],
                              '%.2f' % (time.time() - t0)]
                with _lock:
                    wr.writerow(wr_row); fh.flush()
                    st['abst'] += wr_row[9]
            except Exception as ex:
                with _lock:
                    wr.writerow([item, leg, n, R, S, px_per_obj, '%.4f' % cov, '',
                                 0, 0, 0, str(ex)[:100], '']); fh.flush()
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
    print('[dec/%s] DONE' % arm, flush=True)


if __name__ == '__main__':
    main()
