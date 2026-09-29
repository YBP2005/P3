#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""18_occl_blur.py — 遮挡 × 模糊 析因实验（合成图，2×2 解耦设计）

动机：此前只有单因子证据——切块（去遮挡）在人群域有效、在航拍域收益有限；模糊在受控实验里强驱动弃权。
      本实验把两者放进**同一个设计**里，分离"目标尺寸"与"重叠程度"（二者在真实数据里共线）。

设计：2(半径) × 2(排布) × 4(模糊) × 10(重复) = 160 图
    半径 r ∈ {4, 16}（尺寸因子；与旧脚本 12/13 同区间）
    排布 ∈ {分散 scattered, 聚集 clustered}（重叠因子，在**同半径**下改变重叠！）
    模糊 σ ∈ {0, 2, 4, 8}
    n = 300 固定（个数不变，排除"个数"这个已知非主因）
画布 1024×1024（与旧脚本一致）

★ 两条必须遵守的纪律（都是用上一版失败换来的）：
  ① 提示词必须问"圆形"——上一版问"人数/人头"而图里画的是圆点，模型答 0 是**正确行为**，
     被我误记为"弃权"，160 张全部假弃权（97.5%），所有因子效应被地板效应吞掉。
  ② 默认走**本地 vLLM**（免费），只在显式给出 API_URL 时才走云端。
输出: /root/occl_results/occl_blur.csv
"""
import argparse, base64, csv, io, json, math, os, queue, random, re, sys, threading, time, urllib.request
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

# ★ 默认本地 vLLM（免费）；如需走云端，设 API_URL + SILICONFLOW_API_KEY
API_URL = os.environ.get('API_URL', 'http://127.0.0.1:8000/v1/chat/completions')
MODEL = os.environ.get('SERVED_MODEL', 'qwen3-vl-32b-awq')
_API_KEY = os.environ.get('SILICONFLOW_API_KEY', '')
OUT = os.environ.get('OCCL_OUT', '/root/occl_results')
PROMPT = ('请数出图片中的圆形数量，不要遗漏，不要重复，'
          '以JSON格式输出：{"count": 数量}，只输出JSON。')
# ★ 措辞必须问"圆形"而不是"人"：早前写成"数出图片中的人数/人头"，
#   而合成图里画的是圆点 → 模型回答 0 是**正确行为**，却被我记成"弃权"，
#   导致 160 张图出现 97.5% 的假弃权、所有因子效应被地板效应吞掉。
#   本版与旧脚本 12_abstain_causal.py / 13_abstain_blur.py 的 base 措辞逐字一致。
REFUSE = ['too many', '无法', '数不清', '难以', '众多', 'cannot']
_key_i = [0]
_lock = threading.Lock()


def call(b64, timeout=180):
    for attempt in range(4):
        body = {'model': MODEL, 'messages': [{'role': 'user', 'content': [
            {'type': 'image_url', 'image_url': {'url': 'data:image/png;base64,' + b64}},
            {'type': 'text', 'text': PROMPT}]}], 'temperature': 0.0, 'max_tokens': 48}
        hdr = {'Content-Type': 'application/json'}
        if _API_KEY:
            hdr['Authorization'] = 'Bearer ' + _API_KEY
        req = urllib.request.Request(API_URL, data=json.dumps(body).encode(), headers=hdr)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode())['choices'][0]['message']['content']
        except urllib.error.HTTPError as e:
            raw = e.read().decode('utf-8', 'ignore')[:120]
            if e.code in (402, 429, 401, 403, 500):
                time.sleep(2 + attempt * 3)
                continue
            raise RuntimeError('HTTP %s %s' % (e.code, raw))
        except Exception:
            time.sleep(2 + attempt * 3)
    raise RuntimeError('call failed after retries')


def parse(raw):
    import re
    m = re.search(r'\{\s*(?:count|计数|数量|人数)\s*[:：]\s*(\d+)', raw, re.I)
    if m:
        return int(m.group(1))
    m = re.search(r'-?\d+', raw.replace(',', ''))
    return int(m.group(0)) if m else None


def make_image(n, r, layout, sigma, seed):
    """生成合成人群图；返回 (PIL图, 实际重叠度)
    画布 1024×1024、r ∈ {4,16} —— 与旧脚本 12/13（同一画布、同半径区间）可比。"""
    W = H = 1024
    rng = np.random.default_rng(seed)
    im = Image.new('RGB', (W, H), (235, 235, 235))
    dr = ImageDraw.Draw(im)
    pts = []
    if layout == 'scattered':
        # 抖动网格，保证间距 → 低重叠
        g = int(math.ceil(math.sqrt(n)))
        step = W / g
        for i in range(g):
            for j in range(g):
                if len(pts) >= n:
                    break
                x = (i + 0.5) * step + rng.uniform(-0.12, 0.12) * step
                y = (j + 0.5) * step + rng.uniform(-0.12, 0.12) * step
                pts.append((x, y))
    else:
        # 3 个聚集簇，覆盖约 25% 面积 → 高重叠（同半径下）
        centers = [(W * 0.3, H * 0.3), (W * 0.7, H * 0.32), (W * 0.5, H * 0.72)]
        per = int(math.ceil(n / 3.0))
        for ci, (cx, cy) in enumerate(centers):
            cnt = per if ci < 2 else n - 2 * per
            for _ in range(max(0, cnt)):
                ang = rng.uniform(0, 2 * math.pi)
                rad = abs(rng.normal(0, 1)) * W * 0.055
                pts.append((cx + rad * math.cos(ang), cy + rad * math.sin(ang)))
    pts = pts[:n]
    for (x, y) in pts:
        dr.ellipse([x - r, y - r, x + r, y + r], fill=(40, 40, 45))
    if sigma > 0:                                    # ★ 模糊必须在画完圆之后再施加
        im = im.filter(ImageFilter.GaussianBlur(sigma))
    # 实测重叠度：每个圆的圆心落在其他圆内的比例
    P = np.array(pts)
    ov = 0
    for i in range(len(P)):
        d = np.hypot(P[:, 0] - P[i, 0], P[:, 1] - P[i, 1])
        ov += int(((d < 2 * r) & (d > 0)).sum())
    return im, ov / max(1, len(P))


def enc(im):
    b = io.BytesIO(); im.save(b, 'PNG')
    return base64.b64encode(b.getvalue()).decode()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--reps', type=int, default=10)
    ap.add_argument('--workers', type=int, default=8)
    a = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    jobs = []
    for r in (4, 16):
        for layout in ('scattered', 'clustered'):
            for sigma in (0, 2, 4, 8):
                for rep in range(a.reps):
                    jobs.append((300, r, layout, sigma, rep))
    out_csv = os.path.join(OUT, 'occl_blur.csv')
    seen = set()
    if os.path.exists(out_csv):
        with open(out_csv, encoding='utf-8-sig', newline='') as f:
            for row in csv.DictReader(f):
                if row.get('parse_ok') == '1':
                    seen.add((row['item']))
    jobs = [j for j in jobs if ('n%d_r%d_%s_s%g_%d' % j) not in seen]
    print('[occl] 任务 %d 个' % len(jobs), flush=True)
    fh = open(out_csv, 'a', encoding='utf-8-sig', newline='')
    wr = csv.writer(fh)
    if not seen:
        wr.writerow(['item', 'n', 'r', 'layout', 'sigma', 'overlap', 'pred', 'parse_ok', 'abstain', 'refuse', 'raw'])
    q = queue.Queue()
    for j in jobs:
        q.put(j)
    st = {'n': 0, 't0': time.time(), 'ab': 0}

    def work():
        while True:
            try:
                n, r, layout, sigma, rep = q.get_nowait()
            except queue.Empty:
                return
            item = 'n%d_r%d_%s_s%g_%d' % (n, r, layout, sigma, rep)
            try:
                im, ov = make_image(n, r, layout, sigma, 1000 * rep + r + int(sigma))
                raw = call(enc(im))
                pred = parse(raw)
                ab = 1 if pred == 0 else 0
                with _lock:
                    wr.writerow([item, n, r, layout, sigma, '%.3f' % ov,
                                 pred if pred is not None else '', 1 if pred is not None else 0,
                                 ab, 1 if any(k in raw.lower() for k in REFUSE) else 0,
                                 raw.replace('\n', ' ')[:60]])
                    fh.flush(); st['ab'] += ab
            except Exception as ex:
                with _lock:
                    wr.writerow([item, n, r, layout, sigma, '', '', 0, 0, 0, str(ex)[:60]]); fh.flush()
            with _lock:
                st['n'] += 1
                if st['n'] % 20 == 0:
                    print('  %d/%d (%.2f img/s, abst=%d)' % (
                        st['n'], len(jobs), st['n'] / max(time.time() - st['t0'], 1e-9), st['ab']), flush=True)

    ts = [threading.Thread(target=work, daemon=True) for _ in range(max(1, a.workers))]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    fh.close()
    print('[occl] 完成', flush=True)


if __name__ == '__main__':
    main()
