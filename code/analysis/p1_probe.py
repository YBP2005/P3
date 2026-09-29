#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""p1_probe.py —— P1 的采集器：**importlib 复用冻结探针 19e_probe_multi.py 的提示词/解析/传输**。

设计纪律（沿用本项目做法）：
  * **不重写提示词、不重写解析器、不重写传输**：`P`（提示词字典）、`parse()`、`b64_of()`、`call_img()`
    全部从 `19e_probe_multi.py`（md5 `03edb14c98ffa3aea9ffa20f59b00bc8`，E2/E3 用的同一支）导入，
    启动即断言其 md5；不符即退出（与 `make_19f.py` 同规矩）。
  * 相对母本**只改三件事**：① 图像来自本地网格 manifest（`p1_prep_grid.py` 生成，逐位可复现）；
    ② item 集合 = 全网格（不再按 base 臂 pred==0 抽样）；③ 输出 schema 换成 P1 的，且
    **raw 完整保存不截断**（旧脚本截到 800/80 字符，独立重算就无法复现解析）。
  * 逐行可续跑：已完成的 item 跳过（重跑不重复计费）。

用法:
    python -u p1_probe.py --grid <网格目录> --model <served-id> --arm base \
        --api http://127.0.0.1:8000/v1/chat/completions --outd /root/p1_results \
        --family gemma-3-12b --workers 8 [--limit 5] [--dry]
输出: <outd>/p1_<family>_<arm>.csv
      item,n,r,sigma,gt,pred,parse_ok,is_zero,abstain,raw,latency_s
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

sys.stdout.reconfigure(encoding='utf-8')
HERE = os.path.dirname(os.path.abspath(__file__))
# 冻结探针的位置：默认与本品同目录；远端若把冻结件放在 /root/19e_probe_multi.py，用
#   P1_FROZEN=/root/19e_probe_multi.py 指过去（避免"必须同目录"这个脚坑）。
FROZEN = os.environ.get('P1_FROZEN') or os.path.join(HERE, '19e_probe_multi.py')
FROZEN_MD5 = '03edb14c98ffa3aea9ffa20f59b00bc8'
ABSTAIN_MARK = ('abstain', 'cannot', "can't", 'unable', 'too many', '无法', '不能', '数不清',
                '难以', '不确定', '无法判断', '众多')


def load_frozen():
    got = hashlib.md5(io.open(FROZEN, 'rb').read()).hexdigest()
    if got != FROZEN_MD5:
        raise SystemExit('!! 冻结探针 md5 不符：%s（应 %s）⇒ 拒绝运行，先核来源' % (got[:12], FROZEN_MD5[:12]))
    spec = importlib.util.spec_from_file_location('frozen19e', FROZEN)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    print('  冻结探针 19e_probe_multi.py md5 %s ✓（提示词/解析/传输逐字复用）' % got[:12])
    return m


def circle_prompts(F):
    """把冻结的**合同臂**提示词从"人"改到"圆点"，且**只改对象名词**。

    为什么必须改：P1 的受控版是**合成圆点网格**（`p1_prep_grid.py`），向它问"图中有多少人"会把
    "对象语义"与"契约措辞"搅在一起。改法是**机械且可审计**的：拿冻结臂的原文，
    在**第一个句号之前**只替换对象短语，句号之后的全部内容（`abstain` 子句 + JSON 指令）
    **必须逐字不变**——下面用断言把这一点钉死。这也与 G.2 用"三个合同臂 + 合成圆点网格"的做法一致。
    """
    out = {}
    for arm in ('base', 'permit'):
        src = F.P[arm]
        head, sep, tail = src.partition('。')
        if not sep:
            raise SystemExit('!! 冻结臂 %r 的提示词结构与预期不符（没有句号分隔）' % arm)
        new_head = head.replace('人数（人群中的每个人头或人体）', '圆形数量（画面中的每一个圆点）')
        if new_head == head:
            raise SystemExit('!! 未能替换对象短语，冻结件可能已变：%r' % head)
        out[arm] = new_head + sep + tail
        if out[arm][-len(tail) - 1:] != sep + tail:
            raise SystemExit('!! 句号之后的部分被动过 —— 拒绝运行（只允许改对象名词）')
    return out


def call_img_sys(F, b64, prompt, model, system, timeout=180, retries=5):
    """与冻结 `19e.call_img` **逐字同构**，只在消息列表**最前面**插一条 system 消息。

    用途：P1 的 template 轴（v0547 盲审 grok46 −3.0："一族内 template × contract 交互"）。
    system 文本沿用本项目此前那次消融用过的同一条（`a800_ablate.sh`），以便与 M.19.8 的 `+system` 列可比：
        "You are a careful visual counting assistant. Follow the requested output format exactly."
    不加 `--system` 时**一律走冻结传输**（见 main 里的分支），所以主网格的结果不受本函数影响。
    """
    import urllib.error
    payload = {'model': model, 'messages': [
        {'role': 'system', 'content': system},
        {'role': 'user', 'content': [
            {'type': 'image_url', 'image_url': {'url': 'data:image/jpeg;base64,' + b64}},
            {'type': 'text', 'text': prompt}]}],
        'temperature': 0.0, 'max_tokens': 128}
    req = urllib.request.Request(F.API, data=json.dumps(payload).encode(),
                                 headers={'Content-Type': 'application/json',
                                          'Authorization': 'Bearer ' + getattr(F, 'AK', 'dummy')})
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--grid', required=True, help='p1_prep_grid.py 的输出目录（含 manifest.csv）')
    ap.add_argument('--family', required=True)
    ap.add_argument('--arm', required=True)
    ap.add_argument('--model', required=True)
    ap.add_argument('--api', default='http://127.0.0.1:8000/v1/chat/completions')
    ap.add_argument('--outd', default='/root/p1_results')
    ap.add_argument('--workers', type=int, default=8)
    ap.add_argument('--limit', type=int, default=0)
    ap.add_argument('--object', default='circles', choices=('circles', 'people'),
                    help='受控版用 circles（合成圆点网格）；生态版（真实人群图）用 people')
    ap.add_argument('--system', default='', help='template 轴：插入一条 system 消息（空=走冻结传输）')
    ap.add_argument('--only-sigma', type=float, default=None,
                    help='只跑某一档 σ（template 轴只在 σ=8 那一层做）')
    ap.add_argument('--tag', default='', help='输出文件名附加标记（如 sys / native）')
    ap.add_argument('--dry', action='store_true', help='不调 API，只验证 manifest/写盘/续跑逻辑')
    ap.add_argument('--show-prompts', action='store_true')
    A = ap.parse_args()

    F = load_frozen()
    F.API = A.api                      # 只改端点；提示词与解析仍是冻结件里的那份
    if A.arm not in F.P:
        raise SystemExit('!! 臂 %r 不在冻结提示词字典里（可选：%s）' % (A.arm, sorted(F.P)))
    PROMPT = F.P[A.arm]
    if A.object == 'circles':
        PROMPT = circle_prompts(F)[A.arm]
    if A.show_prompts:
        print('  ── 冻结臂（people）：%s' % F.P[A.arm])
        print('  ── 本次使用（%s）：%s' % (A.object, PROMPT))
        print('  句号之后逐字相同：%s' % (PROMPT.partition('。')[2] == F.P[A.arm].partition('。')[2]))
        return 0
    from PIL import Image
    rows = list(csv.DictReader(io.open(os.path.join(A.grid, 'manifest.csv'), encoding='utf-8')))
    if A.only_sigma is not None:
        rows = [r for r in rows if abs(float(r['sigma']) - A.only_sigma) < 1e-9]
        print('  [%s/%s] --only-sigma %g ⇒ %d 项' % (A.family, A.arm, A.only_sigma, len(rows)))
    if A.limit:
        rows = rows[:A.limit]
    os.makedirs(A.outd, exist_ok=True)
    outp = os.path.join(A.outd, 'p1%s_%s_%s.csv'
                        % (('b_' + A.tag) if A.tag else '', A.family, A.arm))
    done = set()
    if os.path.exists(outp):
        with io.open(outp, encoding='utf-8-sig', newline='') as f:
            done = {r['item'] for r in csv.DictReader(f)}
    todo = [r for r in rows if r['item'] not in done]
    print('  [%s/%s%s] 网格 %d 项 / 已完成 %d / 本次 %d ｜ model=%s ｜ system=%s' %
          (A.family, A.arm, ('/' + A.tag) if A.tag else '', len(rows), len(done), len(todo),
           A.model, ('（插入了 system 消息）' if A.system else '无（冻结传输）')))
    if not todo:
        print('  已完成，跳过')
        return 0
    q = queue.Queue()
    for r in todo:
        q.put(r)
    lock = threading.Lock()
    newf = not os.path.exists(outp)
    fh = io.open(outp, 'a', newline='', encoding='utf-8')
    w = csv.writer(fh, lineterminator='\n')
    if newf:
        w.writerow(['item', 'n', 'r', 'sigma', 'gt', 'pred', 'parse_ok', 'is_zero', 'abstain',
                    'raw', 'latency_s'])
    st = {'n': 0, 't0': time.time(), 'z': 0, 'ab': 0, 'pf': 0}

    def work():
        while True:
            try:
                r = q.get_nowait()
            except queue.Empty:
                return
            t0 = time.time()
            raw, v, ok, z, ab = '', None, 0, 0, 0
            try:
                im = Image.open(os.path.join(A.grid, r['path'])).convert('RGB')
                if A.dry:
                    raw = '{"count": %s}' % (0 if (hash(r['item']) % 2 == 0) else r['n'])
                else:
                    b64 = F.b64_of(im, quality=95)
                    raw = (call_img_sys(F, b64, PROMPT, A.model, A.system) if A.system
                           else F.call_img(b64, PROMPT, A.model))
                v = F.parse(raw)
                ok = 1 if v is not None else 0
                z = 1 if (isinstance(v, int) and v == 0) else 0
                low = (raw or '').lower()
                ab = 1 if any(k in low for k in ABSTAIN_MARK) else 0
            except Exception as e:
                raw, v, ok = 'ERR:%s' % str(e)[:300], None, 0
            dt = time.time() - t0
            with lock:
                # ★ raw **完整**写入（不截断）——独立重算要靠它复现解析
                w.writerow([r['item'], r['n'], r['r'], r['sigma'], r['gt'],
                            '' if v is None else v, ok, z, ab, raw, '%.2f' % dt])
                fh.flush()
                st['n'] += 1
                st['z'] += z
                st['ab'] += ab
                st['pf'] += (1 - ok)
                if st['n'] % 200 == 0:
                    print('    %d/%d  %.2f it/s  zero=%d abstain=%d parse_fail=%d' %
                          (st['n'], len(todo), st['n'] / max(time.time() - st['t0'], 1e-9),
                           st['z'], st['ab'], st['pf']), flush=True)

    ts = [threading.Thread(target=work, daemon=True) for _ in range(max(1, A.workers))]
    [t.start() for t in ts]
    [t.join() for t in ts]
    fh.close()
    print('  [%s/%s] DONE：%d 行写入 %s（zero=%d abstain=%d parse_fail=%d）'
          % (A.family, A.arm, st['n'], outp, st['z'], st['ab'], st['pf']))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
