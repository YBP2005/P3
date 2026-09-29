#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""19f_probe_ablation.py — **消融探针**，由 19e_probe_multi.py 派生（见 make_19f.py）。

与 19e 的差别只有三处：--imgsz（输入尺度）、--system（模板）、--outdir（输出隔离）。
主实验（E2 / A5）一律使用 19e；本文件只用于 M.19 的消融小节。
用法: python3 19b_e1_probe.py --model <id> --arms base,permit,bestA --n 6 --ds st_a [--dry]
图像编码、解析、结果列**逐字复用** 06_dense_vlm.py，保证与语料可比。
"""
import argparse, base64, csv, io, json, os, random, re, sys, threading, queue, time, urllib.request

API = os.environ.get('BAILIAN_API', 'https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions')
AK = os.environ.get('DASHSCOPE_API_KEY', '')
OUTD = '/root/e1_results_ablate'

P = {
    'base':   ('请数出图片中的人数（人群中的每个人头或人体），不要遗漏，不要重复，'
               '以JSON格式输出：{"count": 数量}，只输出JSON。'),
    'permit': ('请数出图片中的人数（人群中的每个人头或人体）。如果你无法逐个确证，'
               '请回答 abstain，而不要猜测。以JSON格式输出：{"count": 数量} 或 {"count": "abstain"}，只输出JSON。'),
    'bestA':  ('报告一个数值人数。即使无法精确计数，也请给出你最好的估计，'
               '并说明哪些部分你无法分辨。以JSON格式输出：{"count": 数量, "unresolved": "说明"}，只输出JSON。'),
    'bestB':  ('你必须给出一个具体数字，不允许回答 0 或拒答。如果你看不清，请按画面中'
               '最可能的人数给出估计值。以JSON格式输出：{"count": 数量}，只输出JSON。'),
    'bestC':  ('先逐块估计画面各区域的人数，再把它们相加，给出最终估计数字。'
               '不允许回答 0 或拒答，必须给出你最好的估计。以JSON格式输出：{"count": 数量}，只输出JSON。'),
    'channel':('请判断这张图片中的人数。你可以：①给出数字；②回答 "cannot_judge" 表示无法判断；'
               '③回答 "no_people" 表示画面中没有可辨认的个体。以JSON格式输出：{"response": ...}，只输出JSON。'),
}
# ===== 为 §3.6(d) 补的臂：把「要求逐项枚举」与「允许弃答」两个因素分开 =====
P['enum'] = ('请把图片中的每一个人**逐个**找出来并数出总数（不要遗漏、不要重复）。'
             '以JSON格式输出：{"count": 数量}，只输出JSON。')
P['enumAbstain'] = ('请把图片中的每一个人**逐个**找出来并数出总数；'
                    '如果有任何一个人你无法确证，请回答 abstain，而不要猜测。'
                    '以JSON格式输出：{"count": 数量} 或 {"count": "abstain"}，只输出JSON。')
P['locate'] = ('请定位并数出图片中的每一个人（locate every person），'
               '对每个人都要给出位置与计数。以JSON格式输出：{"count": 数量}，只输出JSON。')

DS_DIRS = {
    'st_a': '/root/dense/shanghaitech/images/part_A_test',
    'st_b': '/root/dense/shanghaitech/images/part_B_test',
    'ucf':  '/root/dense/ucf_qnrf/UCF-QNRF_ECCV18/Test',
    'visdrone':   '/root/aerial/visdrone/images',
    'aitod':      '/root/aerial/aitod/images',
    'countbench': '/root/ext/countbench/images',
}


def load_gt(ds):
    gt = {}
    # —— 新增域（GT 格式各不相同，故按域分派）——
    if ds in ('visdrone', 'aitod'):
        with open('/root/aerial/gt_%s.csv' % ds, encoding='utf-8-sig') as f:
            for r in csv.DictReader(f):
                gt[r['item']] = int(r['gt'])
        return gt
    if ds == 'countbench':
        with open('/root/ext/countbench/counts.csv', encoding='utf-8-sig') as f:
            for r in csv.DictReader(f):
                _fn = os.path.basename(r['file'])
                # ⚠ countbench 的 item 名**自带扩展名**（base CSV 里是 img_00006.jpg），
                #   而 counts.csv 的 file 也是带扩展名的 ⇒ 两种键都存，避免取交集为空。
                gt[_fn] = int(r['number'])
                gt[os.path.splitext(_fn)[0]] = int(r['number'])
        return gt
    if ds in ('st_a', 'st_b'):
        want = 'part_A' if ds == 'st_a' else 'part_B'
        with open('/root/dense/shanghaitech/counts.csv', encoding='utf-8-sig') as f:
            for r in csv.DictReader(f):
                if r.get('part') == want and r.get('split') == 'test':
                    gt[os.path.splitext(os.path.basename(r['file']))[0]] = int(r['count'])
    else:
        with open('/root/dense/ucf_qnrf/counts.csv', encoding='utf-8-sig') as f:
            for r in csv.DictReader(f):
                if r['split'] == 'Test':
                    gt[os.path.splitext(os.path.basename(r['file']))[0]] = int(r['count'])
    return gt


def b64_of(im, quality=92):
    buf = io.BytesIO(); im.save(buf, 'JPEG', quality=quality)
    return base64.b64encode(buf.getvalue()).decode()


def call_img(b64, prompt, model, timeout=180, retries=5, system=''):
    msgs = []
    if system:
        msgs.append({'role': 'system', 'content': system})
    msgs.append({'role': 'user', 'content': [
        {'type': 'image_url', 'image_url': {'url': 'data:image/jpeg;base64,' + b64}},
        {'type': 'text', 'text': prompt}]})
    payload = {'model': model, 'messages': msgs, 'temperature': 0.0, 'max_tokens': 128}
    req = urllib.request.Request(API, data=json.dumps(payload).encode(),
                                 headers={'Content-Type': 'application/json',
                                          'Authorization': 'Bearer ' + AK})
    last = None
    for a in range(retries):
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


def parse(raw):
    m = re.search(r'\{\s*(?:count|response|计数|数量|人数)\s*[:：]\s*"?(\d+|abstain|cannot_judge|no_people)', raw, re.I)
    if m:
        v = m.group(1)
        return int(v) if v.isdigit() else v
    m = re.search(r'-?\d+', raw.replace(',', ''))
    return int(m.group(0)) if m else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--model', required=True)
    ap.add_argument('--arms', default='base,permit,bestA')
    ap.add_argument('--ds', default='st_a')
    ap.add_argument('--n', type=int, default=6)
    ap.add_argument('--workers', type=int, default=4)
    ap.add_argument('--reps', type=int, default=1)
    ap.add_argument('--pool', default='zero', choices=('zero', 'nonzero'))
    ap.add_argument('--imgsz', type=int, default=0, help='最长边缩放到该值；0=原生')
    ap.add_argument('--system', default='', help='插入的 system 消息；空=不加')
    ap.add_argument('--outdir', default='/root/e1_results_ablate')
    A = ap.parse_args()
    global OUTD
    if A.pool == 'nonzero':
        OUTD = '/root/e1_results_nonzero'
    OUTD = A.outdir
    os.makedirs(OUTD, exist_ok=True)
    variant = ('s%d' % A.imgsz) if A.imgsz else 'native'
    if A.system:
        variant += '_sys'
    tag = A.model.replace('/', '_')
    gt = load_gt(A.ds)
    # 取 base 臂 **pred==0** 的 item
    base_csv = '/root/dense_results/vlm_%s_base_whole.csv' % A.ds
    zero = []
    with open(base_csv, encoding='utf-8-sig') as f:
        for r in csv.DictReader(f):
            _p = str(r.get('pred', '')).strip()
            _want = (_p in ('0', '0.0')) if A.pool == 'zero' else (_p not in ('0', '0.0'))
            if _want and r.get('item') in gt:
                zero.append(r['item'])
    zero.sort(key=lambda i: gt[i])
    # 按 gt 分层抽样：低/中/高三段各取 n/3
    # 分层：按 gt 排序后等间隔取 n 个（原写 len//3 ⇒ 只能取到 4 个）
    step = max(1, len(zero) // max(1, A.n))
    pick = zero[::step][:A.n] if len(zero) > A.n else zero
    print('  base 臂 pred==0 的 item 共 %d 个；本次抽 %d 个（gt 从 %d 到 %d）'
          % (len(zero), len(pick), gt[pick[0]] if pick else 0, gt[pick[-1]] if pick else 0))
    from PIL import Image
    for arm in A.arms.split(','):
        outp = os.path.join(OUTD, 'e1_%s_%s_%s_%s.csv' % (tag, A.ds, arm, variant))
        done = set()
        if os.path.exists(outp):
            with open(outp, encoding='utf-8-sig') as f:
                done = {r['item'] for r in csv.DictReader(f)}
        todo = []
        for i in pick:
            for r in range(A.reps):
                k = i if A.reps == 1 else '%s#r%d' % (i, r)
                if k not in done:
                    todo.append(k)
        if not todo:
            print('  [%s] 已完成，跳过' % arm); continue
        q = queue.Queue()
        for i in todo:
            q.put(i)
        lock = threading.Lock()
        newf = not os.path.exists(outp)
        fh = open(outp, 'a', newline='', encoding='utf-8')
        w = csv.writer(fh)
        if newf:
            w.writerow(['item', 'gt', 'pred', 'parse_ok', 'raw', 'latency_s'])
        def work():
            while True:
                try:
                    it = q.get_nowait()
                except Exception:
                    return
                base_it = it.split('#r')[0]
                p = None
                for _ext in ('', '.jpg', '.png', '.jpeg', '.tif', '.TIF', '.bmp'):
                    _cand = os.path.join(DS_DIRS[A.ds], base_it + _ext)
                    if os.path.exists(_cand):
                        p = _cand
                        break
                if p is None:
                    p = os.path.join(DS_DIRS[A.ds], base_it + '.jpg')
                t0 = time.time()
                try:
                    im = Image.open(p).convert('RGB')
                    if A.imgsz:
                        im.thumbnail((A.imgsz, A.imgsz), Image.LANCZOS)
                    raw = call_img(b64_of(im), P[arm], A.model, system=A.system)
                    v = parse(raw)
                    ok = 1 if v is not None else 0
                except Exception as e:
                    raw, v, ok = 'ERR:%s' % str(e)[:150], None, 0
                dt = time.time() - t0
                with lock:
                    w.writerow([it, gt[base_it], '' if v is None else v, ok, raw[:800], round(dt, 2)])
                    fh.flush()
        ths = [threading.Thread(target=work) for _ in range(A.workers)]
        [t.start() for t in ths]; [t.join() for t in ths]
        fh.close()
        # 摘要
        rows = list(csv.DictReader(open(outp, encoding='utf-8-sig')))
        z = sum(1 for r in rows if r['pred'] in ('0', '0.0', '0'))
        print('  [%s] %d 行；pred==0 的 %d 个；-> %s' % (arm, len(rows), z, outp))


if __name__ == '__main__':
    main()
