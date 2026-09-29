import os
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""07_e4_sfchd.py — E4 三臂（SFCHD 全量）在 5090 自建栈上重跑
   提示词与 E4A（API 版）逐字一致；额外记录 abstain 标记
   用法: python07_e4_sfchd.py <base|over|under> [workers]
"""
import base64, csv, io, json, os, queue, re, sys, threading, time
import urllib.request

API = os.environ.get('LOCAL_API', 'http://127.0.0.1:8000/v1/chat/completions')
MODEL = os.environ.get('SERVED_MODEL', 'qwen3-vl-32b-awq')
IMG_DIR = '/root/sfchd_full/images'
LBL_DIR = '/root/sfchd_full/labels'
OUT_DIR = os.environ.get('E4_OUT', '/root/e4_results')
os.makedirs(OUT_DIR, exist_ok=True)

PROMPTS = {
    'base': ('请逐个数出图片中佩戴安全帽的人数和未佩戴安全帽的人数，不要遗漏，不要重复，'
             '以JSON格式输出：{"helmet": 戴帽人数, "no_helmet": 未戴帽人数}，只输出JSON。'),
    'over': ('请数出图片中佩戴安全帽的人数和未佩戴安全帽的人数。为避免漏数，请把所有可能存在的人物都计入'
             '（包括被遮挡、距离较远、画面模糊、只露出部分身体或头部的人）；宁可多算，不可漏算。'
             '以JSON格式输出：{"helmet": 戴帽人数, "no_helmet": 未戴帽人数}，只输出JSON。'),
    'under': ('请数出图片中佩戴安全帽的人数和未佩戴安全帽的人数。请只统计你能完全确认的人物'
              '（轮廓清晰、无遮挡、可明确判断是否佩戴安全帽）；宁可漏算，不可多算。'
              '以JSON格式输出：{"helmet": 戴帽人数, "no_helmet": 未戴帽人数}，只输出JSON。'),
}
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
        return json.loads(r.read().decode())['choices'][0]['message']['content']


def parse(raw):
    m = re.search(r'\{"helmet"\s*:\s*(\d+)\s*,\s*"no_helmet"\s*:\s*(\d+)\s*\}', raw, re.I)
    if m:
        return int(m.group(1)), int(m.group(2))
    m = re.search(r'\{helmet\s*:\s*(\d+)\s*,\s*no_helmet\s*:\s*(\d+)\s*\}', raw, re.I)
    if m:
        return int(m.group(1)), int(m.group(2))
    nums = re.findall(r'\d+', raw)
    return (int(nums[0]), int(nums[1])) if len(nums) >= 2 else None


def load_gt():
    gt = {}
    for fn in os.listdir(LBL_DIR):
        if not fn.endswith('.txt'):
            continue
        n0 = n1 = 0
        for line in open(os.path.join(LBL_DIR, fn), encoding='utf-8', errors='replace'):
            p = line.split()
            if len(p) >= 5:
                c = int(float(p[0]))
                n0 += (c == 0); n1 += (c == 1)
        gt[fn[:-4]] = (n0, n1)
    return gt


def main():
    tag = sys.argv[1]
    workers = int(sys.argv[2]) if len(sys.argv) > 2 else 24
    prompt = PROMPTS[tag]
    gt = load_gt()
    names = sorted(gt)
    # 支持环境变量：E4_LIMIT 限制图像数（用于 8B 子集对照），OUT_TAG 区分输出文件名
    limit = int(os.environ.get('E4_LIMIT', '0') or 0)
    out_tag = os.environ.get('OUT_TAG', '') or ''
    if limit:
        names = names[:limit]
    out_csv = os.path.join(OUT_DIR, 'E4L%s_vlm_%s_results.csv' % ('_' + out_tag if out_tag else '', tag))
    done = set()
    if os.path.exists(out_csv):
        with open(out_csv, encoding='utf-8-sig', newline='') as f:
            for r in csv.DictReader(f):
                if r.get('parse_ok') == '1':
                    done.add(r['img'])
    todo = [x for x in names if x not in done]
    print('[E4L/%s] total=%d done=%d todo=%d workers=%d' % (tag, len(names), len(done), len(todo), workers), flush=True)
    exists = os.path.exists(out_csv)
    fh = open(out_csv, 'a', encoding='utf-8-sig', newline='')
    wr = csv.writer(fh)
    if not exists:
        wr.writerow(['img', 'hat', 'no_helmet', 'parse_ok', 'raw', 'latency_s', 'abstain'])
    q = queue.Queue()
    for x in todo:
        q.put(x)
    st = {'n': 0, 'fail': 0, 'abst': 0, 't0': time.time()}

    def work():
        while True:
            try:
                nm = q.get_nowait()
            except queue.Empty:
                return
            t0 = time.time()
            try:
                raw = call(os.path.join(IMG_DIR, nm + '.jpg'), prompt)
                pr = parse(raw)
                low = raw.lower()
                abst = 1 if (pr == (0, 0) or any(k in low for k in
                             ['too many', '无法', '数不清', '难以', '众多'])) else 0
                with _lock:
                    wr.writerow([nm, pr[0] if pr else '', pr[1] if pr else '',
                                 1 if pr else 0, raw.replace('\n', ' ')[:120],
                                 '%.2f' % (time.time() - t0), abst])
                    fh.flush()
                    st['abst'] += abst
            except Exception as e:
                with _lock:
                    st['fail'] += 1
                    wr.writerow([nm, '', '', 0, '', str(e)[:120], 0]); fh.flush()
            with _lock:
                st['n'] += 1
                if st['n'] % 500 == 0:
                    el = time.time() - st['t0']
                    print('[E4L/%s] %d/%d (%.2f img/s) fail=%d abst=%d' % (
                        tag, st['n'], len(todo), st['n'] / max(el, 1e-9), st['fail'], st['abst']), flush=True)

    ts = [threading.Thread(target=work, daemon=True) for _ in range(max(1, workers))]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    fh.close()
    print('[E4L/%s] DONE todo=%d fail=%d abst=%d -> %s' % (tag, len(todo), st['fail'], st['abst'],
                                                           out_csv), flush=True)


if __name__ == '__main__':
    main()
