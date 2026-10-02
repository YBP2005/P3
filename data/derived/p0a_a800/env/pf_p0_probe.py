#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""pf_p0_probe.py — P3R4 §3B **P0 动态范围预演**探针（打到本地 vLLM 的 OpenAI 兼容端点）

【依据】方案 §1.5（预演设计 + 五条通过标准）、§1.4.2（仪器）、§1.4.3
【提示词】`base` 臂的提示词**逐字取自**冻结探针 `19e_probe_multi.py`
          （md5 03edb14c98ffa3aea9ffa20f59b00bc8）的 `P['base']` 与 `parse()`。
【参数】temperature 0、max_tokens 128（同冻结探针）。
【schema】输出 CSV 列**逐字**：`item,gt,pred,parse_ok,raw,latency_s`

★ 与冻结探针的**唯一差别**（两者都刻意）：
  ① 端点走**本地 vLLM**（`--api` 默认 `http://127.0.0.1:8012/v1/chat/completions`），
     而不是冻结探针默认的百炼 API —— 这正是第 3 轮的实际用法（`BAILIAN_API=$API`）。
  ② item 来自**冻结清单**（`pf_p0_items.json`，固定种子抽样），
     而不是冻结探针的"按 gt 分层从零池抽 n 个" —— 因为 P0 要的是**两池各 20 项**。

用法：
  python3 pf_p0_probe.py --api <url> --model <served-name> --manifest pf_p0_items.json \
      --pool zero --start 1 --out /root/pf_pilot/B1_zero_start1.csv [--workers 4] [--dry]
"""
import argparse, base64, csv, io, json, os, re, sys, threading, queue, time, urllib.request, urllib.error

# ★ `base` 臂提示词 —— 逐字取自 19e_probe_multi.py 的 P['base']
BASE_PROMPT = ('请数出图片中的人数（人群中的每个人头或人体），不要遗漏，不要重复，'
               '以JSON格式输出：{"count": 数量}，只输出JSON。')

IMG_DIRS = {
    'st_a': '/root/dense/shanghaitech/images/part_A_test',
    'ucf':  '/root/dense/ucf_qnrf/UCF-QNRF_ECCV18/Test',
}
EXTS = ('', '.jpg', '.png', '.jpeg', '.tif', '.TIF', '.bmp')


def parse(raw):
    """★ 逐字取自 19e_probe_multi.py::parse（冻结口径）。"""
    m = re.search(r'\{\s*(?:count|response|计数|数量|人数)\s*[:：]\s*"?(\d+|abstain|cannot_judge|no_people)', raw, re.I)
    if m:
        v = m.group(1)
        return int(v) if v.isdigit() else v
    m = re.search(r'-?\d+', raw.replace(',', ''))
    return int(m.group(0)) if m else None


def find_img(dom, item):
    d = IMG_DIRS[dom]
    for e in EXTS:
        p = os.path.join(d, item + e)
        if os.path.exists(p):
            return p
    return None


def b64_of(im, quality=92):
    buf = io.BytesIO(); im.save(buf, 'JPEG', quality=quality)
    return base64.b64encode(buf.getvalue()).decode()


def call_img(b64, prompt, model, api, timeout=180, retries=5):
    payload = {'model': model, 'messages': [{'role': 'user', 'content': [
        {'type': 'image_url', 'image_url': {'url': 'data:image/jpeg;base64,' + b64}},
        {'type': 'text', 'text': prompt}]}], 'temperature': 0.0, 'max_tokens': 128}
    data = json.dumps(payload).encode()
    last = None
    for a in range(retries):
        req = urllib.request.Request(api, data=data,
                                     headers={'Content-Type': 'application/json',
                                              'Authorization': 'Bearer EMPTY'})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode())['choices'][0]['message']['content']
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--api', default='http://127.0.0.1:8012/v1/chat/completions')
    ap.add_argument('--model', required=True)
    ap.add_argument('--manifest', default='/root/pf_pilot/pf_p0_items.json')
    ap.add_argument('--pool', required=True, choices=('zero', 'nonzero'))
    ap.add_argument('--start', type=int, required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--workers', type=int, default=4)
    ap.add_argument('--dry', action='store_true')
    A = ap.parse_args()

    man = json.load(io.open(A.manifest, encoding='utf-8'))
    key = 'items_zero' if A.pool == 'zero' else 'items_nonzero'
    items = man[key]
    print('清单：seed=%s pool=%s n=%d  源件数=%d' %
          (man['seed'], A.pool, len(items), len(man.get('md5_of_inputs', {}))))

    if A.dry:
        print('--- DRY: 只核对提示词与图像可达性，不发请求、不写盘 ---')
        miss = 0
        for it in items:
            p = find_img(it['domain'], it['img_base'])
            if p is None:
                miss += 1
                print('   !! 图像缺失 %s (%s)' % (it['item'], it['domain']))
        print('   提示词（逐字）: %s' % BASE_PROMPT)
        print('   图像缺失 %d / %d' % (miss, len(items)))
        return 0

    os.makedirs(os.path.dirname(A.out), exist_ok=True)
    done = set()
    if os.path.exists(A.out):
        with io.open(A.out, encoding='utf-8-sig') as f:
            done = {r['item'] for r in csv.DictReader(f)}
    todo = [it for it in items if it['item'] not in done]
    print('待跑 %d 项（已完成 %d），workers=%d，端点 %s' % (len(todo), len(done), A.workers, A.api))

    newf = not os.path.exists(A.out)
    lock = threading.Lock()
    q = queue.Queue()
    for it in todo:
        q.put(it)
    fh = io.open(A.out, 'a', newline='', encoding='utf-8')
    w = csv.writer(fh)
    if newf:
        w.writerow(['item', 'gt', 'pred', 'parse_ok', 'raw', 'latency_s'])
    stats = {'ok': 0, 'empty': 0, 'miss': 0, 'zero': 0}

    def work():
        from PIL import Image
        while True:
            try:
                it = q.get_nowait()
            except Exception:
                return
            t0 = time.time()
            p = find_img(it['domain'], it['img_base'])
            if p is None:
                raw, v, ok = 'ERR:image_not_found', None, 0
                with lock:
                    stats['miss'] += 1
                    stats['empty'] += 1
                    w.writerow([it['item'], it['gt'], '', ok, raw, 0.0]); fh.flush()
                continue
            try:
                im = Image.open(p).convert('RGB')
                raw = call_img(b64_of(im), BASE_PROMPT, A.model, A.api)
                v = parse(raw)
                ok = 1 if v is not None else 0
            except Exception as e:
                raw, v, ok = 'ERR:%s' % str(e)[:150], None, 0
            dt = time.time() - t0
            with lock:
                stats['ok' if ok else 'empty'] += 1
                if v == 0:
                    stats['zero'] += 1
                w.writerow([it['item'], it['gt'], '' if v is None else v, ok, raw[:800], round(dt, 2)])
                fh.flush()

    ths = [threading.Thread(target=work) for _ in range(A.workers)]
    [t.start() for t in ths]
    [t.join() for t in ths]
    fh.close()

    rows = list(csv.DictReader(io.open(A.out, encoding='utf-8-sig')))
    z = sum(1 for r in rows if (r.get('pred') or '').strip() in ('0', '0.0'))
    empt = sum(1 for r in rows if (r.get('pred') or '').strip() == '')
    pok = sum(1 for r in rows if (r.get('parse_ok') or '').strip() == '1')
    print('  [%s] %d 行；pred==0 的 %d；空 pred %d；parse_ok %d（%.1f%%）；-> %s'
          % (A.pool, len(rows), z, empt, pok, 100.0 * pok / len(rows) if rows else float('nan'), A.out))
    return 0


if __name__ == '__main__':
    sys.exit(main())
