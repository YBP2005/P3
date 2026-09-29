#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""05_prompt_family.py — 提示词族敏感性扫描（同一模型、同一批图、5 种问法）

用途：检验"方向可控性"结论是否依赖单一提示词措辞。
用法: python05_prompt_family.py --img-dir /root/sfchd/images --lbl-dir /root/sfchd/labels \
        --out-dir /root/pf --n 500 --workers 16
"""
import argparse, base64, csv, io, json, os, random, re, threading, queue, time
import urllib.request

# 5 种问法：V1=论文选定口径(P2)，V2 直给数字，V3 先定位再计数，V4 内部逐一点数，V5 分块估计
PROMPTS = {
    'V1_json_onedir': ('请逐个数出图片中佩戴安全帽的人数和未佩戴安全帽的人数，不要遗漏，不要重复，'
                       '以JSON格式输出：{"helmet": 戴帽人数, "no_helmet": 未戴帽人数}，只输出JSON。'),
    'V2_two_numbers': '图中佩戴安全帽的人数和未佩戴安全帽的人数分别是多少？只输出两个阿拉伯数字，用逗号分隔，例如 3,1。',
    'V3_locate_first': ('请先在图中逐个定位每个头部/人体并判断其是否佩戴安全帽，再统计两类数量。'
                        '以JSON格式输出：{"helmet": 戴帽人数, "no_helmet": 未戴帽人数}，只输出JSON。'),
    'V4_count_stepwise': ('请在心里逐个标记图中的每个人，确认没有重复和遗漏后给出个数。'
                          '以JSON格式输出：{"helmet": 戴帽人数, "no_helmet": 未戴帽人数}，只输出JSON。'),
    'V5_region_estimate': ('请把图片分成若干区域，逐区域估计人数后求和，分别给出佩戴与未佩戴安全帽的人数。'
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


def gt_of(lbl_dir, name):
    f = os.path.join(lbl_dir, name + '.txt')
    n0 = n1 = 0
    if os.path.exists(f):
        for line in open(f, encoding='utf-8', errors='replace'):
            p = line.split()
            if len(p) >= 5:
                c = int(float(p[0]))
                n0 += (c == 0); n1 += (c == 1)
    return n0, n1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--img-dir', default='/root/sfchd/images')
    ap.add_argument('--lbl-dir', default='/root/sfchd/labels')
    ap.add_argument('--out-dir', default='/root/pf')
    ap.add_argument('--n', type=int, default=500)
    ap.add_argument('--workers', type=int, default=16)
    a = ap.parse_args()
    os.makedirs(a.out_dir, exist_ok=True)

    imgs = sorted(f for f in os.listdir(a.img_dir) if f.lower().endswith('.jpg'))[:a.n]
    names = [os.path.splitext(f)[0] for f in imgs]
    print('[pf] %d 图 × %d 提示词 = %d 次推理' % (len(names), len(PROMPTS), len(names) * len(PROMPTS)), flush=True)

    total = {}
    for tag, prompt in PROMPTS.items():
        out_csv = os.path.join(a.out_dir, 'pf_%s.csv' % tag)
        done = {}
        if os.path.exists(out_csv):
            with open(out_csv, encoding='utf-8-sig', newline='') as f:
                for r in csv.DictReader(f):
                    if r.get('parse_ok') == '1':
                        done[r['img']] = (int(r['hat']), int(r['no_helmet']))
        todo = [x for x in names if x not in done]
        exists = os.path.exists(out_csv)
        fh = open(out_csv, 'a', encoding='utf-8-sig', newline='')
        wr = csv.writer(fh)
        if not exists:
            wr.writerow(['img', 'hat', 'no_helmet', 'parse_ok', 'raw', 'latency_s'])
        q = queue.Queue()
        for x in todo:
            q.put(x)
        st = {'n': 0, 't0': time.time()}

        def w():
            while True:
                try:
                    nm = q.get_nowait()
                except queue.Empty:
                    return
                t0 = time.time()
                try:
                    raw = call(os.path.join(a.img_dir, nm + '.jpg'), prompt)
                    pr = parse(raw)
                    with _lock:
                        wr.writerow([nm, pr[0] if pr else '', pr[1] if pr else '',
                                     1 if pr else 0, raw.replace('\n', ' ')[:100], '%.2f' % (time.time() - t0)])
                        fh.flush()
                except Exception as ex:
                    with _lock:
                        wr.writerow([nm, '', '', 0, '', str(ex)[:80]]); fh.flush()
                with _lock:
                    st['n'] += 1
        ts = [threading.Thread(target=w, daemon=True) for _ in range(max(1, a.workers))]
        for t in ts:
            t.start()
        for t in ts:
            t.join()
        fh.close()

        res = {}
        with open(out_csv, encoding='utf-8-sig', newline='') as f:
            for r in csv.DictReader(f):
                if r.get('parse_ok') == '1':
                    res[r['img']] = (int(r['hat']), int(r['no_helmet']))
        P, T = [], []
        for x in names:
            if x in res:
                P.append(sum(res[x])); T.append(sum(gt_of(a.lbl_dir, x)))
        e = [p - g for p, g in zip(P, T)]
        n = len(e)
        mae = sum(abs(x) for x in e) / n
        me = sum(e) / n
        over = sum(1 for x in e if x > 0) / n
        em = sum(1 for x in e if abs(x) < 0.5) / n
        total[tag] = (n, mae, me, over, em)
        print('[pf] %-18s n=%d MAE=%.3f ME=%+.3f P(over)=%.3f EM=%.3f' % (tag, n, mae, me, over, em), flush=True)

    with open(os.path.join(a.out_dir, 'prompt_family_report.md'), 'w', encoding='utf-8') as f:
        f.write('# 提示词族敏感性（同模型同图，%d 张）\n\n' % len(names))
        f.write('| 提示词 | n | MAE | ME | P(over) | EM | 与 V1 的 ME 差 |\n|---|---|---|---|---|---|---|\n')
        ref = total.get('V1_json_onedir', (0, 0, 0, 0, 0))[2]
        for tag in PROMPTS:
            if tag in total:
                n, mae, me, over, em = total[tag]
                f.write('| %s | %d | %.3f | %+.3f | %.3f | %.3f | %+.3f |\n' % (tag, n, mae, me, over, em, me - ref))
    print('报告: %s/prompt_family_report.md' % a.out_dir)


if __name__ == '__main__':
    main()
