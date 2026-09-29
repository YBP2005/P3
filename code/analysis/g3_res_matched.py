#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""g3_res_matched.py — G1 的 VLM 半边：**行程匹配**的像素预算阶梯。

与已发表的 `res_ctrl.py` 的关系：`fit()` 与 `parse()` **逐字复用**（不改），
只把 `BUDGETS` 换成一组**行程恰好等于检测 τ 阶梯**（0.05→0.5 = 10.0×）的档位，
并加一个 `rep` 维度（同会话 3 遍，本稿既有的噪声口径）。

冻结判据见 `/root/g3_criteria_frozen.json`（启动时断言其 md5）。

用法：
    SERVED_MODEL=Qwen3-VL-32B-Instruct LOCAL_API=http://127.0.0.1:8006/v1/chat/completions \
    ABSTAIN_OUT=/root/g3_res python3 g3_res_matched.py visdrone 24
"""
import base64
import csv
import io
import json
import math
import os
import queue
import re
import sys
import threading
import time
import urllib.request

API = os.environ.get('LOCAL_API', 'http://127.0.0.1:8006/v1/chat/completions')
MODEL = os.environ.get('SERVED_MODEL', 'Qwen3-VL-32B-Instruct')
OUT = os.environ.get('ABSTAIN_OUT', '/root/g3_res')
CRIT = '/root/g3_criteria_frozen.json'
os.makedirs(OUT, exist_ok=True)

# ★ 冻结提示词：逐字复制自 res_ctrl.py 的 PR
PR = ('请数出图片中的人数（人群中的每个人头或人体），不要遗漏，不要重复，'
      '以JSON格式输出：{"count": 数量}，只输出JSON。')

# ★ 行程匹配的 8 档：k=0..7 等比，1048576 / 104856 = 10.0000×（= 检测 τ 阶梯的行程）
BUDGETS = [1048576, 754655, 543118, 390867, 281300, 202447, 145698, 104856]
REPS = 3
STRIDE = 28


def fit(w, h, budget):
    """把 (w,h) 缩放到总像素 <= budget，长宽取 STRIDE 的整数倍；budget=0 表示不缩放。
    ★ 逐字复制自 res_ctrl.py（冻结件）。"""
    if budget <= 0 or w * h <= budget:
        return w, h
    s = math.sqrt(budget / float(w * h))
    nw = max(STRIDE * 2, int(w * s) // STRIDE * STRIDE)
    nh = max(STRIDE * 2, int(h * s) // STRIDE * STRIDE)
    while nw * nh > budget:
        nw -= STRIDE; nh -= STRIDE
        nw = max(STRIDE * 2, nw); nh = max(STRIDE * 2, nh)
        if nw <= STRIDE * 2 and nh <= STRIDE * 2:
            break
    return nw, nh


def parse(raw):
    """★ 逐字复制自 res_ctrl.py（冻结件）。"""
    m = re.search(r'\{\s*(?:count|计数|数量|人数)\s*[:：]\s*(\d+)', raw, re.I)
    if m:
        return int(m.group(1))
    m = re.search(r'-?\d+', raw.replace(',', ''))
    return int(m.group(0)) if m else None


def call(im, timeout=240):
    b = io.BytesIO()
    im.save(b, 'JPEG', quality=92)
    url = 'data:image/jpeg;base64,' + base64.b64encode(b.getvalue()).decode()
    payload = {'model': MODEL, 'messages': [{'role': 'user', 'content': [
        {'type': 'image_url', 'image_url': {'url': url}},
        {'type': 'text', 'text': PR}]}], 'temperature': 0.0, 'max_tokens': 64}
    req = urllib.request.Request(API, data=json.dumps(payload).encode(),
                                 headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())['choices'][0]['message']['content']


def load_gt(ds):
    if ds == 'visdrone':
        idir = '/root/aerial/visdrone/images'
        gt = {}
        with open('/root/aerial/gt_visdrone.csv', encoding='utf-8-sig') as f:
            for r in csv.DictReader(f):
                gt[r['item']] = int(r['gt'])
        return idir, gt, '.jpg'
    if ds == 'st_a':
        idir = '/root/dense/shanghaitech/images/part_A_test'
        gt = {}
        with open('/root/dense/shanghaitech/counts.csv', encoding='utf-8-sig') as f:
            for r in csv.DictReader(f):
                if r.get('part') == 'part_A' and r.get('split') == 'test':
                    gt[os.path.splitext(os.path.basename(r['file']))[0]] = int(r['count'])
        return idir, gt, '.jpg'
    raise SystemExit('unknown ds ' + ds)


def main():
    ds = sys.argv[1] if len(sys.argv) > 1 else 'visdrone'
    workers = int(sys.argv[2]) if len(sys.argv) > 2 else 24
    cfg = json.load(open(CRIT, encoding='utf-8'))
    assert cfg['design']['budgets_matched_10x'] == BUDGETS, '档位与冻结判据不符'
    print('[g3/%s] 冻结判据 %s ｜ model=%s' % (ds, CRIT, MODEL), flush=True)

    from PIL import Image
    idir, gt, ext = load_gt(ds)
    names = [n for n in sorted(gt) if os.path.exists(os.path.join(idir, n + ext))]
    out_csv = os.path.join(OUT, 'res_ctrl_matched_%s.csv' % ds)
    done = set()
    if os.path.exists(out_csv):
        with open(out_csv, encoding='utf-8-sig', newline='') as f:
            for r in csv.DictReader(f):
                if r.get('parse_ok') == '1' and r.get('http_err') == '0':
                    done.add((r['item'], str(r['budget']), str(r['rep'])))
    jobs = [(n, b, rp) for n in names for b in BUDGETS for rp in range(1, REPS + 1)
            if (n, str(b), str(rp)) not in done]
    print('[g3/%s] 图=%d 档=%d 遍=%d 任务=%d（已完成 %d）'
          % (ds, len(names), len(BUDGETS), REPS, len(jobs), len(names) * len(BUDGETS) * REPS - len(jobs)),
          flush=True)
    new = not os.path.exists(out_csv) or os.path.getsize(out_csv) == 0
    fh = open(out_csv, 'a', encoding='utf-8-sig', newline='')
    wr = csv.writer(fh)
    if new:
        wr.writerow(['item', 'dataset', 'budget', 'rep', 'gt', 'nat_w', 'nat_h', 'eff_w', 'eff_h',
                     'eff_px', 'pred', 'parse_ok', 'abstain', 'http_err', 'model', 'raw'])
    q = queue.Queue()
    for j in jobs:
        q.put(j)
    lock = threading.Lock()
    n = [0]
    t0 = time.time()

    def work():
        while True:
            try:
                it, budget, rp = q.get_nowait()
            except queue.Empty:
                return
            p = os.path.join(idir, it + ext)
            row = None
            try:
                im = Image.open(p).convert('RGB')
                nw, nh = fit(im.width, im.height, budget)
                im2 = im if (nw, nh) == (im.width, im.height) else im.resize((nw, nh), Image.BICUBIC)
                raw = call(im2)
                pred = parse(raw)
                row = [it, ds, budget, rp, gt[it], im.width, im.height, im2.width, im2.height,
                       im2.width * im2.height, pred, 1 if pred is not None else 0,
                       0, 0, MODEL, raw[:300]]
            except Exception as e:
                row = [it, ds, budget, rp, gt.get(it, ''), '', '', '', '', '', '', 0, 0, 1,
                       MODEL, 'ERR:%s' % str(e)[:120]]
            with lock:
                wr.writerow(row)
                n[0] += 1
                if n[0] % 100 == 0:
                    fh.flush()
                    print('    %d/%d  (%.1f 分钟, %.0f 项/分)'
                          % (n[0], len(jobs), (time.time() - t0) / 60, n[0] / max(1e-9, (time.time() - t0) / 60)),
                          flush=True)
    ths = [threading.Thread(target=work) for _ in range(workers)]
    for t in ths:
        t.start()
    for t in ths:
        t.join()
    fh.close()
    print('  [g3/%s] 写 %d 行 -> %s（%.1f 分钟）' % (ds, n[0], out_csv, (time.time() - t0) / 60), flush=True)
    print('DONE', flush=True)


if __name__ == '__main__':
    main()
