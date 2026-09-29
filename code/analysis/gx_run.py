#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""gx_run.py — 收官批的运行器（G8b / placebo / g10mix 三件事共用一个）。

冻结判据：/root/gx_criteria_frozen.json（启动时断言 md5；提示词逐字比对）。
仪器：`19f_probe_ablation.py`（md5 28e82b20a7f468680da11b2e9855cff9）由 importlib 载入，
      `parse()` / `b64_of()` / `call_img()` 逐字复用；英文句取自 `20b_probe_lang.py`
      （md5 77385964ee28d6bf26b8a2a3dcca1975）。

用法：PORT=8013 TASK=g8b MODEL=Qwen3-VL-32B-Instruct python3 gx_run.py
任务：g8b ｜ placebo ｜ g10mix
"""
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

PROBE = '/root/19f_probe_ablation.py'
PROBE_MD5 = '28e82b20a7f468680da11b2e9855cff9'
LANG = '/root/20b_probe_lang.py'
LANG_MD5 = '77385964ee28d6bf26b8a2a3dcca1975'
CRIT = '/root/gx_criteria_frozen.json'
CRIT_MD5 = '129005a8a7c1326519c3f63260cbb3ae'
PORT = os.environ.get('PORT', '8013')
TASK = os.environ.get('TASK', 'g8b')
MODEL = os.environ.get('MODEL', 'Qwen3-VL-32B-Instruct')
OUT = '/root/gx_res'
DR = '/root/dense_results'
IMGDIR = {'st_a': '/root/dense/shanghaitech/images/part_A_test',
          'visdrone': '/root/aerial/visdrone/images',
          'aitod': '/root/aerial/aitod/images',
          'ucf': '/root/dense/ucf_qnrf/UCF-QNRF_ECCV18/Test'}
Z0 = '/root/z0/images'
WORKERS = int(os.environ.get('WORKERS', '8'))
os.makedirs(OUT, exist_ok=True)
os.environ.setdefault('BAILIAN_API', 'http://127.0.0.1:%s/v1/chat/completions' % PORT)
os.environ.setdefault('DASHSCOPE_API_KEY', 'EMPTY')


def load(path, want):
    got = hashlib.md5(open(path, 'rb').read()).hexdigest()
    assert got == want, '%s md5 不符：%s' % (path, got)
    spec = importlib.util.spec_from_file_location(os.path.basename(path)[:-3], path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def published(ds):
    """已发表的头条格逐项记录：返回 [(item, path, gt)]，item 名与图名对齐。"""
    p = os.path.join(DR, 'vlm_%s_base_whole.csv' % ds)
    out = []
    for r in csv.DictReader(io.open(p, encoding='utf-8-sig')):
        it = r['item'].strip()
        cand = None
        for ext in ('.jpg', '.jpeg', '.png', '.JPG', ''):
            c = os.path.join(IMGDIR[ds], it + ext)
            if os.path.exists(c):
                cand = c
                break
        if cand is None:
            continue
        out.append((it, cand, int(float(r['gt']))))
    return out


def z0_items(n_easy=50, n_hard=50):
    out = []
    for tag, n in (('z0easy', n_easy), ('z0hard', n_hard)):
        fs = sorted(f for f in os.listdir(Z0) if f.startswith(tag))
        for f in fs[:n]:
            out.append(('%s/%s' % (tag, f), os.path.join(Z0, f), 0))
    return out


def build_jobs(M, J):
    if TASK == 'g8b':
        jobs = []
        for ds in ('st_a', 'visdrone', 'aitod'):
            for it, p, g in published(ds):
                jobs.append((ds, it, p, g, 'en:base'))
                jobs.append((ds, it, p, g, 'cn:base'))
        return jobs, ['en:base', 'cn:base']
    if TASK == 'placebo':
        fs = sorted(f for f in os.listdir(IMGDIR['st_a']) if f.lower().endswith('.jpg'))[:150]
        gt = {i: g for i, _p, g in published('st_a')}
        return [('st_a', f, os.path.join(IMGDIR['st_a'], f), gt.get(f, 0), a)
                for f in fs for a in ('p5', 'p50', 'p100', 'p800')], ['p5', 'p50', 'p100', 'p800']
    if TASK == 'g10mix':
        z = z0_items()
        nz = [(i, p, g) for i, p, g in published('st_a')][:400]
        mixed, zi, ni = [], 0, 0
        # 交错规则事先写死：每 5 项插 1 个真零
        while zi < len(z) or ni < len(nz):
            for _ in range(5):
                if ni < len(nz):
                    mixed.append(('mixed', nz[ni][0], nz[ni][1], nz[ni][2], 'base')); ni += 1
            if zi < len(z):
                mixed.append(('mixed', z[zi][0], z[zi][1], z[zi][2], 'base')); zi += 1
        sep = [('sep_zero', i, p, g, 'base') for i, p, g in z]
        sep += [('sep_nonzero', i, p, g, 'base') for i, p, g in nz]
        return mixed + sep, ['base']
    raise SystemExit('unknown TASK %s' % TASK)


def main():
    M = load(PROBE, PROBE_MD5)
    L = load(LANG, LANG_MD5)
    b = open(CRIT, 'rb').read()
    got = hashlib.md5(b).hexdigest()
    assert got == CRIT_MD5, '冻结件 md5 变了：%s != %s' % (got, CRIT_MD5)
    J = json.loads(b.decode('utf-8'))
    for a, p in J['placebo']['prompts_verbatim'].items():
        assert M.P['base'] in p and str(a[1:]) in p, 'placebo 臂 %s 与冻结件不符' % a
    assert J['G8b']['prompts_verbatim']['en:base'] == L.EN['base']
    assert J['G8b']['prompts_verbatim']['cn:base'] == M.P['base']
    print('[gx/%s] 冻结件 md5 OK：%s ｜ model=%s port=%s' % (TASK, got, MODEL, PORT), flush=True)

    def prompt_of(arm):
        # ★ 2026-09-27 修：g10mix 用的是朴素臂名 ，旧写法一律落到 placebo 字典 ⇒ KeyError 'base'，
        #   实测把 g10mix 的 564×2 行**全部**写成 ERR 'base'（unparsed=564）。这里按前缀分派。
        if arm.startswith('en:'):
            return L.EN[arm.split(':')[1]]
        if arm.startswith('cn:'):
            return M.P[arm.split(':')[1]]
        if arm.startswith('p') and arm[1:].isdigit():
            return J['placebo']['prompts_verbatim'][arm]
        return M.P[arm]

    jobs, arms = build_jobs(M, J)
    out_csv = os.path.join(OUT, 'gx_%s_%s.csv' % (TASK, MODEL.replace('/', '_')))
    done = set()
    if os.path.exists(out_csv):
        for r in csv.DictReader(open(out_csv, encoding='utf-8-sig')):
            if (r.get('http_err') or '0') == '0' and (r.get('raw') or '') != '':
                done.add((r['list'], r['item'], r['arm']))
    jobs = [j for j in jobs if (j[0], j[1], j[4]) not in done]
    new = not os.path.exists(out_csv) or os.path.getsize(out_csv) == 0
    fh = open(out_csv, 'a', encoding='utf-8-sig', newline='')
    wr = csv.writer(fh)
    if new:
        wr.writerow(['model', 'task', 'list', 'item', 'arm', 'gt', 'pred', 'parse_ok',
                     'http_err', 'raw'])
    print('[gx/%s] 待跑 %d 项（已完成 %d）' % (TASK, len(jobs), len(done)), flush=True)
    if not jobs:
        fh.close(); return
    q = queue.Queue()
    for j in jobs:
        q.put(j)
    st = {'n': 0, 'tot': len(jobs), 't0': time.time(), 'bad': 0, 'e': 0}
    lk = threading.Lock()
    from PIL import Image

    def work():
        while True:
            try:
                lst, it, path, g, arm = q.get_nowait()
            except queue.Empty:
                return
            pred, ok, err, raw = None, 0, 0, ''
            try:
                im = Image.open(path).convert('RGB')
                raw = M.call_img(M.b64_of(im), prompt_of(arm), MODEL)
                pred = M.parse(raw)
                ok = 1 if pred is not None else 0
            except Exception as ex:
                raw = 'ERR %s' % str(ex)[:160]
                if '400' in str(ex)[:60]:
                    err = 1
            with lk:
                wr.writerow([MODEL, TASK, lst, it, arm, g, '' if pred is None else pred, ok,
                             err, raw.replace('\n', ' ')[:300]])
                fh.flush()
                st['n'] += 1; st['bad'] += 0 if ok else 1; st['e'] += err
                if st['n'] % 200 == 0:
                    el = max(time.time() - st['t0'], 1e-9)
                    print('  %d/%d (%.2f/s bad=%d err=%d)' % (st['n'], st['tot'], st['n'] / el,
                                                              st['bad'], st['e']), flush=True)

    th = [threading.Thread(target=work, daemon=True) for _ in range(WORKERS)]
    for t in th:
        t.start()
    for t in th:
        t.join()
    fh.close()
    print('[gx/%s] DONE n=%d unparsed=%d err=%d' % (TASK, st['n'], st['bad'], st['e']), flush=True)


if __name__ == '__main__':
    main()
