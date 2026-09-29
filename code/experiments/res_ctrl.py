#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""res_ctrl.py — G1：分辨率受控复跑（按"绝对像素预算"控制有效可辨性）

与 14_scalestep.py 的关键区别：
  14_scalestep 用**乘性缩放**（scale=1.0/0.75/...），图像的绝对像素数随数据集原生尺寸变化
  → "可确证性"与"数据集原生分辨率"混在一起，且低端会被处理器的 min_pixels 上采样。
  本脚本改为**绝对像素预算**：把每张图缩放到固定的总像素数（native/1M/800k/400k/200k），
  长宽取 28 的整数倍 → 有效像素预算精确已知，且跨数据集可比。
服务端以 min_pixels=3136, max_pixels=1048576 起（不再上采样、不再二次下采样）。

用法: python res_ctrl.py <st_a|ucf|visdrone> [workers]
环境: SERVED_MODEL / LOCAL_API / ABSTAIN_OUT
输出: $ABSTAIN_OUT/res_ctrl_<ds>.csv
"""
import base64, csv, io, json, math, os, queue, re, sys, threading, time
import urllib.request

API = os.environ.get('LOCAL_API', 'http://127.0.0.1:8000/v1/chat/completions')
MODEL = os.environ.get('SERVED_MODEL', 'internvl25-8b-awq')
OUT = os.environ.get('ABSTAIN_OUT', '/root/res_ctrl/default')
os.makedirs(OUT, exist_ok=True)
PR = ('请数出图片中的人数（人群中的每个人头或人体），不要遗漏，不要重复，'
      '以JSON格式输出：{"count": 数量}，只输出JSON。')
BUDGETS = [0, 1048576, 800000, 400000, 200000]   # 0 = 原生（不缩放）
STRIDE = 28
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
        return idir, gt, '.jpg'
    if ds == 'st_a':
        idir = '/root/dense/shanghaitech/images/part_A_test'
        gt = {}
        with open('/root/dense/shanghaitech/counts.csv', encoding='utf-8-sig') as f:
            for r in csv.DictReader(f):
                if r.get('part') == 'part_A' and r.get('split') == 'test':
                    gt[os.path.splitext(os.path.basename(r['file']))[0]] = int(r['count'])
        return idir, gt, '.jpg'
    if ds == 'visdrone':
        idir = '/root/aerial/visdrone/images'
        gt = {}
        with open('/root/aerial/gt_visdrone.csv', encoding='utf-8-sig') as f:
            for r in csv.DictReader(f):
                gt[r['item']] = int(r['gt'])
        return idir, gt, '.jpg'
    raise SystemExit('unknown ds ' + ds)


def fit(w, h, budget):
    """把 (w,h) 缩放到总像素 <= budget，长宽取 STRIDE 的整数倍；budget=0 表示不缩放"""
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


def call(im, timeout=240):
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
    idir, gt, ext = load_gt(ds)
    names = [n for n in sorted(gt) if os.path.exists(os.path.join(idir, n + ext))]
    lim = int(os.environ.get('RES_CTRL_LIMIT', '0') or 0)
    if lim > 0:
        names = names[:lim]
    out_csv = os.path.join(OUT, 'res_ctrl_%s.csv' % ds)
    done = set()
    if os.path.exists(out_csv):
        with open(out_csv, encoding='utf-8-sig', newline='') as f:
            for r in csv.DictReader(f):
                if r.get('parse_ok') == '1' and r.get('http_err') == '0':
                    done.add((r['item'], r['budget']))
    jobs = [(n, b) for n in names for b in BUDGETS if (n, str(b)) not in done]
    print('[res_ctrl/%s] model=%s 图=%d 任务=%d' % (ds, MODEL, len(names), len(jobs)), flush=True)
    new = not os.path.exists(out_csv) or os.path.getsize(out_csv) == 0
    fh = open(out_csv, 'a', encoding='utf-8-sig', newline='')
    wr = csv.writer(fh)
    if new:
        wr.writerow(['item', 'dataset', 'budget', 'gt', 'nat_w', 'nat_h', 'eff_w', 'eff_h',
                     'eff_px', 'px_per_obj', 'pred', 'parse_ok', 'abstain', 'refuse',
                     'http_err', 'model', 'raw'])
    q = queue.Queue()
    for j in jobs:
        q.put(j)
    st = {'n': 0, 't0': time.time(), 'abst': 0, 'err': 0}

    def work():
        while True:
            try:
                nm, bud = q.get_nowait()
            except queue.Empty:
                return
            try:
                im = Image.open(os.path.join(idir, nm + ext)).convert('RGB')
                nw0, nh0 = im.size
                tw, th = fit(nw0, nh0, bud)
                if (tw, th) != (nw0, nh0):
                    im = im.resize((tw, th), Image.LANCZOS)
                eff = im.size[0] * im.size[1]
                ppo = eff / max(1, gt[nm])
                raw = call(im)
                pred = parse(raw)
                low = raw.lower()
                zero = (pred == 0)
                ref = any(k in low for k in REFUSE)
                httpe = 1 if re.search(r'HTTP Error|<!DOCTYPE|<html', raw, re.I) else 0
                with _lock:
                    wr.writerow([nm, ds, bud, gt[nm], nw0, nh0, im.size[0], im.size[1],
                                 eff, '%.1f' % ppo, pred if pred is not None else '',
                                 1 if pred is not None else 0, 1 if zero else 0,
                                 1 if ref else 0, httpe, MODEL, raw.replace('\n', ' ')[:90]])
                    fh.flush()
                    st['abst'] += int(zero); st['err'] += httpe
            except Exception as ex:
                with _lock:
                    wr.writerow([nm, ds, bud, gt.get(nm, ''), '', '', '', '', '', '', '', 0,
                                 0, 0, 1, MODEL, str(ex)[:70]])
                    fh.flush(); st['err'] += 1
            with _lock:
                st['n'] += 1
                if st['n'] % 200 == 0:
                    el = max(time.time() - st['t0'], 1e-9)
                    print('  %d/%d (%.2f img/s, zero=%d, err=%d, eta=%.0fmin)' % (
                        st['n'], len(jobs), st['n'] / el, st['abst'], st['err'],
                        (len(jobs) - st['n']) / max(st['n'] / el, 1e-9) / 60), flush=True)

    ts = [threading.Thread(target=work, daemon=True) for _ in range(max(1, workers))]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    fh.close()
    print('[res_ctrl/%s] DONE n=%d abstain=%d err=%d' % (ds, st['n'], st['abst'], st['err']), flush=True)


if __name__ == '__main__':
    main()
