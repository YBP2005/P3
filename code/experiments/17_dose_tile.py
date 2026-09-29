#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""17_dose_tile.py — 切块 × 提示词强度的交互实验

动机：已确立两件事——① 切块能清除弃权（ST-A 56.6%→0.0%）；② 放宽提示词能把 ρ 从 −79% 推到 +587%。
      但二者**从未在同一次测量里交叉**。关键问题是：
      **"放宽提示词造成的高估"是不是"弃权被绕过"的补偿行为？**

      若是 → 在切块后（弃权已 = 0）放宽提示词应当**几乎不再改变 ρ**；
      若不是 → 切块 + 宽松提示仍会大幅高估，说明高估与弃权是两个独立机制。

设计：同一批图，交叉 {切块级别 K} × {提示强度档}，每格给出 ρ 与弃权率。

用法:
  python3 17_dose_tile.py --ds st_a --tile 3 --levels L1_随便给,L3_可近似,L4_中性,L7_不确定就0
输出: /root/dose_tile_results/dose_tile<K>_<ds>.csv
"""
import argparse, base64, csv, io, json, os, re, sys, threading, queue, time
import urllib.request

API = os.environ.get('LOCAL_API', 'http://127.0.0.1:8000/v1/chat/completions')
MODEL = os.environ.get('SERVED_MODEL', 'qwen3-vl-32b-awq')
OUT = os.environ.get('DT_OUT', '/root/dose_tile_results')
_lock = threading.Lock()
REFUSE = ['too many', '无法', '数不清', '难以', '众多', 'cannot']

LEVELS = [
    ('L1_随便给', '图中大概有多少人？给个大致数字就行，以JSON格式输出：{"count": 数量}，只输出JSON。'),
    ('L2_只给数字', '图中有多少人？只输出一个阿拉伯数字。'),
    ('L3_可近似', '请估计图中的人数（允许近似），以JSON格式输出：{"count": 数量}，只输出JSON。'),
    ('L4_中性', '请数出图片中的人数（人群中的每个人头或人体），不要遗漏，不要重复，以JSON格式输出：{"count": 数量}，只输出JSON。'),
    ('L5_逐一点数', '请先逐一定位图中每个人头/人体，确认无重复无遗漏后再给出总人数，以JSON格式输出：{"count": 数量}，只输出JSON。'),
    ('L6_只算清晰', '请只统计你能清晰确认的人，不确定的不要计入，以JSON格式输出：{"count": 数量}，只输出JSON。'),
    ('L7_不确定就0', '请只统计你能 100% 确认的人；若无法确认，请在 count 中填 0。以JSON格式输出：{"count": 数量}，只输出JSON。'),
]
BY_NAME = {n: p for n, p in LEVELS}


def load_items(ds):
    if ds == 'st_a':
        idir = '/root/dense/shanghaitech/images/part_A_test'
        gt = {}
        with open('/root/dense/shanghaitech/counts.csv', encoding='utf-8-sig') as f:
            for r in csv.DictReader(f):
                if r.get('part') == 'part_A' and r.get('split') == 'test':
                    gt[os.path.splitext(os.path.basename(r['file']))[0]] = int(r['count'])
        return idir, gt, '.jpg'
    if ds == 'st_b':
        idir = '/root/dense/shanghaitech/images/part_B_test'
        gt = {}
        with open('/root/dense/shanghaitech/counts.csv', encoding='utf-8-sig') as f:
            for r in csv.DictReader(f):
                if r.get('part') == 'part_B' and r.get('split') == 'test':
                    gt[os.path.splitext(os.path.basename(r['file']))[0]] = int(r['count'])
        return idir, gt, '.jpg'
    if ds == 'ucf':
        idir = '/root/dense/ucf_qnrf/UCF-QNRF_ECCV18/Test'
        gt = {}
        with open('/root/dense/ucf_qnrf/counts.csv', encoding='utf-8-sig') as f:
            for r in csv.DictReader(f):
                if r['split'] == 'Test':
                    gt[os.path.splitext(os.path.basename(r['file']))[0]] = int(r['count'])
        return idir, gt, '.jpg'
    if ds == 'visdrone':
        idir = '/root/aerial/visdrone/images'
        gt = {}
        with open('/root/aerial/gt_visdrone.csv', encoding='utf-8-sig') as f:
            for r in csv.DictReader(f):
                gt[r['item']] = int(r['gt'])
        return idir, gt, '.jpg'
    raise SystemExit('未知数据集 %s' % ds)


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


def enc_img(im):
    b = io.BytesIO()
    im.save(b, 'JPEG', quality=92)
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--ds', required=True, choices=['st_a', 'st_b', 'ucf', 'visdrone'])
    ap.add_argument('--tile', type=int, required=True)
    ap.add_argument('--levels', default='L1_随便给,L3_可近似,L4_中性,L7_不确定就0')
    ap.add_argument('--workers', type=int, default=32)
    ap.add_argument('--limit', type=int, default=0)
    a = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    lv_names = [x.strip() for x in a.levels.split(',') if x.strip()]
    for n in lv_names:
        if n not in BY_NAME:
            raise SystemExit('未知档位 %s（可选：%s）' % (n, ','.join(BY_NAME)))
    idir, gt, ext = load_items(a.ds)
    names = [n for n in sorted(gt) if os.path.exists(os.path.join(idir, n + ext))]
    if a.limit:
        names = names[:a.limit]
    out_csv = os.path.join(OUT, 'dose_tile%d_%s.csv' % (a.tile, a.ds))
    done = set()
    if os.path.exists(out_csv):
        with open(out_csv, encoding='utf-8-sig', newline='') as f:
            for r in csv.DictReader(f):
                if r.get('parse_ok') == '1':
                    done.add((r['item'], r['level']))
    jobs = [(n, lv) for n in names for lv in lv_names if (n, lv) not in done]
    print('[dt/%s/K%d] 图=%d 档位=%d 任务=%d model=%s' % (
        a.ds, a.tile, len(names), len(lv_names), len(jobs), MODEL), flush=True)
    fh = open(out_csv, 'a', encoding='utf-8-sig', newline='')
    wr = csv.writer(fh)
    if not os.path.exists(out_csv) or os.path.getsize(out_csv) == 0:
        wr.writerow(['item', 'level', 'gt', 'pred', 'ntiles', 'parse_ok', 'zero', 'refuse', 'raw'])
    q = queue.Queue()
    for j in jobs:
        q.put(j)
    st = {'n': 0, 't0': time.time(), 'zero': 0}

    def work():
        while True:
            try:
                nm, lv = q.get_nowait()
            except queue.Empty:
                return
            try:
                tl, _ = tiles(os.path.join(idir, nm + ext), a.tile)
                tot, nz, ok, raws = 0, 0, True, []
                for t in tl:
                    raw = call(enc_img(t), BY_NAME[lv])
                    raws.append(raw.replace('\n', ' ')[:20])
                    v = parse(raw)
                    if v is None:
                        ok = False
                    else:
                        tot += v
                        if v == 0:
                            nz += 1
                abst = 1 if (tot == 0 or nz == len(tl)) else 0
                low = ' '.join(raws).lower()
                with _lock:
                    wr.writerow([nm, lv, gt[nm], tot if ok else '', len(tl),
                                 1 if ok else 0, abst,
                                 1 if any(k in low for k in REFUSE) else 0,
                                 ' | '.join(raws)[:80]])
                    fh.flush()
                    st['zero'] += abst
            except Exception as ex:
                with _lock:
                    wr.writerow([nm, lv, gt[nm], '', 0, 0, 0, 0, str(ex)[:70]]); fh.flush()
            with _lock:
                st['n'] += 1
                if st['n'] % 100 == 0:
                    print('  %d/%d (%.2f img/s, abst=%d)' % (
                        st['n'], len(jobs), st['n'] / max(time.time() - st['t0'], 1e-9), st['zero']), flush=True)

    ts = [threading.Thread(target=work, daemon=True) for _ in range(max(1, a.workers))]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    fh.close()
    print('[dt/%s/K%d] 汇总:' % (a.ds, a.tile), flush=True)
    rows = list(csv.DictReader(open(out_csv, encoding='utf-8-sig')))
    for lv in lv_names:
        sub = [(int(float(r['gt'])), int(float(r['pred'])), int(r['zero'])) for r in rows
               if r['level'] == lv and r.get('parse_ok') == '1']
        if not sub:
            continue
        mg = sum(g for g, _, _ in sub) / len(sub)
        me = sum(p - g for g, p, _ in sub) / len(sub)
        print('   %-14s n=%d MAE=%.1f ME=%+.1f rho=%+.1f%% 弃权率=%.1f%%' % (
            lv, len(sub), sum(abs(p - g) for g, p, _ in sub) / len(sub), me,
            100 * me / mg, 100.0 * sum(z for _, _, z in sub) / len(sub)), flush=True)


if __name__ == '__main__':
    main()
