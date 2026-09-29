# -*- coding: utf-8 -*-
"""w1_hosted_probe.py — W2：**闭源/托管端点**上的同契约实验（零 GPU，在 A800 上跑）。

为什么放在 A800 而不是本地：本项目四个域的图像与选样代码都在 A800 上，**同一批 item** 才能与
开源家族面板逐格对比；本地虽然也有归档副本，但多一次搬运就多一次错配风险。

仪器：importlib 加载 /root/19e_probe_multi.py，复用它的 `P`（契约提示词）、`parse()`、`b64_of()`、
`call_img()` —— 19e 本体零改动（md5 03edb14c98ff）。端点通过环境变量切换：
    BAILIAN_API=https://api.ofox.io/v1/chat/completions   DASHSCOPE_API_KEY=<ofox key>
选样：**逐字复刻 19f 的零池抽样**（读 /root/dense_results/vlm_<ds>_base_whole.csv，pred==0，
按 gt 排序后等间隔取 n）⇒ 与开源面板同 item。

冻结选择规则（写死在下面 PANEL，跑前定、跑后不改）：
    每个厂商取一个当前旗舰/主力**视觉**模型，共 3 个厂商；是否能用作受试由 **smoke 门**决定
    （与开源面板同一门：base 臂 2 条 item 中至少 1 条能解析出计数）。
用法：python3 w1_hosted_probe.py [--n 150] [--arms base,permit] [--domains st_a,ucf]
"""
import argparse
import csv
import importlib.util
import io
import os
import queue
import sys
import threading
import time

sys.stdout.reconfigure(encoding='utf-8')
OUTD = '/root/w1_results/hosted'
P19E = '/root/19e_probe_multi.py'
DS_DIRS = {'st_a': '/root/dense/shanghaitech/images/part_A_test',
           'ucf': '/root/dense/ucf_qnrf/UCF-QNRF_ECCV18/Test',
           'visdrone': '/root/aerial/visdrone/images',
           'aitod': '/root/aerial/aitod/images'}
# 冻结的托管端点面板（一厂商一个；跑前定，跑后不得增删）
# ★ 2026-09-23 用户指令（三条，均发生在**任何托管端点有效数据产生之前**）：
#   ① 不使用 Anthropic/Claude；② 先跑通 google/gemini-3.8-flash；③ GPT 侧指定 openai/gpt-5.6-luna；
#   另：x-ai/grok-4.6 亦可用。
#   披露：grok-4.6 同时是本项目**新颖度评审面板**的成员（角色不同：此处是被测对象，那里是评审者）；
#   同一权重担任两种角色不构成方法论冲突，但必须在记录里写明，供读者自行判断。
PANEL = [('google/gemini-3.8-flash', 'gemini-3.8-flash', 'Google'),
         ('openai/gpt-5.6-luna', 'gpt-5.6-luna', 'OpenAI'),
         ('x-ai/grok-4.6', 'grok-4.6', 'xAI')]

spec = importlib.util.spec_from_file_location('p19e', P19E)
E = importlib.util.module_from_spec(spec)
spec.loader.exec_module(E)
assert hasattr(E, 'P') and hasattr(E, 'parse') and hasattr(E, 'call_img'), '19e 结构不符'
print('仪器：复用 19e 的 P/parse/b64_of（19e 未改动）；端点=%s' % E.API)

# ---------------------------------------------------------------- 托管端点的调用器
# ★ 为什么要单独一个调用器（2026-09-23 实测根因）：
#   19e 的 call_img 把 `max_tokens` 写死为 **128**。开源家族在那个额度下够用（答案就是 {"count": N}），
#   但 gemini-3.8-flash 默认带"思考"token，128 个额度全被思考吃掉，回复被截断成
#   ` people visible` / 半截 `{"count"` —— 这是**仪器额度**造成的假失败，不是模型不会数。
#   故：托管端点的调用器复制 19e 的 payload 形状（同样的 image_url + text 两条 content，
#   temperature=0.0），只改两处并全部记录：
#     · max_tokens 128 -> 2048（给"思考型"端点留足余量；实测 512 仍会把 gpt-5.6-luna 截成空回复）
#     · 增加 reasoning_effort='minimal'（端点不支持时自动去掉重试）
#   **提示词 P、解析器 parse() 仍逐字来自 19e**，故与开源面板的口径可比；
#   同时把 finish_reason 落进 CSV，便于如实报"有多少条是被额度截断的"。
#   三家厂商统一用同一额度（公平），且此决定发生在 W2 正跑之前、只影响截断不影响提示词。
def call_img_hosted(b64, prompt, model, timeout=300, retries=4, max_tokens=2048):
    import json as _json
    import urllib.error
    import urllib.request
    base = {'model': model,
            'messages': [{'role': 'user', 'content': [
                {'type': 'image_url', 'image_url': {'url': 'data:image/jpeg;base64,' + b64}},
                {'type': 'text', 'text': prompt}]}],
            'temperature': 0.0, 'max_tokens': max_tokens}
    attempts = [dict(base, reasoning_effort='minimal'), dict(base)]
    last = None
    for a in range(retries):
        payload = attempts[0] if a == 0 else attempts[min(1, a)]
        req = urllib.request.Request(E.API, data=_json.dumps(payload).encode(),
                                     headers={'Content-Type': 'application/json',
                                              'Authorization': 'Bearer ' + E.AK})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                j = _json.loads(r.read().decode())
            ch = (j.get('choices') or [{}])[0]
            content = (ch.get('message') or {}).get('content') or ''
            return content, (ch.get('finish_reason') or '')
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


def load_gt(ds):
    return E.load_gt(ds)


def pick_zero(ds, n):
    """★ 逐字复刻 19f 的零池抽样（保证与开源面板同 item）。"""
    gt = load_gt(ds)
    base_csv = '/root/dense_results/vlm_%s_base_whole.csv' % ds
    zero = []
    with io.open(base_csv, encoding='utf-8-sig') as f:
        for r in csv.DictReader(f):
            if str(r.get('pred', '')).strip() in ('0', '0.0') and r.get('item') in gt:
                zero.append(r['item'])
    zero.sort(key=lambda i: gt[i])
    step = max(1, len(zero) // max(1, n))
    pick = zero[::step][:n] if len(zero) > n else zero
    print('  [%s] 零池 %d 条，取 %d 条（gt %d..%d）' % (ds, len(zero), len(pick),
                                                        gt[pick[0]] if pick else 0,
                                                        gt[pick[-1]] if pick else 0))
    return pick, gt


def run(model_id, tag, ds, arm, n, workers):
    """smoke 门用 n=2；正跑用 n=150。输出名 <tag>__<ds>__<arm>.csv（供本地判定器分组读取）。"""
    os.makedirs(OUTD, exist_ok=True)
    pick, gt = pick_zero(ds, n)
    outp = os.path.join(OUTD, '%s__%s__%s.csv' % (tag, ds, arm))
    done = set()
    if os.path.exists(outp):
        with io.open(outp, encoding='utf-8-sig') as f:
            done = {r['item'] for r in csv.DictReader(f)}
    todo = [i for i in pick if i not in done]
    if not todo:
        print('  [%s/%s/%s] 已完成，跳过' % (tag, ds, arm)); return 0
    from PIL import Image
    q = queue.Queue()
    for i in todo:
        q.put(i)
    lock = threading.Lock()
    fh = io.open(outp, 'a', newline='', encoding='utf-8')
    w = csv.writer(fh)
    if not done:
        w.writerow(['item', 'gt', 'pred', 'parse_ok', 'raw', 'latency_s', 'finish'])
    okn = [0]
    trun = [0]

    def work():
        while True:
            try:
                it = q.get_nowait()
            except Exception:
                return
            p = None
            for ext in ('', '.jpg', '.png', '.jpeg', '.tif', '.TIF', '.bmp'):
                c = os.path.join(DS_DIRS[ds], it + ext)
                if os.path.exists(c):
                    p = c; break
            p = p or os.path.join(DS_DIRS[ds], it + '.jpg')
            t0 = time.time()
            fin = ''
            try:
                im = Image.open(p).convert('RGB')
                raw, fin = call_img_hosted(E.b64_of(im), E.P[arm], model_id)
                v = E.parse(raw)
                ok = 1 if v is not None else 0
            except Exception as ex:
                raw, v, ok = 'ERR:%s' % str(ex)[:200], None, 0
            with lock:
                okn[0] += ok
                if str(fin).lower() == 'length':
                    trun[0] += 1
                w.writerow([it, gt[it], '' if v is None else v, ok, (raw or '')[:800],
                            round(time.time() - t0, 2), fin])
                fh.flush()
    ths = [threading.Thread(target=work) for _ in range(workers)]
    [t.start() for t in ths]; [t.join() for t in ths]
    fh.close()
    rows = list(csv.DictReader(io.open(outp, encoding='utf-8-sig')))
    z = sum(1 for r in rows if str(r.get('pred', '')).strip() in ('0', '0.0'))
    print('  [%s/%s/%s] %d 行；答0 %d；本次可解析 %d；被额度截断(finish=length) %d -> %s'
          % (tag, ds, arm, len(rows), z, okn[0], trun[0], outp))
    return okn[0]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--n', type=int, default=150)
    ap.add_argument('--arms', default='base,permit')
    ap.add_argument('--domains', default='st_a,ucf')
    ap.add_argument('--workers', type=int, default=4)
    ap.add_argument('--smoke', action='store_true', help='只跑 2 条做门控')
    ap.add_argument('--only', default='', help='只跑指定 tag（逗号分隔），便于逐个跑通')
    A = ap.parse_args()
    n = 2 if A.smoke else A.n
    only = [x.strip() for x in A.only.split(',') if x.strip()]
    for mid, tag, vendor in PANEL:
        if only and tag not in only:
            continue
        print('===== 托管端点 %s（%s）=====' % (tag, vendor))
        tot = 0
        for ds in A.domains.split(','):
            for arm in A.arms.split(','):
                try:
                    tot += run(mid, tag, ds, arm, n, A.workers)
                except Exception as ex:
                    print('  !! %s/%s/%s 失败：%s' % (tag, ds, arm, str(ex)[:160]))
        print('  [%s] 本次可解析合计 %d' % (tag, tot))


if __name__ == '__main__':
    main()
