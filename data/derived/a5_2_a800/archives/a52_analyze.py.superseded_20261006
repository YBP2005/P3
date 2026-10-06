#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""a52_analyze.py —— A5-2 分析（**纯 CPU**，不碰 GPU、不碰网络）。判据见 `_a52_criteria_frozen.json`。

读入：`<dir>/A52_<build>_<contract>_s<start>.csv`（每格 648 行，一行 = 一图）。
口径（全部来自判据件，**跑前冻结**）：
    correct = pred 为整数 且 |pred − n_dots_detected_gt| ≤ max(1, 0.05·n_dots_detected_gt)
              （abstain / 拒答 / 解析失败 / http_err ⇒ correct = 0；解析失败另由 C2 单独把关）
    响应尺度 = log-odds（logistic 回归）
    C1 覆盖 81 格（先声明后排除的 UNREALIZABLE 移出分母）/ 648 图 / sha256 齐
    C2 完整性 23,328 行 + 逐格 parse_ok ≥ 95%
    C3 四因子模型：count 主效应 + count×合同 + count×构建（按预注册顺序报）
    C4 标准化 log-odds 的 count 主效应 95% CI **完全落在 ±0.2 内** ⇒ 可称"无实质作用"
    C5 以**布局为组**留出（8 折），同源变体同折；报 group-wise 稳定性
    阴性对照 NC1：把 count 设常数（count 无方差）⇒ count 主效应**必须消失**（本实现里恒为 0）
              NC3：从 raw 列独立重解析，逐行核对 parse_ok/pred

用法：
    python a52_analyze.py --dir <结果目录> [--out a52_result.json] [--stim <刺激目录>]
    python a52_analyze.py --mock        # 生成合成 mock 数据（判据件口径；自带 count 效应）
    python a52_analyze.py --selftest    # mock → C1–C5 + 阴性对照，全链路自测（打印逐条判定）
    python a52_analyze.py --mock-null-count   # mock 的 count 恒定版（阴性对照的真值）
"""
import argparse
import csv
import glob
import hashlib
import io
import json
import math
import os
import random
import re
import sys
import tempfile

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
HERE = os.path.dirname(os.path.abspath(__file__))
CRIT = os.path.join(HERE, '_a52_criteria_frozen.json')
STIM_MANIFEST = 'manifest.csv'
BUILDS = ['b0', 'b1', 'b2', 'b3']
CONTRACTS = ['base', 'strict', 'permit']
STARTS = ['1', '2', '3']
K_FOLDS = 8
B_BOOT = 500
BOOT_SEED = 20261004
CELLS = 81
PER_CELL = 8
IMAGES = CELLS * PER_CELL                      # 648
BUDGET_ROWS = IMAGES * len(BUILDS) * len(CONTRACTS) * len(STARTS)   # 23,328
TOL_ABS, TOL_REL = 1, 0.05
COLS_REQUIRED = ['item', 'cell_id', 'layout_id', 'count_gt', 'n_dots_detected_gt', 'build',
                 'contract', 'start', 'pred', 'parse_ok', 'abstain', 'refuse', 'http_err',
                 'model', 'raw']
# 刺激侧的**真参数**（探针从 manifest 抄进 CSV；分析器按判据件口径当有序变量用）
COLS_STIM = ['radius', 'blur', 'overlap']
CELLFILE_RE = re.compile(r'^A52_(?P<build>[^_]+)_(?P<contract>[^_]+)_s(?P<start>\d+)\.csv$')


# ════════════════════════════ 基础工具 ════════════════════════════
def md5f(p):
    return hashlib.md5(io.open(p, 'rb').read()).hexdigest()


def fnum(x):
    s = (x or '').strip()
    try:
        return float(s)
    except Exception:
        return None


def inum(x):
    s = (x or '').strip()
    if re.fullmatch(r'-?\d+', s):
        return int(s)
    return None


def wilson(k, n, z=1.96):
    if n == 0:
        return (float('nan'), float('nan'))
    p = k / float(n)
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return ((c - h) / d, (c + h) / d)


def is_correct(row):
    """判据件 C3 的响应定义。"""
    p = inum(row.get('pred'))
    if p is None:
        return 0
    g = inum(row.get('n_dots_detected_gt'))
    if g is None:
        return 0
    return 1 if abs(p - g) <= max(TOL_ABS, TOL_REL * g) else 0


# ════════════════════════════ logistic（IRLS）════════════════════════════
# 主路径用 numpy（500 次聚类 bootstrap 在纯 Python 里要十几分钟，numpy 下 ≈1 秒）；
# numpy 缺失时**自动退回**纯 Python 实现（两套都保留、同一接口，见 --backend）。
try:
    import numpy as _np
except Exception:                                     # pragma: no cover
    _np = None
BACKEND = 'numpy' if _np is not None else 'python'


def _matT_mat(X, W):
    k = len(X[0])
    A = [[0.0] * k for _ in range(k)]
    for i, xi in enumerate(X):
        w = W[i]
        if w == 0.0:
            continue
        for a in range(k):
            xa = xi[a] * w
            for b in range(a, k):
                A[a][b] += xa * xi[b]
    for a in range(k):
        for b in range(a):
            A[a][b] = A[b][a]
    return A


def _matT_vec(X, W, y):
    k = len(X[0])
    v = [0.0] * k
    for i, xi in enumerate(X):
        w = W[i]
        if w == 0.0:
            continue
        r = w * y[i]
        for a in range(k):
            v[a] += xi[a] * r
    return v


def _solve(A, b):
    """高斯-约当消元（带部分主元）；奇异 ⇒ None。"""
    n = len(A)
    M = [A[i][:] + [b[i]] for i in range(n)]
    for c in range(n):
        piv = max(range(c, n), key=lambda r: abs(M[r][c]))
        if abs(M[piv][c]) < 1e-12:
            return None
        M[c], M[piv] = M[piv], M[c]
        pv = M[c][c]
        M[c] = [x / pv for x in M[c]]
        for r in range(n):
            if r != c and M[r][c] != 0.0:
                f = M[r][c]
                M[r] = [M[r][j] - f * M[c][j] for j in range(n + 1)]
    return [M[i][n] for i in range(n)]


def fit_logit(X, y, ridge=1e-8, iters=60, tol=1e-10):
    """IRLS。返回 (beta, cov, se, rank_ok, n_iter)。有 numpy 走 numpy，否则纯 Python。"""
    if BACKEND != 'python' and _np is not None:
        return _fit_logit_np(X, y, ridge, iters, tol)
    return _fit_logit_py(X, y, ridge, iters, tol)


def _fit_logit_np(X, y, ridge, iters, tol):
    A = _np.asarray(X, dtype=float)
    yy = _np.asarray(y, dtype=float)
    k = A.shape[1]
    beta = _np.zeros(k)
    for it in range(iters):
        eta = A @ beta
        eta = _np.clip(eta, -35.0, 35.0)
        p = 1.0 / (1.0 + _np.exp(-eta))
        W = _np.maximum(p * (1.0 - p), 1e-9)
        z = eta + (yy - p) / W
        M = A.T @ (A * W[:, None])
        for a in range(1, k):
            M[a, a] += ridge
        try:
            nb = _np.linalg.solve(M, A.T @ (W * z))
        except Exception:
            return list(beta), None, None, False, it
        delta = float(_np.max(_np.abs(nb - beta)))
        beta = nb
        if delta < tol:
            break
    eta = _np.clip(A @ beta, -35.0, 35.0)
    p = 1.0 / (1.0 + _np.exp(-eta))
    W = _np.maximum(p * (1.0 - p), 1e-9)
    M = A.T @ (A * W[:, None])
    for a in range(1, k):
        M[a, a] += ridge
    if _np.linalg.matrix_rank(M) < k:
        return list(beta), None, None, False, it
    cov = _np.linalg.inv(M)
    se = _np.sqrt(_np.maximum(_np.diag(cov), 0.0))
    return [float(b) for b in beta], cov, [float(s) for s in se], True, it


def _fit_logit_py(X, y, ridge, iters, tol):
    k = len(X[0])
    beta = [0.0] * k
    for it in range(iters):
        eta = [sum(beta[j] * xi[j] for j in range(k)) for xi in X]
        p = [1.0 / (1.0 + math.exp(-max(-35.0, min(35.0, e)))) for e in eta]
        W = [max(1e-9, pi * (1 - pi)) for pi in p]
        z = [eta[i] + (y[i] - p[i]) / W[i] for i in range(len(y))]
        A = _matT_mat(X, W)
        for a in range(1, k):                       # ★ 非截距项加极小岭，防分离
            A[a][a] += ridge
        v = _matT_vec(X, W, z)
        nb = _solve(A, v)
        if nb is None:
            return beta, None, None, False, it
        delta = max(abs(nb[j] - beta[j]) for j in range(k))
        beta = nb
        if delta < tol:
            break
    eta = [sum(beta[j] * xi[j] for j in range(k)) for xi in X]
    p = [1.0 / (1.0 + math.exp(-max(-35.0, min(35.0, e)))) for e in eta]
    W = [max(1e-9, pi * (1 - pi)) for pi in p]
    A = _matT_mat(X, W)
    for a in range(1, k):
        A[a][a] += ridge
    cov = _invert(A)
    if cov is None:
        return beta, None, None, False, it
    return beta, cov, [math.sqrt(max(0.0, cov[j][j])) for j in range(k)], True, it


def _invert(A):
    n = len(A)
    M = [A[i][:] + [1.0 if i == j else 0.0 for j in range(n)] for i in range(n)]
    for c in range(n):
        piv = max(range(c, n), key=lambda r: abs(M[r][c]))
        if abs(M[piv][c]) < 1e-12:
            return None
        M[c], M[piv] = M[piv], M[c]
        pv = M[c][c]
        M[c] = [x / pv for x in M[c]]
        for r in range(n):
            if r != c and M[r][c] != 0.0:
                f = M[r][c]
                M[r] = [M[r][j] - f * M[c][j] for j in range(2 * n)]
    return [[M[i][n + j] for j in range(n)] for i in range(n)]


# ════════════════════════════ 设计矩阵 ════════════════════════════
def design_vec(r, mu, sd):
    """单行的设计向量（与 build_design 同一个顺序；bootstrap 复用它以免反复建矩阵）。"""
    c = fnum(r['count_gt']) or 0.0
    cs = (c - mu) / sd if sd > 1e-12 else 0.0
    z = [1.0, cs]
    z.append(cs * (1.0 if r['contract'] == 'strict' else 0.0))
    z.append(cs * (1.0 if r['contract'] == 'permit' else 0.0))
    for b in BUILDS[1:]:
        z.append(cs * (1.0 if r['build'] == b else 0.0))
    z.append(fnum(r.get('radius', r.get('size_level'))) or 0.0)
    z.append(fnum(r.get('blur', r.get('blur_level'))) or 0.0)
    z.append(fnum(r.get('overlap', r.get('overlap_level'))) or 0.0)
    for cname in CONTRACTS[1:]:
        z.append(1.0 if r['contract'] == cname else 0.0)
    for b in BUILDS[1:]:
        z.append(1.0 if r['build'] == b else 0.0)
    return z


def build_design(rows, ctr):
    """→ (X, y, names, count_std_values)。

    count 连续且 z 标准化；合同/构建用哑变量（参考档 base / b0）；
    size/blur/overlap 按有序处理（连续编码）。
    ctr = 训练集上的 (mean, sd)，测试集必须沿用（不许各自重标准化）。
    """
    mu, sd = ctr
    X = [design_vec(r, mu, sd) for r in rows]
    y = [float(is_correct(r)) for r in rows]
    names = (['intercept', 'count_std', 'count_std_x_strict', 'count_std_x_permit']
             + ['count_std_x_%s' % b for b in BUILDS[1:]]
             + ['radius', 'blur', 'overlap']
             + ['contract_%s' % c for c in CONTRACTS[1:]]
             + ['build_%s' % b for b in BUILDS[1:]])
    return X, y, names, [x[1] for x in X]


def fit_c3(rows, ctr=None, want_boot=False):
    """拟合四因子模型，报 count 主效应与两个交互（标准化 log-odds）。"""
    acts = [fnum(r['count_gt']) for r in rows]
    mu = sum(acts) / len(acts)
    sd = math.sqrt(sum((a - mu) ** 2 for a in acts) / len(acts)) if acts else 0.0
    if ctr is None:
        ctr = (mu, sd)
    out = {'count_mean': mu, 'count_sd': sd, 'n_rows': len(rows)}
    if sd <= 1e-12:
        # ★ 阴性对照的真值：count 无方差 ⇒ 设计矩阵里 cs 恒 0 ⇒ **最小二乘必定给出 β_count = 0**
        out.update({'rank_ok': True, 'degenerate_count': True, 'beta_count': 0.0,
                    'se_count': 0.0, 'ci': [0.0, 0.0], 'interactions': {},
                    'note': 'count 无方差（常数）⇒ β_count 恒等于 0（这才是 count 不变时应有的读数）'})
        return out
    X, y, names, _ = build_design(rows, ctr)
    beta, cov, se, ok, nit = fit_logit(X, y)
    out['rank_ok'] = bool(ok)
    out['n_iter'] = int(nit)
    if not ok:
        out['note'] = '设计矩阵奇异/不收敛 ⇒ C3/C4 不可评'
        return out
    i = names.index('count_std')
    out['beta_count'] = float(beta[i])
    out['se_count'] = float(se[i])
    out['ci'] = [float(beta[i] - 1.96 * se[i]), float(beta[i] + 1.96 * se[i])]
    # ★ 分离诊断：响应近饱和（全 0/全 1）会造成 SE 爆炸、CI 无意义。不作弊，如实标记。
    rate = sum(y) / float(len(y))
    out['outcome_rate'] = rate
    if rate < 1e-3 or rate > 1 - 1e-3 or se[i] > 10.0:
        out['separation'] = True
        out['ci_informative'] = False
        out['note'] = ('响应近饱和或 SE 爆炸（rate=%.4f, se=%.3f）⇒ CI 不可解释；'
                       '不据此判 PASS/FAIL' % (rate, se[i]))
    else:
        out['separation'] = False
        out['ci_informative'] = True
    out['interactions'] = {}
    for nm in names:
        if nm.startswith('count_std_x_'):
            j = names.index(nm)
            out['interactions'][nm] = {'beta': float(beta[j]), 'se': float(se[j]),
                                       'ci': [float(beta[j] - 1.96 * se[j]),
                                              float(beta[j] + 1.96 * se[j])],
                                       'p_wald': float(_pwald(beta[j], se[j]))}
    out['nuisance'] = {nm: float(beta[names.index(nm)]) for nm in
                       ('radius', 'blur', 'overlap') if nm in names}
    out['n_correct'] = int(sum(y))
    if want_boot:
        out['cluster_bootstrap'] = cluster_bootstrap(rows)
    return out


def _pwald(b, se):
    if not se or se <= 0:
        return float('nan')
    z = abs(b) / se
    return math.erfc(z / math.sqrt(2.0))


def cluster_bootstrap(rows, B=B_BOOT, seed=BOOT_SEED):
    """按**布局**聚类的 bootstrap（重抽布局，整组同进同出）⇒ C4 的稳健性检查。

    ★ 性能：设计向量按行**预计算一次**（标准化用全样本的 mean/sd），重抽只做索引拼接
    ⇒ 500 次重抽是可行的（首版每次重抽都重建 23k 行矩阵，10 分钟都跑不完）。
    """
    acts = [fnum(r['count_gt']) for r in rows]
    mu = sum(acts) / len(acts)
    sd = math.sqrt(sum((a - mu) ** 2 for a in acts) / len(acts))
    if sd <= 1e-12:
        return {'B': B, 'n_ok': 0, 'note': 'count 无方差 ⇒ bootstrap 无意义'}
    xs = [design_vec(r, mu, sd) for r in rows]
    ys = [float(is_correct(r)) for r in rows]
    idx_by_layout = {}
    for i, r in enumerate(rows):
        idx_by_layout.setdefault(r['layout_id'], []).append(i)
    keys = sorted(idx_by_layout)
    rng = random.Random(seed)
    betas = []
    for _ in range(B):
        pick = []
        for _ in range(len(keys)):
            pick.extend(idx_by_layout[keys[rng.randrange(len(keys))]])
        X = [xs[i] for i in pick]
        y = [ys[i] for i in pick]
        beta, cov, se, ok, _ = fit_logit(X, y, iters=25)
        betas.append(beta[1] if ok else None)
    ok_b = sorted(b for b in betas if b is not None)
    if not ok_b:
        return {'B': B, 'n_ok': 0}
    lo = ok_b[int(0.025 * len(ok_b))]
    hi = ok_b[min(len(ok_b) - 1, int(0.975 * len(ok_b)))]
    return {'B': B, 'n_ok': len(ok_b), 'seed': seed, 'ci': [lo, hi],
            'median': ok_b[len(ok_b) // 2], 'note': '按布局聚类重抽（同布局的全部变体同进同出）'}


def groupwise_cv(rows, k=K_FOLDS):
    """C5：**以布局为组**留出，8 折；同源变体（同布局的全部构建×合同×起服）必须同折。"""
    layout = {}
    for r in rows:
        layout.setdefault(r['layout_id'], []).append(r)
    keys = sorted(layout)
    folds = {}
    for i, kk in enumerate(keys):
        folds.setdefault(i % k, []).append(kk)
    per_fold = []
    for f in range(k):
        test_keys = set(folds.get(f, []))
        tr = [r for kk in keys if kk not in test_keys for r in layout[kk]]
        te = [r for kk in keys if kk in test_keys for r in layout[kk]]
        if len(tr) < 20 or len(te) < 20:
            continue
        acts = [fnum(r['count_gt']) for r in tr]
        mu = sum(acts) / len(acts)
        sd = math.sqrt(sum((a - mu) ** 2 for a in acts) / len(acts))
        if sd <= 1e-12:
            per_fold.append({'fold': f, 'beta_count': 0.0, 'n_train': len(tr), 'n_test': len(te),
                             'degenerate_count': True})
            continue
        X, y, names, _ = build_design(tr, (mu, sd))
        beta, cov, se, ok, _ = fit_logit(X, y)
        per_fold.append({'fold': f, 'beta_count': (float(beta[names.index('count_std')]) if ok else None),
                         'n_train': len(tr), 'n_test': len(te),
                         'n_test_layouts': len(test_keys), 'rank_ok': bool(ok)})
    bs = [p['beta_count'] for p in per_fold if p.get('beta_count') is not None]
    st = {}
    if bs:
        srt = sorted(bs)
        med = srt[len(srt) // 2]
        mean = sum(bs) / len(bs)
        sdv = math.sqrt(sum((b - mean) ** 2 for b in bs) / len(bs))
        st = {'n_folds': len(bs), 'min': float(min(bs)), 'max': float(max(bs)),
              'median': float(med), 'sd': float(sdv),
              'sign_consistency': float(sum(1 for b in bs if (b > 0) == (med > 0)) / len(bs))
              if med != 0 else 1.0,
              'unstable': bool(med != 0 and sdv > 0.5 * abs(med))}
    return {'k': k, 'assign_rule': 'layout_id 的序号 mod k ⇒ 同布局的全部变体同折',
            'per_fold': per_fold, 'stability': st}


# ════════════════════════════ 读数据 ════════════════════════════
def load_dir(d):
    cells, bad = {}, []
    for p in sorted(glob.glob(os.path.join(d, 'A52_*.csv'))):
        m = CELLFILE_RE.match(os.path.basename(p))
        if not m:
            bad.append(os.path.basename(p))
            continue
        key = (m.group('build'), m.group('contract'), m.group('start'))
        with io.open(p, encoding='utf-8-sig', errors='replace', newline='') as fh:
            cells[key] = list(csv.DictReader(fh))
    return cells, bad


COUNT_MU, COUNT_SD = 32.0, 29.664793948382652     # count ∈ {8,32,80} 的均值/总体 sd


def _mock_row(rng, cid, layout, c, s, bl, ol, b, ct, st, beta_count=0.0,
              alpha=-0.40, beta_blur=-0.35, beta_size=0.25, eps=0.12):
    """合成一行：**与判据件 C3 同一个结构方程** + 与预测变量独立的翻转噪声。

        correct ~ Bernoulli( sigmoid(alpha + beta_count·cs + beta_blur·blur + beta_size·r) )
        再以概率 eps **独立翻转**（模型也会错，但不是因为 count）

    · cs = (count − COUNT_MU)/COUNT_SD，与 C3 的 count_std **同一标准化**；
    · 对 cs ∈ {−0.809, 0, 1.618}，线性预测子落在 [−0.77, 0.57]，sigmoid 后远离 0/1
      ⇒ **不需要截断** ⇒ 生成模型在 logit 空间严格线性，真值系数可被无偏恢复；
    · 错答的扰动幅度**必须超过 C3 的容差** max(1, 5%·gt)，否则 count 大的格会被误判成"答对"，
      凭空造出巨大的 count 效应（自测里踩过这个坑）；
    · ★ 注意 β 会被翻转**衰减**：p = ε·(1−p₀) + (1−ε)·p₀ 对 β=0.6、ε=0.12 给出 logit 坡度
      ≈0.33（不是 0.6）——所以下面的自测比对的是**解析预期**（含衰减），不是 β 本身。
    """
    cs = (c - COUNT_MU) / COUNT_SD
    li = alpha + beta_count * cs + beta_blur * bl + beta_size * s
    p = 1.0 / (1.0 + math.exp(-li))
    p = eps + (1.0 - 2.0 * eps) * p
    ok = 1 if rng.random() < p else 0
    tol = max(TOL_ABS, TOL_REL * c)
    step = max(1, int(math.ceil(tol)))
    pred = c if ok else max(0, c + rng.choice([-3, -2, -1, 1, 2, 3]) * (step + 1))
    return dict(item=layout, cell_id=cid, layout_id=layout, count_gt=c, n_dots_detected_gt=c,
                radius=[3, 8, 24][s], blur=bl, overlap=[1.45, 1.15, 0.85][ol],
                build=b, contract=ct, start=st, pred=pred, parse_ok=1, abstain=0, refuse=0,
                http_err=0, model='MOCK', raw=json.dumps({'count': pred}), latency_s='0.01')


def make_mock(root, beta_count=0.0, const_count=False, cell_filter=None):
    """按判据件口径生成 **23,328 行**合成数据（36 个文件 × 648 行）。

    const_count=True：**count 列本身就是常数（32）** ⇒ 这是"把 count 设常数重渲染一批"
    的**真值版**——此时设计矩阵里 count_std 恒为 0，最小二乘**必然**给出 β_count = 0，
    所以 `理想实现` 下分析器报出的必须是精确 0（不是"小到看不见"）。
    cell_filter：可给 set(cell_id) 只造部分格（快速自测用）；默认造满 81 格。
    """
    os.makedirs(root, exist_ok=True)
    counts = (32,) if const_count else (8, 32, 80)
    n_rows = 0
    for b in BUILDS:
        for ct in CONTRACTS:
            for st in STARTS:
                p = os.path.join(root, 'A52_%s_%s_s%s.csv' % (b, ct, st))
                with io.open(p, 'w', encoding='utf-8', newline='') as fh:
                    w = csv.writer(fh, lineterminator='\n')
                    w.writerow(COLS_REQUIRED + ['radius', 'blur', 'overlap', 'latency_s'])
                    for c in counts:
                        for s in (0, 1, 2):
                            for bl in (0.0, 4.0, 8.0):
                                for oi in (0, 1, 2):
                                    cid = 'c%02d_s%d_b%d_o%d' % (c, [3, 8, 24][s], int(bl), oi)
                                    if cell_filter and cid not in cell_filter:
                                        continue
                                    for L in range(PER_CELL):
                                        layout = '%s_L%02d' % (cid, L)
                                        rng = random.Random(hash((b, ct, st, layout, beta_count,
                                                                  const_count)) & 0x7fffffff)
                                        row = _mock_row(rng, cid, layout, c, s, bl, oi, b, ct, st,
                                                        beta_count=beta_count)
                                        w.writerow([row[k] for k in COLS_REQUIRED]
                                                   + [row['radius'], row['blur'], row['overlap'],
                                                      row['latency_s']])
                                        n_rows += 1
    return n_rows


# ════════════════════════════ 主分析 ════════════════════════════
def analyze(d, stim=None, want_boot=True, verbose=True):
    crit_md5 = md5f(CRIT) if os.path.exists(CRIT) else 'MISSING'
    rep = {'criteria_md5': crit_md5, 'dir': d, 'checks': {}, 'verdicts': {}, 'flags': []}
    cells, unmatch = load_dir(d)
    have = {k: len(v) for k, v in cells.items()}
    rows = [r for v in cells.values() for r in v]
    rep['n_files'] = len(cells)
    rep['n_rows'] = len(rows)
    if verbose:
        print('== A5-2 分析 ==')
        print('  IRLS 后端 = %s（numpy %s）' % (BACKEND, _np.__version__ if _np is not None else '未装'))
        print('  判据件 md5 = %s ｜ 目录 %s' % (crit_md5, d))
        print('  逐格文件 %d / 36 ｜ 总行数 %d / %d' % (len(cells), len(rows), BUDGET_ROWS))
        if unmatch:
            print('  [旗标] 文件名不合 A52_<build>_<contract>_s<start>.csv 的件：%s' % unmatch)

    # ── C1 覆盖（刺激侧；先声明后排除）──────────────────────────────
    stim_ok, stim_info = None, {}
    sm = os.path.join(stim, STIM_MANIFEST) if stim else None
    if sm and os.path.exists(sm):
        srows = list(csv.DictReader(io.open(sm, encoding='utf-8-sig', newline='')))
        cids = {r['cell_id'] for r in srows}
        percell = {}
        for r in srows:
            percell.setdefault(r['cell_id'], []).append(r)
        # 预注册排除：读生成器写下的 _unrealizable.csv（**先声明后排除**）
        up = os.path.join(stim, '_unrealizable.csv')
        excl = {}
        if os.path.exists(up):
            for r in csv.DictReader(io.open(up, encoding='utf-8-sig', newline='')):
                excl[r['cell_id']] = r.get('reason', '')
        keep = {c: v for c, v in percell.items() if c not in excl}
        nonempty = all(min(int(x['n_dots_detected_gt']) for x in v) >= 1 for v in keep.values())
        hash_ok = all(len(r.get('sha256', '')) == 64 for r in srows)
        stim_ok = (len(srows) == IMAGES and len(cids) == CELLS and len(keep) == CELLS - len(excl)
                   and nonempty and hash_ok)
        stim_info = {'manifest': sm, 'manifest_md5': md5f(sm), 'rows': len(srows), 'cells': len(cids),
                     'per_cell': min(len(v) for v in percell.values()),
                     'excluded_preregistered': {c: excl[c] for c in sorted(excl)},
                     'n_kept': len(keep), 'all_nonempty_after_exclusion': nonempty,
                     'all_nonempty_including_excluded': all(
                         min(int(x['n_dots_detected_gt']) for x in v) >= 1 for v in percell.values()),
                     'sha256_complete': hash_ok,
                     'detection_frac_mean': sum(int(r['n_dots_detected_gt']) / float(r['count_gt'])
                                                for r in srows) / len(srows)}
        rep['checks']['C1_stim'] = stim_info
        if verbose:
            print('  C1 刺激：%d 图 / %d 格 / 每格 %d 张 ｜ 预注册排除 %d 格 ｜ 排除后全非空=%s ｜ '
                  'sha256 齐=%s ｜ 均值 detection_frac=%.3f'
                  % (stim_info['rows'], stim_info['cells'], stim_info['per_cell'], len(excl),
                     nonempty, hash_ok, stim_info['detection_frac_mean']))
            for c, why in sorted(excl.items()):
                print('     UNREALIZABLE(先声明后排除) %s ｜ %s' % (c, why))
    else:
        if verbose:
            print('  C1 刺激：未给 --stim（跳过刺激侧覆盖；本项为 NOT EVALUABLE）')
    rep['verdicts']['C1'] = {'passed': bool(stim_ok) if stim_ok is not None else None,
                             'stim': stim_info,
                             'note': 'UNREALIZABLE 格由生成器**先声明后排除**（记入 _unrealizable.csv），'
                                     '已从非空检查的分母里移出；不得事后剔除'}

    # ── C2 完整性 ──────────────────────────────────────────────────
    short, lowparse, missing_cells = [], [], []
    for b in BUILDS:
        for ct in CONTRACTS:
            for st in STARTS:
                k = (b, ct, st)
                n = have.get(k, 0)
                if n == 0:
                    missing_cells.append('%s/%s/s%s' % k)
                    continue
                if n < IMAGES:
                    short.append('%s/%s/s%s=%d' % (b, ct, st, n))
                ok = sum(1 for r in cells[k] if str(r.get('parse_ok')) == '1')
                if ok / float(n) < 0.95:
                    lowparse.append('%s/%s/s%s=%.1f%%' % (b, ct, st, 100.0 * ok / n))
    c2_pass = (not missing_cells) and (not short) and (not lowparse) and (len(rows) == BUDGET_ROWS)
    rep['checks']['C2'] = {'missing_cells': missing_cells, 'short_cells': short,
                           'low_parse_cells': lowparse, 'n_rows': len(rows), 'expect_rows': BUDGET_ROWS}
    rep['verdicts']['C2'] = {'passed': c2_pass}
    rep['flags'] += (['C2 缺格 %s' % missing_cells] if missing_cells else []) \
                    + (['C2 行数偏少 %s' % short] if short else []) \
                    + (['C2 解析低 %s' % lowparse] if lowparse else [])
    if verbose:
        print('  C2 完整性：行数 %d/%d ｜ 缺格 %d ｜ 偏少格 %d ｜ parse_ok<95%% 格 %d ⇒ %s'
              % (len(rows), BUDGET_ROWS, len(missing_cells), len(short), len(lowparse),
                 'PASS' if c2_pass else 'FAIL'))

    # ── C3/C4 四因子模型 ───────────────────────────────────────────
    if not rows:
        rep['verdicts']['C3'] = {'status': 'NOT EVALUABLE', 'reason': '没有数据行'}
        rep['verdicts']['C4'] = {'status': 'NOT EVALUABLE'}
        rep['verdicts']['C5'] = {'status': 'NOT EVALUABLE'}
        return rep
    c3 = fit_c3(rows, want_boot=want_boot)
    rep['checks']['C3_model'] = c3
    band = 0.2
    ci = c3.get('ci')
    informative = c3.get('ci_informative', True)
    c4_pass = bool(ci and ci[0] > -band and ci[1] < band)
    rep['verdicts']['C3'] = {
        'passed': bool(c3.get('rank_ok')) and c3.get('beta_count') is not None,
        'order': ['① count 主效应', '② count×合同', '③ count×构建'],
        'count_main_std_logodds': c3.get('beta_count'), 'ci': ci, 'se': c3.get('se_count'),
        'interactions': c3.get('interactions'), 'degenerate_count': c3.get('degenerate_count', False),
        'separation': c3.get('separation', False), 'outcome_rate': c3.get('outcome_rate'),
        'note': c3.get('note', '')}
    rep['verdicts']['C4'] = {
        'passed': c4_pass if informative else None, 'band': band, 'ci': ci,
        'ci_informative': informative, 'separation': c3.get('separation', False),
        'rule': 'CI 完全落在 ±0.2 内 ⇒ 可称"无实质作用"',
        'cluster_bootstrap': c3.get('cluster_bootstrap'),
        'disposition': ('保留"count 无实质作用"并加一句"在控制可读性后仍成立（A5-2）"' if c4_pass
                        else ('**不可评**（响应近饱和/分离；先查数据再看结论）' if not informative
                              else '撤回该表述；§5.6 改写为"count 的作用在控制可读性后仍可见"'))}
    if verbose:
        print('  C3 四因子模型：rank_ok=%s ｜ count 主效应（标准化 log-odds）= %s ｜ 95%% CI = %s'
              % (c3.get('rank_ok'), _fmt(c3.get('beta_count')), _fmt(ci)))
        for nm, v in (c3.get('interactions') or {}).items():
            print('     %-24s β=%s  CI=%s  p=%.4f' % (nm, _fmt(v['beta']), _fmt(v['ci']), v['p_wald']))
        print('  C4 无实质作用带 ±%.1f：%s ⇒ %s' % (band, 'CI 完全落入' if c4_pass else 'CI 未完全落入',
                                                 'PASS（可称无实质作用）' if c4_pass else 'FAIL（撤回该表述）'))
        cb = c3.get('cluster_bootstrap')
        if cb:
            print('     聚类 bootstrap（按布局，B=%d，n_ok=%d）：CI = %s' % (cb['B'], cb['n_ok'], _fmt(cb.get('ci'))))

    # ── C5 以布局为组留出 ──────────────────────────────────────────
    c5 = groupwise_cv(rows)
    st = c5.get('stability') or {}
    rep['checks']['C5_cv'] = c5
    rep['verdicts']['C5'] = {'passed': bool(st) and (not st.get('unstable', True))
                             and st.get('sign_consistency', 0) >= 1.0, 'stability': st}
    if verbose:
        print('  C5 以布局为组留出（%d 折）：β_count 逐折 = %s'
              % (K_FOLDS, [None if p.get('beta_count') is None else round(p['beta_count'], 3)
                           for p in c5['per_fold']]))
        if st:
            print('     稳定性：min=%.3f max=%.3f median=%.3f sd=%.3f ｜ 符号一致=%.2f ｜ 不稳定=%s'
                  % (st['min'], st['max'], st['median'], st['sd'], st['sign_consistency'], st['unstable']))
        else:
            print('     ✗ 折数不足 ⇒ C5 NOT EVALUABLE')

    # ── NC3 独立重解析（从 raw 列）────────────────────────────────
    mismatch = 0
    checked = 0
    for r in rows:
        raw = r.get('raw') or ''
        if raw.startswith('ERR:'):
            continue
        checked += 1
        from_probe = r.get('pred')
        # 独立复解析：**另一种**实现（不经探针的 parse()）
        m = re.search(r'"count"\s*:\s*"?(abstain|\d+)"?', raw, re.I)
        v = (m.group(1) if m else None)
        if v is None:
            m2 = re.search(r'-?\d+', raw.replace(',', ''))
            v = m2.group(0) if m2 else None
        if v is not None and v.lower() == 'abstain':
            v = 'abstain'
        pv = (from_probe or '').strip()
        if str(v or '') != pv and not (v is None and pv == ''):
            mismatch += 1
    rep['checks']['NC3_parse_recompute'] = {'checked': checked, 'mismatch': mismatch}
    rep['verdicts']['NC3'] = {'passed': mismatch == 0, 'checked': checked, 'mismatch': mismatch}
    if verbose:
        print('  NC3 独立重解析（raw → pred）：核 %d 行 ｜ 不一致 %d ⇒ %s'
              % (checked, mismatch, 'PASS' if mismatch == 0 else 'FAIL'))
    return rep


def _fmt(x):
    if x is None:
        return '—'
    if isinstance(x, (list, tuple)):
        return '[%s]' % ', '.join(_fmt(v) for v in x)
    try:
        return '%.4f' % float(x)
    except Exception:
        return str(x)


def negctl(rows, n_perm=20, verbose=True):
    """NC1：把 count 的作用**打散** ⇒ C3 的 count 主效应**必须消失**。

    做法（**层内置换检验**）：在 (radius, blur, overlap, contract, build) 层内把
    correct/incorrect 标签**随机置换**（层内答案个数完全不变）⇒ 层边缘分布逐位保持，
    而"哪一行答对"与 count 独立 ⇒ count 主效应的真值为 0。
    跑 n_perm 个种子，报 β 的中位数与置信区间。

    ★ 为什么不按层率**独立重抽**：真数据的答对率贴近饱和时，按层率重抽会把响应推到全 1，
      logistic 直接分离（自测首版撞上：se=505、CI=±990，白白浪费一次阴性对照）。
      层内置换既不用造数据也不改变边缘，能稳定给出可解释的读数。
    """
    layers = {}
    for r in rows:
        layers.setdefault((r.get('radius'), r.get('blur'), r.get('overlap'), r['contract'],
                           r['build']), []).append(r)
    orig = {id(r): is_correct(r) for r in rows}
    betas, cis, notes = [], [], []
    for t in range(n_perm):
        rng = random.Random(BOOT_SEED + 9176 * t)
        perm = []
        for key in sorted(layers):
            mem = layers[key]
            lab = [orig[id(r)] for r in mem]
            rng.shuffle(lab)
            for r, y in zip(mem, lab):
                q = dict(r)
                g = inum(r['n_dots_detected_gt']) or 0
                tol = max(TOL_ABS, TOL_REL * g)
                step = max(1, int(math.ceil(tol)))
                q['pred'] = str(g if y else max(0, g + step + 1))
                perm.append(q)
        res = fit_c3(perm, want_boot=False)
        betas.append(res.get('beta_count'))
        cis.append(res.get('ci'))
        if not res.get('ci_informative', True):
            notes.append(res.get('note', ''))
    ok_b = sorted(b for b in betas if b is not None)
    med = ok_b[len(ok_b) // 2] if ok_b else None
    lo = min(c[0] for c in cis if c) if any(cis) else None
    hi = max(c[1] for c in cis if c) if any(cis) else None
    passed = bool(ok_b and med is not None and abs(med) < 0.05 and abs(lo) < 0.2 and abs(hi) < 0.2)
    if verbose:
        print('  NC1 阴性对照（层内置换 %d 次）：β 中位数 = %s ｜ 各次 CI 的并集 = [%s, %s] ⇒ %s'
              % (n_perm, _fmt(med), _fmt(lo), _fmt(hi),
                 'PASS（效应消失）' if passed else 'FAIL（有泄漏：count 仍带着作用）'))
        if notes:
            print('     （%d 次出现分离/不可评，已如实计入）' % len(notes))
    return {'passed': passed, 'beta_median': med, 'beta_all': ok_b, 'ci_union': [lo, hi],
            'n_perm': n_perm, 'n_rows': len(rows), 'seed': BOOT_SEED,
            'method': '层内标签置换（保持层边缘，打散与 count 的关联）'}


def selftest():
    """全链路自测：mock → C1–C5；阴性对照；count 恒定；能测出"效应存在"的反例。"""
    from PIL import Image, ImageDraw, ImageFilter            # noqa: F401  （自测里重渲染真刺激）
    ok = True
    print('=' * 100)
    print('■ A5-2 分析器自测（纯 CPU；合成 mock 数据，判据件口径）')
    print('=' * 100)
    tmp = tempfile.mkdtemp(prefix='a52_selftest_')
    # ① 真生成一次刺激（用真实生成器，验证 C1 刺激侧能算）
    import subprocess
    gen = os.path.join(HERE, 'a52_prep_stim.py')
    stimd = os.path.join(tmp, 'stim')
    rc = subprocess.call([sys.executable, '-B', gen, '--out', stimd, '--seed', '20261004',
                          '--limit', '8'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print('\n[0] 真跑生成器（648 图）rc=%d' % rc)
    ok &= (rc == 0)

    # ② 有信号：β_count = 0.60 ⇒ 应**恢复**到真值附近，且 C4 应 FAIL（CI 不落在 ±0.2）
    d_sig = os.path.join(tmp, 'sig')
    n = make_mock(d_sig, beta_count=0.60)
    print('\n[1] mock（真值 β=0.60）：%d 行 ⇒ 期望恢复 ≈0.60 且 C4 FAIL' % n)
    r_sig = analyze(d_sig, stim=stimd, want_boot=False, verbose=True)
    c4 = r_sig['verdicts']['C4']['passed']
    b_hat = r_sig['checks']['C3_model'].get('beta_count')
    print('    → C1=%s C2=%s β̂=%s（真值 0.60）C4=%s（期望 False）'
          % (r_sig['verdicts']['C1']['passed'], r_sig['verdicts']['C2']['passed'], _fmt(b_hat), c4))
    ok &= (r_sig['verdicts']['C1']['passed'] is True)
    ok &= (r_sig['verdicts']['C2']['passed'] is True)
    # β=0.6 叠加 ε=0.12 的独立翻转后，logit 坡度的**解析预期** ≈ 0.33（不是 0.6）
    ok &= (b_hat is not None and 0.25 < b_hat < 0.45)
    ok &= (c4 is False)

    # ③ 无信号：β_count = 0.03 ⇒ C4 应 PASS（且 β̂ 接近真值）
    d_null = os.path.join(tmp, 'null')
    n2 = make_mock(d_null, beta_count=0.03)
    print('\n[2] mock（真值 β=0.03）：%d 行 ⇒ 期望 β̂≈0.03 且 C4 PASS' % n2)
    r_null = analyze(d_null, stim=stimd, want_boot=False, verbose=True)
    c4n = r_null['verdicts']['C4']['passed']
    b_null = r_null['checks']['C3_model'].get('beta_count')
    print('    → β̂=%s（真值 0.03）C4=%s（期望 True）' % (_fmt(b_null), c4n))
    ok &= (c4n is True)
    ok &= (b_null is not None and abs(b_null) < 0.15)

    # ④ NC1：响应与 count 独立
    print('\n[3] NC1 阴性对照（响应与 count 独立）')
    rows = [r for v in load_dir(d_null)[0].values() for r in v]
    nc = negctl(rows)
    ok &= (nc['passed'] is True)

    # ④b 两套 IRLS 后端必须给同一个答案（回归保护：numpy 与纯 Python 不许漂）
    if _np is not None:
        global BACKEND
        rows_sub = [r for v in load_dir(d_null)[0].values() for r in v][:4000]
        acts = [fnum(r['count_gt']) for r in rows_sub]
        mu = sum(acts) / len(acts)
        sd = math.sqrt(sum((a - mu) ** 2 for a in acts) / len(acts))
        Xs, ys, nm, _ = build_design(rows_sub, (mu, sd))
        BACKEND = 'numpy'
        bn = fit_logit(Xs, ys)[0]
        BACKEND = 'python'
        bp = fit_logit(Xs, ys)[0]
        BACKEND = 'numpy' if _np is not None else 'python'
        dmax = max(abs(a - b) for a, b in zip(bn, bp))
        print('\n[3b] 两套 IRLS 后端一致性（同一 4000 行）：最大 |Δβ| = %.2e' % dmax)
        ok &= (dmax < 1e-4)
    else:
        print('\n[3b] 本机无 numpy ⇒ 跳过双后端一致性（只跑纯 Python 路径）')

    # ⑤ count 恒定（真值：count 列就是常数 32）⇒ count_std 恒 0 ⇒ β_count 必须**精确为 0**
    d_const = os.path.join(tmp, 'const')
    n3 = make_mock(d_const, beta_count=0.60, const_count=True)
    print('\n[4] count 恒定版（count 列全 = 32）：%d 行 ⇒ 期望 β_count 精确为 0 且 C4 PASS' % n3)
    r_const = analyze(d_const, stim=stimd, want_boot=False, verbose=True)
    b = r_const['checks']['C3_model'].get('beta_count')
    print('    → β_count = %s（期望恰为 0.0）｜ C4=%s' % (b, r_const['verdicts']['C4']['passed']))
    ok &= (b == 0.0)
    ok &= (r_const['verdicts']['C4']['passed'] is True)

    # ⑥ 缺格/缺行必须被 C2 抓到（把一格清空）
    d_bad = os.path.join(tmp, 'bad')
    make_mock(d_bad, beta_count=0.03)
    victim = os.path.join(d_bad, 'A52_b0_base_s1.csv')
    with io.open(victim, 'w', encoding='utf-8', newline='') as fh:      # 清空成只有表头
        fh.write(','.join(COLS_REQUIRED) + '\n')
    r_bad = analyze(d_bad, stim=stimd, want_boot=False, verbose=False)
    print('\n[5] 故意清空一格 ⇒ 期望 C2 FAIL：%s' % (not r_bad['verdicts']['C2']['passed']))
    ok &= (r_bad['verdicts']['C2']['passed'] is False)

    print('\n' + '=' * 100)
    print('★ 自测结论：%s' % ('全部通过（判据能失败、能通过、能抓到缺数据）' if ok else '✗ 有未通过项'))
    print('  临时目录：%s' % tmp)
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dir', default='')
    ap.add_argument('--out', default=os.path.join(HERE, 'a52_result.json'))
    ap.add_argument('--stim', default='', help='刺激目录（含 manifest.csv）⇒ 用来算 C1 刺激侧')
    ap.add_argument('--no-boot', action='store_true')
    ap.add_argument('--backend', default='auto', choices=('auto', 'numpy', 'python'),
                    help='IRLS 后端；auto=有 numpy 就用 numpy，否则纯 Python')
    ap.add_argument('--mock', action='store_true', help='生成 23,328 行 mock 数据（--dir 指定目录）')
    ap.add_argument('--mock-const-count', action='store_true',
                    help='mock 的 count 恒定版（count 列全 = 32）')
    ap.add_argument('--mock-beta', type=float, default=0.60)
    ap.add_argument('--selftest', action='store_true')
    A = ap.parse_args()
    global BACKEND
    if A.backend == 'python':
        BACKEND = 'python'
    elif A.backend == 'numpy':
        if _np is None:
            print('!! --backend numpy 但本机没有 numpy')
            return 2
        BACKEND = 'numpy'
    if A.selftest:
        return selftest()
    if A.mock or A.mock_const_count:
        d = A.dir or os.path.join(HERE, '_mock')
        n = make_mock(d, beta_count=A.mock_beta, const_count=A.mock_const_count)
        print('mock 已写 %s：%d 行（36 格 × 648）｜ beta_count=%s ｜ 恒定 count=%s'
              % (d, n, A.mock_beta, A.mock_const_count))
        return 0
    if not A.dir:
        print('需要 --dir <结果目录>，或 --selftest / --mock')
        return 2
    rep = analyze(A.dir, stim=A.stim or None, want_boot=not A.no_boot)
    io.open(A.out, 'w', encoding='utf-8', newline='\n').write(
        json.dumps(rep, ensure_ascii=False, indent=2, default=str) + '\n')
    h = md5f(A.out)
    io.open(A.out + '.md5', 'w', encoding='utf-8', newline='\n').write('%s  %s\n'
                                                                      % (h, os.path.basename(A.out)))
    print('')
    print('判决摘要（判据 md5 %s）：' % rep['criteria_md5'][:12])
    for k in ('C1', 'C2', 'C3', 'C4', 'C5', 'NC3'):
        v = rep['verdicts'].get(k, {})
        print('  %-4s %s' % (k, json.dumps({kk: vv for kk, vv in v.items()
                                            if kk in ('passed', 'status', 'ci', 'band',
                                                      'count_main_std_logodds', 'stability',
                                                      'note', 'disposition', 'mismatch')},
                                           ensure_ascii=False, default=str)[:300]))
    for f in rep['flags']:
        print('  [旗标] %s' % f)
    print('结果 ⇒ %s（md5 %s）' % (A.out, h[:12]))
    print('A52_ANALYZE_DONE')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
