import os
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""09_dense_prompts.py — 密集场景的提示词族扫描（5 种问法 × 三臂）

用途：检验密集域的"弃权 + 方向"机制是否依赖措辞。
用法: python09_dense_prompts.py --ds st_a|ucf|st_b --arm base|over|under [--workers 32]
输出: /root/dense_prompt_results/{ds}_{arm}_{Vtag}.csv
"""
import argparse, base64, csv, io, json, os, re, sys, threading, queue, time
import urllib.request

API = os.environ.get('LOCAL_API', 'http://127.0.0.1:8000/v1/chat/completions')
MODEL = os.environ.get('SERVED_MODEL', 'qwen3-vl-32b-awq')
OUT = os.environ.get('DP_OUT', '/root/dense_prompt_results')
DS_DIRS = {
    'st_a': ('/root/dense/shanghaitech/images/part_A_test', '/root/dense/shanghaitech/counts.csv', 'part_A'),
    'st_b': ('/root/dense/shanghaitech/images/part_B_test', '/root/dense/shanghaitech/counts.csv', 'part_B'),
    'ucf': ('/root/dense/ucf_qnrf/UCF-QNRF_ECCV18/Test', '/root/dense/ucf_qnrf/counts.csv', None),
}
# 5 种问法（V1 与主实验 base 逐字一致）
P = {
    'V1_json': '请数出图片中的人数（人群中的每个人头或人体），不要遗漏，不要重复，以JSON格式输出：{"count": 数量}，只输出JSON。',
    'V2_number': '图中有多少人？只输出一个阿拉伯数字。',
    'V3_locate': '请先在图中逐个定位每个人头/人体，再统计总人数，以JSON格式输出：{"count": 数量}，只输出JSON。',
    'V4_estimate': '请估计图中的人数（允许给出近似值），以JSON格式输出：{"count": 数量}，只输出JSON。',
    'V5_region': '请分区域估计人数后求和，以JSON格式输出：{"count": 数量}，只输出JSON。',
}
_lock = threading.Lock()


def enc(path):
    from PIL import Image
    im = Image.open(path).convert('RGB')
    if im.size[0] * im.size[1] > 1048576:
        s = (1048576 / float(im.size[0] * im.size[1])) ** 0.5
        im = im.resize((max(1, int(im.size[0] * s)), max(1, int(im.size[1] * s))))
    b = io.BytesIO(); im.save(b, 'JPEG', quality=92)
    return 'data:image/jpeg;base64,' + base64.b64encode(b.getvalue()).decode()


def call(path, prompt, timeout=180):
    payload = {'model': MODEL, 'messages': [{'role': 'user', 'content': [
        {'type': 'image_url', 'image_url': {'url': enc(path)}},
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


def load_gt(ds):
    idir, cpath, part = DS_DIRS[ds]
    gt = {}
    if ds == 'ucf':
        with open(cpath, encoding='utf-8-sig') as f:
            for r in csv.DictReader(f):
                if r['split'] == 'Test':
                    gt[os.path.splitext(os.path.basename(r['file']))[0]] = int(r['count'])
    else:
        with open(cpath, encoding='utf-8-sig') as f:
            for r in csv.DictReader(f):
                if r.get('part') == part and r.get('split') == 'test':
                    gt[os.path.splitext(os.path.basename(r['file']))[0]] = int(r['count'])
    return idir, gt


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--ds', required=True, choices=list(DS_DIRS))
    ap.add_argument('--arm', required=True, choices=['base', 'over', 'under'])
    ap.add_argument('--workers', type=int, default=32)
    a = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    idir, gt = load_gt(a.ds)
    names = [n for n in sorted(gt) if os.path.exists(os.path.join(idir, n + '.jpg'))]

    for vtag, _ in P.items():
        # V1 用主实验的 arm 提示词；其余问法用同臂的方向引导前缀 + 该问法
        if vtag == 'V1_json':
            prompt = {
                'base': P['V1_json'],
                'over': '请数出图片中的人数。为避免漏数，请把所有可能存在的目标都计入（包括被遮挡、距离较远、画面模糊、只露出部分的个体）；宁可多算，不可漏算。以JSON格式输出：{"count": 数量}，只输出JSON。',
                'under': '请数出图片中的人数。请只统计你能完全确认的目标（轮廓清晰、无遮挡、可明确判断的个体）；宁可漏算，不可多算。以JSON格式输出：{"count": 数量}，只输出JSON。',
            }[a.arm]
        else:
            steer = {'base': '', 'over': ' 为避免漏数，宁可多算不可漏算。', 'under': ' 只统计能完全确认的目标，宁可漏算不可多算。'}[a.arm]
            prompt = P[vtag] + steer
        out_csv = os.path.join(OUT, '%s_%s_%s.csv' % (a.ds, a.arm, vtag))
        done = set()
        if os.path.exists(out_csv):
            with open(out_csv, encoding='utf-8-sig', newline='') as f:
                for r in csv.DictReader(f):
                    if r.get('parse_ok') == '1':
                        done.add(r['item'])
        todo = [x for x in names if x not in done]
        fh = open(out_csv, 'a', encoding='utf-8-sig', newline='')
        wr = csv.writer(fh)
        if not os.path.exists(out_csv) or os.path.getsize(out_csv) == 0:
            wr.writerow(['item', 'gt', 'pred', 'parse_ok', 'abstain', 'raw', 'latency_s'])
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
                t0 = time.time()
                try:
                    raw = call(os.path.join(idir, nm + '.jpg'), prompt)
                    pred = parse(raw)
                    low = raw.lower()
                    abst = 1 if (pred == 0 or any(k in low for k in ['too many', '无法', '数不清', '难以', '众多'])) else 0
                    with _lock:
                        wr.writerow([nm, gt[nm], pred if pred is not None else '',
                                     1 if pred is not None else 0, abst, raw.replace('\n', ' ')[:100],
                                     '%.2f' % (time.time() - t0)])
                        fh.flush()
                        st['abst'] += abst
                except Exception as ex:
                    with _lock:
                        wr.writerow([nm, gt[nm], '', 0, 0, str(ex)[:80], '']); fh.flush()
                with _lock:
                    st['n'] += 1

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
            print('[dp:%s/%s/%s] n=%d MAE=%.1f ME=%+.1f rho=%+.1f%% 弃权率=%.1f%% | 排除后 ME=%+.1f rho=%+.1f%%' % (
                a.ds, a.arm, vtag, len(e), sum(abs(x) for x in e) / len(e), sum(e) / len(e),
                100 * sum(e) / len(e) / mg, 100.0 * A_ / len(P_),
                sum(p - g for p, g in keep) / max(1, len(keep)),
                100 * (sum(p - g for p, g in keep) / max(1, len(keep))) / (sum(g for _, g in keep) / max(1, len(keep)))
                if keep else float('nan')), flush=True)


if __name__ == '__main__':
    main()
