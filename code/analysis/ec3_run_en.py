#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ec3_run_en.py — ③ 的英文臂：用 **M.39 那张冻结英文表**，在四个头条域的**同一批 item** 上重跑 `base`。

为什么要这样写（每一处都有依据）：
  · 英文提示词表 **逐字复用** `20b_probe_lang.py` 里那张冻结表（md5 由本脚本启动时打印核对），
    **不自己另译** —— 另译会破坏与 M.39 的可比性。
  · 冻结探针用 `19e_probe_multi.py`（主实验那个，md5 `03edb14c98ffa3aea9ffa20f59b00bc8`）；
    它的 `base/permit/channel` 与 M.39 用的 `19f` **逐字节相同**（已实测）。
  · **同一批 item**：item 清单直接取自**中文侧**记录里 `parse_ok==1` 的行
    （这正是 J.1 的 canonical 口径；已用 4/4 域 S 对账锁定）。
  · 逐条落盘、可续跑（已在 CSV 里的 item 跳过）。

产物：/root/ec3_en/<ds>_base_en.csv
用法：python3 ec3_run_en.py [--ds st_a,ucf,visdrone,aitod] [--workers 8]
"""
import argparse
import base64
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
import urllib.request

sys.stdout.reconfigure(encoding='utf-8')

FROZEN = '/root/19e_probe_multi.py'
FROZEN_MD5 = '03edb14c98ffa3aea9ffa20f59b00bc8'
CN_DIR = '/root/dense_results'
OUTD = '/root/ec3_en'
SRC = {'st_a': 'vlm_st_a_base_whole.csv', 'ucf': 'vlm_ucf_base_whole.csv',
       'visdrone': 'vlm_visdrone_base_whole.csv', 'aitod': 'vlm_aitod_base_whole.csv'}

# ★ 冻结英文表：逐字复制自 20b_probe_lang.py 的 EN（**三臂都收，本脚本只跑 base**）
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
EN_MD5_EXPECT = None  # 启动时打印，便于与 M.39 记录核对


def load_frozen():
    got = hashlib.md5(open(FROZEN, 'rb').read()).hexdigest()
    print('  冻结探针 %s ｜ md5 %s %s' % (FROZEN, got, '✓' if got == FROZEN_MD5 else '✗ 不符!'))
    assert got == FROZEN_MD5, '冻结探针 md5 不符'
    spec = importlib.util.spec_from_file_location('f19e', FROZEN)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def items_for(ds):
    """中文侧 canonical item 清单（parse_ok==1）—— 与 ec3_share3.py 同一口径。"""
    p = os.path.join(CN_DIR, SRC[ds])
    out = []
    with io.open(p, encoding='utf-8-sig', newline='') as f:
        rd = csv.DictReader(f)
        cols = rd.fieldnames or []
        probe = list(rd)
    swapped = any((r.get('parse_ok') or '').strip() not in ('', '0', '1') for r in probe[:50])
    for r in probe:
        pok = (r.get('ntiles') if swapped else r.get('parse_ok'))
        if (pok or '').strip() != '1':
            continue
        out.append(r['item'])
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--api', default='http://127.0.0.1:8006/v1/chat/completions')
    ap.add_argument('--model', default='Qwen3-VL-32B-Instruct')
    ap.add_argument('--ds', default='st_a,ucf,visdrone,aitod')
    ap.add_argument('--arms', default='base')
    ap.add_argument('--workers', type=int, default=8)
    A = ap.parse_args()

    en_md5 = hashlib.md5('\n'.join(sorted(EN.values())).encode()).hexdigest()
    print('  英文表 md5 %s（%d 臂；M.39 记录里的表 md5 前缀为 a31bd97c6b70，请核对）' % (en_md5[:12], len(EN)))

    M = load_frozen()
    M.API = A.api
    M.AK = 'EMPTY'          # 19e 的 call_img 用模块级 AK；本地 vLLM 不校验
    os.makedirs(OUTD, exist_ok=True)

    for ds in [x for x in A.ds.split(',') if x]:
        imgdir = M.DS_DIRS[ds]
        its = items_for(ds)
        for arm in [x for x in A.arms.split(',') if x]:
            outp = os.path.join(OUTD, '%s_%s_en.csv' % (ds, arm))
            done = set()
            if os.path.exists(outp):
                for r in csv.DictReader(io.open(outp, encoding='utf-8')):
                    done.add(r['item'])
            todo = [it for it in its if it not in done]
            print('  [%s/%s/EN] 共 %d 项，已完成 %d，待跑 %d' % (ds, arm, len(its), len(done), len(todo)))
            if not todo:
                continue
            q = queue.Queue()
            for it in todo:
                q.put(it)
            lock = threading.Lock()
            fh = io.open(outp, 'a', encoding='utf-8', newline='')
            wr = csv.writer(fh)
            if not done:
                wr.writerow(['item', 'gt', 'pred', 'parse_ok', 'raw', 'lang'])
            n = [0]

            def work():
                while True:
                    try:
                        it = q.get_nowait()
                    except queue.Empty:
                        return
                    p = os.path.join(imgdir, it)
                    if not os.path.exists(p):
                        cand = [p + e for e in ('.jpg', '.png', '.jpeg')]
                        p = next((c for c in cand if os.path.exists(c)), None)
                    if not p:
                        continue
                    try:
                        from PIL import Image
                        im = Image.open(p).convert('RGB')
                        b64 = M.b64_of(im)           # ★ b64_of 收 PIL Image，不收路径
                        raw = M.call_img(b64, EN[arm], A.model)
                        pred = M.parse(raw)          # ★ 19e 的 parse() 只返回一个值
                        ok = 1 if pred is not None else 0
                    except Exception as e:
                        raw, pred, ok = 'ERR:%s' % str(e)[:80], None, 0
                    with lock:
                        wr.writerow([it, '', pred, ok, raw, 'en'])
                        n[0] += 1
                        if n[0] % 50 == 0:
                            fh.flush()
                            print('    %d/%d' % (n[0], len(todo)), flush=True)
            ths = [threading.Thread(target=work) for _ in range(A.workers)]
            t0 = time.time()
            for t in ths:
                t.start()
            for t in ths:
                t.join()
            fh.close()
            print('  [%s/%s/EN] 写 %d 行 -> %s（%.1f 分钟）' % (ds, arm, n[0], outp, (time.time() - t0) / 60))
    print('DONE')
    return 0


if __name__ == '__main__':
    sys.exit(main())
