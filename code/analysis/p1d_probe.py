#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""p1d_probe.py —— P1 新增臂（`forbid0` / `neutral0`）的采集器。

与 `p1_probe.py` 的关系：**老仪器一个字节不动**（它产出了已发表的 §M.19.10 base/permit 结果），
本件是它的**加法**：多两个臂、多一个来源冻结件。

冻结链（启动即断言，不符即退出）：
  ① `19e_probe_multi.py` md5 `03edb14c98ffa3aea9ffa20f59b00bc8`（提示词/解析/传输逐字复用）
  ② `p1d_prompts.json`   md5 `d35ec04a163ecdcb021e1273bfc8e198`（新增两臂的人版提示词）
  ③ 圆点版只改**对象名词**：第一个句号之前 `人数（人群中的每个人头或人体）` →
     `圆形数量（画面中的每一个圆点）`，**句号之后必须逐字节相同**
  ④ **交叉自检**：本件的泛化适配器对 `base`/`permit` 的输出，必须与 `p1_probe.circle_prompts()`
     **逐字节相同**——证明"泛化"没有偷偷改变已发表臂的措辞。

用法:
  P1_FROZEN=/root/19e_probe_multi.py python -u p1d_probe.py \
      --grid /root/p1_grid --family <id> --arm forbid0 --model <served-id> \
      --api http://127.0.0.1:8003/v1/chat/completions --outd /root/p1d_results [--tag ...]
输出: <outd>/p1d[_tag]_<family>_<arm>.csv
      item,n,r,sigma,gt,pred,parse_ok,is_zero,abstain,raw,latency_s   （与 p1_probe 同 schema）
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
FROZEN = os.environ.get('P1_FROZEN') or os.path.join(HERE, '19e_probe_multi.py')
FROZEN_MD5 = '03edb14c98ffa3aea9ffa20f59b00bc8'
EXTRA = os.environ.get('P1D_PROMPTS') or os.path.join(HERE, 'p1d_prompts.json')
EXTRA_MD5 = 'd35ec04a163ecdcb021e1273bfc8e198'
# 与 p1_probe.py 完全相同的弃答标记，保证两套产物可比
ABSTAIN_MARK = ('abstain', 'cannot', "can't", 'unable', 'too many', '无法', '不能', '数不清',
                '难以', '不确定', '无法判断', '众多')
OBJ_OLD = '人数（人群中的每个人头或人体）'
OBJ_NEW = '圆形数量（画面中的每一个圆点）'


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def load_frozen():
    got = hashlib.md5(io.open(FROZEN, 'rb').read()).hexdigest()
    if got != FROZEN_MD5:
        raise SystemExit('!! 冻结探针 md5 不符：%s（应 %s）' % (got[:12], FROZEN_MD5[:12]))
    F = _load(FROZEN, 'frozen19e')
    print('  ① 19e_probe_multi.py md5 %s ✓' % got[:12])
    got2 = hashlib.md5(io.open(EXTRA, 'rb').read()).hexdigest()
    if got2 != EXTRA_MD5:
        raise SystemExit('!! p1d_prompts.json md5 不符：%s（应 %s）' % (got2[:12], EXTRA_MD5[:12]))
    E = json.loads(io.open(EXTRA, encoding='utf-8').read())
    print('  ② p1d_prompts.json   md5 %s ✓（新增臂 %s）' % (got2[:12], sorted(E['arms'])))
    return F, E


def to_circles(src, arm):
    """泛化的对象名词适配器：只改第一个句号之前的对象短语，句号之后逐字节不变。"""
    head, sep, tail = src.partition('。')
    if not sep:
        raise SystemExit('!! 臂 %r 的提示词没有句号分隔，结构不符' % arm)
    new_head = head.replace(OBJ_OLD, OBJ_NEW)
    if new_head == head:
        raise SystemExit('!! 臂 %r 未能替换对象短语（冻结件可能已变）：%r' % (arm, head[:60]))
    out = new_head + sep + tail
    if out[-len(tail) - 1:] != sep + tail:
        raise SystemExit('!! 臂 %r 句号之后被动过 —— 拒绝运行' % arm)
    return out


def crosscheck(F, E, base_people):
    """④ 交叉自检：对 19e 里的 base/permit，本件泛化适配器 == p1_probe.circle_prompts()（逐字节）。

    远端 `/root/p1_probe.py` 若不存在则跳过（但会打印跳过原因，不静默）。
    """
    pp = os.path.join(os.path.dirname(FROZEN), 'p1_probe.py')
    if not os.path.exists(pp):
        print('  ④ 交叉自检：跳过（未找到 %s）' % pp)
        return
    try:
        P = _load(pp, 'p1probe')
        ref = P.circle_prompts(F)
    except Exception as ex:
        print('  ④ 交叉自检：跳过（导入 p1_probe 失败：%s）' % str(ex)[:80])
        return
    bad = 0
    for arm in ('base', 'permit'):
        if arm not in base_people:
            continue
        mine = to_circles(base_people[arm], arm)
        if mine != ref[arm]:
            bad += 1
            print('  !! 交叉自检失败 [%s]\n     mine=%r\n     ref =%r' % (arm, mine, ref[arm]))
    print('  ④ 交叉自检：base/permit 与 p1_probe.circle_prompts() %s'
          % ('逐字节相同 ✓' if bad == 0 else '**不一致（%d 处）**' % bad))
    if bad:
        raise SystemExit('!! 泛化适配器改变了已发表臂的措辞 —— 拒绝运行')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--grid', required=True)
    ap.add_argument('--family', required=True)
    ap.add_argument('--arm', required=True)
    ap.add_argument('--model', required=True)
    ap.add_argument('--api', default='http://127.0.0.1:8000/v1/chat/completions')
    ap.add_argument('--outd', default='/root/p1d_results')
    ap.add_argument('--workers', type=int, default=8)
    ap.add_argument('--limit', type=int, default=0)
    ap.add_argument('--only-sigma', type=float, default=None)
    ap.add_argument('--tag', default='')
    ap.add_argument('--show-prompts', action='store_true')
    A = ap.parse_args()

    F, E = load_frozen()
    people = dict(F.P)
    people.update(E['arms'])
    if A.arm not in people:
        raise SystemExit('!! 臂 %r 不在合并后的提示词表里（可选 %s）' % (A.arm, sorted(people)))
    crosscheck(F, E, F.P)
    PROMPT = to_circles(people[A.arm], A.arm)
    if A.show_prompts:
        print('  [%s] 人版：%s' % (A.arm, people[A.arm]))
        print('  [%s] 圆点：%s' % (A.arm, PROMPT))
        print('  句号之后逐字相同：%s' % (PROMPT.partition('。')[2] == people[A.arm].partition('。')[2]))
        return 0

    F.API = A.api
    from PIL import Image
    mf = os.path.join(A.grid, 'manifest.csv')
    mf_md5 = hashlib.md5(io.open(mf, 'rb').read()).hexdigest()
    print('  ③ 网格 manifest md5 %s（%d 字节）' % (mf_md5[:12], os.path.getsize(mf)))
    rows = list(csv.DictReader(io.open(mf, encoding='utf-8')))
    if A.only_sigma is not None:
        rows = [r for r in rows if abs(float(r['sigma']) - A.only_sigma) < 1e-9]
    if A.limit:
        rows = rows[:A.limit]
    os.makedirs(A.outd, exist_ok=True)
    outp = os.path.join(A.outd, 'p1d%s_%s_%s.csv' % (('_' + A.tag) if A.tag else '', A.family, A.arm))
    done = set()
    if os.path.exists(outp):
        with io.open(outp, encoding='utf-8-sig', newline='') as f:
            done = {r['item'] for r in csv.DictReader(f)}
    todo = [r for r in rows if r['item'] not in done]
    print('  [%s/%s%s] 网格 %d / 已完成 %d / 本次 %d ｜ model=%s'
          % (A.family, A.arm, ('/' + A.tag) if A.tag else '', len(rows), len(done), len(todo), A.model))
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
                b64 = F.b64_of(im, quality=95)
                raw = F.call_img(b64, PROMPT, A.model)
                v = F.parse(raw)
                ok = 1 if v is not None else 0
                z = 1 if (isinstance(v, int) and v == 0) else 0
                low = (raw or '').lower()
                ab = 1 if any(k in low for k in ABSTAIN_MARK) else 0
            except Exception as e:
                raw, v, ok = 'ERR:%s' % str(e)[:300], None, 0
            with lock:
                w.writerow([r['item'], r['n'], r['r'], r['sigma'], r['gt'],
                            '' if v is None else v, ok, z, ab, raw, '%.2f' % (time.time() - t0)])
                fh.flush()
                st['n'] += 1
                st['z'] += z
                st['ab'] += ab
                st['pf'] += (1 - ok)
                if st['n'] % 200 == 0:
                    print('    %d/%d  %.2f it/s  zero=%d abstain=%d parse_fail=%d'
                          % (st['n'], len(todo), st['n'] / max(time.time() - st['t0'], 1e-9),
                             st['z'], st['ab'], st['pf']), flush=True)

    ts = [threading.Thread(target=work, daemon=True) for _ in range(max(1, A.workers))]
    [t.start() for t in ts]
    [t.join() for t in ts]
    fh.close()
    print('  [%s/%s] DONE：%d 行 → %s（zero=%d abstain=%d parse_fail=%d）'
          % (A.family, A.arm, st['n'], outp, st['z'], st['ab'], st['pf']))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
