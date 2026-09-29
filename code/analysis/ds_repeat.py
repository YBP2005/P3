#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""重复采样 → 汇总指标离散度。
固定同一批 item（默认取 man1000 前 120 项，全部 GT>=1），重复 M 次，
每次重复算一套汇总指标（ρ含0 / ρ中位 / ρ剔0 / 答0率 / 精确命中 / 逐档），
再看**跨重复的均值 ± 标准差** —— 这决定单次采样的汇总结论能否用。

用法: python ds_repeat.py [N_ITEMS] [REPS] [MODEL]
"""
import io, os, csv, json, base64, re, sys, time, threading, queue, statistics, random
import urllib.request
import numpy as np
from PIL import Image

K = os.environ.get('DS_KEY', '').strip()
API = os.environ.get('DS_API', 'https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions')
MODEL = sys.argv[3] if len(sys.argv) > 3 else 'qwen3.8-flash'
N = int(sys.argv[1]) if len(sys.argv) > 1 else 120
REPS = int(sys.argv[2]) if len(sys.argv) > 2 else 5
UA = 'Mozilla/5.0 (X11; Linux x86_64)'
MAXTOK = int(os.environ.get('MAXTOK', '16384'))
PR = ('请数出图片中的人数（人群中的每个人头或人体），不要遗漏，不要重复，'
      '以JSON格式输出：{"count": 数量}，只输出JSON。')
PAT = re.compile(r'\{\s*"?\s*(?:count|计数|数量|人数)\s*"?\s*[:：]\s*"?\s*(\d+)', re.I)
BINS = [(1, 5), (5, 15), (15, 30), (30, 50), (50, 75), (75, 101)]

rows = list(csv.DictReader(open('/root/closed/man1000.csv', encoding='utf-8-sig')))[:N]
print('设计：item %d 项 × 重复 %d 次 = %d 次调用；model=%s' % (len(rows), REPS, len(rows) * REPS, MODEL))
print('item 的 GT：均值 %.1f  中位 %d  max %d  （全部 GT>=1）'
      % (np.mean([int(r['gt']) for r in rows]), int(np.median([int(r['gt']) for r in rows])),
         max(int(r['gt']) for r in rows)), flush=True)

# 预编码，保证每次重复输入逐字节一致
CACHE = {}
for r in rows:
    with Image.open('/root/datasets_mask/visdrone/images/test/%s.jpg' % r['item']) as im:
        b = io.BytesIO(); im.convert('RGB').save(b, 'JPEG', quality=92)
        CACHE[r['item']] = 'data:image/jpeg;base64,' + base64.b64encode(b.getvalue()).decode()
print('预编码完成，共 %d 张' % len(CACHE), flush=True)


def call(item):
    body = json.dumps({'model': MODEL, 'temperature': 0.0, 'max_tokens': MAXTOK,
                       'messages': [{'role': 'user', 'content': [
                           {'type': 'image_url', 'image_url': {'url': CACHE[item]}},
                           {'type': 'text', 'text': PR}]}]}).encode()
    req = urllib.request.Request(API, data=body, headers={
        'Authorization': 'Bearer ' + K, 'Content-Type': 'application/json', 'User-Agent': UA})
    for t in range(8):
        try:
            with urllib.request.urlopen(req, timeout=300) as rp:
                d = json.loads(rp.read().decode())
            ch = d['choices'][0]
            c = ch['message'].get('content') or ''
            m = PAT.search(c.replace(',', ''))
            return (int(m.group(1)) if m else None), ch.get('finish_reason')
        except Exception as e:
            time.sleep(6 * (t + 1) + random.random() * 3)
    return None, 'ERR'


res = {}          # (item, rep) -> (pred, fin)
lock = threading.Lock()
SAFE = MODEL.replace('/', '_').replace('.', '_')
RAW = '/root/ds_repeat_raw_%s.jsonl' % SAFE
# 续跑：读回已完成
if os.path.exists(RAW):
    for line in io.open(RAW, encoding='utf-8'):
        line = line.strip()
        if not line:
            continue
        try:
            o = json.loads(line)
            res[(o['item'], o['rep'])] = (o['pred'], o['finish'])
        except Exception:
            pass
    print('续跑：已有 %d 次结果' % len(res), flush=True)
rawfh = io.open(RAW, 'a', encoding='utf-8')

q = queue.Queue()
for rep in range(REPS):
    for r in rows:
        if (r['item'], rep) not in res:
            q.put((r['item'], rep))
print('待做 %d 次' % q.qsize(), flush=True)
done = [0]


def work():
    while True:
        try:
            item, rep = q.get_nowait()
        except queue.Empty:
            return
        pred, fin = call(item)
        with lock:
            res[(item, rep)] = (pred, fin)
            rawfh.write(json.dumps({'item': item, 'rep': rep, 'pred': pred,
                                    'finish': fin}, ensure_ascii=False) + '\n')
            rawfh.flush()
            done[0] += 1
            if done[0] % 25 == 0:
                print('  本轮 %d/%d' % (done[0], N * REPS - len(res) + done[0]), flush=True)


t0 = time.time()
W = int(os.environ.get('WORKERS', '6') or 6)
th = [threading.Thread(target=work, daemon=True) for _ in range(W)]
for t in th:
    t.start()
for t in th:
    t.join()
rawfh.close()
print('全部完成，用时 %.0f 秒（workers=%d）' % (time.time() - t0, W), flush=True)

GT = {r['item']: int(r['gt']) for r in rows}
items = [r['item'] for r in rows]


def agg(rep):
    preds = np.array([res[(it, rep)][0] if res[(it, rep)][0] is not None else np.nan for it in items], float)
    gt = np.array([GT[it] for it in items], float)
    ok = ~np.isnan(preds)
    p, g = preds[ok], gt[ok]
    z = (p == 0)
    rho_a = (p.mean() - g.mean()) / g.mean() * 100
    rho_m = np.median((p - g) / g * 100)
    rho_b = ((p[~z].mean() - g[~z].mean()) / g[~z].mean() * 100) if (~z).sum() else np.nan
    return dict(rho_a=rho_a, rho_m=rho_m, rho_b=rho_b, zero=z.mean() * 100,
                hit=(p == g).mean() * 100, n=len(p),
                bins={f'{lo}-{hi}': (((p[(g >= lo) & (g < hi)] == 0).mean() * 100)
                                     if ((g >= lo) & (g < hi)).sum() else np.nan)
                      for lo, hi in BINS})


A = [agg(rp) for rp in range(REPS)]
print('\n=== 各次重复的汇总指标 ===')
print('%-6s %10s %10s %10s %10s %10s' % ('rep', 'ρ含0%', 'ρ中位%', 'ρ剔0%', '答0率%', '精确命中%'))
for i, a in enumerate(A):
    print('%-6d %10.1f %10.1f %10.1f %10.2f %10.2f'
          % (i, a['rho_a'], a['rho_m'], a['rho_b'], a['zero'], a['hit']))

print('\n=== 跨重复离散度（决定性证据）===')
print('%-12s %10s %10s %10s %s' % ('指标', '均值', '标准差', '极差', '相对均值%'))
for k, lab in [('rho_a', 'ρ含0'), ('rho_m', 'ρ中位'), ('rho_b', 'ρ剔0'),
               ('zero', '答0率'), ('hit', '精确命中')]:
    v = np.array([a[k] for a in A], float)
    print('%-12s %10.2f %10.3f %10.3f %s'
          % (lab, v.mean(), v.std(ddof=1) if len(v) > 1 else 0.0, v.max() - v.min(),
             ('%.2f%%' % (100 * v.std(ddof=1) / abs(v.mean()))) if len(v) > 1 and v.mean() else '-'))

print('\n=== 逐档答0率的跨重复离散度 ===')
for lo, hi in BINS:
    key = f'{lo}-{hi}'
    v = np.array([a['bins'][key] for a in A], float)
    if np.isnan(v).all():
        continue
    print('  [%d,%d)  均值 %6.2f  标准差 %6.3f  极差 %6.3f' % (lo, hi, np.nanmean(v), np.nanstd(v, ddof=1), np.nanmax(v) - np.nanmin(v)))

io.open('/root/ds_repeat_%s.json' % SAFE, 'w', encoding='utf-8').write(json.dumps(
    dict(model=MODEL, n=N, reps=REPS, workers=W,
         raw={('%s|%d' % k): v for k, v in res.items()},
         agg=A), ensure_ascii=False, indent=1))
print('\n明细写入 /root/ds_repeat_%s.json' % SAFE)
