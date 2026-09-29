#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""22_tier2.py — PaperB Tier 2 合成实验（三合一）

用法：python22_tier2.py <exp> <arm> [workers]
  exp = legigrid   T2-1 ⭐ 把可确证性网格推进到"base 臂也弃权"的低像素区
  exp = occlkind   T2-3 ⭐ 区分"实例可辨性"(感知) 与"模态补全推理"
  exp = entknob    T2-4   提示强度/可确证性能否"撬开"输出熵

输出：$T2_OUT/<exp>_<arm>.csv（默认 /root/t2_results）
与 20/21 号脚本同源的画法（背景 235、圆点 (30,60,200)、sqrt(n) 格抖动），保持可比。
"""
import base64, csv, io, json, math, os, queue, random, re, sys, threading, time
import urllib.request

API = os.environ.get('LOCAL_API', 'http://127.0.0.1:8000/v1/chat/completions')
MODEL = os.environ.get('SERVED_MODEL', 'internvl25-8b-awq')
OUT = os.environ.get('T2_OUT', '/root/t2_results')
os.makedirs(OUT, exist_ok=True)

P = {
    'base': '请数出图片中的圆形数量，不要遗漏，不要重复，以JSON格式输出：{"count": 数量}，只输出JSON。',
    'over': ('请数出图片中的圆形数量。为避免漏数，请把所有可能存在的圆形都计入；宁可多算，不可漏算。'
             '以JSON格式输出：{"count": 数量}，只输出JSON。'),
    'under': ('请数出图片中的圆形数量。请只统计你能完全确认的圆形；宁可漏算，不可多算。'
              '以JSON格式输出：{"count": 数量}，只输出JSON。'),
}
BG = (235, 235, 235); DOT = (30, 60, 200); OCC = (120, 120, 120)
S = 1024
_lock = threading.Lock()


def make_dots(n, r, seed, s=S, jitter=True, occ_box=None):
    """与 20/21 号脚本同源；jitter=False 时用严格栅格（供 T2-3 的"可推断"条件）"""
    from PIL import Image, ImageDraw
    rng = random.Random(seed)
    im = Image.new('RGB', (s, s), BG)
    d = ImageDraw.Draw(im)
    k = int(n ** 0.5) + 1
    cell = s / k
    placed = 0
    pos = []
    for i in range(k):
        for j in range(k):
            if placed >= n:
                break
            if jitter:
                cx = int((i + rng.uniform(0.2, 0.8)) * cell)
                cy = int((j + rng.uniform(0.2, 0.8)) * cell)
            else:
                cx = int((i + 0.5) * cell)
                cy = int((j + 0.5) * cell)
            cx = min(max(cx, r + 1), s - r - 2)
            cy = min(max(cy, r + 1), s - r - 2)
            pos.append((cx, cy, r))
            placed += 1
    if occ_box:
        x0, y0, x1, y1 = occ_box
        for (cx, cy, r_) in pos:
            if x0 - r_ <= cx <= x1 + r_ and y0 - r_ <= cy <= y1 + r_:
                continue                      # 被遮挡的不画
            d.ellipse([cx - r_, cy - r_, cx + r_, cy + r_], fill=DOT)
        d.rectangle([x0, y0, x1, y1], fill=OCC)
    else:
        for (cx, cy, r_) in pos:
            d.ellipse([cx - r_, cy - r_, cx + r_, cy + r_], fill=DOT)
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


# ---------------- 三个实验的单元定义 ----------------
OCC = (int(S * 0.36), int(S * 0.36), int(S * 0.64), int(S * 0.64))   # 中央遮挡块（28% 面积）


def cells_legigrid():
    """T2-1：r∈{2,3}（px/obj 16,36）、σ∈{0,2,4,8}、n∈{150,300,600}，alpha=1，画布 1024"""
    out = []
    for r in (2, 3):
        for sg in (0.0, 2.0, 4.0, 8.0):
            for n in (150, 300, 600):
                for i in range(8):
                    out.append(('%s|r%d_s%g_n%d_%d' % ('lg', r, sg, n, i),
                                dict(r=r, sigma=sg, n=n, cond='-')))
    return out


def cells_occlkind():
    """T2-3：三条件 × n∈{100,400} × 10 重复
       lattice_infer : 严格栅格 + 遮挡 → 被遮位置可由周期性推断
       jitter_hide   : 抖动 + 同位置遮挡 → 被遮位置不可推断
       lattice_clear : 严格栅格、不遮挡（对照）
    """
    out = []
    for cond in ('lattice_clear', 'lattice_infer', 'jitter_hide'):
        for n in (100, 400):
            for i in range(10):
                out.append(('%s|%s_n%d_%d' % ('ok', cond, n, i),
                            dict(r=6, sigma=0.0, n=n, cond=cond)))
    return out


def cells_entknob():
    """T2-4：三个可确证性档（r∈{3,4,8}，σ=2 固定，n=300）× 20 重复"""
    out = []
    for r in (3, 4, 8):
        for i in range(20):
            out.append(('%s|r%d_%d' % ('ek', r, i), dict(r=r, sigma=2.0, n=300, cond='-')))
    return out


BUILD = {'legigrid': cells_legigrid, 'occlkind': cells_occlkind, 'entknob': cells_entknob}


def render(exp, item, meta):
    seed = hash(item) & 0xffff
    if exp == 'legigrid':
        r = meta['r']
        im = make_dots(meta['n'], r, seed)
        if meta['sigma'] > 0:
            from PIL import ImageFilter
            im = im.filter(ImageFilter.GaussianBlur(meta['sigma']))
        return im, meta['n']
    if exp == 'occlkind':
        cond = meta['cond']
        jitter = (cond == 'jitter_hide')
        occ = None if cond == 'lattice_clear' else OCC
        im = make_dots(meta['n'], meta['r'], seed, jitter=jitter, occ_box=occ)
        return im, meta['n']
    if exp == 'entknob':
        from PIL import ImageFilter
        im = make_dots(meta['n'], meta['r'], seed).filter(ImageFilter.GaussianBlur(meta['sigma']))
        return im, meta['n']
    raise SystemExit('未知 exp')


def main():
    exp = sys.argv[1]
    arm = sys.argv[2]
    workers = int(sys.argv[3]) if len(sys.argv) > 3 else 20
    out_csv = os.path.join(OUT, '%s_%s.csv' % (exp, arm))
    done = set()
    if os.path.exists(out_csv):
        with open(out_csv, encoding='utf-8-sig', newline='') as f:
            for r in csv.DictReader(f):
                if r.get('parse_ok') == '1':
                    done.add(r['item'])
    cells = BUILD[exp]()
    todo = [c for c in cells if c[0] not in done]
    print('[t2/%s/%s] 单元=%d 待跑=%d model=%s' % (exp, arm, len(cells), len(todo), MODEL), flush=True)
    fh = open(out_csv, 'a', encoding='utf-8-sig', newline='')
    wr = csv.writer(fh)
    if not os.path.exists(out_csv) or os.path.getsize(out_csv) == 0:
        wr.writerow(['item', 'exp', 'cond', 'n', 'r', 'sigma', 'px_per_obj',
                     'pred', 'parse_ok', 'abstain', 'refuse', 'raw', 'latency_s'])
    q = queue.Queue()
    for c in todo:
        q.put(c)
    st = {'n': 0, 't0': time.time(), 'abst': 0}

    def work():
        while True:
            try:
                item, meta = q.get_nowait()
            except queue.Empty:
                return
            try:
                im, gt = render(exp, item, meta)
            except Exception as ex:
                with _lock:
                    wr.writerow([item, exp, meta.get('cond', ''), meta.get('n'), meta.get('r'),
                                 meta.get('sigma'), 4 * meta['r'] ** 2, '', 0, 0, 0,
                                 'render_err:%s' % str(ex)[:60], '']); fh.flush()
                continue
            t0 = time.time()
            try:
                raw = call(im, P[arm])
                pred = parse(raw)
                low = raw.lower()
                ref = any(k in low for k in ('无法', '不能', '难以', '不确定', '数不清', '看不清'))
                if pred is None:
                    row = [item, exp, meta.get('cond', ''), meta.get('n'), meta.get('r'),
                           meta.get('sigma'), 4 * meta['r'] ** 2, '', 0, 0, 1 if ref else 0,
                           raw.replace('\n', ' ')[:100], '%.2f' % (time.time() - t0)]
                else:
                    abst = 1 if (pred == 0 or ref) else 0
                    row = [item, exp, meta.get('cond', ''), meta.get('n'), meta.get('r'),
                           meta.get('sigma'), 4 * meta['r'] ** 2, pred, 1, abst, 0,
                           raw.replace('\n', ' ')[:100], '%.2f' % (time.time() - t0)]
                with _lock:
                    wr.writerow(row); fh.flush(); st['abst'] += row[9]
            except Exception as ex:
                with _lock:
                    wr.writerow([item, exp, meta.get('cond', ''), meta.get('n'), meta.get('r'),
                                 meta.get('sigma'), 4 * meta['r'] ** 2, '', 0, 0, 0,
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
    print('[t2/%s/%s] DONE' % (exp, arm), flush=True)


if __name__ == '__main__':
    main()
