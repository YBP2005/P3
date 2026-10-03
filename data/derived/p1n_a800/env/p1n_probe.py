#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""p1d_probe.py —— P1-D 的探针：**按像素预算缩放**后调用冻结探针，schema 与放行的 res_ctrl 逐字同构。

★ 仪器逐字复用（不重打任何提示词、不改调用参数）：
    from pf_p0_probe import b64_of, call_img, parse, BASE_PROMPT     （/root/pf_p0_probe.py，md5 断言）
    temperature 0 / max_tokens 128 / retries 5 / workers 4 都随 call_img 一起继承
★ 预算**客户端**施加：服务端 mm-processor 保持冻结值（max_pixels 1048576 / min_pixels 3136），
  所以档位之间**只有像素预算在动**。缩放规则：等比缩到 W*H ≤ budget（s = sqrt(budget/(W*H))，取整）。
★ 输出列 = item,dataset,budget,gt,nat_w,nat_h,eff_w,eff_h,eff_px,px_per_obj,pred,parse_ok,abstain,refuse,http_err,model,raw

用法：
  python3 p1d_probe.py --api http://127.0.0.1:8013/v1/chat/completions --model Qwen3-VL-32B-Instruct-AWQ \
      --items /root/p1d/data/sample_mtdc.csv --domain mtdc --budget 543118 --start 1 \
      --imgdir /root/p1d/data/mtdc/images --out /root/p1d/res/P1N_mtdc_b543118_s1.csv --workers 4
"""
import argparse
import csv
import hashlib
import importlib.util
import io
import math
import os
import queue
import sys
import threading
import time

P0 = '/root/pf_p0_probe.py'
P0_MD5 = 'e7a65fd47345c2fe040fa4d05a3b1d86'

_OLD = '人数（人群中的每个人头或人体）'
_NEW = {'mtdc': '玉米雄穗的数量（图中的每一根雄穗）',
        'gwhd': '小麦穗的数量（图中的每一个麦穗）'}
PROMPT_FOR = {}   # 在 main() 里、载入冻结提示词之后填充（并跑可逆性断言）

COLS = ['item', 'dataset', 'budget', 'gt', 'nat_w', 'nat_h', 'eff_w', 'eff_h', 'eff_px',
        'px_per_obj', 'pred', 'parse_ok', 'abstain', 'refuse', 'http_err', 'model', 'raw']


def load(path, want_md5=None):
    if want_md5:
        got = hashlib.md5(open(path, 'rb').read()).hexdigest()
        assert got == want_md5, '!! %s md5 %s != 冻结值 %s' % (path, got, want_md5)
    spec = importlib.util.spec_from_file_location('frozen_p0', path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def img_path(d, item):
    for e in ('.jpg', '.jpeg', '.png'):
        p = os.path.join(d, item + e)
        if os.path.exists(p):
            return p
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--api', required=True)
    ap.add_argument('--model', required=True)
    ap.add_argument('--items', required=True)
    ap.add_argument('--domain', required=True)
    ap.add_argument('--budget', type=int, required=True)
    ap.add_argument('--start', required=True)
    ap.add_argument('--imgdir', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--workers', type=int, default=4)
    ap.add_argument('--limit', type=int, default=0)
    ap.add_argument('--dry', action='store_true')
    A = ap.parse_args()

    p0 = load(P0, P0_MD5)
    # ★ 名词替换：只改一处对象名词短语；断言该替换**可逆且唯一**，不成立即拒绝运行（§M.49 式自检）
    for _dom, _new in _NEW.items():
        assert _OLD in p0.BASE_PROMPT, '冻结提示词里找不到待替换的名词短语'
        _p = p0.BASE_PROMPT.replace(_OLD, _new)
        assert _p != p0.BASE_PROMPT and _p.replace(_new, _OLD) == p0.BASE_PROMPT, '替换不是唯一差异（可逆性断言失败）⇒ 拒绝运行'
        PROMPT_FOR[_dom] = _p
    print('   名词替换自检通过：%s' % {k: hashlib.md5(v.encode()).hexdigest()[:8] for k, v in PROMPT_FOR.items()})
    items = [(r['item'], r['gt']) for r in csv.DictReader(io.open(A.items, encoding='utf-8-sig', newline=''))]
    if A.limit:
        items = items[:A.limit]
    print('== P1-D ==')
    print('  探针 md5（已断言）%s ｜ prompt md5 %s ｜ budget %d ｜ domain %s ｜ start %s ｜ workers %d'
          % (P0_MD5[:16], hashlib.md5(p0.BASE_PROMPT.encode()).hexdigest()[:16], A.budget, A.domain,
             A.start, A.workers))
    print('  item 数 = %d' % len(items))
    if A.dry:
        return 0

    q = queue.Queue()
    for x in items:
        q.put(x)
    done = set()
    if os.path.exists(A.out):
        done = {r['item'] for r in csv.DictReader(io.open(A.out, encoding='utf-8-sig', newline=''))}
    if done:
        q = queue.Queue()
        for x in items:
            if x[0] not in done:
                q.put(x)
        print('  续跑：已完成 %d' % len(done))
    fh = open(A.out, 'a', newline='', encoding='utf-8')
    wr = csv.writer(fh)
    if not done:
        wr.writerow(COLS)
    lock = threading.Lock()
    from PIL import Image

    def work():
        while True:
            try:
                it, gt = q.get_nowait()
            except Exception:
                return
            ip = img_path(A.imgdir, it)
            if not ip:
                with lock:
                    wr.writerow([it, A.domain, A.budget, gt, '', '', '', '', '', '', '', 0, 0, 0, 1, A.model,
                                 'ERR:image_not_found'])
                    fh.flush()
                continue
            try:
                im = Image.open(ip).convert('RGB')
                w, h = im.size
                # ★ 口径与放行件一致（按 res_ctrl__q32 逐行反解锁定）：
                #   budget == 0 ⇒ **原生，不缩放**（eff = nat）；否则 s = sqrt(budget/(W*H))（只在需缩小时），
                #   然后把两个方向 **向下取整到 28 的倍数**（Qwen smart_resize 的 factor=28）。
                #   实测锚：902x409 + budget 200000 → 放行件 eff = 644x280 = floor(902*0.7362/28)*28 × floor(409*0.7362/28)*28 ✓
                if A.budget and w * h > A.budget:
                    s = math.sqrt(float(A.budget) / float(w * h))
                    ew, eh = max(28, int(w * s // 28) * 28), max(28, int(h * s // 28) * 28)
                else:
                    ew, eh = w, h
                if (ew, eh) != (w, h) and im.size != (ew, eh):
                    pass
                im2 = im.resize((ew, eh), Image.BICUBIC) if (ew, eh) != (w, h) else im
                t0 = time.time()
                b64 = p0.b64_of(im2)
                raw = p0.call_img(b64, PROMPT_FOR[A.domain], A.model, A.api)
                v = p0.parse(raw)
                with lock:
                    wr.writerow([it, A.domain, A.budget, gt, w, h, ew, eh, ew * eh,
                                 '%.1f' % ((ew * eh) / float(gt)) if float(gt or 0) > 0 else '',
                                 '' if v is None else v, 1 if v is not None else 0,
                                 1 if (v == 'abstain') else 0, 1 if (v in ('cannot_judge', 'no_people')) else 0,
                                 0, A.model, (raw or '')[:400]])
                    fh.flush()
            except Exception as ex:
                with lock:
                    wr.writerow([it, A.domain, A.budget, gt, '', '', '', '', '', '', '', 0, 0, 0, 1, A.model,
                                 'ERR:' + str(ex)[:200]])
                    fh.flush()
            time.sleep(0.0)

    ts = [threading.Thread(target=work) for _ in range(A.workers)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    fh.close()
    n = sum(1 for _ in csv.DictReader(io.open(A.out, encoding='utf-8-sig', newline='')))
    ok = sum(1 for r in csv.DictReader(io.open(A.out, encoding='utf-8-sig', newline=''))
             if r['parse_ok'] == '1')
    print('  [%s b%d s%s] %d 行（parse_ok=%d）-> %s' % (A.domain, A.budget, A.start, n, ok, A.out))
    return 0


if __name__ == '__main__':
    sys.exit(main())
