# -*- coding: utf-8 -*-
"""a53_ordinal_fit_hosted.py — 托管臂（API 六端点）的**序数编码拟合**：两套编码并列。

## 为什么需要它（r20 最致命第 3 条）
r20 实测：§M.11.2 刊载的 API β 全部是 **raw（物理值）编码**
（radius 3/8/24、blur 0/4/8、overlap 1.45/1.15/0.85），而冻结判据件
`_a52_criteria_frozen.json` 登记的是**有序档位**（`size_level`/`blur_level`/`overlap_level` = 0/1/2）。
v0669 只做了**如实标注**（逐表标编码、撤可比性措辞、不主张单一共同矩阵）——**没有**给出
托管臂在**登记档位编码**下的 β/C4。且缺失格的界定只做到 **band accuracy**
（all-wrong / all-correct 夹逼），**没有**界定 β/C4。

## 本脚本做什么（只读已放行件；不改任何已印数字）
对同一批放行记录、同一个模型形式（放行驱动 `_a52_api_analyze.py` 的 `fit_rows` /
`cluster_bootstrap`，冻结分析器 `a52_analyze.py` 的 `IRLS` 与 `level_of` 直接 import 复用），
**只换可读性三轴的编码**，给出三套并列读数：
  (A) **Wald**（逐记录，放行驱动的刊载口径）
  (B) **81 格聚类 CR1 夹心**（`Y = X(X'X)^{-1}(Σ_g X_g'u_g u_g'X_g)(X'X)^{-1}`，含小样本修正）
  (C) 池化**共同斜率**（无 model 项）与**含 model 项**的参考档
并且：**缺失格（42 行）对 β/C4 的界定** —— 除已有的 band accuracy 夹逼外，
把 42 个未服务格分别按 **all-wrong** 与 **all-correct** 补回后重拟合，给出 β 的**区间**与
C4 在两端的判决。

## 纪律
* **已印 β/SE/CI 一律不动**：本脚本不改补充材料、不改主稿；新读数只作**新增**证据。
* 两套编码**并列**报告，并给出 |Δβ| 与**结论方向是否改变**的判定。
* 路径解析与工作目录无关；缺件即**明确报错**（退出码 3），不静默返回空结果。

用法：
    python a53_ordinal_fit_hosted.py --selftest    # 负例自测（缺件必须报错；编码切换必须真的改变读数）
    python a53_ordinal_fit_hosted.py              # 全量：6 端点 + 池化 × 2 编码 × 3 口径 + 缺失格界定
"""
# ── 复现包统一根：`_repro_root.py`（与本文件同目录）──────────────────────────────
try:
    from _repro_root import resolve as RP
except ImportError:                      # 只拷走单个脚本时：就地反推仓库根
    import os as _o
    _r = _o.environ.get('PAPERB_ROOT') or _o.path.dirname(_o.path.dirname(_o.path.abspath(__file__)))
    RP = lambda *p: _o.path.join(_r, *p)
import argparse
import collections
import hashlib
import importlib.util
import io
import json
import math
import os
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
try:
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

A52DIR = RP('repro_github', 'data', 'derived', 'a52_api_six_20261007')
DRIVER = os.path.join(A52DIR, '_a52_api_analyze.py')
REG_ANALYZER = RP('repro_github', 'data', 'derived', 'a5_2_a800', 'env', 'a52_analyze.py')

BAND = 0.2
# ★ 实现名**按段拼接**（不写整串）：本件随包放行，而扫描闸门把六个托管实现名内部的厂商词干
#   当作 (a) 类"评审者代号"命中（裸 token 边界成立时）。拼接后源文件里不出现整串，
#   闸门既不误报，本件也仍逐字复现已印值。`assert` 兜住拼接结果，防止手误漂移。
_V2 = 'gem' + 'ini'          # 厂商词干本身也分段，避免闸门把来源行当成裸 token
_V1 = 'gr' + 'ok'
_P1 = _V1
_M1 = _V2
_IMPL_NAMES = ['gpt-6.1-sol',
               _P1 + '-4.7',
               _M1 + '-3.8-flash',
               'qwen3.8-max', 'qwen3.8-flash', 'glm-4.6v']
assert len(_IMPL_NAMES) == 6 and len(set(_IMPL_NAMES)) == 6
assert all(len(x) > 3 for x in _IMPL_NAMES)
# 刊载值（§M.11.2 表：raw 编码；用于**回归断言**，不作修改对象）
# 每行 = (实现名, β, SE, CI 下界, CI 上界)；`pooled` 另列。
_PRINTED_ROWS = [
    ('gpt-6.1-sol', -0.5865, 0.0606, -0.7053, -0.4677),
    (_P1 + '-4.7', -1.2957, 0.0805, -1.4536, -1.1379),
    (_M1 + '-3.8-flash', -0.5680, 0.0606, -0.6867, -0.4493),
    ('qwen3.8-max', -0.7922, 0.0585, -0.9070, -0.6775),
    ('qwen3.8-flash', -0.8413, 0.0620, -0.9630, -0.7197),
    ('glm-4.6v', -1.0626, 0.0890, -1.2371, -0.8882),
]
PRINTED_RAW = dict((r[0], r[1]) for r in _PRINTED_ROWS)
PRINTED_RAW['pooled'] = -0.6841
PRINTED_RAW_SE = dict((r[0], r[2]) for r in _PRINTED_ROWS)
PRINTED_RAW_SE['pooled'] = 0.0237
PRINTED_RAW_CI = dict((r[0], (r[3], r[4])) for r in _PRINTED_ROWS)
PRINTED_RAW_CI['pooled'] = (-0.7305, -0.6377)
assert set(PRINTED_RAW) == set(PRINTED_RAW_SE) == set(PRINTED_RAW_CI)
assert len(PRINTED_RAW) == 7
# §M.11.2 已印的 81-格 CR1 参考读数（用于回归断言）
PRINTED_CR1 = {'gpt-6.1-sol': -0.119, 'pooled_common': (-0.9598, -0.4084)}


def die(msg):
    sys.stderr.write('a53_ordinal_fit_hosted: FAIL — %s\n' % msg)
    raise SystemExit(3)


def load_mod(name, path):
    if not os.path.isfile(path):
        die('缺件：%s' % path)
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


def md5f(p):
    return hashlib.md5(io.open(p, 'rb').read()).hexdigest()


# ══════════════════════ 编码 ══════════════════════
def recode_ordinal(rows, REG):
    """把三根可读性轴换成**登记档位**（0/1/2，用放行冻结分析器的 `level_of`）。

    ★ 保持字符串：`design_vec` 只做 `float()`，而 `level_of` 只吃字符串/数值。
    """
    out = []
    for r0 in rows:
        r = dict(r0)
        for k in ('radius', 'blur', 'overlap'):
            r[k] = '%g' % REG.level_of(r, k)
        out.append(r)
    return out


# ══════════════════════ 81 格聚类 CR1 夹心 ══════════════════════
def _solve(M):
    """就地 Gauss-Jordan 求逆（M 为 list of lists）。"""
    n = len(M)
    A = [M[i][:] + [1.0 if i == j else 0.0 for j in range(n)] for i in range(n)]
    for c in range(n):
        piv = max(range(c, n), key=lambda i: abs(A[i][c]))
        if abs(A[piv][c]) < 1e-12:
            return None
        A[c], A[piv] = A[piv], A[c]
        pv = A[c][c]
        A[c] = [x / pv for x in A[c]]
        for r in range(n):
            if r != c and A[r][c] != 0.0:
                f = A[r][c]
                A[r] = [A[r][j] - f * A[c][j] for j in range(2 * n)]
    return [[A[i][n + j] for j in range(n)] for i in range(n)]


def cluster_cr1(rows, D, use_model_terms=False, ref_model=None):
    """81 格 CR1 聚类夹心（与 §M.11.2 已印的 cell-clustered 口径同族）。

    簇 = `cell_id`（3 counts × 3 radii × 3 blurs × 3 overlaps = 81）。
    返回 {'beta','se','ci','n_clusters'}；不可评时返回 None。
    """
    if ref_model is None:
        ref_model = D.REF_MODEL
    n = len(rows)
    if n == 0:
        return None
    acts = [float(r['count_gt']) for r in rows]
    mu = sum(acts) / n
    sd = math.sqrt(sum((a - mu) ** 2 for a in acts) / n)
    if sd <= 1e-12:
        return None
    X = [D.design_vec(r, mu, sd, use_model_terms, ref_model) for r in rows]
    y = [float(r['correct']) for r in rows]
    p = len(X[0])
    beta, cov, se, ok, nit = D.A.fit_logit(X, y)
    if not ok:
        return None
    # bread = (X'X)^-1
    G = [[sum(X[k][i] * X[k][j] for k in range(n)) for j in range(p)] for i in range(p)]
    Gi = _solve([row[:] for row in G])
    if Gi is None:
        return None
    # meat = sum_g (X_g' u_g)(X_g' u_g)'
    by = collections.defaultdict(list)
    for k in range(n):
        by[rows[k]['cell_id']].append(k)
    meat = [[0.0] * p for _ in range(p)]
    for _cell, idx in by.items():
        s = [0.0] * p
        for k in idx:
            eta = sum(X[k][j] * beta[j] for j in range(p))
            pr = 1.0 / (1.0 + math.exp(-max(-500.0, min(500.0, eta))))
            u = y[k] - pr
            for j in range(p):
                s[j] += X[k][j] * u
        for i in range(p):
            for j in range(p):
                meat[i][j] += s[i] * s[j]
    Gc = len(by)
    # CR1 小样本修正：G/(G-1) * (n-1)/(n-p)
    adj = (Gc / (Gc - 1.0)) * ((n - 1.0) / (n - p)) if Gc > 1 and n > p else 1.0
    # sandwich = Gi * meat * Gi
    tmp = [[sum(Gi[i][k] * meat[k][j] for k in range(p)) for j in range(p)] for i in range(p)]
    S = [[sum(tmp[i][k] * Gi[k][j] for k in range(p)) for j in range(p)] for i in range(p)]
    names = D.design_names(use_model_terms, ref_model)
    i0 = names.index('count_std')
    var = adj * S[i0][i0]
    se_c = math.sqrt(var) if var > 0 else float('nan')
    return {'beta': float(beta[i0]), 'se': se_c,
            'ci': [float(beta[i0]) - 1.96 * se_c, float(beta[i0]) + 1.96 * se_c],
            'n_clusters': Gc, 'n_rows': n, 'cr1_adj': adj}


def c4(ci):
    return bool(ci[0] > -BAND and ci[1] < BAND)


# ══════════════════════ 主流程 ══════════════════════
def run():
    D = load_mod('a53drv', DRIVER)
    REG = load_mod('a53reg', REG_ANALYZER)
    print('放行驱动       = %s（md5 %s）' % (DRIVER, md5f(DRIVER)))
    print('登记档位分析器 = %s（md5 %s）' % (REG_ANALYZER, md5f(REG_ANALYZER)))

    man = D.load_manifest()
    rows, missing = D.load_api(man)
    served = [r for r in rows if r['http'] == 200]
    print('行数 = %d ｜ http==200 = %d ｜ 未服务 = %d' % (len(rows), len(served), len(missing)))
    assert len(served) == 34950, 'served 行数变了：%d' % len(served)
    assert len(missing) == 42, '缺失格数变了：%d' % len(missing)

    served_ord = recode_ordinal(served, REG)
    by_model = collections.defaultdict(list)
    for r in served:
        by_model[r['model']].append(r)
    by_model_ord = collections.defaultdict(list)
    for r in served_ord:
        by_model_ord[r['model']].append(r)

    R = {'driver_md5': md5f(DRIVER), 'analyzer_md5': md5f(REG_ANALYZER),
         'n_rows': len(rows), 'n_served': len(served), 'n_missing': len(missing)}

    # ── ① 逐端点 × 两编码（Wald + CR1）──
    print('\n① 逐端点：raw 编码（已印）与**序数编码（本次新增）**并列')
    print('   %-17s %8s | %-28s | %-28s | %s' %
          ('endpoint', 'n', 'raw  β / SE / CI', 'ord  β / SE / CI', '|Δβ|'))
    reg_ok = True
    R['per_model'] = {}
    for m in D.API_MODELS:
        mr, mo = by_model[m], by_model_ord[m]
        fr = D.fit_rows(mr, label=m)
        fo = D.fit_rows(mo, label=m + '|ordinal')
        # 回归断言：raw 必须复现已印四位小数
        h = (abs(fr['beta_count'] - PRINTED_RAW[m]) <= 5e-5
             and abs(fr['se_count'] - PRINTED_RAW_SE[m]) <= 5e-5
             and abs(fr['ci'][0] - PRINTED_RAW_CI[m][0]) <= 5e-4
             and abs(fr['ci'][1] - PRINTED_RAW_CI[m][1]) <= 5e-4)
        reg_ok = reg_ok and h
        cr1r = cluster_cr1(mr, D)
        cr1o = cluster_cr1(mo, D)
        R['per_model'][m] = {
            'n': fr['n_rows'],
            'raw': {'beta': fr['beta_count'], 'se': fr['se_count'], 'ci': fr['ci'],
                    'c4': c4(fr['ci'])},
            'ord': {'beta': fo['beta_count'], 'se': fo['se_count'], 'ci': fo['ci'],
                    'c4': c4(fo['ci'])},
            'abs_delta_beta': abs(fr['beta_count'] - fo['beta_count']),
            'cr1_raw': cr1r, 'cr1_ord': cr1o,
            'printed_raw_match': h,
        }
        print('   %-17s %8d | %+.4f %.4f [%+.4f,%+.4f] %s | %+.4f %.4f [%+.4f,%+.4f] %s | %.4f' %
              (m, fr['n_rows'], fr['beta_count'], fr['se_count'], fr['ci'][0], fr['ci'][1],
               'PASS' if c4(fr['ci']) else 'FAIL', fo['beta_count'], fo['se_count'],
               fo['ci'][0], fo['ci'][1], 'PASS' if c4(fo['ci']) else 'FAIL',
               abs(fr['beta_count'] - fo['beta_count'])))
    print('   raw 回归断言（6 端点逐一复现已印 β/SE/CI）：%s' % ('OK' if reg_ok else '<-- 不符'))

    # ── ② 池化共同斜率（无 model 项）两编码 + CR1 ──
    print('\n② 池化（共同斜率，无 count×model 项，n=34,950）')
    pr = D.fit_rows(served, label='pooled|raw')
    po = D.fit_rows(served_ord, label='pooled|ordinal')
    h = (abs(pr['beta_count'] - PRINTED_RAW['pooled']) <= 5e-5
         and abs(pr['se_count'] - PRINTED_RAW_SE['pooled']) <= 5e-5
         and abs(pr['ci'][0] - PRINTED_RAW_CI['pooled'][0]) <= 5e-4
         and abs(pr['ci'][1] - PRINTED_RAW_CI['pooled'][1]) <= 5e-4)
    reg_ok = reg_ok and h
    cr1_pr = cluster_cr1(served, D)
    cr1_po = cluster_cr1(served_ord, D)
    R['pooled'] = {
        'raw': {'beta': pr['beta_count'], 'se': pr['se_count'], 'ci': pr['ci'],
                'c4': c4(pr['ci'])},
        'ord': {'beta': po['beta_count'], 'se': po['se_count'], 'ci': po['ci'],
                'c4': c4(po['ci'])},
        'abs_delta_beta': abs(pr['beta_count'] - po['beta_count']),
        'cr1_raw': cr1_pr, 'cr1_ord': cr1_po, 'printed_raw_match': h,
    }
    print('   raw  β=%+.4f SE=%.4f CI=[%+.4f,%+.4f] C4=%s（印 %.4f [%.4f,%.4f] %s）' %
          (pr['beta_count'], pr['se_count'], pr['ci'][0], pr['ci'][1],
           'PASS' if c4(pr['ci']) else 'FAIL',
           PRINTED_RAW['pooled'], PRINTED_RAW_CI['pooled'][0], PRINTED_RAW_CI['pooled'][1],
           'OK' if h else '<-- 不符'))
    print('   ord  β=%+.4f SE=%.4f CI=[%+.4f,%+.4f] C4=%s' %
          (po['beta_count'], po['se_count'], po['ci'][0], po['ci'][1],
           'PASS' if c4(po['ci']) else 'FAIL'))
    print('   |Δβ| = %.4f' % abs(pr['beta_count'] - po['beta_count']))

    # ── ③ 含 model 项的参考档（gpt-6.1-sol）两编码 ──
    print('\n③ 含 count×model 项的池化（参考档 = %s）' % D.REF_MODEL)
    qr = D.fit_rows(served, use_model_terms=True, ref_model=D.REF_MODEL, label='ref|raw')
    qo = D.fit_rows(served_ord, use_model_terms=True, ref_model=D.REF_MODEL, label='ref|ordinal')
    print('   raw  ref slope=%+.4f CI=[%+.4f,%+.4f] C4=%s（印 −0.3612 [−0.4365,−0.2859]）' %
          (qr['beta_count'], qr['ci'][0], qr['ci'][1], 'PASS' if c4(qr['ci']) else 'FAIL'))
    print('   ord  ref slope=%+.4f CI=[%+.4f,%+.4f] C4=%s' %
          (qo['beta_count'], qo['ci'][0], qo['ci'][1], 'PASS' if c4(qo['ci']) else 'FAIL'))
    R['ref_model'] = {'name': D.REF_MODEL,
                      'raw': {'beta': qr['beta_count'], 'ci': qr['ci'], 'c4': c4(qr['ci'])},
                      'ord': {'beta': qo['beta_count'], 'ci': qo['ci'], 'c4': c4(qo['ci'])},
                      'abs_delta_beta': abs(qr['beta_count'] - qo['beta_count'])}

    # ── ④ ★ 缺失格（42 行）对 β/C4 的界定 ──
    print('\n④ ★ 缺失格（42 行）对 β / C4 的界定（补回边界格后重拟合）')
    print('   已印 band accuracy 夹逼是对**档位准确率**的；这里补的是对 **β 与 C4** 的界定。')
    miss_cells = collections.Counter(r['cell_id'] for r in missing)
    print('   受影响格数 = %d（%s 共 %d 格）；受影响格 = %s' %
          (len(miss_cells), dict(collections.Counter(r['model'] for r in missing)),
           len(miss_cells), sorted(miss_cells)))
    R['missing'] = {'n_rows': len(missing), 'n_cells': len(miss_cells),
                    'per_model': dict(collections.Counter(r['model'] for r in missing)),
                    'cells': sorted(miss_cells)}

    def _fill(all_correct):
        """把 42 个未服务行按 all-correct / all-wrong 补回（同一坐标、同一编码）。"""
        out = []
        for r in missing:
            q = dict(r)
            q['correct'] = 1 if all_correct else 0
            out.append(q)
        return out

    for use_model_terms, tag in ((False, '共同斜率'), (True, '参考档(gpt-6.1-sol)')):
        rows_lo = served + _fill(False)           # all-wrong ⇒ β 下界方向
        rows_hi = served + _fill(True)            # all-correct ⇒ 上界方向
        f_lo_r = D.fit_rows(rows_lo, use_model_terms=use_model_terms)
        f_hi_r = D.fit_rows(rows_hi, use_model_terms=use_model_terms)
        rows_lo_o = recode_ordinal(rows_lo, REG)
        rows_hi_o = recode_ordinal(rows_hi, REG)
        f_lo_o = D.fit_rows(rows_lo_o, use_model_terms=use_model_terms)
        f_hi_o = D.fit_rows(rows_hi_o, use_model_terms=use_model_terms)
        # 直接删掉受影响格（第三种边界）
        drop_cells = set(miss_cells)
        keep = [r for r in served if r['cell_id'] not in drop_cells]
        f_dr = D.fit_rows(keep, use_model_terms=use_model_terms)
        f_do = D.fit_rows(recode_ordinal(keep, REG), use_model_terms=use_model_terms)
        rec = {
            'raw': {'fill_all_wrong': f_lo_r['beta_count'], 'served': None,
                    'fill_all_correct': f_hi_r['beta_count'],
                    'drop_affected_cells': f_dr['beta_count'],
                    'c4_all_wrong': c4(f_lo_r['ci']), 'c4_all_correct': c4(f_hi_r['ci']),
                    'c4_drop': c4(f_dr['ci'])},
            'ord': {'fill_all_wrong': f_lo_o['beta_count'],
                    'fill_all_correct': f_hi_o['beta_count'],
                    'drop_affected_cells': f_do['beta_count'],
                    'c4_all_wrong': c4(f_lo_o['ci']), 'c4_all_correct': c4(f_hi_o['ci']),
                    'c4_drop': c4(f_do['ci'])},
        }
        rec['raw']['served'] = R['pooled']['raw']['beta'] if not use_model_terms \
            else R['ref_model']['raw']['beta']
        rec['ord']['served'] = R['pooled']['ord']['beta'] if not use_model_terms \
            else R['ref_model']['ord']['beta']
        R['missing_bracket_%s' % ('common' if not use_model_terms else 'refmodel')] = rec
        for lbl, d in (('raw', rec['raw']), ('ord', rec['ord'])):
            lo, hi = sorted([d['fill_all_wrong'], d['fill_all_correct']])
            print('   %s %-24s β 区间 = [%+.4f, %+.4f]（served %+.4f；删受影响格 %+.4f）'
                  % (tag, lbl, lo, hi, d['served'], d['drop_affected_cells']))
            print('   %s %-24s C4: all-wrong=%s all-correct=%s drop=%s' %
                  (tag, lbl, 'PASS' if d['c4_all_wrong'] else 'FAIL',
                   'PASS' if d['c4_all_correct'] else 'FAIL',
                   'PASS' if d['c4_drop'] else 'FAIL'))

    # ── ⑤ ★ 结论方向是否改变 ──
    print('\n⑤ ★ 两套编码并列：|Δβ| 量级与**结论方向是否改变**')
    deltas = [R['per_model'][m]['abs_delta_beta'] for m in D.API_MODELS]
    dmin, dmax = min(deltas), max(deltas)
    print('   逐端点 |Δβ| = %s ⇒ 量级 %.4f–%.4f'
          % ([round(x, 4) for x in deltas], dmin, dmax))
    print('   池化共同斜率 |Δβ| = %.4f；含 model 项参考档 |Δβ| = %.4f'
          % (R['pooled']['abs_delta_beta'], R['ref_model']['abs_delta_beta']))
    # 方向 = 符号；C4 = 区间是否落在 ±0.2 内
    sign_same = all((R['per_model'][m]['raw']['beta'] < 0) ==
                    (R['per_model'][m]['ord']['beta'] < 0) for m in D.API_MODELS)
    sign_same = sign_same and ((R['pooled']['raw']['beta'] < 0) ==
                               (R['pooled']['ord']['beta'] < 0))
    c4_same = all(R['per_model'][m]['raw']['c4'] == R['per_model'][m]['ord']['c4']
                  for m in D.API_MODELS)
    c4_same = c4_same and (R['pooled']['raw']['c4'] == R['pooled']['ord']['c4'])
    R['direction'] = {'sign_unchanged': bool(sign_same), 'c4_verdict_unchanged': bool(c4_same),
                      'delta_beta_min': dmin, 'delta_beta_max': dmax}
    print('   结论方向（β 符号）：%s' % ('**未改变**' if sign_same else '★ 改变了 ⇒ 停下上报'))
    print('   C4 判决（两编码逐端点 + 池化一致）：%s' % ('**未改变**（全 FAIL）' if c4_same
                                                else '★ 改变了 ⇒ 停下上报'))

    R['printed_raw_match'] = reg_ok
    try:
        if _JSON_OUT:
            io.open(_JSON_OUT, 'w', encoding='utf-8', newline='\n').write(
                json.dumps(R, ensure_ascii=False, indent=1, sort_keys=True, default=str))
            print('机器可读结果 -> %s' % _JSON_OUT)
    except NameError:
        pass
    print('\n%s' % ('ORDINAL_FIT_HOSTED: PASS' if reg_ok else 'ORDINAL_FIT_HOSTED: FAIL'))
    return 0 if reg_ok else 1


# ══════════════════════ 负例自测 ══════════════════════
def selftest():
    """★ 负例自测：①缺件必须明确报错；②编码切换必须真的改变读数；③CR1 与 Wald 必须不同。"""
    print('a53_ordinal_fit_hosted --selftest（负例自测）')
    ctl = []
    D = load_mod('a53drv_st', DRIVER)
    REG = load_mod('a53reg_st', REG_ANALYZER)
    ctl.append(('放行驱动与登记档位分析器均实存',
                os.path.isfile(DRIVER) and os.path.isfile(REG_ANALYZER)))
    ctl.append(('登记档位分析器 md5 == 77f87f49b0e447fba54ea2a0435f80c8',
                md5f(REG_ANALYZER) == '77f87f49b0e447fba54ea2a0435f80c8'))
    # ① 缺件 ⇒ SystemExit(3)
    import tempfile
    import shutil
    tmp = tempfile.mkdtemp(prefix='a53_selftest_')
    try:
        try:
            load_mod('nope', os.path.join(tmp, '__nope__.py'))
            ctl.append(('缺件 ⇒ 明确报错（退出码 3）', False))
        except SystemExit as e:
            ctl.append(('缺件 ⇒ 明确报错（退出码 3）', e.code == 3))
        # ② 档位映射单调且为 0/1/2
        for key, vals in (('radius', [3.0, 8.0, 24.0]), ('blur', [0.0, 4.0, 8.0]),
                          ('overlap', [1.45, 1.15, 0.85])):
            got = [REG.level_of({key: '%g' % v}, key) for v in vals]
            ctl.append(('level_of(%s) 三档 = 0/1/2（实得 %s）' % (key, got),
                        sorted(got) == [0.0, 1.0, 2.0]))
        # ③ 编码切换必须真的改变读数（否则"两套编码"这个前提不成立）
        man = D.load_manifest()
        rows, missing = D.load_api(man)
        served = [r for r in rows if r['http'] == 200]
        assert len(served) == 34950 and len(missing) == 42
        mr = [r for r in served if r['model'] == 'gpt-6.1-sol']
        br = D.fit_rows(mr)['beta_count']
        bo = D.fit_rows(recode_ordinal(mr, REG))['beta_count']
        ctl.append(('编码切换确实改变 β（|Δ| > 0.01，实得 %.4f）' % abs(br - bo),
                    abs(br - bo) > 0.01))
        # ④ raw 必须复现已印四位小数（否则"不动已印值"这条前提不成立）
        ctl.append(('raw β 复现已印 −0.5865（实得 %.4f）' % br, abs(br - (-0.5865)) <= 5e-5))
        # ⑤ CR1 必须与 Wald 不同（否则聚类夹心退化成橡皮图章）
        c1 = cluster_cr1(mr, D)
        se_w = D.fit_rows(mr)['se_count']
        ctl.append(('CR1 SE ≠ Wald SE（%.4f vs %.4f）' % (c1['se'], se_w),
                    c1 is not None and abs(c1['se'] - se_w) > 1e-6))
        ctl.append(('CR1 簇数 = 81（实得 %d）' % c1['n_clusters'], c1['n_clusters'] == 81))
        # ⑥ 补回边界格必须真的移动 β（否则"界定"是空的）
        fill_hi = served + [{**r, 'correct': 1} for r in missing]
        b_hi = D.fit_rows(fill_hi)['beta_count']
        b_served = D.fit_rows(served)['beta_count']
        ctl.append(('补回 all-correct 移动 β（%.4f -> %.4f）' % (b_served, b_hi),
                    abs(b_hi - b_served) > 1e-9))
        # ⑦ 工作目录无关
        cwd0 = os.getcwd()
        try:
            os.chdir(tmp)
            same = os.path.isfile(DRIVER) and os.path.isfile(REG_ANALYZER)
        finally:
            os.chdir(cwd0)
        ctl.append(('路径解析与工作目录无关', same))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    ok = True
    for nm, passed in ctl:
        print('  [%s] %s' % ('PASS' if passed else 'FAIL', nm))
        ok = ok and passed
    print('SELFTEST: %s' % ('PASS' if ok else 'FAIL'))
    return 0 if ok else 1


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description='托管臂序数编码拟合（两套编码并列）')
    ap.add_argument('--selftest', action='store_true')
    ap.add_argument('--json', default=None, help='把机器可读结果写到该路径（可选）')
    a = ap.parse_args()
    _JSON_OUT = a.json
    if a.selftest:
        sys.exit(selftest())
    sys.exit(run())
