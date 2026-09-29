#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""15_aerial_tile.py — 航拍域的切块 VLM 计数（检验"切块消除弃权"是否跨域成立）

用法: python15_aerial_tile.py --ds visdrone|aitod --arm base|over|under --tile K [--limit N]
输出: /root/aerial_tile_results/aer_<ds>_<arm>_tile<K>.csv
"""
import argparse, base64, csv, io, json, os, re, sys, threading, queue, time
import urllib.request

API = os.environ.get('LOCAL_API', 'http://127.0.0.1:8000/v1/chat/completions')
MODEL = os.environ.get('SERVED_MODEL', 'qwen3-vl-32b-awq')
ROOT = '/root/aerial'
OUT = os.environ.get('AERTILE_OUT', '/root/aerial_tile_results')
_lock = threading.Lock()

P = {
    'base': '请数出图片中的人数（人群中的每个人头或人体），不要遗漏，不要重复，以JSON格式输出：{"count": 数量}，只输出JSON。',
    'over': ('请数出图片中的人数。为避免漏数，请把所有可能存在的目标都计入（包括被遮挡、距离较远、画面模糊、'
             '只露出部分的个体）；宁可多算，不可漏算。以JSON格式输出：{"count": 数量}，只输出JSON。'),
    'under': ('请数出图片中的人数。请只统计你能完全确认的目标（轮廓清晰、无遮挡、可明确判断的个体）；'
              '宁可漏算，不可多算。以JSON格式输出：{"count": 数量}，只输出JSON。'),
}


def enc_img(im, max_pixels=1048576, quality=92):
    if im.size[0] * im.size[1] > max_pixels:
        s = (max_pixels / float(im.size[0] * im.size[1])) ** 0.5
        im = im.resize((max(1, int(im.size[0] * s)), max(1, int(im.size[1] * s))))
    b = io.BytesIO(); im.save(b, 'JPEG', quality=quality)
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


def tiles_of(im, k, overlap=0.2, max_pixels=1048576):
    W, H = im.size
    tw, th = int(W / k * (1 + overlap)), int(H / k * (1 + overlap))
    out = []
    for i in range(k):
        for j in range(k):
            x0 = max(0, int(W * i / k) - int(tw * overlap / 2))
            y0 = max(0, int(H * j / k) - int(th * overlap / 2))
            t = im.crop((x0, y0, min(W, x0 + tw), min(H, y0 + th)))
            out.append(t)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--ds', required=True, choices=['visdrone', 'aitod'])
    ap.add_argument('--arm', required=True, choices=list(P))
    ap.add_argument('--tile', type=int, required=True)
    ap.add_argument('--limit', type=int, default=0)
    ap.add_argument('--workers', type=int, default=32)
    a = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    from PIL import Image
    idir = os.path.join(ROOT, a.ds, 'images')
    gt = {}
    with open(os.path.join(ROOT, 'gt_%s.csv' % a.ds), encoding='utf-8-sig') as f:
        for r in csv.DictReader(f):
            gt[r['item']] = int(r['gt'])
    # 扩展名兼容：VisDrone 为 .jpg，AI-TOD 为 .png（此前只查 .jpg，导致 aitod 被静默跳过）
    EXTS = ('.jpg', '.jpeg', '.png', '.bmp', '.JPG', '.PNG')
    _cache = {}

    def img_path(n):
        if n in _cache:
            return _cache[n]
        p = None
        for e in EXTS:
            q = os.path.join(idir, n + e)
            if os.path.exists(q):
                p = q
                break
        _cache[n] = p
        return p
    names = [n for n in sorted(gt) if img_path(n)]
    if a.limit:
        names = names[:a.limit]
    out_csv = os.path.join(OUT, 'aer_%s_%s_tile%d.csv' % (a.ds, a.arm, a.tile))
    done = set()
    if os.path.exists(out_csv):
        with open(out_csv, encoding='utf-8-sig', newline='') as f:
            for r in csv.DictReader(f):
                if r.get('parse_ok') == '1':
                    done.add(r['item'])
    todo = [x for x in names if x not in done]
    print('[aertile:%s/%s/%d] total=%d todo=%d model=%s' % (a.ds, a.arm, a.tile, len(names), len(todo), MODEL), flush=True)
    fh = open(out_csv, 'a', encoding='utf-8-sig', newline='')
    wr = csv.writer(fh)
    if not os.path.exists(out_csv) or os.path.getsize(out_csv) == 0:
        wr.writerow(['item', 'gt', 'pred', 'parse_ok', 'ntiles', 'abstain', 'raw'])
    q = queue.Queue()
    for x in todo:
        q.put(x)
    st = {'n': 0, 't0': time.time(), 'abst': 0}

    def work():
        while True:
            try:
                nm = q.get_nowait()
            except queue.Empty:
                return
            try:
                im = Image.open(img_path(nm)).convert('RGB')
                tl = tiles_of(im, a.tile)
                tot, raws, ok, nz = 0, [], True, 0
                for t in tl:
                    raw = call(enc_img(t), P[a.arm])
                    raws.append(raw.replace('\n', ' ')[:24])
                    v = parse(raw)
                    if v is None:
                        ok = False
                    else:
                        tot += v
                        if v == 0:
                            nz += 1
                pred = tot if ok else None
                abst = 1 if (pred == 0 or nz == len(tl)) else 0
                with _lock:
                    wr.writerow([nm, gt[nm], pred if pred is not None else '',
                                 1 if pred is not None else 0, len(tl), abst, ' | '.join(raws)[:120]])
                    fh.flush()
                    st['abst'] += abst
            except Exception as ex:
                with _lock:
                    wr.writerow([nm, gt[nm], '', 0, 0, 0, str(ex)[:80]]); fh.flush()
            with _lock:
                st['n'] += 1
                if st['n'] % 25 == 0:
                    print('  %d/%d (%.2f img/s, abst=%d)' % (
                        st['n'], len(todo), st['n'] / max(time.time() - st['t0'], 1e-9), st['abst']), flush=True)

    ts = [threading.Thread(target=work, daemon=True) for _ in range(max(1, a.workers))]
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
        print('[aertile:%s/%s/%d] n=%d MAE=%.2f ME=%+.2f rho=%+.1f%% | 弃权率=%.1f%% | 排除后 rho=%+.1f%%' % (
            a.ds, a.arm, a.tile, len(e), sum(abs(x) for x in e) / len(e), sum(e) / len(e),
            100 * sum(e) / len(e) / mg, 100.0 * A_ / len(P_),
            100 * (sum(p - g for p, g in keep) / max(1, len(keep))) /
            (sum(g for _, g in keep) / max(1, len(keep))) if keep else float('nan')), flush=True)


if __name__ == '__main__':
    main()
