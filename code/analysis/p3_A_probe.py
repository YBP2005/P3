#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""p3_A_probe.py —— 实验 A 的探针（两个新计数域，MTDC 玉米雄穗 / GWHD 麦穗）。

纪律（见 /root/A_criteria_frozen.json）：
  · 仪器 19e **一行不改**（断言 md5 03edb14c98ffa3aea9ffa20f59b00bc8），只复用 P / b64_of / call_img / parse。
  · 提示词**只换物件名词短语**，其余（含 outlet token `cannot_judge` / `no_people`）逐字不变；
    替换前逐个断言"确实发生且只发生一次"。
  · 两个旋钮：**契约 6 臂** + **像素预算 5 档**（几何梯，开跑前写定）。
  · 每档/每臂独立落盘、可续跑；schema 与 E2/E3 一致。

用法：
  python3 p3_A_probe.py --domain mtdc --kind contract --start 1 --model Qwen3-VL-32B-Instruct --workers 8
  python3 p3_A_probe.py --domain mtdc --kind pixelbudget --start 1 --model ... --workers 8
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

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

P19E = '/root/19e_probe_multi.py'
MD5_EXPECT = '03edb14c98ffa3aea9ffa20f59b00bc8'
BASE = '/root/A_data'
OUTD = '/root/A_results'

h = hashlib.md5(io.open(P19E, 'rb').read()).hexdigest()
assert h == MD5_EXPECT, '仪器 md5 不符：%s != %s' % (h, MD5_EXPECT)
spec = importlib.util.spec_from_file_location('p19e', P19E)
E = importlib.util.module_from_spec(spec)
spec.loader.exec_module(E)

# ---- 冻结的问法替换（只换物件名词短语）----
# ★ 2026-09-28 修正：`unit` 必须逐字等于冻结件 `prompts_frozen` 里的限定语
#   （仪器原文是「人数（人群中的每个人头或人体）」，限定语是「人群中的每个人头或人体」，
#    故替换后应为「画面中的每一根雄穗」——**不能**省掉「画面中的」）。
#   原版写成「每一根雄穗」，与冻结件不逐字相等；这是本探针的第一个版本的真实缺陷。
NOUN = {
    'mtdc': {'obj': '玉米雄穗数', 'unit': '画面中的每一根雄穗', 'bestB': '画面中最可能的雄穗数', 'bestC': '画面各区域的雄穗数'},
    'gwhd': {'obj': '麦穗数',     'unit': '画面中的每一根麦穗', 'bestB': '画面中最可能的麦穗数', 'bestC': '画面各区域的麦穗数'},
}
CONTRACT_ARMS = ['base', 'permit', 'bestA', 'bestB', 'bestC', 'channel']
PIXEL_BUDGETS = [1048576, 489987, 228966, 106993, 50000]
ANOM = 1e5
FREEZE = '/root/A_criteria_frozen.json'


def _frozen_prompts(domain):
    """冻结件里逐字写定的问法（只有 base / permit / channel 有逐字条目；bestA/B/C 只有替换规则）。"""
    try:
        d = json.load(io.open(FREEZE, encoding='utf-8'))['prompts_frozen']
    except Exception:                                       # noqa: BLE001
        return {}
    out = {}
    for arm in ('base', 'permit', 'channel'):
        v = d.get(arm)
        if isinstance(v, dict) and domain in v:
            out[arm] = v[domain]
    return out


def prompts_for(domain):
    n = NOUN[domain]
    out = {}
    for arm in CONTRACT_ARMS:
        s = E.P[arm]
        before = s
        s = s.replace('人数（人群中的每个人头或人体）', '%s（%s）' % (n['obj'], n['unit']))
        s = s.replace('画面中最可能的人数', n['bestB'])
        s = s.replace('画面各区域的人数', n['bestC'])
        s = s.replace('这张图片中的人数', '这张图片中的%s' % n['obj'])
        s = s.replace('报告一个数值人数', '报告一个数值%s' % n['obj'])
        s = s.replace('请数出图片中的人数', '请数出图片中的%s' % n['obj'])
        assert s != before, '臂 %s 的替换没有发生' % arm
        # 只允许出现在被声明的名词区段内：替换后不得残留"人数"二字
        assert '人数' not in s, '臂 %s 仍残留「人数」：%s' % (arm, s)
        out[arm] = s
    # ★ 2026-09-28 新增的核心断言：产出必须与**冻结件逐字相等**（原先只断言"替换发生了"，
    #   因此漏掉了「画面中的」这类差异 —— 那正是本探针第一版的真实缺陷）。
    fz = _frozen_prompts(domain)
    assert fz, '冻结件 %s 里读不到 prompts_frozen 的逐字条目，拒绝开跑' % FREEZE
    for arm, want in fz.items():
        assert out[arm] == want, (
            '臂 %s 的问法与冻结件不逐字相等\n  实得：%r\n  冻结：%r' % (arm, out[arm], want))
    print('  问法逐字核对：%d 个臂与冻结件 %s 逐字相等 ✓' % (len(fz), FREEZE))
    return out


def load_items(domain):
    return json.load(io.open(os.path.join(BASE, domain, 'items.json'), encoding='utf-8'))


def img_path(domain, item):
    return os.path.join(BASE, domain, 'images', item + '.jpg')


def resize_to(im, max_pixels):
    w, hh = im.size
    if w * hh <= max_pixels:
        return im
    s = (max_pixels / float(w * hh)) ** 0.5
    return im.resize((max(1, int(w * s)), max(1, int(hh * s))))


def run(domain, kind, start, model, workers):
    from PIL import Image
    P = prompts_for(domain)
    items = load_items(domain)
    os.makedirs(os.path.join(OUTD, domain), exist_ok=True)
    if kind == 'contract':
        cells = [(a, None) for a in CONTRACT_ARMS]
    else:
        cells = [('base', v) for v in PIXEL_BUDGETS]
    for arm, budget in cells:
        tag = arm if budget is None else 'pb%d' % budget
        outp = os.path.join(OUTD, domain, '%s__%s__s%d.csv' % (domain, tag, start))
        done = set()
        if os.path.exists(outp):
            with io.open(outp, encoding='utf-8-sig') as f:
                done = {r['item'] for r in csv.DictReader(f)}
        todo = [x for x in items if x['item'] not in done]
        if not todo:
            print('  [%s/%s] 已完成，跳过' % (domain, tag))
            continue
        q = queue.Queue()
        for x in todo:
            q.put(x)
        lock = threading.Lock()
        newf = not os.path.exists(outp)
        fh = io.open(outp, 'a', newline='', encoding='utf-8')
        w = csv.writer(fh)
        if newf:
            w.writerow(['item', 'gt', 'pred', 'parse_ok', 'raw', 'latency_s', 'level_kind', 'level'])

        def work():
            while True:
                try:
                    x = q.get_nowait()
                except Exception:
                    return
                t0 = time.time()
                try:
                    im = Image.open(img_path(domain, x['item'])).convert('RGB')
                    if budget is not None:
                        im = resize_to(im, budget)
                    raw = E.call_img(E.b64_of(im), P[arm], model)
                    v = E.parse(raw)
                    ok = 1 if v is not None else 0
                except Exception as e:                      # noqa: BLE001
                    raw, v, ok = 'ERR:%s' % str(e)[:150], None, 0
                dt = time.time() - t0
                with lock:
                    w.writerow([x['item'], x['gt'], '' if v is None else v, ok, raw[:800],
                                round(dt, 2), kind, '' if budget is None else budget])
                    fh.flush()

        ths = [threading.Thread(target=work) for _ in range(workers)]
        [t.start() for t in ths]
        [t.join() for t in ths]
        fh.close()
        rows = list(csv.DictReader(io.open(outp, encoding='utf-8-sig')))
        z = sum(1 for r in rows if str(r['pred']).strip() in ('0', '0.0'))
        print('  [%s/%s] %d 行；pred==0 %d（%.1f%%）' % (domain, tag, len(rows), z,
                                                     100.0 * z / len(rows) if rows else 0))
    print('A_PROBE_%s_%s_s%d_DONE' % (domain.upper(), kind.upper(), start))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--domain', required=True, choices=('mtdc', 'gwhd'))
    ap.add_argument('--kind', required=True, choices=('contract', 'pixelbudget'))
    ap.add_argument('--start', type=int, required=True)
    ap.add_argument('--model', required=True)
    ap.add_argument('--workers', type=int, default=8)
    A = ap.parse_args()
    # 起跑前把"实际发出的问法"留档，便于事后审计替换
    P = prompts_for(A.domain)
    d = os.path.join(OUTD, A.domain)
    os.makedirs(d, exist_ok=True)
    json.dump(P, io.open(os.path.join(d, 'prompts_used_%s.json' % A.domain), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    print('问法留档 -> %s；md5 %s' % (os.path.join(d, 'prompts_used_%s.json' % A.domain),
                                 hashlib.md5(json.dumps(P, ensure_ascii=False).encode()).hexdigest()[:12]))
    run(A.domain, A.kind, A.start, A.model, A.workers)


if __name__ == '__main__':
    main()
