# -*- coding: utf-8 -*-
"""a44_split16.py —— **把"检测 τ×尺寸"三个单元按输入尺寸拆开**，看排序/分离检验的功效是否被解开。

## 为什么做（[external-review][external-review] 的 [Δ]，原话）
"增加旋钮单元数——最可行的路径是将**检测阈值在不同输入尺寸下拆为独立单元**
（当前合并为一个 `threshold × input size` 旋钮），可将单元数从 **10 增至约 14–16**。"

原文 §7.3/F.7 的困境是**结构性**的：十单元里被观察到的分离是 **3 vs 7**，
而 3-vs-7 只有 $\\binom{10}{3}=120$ 种赋值 ⇒ 对 9 个枚举分割点做 Bonferroni 后
**最小可达校正 $p = 9/120 = 0.075 > 0.05$** ⇒ **无论间隙多大都不可能显著**。
把三个检测单元各拆成三个（τ@640/@1024/@1536）后单元数为 **16** ⇒
$\\binom{16}{3}=560$ ⇒ 最小可达校正 $p = 15/560 = 0.0268 \\le 0.05$ ⇒ **结构性障碍消失**。

## 本脚本做什么
1. **回归自检**（必须先过）：用原 A44 的单元构造复算出 `a44_result.json` 的 10 个单元
   （iso 跨度与 95% CI 逐位一致），证明本脚本是从原口径**忠实复制**而来，不是"另写一套"；
2. 把三个检测单元**按 `imgsz` 拆开**，得到 **16 单元**，同样算 iso 跨度 + 200 次 bootstrap CI；
3. 对 10 单元与 16 单元**各跑一遍 B2 的分离检验**（枚举切分点 → 找最大间隙 → 置换检验 → 内部重叠），
   并给出各自的"最小可达校正 p"与功效；
4. 冻结 `a44_split16_result.json`（含两套单元表与两套检验结果），供 M.37/F.7/§7.3 引用。

数据源与 A44 **逐字相同**（不改任何冻结产物）。用法：python -u a44_split16.py
"""


# ── 复现包统一根：`_repro_root.py`（与本文件同目录）──────────────────────────────
# RP(*parts) = 作者树相对路径 -> 绝对路径（作者树上原样；放行树上查前缀映射表）；
# NR(*parts) = **未随包发布**的作者侧路径（放行树上落到 _NOT_RELEASED/，使失败可见）。
try:
    from _repro_root import resolve as RP, not_released as NR
except ImportError:                      # 只拷走单个脚本时：就地反推仓库根，无前缀映射表
    import os as _o
    _r = _o.environ.get('PAPERB_ROOT') or _o.path.dirname(_o.path.dirname(_o.path.abspath(__file__)))
    RP = lambda *p: _o.path.join(_r, *p)
    NR = lambda *p: _o.path.join(_r, '_NOT_RELEASED', *p)
import collections
import hashlib
import io
import itertools
import json
import math
import os
import random
import sys

import numpy as np

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
PM = RP('analysis', 'data', 'pod_mirror')
B = NR('@shared', 'work', 'b_harvest_20260917')
W = NR('@shared', 'work')
OUT = RP('analysis', 'work', 'a44_split16_result.json')
ANOM, SENT, SEED, NBOOT = 1e5, 1234567890, 20260918, 200


def load(p):
    return list(csv_dict(p))


def csv_dict(p):
    import csv
    return csv.DictReader(io.open(p, encoding='utf-8-sig', errors='replace'))


def fn(s, d=None):
    try:
        v = float(s)
        return v if math.isfinite(v) else d
    except Exception:
        return d


def unitize(rows, dims, pcol):
    out = collections.defaultdict(dict)
    for r in rows:
        g = fn(r.get('gt')); p = fn(r.get(pcol))
        if g is None or g <= 0 or p is None or p >= ANOM or p == SENT:
            continue
        out[tuple(str(r[d]).strip() for d in dims)][str(r['item']).strip()] = (g, float(p))
    return out


def fit_affine(prs):
    P = np.array([v[1] for v in prs]); G = np.array([v[0] for v in prs])
    A = np.column_stack([P, np.ones_like(P)])
    c, *_ = np.linalg.lstsq(A, G, rcond=None)
    return c[0], c[1]


def pava(x, y):
    o = np.argsort(x, kind='mergesort')
    xs, ys = np.asarray(x)[o], np.asarray(y, float)[o]
    out_v, out_w = [], []
    for k in range(len(ys)):
        out_v.append(ys[k]); out_w.append(1.0)
        while len(out_v) > 1 and out_v[-2] > out_v[-1]:
            v2, w2 = out_v.pop(), out_w.pop()
            v1, w1 = out_v.pop(), out_w.pop()
            nw = w1 + w2
            out_v.append((v1 * w1 + v2 * w2) / nw); out_w.append(nw)
    fit = np.empty(len(ys))
    idx = 0
    for v, ww in zip(out_v, out_w):
        n = int(round(ww))
        fit[idx:idx + n] = v
        idx += n
    return xs, fit


def apply_iso(model, P):
    xs, fit = model
    return np.interp(np.asarray(P, float), xs, fit)


def rho_f(prs):
    g = np.array([v[0] for v in prs], float); p = np.array([v[1] for v in prs], float)
    return (p.mean() - g.mean()) / g.mean() * 100


def run_unit(unit, seed):
    settings = sorted(unit)
    items = sorted(next(iter(unit.values())))
    rb = np.random.RandomState(seed)
    fold = {i: (0 if rb.rand() < 0.5 else 1) for i in items}
    tr = [unit[s][i] for s in settings for i in items if fold[i] == 0]
    iso = pava([v[1] for v in tr], [v[0] for v in tr])
    out = collections.defaultdict(list)
    for s in settings:
        te = [unit[s][i] for i in items if fold[i] == 1]
        out['rho_iso'].append(rho_f([(v[0], float(apply_iso(iso, [v[1]])[0])) for v in te]))
    return out


def span_ci(unit, seed=SEED, nboot=NBOOT):
    sp = float(np.ptp(run_unit(unit, seed)['rho_iso']))
    bs = []
    for k in range(nboot):
        try:
            bs.append(float(np.ptp(run_unit(unit, seed + 1000 + k)['rho_iso'])))
        except Exception:
            pass
    lo, hi = (float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))) if bs else (float('nan'),) * 2
    return sp, lo, hi


# ── 单元构造（与 A44 逐字同源；★ 唯一差别：检测单元可选定是否按 imgsz 拆开） ──────────
def build(split_detector):
    units = []

    def add(lab, kind, u):
        settings = sorted(u)
        if len(settings) < 3:
            return
        common = set.intersection(*[set(u[s]) for s in settings])
        if len(common) < 20:
            return
        units.append((lab, kind, {s: {i: u[s][i] for i in common} for s in settings}))

    det = (('检测·域内 VisDrone', RP('analysis', 'data', 'pod_mirror', 'A', 'det_yolo_ladder_visdrone_det.csv'), 'n_det_person'),
           ('检测·零样本 COCO', RP('analysis', 'data', 'pod_mirror', 'A', 'det_yolo_ladder_yolo12n.csv'), 'n_det_person'),
           ('检测·域内 BBBC005', NR('@shared', 'work', 'b_harvest_20260917', 'bbbc_eval', 'ladder.csv'), 'n_det'))
    for lab, path, pcol in det:
        rows = list(csv_dict(path))
        if not split_detector:
            add(lab + '(全网格)', '检测器 τ×尺寸', unitize(rows, ['tau', 'imgsz'], pcol))
        else:
            u = unitize(rows, ['imgsz', 'tau'], pcol)
            for sz in sorted({k[0] for k in u}):
                sub = {k[1]: v for k, v in u.items() if k[0] == sz}
                add('%s/tau@%s' % (lab, sz), '检测器 τ×尺寸', sub)

    u = unitize(list(csv_dict(NR('@shared', 'work', 'dm_ladder.csv'))), ['dataset', 'protocol', 'value'], 'pred')
    for ds in sorted({k[0] for k in u}):
        add('密度·官方DM/' + ds, '密度输入尺度', {k: v for k, v in u.items() if k[0] == ds})
    for dom in ('visdrone', 'st_a', 'ucf'):
        p = os.path.join(RP('analysis', 'data', 'pod_mirror', 'res_ctrl__ivl'), 'res_ctrl_%s.csv' % dom)
        if os.path.exists(p):
            add('VLM·像素预算/' + dom, 'VLM·视觉侧', unitize(list(csv_dict(p)), ['budget'], 'pred'))
    for tag, p in (('ivl', RP('analysis', 'data', 'pod_mirror', 'b2__out_ivl', 'E1.csv')),
                   ('q32', RP('analysis', 'data', 'pod_mirror', 'b2__out_q32', 'E1.csv'))):
        if os.path.exists(p):
            add('VLM·输出契约/' + tag, 'VLM·语言侧', unitize(list(csv_dict(p)), ['arm'], 'pred'))
    return units


def measure(units, tag):
    out = []
    print('\n' + '=' * 118)
    print('■ %s：%d 个单元（iso 保序校准跨度 + %d 次 bootstrap 95%% CI）' % (tag, len(units), NBOOT))
    print('=' * 118)
    print('%-32s %-16s %5s %9s   %s' % ('单元', '大类', '档位', 'ISO 跨度', '95% CI'))
    for lab, kind, unit in units:
        sp, lo, hi = span_ci(unit)
        n = len(next(iter(unit.values())))
        out.append(dict(lab=lab, kind=kind, n=n, ns=len(unit), iso=sp, iso_lo=lo, iso_hi=hi))
        print('%-32s %-16s %5d %9.1f   [%.1f, %.1f]' % (lab, kind, len(unit), sp, lo, hi), flush=True)
    return out


def split_test(U, tag):
    """B2 的分离检验：枚举切分点 → 最大间隙 → 置换检验 → 高组内部重叠 → 最小可达校正 p。"""
    U = sorted(U, key=lambda r: r['iso'])
    n = len(U)
    # ★ 报出**所有** CI 互不重叠的切分（不只最优）：选"最优"时要靠 `>` 严格比较，
    #   而当多个切分并列时（本轮 16 单元里 k=1 与 k=3 都是 0.2 pp），只报一个会掩盖真相。
    pos = []
    for k in range(1, n):
        gap = min(r['iso_lo'] for r in U[k:]) - max(r['iso_hi'] for r in U[:k])
        if gap > 0:
            pos.append(dict(k=k, gap=round(gap, 1), gap_raw=gap))
    best = max(pos, key=lambda d: d['gap_raw']) if pos else None
    res = dict(tag=tag, n_units=n, kinds=sorted({r['kind'] for r in U}),
               all_positive_gap_splits=[{kk: v for kk, v in d.items() if kk != 'gap_raw'} for d in pos])
    if not best:
        res.update(best_split=None, perm_p=None, min_corrected_p=1.0)
        print('\n  [%s] **没有**任何切分点的 CI 互不重叠 ⇒ 不存在可分离子群' % tag)
        return res, U
    k, gap = best['k'], best['gap_raw']
    N, ge = 20000, 0
    rnd = random.Random(20260924)
    for _ in range(N):
        idx = set(rnd.sample(range(n), k))
        a = [U[i] for i in range(n) if i in idx]
        b = [U[i] for i in range(n) if i not in idx]
        if min(r['iso_lo'] for r in b) - max(r['iso_hi'] for r in a) >= gap:
            ge += 1
    n_assign = math.comb(n, k)
    min_corr = min(1.0, (n - 1) / n_assign)
    # ★ p 用本文自己的约定 (1+ge)/(1+N)（与 m37_ci_power.py 一致），不用 ge/N：
    #   后者在 ge=0 时给出 0.0000，等于声称"p=0"，而 20000 次置换只支持 p ≲ 5e-5。
    p_perm = (1.0 + ge) / (1.0 + N)
    hi = U[k:]
    ov = sum(1 for a, b in zip(hi, hi[1:])
             if min(a['iso_hi'], b['iso_hi']) - max(a['iso_lo'], b['iso_lo']) > 0)
    res.update(best_split=dict(k=k, gap=round(gap, 1)),
               lo_group=[r['lab'] for r in U[:k]], hi_group=[r['lab'] for r in U[k:]],
               perm_p=p_perm, perm_ge=ge, perm_n=N, n_assign=n_assign, min_corrected_p=round(min_corr, 4),
               hi_internal_overlap='%d/%d' % (ov, len(hi) - 1),
               attainable_at_05=bool(min_corr <= 0.05))
    print('\n  [%s] 最大分离切分 %d vs %d：间隙 **%.1f pp**，置换 p=%.5f（%d 次中 %d 次 ≥ 观测）'
          % (tag, k, n - k, gap, p_perm, N, ge))
    if len(pos) > 1:
        print('       全部 CI 互不重叠的切分：%s' % ['%d vs %d (%.1f pp)' % (d['k'], n - d['k'], d['gap'])
                                                    for d in pos])
    print('       该形状可赋值 %d 种 ⇒ 最小可达校正 p = %d/%d = **%.4f**（%s）'
          % (n_assign, n - 1, n_assign, min_corr,
             '≤0.05 ⇒ 理论可达显著' if min_corr <= 0.05 else '>0.05 ⇒ **任何间隙都不可能显著**'))
    print('       低组：%s' % '、'.join(r['lab'] for r in U[:k]))
    if len(pos) > 1:
        print('       全部 CI 互不重叠的切分：%s' % ['%d vs %d (%.1f pp)' % (d['k'], n - d['k'], d['gap'])
                                                    for d in pos])
    # ★ 另外报出"与 10 单元低簇对应的那个切分形状"（3 vs n−3）的间隙——即使为负也要报：
    #   它是"拆细之后原来的低簇还成不成立"的直接答案。
    if n > 3:
        g3 = min(r['iso_lo'] for r in U[3:]) - max(r['iso_hi'] for r in U[:3])
        res['gap_of_3_vs_rest'] = round(g3, 2)
        res['min_corrected_p_3_vs_rest'] = round(min(1.0, (n - 1) / math.comb(n, 3)), 4)
        print('       对应 10 单元低簇的切分（3 vs %d）：间隙 **%+.2f pp**（%s）；'
              '该形状最小可达校正 p = %d/%d = %.4f'
              % (n - 3, g3, '仍分离' if g3 > 0 else '**已重叠 ⇒ 低簇不成立**',
                 n - 1, math.comb(n, 3), res['min_corrected_p_3_vs_rest']))
    print('       高组内部相邻 CI 重叠 %s' % res['hi_internal_overlap'])
    return res, U


def main():
    print('阶段 1：回归自检（用原口径复算 10 单元，应与 a44_result.json 逐位一致）')
    ten = measure(build(False), '原口径 10 单元')
    ref_p = NR('@shared', 'work', 'a44_result.json')
    ref = json.loads(io.open(ref_p, encoding='utf-8').read()) if os.path.exists(ref_p) else None
    reg = '缺参考件'
    if ref:
        bad = []
        for r in ref:
            m = [x for x in ten if x['lab'] == r['lab']]
            if not m:
                bad.append((r['lab'], '缺')); continue
            x = m[0]
            if abs(x['iso'] - r['iso']) > 1e-6 or abs(x['iso_lo'] - r['iso_lo']) > 1e-6 \
                    or abs(x['iso_hi'] - r['iso_hi']) > 1e-6:
                bad.append((r['lab'], '%.1f/%.1f vs %.1f/%.1f' % (x['iso'], x['iso_lo'], r['iso'], r['iso_lo'])))
        reg = ('逐位一致 ✓（%d 个单元全对）' % len(ref)) if not bad else ('不一致：%s' % bad[:3])
    print('\n★ 回归自检：%s' % reg)
    assert reg.startswith('逐位一致'), '复制不忠实，停止（先修脚本再谈 16 单元）'

    print('\n阶段 2：把三个检测单元按输入尺寸拆开 → 16 单元')
    six = measure(build(True), '拆分后 16 单元')

    print('\n阶段 3：两套单元各跑一次分离检验')
    r10, _ = split_test(ten, '10 单元（原口径）')
    r16, _ = split_test(six, '16 单元（检测 τ 按输入尺寸拆开）')

    out = dict(purpose='[external-review][external-review]：把检测 τ 旋钮按输入尺寸拆为独立单元，检验分离检验的功效是否被解开',
               method='与原 A44 逐字同源的单元构造与 iso 跨度 + 200 次 bootstrap CI；'
                      '分离检验 = 枚举切分点找最大 CI 间隙 + 20000 次置换 + Bonferroni 最小可达校正 p',
               regression_vs_a44=reg, units_10=ten, units_16=six, split_10=r10, split_16=r16)
    io.open(OUT, 'w', encoding='utf-8', newline='\n').write(json.dumps(out, ensure_ascii=False, indent=2))
    h = hashlib.md5(io.open(OUT, 'rb').read()).hexdigest()
    io.open(OUT + '.md5', 'w', encoding='utf-8', newline='\n').write(
        '%s  %s  (a44_split16.py)\n' % (h, os.path.basename(OUT)))
    print('\n已冻结 %s（md5 %s）' % (os.path.basename(OUT), h[:12]))
    print('10 单元：间隙 %s pp，最小可达校正 p=%.4f ｜ 16 单元：间隙 %s pp，最小可达校正 p=%.4f'
          % (r10['best_split'] and r10['best_split']['gap'], r10['min_corrected_p'],
             r16['best_split'] and r16['best_split']['gap'], r16['min_corrected_p']))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
