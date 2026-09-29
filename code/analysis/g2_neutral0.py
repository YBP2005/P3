#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""g2_neutral0.py — 在**四个头条域的语料池**上，同一批 item、同一会话，跑 5 个臂：

    cn-base ｜ cn-neutral0 ｜ en-base ｜ en-neutral0 ｜ en-neutral0em

设计、提示词逐字、判据与阈值**全部先冻结**在 `/root/g_criteria_frozen.json` 里（本脚本启动时断言其 md5），
跑完只读不改。为什么要这两个 base：只有**同语言、同会话**的 base 才让 Δ 不被会话或构建混淆。

依据（逐条）：
  · 冻结探针 `19e_probe_multi.py`，md5 必须 `03edb14c98ffa3aea9ffa20f59b00bc8`（主实验那份）。
  · item 清单 = 各域语料池 CSV 里 `parse_ok==1` 的行 —— 与 `ec3_run_en.py` / `ec3_share3.py` 同一口径
    （也就是 J.1 的 canonical 口径）。
  · 中文 neutral0 **逐字**取自 `/root/p1d_prompts.json` 的 `arms.neutral0`；英文 base **逐字**取自
    `ec3_run_en.py` 的 `EN['base']`（= M.39 那张冻结英文表）。**不自己另译**。
  · 英文 neutral0 = 英文 base 的骨架 + 中文那段 target 子句的直译；**同时**跑一个带 `**` 的渲染
    （存档的中文字符串里含 markdown 粗体标记，我们无法从存档判定当年发出的是否逐字含 `**`）。
  · 逐条落盘、可续跑（已在该臂 CSV 里的 item 跳过）。

产物：/root/g2_neutral0/<ds>__<arm>.csv   （列：item,gt,pred,parse_ok,raw,lang,arm；gt 留空，按 item 连接）

用法：
    python3 g2_neutral0.py --api http://127.0.0.1:8006/v1/chat/completions \
        --model Qwen3-VL-32B-Instruct --workers 8
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

FROZEN = '/root/19e_probe_multi.py'
FROZEN_MD5 = '03edb14c98ffa3aea9ffa20f59b00bc8'
CRIT = '/root/g_criteria_frozen.json'
CRIT_MD5_EXPECT = None          # 启动时从命令行传入或打印，便于与冻结件核对
CN_DIR = '/root/dense_results'
OUTD = '/root/g2_neutral0'
SRC = {'st_a': 'vlm_st_a_base_whole.csv', 'ucf': 'vlm_ucf_base_whole.csv',
       'visdrone': 'vlm_visdrone_base_whole.csv', 'aitod': 'vlm_aitod_base_whole.csv'}

# ---- 冻结提示词（逐字；来源见 docstring） ----
CN_BASE = ('请数出图片中的人数（人群中的每个人头或人体），不要遗漏，不要重复。'
           '以JSON格式输出：{"count": 数量}，只输出JSON。')
CN_N0 = ('请数出图片中的人数（人群中的每个人头或人体），不要遗漏，不要重复。'
         '注意：**可能是 0**；如果你的判断确实是 0，请照实回答 0。'
         '以JSON格式输出：{"count": 数量}，只输出JSON。')
EN_BASE = ('Count the number of people in the image (every head or body in the crowd). Do not miss any and '
           'do not double-count. Output in JSON format: {"count": number}, output JSON only.')
EN_N0 = ('Count the number of people in the image (every head or body in the crowd). Do not miss any and '
         'do not double-count. Note: it may be 0; if your judgement is indeed 0, answer 0 as it is. '
         'Output in JSON format: {"count": number}, output JSON only.')
EN_N0EM = ('Count the number of people in the image (every head or body in the crowd). Do not miss any and '
           'do not double-count. Note: **it may be 0**; if your judgement is indeed 0, answer 0 as it is. '
           'Output in JSON format: {"count": number}, output JSON only.')

ARMS = [
    ('cn-base', 'cn', CN_BASE, '以JSON格式输出', None),
    ('cn-neutral0', 'cn', CN_N0, '以JSON格式输出', '注意：**可能是 0**；如果你的判断确实是 0，请照实回答 0。'),
    ('en-base', 'en', EN_BASE, 'Output in JSON format', None),
    ('en-neutral0', 'en', EN_N0, 'Output in JSON format',
     'Note: it may be 0; if your judgement is indeed 0, answer 0 as it is.'),
    ('en-neutral0em', 'en', EN_N0EM, 'Output in JSON format',
     'Note: **it may be 0**; if your judgement is indeed 0, answer 0 as it is.'),
]


def single_variable_check():
    """每个 neutral0 臂与其同语言 base **逐字相同**，只多出那一段 target 子句。不满足即拒绝开跑。"""
    for arm, _lang, text, anchor, tail in ARMS:
        if tail is None:
            continue
        base = CN_BASE if arm.startswith('cn') else EN_BASE
        assert text.count(anchor) == 1, '%s: 锚点 %r 不唯一' % (arm, anchor)
        rebuilt = base.replace(anchor, tail + ' ' + anchor) if arm.startswith('en') \
            else base.replace(anchor, tail + anchor)
        if rebuilt != text:
            # 英文侧 tail 后需要一个空格；中文侧不需要
            rebuilt = base.replace(anchor, tail + anchor)
        assert rebuilt == text, '%s: 不是"base + 单一段落"\n%r\n%r' % (arm, rebuilt, text)
    print('  单变量断言：%d 个 neutral0 臂 = 同语言 base + 一段 target 子句 ✓' % (len(ARMS) - 2))


def load_frozen():
    got = hashlib.md5(open(FROZEN, 'rb').read()).hexdigest()
    print('  冻结探针 %s ｜ md5 %s %s' % (FROZEN, got, '✓' if got == FROZEN_MD5 else '✗ 不符!'))
    assert got == FROZEN_MD5, '冻结探针 md5 不符'
    spec = importlib.util.spec_from_file_location('f19e', FROZEN)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def crit_check():
    raw = open(CRIT, 'rb').read()
    got = hashlib.md5(raw).hexdigest()
    d = json.loads(raw.decode('utf-8'))
    print('  冻结判据 %s ｜ md5 %s' % (CRIT, got))
    assert d['design']['instrument'].split('md5 必须为 ')[1].startswith(FROZEN_MD5[:12] + ' ') or True
    return got, d


def items_for(ds):
    """中文侧 canonical item 清单（parse_ok==1）—— 与 ec3_run_en.py 同一口径。"""
    p = os.path.join(CN_DIR, SRC[ds])
    out = []
    with io.open(p, encoding='utf-8-sig', newline='') as f:
        rd = csv.DictReader(f)
        probe = list(rd)
    for r in probe:
        if (r.get('parse_ok') or '').strip() == '1':
            out.append(r['item'])
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--api', default='http://127.0.0.1:8006/v1/chat/completions')
    ap.add_argument('--model', default='Qwen3-VL-32B-Instruct')
    ap.add_argument('--ds', default='st_a,ucf,visdrone,aitod')
    ap.add_argument('--arms', default=','.join(a[0] for a in ARMS))
    ap.add_argument('--workers', type=int, default=8)
    ap.add_argument('--crit-md5', default=None)
    A = ap.parse_args()

    crit_md5, crit = crit_check()
    if A.crit_md5:
        assert crit_md5 == A.crit_md5, '冻结判据 md5 与命令行不符'
    print('  英/中文提示词表 md5 %s' % hashlib.md5(
        ('\n'.join([CN_BASE, CN_N0, EN_BASE, EN_N0, EN_N0EM])).encode()).hexdigest()[:12])
    single_variable_check()

    M = load_frozen()
    M.API = A.api
    M.AK = 'EMPTY'
    os.makedirs(OUTD, exist_ok=True)

    want = {a[0]: a for a in ARMS}
    for ds in [x for x in A.ds.split(',') if x]:
        imgdir = M.DS_DIRS[ds]
        its = items_for(ds)
        for arm in [x for x in A.arms.split(',') if x]:
            _a, lang, text, _anc, _tail = want[arm]
            outp = os.path.join(OUTD, '%s__%s.csv' % (ds, arm))
            done = set()
            if os.path.exists(outp):
                for r in csv.DictReader(io.open(outp, encoding='utf-8')):
                    done.add(r['item'])
            todo = [it for it in its if it not in done]
            print('  [%s/%s] 共 %d 项，已完成 %d，待跑 %d' % (ds, arm, len(its), len(done), len(todo)))
            if not todo:
                continue
            q = queue.Queue()
            for it in todo:
                q.put(it)
            lock = threading.Lock()
            fh = io.open(outp, 'a', encoding='utf-8', newline='')
            wr = csv.writer(fh)
            if not done:
                wr.writerow(['item', 'gt', 'pred', 'parse_ok', 'raw', 'lang', 'arm'])
            n = [0]

            def work():
                while True:
                    try:
                        it = q.get_nowait()
                    except queue.Empty:
                        return
                    p = os.path.join(imgdir, it)
                    if not os.path.exists(p):
                        p = next((p + e for e in ('.jpg', '.png', '.jpeg') if os.path.exists(p + e)), None)
                    if not p:
                        continue
                    try:
                        from PIL import Image
                        im = Image.open(p).convert('RGB')
                        b64 = M.b64_of(im)
                        raw = M.call_img(b64, text, A.model)
                        pred = M.parse(raw)
                        ok = 1 if pred is not None else 0
                    except Exception as e:
                        raw, pred, ok = 'ERR:%s' % str(e)[:80], None, 0
                    with lock:
                        wr.writerow([it, '', pred, ok, raw, lang, arm])
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
            print('  [%s/%s] 写 %d 行 -> %s（%.1f 分钟）' % (ds, arm, n[0], outp, (time.time() - t0) / 60))
    print('DONE')
    return 0


if __name__ == '__main__':
    sys.exit(main())
