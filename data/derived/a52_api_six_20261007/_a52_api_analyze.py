# -*- coding: utf-8 -*-
"""_a52_api_analyze.py —— A5-2 **API 臂**（6 个 API 模型）分析驱动。

★ 口径纪律：**不另创口径**。所有判据量都从冻结件 `_a52_criteria_frozen.json`
  （md5 758962a2643e1035698682abefec5748）与冻结分析器 `_a5_2/a52_analyze.py`
  里**直接 import 复用**：

    correct   = a52_analyze.is_correct      （|pred − n_dots_detected_gt| ≤ max(1, 0.05·gt)）
    Wilson CI = a52_analyze.wilson
    IRLS      = a52_analyze.fit_logit       （logistic，Wald SE = (X'WX)^-1）
    β 定义    = criteria.C3.standardization：count_std 先 z 标准化 ⇒ β_std = β̂_count
                95% CI（Wald）= β̂ ± 1.96·SE
    C4        = criteria.C4：CI 完全落在 ±0.2 内 ⇒ 可称"无实质作用"
    C5        = criteria.C5：以 layout 为组 8 折留出，同源变体同折

  与冻结分析器的**唯一**必要差异（已在报告里声明）：
    本地臂的 `build` 因子（b0/b1/b2/b3）在 API 臂里对应 6 个 API 模型。
    · 逐模型拟合 ⇒ 去掉模型项（与 `a52_ext_b1_analyze.py` 的 build-free 补充口径
      **同一模型形式**，该口径已在 2026-10-06 的 A800 报告里被采用）；
    · 池化拟合 ⇒ 用 `model` 哑变量替代 `build` 哑变量（参考档 gpt-6.1-sol），
      并按冻结顺序报 ① count 主效应 ② count×合同 ③ count×模型。

只读输入、只写本目录的 5 个新产物（+ 本脚本）。不联网、不启服务、不跑 GPU。
"""
import argparse
import collections
import csv
import hashlib
import importlib.util
import io
import json
import math
import os
import random
import re
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
try:
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

# ══════════════════════ 路径与导入（★ v0669 A8-3/M-6）══════════════════════
# ★ 旧写法把运行布局**写死**成作者工作树：
#     HERE = 本脚本所在；WS = 上一级；A52 = WS/_a5_2；sys.path.insert(0, A52); import a52_analyze
#   放行树上本脚本位于 `data/derived/a52_api_six_20261007/`，`WS/_a5_2` **不存在** ⇒
#   **ModuleNotFoundError: No module named 'a52_analyze'**；即便把 import 修好，
#   `load_baseline()` 的 `os.listdir(WS/_a5_2/_a800_a52/res)` 仍会 FileNotFoundError。
#   现在改为**显式候选路径 + 按文件路径导入 + 缺件即停**，两种布局都跑得通、且与 CWD 无关：
#     release 布局 = 放行树：所有输入与冻结分析器都是本脚本的**同级件**；
#     author  布局 = `_a52_api_work/`：输入在 `..\_p3_api_results_20261007\`、
#                  分析器在 `..\_a5_2\a52_analyze.py`、本地臂在 `..\_a5_2\_a800_a52{,_ext}\`。
#   ★ 判据与算术**一字未改**：只改"路径怎么找到"。
HERE = os.path.dirname(os.path.abspath(__file__))
WS = os.path.dirname(HERE)


def _need(tag, cands, kind='file'):
    for c in cands:
        if kind == 'dir' and os.path.isdir(c):
            return c
        if kind == 'file' and os.path.isfile(c):
            return c
    sys.stderr.write('_a52_api_analyze: FAIL — 找不到 %s（%s）；候选：\n  %s\n'
                     % (tag, kind, '\n  '.join(str(c) for c in cands)))
    raise SystemExit(3)


# 冻结分析器：放行树里改名 `_a52_analyze_frozen.py`（与作者侧 `_a5_2/a52_analyze.py` **同字节**，
# md5 bf873c5e7da083dae42cb379efe9af9d）。按**文件路径**导入，不再依赖 sys.path 猜测。
_ANALYZER = _need('冻结分析器（a52_analyze）', [
    os.path.join(HERE, '_a52_analyze_frozen.py'),
    os.path.join(WS, '_a5_2', 'a52_analyze.py'),
])
_spec = importlib.util.spec_from_file_location('a52_analyze', _ANALYZER)
A = importlib.util.module_from_spec(_spec)                  # noqa: E402  冻结分析器
sys.modules['a52_analyze'] = A
_spec.loader.exec_module(A)

# 交付/输入目录：放行树上就是本脚本所在；作者树上是上一级的 `_p3_api_results_20261007`。
_DELIV = [HERE, os.path.join(WS, '_p3_api_results_20261007')]
MERGED = _need('merged_best.jsonl', [os.path.join(d, 'merged_best.jsonl') for d in _DELIV])
CRIT = _need('_a52_criteria_frozen.json', [os.path.join(d, '_a52_criteria_frozen.json') for d in _DELIV])
DMAT = _need('detection_matrix.csv', [os.path.join(d, 'detection_matrix.csv') for d in _DELIV])
MANIFEST = _need('a52__stim__manifest.csv（md5 d2dde2a8…，与源包一致）', [
    os.path.join(HERE, 'a52__stim__manifest.csv'),
    os.path.join(WS, '_a5_2', '_a800_a52_ext', 'a52__stim__manifest.csv'),
])
BASE_RES = _need('本地臂 b0/b2 的 18 格目录', [                       # b0 / b2 的 18 格
    os.path.join(HERE, 'local_arm', 'res'),
    os.path.join(WS, '_a5_2', '_a800_a52', 'res'),
], kind='dir')
BASE_EXT = _need('本地臂 b1 的 9 格目录', [                           # b1 的 9 格
    os.path.join(HERE, 'local_arm', 'ext'),
    os.path.join(WS, '_a5_2', '_a800_a52_ext'),
], kind='dir')
# 交付目录（3 张表）与原始转储目录：默认沿用作者树行为；`--out` / `--raw-out` 可覆盖。
OUT = os.path.dirname(MERGED)
RAWD = HERE
LAYOUTS = ['L%02d' % i for i in range(8)]
BAND = 0.2
BOOT_B = 500
BOOT_SEED = 20261004
K_FOLDS = 8
SPOT_N = 20
SPOT_SEED = 20261007
API_MODELS = ['gpt-6.1-sol', 'grok-4.7', 'gemini-3.8-flash',
              'qwen3.8-max', 'qwen3.8-flash', 'glm-4.6v']
REF_MODEL = 'gpt-6.1-sol'                                  # 池化拟合的参考档（= 跑单里的首个模型）


# ══════════════════════ 冻结工具 ══════════════════════
def md5f(p):
    return hashlib.md5(io.open(p, 'rb').read()).hexdigest()


def parse_frozen(raw):
    """冻结解析器（criteria.prompts_frozen.parser）：先取键值对，否则兜底取第一个整数。"""
    m = re.search(r'\{\s*["\'`]?\s*(?:count|response|计数|数量|人数)\s*["\'`]?\s*[:：=]\s*["\'`]?\s*'
                  r'(\d+|abstain|cannot_judge|no_people)', raw or '', re.I)
    if m:
        v = m.group(1)
        return int(v) if v.isdigit() else v
    m = re.search(r'-?\d+', (raw or '').replace(',', ''))
    return int(m.group(0)) if m else None


def parse_indep(raw):
    """NC3 用的**另一套**独立复解析（与 a52_analyze.NC3 同思路、不同实现）。"""
    m = re.search(r'"count"\s*:\s*"?(abstain|\d+)"?', raw or '', re.I)
    v = m.group(1) if m else None
    if v is None:
        m2 = re.search(r'-?\d+', (raw or '').replace(',', ''))
        v = m2.group(0) if m2 else None
    if v is not None and str(v).lower() == 'abstain':
        v = 'abstain'
    return v


def wilson(k, n, z=1.96):
    return A.wilson(k, n, z)


def is_correct(pred, gt_detected):
    """冻结判据 C3 的响应定义（逐字复用 a52_analyze.is_correct）。"""
    return A.is_correct({'pred': '' if pred is None else str(pred),
                         'n_dots_detected_gt': str(gt_detected)})


def tol_of(gt):
    return max(A.TOL_ABS, A.TOL_REL * gt)


# ══════════════════════ 载入 ══════════════════════
def load_manifest():
    man = {}
    for r in csv.DictReader(io.open(MANIFEST, encoding='utf-8-sig', newline='')):
        man[r['layout_id']] = r
    return man


def load_dmatrix():
    out = {}
    for r in csv.DictReader(io.open(DMAT, encoding='utf-8-sig', newline='')):
        for L in LAYOUTS:
            out[r['cell_id'] + '_' + L] = int(r[L])
    return out


def load_api(man):
    """merged_best.jsonl → 冻结 schema 的 row 列表（一行 = 一格）。"""
    rows, missing = [], []
    for line in io.open(MERGED, encoding='utf-8'):
        line = line.strip()
        if not line:
            continue
        d = json.loads(line)
        m = man.get(d['item'])
        assert m is not None, d['item']
        r = {'key': d['key'], 'model': d['model'], 'contract': d['contract'],
             'rep': int(d['rep']), 'item': d['item'], 'cell_id': m['cell_id'],
             'layout_id': d['item'], 'count_gt': m['count_gt'],
             'n_dots_detected_gt': m['n_dots_detected_gt'],
             'radius': m['radius'], 'blur': m['blur'], 'overlap': m['overlap'],
             'build': d['model'],                       # ★ 冻结分析器的 build 槽位 = API 模型
             'http': d['http'], 'served': d.get('served'),
             'ptok': (d.get('usage') or {}).get('prompt_tokens'),
             'ctok': (d.get('usage') or {}).get('completion_tokens'),
             'finish': d.get('finish'), 'err': d.get('err'),
             'latency_s': d.get('latency_s'), 'ts': d.get('ts'),
             'att': d.get('att'), 'raw': d.get('raw')}
        if d['http'] != 200:
            r.update({'pred': None, 'parse_ok': 0, 'abstain': 0, 'cls': 'unserved'})
            missing.append(r)
        else:
            v = parse_frozen(r['raw'] or '')
            cls = 'int' if isinstance(v, int) else ('abstain' if v == 'abstain' else 'unparsed')
            r.update({'pred': v if isinstance(v, int) else None, 'cls': cls,
                      'parse_ok': 1 if cls in ('int', 'abstain') else 0,
                      'abstain': 1 if cls == 'abstain' else 0})
        r['correct'] = is_correct(r['pred'], int(r['n_dots_detected_gt']))
        rows.append(r)
    return rows, missing


def load_baseline():
    """本地三构建（b0/b1/b2）的同口径复算；返回 {build: [row,...]}。"""
    cells = collections.defaultdict(list)
    files = [(os.path.join(BASE_RES, f)) for f in sorted(os.listdir(BASE_RES))
             if f.startswith('A52_') and f.endswith('.csv')]
    files += [os.path.join(BASE_EXT, f) for f in sorted(os.listdir(BASE_EXT))
              if f.startswith('a52__res__A52_') and f.endswith('.csv')]
    for p in files:
        for r in csv.DictReader(io.open(p, encoding='utf-8-sig', newline='')):
            r['correct'] = A.is_correct(r)
            pv = A.inum(r.get('pred'))
            r['pred'] = pv if pv is not None else None
            r['cls'] = ('int' if pv is not None else
                        ('abstain' if str(r.get('abstain')) == '1' else 'unparsed'))
            cells[r['build']].append(r)
    return cells

# ══════════════════════ 设计矩阵（同冻结形式；模型项替代构建项）══════════════════════
def design_vec(r, mu, sd, use_model_terms, ref_model):
    c = float(r['count_gt'])
    cs = (c - mu) / sd if sd > 1e-12 else 0.0
    z = [1.0, cs]
    z.append(cs * (1.0 if r['contract'] == 'strict' else 0.0))
    z.append(cs * (1.0 if r['contract'] == 'permit' else 0.0))
    if use_model_terms:
        for m in API_MODELS:
            if m == ref_model:
                continue
            z.append(cs * (1.0 if r['model'] == m else 0.0))
    z.append(float(r['radius']))
    z.append(float(r['blur']))
    z.append(float(r['overlap']))
    z.append(1.0 if r['contract'] == 'strict' else 0.0)
    z.append(1.0 if r['contract'] == 'permit' else 0.0)
    if use_model_terms:
        for m in API_MODELS:
            if m == ref_model:
                continue
            z.append(1.0 if r['model'] == m else 0.0)
    return z


def design_names(use_model_terms, ref_model):
    nm = ['intercept', 'count_std', 'count_std_x_strict', 'count_std_x_permit']
    if use_model_terms:
        nm += ['count_std_x_%s' % m for m in API_MODELS if m != ref_model]
    nm += ['radius', 'blur', 'overlap', 'contract_strict', 'contract_permit']
    if use_model_terms:
        nm += ['model_%s' % m for m in API_MODELS if m != ref_model]
    return nm


def fit_rows(rows, use_model_terms=False, ref_model=REF_MODEL, label=''):
    """与冻结 C3 **同一模型形式**的 logistic 拟合；IRLS 直接调 a52_analyze.fit_logit。"""
    acts = [float(r['count_gt']) for r in rows]
    mu = sum(acts) / len(acts)
    sd = math.sqrt(sum((a - mu) ** 2 for a in acts) / len(acts)) if acts else 0.0
    names = design_names(use_model_terms, ref_model)
    out = {'label': label, 'n_rows': len(rows), 'count_mean': mu, 'count_sd': sd,
           'use_model_terms': use_model_terms, 'ref_model': ref_model if use_model_terms else None}
    if sd <= 1e-12:
        out.update({'rank_ok': True, 'degenerate_count': True, 'beta_count': 0.0,
                    'se_count': 0.0, 'ci': [0.0, 0.0], 'interactions': {}})
        return out
    X = [design_vec(r, mu, sd, use_model_terms, ref_model) for r in rows]
    y = [float(r['correct']) for r in rows]
    beta, cov, se, ok, nit = A.fit_logit(X, y)
    out['rank_ok'] = bool(ok)
    out['n_iter'] = int(nit)
    if not ok:
        out['note'] = '设计矩阵奇异/不收敛 ⇒ 不可评'
        return out
    i = names.index('count_std')
    out['beta_count'] = float(beta[i])
    out['se_count'] = float(se[i])
    out['ci'] = [out['beta_count'] - 1.96 * out['se_count'],
                 out['beta_count'] + 1.96 * out['se_count']]
    rate = sum(y) / float(len(y))
    out['outcome_rate'] = rate
    out['n_correct'] = int(sum(y))
    out['separation'] = bool(rate < 1e-3 or rate > 1 - 1e-3 or out['se_count'] > 10.0)
    out['ci_informative'] = not out['separation']
    out['interactions'] = {}
    for nm in names:
        if nm.startswith('count_std_x_'):
            j = names.index(nm)
            out['interactions'][nm] = {
                'beta': float(beta[j]), 'se': float(se[j]),
                'ci': [float(beta[j] - 1.96 * se[j]), float(beta[j] + 1.96 * se[j])],
                'p_wald': float(A._pwald(beta[j], se[j]))}
    out['nuisance'] = {k: float(beta[names.index(k)]) for k in ('radius', 'blur', 'overlap')}
    return out


def c4(ci, informative=True):
    if not informative or not ci:
        return None
    return bool(ci[0] > -BAND and ci[1] < BAND)


def cluster_bootstrap(rows, B=BOOT_B, seed=BOOT_SEED, use_model_terms=False,
                      ref_model=REF_MODEL):
    """按**布局**聚类的 bootstrap（复刻冻结分析器的做法；同布局的全部变体同进同出）。"""
    acts = [float(r['count_gt']) for r in rows]
    mu = sum(acts) / len(acts)
    sd = math.sqrt(sum((a - mu) ** 2 for a in acts) / len(acts))
    if sd <= 1e-12:
        return {'B': B, 'n_ok': 0, 'note': 'count 无方差'}
    xs = [design_vec(r, mu, sd, use_model_terms, ref_model) for r in rows]
    ys = [float(r['correct']) for r in rows]
    by = {}
    for i, r in enumerate(rows):
        by.setdefault(r['layout_id'], []).append(i)
    keys = sorted(by)
    rng = random.Random(seed)
    betas = []
    for _ in range(B):
        pick = []
        for _ in range(len(keys)):
            pick.extend(by[keys[rng.randrange(len(keys))]])
        beta, cov, se, ok, _ = A.fit_logit([xs[i] for i in pick], [ys[i] for i in pick], iters=25)
        betas.append(beta[1] if ok else None)
    ok_b = sorted(b for b in betas if b is not None)
    if not ok_b:
        return {'B': B, 'n_ok': 0}
    return {'B': B, 'n_ok': len(ok_b), 'seed': seed,
            'ci': [ok_b[int(0.025 * len(ok_b))], ok_b[min(len(ok_b) - 1, int(0.975 * len(ok_b)))]],
            'median': ok_b[len(ok_b) // 2],
            'note': '按布局聚类重抽（同布局全部变体同进同出）'}


def groupwise(rows, k=K_FOLDS, use_model_terms=False, ref_model=REF_MODEL):
    """C5：以 layout 为组 8 折留出（复刻冻结分析器的分折规则）。"""
    by = collections.defaultdict(list)
    for r in rows:
        by[r['layout_id']].append(r)
    keys = sorted(by)
    folds = collections.defaultdict(list)
    for i, kk in enumerate(keys):
        folds[i % k].append(kk)
    per = []
    for f in range(k):
        te = set(folds.get(f, []))
        tr = [r for kk in keys if kk not in te for r in by[kk]]
        if len(tr) < 20:
            continue
        res = fit_rows(tr, use_model_terms, ref_model)
        per.append({'fold': f, 'beta_count': res.get('beta_count'), 'rank_ok': res.get('rank_ok'),
                    'n_train': len(tr), 'n_test': sum(len(by[kk]) for kk in te)})
    bs = [p['beta_count'] for p in per if p.get('beta_count') is not None]
    st = {}
    if bs:
        srt = sorted(bs)
        med = srt[len(srt) // 2]
        mean = sum(bs) / len(bs)
        sdv = math.sqrt(sum((b - mean) ** 2 for b in bs) / len(bs))
        st = {'n_folds': len(bs), 'min': min(bs), 'max': max(bs), 'median': med, 'sd': sdv,
              'sign_consistency': sum(1 for b in bs if (b > 0) == (med > 0)) / float(len(bs))
              if med != 0 else 1.0,
              'unstable': bool(med != 0 and sdv > 0.5 * abs(med))}
    return {'k': k, 'assign_rule': 'layout_id 排序序号 mod k ⇒ 同布局的全部变体同折',
            'per_fold': per, 'stability': st}


# ══════════════════════ 表 1：逐档 ══════════════════════
def bands(rows):
    out = {}
    for c in sorted({int(r['count_gt']) for r in rows}):
        b = [r for r in rows if int(r['count_gt']) == c]
        k = sum(1 for r in b if r['correct'])
        ints = [r['pred'] for r in b if isinstance(r['pred'], int)]
        gts = [int(r['n_dots_detected_gt']) for r in b]
        lo, hi = wilson(k, len(b))
        mode, mode_n = (collections.Counter(ints).most_common(1)[0] if ints else (None, 0))
        out[c] = {'n': len(b), 'hits': k, 'acc': k / float(len(b)),
                  'wilson_lo': lo, 'wilson_hi': hi,
                  'n_int': len(ints),
                  'mae': (sum(abs(p - g) for p, g in
                              zip(ints, [int(r['n_dots_detected_gt']) for r in b if
                                         isinstance(r['pred'], int)])) / float(len(ints))
                          if ints else None),
                  'med_pred': (sorted(ints)[len(ints) // 2] if ints else None),
                  'mode_pred': mode, 'mode_share': mode_n / float(len(ints)) if ints else None,
                  'abstain': sum(1 for r in b if r['cls'] == 'abstain'),
                  'unparsed': sum(1 for r in b if r['cls'] in ('unparsed', 'unserved')),
                  'n_gt': len(gts), 'mean_gt': sum(gts) / float(len(gts))}
    return out


def band_rows_for_csv(label, bd, extra=None):
    r = []
    for c in sorted(bd):
        v = bd[c]
        r.append(dict([('arm', label), ('count_band', 'c%02d' % c), ('n', v['n']),
                       ('hits', v['hits']), ('acc', '%.6f' % v['acc']),
                       ('wilson_lo', '%.6f' % v['wilson_lo']), ('wilson_hi', '%.6f' % v['wilson_hi']),
                       ('n_int', v['n_int']),
                       ('mae', '' if v['mae'] is None else '%.4f' % v['mae']),
                       ('median_pred', '' if v['med_pred'] is None else v['med_pred']),
                       ('mode_pred', '' if v['mode_pred'] is None else v['mode_pred']),
                       ('mode_share', '' if v['mode_share'] is None else '%.4f' % v['mode_share']),
                       ('n_abstain', v['abstain']), ('n_unparsed_or_unserved', v['unparsed']),
                       ('mean_n_dots_detected_gt', '%.4f' % v['mean_gt'])] +
                      (list((extra or {}).items()))))
    return r


# ══════════════════════ 重复一致性 ══════════════════════
def repeat_stats(rows, models):
    """按 (model, contract, item) 的 3 次重复：不一致率、|Δ| 分布、两套口径的逐档命中率。"""
    rep = {}
    for m in models:
        cells = collections.defaultdict(dict)
        for r in rows:
            if r['model'] == m:
                cells[(r['contract'], r['item'])][r['rep']] = r
        n_tri = n_full = n_incons = n_split = 0
        dmax = collections.Counter()
        dvals = []
        cls_drift = collections.Counter()
        for kk, v in cells.items():
            if len(v) < 3:
                continue
            n_tri += 1
            seq = [v[i] for i in (1, 2, 3)]
            if any(s['cls'] == 'unserved' for s in seq):
                continue
            n_full += 1
            vals = [s['pred'] if s['cls'] == 'int' else s['cls'] for s in seq]
            if len(set(vals)) > 1:
                n_incons += 1
            if len(set(vals)) == 3 and len(set(v for v in vals if isinstance(v, int))) == 3:
                n_split += 1
            else:
                cnt = collections.Counter(vals)
                if cnt.most_common(1)[0][1] < 2:
                    n_split += 1
            ints = [x for x in vals if isinstance(x, int)]
            if len(ints) == 3:
                d = max(ints) - min(ints)
                dvals.append(d)
                dmax[d if d <= 5 else '>5'] += 1
            if len(set(s['cls'] for s in seq)) > 1:
                cls_drift['/'.join(sorted(set(s['cls'] for s in seq)))] += 1
        # 两套口径的逐档命中率
        per_rep_rows = [r for r in rows if r['model'] == m]
        maj_rows = []
        for kk, v in cells.items():
            seq = [v.get(i) for i in (1, 2, 3)]
            if any(s is None for s in seq):
                continue
            vals = [s['pred'] if s['cls'] == 'int' else s['cls'] for s in seq]
            cnt = collections.Counter(vals)
            top, tcnt = cnt.most_common(1)[0]
            if tcnt < 2:
                maj = 'no_majority'
            else:
                maj = top
            src = seq[0]
            maj_rows.append({'model': m, 'contract': kk[0], 'item': kk[1],
                             'layout_id': kk[1], 'cell_id': src['cell_id'],
                             'count_gt': src['count_gt'],
                             'n_dots_detected_gt': src['n_dots_detected_gt'],
                             'radius': src['radius'], 'blur': src['blur'],
                             'overlap': src['overlap'],
                             'pred': maj if isinstance(maj, int) else None,
                             'cls': 'int' if isinstance(maj, int) else str(maj)})
        for r in maj_rows:
            r['correct'] = is_correct(r['pred'], int(r['n_dots_detected_gt']))
        rep[m] = {'n_items': len(cells), 'n_triples_complete': n_tri,
                  'n_triples_all_served': n_full, 'n_inconsistent': n_incons,
                  'inconsistency_rate': (n_incons / float(n_full)) if n_full else None,
                  'n_all_three_distinct_or_no_majority': n_split,
                  'n_triples_with_3_ints': len(dvals),
                  'absdelta_hist': dict(sorted(dmax.items(), key=lambda x: str(x[0]))),
                  'absdelta_median': (sorted(dvals)[len(dvals) // 2] if dvals else None),
                  'absdelta_mean': (sum(dvals) / float(len(dvals)) if dvals else None),
                  'absdelta_p90': (sorted(dvals)[int(0.9 * (len(dvals) - 1))] if dvals else None),
                  'class_drift': dict(cls_drift),
                  'bands_per_rep': bands(per_rep_rows),
                  'bands_majority': bands(maj_rows),
                  'majority_rows': maj_rows,
                  'n_rows_majority': len(maj_rows)}
    return rep


# ══════════════════════ served / ptok 分层 ══════════════════════
def stratum_stats(rows, models):
    out = {}
    for m in models:
        mr = [r for r in rows if r['model'] == m]
        modal = {}
        for ct in ('base', 'strict', 'permit'):
            c = collections.Counter(r['ptok'] for r in mr if r['contract'] == ct and r['ptok'])
            modal[ct] = c.most_common(1)[0][0] if c else None
        for r in mr:
            r['_ptok_cluster'] = ('modal' if r['ptok'] == modal.get(r['contract'])
                                  else ('off-modal' if r['ptok'] else 'unserved'))
            r['_ptok_dir'] = (None if not r['ptok'] else
                              ('equal' if r['ptok'] == modal.get(r['contract'])
                               else ('below' if r['ptok'] < modal.get(r['contract'], 0)
                                     else 'above')))
        info = {'modal_ptok_by_contract': modal,
                'n_distinct_ptok': len({r['ptok'] for r in mr if r['ptok']}),
                'served_names': dict(collections.Counter(r['served'] for r in mr if r['served'])),
                'n_off_modal': sum(1 for r in mr if r['_ptok_cluster'] == 'off-modal'),
                'n_modal': sum(1 for r in mr if r['_ptok_cluster'] == 'modal'),
                'unserved': sum(1 for r in mr if r['_ptok_cluster'] == 'unserved')}
        for st in ('modal', 'off-modal'):
            sub = [r for r in mr if r['_ptok_cluster'] == st]
            info['fit_' + st] = fit_rows(sub, label='%s|%s' % (m, st)) if len(sub) > 200 else None
            info['acc_' + st] = (sum(1 for r in sub if r['correct']) / float(len(sub))
                                 if sub else None)
        # 只有存在 served 漂移或多个 ptok 簇时才逐簇拟合
        info['fit_all'] = fit_rows(mr, label='%s|all' % m)
        by_served = {}
        for sn in sorted({r['served'] for r in mr if r['served']}):
            sub = [r for r in mr if r['served'] == sn]
            by_served[sn] = {'n': len(sub),
                             'acc': sum(1 for r in sub if r['correct']) / float(len(sub)),
                             'fit': fit_rows(sub, label='%s|served=%s' % (m, sn))
                             if len(sub) > 200 else None}
        info['by_served'] = by_served
        # 主导 ptok 簇（每个 contract 众数簇的并集）下重拟合
        dom = [r for r in mr if r['_ptok_cluster'] == 'modal']
        info['fit_dominant_ptok'] = fit_rows(dom, label='%s|dominant-ptok' % m) if dom else None
        # ptok 方向：低于 / 高于该合同众数值（暴露"另一后端/另一套图像 tokenizer"）
        for tag, sel in (('ptok-below-modal', 'below'), ('ptok-above-modal', 'above')):
            sub = [r for r in mr if r['_ptok_dir'] == sel]
            info['n_' + tag] = len(sub)
            info[tag] = {'n': len(sub),
                         'acc': (sum(1 for r in sub if r['correct']) / float(len(sub)))
                         if sub else None,
                         'fit': fit_rows(sub, label='%s|%s' % (m, tag)) if len(sub) > 200 else None}
        out[m] = info
    return out


# ══════════════════════ 抽检 ══════════════════════
def spotcheck(raw_rows, man, dm, n=SPOT_N, seed=SPOT_SEED):
    """随机 n 行的**逐项**核对：http / 计数解析 / 真值配对（两套独立来源）。

    通过 ⇔ 四项全真：
      (a) http == 200
      (b) 冻结解析器与独立解析器给出**同一个**取值（含 abstain / 无值）
      (c) manifest 的 n_dots_detected_gt 与 detection_matrix 的同一格取值**逐位相同**
      (d) correct == is_correct(pred, gt)（用冻结容差重算一遍）
    """
    rng = random.Random(seed)
    idx = sorted(rng.sample(range(len(raw_rows)), n))
    out = []
    for i in idx:
        r = raw_rows[i]
        m = man[r['item']]
        gt_m = int(m['n_dots_detected_gt'])
        gt_d = dm[r['item']]
        a = parse_frozen(r['raw'] or '')
        b = parse_indep(r['raw'] or '')
        chk_a = (r['http'] == 200)
        chk_b = (str(a if a is not None else '') == str(b if b is not None else ''))
        chk_c = (gt_m == gt_d)
        chk_d = (r['correct'] == is_correct(r['pred'], gt_m))
        out.append({'key': r['key'], 'model': r['model'], 'contract': r['contract'],
                    'rep': r['rep'], 'http': r['http'], 'served': r['served'],
                    'raw': (r['raw'] or '')[:200], 'parsed_frozen': a, 'parsed_indep': b,
                    'parse_class': r['cls'], 'count_gt': int(r['count_gt']),
                    'n_dots_detected_gt_manifest': gt_m,
                    'n_dots_detected_gt_detection_matrix': gt_d,
                    'tol': tol_of(gt_m), 'correct': r['correct'],
                    'check_http200': bool(chk_a), 'check_parser_agree': bool(chk_b),
                    'check_gt_crosssource': bool(chk_c), 'check_correct_recompute': bool(chk_d),
                    'pass': bool(chk_a and chk_b and chk_c and chk_d)})
    return out, sum(1 for o in out if o['pass']) / float(len(out))


# ══════════════════════ 主流程 ══════════════════════
def main():
    man = load_manifest()
    dm = load_dmatrix()
    rows, missing = load_api(man)
    served_rows = [r for r in rows if r['http'] == 200]
    print('== A5-2 API 臂分析 ==')
    print('  merged_best.jsonl md5 = %s' % md5f(MERGED))
    print('  行数 = %d ｜ http==200 = %d ｜ 未成功 = %d' % (len(rows), len(served_rows), len(missing)))
    print('  判据件 md5 = %s' % md5f(CRIT))
    print('  冻结分析器 = %s（md5 %s）' % (A.__file__, md5f(A.__file__)))
    print('  IRLS 后端 = %s' % A.BACKEND)

    R = {'criteria_md5': md5f(CRIT), 'analyzer_md5': md5f(A.__file__),
         'merged_md5': md5f(MERGED), 'n_rows': len(rows), 'n_served': len(served_rows),
         'n_missing': len(missing)}

    # ---- 解析/完整性 ----
    cls_tab = collections.defaultdict(collections.Counter)
    for r in rows:
        cls_tab[r['model']][r['cls']] += 1
    R['parse_table'] = {m: dict(v) for m, v in cls_tab.items()}
    print('  解析：int=%d abstain=%d unparsed=%d unserved=%d' % (
        sum(v['int'] for v in cls_tab.values()), sum(v['abstain'] for v in cls_tab.values()),
        sum(v['unparsed'] for v in cls_tab.values()), sum(v['unserved'] for v in cls_tab.values())))

    # ---- 逐档 + 逐模型拟合 ----
    R['bands_api'] = {}
    R['fit_api'] = {}
    for m in API_MODELS:
        mr = [r for r in served_rows if r['model'] == m]
        R['bands_api'][m] = bands(mr)
        f = fit_rows(mr, use_model_terms=False, label=m)
        f['cluster_bootstrap'] = cluster_bootstrap(mr)
        f['c4_pass'] = c4(f['ci'], f.get('ci_informative', True))
        f['c5'] = groupwise(mr)
        R['fit_api'][m] = f
        print('  [%s] n=%d 正确=%d  β=%s  se=%s  CI=%s  C4=%s' % (
            m, f['n_rows'], f['n_correct'], round(f['beta_count'], 4), round(f['se_count'], 4),
            [round(v, 4) for v in f['ci']], f['c4_pass']))

    # ---- 池化（6 模型）----
    P1 = fit_rows(served_rows, use_model_terms=False, label='API-pooled|no-model-terms')
    P1['cluster_bootstrap'] = cluster_bootstrap(served_rows)
    P1['c4_pass'] = c4(P1['ci'], P1.get('ci_informative', True))
    P1['c5'] = groupwise(served_rows)
    P2 = fit_rows(served_rows, use_model_terms=True, ref_model=REF_MODEL,
                  label='API-pooled|model-dummies')
    P2['cluster_bootstrap'] = cluster_bootstrap(served_rows, use_model_terms=True)
    P2['c4_pass'] = c4(P2['ci'], P2.get('ci_informative', True))
    R['fit_pooled_common'] = P1
    R['fit_pooled_model_terms'] = P2
    R['bands_api_pooled'] = bands(served_rows)
    print('  池化(共同斜率) β=%s CI=%s C4=%s' % (round(P1['beta_count'], 4),
                                          [round(v, 4) for v in P1['ci']], P1['c4_pass']))
    print('  池化(模型哑变量, ref=%s) β=%s CI=%s' % (REF_MODEL, round(P2['beta_count'], 4),
                                              [round(v, 4) for v in P2['ci']]))

    # ---- NC1 / NC3 ----
    R['nc1'] = A.negctl([{**r, 'build': r['model'], 'pred': '' if r['pred'] is None else str(r['pred']),
                          'parse_ok': r['parse_ok'], 'abstain': r['abstain'], 'refuse': 0,
                          'http_err': 0} for r in served_rows], n_perm=20, verbose=False)
    mis = chk = 0
    for r in served_rows:
        raw = r['raw'] or ''
        chk += 1
        a = parse_indep(raw)
        b = ('abstain' if r['cls'] == 'abstain' else
             (str(r['pred']) if r['cls'] == 'int' else None))
        if str(a or '') != str(b or ''):
            mis += 1
    R['nc3'] = {'checked': chk, 'mismatch': mis, 'passed': mis == 0,
                'method': 'raw → 独立正则复解析（a52_analyze.NC3 的同思路异实现）'}
    print('  NC1 β中位=%s CI并集=%s PASS=%s' % (
        None if R['nc1']['beta_median'] is None else round(R['nc1']['beta_median'], 4),
        [None if v is None else round(v, 3) for v in R['nc1']['ci_union']], R['nc1']['passed']))
    print('  NC3 核 %d 不一致 %d ⇒ %s' % (chk, mis, R['nc3']['passed']))

    # ---- 重复一致性 ----
    R['repeat'] = repeat_stats(served_rows, API_MODELS)
    # 多数值口径重拟合（回答"重复噪声会不会改变档位结论"）
    R['fit_api_majority'] = {}
    for m in API_MODELS:
        majr = R['repeat'][m]['majority_rows']
        f = fit_rows(majr, label='%s|majority-of-3' % m)
        f['c4_pass'] = c4(f['ci'], f.get('ci_informative', True))
        f['c5'] = groupwise(majr)
        R['fit_api_majority'][m] = f
    R['fit_pooled_majority'] = fit_rows(
        [r for m in API_MODELS for r in R['repeat'][m]['majority_rows']],
        label='API-pooled|majority-of-3')
    R['fit_pooled_majority']['c4_pass'] = c4(R['fit_pooled_majority']['ci'],
                                             R['fit_pooled_majority'].get('ci_informative', True))
    for m in API_MODELS:
        v = R['repeat'][m]
        f = R['fit_api_majority'][m]
        print('  [%s] 不一致率=%s ｜Δ|中位=%s β多数=%s CI=[%.4f, %.4f]' % (
            m, None if v['inconsistency_rate'] is None else round(v['inconsistency_rate'], 4),
            v['absdelta_median'], round(f['beta_count'], 4), f['ci'][0], f['ci'][1]))
    print('  池化（多数值口径）β=%.4f CI=[%.4f, %.4f]' % (
        R['fit_pooled_majority']['beta_count'], R['fit_pooled_majority']['ci'][0],
        R['fit_pooled_majority']['ci'][1]))

    # ---- 基线 b0/b1/b2 复算 ----
    bl = load_baseline()
    R['bands_baseline'] = {}
    R['fit_baseline'] = {}
    for b in ('b0', 'b1', 'b2'):
        br = bl[b]
        br2 = [{**r, 'model': r['build'], 'cls': 'int', 'correct': r['correct']} for r in br]
        R['bands_baseline'][b] = bands(br2)
        f = fit_rows([{**r, 'model': r['build']} for r in br], use_model_terms=False, label=b)
        f['c4_pass'] = c4(f['ci'], f.get('ci_informative', True))
        f['c5'] = groupwise([{**r, 'model': r['build']} for r in br])
        R['fit_baseline'][b] = f
        print('  [%s] n=%d β=%s CI=%s 档=%s' % (
            b, f['n_rows'], round(f['beta_count'], 4), [round(v, 4) for v in f['ci']],
            {c: round(R['bands_baseline'][b][c]['acc'] * 100, 2) for c in sorted(R['bands_baseline'][b])}))

    # ---- served/ptok 分层 ----
    R['strata'] = stratum_stats(served_rows, API_MODELS)

    # ---- 抽检 ----
    spot, spot_pass = spotcheck(rows, man, dm)
    R['spotcheck'] = {'n': len(spot), 'pass_rate': spot_pass, 'seed': SPOT_SEED, 'rows': spot}
    print('  抽检 %d 行，通过率 = %.3f' % (len(spot), spot_pass))

    # ---- 稳健性：预注册排除格 / abstain 处置 / 合同分层 ----
    UNREAL = ['c08_s3_b8_o0', 'c80_s24_b0_o0', 'c80_s24_b4_o0']   # 冻结件里"先声明后排除"的 3 格
    R['sensitivity'] = {}
    for m in API_MODELS:
        mr = [r for r in served_rows if r['model'] == m]
        keep = [r for r in mr if r['cell_id'] not in UNREAL]
        R['sensitivity'].setdefault('excl_unrealizable', {})[m] = fit_rows(
            keep, label='%s|excl-3-unrealizable' % m)
        ans = [r for r in mr if r['cls'] != 'abstain']
        R['sensitivity'].setdefault('abstain_excluded', {})[m] = fit_rows(
            ans, label='%s|abstain-excluded' % m)
        per_ct = {}
        for ct in ('base', 'strict', 'permit'):
            sub = [r for r in mr if r['contract'] == ct]
            per_ct[ct] = {'n': len(sub),
                          'acc': sum(1 for r in sub if r['correct']) / float(len(sub)),
                          'n_abstain': sum(1 for r in sub if r['cls'] == 'abstain'),
                          'abstain_rate': sum(1 for r in sub if r['cls'] == 'abstain') / float(len(sub))}
        R['sensitivity'].setdefault('by_contract', {})[m] = per_ct
    R['sensitivity']['excl_unrealizable']['_cells'] = UNREAL
    print('  稳健性：预注册 3 格排除 / abstain 排除 / 逐合同 —— 已算')

    # ---- 缺失格 ----
    R['missing_cells'] = [{'key': r['key'], 'model': r['model'], 'contract': r['contract'],
                           'rep': r['rep'], 'item': r['item'], 'http': r['http'],
                           'err': (r.get('err') or '')[:120]} for r in missing]
    R['missing_by_model'] = dict(collections.Counter(r['model'] for r in missing))
    # 已回 200 但正文为空/不可解析的格（不是服务失败，属解析口径内的失败）
    R['empty_body_cells'] = [{'key': r['key'], 'http': r['http'], 'cls': r['cls'],
                              'raw': repr(r['raw']), 'usage': r['ptok']}
                             for r in served_rows if r['cls'] == 'unparsed']
    print('  已回 200 但无正文/不可解析 = %d' % len(R['empty_body_cells']))

    io.open(os.path.join(RAWD, '_api_analysis_raw.json'), 'w', encoding='utf-8', newline='\n').write(
        json.dumps(R, ensure_ascii=False, indent=1, default=str) + '\n')
    print('\n原始结果 ⇒ %s' % os.path.join(RAWD, '_api_analysis_raw.json'))

    write_tables(R, served_rows)
    print('交付表 ⇒ %s' % OUT)
    return R


# ══════════════════════ 写交付表（CSV）══════════════════════
def _w(path, header, rows):
    """用 csv 模块写出（正确加引号：absdelta_hist / class_drift / served_names 里含逗号）。"""
    with io.open(path, 'w', encoding='utf-8', newline='') as fh:
        w = csv.writer(fh, lineterminator='\n')
        w.writerow(header)
        for r in rows:
            w.writerow(['' if r.get(h) is None else r.get(h) for h in header])


def write_tables(R, served_rows):
    # ── 表 2：逐模型 × 逐档 ──
    hdr2 = ['arm', 'arm_kind', 'count_band', 'n', 'hits', 'accuracy', 'wilson_lo', 'wilson_hi',
            'n_integer_pred', 'mae_vs_n_dots_detected_gt', 'median_pred', 'collapse_mode_pred',
            'collapse_mode_share', 'n_abstain', 'n_unparsed_or_unserved',
            'mean_n_dots_detected_gt']
    rows2 = []

    def add_arm(label, kind, bd):
        for c in sorted(bd):
            v = bd[c]
            rows2.append({'arm': label, 'arm_kind': kind, 'count_band': 'c%02d' % c, 'n': v['n'],
                          'hits': v['hits'], 'accuracy': '%.6f' % v['acc'],
                          'wilson_lo': '%.6f' % v['wilson_lo'],
                          'wilson_hi': '%.6f' % v['wilson_hi'],
                          'n_integer_pred': v['n_int'],
                          'mae_vs_n_dots_detected_gt':
                              '' if v['mae'] is None else '%.4f' % v['mae'],
                          'median_pred': v['med_pred'], 'collapse_mode_pred': v['mode_pred'],
                          'collapse_mode_share':
                              '' if v['mode_share'] is None else '%.4f' % v['mode_share'],
                          'n_abstain': v['abstain'], 'n_unparsed_or_unserved': v['unparsed'],
                          'mean_n_dots_detected_gt': '%.4f' % v['mean_gt']})
    for m in API_MODELS:
        add_arm(m, 'api_model', R['bands_api'][m])
        rc = R['repeat'][m]
        add_arm(m + ' [majority-of-3]', 'api_model_majority', rc['bands_majority'])
    add_arm('API-ARM-POOLED(6 models)', 'api_pooled', R['bands_api_pooled'])
    for b in ('b0', 'b1', 'b2'):
        add_arm(b, 'local_build', R['bands_baseline'][b])
    _w(os.path.join(OUT, 'table_per_model_band_accuracy.csv'), hdr2, rows2)

    # ── 表 3：重复一致性 ──
    hdr3 = ['model', 'n_items', 'n_triples_complete', 'n_triples_all_served',
            'n_inconsistent', 'inconsistency_rate', 'n_all_three_distinct',
            'n_triples_with_3_integer_preds', 'absdelta_median', 'absdelta_mean', 'absdelta_p90',
            'absdelta_hist', 'class_drift',
            'beta_per_rep_allrows', 'ci_per_rep_lo', 'ci_per_rep_hi',
            'beta_majority', 'ci_majority_lo', 'ci_majority_hi', 'c4_majority',
            'acc_c08_per_rep', 'acc_c32_per_rep', 'acc_c80_per_rep',
            'acc_c08_majority', 'acc_c32_majority', 'acc_c80_majority',
            'delta_acc_c08_pp', 'delta_acc_c32_pp', 'delta_acc_c80_pp', 'n_rows_majority']
    rows3 = []
    for m in API_MODELS:
        v = R['repeat'][m]
        b1_, b2_ = v['bands_per_rep'], v['bands_majority']
        fm = R['fit_api_majority'][m]
        fr = R['fit_api'][m]
        def acc(bd, c):
            return bd[c]['acc'] if c in bd else float('nan')
        rec = {'model': m, 'n_items': v['n_items'], 'n_triples_complete': v['n_triples_complete'],
               'n_triples_all_served': v['n_triples_all_served'],
               'n_inconsistent': v['n_inconsistent'],
               'inconsistency_rate': '%.6f' % v['inconsistency_rate'],
               'n_all_three_distinct': v['n_all_three_distinct_or_no_majority'],
               'n_triples_with_3_integer_preds': v['n_triples_with_3_ints'],
               'absdelta_median': v['absdelta_median'], 'absdelta_mean':
                   '' if v['absdelta_mean'] is None else '%.4f' % v['absdelta_mean'],
               'absdelta_p90': v['absdelta_p90'],
               'absdelta_hist': json.dumps(v['absdelta_hist'], ensure_ascii=False),
               'class_drift': json.dumps(v['class_drift'], ensure_ascii=False),
               'beta_per_rep_allrows': '%.6f' % fr['beta_count'],
               'ci_per_rep_lo': '%.6f' % fr['ci'][0], 'ci_per_rep_hi': '%.6f' % fr['ci'][1],
               'beta_majority': '%.6f' % fm['beta_count'],
               'ci_majority_lo': '%.6f' % fm['ci'][0], 'ci_majority_hi': '%.6f' % fm['ci'][1],
               'c4_majority': str(fm['c4_pass']),
               'n_rows_majority': v['n_rows_majority']}
        for c, tag in ((8, 'c08'), (32, 'c32'), (80, 'c80')):
            rec['acc_%s_per_rep' % tag] = '%.6f' % acc(b1_, c)
            rec['acc_%s_majority' % tag] = '%.6f' % acc(b2_, c)
            rec['delta_acc_%s_pp' % tag] = '%.4f' % (100.0 * (acc(b2_, c) - acc(b1_, c)))
        rows3.append(rec)
    _w(os.path.join(OUT, 'table_repeat_consistency.csv'), hdr3, rows3)

    # ── 表 4：served / ptok 分层 ──
    hdr4 = ['model', 'stratum', 'definition', 'n', 'accuracy', 'beta_count_std', 'se',
            'ci_lo', 'ci_hi', 'ci_width', 'c4_pass_band_0.2', 'n_distinct_ptok',
            'modal_ptok_base', 'modal_ptok_strict', 'modal_ptok_permit', 'served_names']
    rows4 = []
    for m in API_MODELS:
        s = R['strata'][m]
        base = {'model': m, 'n_distinct_ptok': s['n_distinct_ptok'],
                'modal_ptok_base': s['modal_ptok_by_contract'].get('base'),
                'modal_ptok_strict': s['modal_ptok_by_contract'].get('strict'),
                'modal_ptok_permit': s['modal_ptok_by_contract'].get('permit'),
                'served_names': json.dumps(s['served_names'], ensure_ascii=False)}
        groups = [('ALL', 'all rows of this model', s['fit_all'], None, None)]
        for st, defn in (('modal', 'usage.prompt_tokens == modal ptok of its (model,contract)'),
                         ('off-modal', 'usage.prompt_tokens != that modal value')):
            groups.append((st, defn, s.get('fit_' + st), s.get('acc_' + st),
                           s['n_modal'] if st == 'modal' else s['n_off_modal']))
        groups.append(('dominant-ptok-only', 'keep only modal-ptok rows',
                       s['fit_dominant_ptok'], None, s['n_modal']))
        for tag, defn in (('ptok-below-modal',
                           'usage.prompt_tokens < modal value of its (model,contract)'),
                          ('ptok-above-modal',
                           'usage.prompt_tokens > modal value of its (model,contract)')):
            d = s.get(tag) or {}
            groups.append((tag, defn, d.get('fit'), d.get('acc'), d.get('n')))
        for sn, v in sorted(s['by_served'].items()):
            groups.append(('served=' + sn, 'value of the `served` field echoed by the API',
                           v['fit'], v['acc'], v['n']))
        for st, defn, f, acc, n in groups:
            if f is None:
                rows4.append({**base, 'stratum': st, 'definition': defn,
                              'n': n, 'accuracy': '' if acc is None else '%.6f' % acc})
                continue
            ci = f.get('ci')
            rows4.append({**base, 'stratum': st, 'definition': defn, 'n': f['n_rows'],
                          'accuracy': '%.6f' % f['outcome_rate'],
                          'beta_count_std': '%.6f' % f['beta_count'],
                          'se': '%.6f' % f['se_count'],
                          'ci_lo': '%.6f' % ci[0], 'ci_hi': '%.6f' % ci[1],
                          'ci_width': '%.6f' % (ci[1] - ci[0]),
                          'c4_pass_band_0.2': str(c4(ci, f.get('ci_informative', True)))})
    _w(os.path.join(OUT, 'table_stratified_served_ptok.csv'), hdr4, rows4)


# ══════════════════════ ★ 负例自测（v0669 A8-3/M-6）══════════════════════
def selftest():
    """负例自测：路径解析与导入的三类失败必须**明确报错**，且与工作目录无关。"""
    import shutil
    import tempfile
    ctl = []

    # (1) 冻结分析器已被找到、按文件路径导入、且三个复用入口齐备
    ctl.append(('冻结分析器按文件路径导入成功（%s）' % os.path.basename(_ANALYZER),
                os.path.isfile(_ANALYZER) and all(
                    hasattr(A, n) for n in ('is_correct', 'wilson', 'fit_logit'))))
    ctl.append(('冻结分析器 md5 == bf873c5e7da083dae42cb379efe9af9d',
                md5f(_ANALYZER) == 'bf873c5e7da083dae42cb379efe9af9d'))

    # (2) 缺件 ⇒ SystemExit(3) 且信息里带可读的候选路径（不是静默 0 结果）
    tmp = tempfile.mkdtemp(prefix='_a52_api_selftest_')
    try:
        try:
            _need('故意不存在的件', [os.path.join(tmp, '__nope__.json')])
            ctl.append(('缺件 ⇒ 明确失败（退出码 3）', False))
        except SystemExit as e:
            ctl.append(('缺件 ⇒ 明确失败（退出码 3）', e.code == 3))
        try:
            _need('故意不存在的目录', [os.path.join(tmp, '__nope_dir__')], kind='dir')
            ctl.append(('缺目录 ⇒ 明确失败（退出码 3）', False))
        except SystemExit as e:
            ctl.append(('缺目录 ⇒ 明确失败（退出码 3）', e.code == 3))

        # (3) 四个输入件与两个本地臂目录**逐一实存**
        ctl.append(('四个输入件实存',
                    all(os.path.isfile(x) for x in (MERGED, CRIT, DMAT, MANIFEST))))
        ctl.append(('两个本地臂目录实存',
                    all(os.path.isdir(x) for x in (BASE_RES, BASE_EXT))))

        # (4) 工作目录无关：切到临时目录后，同一批路径的判断不变
        cwd0 = os.getcwd()
        try:
            os.chdir(tmp)
            same = all(os.path.isfile(x) for x in (MERGED, CRIT, DMAT, MANIFEST))
        finally:
            os.chdir(cwd0)
        ctl.append(('路径解析与工作目录无关', same))

        # (5) 解析器负例：不可解析的 raw ⇒ None（下游 cls=unparsed、计 0 分），绝不静默丢弃
        ctl.append(('不可解析 raw ⇒ parse_frozen 返回 None',
                    parse_frozen('I cannot count these.') is None))
        ctl.append(('is_correct(None) == 0（不计入正确）',
                    A.is_correct({'pred': '', 'n_dots_detected_gt': '10'}) == 0))

        # (6) 解析器正例回归
        ctl.append(('parse_frozen `{"count": 8}` == 8', parse_frozen('{"count": 8}') == 8))
        ctl.append(('parse_frozen abstain 保持字面量',
                    parse_frozen('{"count": "abstain"}') == 'abstain'))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    ok = True
    for nm, passed in ctl:
        print('  [%s] %s' % ('PASS' if passed else 'FAIL', nm))
        ok = ok and passed
    print('SELFTEST: %s' % ('PASS' if ok else 'FAIL'))
    return 0 if ok else 1


if __name__ == '__main__':
    _ap = argparse.ArgumentParser(description='A5-2 API 臂分析驱动（只读已放行记录）')
    _ap.add_argument('--out', default=None, help='3 张交付表的输出目录（默认为输入所在目录）')
    _ap.add_argument('--raw-out', default=None, help='_api_analysis_raw.json 的输出目录（默认本脚本目录）')
    _ap.add_argument('--selftest', action='store_true', help='★ 负例自测（不跑全量分析）')
    _a = _ap.parse_args()
    if _a.selftest:
        sys.exit(selftest())
    if _a.out:
        OUT = os.path.abspath(_a.out)
    if _a.raw_out:
        RAWD = os.path.abspath(_a.raw_out)
    os.makedirs(OUT, exist_ok=True)
    os.makedirs(RAWD, exist_ok=True)
    print('输入目录 = %s' % os.path.dirname(MERGED))
    print('交付目录 = %s' % OUT)
    main()
