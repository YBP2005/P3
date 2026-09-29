#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""adopt_contract_probe.py — **可采用件**：把本稿的契约实验搬到任意模型/数据集上（单文件、零依赖）。

设计目标（这是评审要的"a transferable framework others can adopt"）：
  · **不需要**本仓库的任何模块、语料、标注或检测框；只需要一个 OpenAI 兼容端点 + 一个图片目录（或 CSV 清单）。
  · 三个契约臂的提示词**与原稿逐字相同**（`PROMPTS` 与 19e 的 P 字典一致；本文件自包含）。
  · 输出与原稿同 schema 的逐图 CSV（item, gt, pred, parse_ok, raw, latency_s），便于与 `adopt_report.py` 对接。
  · 温度 0、单图单次、`max_tokens 128`——与论文的固定栈一致。

用法：
  export ADOPT_API=http://127.0.0.1:8000/v1/chat/completions     # 你的服务端点（vLLM 等）
  export ADOPT_KEY=dummy
  python adopt_contract_probe.py --model <served-name> --images /path/to/imgs \
         --gt-csv /path/to/gt.csv --arms base,permit,channel --n 150 --workers 8 --outdir ./out

  --images   图片目录（文件名即 item）
  --gt-csv   两列 CSV：item,gt（可选；缺省则 gt 列留空，`adopt_report.py` 的双口径部分需要它）
  完成后： python adopt_report.py --dir ./out --criteria adopt_criteria.json
"""
import argparse
import base64
import csv
import io
import json
import os
import queue
import re
import sys
import threading
import time
import urllib.request

API = os.environ.get('ADOPT_API', 'http://127.0.0.1:8000/v1/chat/completions')
KEY = os.environ.get('ADOPT_KEY', 'dummy')

# —— 与论文 19e 探针**逐字相同**的三个契约臂（base / permit / channel）——
PROMPTS = {
    'base': ('请数出图片中的人数（人群中的每个人头或人体），不要遗漏，不要重复，'
             '以JSON格式输出：{"count": 数量}，只输出JSON。'),
    'permit': ('请数出图片中的人数（人群中的每个人头或人体）。如果你无法逐个确证，'
               '请回答 abstain，而不要猜测。以JSON格式输出：{"count": 数量} 或 {"count": "abstain"}，只输出JSON。'),
    'channel': ('请判断这张图片中的人数。你可以：①给出数字；②回答 "cannot_judge" 表示无法判断；'
                '③回答 "no_people" 表示画面中没有可辨认的个体。以JSON格式输出：{"response": ...}，只输出JSON。'),
}


def b64_of(im, quality=92):
    buf = io.BytesIO()
    im.save(buf, 'JPEG', quality=quality)
    return base64.b64encode(buf.getvalue()).decode()


def call_img(b64, prompt, model, timeout=180, retries=5):
    payload = {'model': model, 'messages': [{'role': 'user', 'content': [
        {'type': 'image_url', 'image_url': {'url': 'data:image/jpeg;base64,' + b64}},
        {'type': 'text', 'text': prompt}]}], 'temperature': 0.0, 'max_tokens': 128}
    req = urllib.request.Request(API, data=json.dumps(payload).encode(),
                                 headers={'Content-Type': 'application/json',
                                          'Authorization': 'Bearer ' + KEY})
    last = None
    for a in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode())['choices'][0]['message']['content']
        except Exception as ex:                     # 429/5xx 退避重试；其余直接抛出
            last = ex
            code = getattr(ex, 'code', None)
            if code is not None and code not in (429, 500, 502, 503, 504):
                raise
            time.sleep(min(20, 2 * (a + 1)))
    raise last if last else RuntimeError('retry exhausted')


def parse(raw):
    """与论文 19e 的 parse() 同规则：先找 {count|response: 值}，再退化为第一个整数。"""
    m = re.search(r'\{\s*(?:count|response|计数|数量|人数)\s*[:：]\s*"?(\d+|abstain|cannot_judge|no_people)',
                  raw, re.I)
    if m:
        v = m.group(1)
        return int(v) if v.isdigit() else v
    m = re.search(r'-?\d+', raw.replace(',', ''))
    return int(m.group(0)) if m else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--model', required=True)
    ap.add_argument('--images', required=True)
    ap.add_argument('--gt-csv', default='')
    ap.add_argument('--arms', default='base,permit,channel')
    ap.add_argument('--n', type=int, default=150)
    ap.add_argument('--workers', type=int, default=8)
    ap.add_argument('--outdir', default='./out')
    A = ap.parse_args()
    os.makedirs(A.outdir, exist_ok=True)

    gt = {}
    if A.gt_csv and os.path.exists(A.gt_csv):
        for r in csv.DictReader(io.open(A.gt_csv, encoding='utf-8-sig')):
            gt[r['item']] = r['gt']

    exts = ('.jpg', '.jpeg', '.png', '.bmp', '.tif', '.tiff')
    files = sorted(f for f in os.listdir(A.images) if f.lower().endswith(exts))
    if not files:
        print('!! 图片目录里没有图片：%s' % A.images)
        return 2
    step = max(1, len(files) // max(1, A.n))
    pick = files[::step][:A.n]
    print('图片 %d 张；本次抽 %d 张（等间隔，固定顺序 ⇒ 各臂同一批 item）' % (len(files), len(pick)))

    from PIL import Image
    for arm in A.arms.split(','):
        if arm not in PROMPTS:
            print('!! 未知臂：%s（可用：%s）' % (arm, ','.join(PROMPTS)))
            return 2
        outp = os.path.join(A.outdir, 'adopt_%s_%s.csv' % (A.model.replace('/', '_'), arm))
        done = set()
        if os.path.exists(outp):
            with io.open(outp, encoding='utf-8-sig') as f:
                done = {r['item'] for r in csv.DictReader(f)}
        todo = [i for i in pick if i not in done]
        if not todo:
            print('  [%s] 已完成，跳过' % arm)
            continue
        q = queue.Queue()
        for i in todo:
            q.put(i)
        lock = threading.Lock()
        newf = not os.path.exists(outp)
        fh = io.open(outp, 'a', newline='', encoding='utf-8')
        w = csv.writer(fh)
        if newf:
            w.writerow(['item', 'gt', 'pred', 'parse_ok', 'raw', 'latency_s'])

        def work():
            while True:
                try:
                    it = q.get_nowait()
                except Exception:
                    return
                t0 = time.time()
                try:
                    im = Image.open(os.path.join(A.images, it)).convert('RGB')
                    raw = call_img(b64_of(im), PROMPTS[arm], A.model)
                    v = parse(raw)
                    ok = 1 if v is not None else 0
                except Exception as e:
                    raw, v, ok = 'ERR:%s' % str(e)[:150], None, 0
                with lock:
                    w.writerow([it, gt.get(it, ''), '' if v is None else v, ok, raw[:800],
                                round(time.time() - t0, 2)])
                    fh.flush()
        ths = [threading.Thread(target=work) for _ in range(A.workers)]
        [t.start() for t in ths]
        [t.join() for t in ths]
        fh.close()
        rows = list(csv.DictReader(io.open(outp, encoding='utf-8-sig')))
        z = sum(1 for r in rows if str(r['pred']).strip() in ('0', '0.0'))
        print('  [%s] %d 行；pred==0 的 %d 个 -> %s' % (arm, len(rows), z, outp))
    print('\n下一步：python adopt_report.py --dir %s --criteria adopt_criteria.json' % A.outdir)
    return 0


if __name__ == '__main__':
    sys.exit(main())
