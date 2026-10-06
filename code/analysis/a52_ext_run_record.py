#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""a52_ext_run_record.py — 合成数值刺激实验**第三构建（FP8）**扩展的**机器可读运行记录**。

它只做两件事：**从放行件里派生**、**把派生结果写成一份 JSON**。所有数字都由以下实物算出，
没有一个是手写的（本项目纪律：数字能算就不要抄）：

  ① `data/derived/a5_2_a800/A52_b0_<contract>_s<k>.csv`（既有 18 格）＋
     `data/derived/a52_ext/res/A52_b1_<contract>_s<k>.csv`（本轮 9 格）—— 27 个逐 item 记录；
     逐格行数、`parse_ok`、`http_err`、零格、单请求时延分位、按 count 档/按构建的**答对率**，
     全部用**随包分析器**里的同一个响应定义（`a52_analyze.py::is_correct`，TOL_ABS=1 / TOL_REL=0.05）重算。
  ② `data/derived/a52_ext/analysis/a52_b1.runner.log` —— 编排器全日志（起服次数、每次收服后
     显存是否回 0、总墙钟）。
  ③ `data/derived/a52_ext/b1_analysis_pooled.json` —— 冻结的池化分析（27 格 / 17,496 行）；
     它的判据件摘要与逐项交互系数原样读入（并记录其 md5）。
  ④ `--recompute` 时另跑**随包分析器**（`data/derived/a5_2_a800/env/a52_analyze.py`）一次，
     把同一批 27 个放行件按"主口径 = 整格排除 / 对照 = 含排除格"重算，并与上面③并列登记。
     ★ 两套读数并列是**如实披露**，不是替换：③ 是 2026-10-06 那次实跑（主机上的分析器副本，
     未含 v0646 的两处更正），④ 是随包副本（含更正）。

用法（在包根或作者树跑都行；包根自动识别）：

    python a52_ext_run_record.py --root <package root> [--out <file>] [--recompute]

默认输出 `<root>/data/derived/a52_ext/a52_ext_run_record_20261006.json` 并写同名 `.md5` 旁车。
本脚本**纯 CPU / 不联网 / 不启服务**。
"""
import argparse
import collections
import csv
import datetime
import hashlib
import io
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
HERE = os.path.dirname(os.path.abspath(__file__))
REL_EXT = os.path.join('data', 'derived', 'a52_ext')
REL_A800 = os.path.join('data', 'derived', 'a5_2_a800')


def md5f(p):
    h = hashlib.md5()
    with io.open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def find_root(explicit=''):
    """包根 = 含 MANIFEST.csv 与 data/derived/ 的那一层。"""
    cands = []
    if explicit:
        cands.append(explicit)
    env = os.environ.get('PAPERB_ROOT')
    if env:
        cands += [env, os.path.join(env, 'repro_github')]
    d = HERE
    for _ in range(6):
        cands.append(d)
        cands.append(os.path.join(d, 'repro_github'))
        d = os.path.dirname(d)
    for c in cands:
        if c and os.path.exists(os.path.join(c, 'MANIFEST.csv')) and os.path.isdir(os.path.join(c, 'data')):
            return os.path.abspath(c)
    sys.exit('!! 找不到包根（含 MANIFEST.csv 与 data/）：用 --root 指定')


def respfn(root):
    """响应定义直接 import 随包分析器，避免第二套实现。"""
    sys.dont_write_bytecode = True      # ★ 不在放行树里留下 __pycache__/*.pyc
    p = os.path.join(root, REL_A800, 'env', 'a52_analyze.py')
    if not os.path.exists(p):
        sys.exit('!! 缺随包分析器：%s' % p)
    import importlib.util
    spec = importlib.util.spec_from_file_location('_a52_frozen_analyzer', p)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m, md5f(p)


def pctl(v, q):
    v = sorted(v)
    i = min(len(v) - 1, max(0, int(math.ceil(q * len(v))) - 1))
    return v[i]


def facts_from_csvs(root):
    d0 = os.path.join(root, REL_A800)
    d1 = os.path.join(root, REL_EXT, 'res')
    files = []
    for d in (d0, d1):
        files += [os.path.join(d, f) for f in sorted(os.listdir(d))
                  if f.startswith('A52_') and f.endswith('.csv')]
    if len(files) != 27:
        sys.exit('!! 期望 27 个逐格 CSV，实得 %d（b0/b2 在 %s，b1 在 %s）' % (len(files), d0, d1))
    az, az_md5 = respfn(root)
    per_build = collections.defaultdict(lambda: dict(
        cells=0, calls=0, parse_ok=0, http_err=0, zero_cells=0, lat=[], bands={},
        abstain=0, refuse=0, rows_per_cell={}))
    src = {}
    for p in files:
        b = os.path.basename(p).split('_')[1]
        ct = os.path.basename(p).split('_')[2]
        st = os.path.basename(p).split('_')[3].split('.')[0]
        src['%s/%s/%s' % (b, ct, st)] = md5f(p)
        nb = collections.Counter()
        lat_rows = []
        with io.open(p, encoding='utf-8', newline='') as fh:
            for r in csv.DictReader(fh):
                nb['rows'] += 1
                if str(r.get('parse_ok')).strip() not in ('1', '1.0'):
                    nb['parse_bad'] += 1
                if str(r.get('http_err')).strip() not in ('0', '0.0', ''):
                    nb['http'] += 1
                if str(r.get('abstain')).strip() not in ('0', '0.0', ''):
                    nb['abstain'] += 1
                if str(r.get('refuse')).strip() not in ('0', '0.0', ''):
                    nb['refuse'] += 1
                try:
                    lat_rows.append(float(r['latency_s']))
                except (KeyError, ValueError):
                    pass
                c = int(r['count_gt'])
                ok = az.is_correct(r)
                band = per_build[b]['bands'].setdefault(str(c), {'correct': 0, 'n': 0})
                band['correct'] += ok
                band['n'] += 1
        per_build[b]['cells'] += 1
        per_build[b]['calls'] += nb['rows']
        per_build[b]['parse_ok'] += nb['rows'] - nb['parse_bad']
        per_build[b]['http_err'] += nb['http']
        per_build[b]['abstain'] += nb['abstain']
        per_build[b]['refuse'] += nb['refuse']
        per_build[b]['zero_cells'] += 1 if nb['rows'] == 0 else 0
        per_build[b]['lat'] += lat_rows
        per_build[b]['rows_per_cell']['%s/%s' % (ct, st)] = nb['rows']
    out = {}
    for b, v in sorted(per_build.items()):
        lat = v['lat']
        bands = {}
        for c, bd in sorted(v['bands'].items(), key=lambda kv: int(kv[0])):
            bands[c] = {'correct': bd['correct'], 'n': bd['n'],
                        'rate': round(100.0 * bd['correct'] / bd['n'], 4)}
        out[b] = {
            'cells': v['cells'], 'calls': v['calls'],
            'rows_per_cell_min': min(v['rows_per_cell'].values()),
            'rows_per_cell_max': max(v['rows_per_cell'].values()),
            'parse_ok': v['parse_ok'], 'parse_ok_pct': round(100.0 * v['parse_ok'] / v['calls'], 6),
            'http_err': v['http_err'], 'zero_cells': v['zero_cells'],
            'abstain': v['abstain'], 'refuse': v['refuse'],
            'latency_s': {'mean': round(sum(lat) / len(lat), 4), 'p50': round(pctl(lat, 0.5), 4),
                          'p90': round(pctl(lat, 0.9), 4), 'min': round(min(lat), 4),
                          'max': round(max(lat), 4)},
            'correct_by_count': bands}
    return out, src, az_md5, files


LOG_PAT = {
    'cells_done': re.compile(r'完成格数 = (\d+) / (\d+)'),
    'ready': re.compile(r'起服就绪（等待 (\d+)s）'),
    'gpu_zero': re.compile(r'已收服；GPU 现 = (\d+), (\d+) MiB'),
    'ts': re.compile(r'^\[(\d{4}-\d{2}-\d{2}_\d{2}:\d{2}:\d{2})\]', re.M),
}


def facts_from_log(root):
    p = os.path.join(root, REL_EXT, 'analysis', 'a52_b1.runner.log')
    if not os.path.exists(p):
        sys.exit('!! 缺编排器日志：%s' % p)
    s = io.open(p, encoding='utf-8', errors='replace').read()
    ts = LOG_PAT['ts'].findall(s)
    fmt = '%Y-%m-%d_%H:%M:%S'
    t0 = datetime.datetime.strptime(ts[0], fmt)
    t1 = datetime.datetime.strptime(ts[-1], fmt)
    wall = (t1 - t0).total_seconds()
    cd = LOG_PAT['cells_done'].search(s)
    rig = LOG_PAT['ready'].findall(s)
    gz = LOG_PAT['gpu_zero'].findall(s)
    return {
        'log': os.path.join(REL_EXT, 'analysis', 'a52_b1.runner.log').replace(os.sep, '/'),
        'log_md5': md5f(p),
        'first_timestamp': ts[0], 'last_timestamp': ts[-1],
        'wall_clock_s': wall,
        'wall_clock_hms': '%d min %d s' % (wall // 60, wall % 60),
        'gpu_hours': round(wall / 3600.0, 4),
        'cells_done': (int(cd.group(1)), int(cd.group(2))) if cd else None,
        'service_starts': len(rig),
        'gpu_back_to_zero_after_each_start': len(gz) == len(rig) and len(rig) > 0,
        'gpu_zero_readings_mib': [int(a) for a, _b in gz],
    }


def facts_from_pooled(root):
    p = os.path.join(root, REL_EXT, 'b1_analysis_pooled.json')
    if not os.path.exists(p):
        sys.exit('!! 缺冻结池化分析：%s' % p)
    j = json.loads(io.open(p, encoding='utf-8').read())
    c3 = j['checks']['C3_model']
    c5 = j['checks']['C5_cv']
    nc3 = j['checks']['NC3_parse_recompute']
    return {
        'json': os.path.join(REL_EXT, 'b1_analysis_pooled.json').replace(os.sep, '/'),
        'json_md5': md5f(p),
        'criteria_md5_printed': j.get('criteria_md5'),
        'pool_rows': j.get('n_rows'), 'pool_files': j.get('n_files'),
        'C3': {'passed': bool(j['verdicts']['C3']['passed']),
               'beta_count': c3['beta_count'], 'se': c3['se_count'], 'ci': c3['ci'],
               'interactions': {k: {'beta': v['beta'], 'p_wald': v['p_wald']}
                                for k, v in sorted(c3['interactions'].items())}},
        'C4': {'passed': bool(j['verdicts']['C4']['passed']), 'band': j['verdicts']['C4']['band'],
               'ci': j['verdicts']['C4']['ci'],
               'cluster_bootstrap_ci': j['verdicts']['C4']['cluster_bootstrap']['ci'],
               'disposition_zh': j['verdicts']['C4']['disposition']},
        'C5': {'passed': bool(j['verdicts']['C5']['passed']),
               'sign_consistency': c5['stability']['sign_consistency'],
               'folds': [round(f['beta_count'], 4) for f in c5['per_fold']],
               'median': round(c5['stability']['median'], 4)},
        'NC3': {'passed': bool(j['verdicts']['NC3']['passed']),
                'checked': nc3['checked'], 'mismatch': nc3['mismatch']},
    }


def recompute_with_shipped(root):
    """用**随包**分析器把同一批 27 个放行件重算一遍（主口径 / 对照口径）。"""
    az = os.path.join(root, REL_A800, 'env', 'a52_analyze.py')
    stim = os.path.join(root, 'data', 'derived', 'a5_2_stim')
    tmp = tempfile.mkdtemp(prefix='a52_rec_')
    try:
        pool = os.path.join(tmp, 'pooled')
        os.makedirs(pool)
        n = 0
        for d in (os.path.join(root, REL_A800), os.path.join(root, REL_EXT, 'res')):
            for f in sorted(os.listdir(d)):
                if f.startswith('A52_') and f.endswith('.csv'):
                    shutil.copy2(os.path.join(d, f), os.path.join(pool, f))
                    n += 1
        if n != 27:
            sys.exit('!! 重算池应有 27 个 CSV，实得 %d' % n)
        outp = os.path.join(tmp, 'out.json')
        cmd = [sys.executable, '-B', az, '--dir', pool]
        if os.path.isdir(stim):
            cmd += ['--stim', stim]
        cmd += ['--out', outp]
        r = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace',
                           env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'))
        if r.returncode or not os.path.exists(outp):
            sys.exit('!! 随包分析器重算失败（退出码 %s）：\n%s' % (r.returncode, (r.stdout or '')[-800:]))
        j = json.loads(io.open(outp, encoding='utf-8').read())
        c3 = j['checks']['C3_model']
        c3x = j['checks'].get('C3_model_including_excluded_cells', {})
        c5 = j['checks']['C5_cv']
        return {
            'analyzer': os.path.join(REL_A800, 'env', 'a52_analyze.py').replace(os.sep, '/'),
            'analyzer_md5': md5f(az),
            'caliber_primary': j.get('caliber', {}).get('primary'),
            'caliber_contrast': j.get('caliber', {}).get('contrast'),
            'primary': {'n_rows': j['verdicts']['C3'].get('n_rows'),
                        'beta_count': c3['beta_count'], 'se': c3['se_count'], 'ci': c3['ci'],
                        'interactions': {k: {'beta': v['beta'], 'p_wald': v['p_wald']}
                                         for k, v in sorted(c3['interactions'].items())}},
            'contrast': {'beta_count': c3x.get('beta_count'), 'se': c3x.get('se_count'),
                         'ci': c3x.get('ci'),
                         'interactions': {k: {'beta': v['beta'], 'p_wald': v['p_wald']}
                                          for k, v in sorted(c3x.get('interactions', {}).items())}},
            'C4_primary_passed': bool(j['verdicts']['C4']['passed']),
            'C5_sign_consistency': c5['stability']['sign_consistency'],
            'NC3_mismatch': j['verdicts']['NC3']['mismatch'],
            'NC3_checked': j['verdicts']['NC3']['checked'],
        }
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def facts_from_smoke(root):
    """冒烟件（workers=4 / n=24，每构建一次起服）的 P50 —— 与逐格记录同源放行。"""
    out = {}
    for tag, f in (('b0', 'b0_smoke_summary.json'), ('b1', 'b1_smoke_summary.json')):
        p = os.path.join(root, REL_EXT, f)
        if not os.path.exists(p):
            continue
        j = json.loads(io.open(p, encoding='utf-8').read())
        out[tag] = {'file': os.path.join(REL_EXT, f).replace(os.sep, '/'), 'md5': md5f(p),
                    'protocol': 'workers=%s, n=%s' % (j.get('workers'), j['conc']['n']),
                    'p50_s': j['conc']['p50'], 'p90_s': j['conc']['p90'],
                    'http_err': j['conc']['http_err']}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', default='')
    ap.add_argument('--out', default='')
    ap.add_argument('--recompute', action='store_true')
    A = ap.parse_args()
    root = find_root(A.root)
    out = A.out or os.path.join(root, REL_EXT, 'a52_ext_run_record_20261006.json')
    print('包根 = %s' % root)
    builds, src, az_md5, files = facts_from_csvs(root)
    log = facts_from_log(root)
    pooled = facts_from_pooled(root)
    smoke = facts_from_smoke(root)
    _b0p = smoke.get('b0', {}).get('p50_s')
    _b1p = smoke.get('b1', {}).get('p50_s')
    _b2p = builds.get('b2', {}).get('latency_s', {}).get('p50')
    _smoke_cmp = {'protocol': 'workers = 4, n = 24, one service start per build',
                  'source_files': [v['file'] for _k, v in sorted(smoke.items())],
                  'p50_s': {k: v['p50_s'] for k, v in sorted(smoke.items())},
                  'p50_s_b2_from_frozen_full_run': _b2p}
    if _b0p and _b1p:
        _smoke_cmp['slower_than_b0_pct_exact'] = round(100.0 * (_b1p / _b0p - 1.0), 2)
        _smoke_cmp['slower_than_b0_pct_rounded_pair'] = round(100.0 * (2.03 / 1.82 - 1.0), 2)
    if _b2p and _b1p:
        _smoke_cmp['slower_than_b2_pct_exact'] = round(100.0 * (_b1p / _b2p - 1.0), 2)
        _smoke_cmp['slower_than_b2_pct_rounded_pair'] = round(100.0 * (2.03 / 1.71 - 1.0), 2)
    rec = {
        'record': 'synthetic-dot count x legibility experiment: third build (FP8) extension',
        'record_version': 1,
        'scope': {
            'builds': {'b0': 'AWQ 4-bit (community requantisation)',
                       'b1': 'FP8 (official FP8 checkpoint, W8A16 dequantisation on this host)',
                       'b2': 'BF16 (hosted API)'},
            'contracts': ['base', 'strict', 'permit'],
            'service_starts_per_build': 3,
            'items_per_cell': 648,
            'note': 'every number below is derived from the released per-item records / logs; '
                    'no value is hand-typed',
        },
        'response_definition': {
            'source': os.path.join(REL_A800, 'env', 'a52_analyze.py').replace(os.sep, '/'),
            'md5': az_md5,
            'rule': 'correct = pred is an integer and |pred - n_dots_detected_gt| <= '
                    'max(1, 0.05 * n_dots_detected_gt); abstain / refuse / parse failure / '
                    'http error count as incorrect',
        },
        'per_item_records': {'n_files': len(files), 'n_rows': sum(v['calls'] for v in builds.values()),
                             'md5': src},
        'by_build': builds,
        'b1_run_facts': log,
        'frozen_pooled_analysis_as_run': pooled,
        'disclosures': {
            'fp8_not_faster_on_this_host': {
                'statement': 'On this Ampere part (compute capability 8.0) the FP8 build is not '
                             'faster: W8A8 needs 8.9, so the loader takes the weight-only (W8A16) '
                             'path and dequantises. The comparison this section licenses is about '
                             'numerical-format robustness, not about speed.',
                'matched_smoke_protocol': _smoke_cmp,
                'frozen_full_run_p50_s': {b: builds[b]['latency_s']['p50'] for b in sorted(builds)},
            },
            'second_four_bit_build_not_producible': {
                'statement': 'No usable second 4-bit implementation could be produced in this '
                             'environment (vLLM 0.29.0 + compressed-tensors 0.17.0); changing the '
                             'shared library versions is a hard constraint.',
                'routes': {
                    'bitsandbytes_NF4': 'vLLM 0.29.0 has no bitsandbytes quantization method and no '
                                        'bitsandbytes_loader module, so a quantised artifact could not '
                                        'be served',
                    'llmcompressor_oneshot': 'the version-matched llmcompressor declares '
                                             'transformers <= 5.10.1 while the shared environment has '
                                             '5.17.0 (GraniteMoeParallelExperts removed) => ImportError',
                    'in_house_RTN_INT4': 'structure mirrored the working AWQ artifact and vLLM loaded '
                                         'it, but the packing round-trip was wrong (ModelCompressor '
                                         'relative error ~1.07) and the 4B smoke run degenerated '
                                         '(128 completion tokens, repeated token) => stopped by the '
                                         'pre-registered "degenerate => stop" rule',
                },
                'probe_scripts': [os.path.join('code', 'analysis', 'a52_ext_rtn_quant.py').replace(os.sep, '/'),
                                  os.path.join('code', 'analysis', 'a52_ext_verify_rtn.py').replace(os.sep, '/'),
                                  os.path.join('code', 'analysis', 'a52_ext_verify_ctl.py').replace(os.sep, '/')],
            },
            'fp8_download_facts': {
                'repository': 'Qwen/Qwen3-VL-32B-Instruct-FP8',
                'revision': '4bf2c2f39c37c0fede78bede4056e1f18cdf8109',
                'files': 18, 'bytes': 35532290088,
                'per_file_sha256_matched_hf_lfs': '18/18',
                'declared_files_before_the_run': 19,
                'correction': 'the pre-run declaration in the download script (line 21) said 19 '
                              'files; the measured count is 18 (off by one)',
            },
        },
    }
    if A.recompute:
        rec['shipped_analyzer_recomputation'] = recompute_with_shipped(root)
    buf = json.dumps(rec, ensure_ascii=False, indent=1, sort_keys=True) + '\n'
    io.open(out, 'w', encoding='utf-8', newline='\n').write(buf)
    h = md5f(out)
    io.open(out + '.md5', 'w', encoding='utf-8', newline='\n').write(
        '%s  %s\n' % (h, os.path.basename(out)))
    print('已写 %s（%d 字节，md5 %s）' % (out, len(buf.encode('utf-8')), h[:12]))
    print('旁车 %s.md5' % out)
    return 0


if __name__ == '__main__':
    sys.exit(main())
