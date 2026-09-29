# -*- coding: utf-8 -*-
"""19g_probe_fsc.py — **公开基准（FSC-147）专用探针**。

设计要点（为什么这样写）：
  ① **不复制提示词、不复制解析器**：直接 `importlib` 加载远端 `/root/19e_probe_multi.py`，
     复用它的 `P`（契约提示词）、`parse()`、`b64_of()`、`call_img()`。
     ⇒ 与 E2/E3 的仪器**逐字同一**，且 19e 本体**零改动**（md5 仍为 03edb14c98ff…）。
  ② 数据与抽样：读 `/root/fsc147/sample_test_ids.txt`（固定种子、按 GT 分层的 300 张测试图），
     GT 取 `annotation_FSC147_384.json` 的 `points` 数量；跨配置**同一批 item**。
  ③ 输出 schema 与 E2/E3 完全一致：`item, gt, pred, parse_ok, raw, latency_s`，
     写入 `/root/fsc_results/`，便于用同一套判定脚本处理。

用法：
  python /root/19g_probe_fsc.py --model <served-name> --arms base,permit --workers 8 [--n 300]
"""
import argparse
import base64
import csv
import importlib.util
import io
import json
import os
import queue
import sys
import threading
import time

sys.stdout.reconfigure(encoding='utf-8')
FSC = '/root/fsc147'
OUTD = '/root/fsc_results'
P19E = '/root/19e_probe_multi.py'

spec = importlib.util.spec_from_file_location('p19e', P19E)
E = importlib.util.module_from_spec(spec)
spec.loader.exec_module(E)
assert hasattr(E, 'P') and hasattr(E, 'parse') and hasattr(E, 'call_img'), '19e 结构不符，停止'
print('仪器：复用 19e 的 P/parse/call_img（19e 未改动）')


def load_gt():
    ann = json.load(io.open(os.path.join(FSC, 'annotation_FSC147_384.json')))
    gt = {}
    for k, v in ann.items():
        pts = v.get('points') or []
        if pts:
            gt[k] = len(pts)
        else:                       # 极少数条目用 boxes 的 count 兜底
            gt[k] = int(sum(b.get('count', 0) for b in (v.get('boxes') or [])))
    return gt


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--model', required=True)
    ap.add_argument('--arms', default='base,permit')
    ap.add_argument('--n', type=int, default=300)
    ap.add_argument('--workers', type=int, default=8)
    ap.add_argument('--reps', type=int, default=1)
    A = ap.parse_args()
    os.makedirs(OUTD, exist_ok=True)
    gt = load_gt()
    ids = [x.strip() for x in io.open(os.path.join(FSC, 'sample_test_ids.txt')) if x.strip()]
    pick = ids[:A.n]
    from PIL import Image
    for arm in A.arms.split(','):
        outp = os.path.join(OUTD, 'fsc_%s_%s.csv' % (A.model.replace('/', '_'), arm))
        done = set()
        if os.path.exists(outp):
            with io.open(outp, encoding='utf-8-sig') as f:
                done = {r['item'] for r in csv.DictReader(f)}
        todo = []
        for i in pick:
            for r in range(A.reps):
                k = i if A.reps == 1 else '%s#r%d' % (i, r)
                if k not in done:
                    todo.append(k)
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
                base_it = it.split('#r')[0]
                p = os.path.join(FSC, 'images', base_it)
                t0 = time.time()
                try:
                    im = Image.open(p).convert('RGB')
                    raw = E.call_img(E.b64_of(im), E.P[arm], A.model)
                    v = E.parse(raw)
                    ok = 1 if v is not None else 0
                except Exception as e:
                    raw, v, ok = 'ERR:%s' % str(e)[:150], None, 0
                dt = time.time() - t0
                with lock:
                    w.writerow([it, gt.get(base_it, ''), '' if v is None else v, ok, raw[:800], round(dt, 2)])
                    fh.flush()
        ths = [threading.Thread(target=work) for _ in range(A.workers)]
        [t.start() for t in ths]
        [t.join() for t in ths]
        fh.close()
        rows = list(csv.DictReader(io.open(outp, encoding='utf-8-sig')))
        z = sum(1 for r in rows if str(r['pred']).strip() in ('0', '0.0'))
        print('  [%s] %d 行；pred==0 的 %d 个；-> %s' % (arm, len(rows), z, outp))


if __name__ == '__main__':
    main()
