#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""06_dense_vlm.py — 在 5090 上跑密集人群的 VLM 三臂（支持切块，突破 API 的 1024 长边限制）

用法:
  python06_dense_vlm.py --ds st_a|st_b|ucf --arm base|over|under [--tile K] [--workers 16]
输出: /root/dense_results/vlm_<ds>_<arm>[_tile<K>].csv
"""
import argparse, base64, csv, io, json, os, random, re, threading, queue, time
import urllib.request

P = {
    'base': ('请数出图片中的人数（人群中的每个人头或人体），不要遗漏，不要重复，'
             '以JSON格式输出：{"count": 数量}，只输出JSON。'),
    'over': ('请数出图片中的人数。为避免漏数，请把所有可能存在的目标都计入'
             '（包括被遮挡、距离较远、画面模糊、只露出部分的个体）；宁可多算，不可漏算。'
             '以JSON格式输出：{"count": 数量}，只输出JSON。'),
    'under': ('请数出图片中的人数。请只统计你能完全确认的目标'
              '（轮廓清晰、无遮挡、可明确判断的个体）；宁可漏算，不可多算。'
              '以JSON格式输出：{"count": 数量}，只输出JSON。'),
}
MODEL = os.environ.get('SERVED_MODEL', 'qwen3-vl-32b-awq')
API = os.environ.get('LOCAL_API', 'http://127.0.0.1:8000/v1/chat/completions')
_lock = threading.Lock()

DS_DIRS = {
    'st_a': '/root/dense/shanghaitech/images/part_A_test',
    'st_b': '/root/dense/shanghaitech/images/part_B_test',
    'ucf': '/root/dense/ucf_qnrf/UCF-QNRF_ECCV18/Test',
}


def load_gt(ds):
    gt = {}
    if ds in ('st_a', 'st_b'):
        want = 'part_A' if ds == 'st_a' else 'part_B'
        with open('/root/dense/shanghaitech/counts.csv', encoding='utf-8-sig') as f:
            for r in csv.DictReader(f):
                if r.get('part') == want and r.get('split') == 'test':
                    gt[os.path.splitext(os.path.basename(r['file']))[0]] = int(r['count'])
    else:
        with open('/root/dense/ucf_qnrf/counts.csv', encoding='utf-8-sig') as f:
            for r in csv.DictReader(f):
                if r['split'] == 'Test':
                    gt[os.path.splitext(os.path.basename(r['file']))[0]] = int(r['count'])
    return gt


def b64_of(im, quality=92):
    buf = io.BytesIO()
    im.save(buf, 'JPEG', quality=quality)
    return base64.b64encode(buf.getvalue()).decode()


def tiles(path, k, overlap=0.2, max_pixels=1048576):
    from PIL import Image
    im = Image.open(path).convert('RGB')
    W, H = im.size
    out = []
    tw, th = int(W / k * (1 + overlap)), int(H / k * (1 + overlap))
    for i in range(k):
        for j in range(k):
            x0 = max(0, int(W * i / k) - int(tw * overlap / 2))
            y0 = max(0, int(H * j / k) - int(th * overlap / 2))
            t = im.crop((x0, y0, min(W, x0 + tw), min(H, y0 + th)))
            if t.size[0] * t.size[1] > max_pixels:
                s = (max_pixels / float(t.size[0] * t.size[1])) ** 0.5
                t = t.resize((max(1, int(t.size[0] * s)), max(1, int(t.size[1] * s))))
            out.append(t)
    return out, (W, H)


def call_img(b64, prompt, timeout=180):
    payload = {'model': MODEL, 'messages': [{'role': 'user', 'content': [
        {'type': 'image_url', 'image_url': {'url': 'data:image/jpeg;base64,' + b64}},
        {'type': 'text', 'text': prompt}]}], 'temperature': 0.0, 'max_tokens': 64}
    req = urllib.request.Request(API, data=json.dumps(payload).encode(),
                                 headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())['choices'][0]['message']['content']


ABSTAIN_MARK = True  # 0 且提示语含拒绝措辞 -> 记为弃权


def parse(raw):
    m = re.search(r'\{\s*(?:count|计数|数量|人数)\s*[:：]\s*(\d+)', raw, re.I)
    if m:
        return int(m.group(1))
    m = re.search(r'-?\d+', raw.replace(',', ''))
    return int(m.group(0)) if m else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--ds', required=True, choices=list(DS_DIRS))
    ap.add_argument('--arm', required=True, choices=list(P))
    ap.add_argument('--tile', type=int, default=0)
    ap.add_argument('--workers', type=int, default=16)
    ap.add_argument('--out-dir', default='/root/dense_results')
    ap.add_argument('--limit', type=int, default=0)
    a = ap.parse_args()
    os.makedirs(a.out_dir, exist_ok=True)

    from PIL import Image
    gt = load_gt(a.ds)
    idir = DS_DIRS[a.ds]
    names = sorted(gt)
    if a.limit:
        names = names[:a.limit]
    suf = ('_tile%d' % a.tile) if a.tile else '_whole'
    out_csv = os.path.join(a.out_dir, 'vlm_%s_%s%s.csv' % (a.ds, a.arm, suf))
    done = set()
    if os.path.exists(out_csv):
        with open(out_csv, encoding='utf-8-sig', newline='') as f:
            for r in csv.DictReader(f):
                if r.get('parse_ok') == '1':
                    done.add(r['item'])
    todo = [x for x in names if x not in done]
    print('[%s/%s%s] total=%d done=%d todo=%d' % (a.ds, a.arm, suf, len(names), len(done), len(todo)), flush=True)
    fh = open(out_csv, 'a', encoding='utf-8-sig', newline='')
    wr = csv.writer(fh)
    if not os.path.exists(out_csv) or os.path.getsize(out_csv) == 0:
        wr.writerow(['item', 'gt', 'pred', 'ntiles', 'parse_ok', 'raw', 'latency_s', 'abstain'])

    q = queue.Queue()
    for x in todo:
        q.put(x)
    st = {'n': 0, 'fail': 0, 't0': time.time()}

    def work():
        while True:
            try:
                nm = q.get_nowait()
            except queue.Empty:
                return
            p = os.path.join(idir, nm + '.jpg')
            t0 = time.time()
            try:
                if a.tile:
                    tl, _ = tiles(p, a.tile)
                    tot, raws, ok = 0, [], True
                    for t in tl:
                        raw = call_img(b64_of(t), P[a.arm])
                        raws.append(raw.replace('\n', ' ')[:30])
                        v = parse(raw)
                        if v is None:
                            ok = False
                        else:
                            tot += v
                    pred = tot if ok else None
                    nraw = ' | '.join(raws)[:150]
                    nt = len(tl)
                else:
                    im = Image.open(p).convert('RGB')
                    if im.size[0] * im.size[1] > 1048576:
                        s = (1048576 / float(im.size[0] * im.size[1])) ** 0.5
                        im = im.resize((max(1, int(im.size[0] * s)), max(1, int(im.size[1] * s))))
                    raw = call_img(b64_of(im), P[a.arm])
                    pred = parse(raw)
                    nraw = raw.replace('\n', ' ')[:150]
                    nt = 1
                with _lock:
                    abandon = 1 if (pred == 0 or (nraw and any(k in nraw.lower() for k in
                              ['too many', '无法', '数不清', '难以', '众多']))) else 0
                    wr.writerow([nm, gt[nm], pred if pred is not None else '',
                                 1 if pred is not None else 0, nt, nraw, '%.2f' % (time.time() - t0), abandon])
                    fh.flush()
            except Exception as ex:
                with _lock:
                    st['fail'] += 1
                    wr.writerow([nm, gt[nm], '', 0, 0, '', str(ex)[:100]]); fh.flush()
            with _lock:
                st['n'] += 1
                if st['n'] % 25 == 0:
                    el = time.time() - st['t0']
                    print('  %d/%d (%.2f img/s, fail=%d)' % (st['n'], len(todo), st['n'] / max(el, 1e-9), st['fail']), flush=True)

    ts = [threading.Thread(target=work, daemon=True) for _ in range(max(1, a.workers))]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    fh.close()

    P_, T_ = [], []
    with open(out_csv, encoding='utf-8-sig', newline='') as f:
        for r in csv.DictReader(f):
            if not (r.get('pred') or '').strip():   # IVL-FIX: 空 pred（文本格式漂移）跳过
                continue
            if r.get('parse_ok') == '1':
                P_.append(int(float(r['pred']))); T_.append(int(float(r['gt'])))
    if P_:
        e = [p - g for p, g in zip(P_, T_)]
        mg = sum(T_) / len(T_)
        mae = sum(abs(x) for x in e) / len(e)
        me = sum(e) / len(e)
        print('[%s/%s%s] n=%d MAE=%.1f ME=%+.1f rho=%+.1f%% P(over)=%.3f meanGT=%.1f' % (
            a.ds, a.arm, suf, len(e), mae, me, 100 * me / mg, sum(1 for x in e if x > 0) / len(e), mg), flush=True)


if __name__ == '__main__':
    main()
