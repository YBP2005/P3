#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""p5a_probe.py —— **P5 Phase 1**：`forbid0` 的输出分布探针（用 vLLM 的 logprobs 看"值位置"的分布）。

回答什么（[external-review][external-review]与 T12 的"未解机制"）：`forbid0` 到底是
  (a) **把已经算出来的量吐出来**（值位置上本来就有一个非 0 的候选，只是被"0"压住），还是
  (b) **换一套说法重算**（值位置的分布被重塑）？
判据见 `p5a_criteria_frozen.json`（跑之前冻结）：H11 零质量下降、H12 重分配 vs 重算、H13 与 GT 的秩相关。

设计
  * 臂：`base` / `forbid0` / `permit`
      - `base`、`permit` 的提示词 importlib 自冻结的 `19e_probe_multi.py`（md5 断言）；
      - `forbid0` 的提示词**逐字取自语料普查用的那套**（`pod_evidence/scripts/probe_gen.py` 的 PROMPTS），
        本文件里以常量冻结，不做任何改写。
  * item：**语料密集域的零池**——即普查里 `base` 答 0 的那些 item（`/root/dense_results/vlm_<ds>_base_whole.csv`）。
  * 相对母本只改一处**传输**：payload 里加 `logprobs: true, top_logprobs: 20, max_tokens: 12`
    （母本不带 logprobs）。提示词、解析器、图像编码逐字复用。
  * 输出：每 item 一行，含"值位置"的 top-k 分布、零质量、数字质量、被选中的值。

用法：
  python -u p5a_probe.py --model <served> --arm base --domains st_a,ucf --n 150 \
      --api http://127.0.0.1:PORT/v1/chat/completions --outd /root/p5a_results [--workers 6]
"""
import argparse
import base64
import csv
import hashlib
import importlib.util
import io
import json
import math
import os
import queue
import re
import sys
import threading
import time
import urllib.error
import urllib.request

sys.stdout.reconfigure(encoding='utf-8')
HERE = os.path.dirname(os.path.abspath(__file__))
FROZEN = os.environ.get('P1_FROZEN') or os.path.join(HERE, '19e_probe_multi.py')
FROZEN_MD5 = '03edb14c98ffa3aea9ffa20f59b00bc8'
# ★ 逐字取自语料普查的提示词集（`pod_evidence/scripts/probe_gen.py` 的 PROMPTS['forbid0']）
FROZEN_FORBID0 = ('请数出图片中的人数（人群中的每个人头或人体），不要遗漏，不要重复。'
                  '注意：**不要回答 0**；如果你认为可能是 0，请给出你最接近的估计值。'
                  '以JSON格式输出：{"count": 数量}，只输出JSON。')
DENSE = {'st_a': '/root/dense/shanghaitech/images/part_A_test',
         'ucf': '/root/dense/ucf_qnrf/UCF-QNRF_ECCV18/Test'}


def load_frozen():
    got = hashlib.md5(io.open(FROZEN, 'rb').read()).hexdigest()
    if got != FROZEN_MD5:
        raise SystemExit('!! 冻结探针 md5 不符：%s（应 %s）' % (got[:12], FROZEN_MD5[:12]))
    spec = importlib.util.spec_from_file_location('f19e', FROZEN)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def call_logprobs(api, b64, prompt, model, k=20, mt=12, timeout=180, retries=5):
    """与冻结 `19e.call_img` 逐字同构，**只多两件事**：请求 logprobs、截短输出。"""
    payload = {'model': model, 'messages': [{'role': 'user', 'content': [
        {'type': 'image_url', 'image_url': {'url': 'data:image/jpeg;base64,' + b64}},
        {'type': 'text', 'text': prompt}]}],
        'temperature': 0.0, 'max_tokens': mt, 'logprobs': True, 'top_logprobs': k}
    req = urllib.request.Request(api, data=json.dumps(payload).encode(),
                                 headers={'Content-Type': 'application/json'})
    last = None
    for a in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode())
        except urllib.error.HTTPError as ex:
            last = ex
            if ex.code in (429, 500, 502, 503, 504):
                time.sleep(min(30, 3 * (2 ** a)))
                continue
            raise
        except Exception as ex:
            last = ex
            time.sleep(min(20, 2 * (a + 1)))
    raise last if last else RuntimeError('retry exhausted')


def value_position(logprobs):
    """找"值位置"：第一个 token 文本里含数字的位置；返回 (idx, top列表[(tok,prob)])."""
    cont = ((logprobs or {}).get('content') or [])
    for i, t in enumerate(cont):
        if re.search(r'\d', t.get('token') or ''):
            top = t.get('top_logprobs') or [{'token': t.get('token'), 'logprob': t.get('logprob')}]
            return i, [(x.get('token'), math.exp(x.get('logprob', -50.0))) for x in top]
    return -1, []


def zero_digit_mass(top):
    """零质量 / 数字质量：按 token 文本首字符判定（剥掉空格与引号）。"""
    z = d = 0.0
    for tok, p in top:
        s = (tok or '').strip().strip('"').strip()
        if not s:
            continue
        if s[0] == '0':
            z += p
        elif s[0].isdigit():
            d += p
    return z, d


def load_items(pool, n):
    """零池来自普查的 base 臂答案表（pred == 0 的 item）。"""
    rows = []
    for ds in pool:
        p = '/root/dense_results/vlm_%s_base_whole.csv' % ds
        if not os.path.exists(p):
            print('  !! 缺 %s' % p)
            continue
        with io.open(p, encoding='utf-8-sig', newline='') as f:
            for r in csv.DictReader(f):
                if str(r.get('pred', '')).strip() in ('0', '0.0'):
                    rows.append((ds, r['item'], r.get('gt', '')))
    rows.sort(key=lambda x: (x[0], x[1]))
    if n and len(rows) > n:
        step = len(rows) / float(n)
        rows = [rows[int(i * step)] for i in range(n)]
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--model', required=True)
    ap.add_argument('--arm', required=True, choices=('base', 'forbid0', 'permit'))
    ap.add_argument('--domains', default='st_a,ucf')
    ap.add_argument('--n', type=int, default=150)
    ap.add_argument('--api', default='http://127.0.0.1:8000/v1/chat/completions')
    ap.add_argument('--outd', default='/root/p5a_results')
    ap.add_argument('--workers', type=int, default=6)
    ap.add_argument('--topk', type=int, default=20)
    ap.add_argument('--tag', default='')
    A = ap.parse_args()

    F = load_frozen()
    print('  冻结探针 %s md5 ✓' % os.path.basename(FROZEN))
    from PIL import Image
    PROMPT = FROZEN_FORBID0 if A.arm == 'forbid0' else F.P[A.arm]
    rows = load_items(A.domains.split(','), A.n)
    print('  零池：%d 项（%s）｜臂 %s' % (len(rows), A.domains, A.arm))
    os.makedirs(A.outd, exist_ok=True)
    tag = A.tag or A.arm
    outp = os.path.join(A.outd, 'p5a_%s_%s.csv' % (A.model.replace('/', '_'), tag))
    done = set()
    if os.path.exists(outp):
        with io.open(outp, encoding='utf-8-sig', newline='') as f:
            done = {r['item'] for r in csv.DictReader(f)}
    todo = [r for r in rows if r[1] not in done]
    print('  待跑 %d 项 → %s' % (len(todo), outp))
    if not todo:
        return 0
    q = queue.Queue()
    for r in todo:
        q.put(r)
    lock = threading.Lock()
    newf = not os.path.exists(outp)
    fh = io.open(outp, 'a', newline='', encoding='utf-8')
    w = csv.writer(fh, lineterminator='\n')
    if newf:
        w.writerow(['item', 'domain', 'gt', 'arm', 'value_pos', 'chosen_tok', 'chosen_p',
                    'zero_mass', 'digit_mass', 'topk', 'pred', 'parse_ok', 'raw', 'latency_s'])
    st = {'n': 0, 't0': time.time(), 'err': 0}

    def work():
        while True:
            try:
                ds, item, gt = q.get_nowait()
            except queue.Empty:
                return
            t0 = time.time()
            rec = dict(item=item, domain=ds, gt=gt, arm=A.arm, value_pos=-1, chosen_tok='',
                       chosen_p='', zero_mass='', digit_mass='', topk='', pred='', parse_ok=0,
                       raw='', latency_s='')
            try:
                p = None
                for ext in ('', '.jpg', '.png', '.jpeg'):
                    c = os.path.join(DENSE[ds], item + ext)
                    if os.path.exists(c):
                        p = c
                        break
                im = Image.open(p).convert('RGB')
                b64 = F.b64_of(im, quality=95)
                resp = call_logprobs(A.api, b64, PROMPT, A.model, k=A.topk)
                ch = resp['choices'][0]
                raw = ch['message']['content']
                lp = ch.get('logprobs') or {}
                vi, top = value_position(lp)
                z, d = zero_digit_mass(top)
                v = F.parse(raw)
                rec.update(value_pos=vi, zero_mass='%.6f' % z, digit_mass='%.6f' % d,
                           topk=json.dumps([[t, round(pp, 6)] for t, pp in top[:A.topk]],
                                           ensure_ascii=False),
                           pred=('' if v is None else v), parse_ok=(1 if v is not None else 0),
                           raw=raw)
                if top:
                    rec['chosen_tok'] = top[0][0]
                    rec['chosen_p'] = '%.6f' % top[0][1]
            except Exception as e:
                rec['raw'] = 'ERR:%s' % str(e)[:200]
                with lock:
                    st['err'] += 1
            rec['latency_s'] = '%.2f' % (time.time() - t0)
            with lock:
                w.writerow([rec[k] for k in ('item', 'domain', 'gt', 'arm', 'value_pos', 'chosen_tok',
                                             'chosen_p', 'zero_mass', 'digit_mass', 'topk', 'pred',
                                             'parse_ok', 'raw', 'latency_s')])
                fh.flush()
                st['n'] += 1
                if st['n'] % 50 == 0:
                    print('    %d/%d  %.2f it/s  err=%d' % (st['n'], len(todo),
                          st['n'] / max(time.time() - st['t0'], 1e-9), st['err']), flush=True)

    ts = [threading.Thread(target=work, daemon=True) for _ in range(max(1, A.workers))]
    [t.start() for t in ts]
    [t.join() for t in ts]
    fh.close()
    print('  [%s] DONE：%d 行（err=%d）→ %s' % (A.arm, st['n'], st['err'], outp))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
