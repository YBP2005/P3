#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""19_selfconsist.py — 自一致性校准：温度采样 K 次取中位数

动机：VLM 单次采样（温度 0 或 0.7）的预测波动多大？取中位数能否改善偏差？
      更重要的副产物：**5 次采样中"是否弃权"的一致性**——检验弃权是稳定属性还是掷硬币。

设计：对每张图用 temperature=T 采样 K 次，记录全部预测；分析
      ① 单次（第 1 次）vs 中位数的 MAE/ρ
      ② 各次之间的离散度（std / IQR）
      ③ 弃权一致性：K 次全部弃权 / 部分弃权 / 全部作答 的比例
用法: python3 19_selfconsist.py --ds st_a --k 5 --temp 0.7
输出: /root/selfconsist_results/sc_<ds>_k<K>_t<temp>.csv
"""
import argparse, base64, csv, io, json, os, queue, re, sys, threading, time, urllib.request
import numpy as np
from PIL import Image

# ★ 默认本地 vLLM（免费）；如需走云端，设 API_URL + SILICONFLOW_API_KEY
API_URL = os.environ.get('API_URL', 'http://127.0.0.1:8000/v1/chat/completions')
MODEL = os.environ.get('SERVED_MODEL', 'qwen3-vl-32b-awq')
_API_KEY = os.environ.get('SILICONFLOW_API_KEY', '')
OUT = os.environ.get('SC_OUT', '/root/selfconsist_results')
PROMPT = ('请数出图片中的人数（人群中的每个人头或人体），不要遗漏，不要重复，'
          '以JSON格式输出：{"count": 数量}，只输出JSON。')
REFUSE = ['too many', '无法', '数不清', '难以', '众多', 'cannot']
_key_i = [0]
_lock = threading.Lock()


def call(b64, temp, timeout=180):
    for attempt in range(4):
        body = {'model': MODEL, 'messages': [{'role': 'user', 'content': [
            {'type': 'image_url', 'image_url': {'url': 'data:image/jpeg;base64,' + b64}},
            {'type': 'text', 'text': PROMPT}]}], 'temperature': temp, 'max_tokens': 48}
        hdr = {'Content-Type': 'application/json'}
        if _API_KEY:
            hdr['Authorization'] = 'Bearer ' + _API_KEY
        req = urllib.request.Request(API_URL, data=json.dumps(body).encode(), headers=hdr)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode())['choices'][0]['message']['content']
        except urllib.error.HTTPError as e:
            e.read()
            time.sleep(2 + attempt * 3)
        except Exception:
            time.sleep(2 + attempt * 3)
    raise RuntimeError('call failed')


def parse(raw):
    m = re.search(r'\{\s*(?:count|计数|数量|人数)\s*[:：]\s*(\d+)', raw, re.I)
    if m:
        return int(m.group(1))
    m = re.search(r'-?\d+', raw.replace(',', ''))
    return int(m.group(0)) if m else None


def enc(path, max_pixels=1048576):
    im = Image.open(path).convert('RGB')
    if im.size[0] * im.size[1] > max_pixels:
        s = (max_pixels / float(im.size[0] * im.size[1])) ** 0.5
        im = im.resize((max(1, int(im.size[0] * s)), max(1, int(im.size[1] * s))))
    b = io.BytesIO(); im.save(b, 'JPEG', quality=92)
    return base64.b64encode(b.getvalue()).decode()


def load_items(ds, limit=0):
    # 5090 上的数据布局（A 机是 paperB_assets/datasets，故用环境变量区分）
    R = os.environ.get('DATA_ROOT', '/root/dense')
    items = []
    if ds == 'st_a':
        idir = os.path.join(R, 'shanghaitech', 'images', 'part_A_test')
        with open(os.path.join(R, 'shanghaitech', 'counts.csv'), encoding='utf-8-sig') as f:
            for r in csv.DictReader(f):
                if r.get('part') == 'part_A' and r.get('split') == 'test':
                    p = os.path.join(idir, os.path.basename(r['file']))
                    if os.path.exists(p):
                        items.append((os.path.basename(r['file']), p, int(r['count'])))
    elif ds == 'st_b':
        idir = os.path.join(R, 'shanghaitech', 'images', 'part_B_test')
        with open(os.path.join(R, 'shanghaitech', 'counts.csv'), encoding='utf-8-sig') as f:
            for r in csv.DictReader(f):
                if r.get('part') == 'part_B' and r.get('split') == 'test':
                    p = os.path.join(idir, os.path.basename(r['file']))
                    if os.path.exists(p):
                        items.append((os.path.basename(r['file']), p, int(r['count'])))
    elif ds == 'ucf':
        idir = os.path.join(R, 'ucf_qnrf', 'UCF-QNRF_ECCV18', 'Test')
        with open(os.path.join(R, 'ucf_qnrf', 'counts.csv'), encoding='utf-8-sig') as f:
            for r in csv.DictReader(f):
                if r['split'] == 'Test':
                    p = os.path.join(idir, os.path.basename(r['file']))
                    if os.path.exists(p):
                        items.append((os.path.basename(r['file']), p, int(r['count'])))
    items.sort()
    return items[:limit] if limit else items


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--ds', required=True, choices=['st_a', 'st_b', 'ucf'])
    ap.add_argument('--k', type=int, default=5)
    ap.add_argument('--temp', type=float, default=0.7)
    ap.add_argument('--limit', type=int, default=0)
    ap.add_argument('--workers', type=int, default=8)
    a = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    items = load_items(a.ds, a.limit)
    out_csv = os.path.join(OUT, 'sc_%s_k%d_t%g.csv' % (a.ds, a.k, a.temp))
    done = set()
    if os.path.exists(out_csv):
        with open(out_csv, encoding='utf-8-sig', newline='') as f:
            for r in csv.DictReader(f):
                if r.get('parse_ok') == '1':
                    done.add(r['item'])
    jobs = [it for it in items if it[0] not in done]
    print('[sc/%s] 图=%d 任务=%d k=%d temp=%g' % (a.ds, len(items), len(jobs), a.k, a.temp), flush=True)
    fh = open(out_csv, 'a', encoding='utf-8-sig', newline='')
    wr = csv.writer(fh)
    if not os.path.exists(out_csv) or os.path.getsize(out_csv) == 0:
        wr.writerow(['item', 'gt', 'k'] + ['p%d' % i for i in range(1, a.k + 1)] +
                    ['median', 'mean', 'std', 'n_zero', 'parse_ok'])
    q = queue.Queue()
    for j in jobs:
        q.put(j)
    st = {'n': 0, 't0': time.time()}

    def work():
        while True:
            try:
                name, path, gt = q.get_nowait()
            except queue.Empty:
                return
            try:
                b64 = enc(path)
                preds = []
                for _ in range(a.k):
                    preds.append(parse(call(b64, a.temp)))
                ok = all(p is not None for p in preds)
                vals = [p for p in preds if p is not None]
                med = int(np.median(vals)) if vals else ''
                mn = float(np.mean(vals)) if vals else ''
                sd = float(np.std(vals)) if vals else ''
                nz = sum(1 for p in preds if p == 0)
                with _lock:
                    wr.writerow([name, gt, a.k] + [p if p is not None else '' for p in preds] +
                                [med, mn, sd, nz, 1 if ok else 0])
                    fh.flush()
            except Exception as ex:
                with _lock:
                    wr.writerow([name, gt, a.k] + [''] * a.k + ['', '', '', '', 0]); fh.flush()
            with _lock:
                st['n'] += 1
                if st['n'] % 20 == 0:
                    print('  %d/%d (%.2f img/s)' % (
                        st['n'], len(jobs), st['n'] / max(time.time() - st['t0'], 1e-9)), flush=True)

    ts = [threading.Thread(target=work, daemon=True) for _ in range(max(1, a.workers))]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    fh.close()
    print('[sc/%s] 完成' % a.ds, flush=True)


if __name__ == '__main__':
    main()
