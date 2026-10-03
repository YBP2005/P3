#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""20b_probe_lang.py —— **E-C 语言均衡对照**：把冻结的中文臂提示词做**语义等价英译**，在同一批图上重跑。

## 为什么
两家具名：[external-review] *"跨家族比较时所有家族使用相同中文提示，但**未做语言等价性检验**（如将全部提示
翻译为英文验证结论不变）"*；[external-review] *"部分跨家族率比较受 template × family 混淆（M.19.8）"*。

## 纪律
· 仪器仍是 `/root/19f_probe_ablation.py`（md5 28e82b20a7f4…，**不改**）：`importlib` 载入，
  **逐字复用** `parse()` / `b64_of()` / `call_img()`；
· 只用**另行冻结**的英文提示词表（下表，脚本启动时打印其 md5），**不动** CN 表；
· **同一批 item**（由 `_ea_lang/items.csv` 指定，取自 CN 侧已有产物的 item 列）⇒ 配对比较。
"""
import argparse, csv, hashlib, importlib.util, io, os, queue, sys, threading, time

FROZEN = '/root/19f_probe_ablation.py'
FROZEN_MD5 = '28e82b20a7f468680da11b2e9855cff9'
MANIFEST = '/root/ea_lang/items.csv'

# ★ 冻结的英文提示词表：CN 三臂的语义等价英译（逐字固定，md5 由脚本启动时打印）
EN = {
    'base': ('Count the number of people in the image (every head or body in the crowd). Do not miss any and '
             'do not double-count. Output in JSON format: {"count": number}, output JSON only.'),
    'permit': ('Count the number of people in the image (every head or body in the crowd). If you cannot confirm '
               'each one individually, answer abstain rather than guessing. Output in JSON format: '
               '{"count": number} or {"count": "abstain"}, output JSON only.'),
    'channel': ('Judge the number of people in this image. You may: (1) give a number; (2) answer "cannot_judge" '
                'if you cannot judge; (3) answer "no_people" if there are no recognizable individuals in the '
                'image. Output in JSON format: {"response": ...}, output JSON only.'),
}
IMGDIR = {
    'z0easy': ('/root/z0/images', ''),
    'z0hard': ('/root/z0/images', ''),
    'd0st_a': ('/root/dense/shanghaitech/images/part_A_test', '.jpg'),
    'd0ucf': ('/root/dense/ucf_qnrf/UCF-QNRF_ECCV18/Test', '.jpg'),
}


def load_frozen():
    got = hashlib.md5(open(FROZEN, 'rb').read()).hexdigest()
    assert got == FROZEN_MD5, '冻结探针 md5 不符：%s' % got
    spec = importlib.util.spec_from_file_location('frozen19f', FROZEN)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--model', required=True)
    ap.add_argument('--pool', required=True, choices=sorted(IMGDIR))
    ap.add_argument('--arms', default='base,channel')
    ap.add_argument('--manifest', default=MANIFEST)
    ap.add_argument('--workers', type=int, default=8)
    ap.add_argument('--imgsz', type=int, default=0)
    ap.add_argument('--outdir', default='/root/lang_results')
    A = ap.parse_args()

    M = load_frozen()
    en_md5 = hashlib.md5(('\n'.join(sorted(EN.values()))).encode()).hexdigest()
    print('EN 提示词表 md5 %s（%d 臂）；冻结 CN 表来自 %s md5 %s'
          % (en_md5[:12], len(EN), FROZEN, FROZEN_MD5[:12]))
    os.makedirs(A.outdir, exist_ok=True)
    d, ext = IMGDIR[A.pool]
    items = [r['item'] for r in csv.DictReader(io.open(A.manifest, encoding='utf-8-sig'))
             if r['model'] == A.model and r['pool'] == A.pool]
    print('池 %s：%d 条（同 item 配对）' % (A.pool, len(items)))
    from PIL import Image
    tag = A.model.replace('/', '_')
    for arm in A.arms.split(','):
        assert arm in EN, '未知臂 %s' % arm
        outp = os.path.join(A.outdir, 'e1_%s_%s_%s_en.csv' % (tag, A.pool, arm))
        done = set()
        if os.path.exists(outp):
            done = {r['item'] for r in csv.DictReader(io.open(outp, encoding='utf-8-sig'))}
        todo = [i for i in items if i not in done]
        if not todo:
            print('  [%s/EN] 已完成，跳过' % arm); continue
        q = queue.Queue()
        for i in todo:
            q.put(i)
        fh = open(outp, 'a', newline='', encoding='utf-8')
        w = csv.writer(fh)
        if not done:
            w.writerow(['item', 'gt', 'pred', 'parse_ok', 'raw', 'latency_s'])
        lock = threading.Lock()

        def work():
            while True:
                try:
                    it = q.get_nowait()
                except Exception:
                    return
                ip = os.path.join(d, it if it.endswith(ext or '.jpg') else it + ext)
                try:
                    t0 = time.time()
                    im = Image.open(ip).convert('RGB')
                    if A.imgsz:
                        im.thumbnail((A.imgsz, A.imgsz))
                    raw = M.call_img(M.b64_of(im), EN[arm], A.model)
                    v = M.parse(raw)
                    with lock:
                        w.writerow([it, 0, '' if v is None else v, 1 if v is not None else 0,
                                    (raw or '')[:400], '%.2f' % (time.time() - t0)])
                        fh.flush()
                except Exception as ex:
                    with lock:
                        w.writerow([it, 0, '', 0, 'ERR:' + str(ex)[:200], '0']); fh.flush()
        ts = [threading.Thread(target=work) for _ in range(A.workers)]
        for t in ts:
            t.start()
        for t in ts:
            t.join()
        fh.close()
        n = sum(1 for _ in csv.DictReader(io.open(outp, encoding='utf-8-sig')))
        print('  [%s/EN] %d 行 -> %s' % (arm, n, outp))


if __name__ == '__main__':
    main()
