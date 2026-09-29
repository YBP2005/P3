#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""04_consistency.py — 自建 AWQ-32B 与 API BF16-32B 一致性校验（修正版）

用法（在 5090 上）:
  /root/vllm312/bin/python 04_consistency.py --ref-dir /root/ref --img-dir /root/ref/images \
      --gt-dir /root/ref/labels --out-dir /root/ref/results --n 300 --workers 16
"""
import argparse, base64, csv, io, json, os, random, re, sys, threading, queue, time
import urllib.request

P = {
    'base': ('请逐个数出图片中佩戴安全帽的人数和未佩戴安全帽的人数，不要遗漏，不要重复，'
             '以JSON格式输出：{"helmet": 戴帽人数, "no_helmet": 未戴帽人数}，只输出JSON。'),
    'over': ('请数出图片中佩戴安全帽的人数和未佩戴安全帽的人数。为避免漏数，请把所有可能存在的人物都计入'
             '（包括被遮挡、距离较远、画面模糊、只露出部分身体或头部的人）；宁可多算，不可漏算。'
             '以JSON格式输出：{"helmet": 戴帽人数, "no_helmet": 未戴帽人数}，只输出JSON。'),
    'under': ('请数出图片中佩戴安全帽的人数和未佩戴安全帽的人数。请只统计你能完全确认的人物'
              '（轮廓清晰、无遮挡、可明确判断是否佩戴安全帽）；宁可漏算，不可多算。'
              '以JSON格式输出：{"helmet": 戴帽人数, "no_helmet": 未戴帽人数}，只输出JSON。'),
}
MODEL = os.environ.get('SERVED_MODEL', 'qwen3-vl-32b-awq')
API = os.environ.get('LOCAL_API', 'http://127.0.0.1:8000/v1/chat/completions')
_lock = threading.Lock()


def enc(path):
    data = open(path, 'rb').read()
    if len(data) > 8 * 1024 * 1024:
        from PIL import Image
        im = Image.open(path).convert('RGB')
        w, h = im.size
        s = min(1.0, 2048 / max(w, h))
        im = im.resize((int(w * s), int(h * s)))
        b = io.BytesIO(); im.save(b, 'JPEG', quality=85); data = b.getvalue()
    return 'data:image/jpeg;base64,' + base64.b64encode(data).decode()


def call(path, prompt, timeout=180):
    payload = {'model': MODEL, 'messages': [{'role': 'user', 'content': [
        {'type': 'image_url', 'image_url': {'url': enc(path)}},
        {'type': 'text', 'text': prompt}]}], 'temperature': 0.0, 'max_tokens': 128}
    req = urllib.request.Request(API, data=json.dumps(payload).encode(),
                                 headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        j = json.loads(r.read().decode())
    return j['choices'][0]['message']['content']


def parse(raw):
    m = re.search(r'\{"helmet"\s*:\s*(\d+)\s*,\s*"no_helmet"\s*:\s*(\d+)\s*\}', raw, re.I)
    if m:
        return int(m.group(1)), int(m.group(2))
    m = re.search(r'\{helmet\s*:\s*(\d+)\s*,\s*no_helmet\s*:\s*(\d+)\s*\}', raw, re.I)
    if m:
        return int(m.group(1)), int(m.group(2))
    nums = re.findall(r'\d+', raw)
    return (int(nums[0]), int(nums[1])) if len(nums) >= 2 else None


def load_ref(ref_dir):
    per = {}
    for arm in P:
        p = os.path.join(ref_dir, 'E4A_vlm_%s_results.csv' % arm)
        d = {}
        with open(p, encoding='utf-8-sig', newline='') as f:
            for r in csv.DictReader(f):
                if r.get('parse_ok') == '1' and r.get('hat') not in ('', None):
                    d[r['img']] = (int(float(r['hat'])), int(float(r['no_helmet'])))
        per[arm] = d
    return per


def gt_of(gt_dir, name):
    f = os.path.join(gt_dir, name + '.txt')
    n0 = n1 = 0
    if os.path.exists(f):
        for line in open(f, encoding='utf-8', errors='replace'):
            p = line.split()
            if len(p) >= 5:
                c = int(float(p[0]))
                n0 += (c == 0); n1 += (c == 1)
    return n0, n1


def stats(pred, gt):
    e = [a - b for a, b in zip(pred, gt)]
    n = len(e)
    return (sum(abs(x) for x in e) / n, sum(e) / n, sum(1 for x in e if x > 0) / n)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--ref-dir', default='/root/ref')
    ap.add_argument('--img-dir', default='/root/ref/images')
    ap.add_argument('--gt-dir', default='/root/ref/labels')
    ap.add_argument('--out-dir', default='/root/ref/results')
    ap.add_argument('--n', type=int, default=300)
    ap.add_argument('--workers', type=int, default=16)
    a = ap.parse_args()
    os.makedirs(a.out_dir, exist_ok=True)

    per_ref = load_ref(a.ref_dir)
    picked = open(os.path.join(a.ref_dir, 'picked.txt')).read().split()
    names = [x for x in picked if os.path.exists(os.path.join(a.img_dir, x + '.jpg'))][:a.n]
    print('[consistency] 图像 %d 张，三臂 × %d 次本地推理' % (len(names), len(P)), flush=True)

    report = ['# 自建 AWQ-4bit vs API BF16 一致性校验', '',
              '同一批 %d 张图、同一提示词、温度 0；指标均对 GT（标签行数）计算' % len(names), '',
              '| 臂 | 指标 | API(BF16) | 自建(AWQ-4bit) | 差异 |', '|---|---|---|---|---|']

    for arm in ['base', 'over', 'under']:
        out_csv = os.path.join(a.out_dir, 'consistency_local_%s.csv' % arm)
        done = {}
        if os.path.exists(out_csv):
            with open(out_csv, encoding='utf-8-sig', newline='') as f:
                for r in csv.DictReader(f):
                    if r.get('parse_ok') == '1':
                        done[r['img']] = (int(r['hat']), int(r['no_helmet']))
        todo = [x for x in names if x not in done]
        fh = open(out_csv, 'a', encoding='utf-8-sig', newline='')
        wr = csv.writer(fh)
        if not os.path.exists(out_csv) or fh.tell() == 0:
            wr.writerow(['img', 'hat', 'no_helmet', 'parse_ok', 'raw', 'latency_s'])
        q = queue.Queue()
        for x in todo:
            q.put(x)
        stat = {'n': 0, 't0': time.time()}

        def w():
            while True:
                try:
                    nm = q.get_nowait()
                except queue.Empty:
                    return
                t0 = time.time()
                try:
                    raw = call(os.path.join(a.img_dir, nm + '.jpg'), P[arm])
                    pr = parse(raw)
                    with _lock:
                        wr.writerow([nm, pr[0] if pr else '', pr[1] if pr else '',
                                     1 if pr else 0, raw.replace('\n', ' ')[:120],
                                     '%.2f' % (time.time() - t0)])
                        fh.flush()
                except Exception as ex:
                    with _lock:
                        wr.writerow([nm, '', '', 0, '', str(ex)[:100]])
                        fh.flush()
                with _lock:
                    stat['n'] += 1
                    if stat['n'] % 50 == 0:
                        el = time.time() - stat['t0']
                        print('  [%s] %d/%d (%.2f img/s)' % (arm, stat['n'], len(todo),
                                                             stat['n'] / max(el, 1e-9)), flush=True)
        ts = [threading.Thread(target=w, daemon=True) for _ in range(max(1, a.workers))]
        for t in ts:
            t.start()
        for t in ts:
            t.join()
        fh.close()

        local = {}
        with open(out_csv, encoding='utf-8-sig', newline='') as f:
            for r in csv.DictReader(f):
                if r.get('parse_ok') == '1':
                    local[r['img']] = (int(r['hat']), int(r['no_helmet']))
        common = [x for x in names if x in local and x in per_ref[arm]]
        gt = [gt_of(a.gt_dir, x) for x in common]
        for dim, idx in [('总人数', None), ('戴帽', 0), ('未戴帽', 1)]:
            def pick(v, i):
                return v[0] + v[1] if i is None else v[i]
            ap_, lo_, g_ = [pick(per_ref[arm][x], idx) for x in common], \
                           [pick(local[x], idx) for x in common], \
                           [pick(g, idx) for g in gt]
            am, aM, aO = stats(ap_, g_)
            lm, lM, lO = stats(lo_, g_)
            report.append('| %s | %s | MAE %.3f / ME %+.3f / P(over) %.3f | MAE %.3f / ME %+.3f / P(over) %.3f | ΔME %+.3f |'
                          % (arm, dim, am, aM, aO, lm, lM, lO, lM - aM))
        exact = sum(1 for x in common if per_ref[arm][x] == local[x]) / max(1, len(common))
        dsum = [abs(sum(local[x]) - sum(per_ref[arm][x])) for x in common]
        report.append('| %s | 逐图完全一致率 / 平均\\|Δ总人数\\| | — | — | **%.1f%%** / %.3f |'
                      % (arm, exact * 100, sum(dsum) / max(1, len(dsum))))
        print('[%s] n=%d 完全一致率=%.1f%% 平均|Δ|=%.3f' % (arm, len(common), exact * 100,
                                                          sum(dsum) / max(1, len(dsum))), flush=True)

    with open(os.path.join(a.out_dir, 'consistency_report.md'), 'w', encoding='utf-8') as f:
        f.write('\n'.join(report) + '\n')
    print()
    print('\n'.join(report))


if __name__ == '__main__':
    main()
