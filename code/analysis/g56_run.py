#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""g56_run.py — G5（数字锚中性化）+ G6（预注册等水平四旋钮重扫）的运行器。

冻结判据：/root/g56_criteria_frozen.json（启动时断言 md5）。
提示词**逐字内置**（与本件同源），启动时逐字断言与冻结件一致 —— 提示词不允许在运行中被拼接。

阶段：
  arms   契约 7 臂 + 问法 5 档（各 182 项）
  budget 像素预算 5 档（V1_json，182 项）
  tile   切块 1/2/3/4/6（各 182 项；每项 k*k 次调用）
  noise  base 臂第 2、3 遍（同会话）

用法：python3 g56_run.py arms|budget|tile|noise [workers]
输出：/root/g56_res/g56_<phase>.csv（断点续跑：(phase,item,arm,budget,tilek,rep) 已完成则跳过）
"""
import base64
import csv
import hashlib
import io
import json
import math
import os
import queue
import re
import sys
import threading
import time
import urllib.request

API = os.environ.get('LOCAL_API', 'http://127.0.0.1:8006/v1/chat/completions')
MODEL = os.environ.get('SERVED_MODEL', 'Qwen3-VL-32B-Instruct')
CRIT = '/root/g56_criteria_frozen.json'
CRIT_MD5 = '22869fd86fefb37502ddf9d8dd5bec8b'
OUT = '/root/g56_res'
IMG = '/root/dense/shanghaitech/images'
COUNTS = '/root/dense/shanghaitech/counts.csv'
STRIDE = 28
REFUSE = ['too many', '无法', '数不清', '难以', '众多', 'cannot', 'unable', '抱歉']
os.makedirs(OUT, exist_ok=True)

# ── 提示词（逐字；启动时与冻结件比对） ──────────────────────────────────────────
PROMPTS = {
    'base': '请数出图片中的人数（人群中的每个人头或人体），不要遗漏，不要重复，'
            '以JSON格式输出：{"count": 数量}，只输出JSON。',
    'forbid0': '请数出图片中的人数（人群中的每个人头或人体），不要遗漏，不要重复。'
               '注意：**不要回答 0**；如果你认为可能是 0，请给出你最接近的估计值。'
               '以JSON格式输出：{"count": 数量}，只输出JSON。',
    'range': '请估计图片中的人数范围（人群中的每个人头或人体）。'
             '以JSON格式输出：{"low": 下界, "high": 上界}，只输出JSON。',
    'choice': '请从以下选项中选择最接近图片中实际人数的选项：0, 10, 50, 100, 500, 1000。'
              '以JSON格式输出：{"choice": 选项}，只输出JSON。',
    'neutral0': '请数出图片中的人数（人群中的每个人头或人体），不要遗漏，不要重复。'
                '人数可能是 0；若你的判断是 0，就回答 0。'
                '以JSON格式输出：{"count": 数量}，只输出JSON。',
    'forbid0n': '请数出图片中的人数（人群中的每个人头或人体），不要遗漏，不要重复。'
                '注意：不要给出最小的可能取值；如果你认为人数极少，请给出你最接近的估计值。'
                '以JSON格式输出：{"count": 数量}，只输出JSON。',
    'choicen': '请从你认为合理的候选取值中，选择与图片中实际人数最接近的一项。'
               '以JSON格式输出：{"choice": 选项}，只输出JSON。',
    'V1_json': '请数出图片中的人数（人群中的每个人头或人体），不要遗漏，不要重复，'
               '以JSON格式输出：{"count": 数量}，只输出JSON。',
    'V2_number': '图中有多少人？只输出一个阿拉伯数字。',
    'V3_locate': '请先在图中逐个定位每个人头/人体，再统计总人数，以JSON格式输出：{"count": 数量}，只输出JSON。',
    'V4_estimate': '请估计图中的人数（允许给出近似值），以JSON格式输出：{"count": 数量}，只输出JSON。',
    'V5_region': '请分区域估计人数后求和，以JSON格式输出：{"count": 数量}，只输出JSON。',
}
CONTRACT7 = ['base', 'forbid0', 'range', 'choice', 'neutral0', 'forbid0n', 'choicen']
FAMILY5 = ['V1_json', 'V2_number', 'V3_locate', 'V4_estimate', 'V5_region']
BUDGETS = [1048576, 400000, 200000, 100000, 50000]
TILEKS = [1, 2, 3, 4, 6]
CHOICE_LIKE = ('choice', 'choicen')
_lock = threading.Lock()


def check_criteria():
    b = open(CRIT, 'rb').read()
    got = hashlib.md5(b).hexdigest()
    assert got == CRIT_MD5, '冻结件 md5 变了：%s != %s' % (got, CRIT_MD5)
    j = json.loads(b.decode('utf-8'))
    # 逐字断言放在冻结件里的每一条提示词
    c = j['G5']
    assert c['arms_present'] == ['base', 'forbid0', 'range', 'choice']
    assert c['arms_neutralised'] == ['base', 'forbid0n', 'range', 'choicen']
    assert j['G6']['knobs_covered']['K4 VLM·prompt family'] == FAMILY5
    assert j['G6']['knobs_covered']['K6 VLM·pixel budget'] == BUDGETS
    assert j['G6']['knobs_covered']['K5 VLM·tiling level'] == ['1x1', '2x2', '3x3', '4x4', '6x6']
    assert j['shared_design']['gt_source'] == COUNTS
    # ★ 逐字断言：冻结件里的每一条提示词必须与本文件内置的常量**逐字符相同**
    frz = j['prompts_verbatim']
    assert set(frz) == set(PROMPTS), '提示词集合不一致：%s' % (set(frz) ^ set(PROMPTS))
    for a, p in sorted(PROMPTS.items()):
        assert frz[a] == p, '提示词 %s 与冻结件不一致' % a
    print('[g56] 冻结件 md5 OK：%s ｜ %d 条提示词逐字一致' % (got, len(PROMPTS)), flush=True)


def fit(w, h, budget):
    """逐字复制自 res_ctrl.py（冻结件）。"""
    if budget <= 0 or w * h <= budget:
        return w, h
    s = math.sqrt(budget / float(w * h))
    nw = max(STRIDE * 2, int(w * s) // STRIDE * STRIDE)
    nh = max(STRIDE * 2, int(h * s) // STRIDE * STRIDE)
    while nw * nh > budget:
        nw -= STRIDE; nh -= STRIDE
        nw = max(STRIDE * 2, nw); nh = max(STRIDE * 2, nh)
        if nw <= STRIDE * 2 and nh <= STRIDE * 2:
            break
    return nw, nh


def parse(raw, arm):
    """逐字复制自 `_probe_gen_remote.py::parse`；arm 映射到它认得的名字。"""
    t = raw.replace(',', '')
    if arm == 'range':
        m = re.search(r'"?(?:low|下界|min)"?\s*[:：]\s*(\d+)', t, re.I)
        m2 = re.search(r'"?(?:high|上界|max)"?\s*[:：]\s*(\d+)', t, re.I)
        if m and m2:
            return int(m.group(1)), int(m2.group(1)), 1
        nums = [int(x) for x in re.findall(r'\d+', t)]
        if len(nums) >= 2:
            return min(nums[0], nums[1]), max(nums[0], nums[1]), 1
        return None, None, 0
    m = re.search(r'"?(?:count|choice|计数|数量|人数|选项)"?\s*[:：]\s*(\d+)', t, re.I)
    if m:
        return int(m.group(1)), None, 1
    m = re.search(r'\d+', t)
    return (int(m.group(0)), None, 1) if m else (None, None, 0)


def call(im, prompt, timeout=300):
    b = io.BytesIO()
    im.save(b, 'JPEG', quality=92)
    url = 'data:image/jpeg;base64,' + base64.b64encode(b.getvalue()).decode()
    payload = {'model': MODEL, 'messages': [{'role': 'user', 'content': [
        {'type': 'image_url', 'image_url': {'url': url}},
        {'type': 'text', 'text': prompt}]}], 'temperature': 0.0, 'max_tokens': 96}
    req = urllib.request.Request(API, data=json.dumps(payload).encode(),
                                 headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        d = json.loads(r.read().decode())
    return d['choices'][0]['message']['content']


def items():
    """st_a = part_A / test，按文件名排序（确定性）。"""
    from PIL import Image
    out = []
    for r in csv.DictReader(open(COUNTS, encoding='utf-8-sig')):
        if r['part'] == 'part_A' and r['split'] == 'test':
            p = os.path.join('/root/dense/shanghaitech', r['file'])
            out.append((os.path.basename(p), p, int(r['count'])))
    out.sort()
    return out


def build_jobs(phase):
    it = items()
    jobs = []
    if phase == 'arms':
        for name, p, gt in it:
            for a in CONTRACT7:
                jobs.append((name, p, gt, a, 1048576, 1, 1))
            for a in FAMILY5:
                jobs.append((name, p, gt, a, 1048576, 1, 1))
    elif phase == 'budget':
        for name, p, gt in it:
            for b in BUDGETS:
                jobs.append((name, p, gt, 'base', b, 1, 1))
    elif phase == 'tile':
        for name, p, gt in it:
            for k in TILEKS:
                jobs.append((name, p, gt, 'V1_json', 0, k, 1))
    elif phase == 'noise':
        for name, p, gt in it:
            for rep in (2, 3):
                jobs.append((name, p, gt, 'base', 1048576, 1, rep))
    else:
        raise SystemExit('unknown phase %s' % phase)
    return jobs


def run_one(job, st, wr, fh):
    from PIL import Image
    name, path, gt, arm, budget, k, rep = job
    im = Image.open(path).convert('RGB')
    w0, h0 = im.size
    tile_ok = ntile = 0
    preds = []
    if k == 1:
        tw, th = fit(w0, h0, budget)
        if (tw, th) != (w0, h0):
            im = im.resize((tw, th), Image.LANCZOS)
        eff = im.size[0] * im.size[1]
        raw = call(im, PROMPTS[arm])
        ntile = 1
        p, _p2, ok = parse(raw, arm)
        tile_ok = ok
        preds = [p] if ok else []
        raws = [raw]
    else:
        # k×k 整数网格，行优先；每块原生尺寸各一次调用
        eff = 0
        raws = []
        for i in range(k):
            for j in range(k):
                x0 = int(round(w0 * j / k)); x1 = int(round(w0 * (j + 1) / k))
                y0 = int(round(h0 * i / k)); y1 = int(round(h0 * (i + 1) / k))
                t = im.crop((x0, y0, x1, y1))
                eff = t.size[0] * t.size[1]
                raw = call(t, PROMPTS['V1_json'])
                ntile += 1
                p, _p2, ok = parse(raw, 'V1_json')
                if ok:
                    tile_ok += 1; preds.append(p)
                raws.append(raw)
    all_ok = (ntile > 0 and tile_ok == ntile)
    pred = sum(preds) if all_ok else ''
    low = ' '.join(raws).lower()
    ref = any(x in low for x in REFUSE)
    httpe = 1 if any(re.search(r'HTTP Error|<!DOCTYPE|<html', r, re.I) for r in raws) else 0
    with _lock:
        wr.writerow([name, 'st_a', arm, budget, k, rep, gt, pred,
                     1 if all_ok else 0, tile_ok, ntile,
                     1 if (all_ok and pred == 0) else 0, 1 if ref else 0, httpe, MODEL,
                     (' || '.join(raws)).replace('\n', ' ')[:300]])
        fh.flush()
        st['n'] += 1
        st['bad'] += 0 if all_ok else 1
        if st['n'] % 200 == 0:
            el = max(time.time() - st['t0'], 1e-9)
            print('  %d/%d (%.2f/s unparsed=%d eta=%.0fmin)' %
                  (st['n'], st['tot'], st['n'] / el, st['bad'],
                   (st['tot'] - st['n']) / max(st['n'] / el, 1e-9) / 60), flush=True)


def main():
    phase = sys.argv[1]
    nw = int(sys.argv[2]) if len(sys.argv) > 2 else 16
    check_criteria()
    jobs = build_jobs(phase)
    out_csv = os.path.join(OUT, 'g56_%s.csv' % phase)
    done = set()
    if os.path.exists(out_csv):
        for r in csv.DictReader(open(out_csv, encoding='utf-8-sig')):
            if r.get('http_err') == '0' and (r.get('raw') or '') != '':
                done.add((r['item'], r['arm'], int(r['budget']), int(r['tilek']), int(r['rep'])))
    jobs = [j for j in jobs if (j[0], j[3], j[4], j[5], j[6]) not in done]
    new = not os.path.exists(out_csv) or os.path.getsize(out_csv) == 0
    fh = open(out_csv, 'a', encoding='utf-8-sig', newline='')
    wr = csv.writer(fh)
    if new:
        wr.writerow(['item', 'domain', 'arm', 'budget', 'tilek', 'rep', 'gt', 'pred',
                     'parse_ok', 'tile_ok', 'ntile', 'abstain', 'refuse', 'http_err',
                     'model', 'raw'])
    print('[g56/%s] 待跑 %d 项（已完成 %d）｜模型 %s' % (phase, len(jobs), len(done), MODEL), flush=True)
    if not jobs:
        fh.close(); return
    q = queue.Queue()
    for j in jobs:
        q.put(j)
    st = {'n': 0, 'tot': len(jobs), 't0': time.time(), 'bad': 0}
    th = [threading.Thread(target=lambda: worker(q, st, wr, fh), daemon=True) for _ in range(nw)]
    for t in th:
        t.start()
    for t in th:
        t.join()
    fh.close()
    print('[g56/%s] DONE n=%d unparsed=%d' % (phase, st['n'], st['bad']), flush=True)


def worker(q, st, wr, fh):
    while True:
        try:
            job = q.get_nowait()
        except queue.Empty:
            return
        for attempt in (1, 2):
            try:
                run_one(job, st, wr, fh)
                break
            except Exception as ex:
                if attempt == 2:
                    with _lock:
                        wr.writerow([job[0], 'st_a', job[3], job[4], job[5], job[6], job[2],
                                     '', 0, 0, 0, 0, 0, 1, MODEL, 'ERR %s' % str(ex)[:120]])
                        fh.flush(); st['n'] += 1; st['bad'] += 1
                else:
                    time.sleep(2)


if __name__ == '__main__':
    main()
