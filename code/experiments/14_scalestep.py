import os
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""14_scalestep.py — 真实图像的"分辨率阶梯"：弃权率 vs 每目标像素数

对 UCF/ST-A 的每张测试图，按 5 档缩放（1.0/0.75/0.5/0.35/0.25），
记录每目标像素数 px_per_obj 与是否弃权 → 得到自然图像的弃权-可分辨度曲线。

用法: python14_scalestep.py <st_a|ucf> [workers]
输出: /root/abstain_results/scalestep_<ds>.csv
"""
import base64, csv, io, json, os, queue, re, sys, threading, time
import urllib.request

API = os.environ.get('LOCAL_API', 'http://127.0.0.1:8000/v1/chat/completions')
MODEL = os.environ.get('SERVED_MODEL', 'qwen3-vl-32b-awq')
OUT = os.environ.get('ABSTAIN_OUT', '/root/abstain_results')
os.makedirs(OUT, exist_ok=True)
PR = ('请数出图片中的人数（人群中的每个人头或人体），不要遗漏，不要重复，'
      '以JSON格式输出：{"count": 数量}，只输出JSON。')
SCALES = [1.0, 0.75, 0.5, 0.35, 0.25]
_lock = threading.Lock()
REFUSE = ['too many', '无法', '数不清', '难以', '众多', 'cannot']


def load_gt(ds):
    if ds == 'ucf':
        idir = '/root/dense/ucf_qnrf/UCF-QNRF_ECCV18/Test'
        gt = {}
        with open('/root/dense/ucf_qnrf/counts.csv', encoding='utf-8-sig') as f:
            for r in csv.DictReader(f):
                if r['split'] == 'Test':
                    gt[os.path.splitext(os.path.basename(r['file']))[0]] = int(r['count'])
        return idir, gt
    idir = '/root/dense/shanghaitech/images/part_A_test'
    gt = {}
    with open('/root/dense/shanghaitech/counts.csv', encoding='utf-8-sig') as f:
        for r in csv.DictReader(f):
            if r.get('part') == 'part_A' and r.get('split') == 'test':
                gt[os.path.splitext(os.path.basename(r['file']))[0]] = int(r['count'])
    return idir, gt


def call(im, timeout=180):
    b = io.BytesIO(); im.save(b, 'JPEG', quality=92)
    url = 'data:image/jpeg;base64,' + base64.b64encode(b.getvalue()).decode()
    payload = {'model': MODEL, 'messages': [{'role': 'user', 'content': [
        {'type': 'image_url', 'image_url': {'url': url}},
        {'type': 'text', 'text': PR}]}], 'temperature': 0.0, 'max_tokens': 64}
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
    ds = sys.argv[1]
    workers = int(sys.argv[2]) if len(sys.argv) > 2 else 24
    from PIL import Image
    idir, gt = load_gt(ds)
    names = [n for n in sorted(gt) if os.path.exists(os.path.join(idir, n + '.jpg'))]
    out_csv = os.path.join(OUT, 'scalestep_%s.csv' % ds)
    done = set()
    if os.path.exists(out_csv):
        with open(out_csv, encoding='utf-8-sig', newline='') as f:
            for r in csv.DictReader(f):
                if r.get('parse_ok') == '1':
                    done.add((r['item'], r['scale']))
    jobs = [(n, s) for n in names for s in SCALES if (n, str(s)) not in done]
    print('[scalestep/%s] 图=%d 任务=%d' % (ds, len(names), len(jobs)), flush=True)
    fh = open(out_csv, 'a', encoding='utf-8-sig', newline='')
    wr = csv.writer(fh)
    if not os.path.exists(out_csv) or os.path.getsize(out_csv) == 0:
        wr.writerow(['item', 'scale', 'gt', 'img_w', 'img_h', 'px_per_obj', 'pred',
                     'parse_ok', 'abstain', 'refuse', 'raw'])
    q = queue.Queue()
    for j in jobs:
        q.put(j)
    st = {'n': 0, 't0': time.time(), 'abst': 0}

    def work():
        while True:
            try:
                nm, sc = q.get_nowait()
            except queue.Empty:
                return
            try:
                im = Image.open(os.path.join(idir, nm + '.jpg')).convert('RGB')
                w, h = im.size
                if sc < 1.0:
                    im = im.resize((max(64, int(w * sc)), max(64, int(h * sc))))
                px = (im.size[0] * im.size[1]) / max(1, gt[nm])
                raw = call(im)
                pred = parse(raw)
                low = raw.lower()
                zero = (pred == 0)
                ref = any(k in low for k in REFUSE)
                with _lock:
                    wr.writerow([nm, sc, gt[nm], im.size[0], im.size[1], '%.1f' % px,
                                 pred if pred is not None else '', 1 if pred is not None else 0,
                                 1 if zero else 0, 1 if ref else 0, raw.replace('\n', ' ')[:80]])
                    fh.flush()
                    st['abst'] += int(zero)
            except Exception as ex:
                with _lock:
                    wr.writerow([nm, sc, gt.get(nm, ''), '', '', '', '', 0, 0, 0, str(ex)[:60]])
                    fh.flush()
            with _lock:
                st['n'] += 1
                if st['n'] % 100 == 0:
                    print('  %d/%d (%.2f img/s, zero=%d)' % (
                        st['n'], len(jobs), st['n'] / max(time.time() - st['t0'], 1e-9), st['abst']), flush=True)

    ts = [threading.Thread(target=work, daemon=True) for _ in range(max(1, workers))]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    fh.close()
    print('[scalestep/%s] DONE' % ds, flush=True)


if __name__ == '__main__':
    main()
