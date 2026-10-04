#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""a52_probe.py —— A5-2 采集器：**冻结提示词 + 冻结解析器 + 自带可逆性/唯一性自检**。

════════════════════════════════════════════════════════════════════════════
同源声明（★ A5-2 的对象是**合成圆点**，本件与既有 675 张网格**同源**）
════════════════════════════════════════════════════════════════════════════
* 刺激与 `/root/p1_grid/`（675 张，p1_prep_grid.py 生成）**同源**：同画布 1024、同配色、
  同抖动规则、同 GaussianBlur、同 PNG 落盘；A5-2 只加了四因子与 8 布局。
* 提示词与 G.2 的**三个合同臂 + 合成圆点网格**做法一致：拿冻结的人版合同，
  **只把对象短语整段换掉**（`人数（人群中的每个人头或人体）` →
  `圆形数量（画面中的每一个圆点）`，该短语在冻结文本里恰好出现一次），**其余逐字节不变**。
  本件把这条写成了**可逆性 + 唯一性断言**（见 selfcheck 的 ②③），不通过即拒绝运行。
  ★ 注意：base 臂的第一个分句用 `，` 收尾（不是 `。`）——所以自检**不能**靠"第一个句号切分"
  这种脆弱假设（首版就是这么写的，被自检当场拦下）；现在改成按对象短语切分。
* 解析器照抄冻结 `19e_probe_multi.py` 的 `parse()`（md5 03edb14c98ffa3aea9ffa20f59b00bc8），
  包括"允许键带引号/反引号"那个 round-4 修法；能直接吃 `{"count": 7}` 类 JSON。
  本件**不 import 远端冻结件**（本地自测要能离线跑），故把该 `parse()` 逐字复制过来，
  并用 12 条语法用例把它钉在**行为**上（见 PARSER_CASES）。

契约 3 档（文本逐字冻结在 `_a52_criteria_frozen.json` 的 `prompts_frozen`）：
    base   请数出图片中的圆形数量（画面中的每一个圆点），不要遗漏，不要重复，以JSON格式输出：{"count": 数量}，只输出JSON。
    strict 请数出图片中的圆形数量（画面中的每一个圆点）。只输出JSON，不要输出任何其他文字。不要遗漏，不要重复，以JSON格式输出：{"count": 数量}，只输出JSON。
    permit 请数出图片中的圆形数量（画面中的每一个圆点）。如果你无法逐个确证，请回答 abstain，而不要猜测。以JSON格式输出：{"count": 数量} 或 {"count": "abstain"}，只输出JSON。

用法：
    python3 a52_probe.py --api http://127.0.0.1:8013/v1/chat/completions \\
        --model Qwen3-VL-32B-Instruct-AWQ --grid /root/a52/stim --manifest /root/a52/stim/manifest.csv \\
        --build b0 --served-model Qwen3-VL-32B-Instruct-AWQ --contract base --start 1 \\
        --out /root/a52/res/A52_b0_base_s1.csv --workers 4
    python3 a52_probe.py --selftest           # 只跑自检（离线、不碰网络、不碰 GPU）
    python3 a52_probe.py --show-prompts       # 打印三档提示词 md5 与可逆性断言结果

输出列（一行 = 一图）：
    item,cell_id,layout_id,count_gt,n_dots_detected_gt,radius,blur,overlap,build,served_model,
    contract,start,pred,parse_ok,abstain,refuse,http_err,model,raw,latency_s
    （radius/blur/overlap = 刺激的**真参数**，从 manifest 抄过来，供分析器的四因子模型直接用；
      raw **完整保存不截断**：独立复算要走它复现解析）
"""
import argparse
import base64
import csv
import hashlib
import io
import json
import os
import queue
import re
import sys
import threading
import time
import urllib.error
import urllib.request

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

COLS = ['item', 'cell_id', 'layout_id', 'count_gt', 'n_dots_detected_gt', 'radius', 'blur',
        'overlap', 'build', 'served_model', 'contract', 'start', 'pred', 'parse_ok', 'abstain',
        'refuse', 'http_err', 'model', 'raw', 'latency_s']

# ── 冻结来源（只作 md5/出处记录；本件不 import，保证离线可跑、口径靠行为用例钉住）──────
FROZEN_SRC = '/root/19e_probe_multi.py'
FROZEN_SRC_MD5 = '03edb14c98ffa3aea9ffa20f59b00bc8'
OBJ_OLD = '人数（人群中的每个人头或人体）'
OBJ_NEW = '圆形数量（画面中的每一个圆点）'
# 冻结的人版（19e_probe_multi.py 的 P 字典，逐字；只取本实验用到的两档）
PEOPLE_BASE = ('请数出图片中的人数（人群中的每个人头或人体），不要遗漏，不要重复，'
               '以JSON格式输出：{"count": 数量}，只输出JSON。')
PEOPLE_PERMIT = ('请数出图片中的人数（人群中的每个人头或人体）。如果你无法逐个确证，'
                 '请回答 abstain，而不要猜测。以JSON格式输出：{"count": 数量} 或 '
                 '{"count": "abstain"}，只输出JSON。')
STRICT_SENTENCE = '只输出JSON，不要输出任何其他文字。'
# 弃答标记：与 p1_probe.py / p1d_probe.py 逐字相同的表，保证两套产物可比
ABSTAIN_MARK = ('abstain', 'cannot', "can't", 'unable', 'too many', '无法', '不能', '数不清',
                '难以', '不确定', '无法判断', '众多')

# ── 冻结解析器的 12 条行为用例（期望：int / 'abstain' / 'cannot_judge' / None）──────────
PARSER_CASES = [
    ('{"count": 7}', 7),
    ('{"count":"7"}', 7),
    ('{ "count" : 7 }', 7),
    ('{"count": "abstain"}', 'abstain'),
    ('{"count": 0}', 0),
    ('{"count": 1,234}', 1),                 # 冻结正则不跨逗号：数字停在 1（旧行为，保留）
    ('{"response": "cannot_judge"}', 'cannot_judge'),
    ('{"response": "no_people"}', 'no_people'),
    ('图中大约有 12 个圆点。', 12),           # 兜底支：文中第一个整数
    ('No JSON here, I cannot count them.', None),
    ('', None),
    ('{"foo": 3}', 3),                        # 键不在词表里 ⇒ 兜底支取第一个整数
]


def parse(raw):
    """冻结解析器（照抄 19e_probe_multi.parse，含允许键带引号/反引号的 round-4 修法）。

    命中 `{"count"|"response"|计数|数量|人数 : <数字|abstain|cannot_judge|no_people>}` 即返回；
    否则兜底取文中第一个整数；都没有 ⇒ None。
    """
    m = re.search(r'\{\s*["\'`]?\s*(?:count|response|计数|数量|人数)\s*["\'`]?\s*[:：=]\s*["\'`]?\s*'
                  r'(\d+|abstain|cannot_judge|no_people)', raw or '', re.I)
    if m:
        v = m.group(1)
        return int(v) if v.isdigit() else v
    m = re.search(r'-?\d+', (raw or '').replace(',', ''))
    return int(m.group(0)) if m else None


def to_circles(src):
    """人版 → 圆点版：把**恰好一次**出现的对象短语整段换掉，其余**逐字节不动**。

    返回 (新文本, prov)；prov 拆出 pre / sep / suffix 以便核对"唯一差异就是对象短语"。
    替换必须**唯一**（恰好 1 处）且**可逆**（换回去必须逐字复原）——不成立即抛错。
    """
    if src.count(OBJ_OLD) != 1:
        raise AssertionError('对象短语在冻结人版里出现 %d 次（要求恰好 1 次）⇒ 替换不唯一'
                             % src.count(OBJ_OLD))
    pre, rest = src.split(OBJ_OLD, 1)
    sep = rest[:1]                     # 紧随对象短语的那个分隔符（base 为 '，'，permit 为 '。'）
    suffix = rest[1:]
    out = pre + OBJ_NEW + sep + suffix
    if out.replace(OBJ_NEW, OBJ_OLD) != src:
        raise AssertionError('替换不可逆：把新短语换回去不能逐字复原冻结人版')
    return out, {'pre': pre, 'sep': sep, 'suffix': suffix}


def build_prompts():
    """→ ({'base','strict','permit'}, prov)。

    机制（**不靠"第一个句号"这种脆弱假设**）：冻结人版里对象短语
    `人数（人群中的每个人头或人体）` 出现**恰好一次**；把它整段换成圆点短语，其余**逐字不动**。
    圆点版（= 判据件 prompts_frozen 的文本，逐字复核）：

        base   请数出图片中的圆形数量（画面中的每一个圆点），不要遗漏，不要重复，以JSON格式输出：{"count": 数量}，只输出JSON。
        strict 请数出图片中的圆形数量（画面中的每一个圆点）。只输出JSON，不要输出任何其他文字。以JSON格式输出：{"count": 数量}，只输出JSON。
        permit 请数出图片中的圆形数量（画面中的每一个圆点）。如果你无法逐个确证，请回答 abstain，而不要猜测。以JSON格式输出：{"count": 数量} 或 {"count": "abstain"}，只输出JSON。

    strict 由 **base** 派生：在"对象短语 + 分隔符"之后、JSON 指令之前插入冻结插句
    `只输出JSON，不要输出任何其他文字。`（base 的分隔符是 `，`，strict 改用 `。`）。
    """
    base, prov_b = to_circles(PEOPLE_BASE)
    permit, prov_p = to_circles(PEOPLE_PERMIT)
    pre = prov_b['pre']
    sep_strict = '。'
    strict = pre + OBJ_NEW + sep_strict + STRICT_SENTENCE + prov_b['suffix']
    prov = {'pre': pre, 'obj': OBJ_NEW, 'base_sep': prov_b['sep'], 'base_suffix': prov_b['suffix'],
            'permit_sep': prov_p['sep'], 'permit_suffix': prov_p['suffix'],
            'strict_sep': sep_strict, 'strict_insert': STRICT_SENTENCE}
    return {'base': base, 'strict': strict, 'permit': permit}, prov


def selfcheck(verbose=True):
    """可逆性/唯一性/语法自检。任何一条不过 ⇒ 返回非 0（探针拒绝运行）。"""
    bad = 0
    prompts, tails = build_prompts()
    if verbose:
        print('  ① 提示词（由冻结人版机械派生，对象=%s）' % OBJ_NEW)
        for k in ('base', 'strict', 'permit'):
            print('     %-6s md5 %s  len %d' % (k, hashlib.md5(prompts[k].encode()).hexdigest()[:12],
                                                len(prompts[k])))
    # ② 对象替换的**唯一差异**：三档的"对象短语之前"前缀必须逐字相同；base/permit 的
    #    后缀必须恰好等于冻结人版去头之后的后缀；strict = 前缀 + 对象短语 + '。' + 插句 + base 后缀。
    if not (tails['pre'] == prompts['base'].split(OBJ_NEW, 1)[0]
            == prompts['permit'].split(OBJ_NEW, 1)[0]
            == prompts['strict'].split(OBJ_NEW, 1)[0]):
        print('  ✗ ② 三档的"对象短语之前"前缀不完全相同（替换污染了别处）')
        bad += 1
    if prompts['base'] != tails['pre'] + OBJ_NEW + tails['base_sep'] + tails['base_suffix']:
        print('  ✗ ② base 无法由"人版去头换名"复原')
        bad += 1
    if prompts['permit'] != tails['pre'] + OBJ_NEW + tails['permit_sep'] + tails['permit_suffix']:
        print('  ✗ ② permit 无法由"人版去头换名"复原')
        bad += 1
    if prompts['strict'] != tails['pre'] + OBJ_NEW + tails['strict_sep'] + STRICT_SENTENCE + tails['base_suffix']:
        print('  ✗ ② strict != 前缀 + 对象短语 + 插句 + base 后缀')
        bad += 1
    if verbose:
        print('  ② 唯一差异 = 对象短语：三档前缀逐字相同 = True ｜ base 分隔符 %r ｜ permit 分隔符 %r ｜ '
              'strict 由 base 派生（插句 %r）' % (tails['base_sep'], tails['permit_sep'], STRICT_SENTENCE))
    # ③ 每个提示词里对象短语恰好 1 次，且不含人版旧短语
    for k, v in prompts.items():
        if v.count(OBJ_NEW) != 1 or OBJ_OLD in v:
            print('  ✗ ③ %s 的对象短语计数异常（new=%d, old=%d）' % (k, v.count(OBJ_NEW), v.count(OBJ_OLD)))
            bad += 1
    if verbose:
        print('  ③ 唯一性：三档各含 %r 恰好 1 次、均不含人版短语 ✓' % OBJ_NEW)
    # ④ 解析器行为 12 条
    nfail = 0
    for src, want in PARSER_CASES:
        got = parse(src)
        if got != want:
            nfail += 1
            print('  ✗ ④ 解析用例失败：%r → %r（期望 %r）' % (src, got, want))
    if nfail:
        bad += 1
    if verbose:
        print('  ④ 解析器行为用例 %d/%d 通过' % (len(PARSER_CASES) - nfail, len(PARSER_CASES)))
    # ⑤ 弃答/拒答标记与解析器语义一致（abstain 能被标记到）
    if not any(k in 'abstain' for k in ABSTAIN_MARK):
        print('  ✗ ⑤ 弃答标记表不含 abstain')
        bad += 1
    if verbose:
        print('  ⑤ 弃答标记 %d 个（abstain/cannot/无法/数不清…）✓' % len(ABSTAIN_MARK))
    # ⑥ 与判据件冻结文本比对（若判据件在同目录）
    cp = os.path.join(os.path.dirname(os.path.abspath(__file__)), '_a52_criteria_frozen.json')
    if os.path.exists(cp):
        try:
            fr = json.loads(io.open(cp, encoding='utf-8').read())['prompts_frozen']
            for k in ('base', 'strict', 'permit'):
                if fr.get(k) != prompts[k]:
                    print('  ✗ ⑥ %s 与判据件冻结文本不一致\n     探针=%r\n     判据=%r' % (k, prompts[k], fr.get(k)))
                    bad += 1
            print('  ⑥ 与 _a52_criteria_frozen.json 的三档提示词逐字一致 = %s'
                  % all(fr.get(k) == prompts[k] for k in ('base', 'strict', 'permit')))
        except Exception as ex:
            print('  ✗ ⑥ 读判据件失败：%s' % str(ex)[:120])
            bad += 1
    else:
        print('  ⑥ 判据件不在同目录 ⇒ 跳过文本比对（%s）' % cp)
    print('  自检结论：%s' % ('★ 通过（可逆/唯一/语法/判据一致）' if bad == 0 else '✗ 有 %d 项不通过 ⇒ 拒绝运行' % bad))
    return bad


def call_img(b64, prompt, model, api, ak='dummy', timeout=180, retries=5, max_tokens=128):
    """与冻结 19e.call_img 同构（temperature 0 / max_tokens 128 / 5 次退避重试）。"""
    payload = {'model': model, 'messages': [{'role': 'user', 'content': [
        {'type': 'image_url', 'image_url': {'url': 'data:image/jpeg;base64,' + b64}},
        {'type': 'text', 'text': prompt}]}], 'temperature': 0.0, 'max_tokens': max_tokens}
    req = urllib.request.Request(api, data=json.dumps(payload).encode(),
                                 headers={'Content-Type': 'application/json',
                                          'Authorization': 'Bearer ' + ak})
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


def b64_of(im, quality=95):
    """与冻结 b64_of 同构（JPEG quality=95；PNG 源图 → JPEG 编码，与 p1 口径一致）。"""
    buf = io.BytesIO()
    im.save(buf, 'JPEG', quality=quality)
    return base64.b64encode(buf.getvalue()).decode()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--api', default='http://127.0.0.1:8013/v1/chat/completions')
    ap.add_argument('--api-key', default='dummy')
    ap.add_argument('--model', default='', help='请求体里的 model（通常=--served-model）')
    ap.add_argument('--served-model', default='', help='落进 CSV 的 served-model 名（核验用）')
    ap.add_argument('--grid', required=False, help='刺激目录（含 images/ 与 manifest.csv）')
    ap.add_argument('--manifest', required=False, help='默认 <grid>/manifest.csv')
    ap.add_argument('--items', default='', help='只跑这些 item（逗号分隔 layout_id）；空=全 648')
    ap.add_argument('--build', default='b0')
    ap.add_argument('--contract', default='base', choices=('base', 'strict', 'permit'))
    ap.add_argument('--start', default='1')
    ap.add_argument('--out', default='', help='逐格 CSV；空则用 --outd + A52_<build>_<contract>_s<start>.csv')
    ap.add_argument('--outd', default='/root/a52/res')
    ap.add_argument('--workers', type=int, default=4)
    ap.add_argument('--limit', type=int, default=0)
    ap.add_argument('--dry', action='store_true', help='不调 API，用 ground truth 造 raw（自测用）')
    ap.add_argument('--selftest', action='store_true')
    ap.add_argument('--show-prompts', action='store_true')
    A = ap.parse_args()

    if A.selftest or A.show_prompts:
        print('== a52_probe 自检 ==')
        return 0 if selfcheck() == 0 else 3

    model = A.model or A.served_model
    if not model:
        if A.dry:
            model = 'DRY'
        else:
            print('!! 必须给 --model 或 --served-model')
            return 2
    print('== A5-2 采集 ==')
    if selfcheck(verbose=False) != 0:
        print('!! 自检不通过 ⇒ 拒绝运行')
        return 3
    prompts, _ = build_prompts()
    PROMPT = prompts[A.contract]
    print('  探针自检 ✓ ｜ 冻结来源 %s（md5 %s，仅记录）' % (FROZEN_SRC, FROZEN_SRC_MD5[:12]))
    print('  build=%s ｜ served-model=%s ｜ contract=%s ｜ start=%s ｜ workers=%d'
          % (A.build, A.served_model or model, A.contract, A.start, A.workers))
    print('  prompt md5 = %s' % hashlib.md5(PROMPT.encode()).hexdigest())

    mf = A.manifest or os.path.join(A.grid or '', 'manifest.csv')
    if not os.path.exists(mf):
        print('!! 找不到 manifest：%s' % mf)
        return 2
    mf_md5 = hashlib.md5(io.open(mf, 'rb').read()).hexdigest()
    grid = A.grid or os.path.dirname(os.path.abspath(mf))
    rows = list(csv.DictReader(io.open(mf, encoding='utf-8-sig', newline='')))
    print('  manifest md5 %s ｜ %d 行' % (mf_md5[:12], len(rows)))
    if A.items:
        want = {x.strip() for x in A.items.split(',') if x.strip()}
        rows = [r for r in rows if r['layout_id'] in want]
    if A.limit:
        rows = rows[:A.limit]
    outp = A.out or os.path.join(A.outd, 'A52_%s_%s_s%s.csv' % (A.build, A.contract, A.start))
    os.makedirs(os.path.dirname(os.path.abspath(outp)), exist_ok=True)
    done = set()
    if os.path.exists(outp):
        with io.open(outp, encoding='utf-8-sig', newline='') as f:
            done = {r['item'] for r in csv.DictReader(f)}
    todo = [r for r in rows if r['layout_id'] not in done]
    print('  本格 %d 行 / 已完成 %d / 本次 %d ｜ out=%s' % (len(rows), len(done), len(todo), outp))
    if not todo:
        print('  已完成，跳过（可重入）')
        return 0
    if A.dry:
        print('  --dry：不调 API，用 ground truth 造 raw')

    q = queue.Queue()
    for r in todo:
        q.put(r)
    lock = threading.Lock()
    newf = not os.path.exists(outp)
    fh = io.open(outp, 'a', newline='', encoding='utf-8')
    w = csv.writer(fh, lineterminator='\n')
    if newf:
        w.writerow(COLS)
    st = {'n': 0, 't0': time.time(), 'pf': 0, 'he': 0, 'ab': 0, 'ok': 0}
    from PIL import Image

    def work():
        while True:
            try:
                r = q.get_nowait()
            except queue.Empty:
                return
            t0 = time.time()
            raw, v, ok, ab, rf, he = '', None, 0, 0, 0, 0
            try:
                if A.dry:
                    gt = int(r['count_gt'])
                    raw = json.dumps({'count': gt if int(r['layout_id'][-2:]) % 4 else gt + 1})
                    v = parse(raw)
                else:
                    rel = r.get('img') or r.get('path') or ('images/%s.png' % r['layout_id'])
                    im = Image.open(os.path.join(grid, rel)).convert('RGB')
                    raw = call_img(b64_of(im), PROMPT, model, A.api, A.api_key)
                    v = parse(raw)
                ok = 1 if v is not None else 0
                low = (raw or '').lower()
                ab = 1 if any(k in low for k in ABSTAIN_MARK) else 0
                rf = 1 if any(k in low for k in ('cannot_judge', 'no_people')) else 0
            except Exception as e:
                raw, v, ok, he = 'ERR:%s' % str(e)[:400], None, 0, 1
            with lock:
                w.writerow([r['layout_id'], r['cell_id'], r['layout_id'], r['count_gt'],
                            r['n_dots_detected_gt'], r.get('radius', ''), r.get('blur', ''),
                            r.get('overlap', ''), A.build, A.served_model or model, A.contract,
                            A.start, '' if v is None else v, ok, ab, rf, he, model, raw,
                            '%.2f' % (time.time() - t0)])
                fh.flush()
                st['n'] += 1
                st['ok'] += ok
                st['pf'] += (1 - ok)
                st['he'] += he
                st['ab'] += ab
                if st['n'] % 200 == 0:
                    print('    %d/%d  %.2f it/s  parse_ok=%d http_err=%d abstain=%d'
                          % (st['n'], len(todo), st['n'] / max(time.time() - st['t0'], 1e-9),
                             st['ok'], st['he'], st['ab']), flush=True)

    ts = [threading.Thread(target=work, daemon=True) for _ in range(max(1, A.workers))]
    [t.start() for t in ts]
    [t.join() for t in ts]
    fh.close()
    n = sum(1 for _ in csv.DictReader(io.open(outp, encoding='utf-8-sig', newline='')))
    print('  DONE：本格 %d 行（累计 %d 行，parse_ok=%d http_err=%d abstain=%d）→ %s'
          % (st['n'], n, st['ok'], st['he'], st['ab'], outp))
    print('A52_PROBE_DONE %s %s s%s rows=%d' % (A.build, A.contract, A.start, n))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
