#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""20a_probe_truezero.py —— **E-A 驱动器**：在真零池（Z0）上跑与 E2/E3 同一支探针的三条臂。

## 纪律：**绝不改动冻结仪器**
`/root/19f_probe_ablation.py`（md5 28e82b20a7f4…）与其上游 19e（03edb14c98ff…）是 E2/E3 的可比性基础。
本文件**不复制、不改写**它们，而是 `importlib` 动态载入 19f，**直接复用** `P`（全部提示词）、
`parse()`、`b64_of()`、`call_img()`、`load_gt()` 的**同一对象**，并在启动时断言 19f 的 md5 未变。
⇒ 提示词/解析器与语料普查**逐字同一**，只有"读哪些图"这一点不同（Z0 池由 ea_build_z0.py 冻结）。

## 输出
`<outdir>/e1_<served_name>_<ds>_<arm>_native.csv`，列与原探针**逐字相同**：
`item,gt,pred,parse_ok,raw,latency_s`（served_name 与本地对照件命名一致，便于直接 join）。
"""
import argparse, csv, hashlib, importlib.util, os, queue, sys, threading, time

FROZEN = '/root/19f_probe_ablation.py'
FROZEN_MD5 = '28e82b20a7f468680da11b2e9855cff9'
POOL = '/root/z0/gt_z0.csv'


def load_frozen():
    got = hashlib.md5(open(FROZEN, 'rb').read()).hexdigest()
    assert got == FROZEN_MD5, '冻结探针 md5 不符：%s != %s' % (got, FROZEN_MD5)
    spec = importlib.util.spec_from_file_location('frozen19f', FROZEN)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)          # 有 __main__ 守卫 ⇒ 只定义、不执行 main()
    return m


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--model', required=True, help='served model name（须与本地对照件命名一致）')
    ap.add_argument('--arms', default='base,permit,channel')
    ap.add_argument('--ds', required=True, help='z0easy / z0hard')
    ap.add_argument('--pool', default=POOL)
    ap.add_argument('--imgsz', type=int, default=0)
    ap.add_argument('--workers', type=int, default=8)
    ap.add_argument('--n', type=int, default=0, help='0=全部')
    ap.add_argument('--outdir', default='/root/z0_results')
    A = ap.parse_args()

    M = load_frozen()
    os.makedirs(A.outdir, exist_ok=True)
    from PIL import Image

    rows = [r for r in csv.DictReader(open(A.pool, encoding='utf-8-sig'))
            if r['stratum'] == A.ds]
    rows.sort(key=lambda r: r['item'])
    if A.n:
        rows = rows[:A.n]
    print('池 %s：%d 条（gt 全为 %s）' % (A.ds, len(rows), rows[0]['gt'] if rows else '?'))
    variant = ('s%d' % A.imgsz) if A.imgsz else 'native'
    tag = A.model.replace('/', '_')
    for arm in A.arms.split(','):
        if arm not in M.P:
            print('!! 未知臂 %s（可用：%s）' % (arm, ','.join(sorted(M.P)))); continue
        outp = os.path.join(A.outdir, 'e1_%s_%s_%s_%s.csv' % (tag, A.ds, arm, variant))
        done = set()
        if os.path.exists(outp):
            done = {r['item'] for r in csv.DictReader(open(outp, encoding='utf-8-sig'))}
        todo = [r for r in rows if r['item'] not in done]
        if not todo:
            print('  [%s] 已完成，跳过' % arm); continue
        q = queue.Queue()
        for r in todo:
            q.put(r)
        fh = open(outp, 'a', newline='', encoding='utf-8')
        w = csv.writer(fh)
        if not done:
            w.writerow(['item', 'gt', 'pred', 'parse_ok', 'raw', 'latency_s'])
        lock = threading.Lock()
        zc = [0]

        def work():
            while True:
                try:
                    r = q.get_nowait()
                except Exception:
                    return
                ip = os.path.join('/root/z0/images', r['item'])
                try:
                    t0 = time.time()
                    im = Image.open(ip).convert('RGB')
                    if A.imgsz:
                        im.thumbnail((A.imgsz, A.imgsz))
                    b64 = M.b64_of(im)
                    raw = M.call_img(b64, M.P[arm], A.model)
                    lat = time.time() - t0
                    v = M.parse(raw)
                    ok = 1 if v is not None else 0
                    if v == 0 or v == '0':
                        zc[0] += 1
                    with lock:
                        w.writerow([r['item'], r['gt'], '' if v is None else v, ok,
                                    (raw or '')[:400], '%.2f' % lat])
                        fh.flush()
                except Exception as ex:
                    with lock:
                        w.writerow([r['item'], r['gt'], '', 0, 'ERR:' + str(ex)[:200], '0'])
                        fh.flush()
        ts = [threading.Thread(target=work) for _ in range(A.workers)]
        for t in ts:
            t.start()
        for t in ts:
            t.join()
        fh.close()
        n = sum(1 for _ in csv.DictReader(open(outp, encoding='utf-8-sig')))
        print('  [%s] %d 行；其中 pred==0 的 %d 个 -> %s' % (arm, n, zc[0], outp))


if __name__ == '__main__':
    main()
