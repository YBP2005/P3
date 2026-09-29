#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""probe_gen.py — 通用"清单驱动"探测运行器（Batch 2 全部实验共用）

清单列: exp,item,path,gt,arm,budget,nsample,temp
  arm    : 提示契约名（见 PROMPTS）
  budget : 0=原生；>0 时缩放到该总像素（长宽取 28 的整数倍）
  nsample: 同一图重复采样次数（E7 用）
输出: $PROBE_OUT/<exp>.csv
断点续跑：按 (exp,item,arm,budget,sample) 跳过已完成行。
"""
import base64, csv, io, json, math, os, queue, re, sys, threading, time
import urllib.request

API = os.environ.get('LOCAL_API', 'http://127.0.0.1:8000/v1/chat/completions')
MODEL = os.environ.get('SERVED_MODEL', 'qwen3-vl-32b-awq')
MAN = os.environ.get('MANIFEST', '/root/b2/manifest.csv')
OUT = os.environ.get('PROBE_OUT', '/root/b2/out')
os.makedirs(OUT, exist_ok=True)
STRIDE = 28
REFUSE = ['too many', '无法', '数不清', '难以', '众多', 'cannot', 'unable', '抱歉']

PROMPTS = {
 'base': '请数出图片中的人数（人群中的每个人头或人体），不要遗漏，不要重复，'
         '以JSON格式输出：{"count": 数量}，只输出JSON。',
 'forbid0': '请数出图片中的人数（人群中的每个人头或人体），不要遗漏，不要重复。'
            '注意：**不要回答 0**；如果你认为可能是 0，请给出你最接近的估计值。'
            '以JSON格式输出：{"count": 数量}，只输出JSON。',
 'range': '请估计图片中的人数范围（人群中的每个人头或人体）。'
          '以JSON格式输出：{"low": 下界, "high": 上界}，只输出JSON。',
 'choice': '请从以下选项中选择最接近图片中实际人数的选项：0, 10, 50, 100, 500, 1000。'
           '以JSON格式输出：{"choice": 选项}，只输出JSON。',
 'cells': '请数出图片中的细胞个数，不要遗漏，不要重复，'
          '以JSON格式输出：{"count": 数量}，只输出JSON。',
 'objects': '请数出图片中的物体个数（图中出现的可数物体），不要遗漏，不要重复，'
            '以JSON格式输出：{"count": 数量}，只输出JSON。',
}
_lock = threading.Lock()


def fit(w, h, budget):
    if budget <= 0 or w * h <= budget:
        return w, h
    s = math.sqrt(budget / float(w * h))
    nw = max(STRIDE * 2, int(w * s) // STRIDE * STRIDE)
    nh = max(STRIDE * 2, int(h * s) // STRIDE * STRIDE)
    while nw * nh > budget and (nw > STRIDE * 2 or nh > STRIDE * 2):
        nw = max(STRIDE * 2, nw - STRIDE); nh = max(STRIDE * 2, nh - STRIDE)
    return nw, nh


def call(im, prompt, temp, timeout=240):
    b = io.BytesIO(); im.save(b, 'JPEG', quality=92)
    url = 'data:image/jpeg;base64,' + base64.b64encode(b.getvalue()).decode()
    payload = {'model': MODEL, 'messages': [{'role': 'user', 'content': [
        {'type': 'image_url', 'image_url': {'url': url}},
        {'type': 'text', 'text': prompt}]}], 'temperature': temp, 'max_tokens': 96}
    if temp and temp > 0:
        payload['top_p'] = 1.0; payload['seed'] = None
        payload.pop('seed')
    req = urllib.request.Request(API, data=json.dumps(payload).encode(),
                                 headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        d = json.loads(r.read().decode())
    ch = d['choices'][0]
    return (ch['message']['content'], ch.get('finish_reason'),
            (d.get('usage') or {}).get('completion_tokens'))


def parse(raw, arm):
    """返回 (pred, pred2, ok)。range 臂 pred=low, pred2=high；choice 臂 pred=选项值。"""
    t = raw.replace(',', '')
    if arm == 'range':
        m = re.search(r'"?(?:low|下界|min)"?\s*[:：]\s*(\d+)', t, re.I)
        m2 = re.search(r'"?(?:high|上界|max)"?\s*[:：]\s*(\d+)', t, re.I)
        if m and m2:
            return int(m.group(1)), int(m2.group(1)), 1
        nums = [int(x) for x in re.findall(r'\d+', t)]
        if len(nums) >= 2:
            return min(nums[0], nums[1]), max(nums[0], nums[1]), 1
        return None, None, 0
    m = re.search(r'"?(?:count|choice|计数|数量|人数|选项)"?\s*[:：]\s*(\d+)', t, re.I)
    if m:
        return int(m.group(1)), None, 1
    m = re.search(r'\d+', t)
    return (int(m.group(0)), None, 1) if m else (None, None, 0)


def main():
    from PIL import Image
    rows = list(csv.DictReader(open(MAN, encoding='utf-8-sig', newline='')))
    exps = sorted({r['exp'] for r in rows})
    print('[probe_gen] model=%s 清单=%d 行，实验=%s' % (MODEL, len(rows), exps), flush=True)
    for exp in exps:
        sub = [r for r in rows if r['exp'] == exp]
        out_csv = os.path.join(OUT, '%s.csv' % exp)
        done = set()
        if os.path.exists(out_csv):
            for r in csv.DictReader(open(out_csv, encoding='utf-8-sig', newline='')):
                if r.get('parse_ok') == '1' and (r.get('http_err') or '0') == '0':
                    done.add((r['item'], r['arm'], r['budget'], r['sample']))
        jobs = []
        for r in sub:
            ns = max(1, int(r.get('nsample') or 1))
            for s in range(ns):
                if (r['item'], r['arm'], r['budget'], str(s)) not in done:
                    jobs.append((r, s))
        new = not os.path.exists(out_csv) or os.path.getsize(out_csv) == 0
        fh = open(out_csv, 'a', encoding='utf-8-sig', newline='')
        wr = csv.writer(fh)
        if new:
            wr.writerow(['exp', 'item', 'domain', 'arm', 'budget', 'sample', 'temp', 'gt',
                         'nat_w', 'nat_h', 'eff_px', 'pred', 'pred2', 'parse_ok', 'abstain',
                         'refuse', 'http_err', 'finish', 'ctok', 'model', 'raw'])
        print('[probe_gen/%s] 任务=%d' % (exp, len(jobs)), flush=True)
        if not jobs:
            fh.close(); continue
        q = queue.Queue()
        for j in jobs:
            q.put(j)
        st = {'n': 0, 't0': time.time(), 'ab': 0, 'er': 0}

        def work():
            while True:
                try:
                    r, s = q.get_nowait()
                except queue.Empty:
                    return
                try:
                    im = Image.open(r['path']).convert('RGB')
                    w0, h0 = im.size
                    b = int(float(r.get('budget') or 0))
                    tw, th = fit(w0, h0, b)
                    if (tw, th) != (w0, h0):
                        im = im.resize((tw, th), Image.LANCZOS)
                    eff = im.size[0] * im.size[1]
                    temp = float(r.get('temp') or 0.0)
                    arm = r['arm']
                    pr = (r.get('prompt') or '').strip() or PROMPTS[arm]
                    raw, fin, ctok = call(im, pr, temp)
                    pred, pred2, ok = parse(raw, arm)
                    low = raw.lower()
                    ref = any(k in low for k in REFUSE)
                    httpe = 1 if re.search(r'HTTP Error|<!DOCTYPE|<html', raw, re.I) else 0
                    with _lock:
                        wr.writerow([r['exp'], r['item'], r.get('domain', ''), arm, b, s, temp,
                                     r.get('gt', ''), w0, h0, eff,
                                     pred if pred is not None else '',
                                     pred2 if pred2 is not None else '', ok,
                                     1 if (ok and pred == 0) else 0, 1 if ref else 0,
                                     httpe, fin, ctok if ctok is not None else '', MODEL, raw.replace('\n', ' ')[:110]])
                        fh.flush(); st['ab'] += 1 if (ok and pred == 0) else 0; st['er'] += httpe
                except Exception as ex:
                    with _lock:
                        wr.writerow([r['exp'], r['item'], r.get('domain', ''), r['arm'],
                                     r.get('budget', ''), s, r.get('temp', 0), r.get('gt', ''),
                                     '', '', '', '', '', 0, 0, 0, 1, 'ERR', '', MODEL, str(ex)[:60]])
                        fh.flush(); st['er'] += 1
                with _lock:
                    st['n'] += 1
                    if st['n'] % 150 == 0:
                        el = max(time.time() - st['t0'], 1e-9)
                        print('  %d/%d (%.2f/s zero=%d err=%d eta=%.0fmin)' %
                              (st['n'], len(jobs), st['n'] / el, st['ab'], st['er'],
                               (len(jobs) - st['n']) / max(st['n'] / el, 1e-9) / 60), flush=True)

        th = [threading.Thread(target=work, daemon=True) for _ in range(24)]
        for t in th:
            t.start()
        for t in th:
            t.join()
        fh.close()
        print('[probe_gen/%s] DONE n=%d zero=%d err=%d' % (exp, st['n'], st['ab'], st['er']), flush=True)


if __name__ == '__main__':
    main()
