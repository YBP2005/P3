#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""pf_p0a_probe.py — P0-A：第二血统（InternVL3.5-38B-BF16）在**锚点自身精度**上的
**英文臂**与**缺失的契约臂**（CN permit / CN channel）。

★ 本文件是**适配件**，不是未改动的原脚本：`20b_probe_lang.py` 把四个池写死
  （z0easy/z0hard/d0_st_a/d0_ucf），**装不下 482 项密集集**，故原样无法寻址本轮的格。
  本包装器**按 import 取用**三份冻结件，**不转录任何一个字**的提示词：
    · `/root/pf_p0_probe.py`      —— 取图 / b64 / 调用 / 解析 / CSV schema（与 B1 那轮同一套）
    · `/root/19f_probe_ablation.py`（md5 断言）—— CN 的 `P['permit']` / `P['channel']`
    · `/root/20b_probe_lang.py`   —— 冻结英文表 `EN['base'|'permit'|'channel']`
★ 明示偏离（已写进判据件）：`20b` 把 `gt` 写成 0；本件对 **EN 格也写真 gt**（来自 482 冻结清单），
  使 EN 侧也能算 S、且 CN/EN 可配对比较。CSV schema 不变。

用法：
  python3 pf_p0a_probe.py --api http://127.0.0.1:8021/v1/chat/completions \
      --model InternVL3_5-38B-BF16 --manifest /root/pf_pilot/pf_items_dense482.json \
      --pool zero --arm en_channel --start 1 --out /root/p0a/P0A_en_channel_zero_start1.csv \
      [--workers 4] [--dry]
"""
import argparse
import csv
import hashlib
import importlib.util
import io
import json
import os
import queue
import sys
import threading
import time

P0 = '/root/pf_p0_probe.py'
CNF = '/root/19f_probe_ablation.py'
CNF_MD5 = '28e82b20a7f468680da11b2e9855cff9'
LANG = '/root/20b_probe_lang.py'
ARMS = ('cn_base', 'cn_permit', 'cn_channel', 'en_base', 'en_permit', 'en_channel')


def load(path, want_md5=None, alias=None):
    if want_md5:
        got = hashlib.md5(open(path, 'rb').read()).hexdigest()
        assert got == want_md5, '!! %s md5 %s != %s' % (path, got, want_md5)
    spec = importlib.util.spec_from_file_location(alias or os.path.basename(path)[:-3], path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def norm(e):
    """482 清单里的条目形状不写死：dict 或裸串都吃。"""
    if isinstance(e, dict):
        it = e.get('item') or e.get('name') or e.get('file') or e.get('img')
        gt = e.get('gt', e.get('count', ''))
        dom = e.get('domain') or e.get('dom') or e.get('ds') or e.get('pool') or ''
        return it, gt, dom
    return str(e), '', ''


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--api', required=True)
    ap.add_argument('--model', required=True)
    ap.add_argument('--manifest', required=True)
    ap.add_argument('--pool', required=True, choices=('zero', 'nonzero'))
    ap.add_argument('--arm', required=True, choices=ARMS)
    ap.add_argument('--start', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--workers', type=int, default=4)
    ap.add_argument('--dry', action='store_true')
    A = ap.parse_args()

    p0 = load(P0)
    cnf = load(CNF, CNF_MD5, alias='frozen19f')
    lang = load(LANG)
    P = {'cn_base': p0.BASE_PROMPT,
         'cn_permit': cnf.P['permit'], 'cn_channel': cnf.P['channel'],
         'en_base': lang.EN['base'], 'en_permit': lang.EN['permit'], 'en_channel': lang.EN['channel']}
    prompt = P[A.arm]
    # 打印指纹：三份输入 + 本件所用提示词的 md5（可复核）
    print('== P0-A ==')
    for pth in (P0, CNF, LANG, os.path.abspath(__file__)):
        print('  md5 %s  %s' % (hashlib.md5(open(pth, 'rb').read()).hexdigest()[:16], pth))
    print('  prompt md5 %s  (arm=%s, %d 字符)' % (hashlib.md5(prompt.encode()).hexdigest()[:16], A.arm, len(prompt)))
    print('  api=%s model=%s pool=%s start=%s workers=%d' % (A.api, A.model, A.pool, A.start, A.workers))

    man = json.load(io.open(A.manifest, encoding='utf-8'))
    raw_items = man['items_zero'] if A.pool == 'zero' else man['items_nonzero']
    items = [norm(e) for e in raw_items]
    print('  池 %s：%d 条（清单首条示例 = %r）' % (A.pool, len(items), raw_items[0] if raw_items else None))
    assert items and items[0][0], '清单条目解析失败（item 为空）'

    done = set()
    if os.path.exists(A.out):
        done = {r['item'] for r in csv.DictReader(io.open(A.out, encoding='utf-8-sig'))}
    todo = [x for x in items if x[0] not in done]
    print('  已完成 %d，待跑 %d' % (len(done), len(todo)))
    if A.dry or not todo:
        return 0

    dirs = getattr(p0, 'IMG_DIRS', {})
    exts = getattr(p0, 'EXTS', ('.jpg', '.jpeg', '.png'))

    def find(it, dom):
        try:
            p = p0.find_img(dom, it)
            if p:
                return p
        except Exception:
            pass
        order = [dom] + [d for d in dirs if d != dom] if dom in dirs else list(dirs)
        for d in order:
            for e in exts:
                p = os.path.join(dirs.get(d, ''), it + e)
                if os.path.exists(p):
                    return p
        return None

    q = queue.Queue()
    for x in todo:
        q.put(x)
    fh = open(A.out, 'a', newline='', encoding='utf-8')
    w = csv.writer(fh)
    if not done:
        w.writerow(['item', 'gt', 'pred', 'parse_ok', 'raw', 'latency_s'])
    lock = threading.Lock()

    def work():
        while True:
            try:
                it, gt, dom = q.get_nowait()
            except Exception:
                return
            ip = find(it, dom)
            if not ip:
                with lock:
                    w.writerow([it, gt, '', 0, 'ERR:image_not_found dom=%s' % dom, '0']); fh.flush()
                continue
            try:
                t0 = time.time()
                from PIL import Image
                with Image.open(ip) as im:
                    b64 = p0.b64_of(im.convert('RGB'))
                raw = p0.call_img(b64, prompt, A.model, A.api)
                v = p0.parse(raw)
                with lock:
                    w.writerow([it, gt, '' if v is None else v, 1 if v is not None else 0,
                                (raw or '')[:400], '%.2f' % (time.time() - t0)]); fh.flush()
            except Exception as ex:
                with lock:
                    w.writerow([it, gt, '', 0, 'ERR:' + str(ex)[:200], '0']); fh.flush()

    ts = [threading.Thread(target=work) for _ in range(A.workers)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    fh.close()
    n = sum(1 for _ in csv.DictReader(io.open(A.out, encoding='utf-8-sig')))
    ok = sum(1 for r in csv.DictReader(io.open(A.out, encoding='utf-8-sig')) if r['parse_ok'] == '1')
    print('  [%s/%s/start%s] %d 行（parse_ok=%d）-> %s' % (A.arm, A.pool, A.start, n, ok, A.out))
    return 0


if __name__ == '__main__':
    sys.exit(main())
