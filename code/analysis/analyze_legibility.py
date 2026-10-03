# -*- coding: utf-8 -*-
"""analyze_legibility.py — GLM P1 #5：可确证性得分（Legibility Score）与弃权的 logistic 拟合

目标：把论文的中心构念"单实例可确证性（legibility）"从**语言主张**变成**可测量的量**，
     并检验论文的一个关键预言：**弃权由可确证性驱动，与目标个数无关**。

数据（全部为受控实验，排除了观测性臂）：
  A) 真实图像尺度阶梯  abstain_results__scalestep_{st_a,ucf}.csv
     scale ∈ {0.25,0.35,0.5,0.75,1.0}，逐图记录 px_per_obj 与 gt
  B) 合成点场（剂量臂）abstain_results__{causal,blur}_{base,over,under}.csv
     n ∈ {50..800}，r ∈ {2..16}（px_per_obj = 4r²），sigma ∈ {0,1,2,4,8}
  C) 合成点场（遮挡/模糊析因）occl*__occl_blur.csv
     n=300 固定，r ∈ {4,16,18,40}，layout ∈ {clustered,scattered}，
     sigma ∈ {0,2,4,8}，并逐图记录了实际 overlap

特征：
  log_pxob = ln(px_per_obj)      可确证性的分辨率分量
  sigma                         模糊/对比度退化分量
  overlap                       遮挡分量（仅 C 有）
  log_n   = ln(n 或 gt)         目标个数（论文预言其系数 ≈ 0）

拟合：P(abstain) = σ(β0 + Σβk·xk + 臂/数据集哑变量)
      Legibility  L = −(β_pxob·log_pxob + β_sigma·sigma + β_overlap·overlap)
      （符号约定：L 越大越"可确证"，弃权概率越低）

输出：系数表（标准化单位 + 每 1 SD 的 odds ratio）、AUC（5 折交叉验证）、
      按 L 分箱的弃权率剂量反应曲线、以及纵向比较各实验族系数的稳定性。
"""
import os, csv, sys, json, math, collections
sys.stdout.reconfigure(encoding='utf-8')
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold
from sklearn.metrics import roc_auc_score
from sklearn.preprocessing import StandardScaler

D = r'<WORKDIR>\PaperB\analysis\data'
OUTJ = r'<WORKDIR>\analysis\work\_legibility.json'


def load(rel):
    p = os.path.join(D, rel)
    if not os.path.exists(p):
        return None
    with open(p, encoding='utf-8-sig', errors='replace') as f:
        return list(csv.DictReader(f))


def fnum(r, k, d=None):
    s = (r.get(k) or '').strip()
    try:
        return float(s)
    except ValueError:
        return d


def rows_ok(rows):
    """剔除服务端失败行（parse_ok=0 且 raw 含 HTTP/错误）"""
    out = []
    for r in rows or []:
        ok = (r.get('parse_ok') or '').strip()
        raw = (r.get('raw') or '')
        if ok == '0' and ('HTTP' in raw or 'Error' in raw or 'error' in raw):
            continue
        out.append(r)
    return out


def build():
    """构造统一记录表"""
    recs = []

    # ---- A) 真实图像尺度阶梯 ----
    for ds, rel in [('st_a', r'harvest_5090\abstain_results__scalestep_st_a.csv'),
                    ('ucf', r'harvest_5090\abstain_results__scalestep_ucf.csv')]:
        for r in rows_ok(load(rel)):
            px = fnum(r, 'px_per_obj'); gt = fnum(r, 'gt')
            if not px or not gt or px <= 0 or gt <= 0:
                continue
            recs.append(dict(fam='scalestep', ds=ds, arm='base',
                             log_pxob=math.log(px), log_n=math.log(gt),
                             sigma=0.0, overlap=0.0, has_overlap=0,
                             abstain=int(fnum(r, 'abstain', 0) or 0)))

    # ---- B) 合成点场（剂量臂）----
    for stem in ('causal', 'blur'):
        for arm in ('base', 'over', 'under'):
            rel = r'harvest_5090\abstain_results__%s_%s.csv' % (stem, arm)
            for r in rows_ok(load(rel)):
                n = fnum(r, 'n'); rr = fnum(r, 'r')
                px = fnum(r, 'px_per_obj') or (4.0 * rr * rr if rr else None)
                if not n or not px or n <= 0 or px <= 0:
                    continue
                sg = fnum(r, 'sigma', 0.0) or 0.0     # causal 无 sigma 列 → 视为 0（锐利）
                recs.append(dict(fam=stem, ds='syn', arm=arm,
                                 log_pxob=math.log(px), log_n=math.log(n),
                                 sigma=sg, overlap=0.0, has_overlap=0,
                                 abstain=int(fnum(r, 'abstain', 0) or 0)))

    # ---- C) 遮挡/模糊析因 ----
    seen = {}
    for rel in (r'harvest_5090\occl_results__occl_blur.csv',
                r'harvest_5090\occl2__occl_blur.csv',
                r'harvest_5090\occl_results_8b__occl_blur.csv',
                r'harvest_A\occl__occl_blur.csv'):
        rows = load(rel)
        if rows is None:
            continue
        key = json.dumps(sorted((r.get('item'), r.get('pred'), r.get('abstain')) for r in rows),
                         ensure_ascii=False)
        if key in seen:
            continue                      # 逐项镜像，去重
        seen[key] = rel
        for r in rows_ok(rows):
            n = fnum(r, 'n'); rr = fnum(r, 'r')
            px = 4.0 * rr * rr if rr else None
            ov = fnum(r, 'overlap')
            if not n or not px or ov is None:
                continue
            sg = fnum(r, 'sigma', 0.0) or 0.0
            # 把 r 的档位作为"刺激尺度"标识（4/16 vs 18/40 是两套刺激）
            stim = 'small' if rr <= 16 else 'large'
            recs.append(dict(fam='occl', ds=stim, arm='base',
                             log_pxob=math.log(px), log_n=math.log(n),
                             sigma=sg, overlap=ov, has_overlap=1,
                             abstain=int(fnum(r, 'abstain', 0) or 0)))
    return recs


def fit(recs, feats, cat_dummies, title, ridge=False):
    """feats: 数值特征名列表；cat_dummies: [(列名, 取值函数, 参考类), ...]"""
    X, names = [], list(feats)
    for r in recs:
        X.append([r[f] for f in feats])
    for col, keyfn, refname in cat_dummies:
        vals = sorted(set(keyfn(r) for r in recs))
        for v in vals:
            if v == refname:
                continue
            names.append('%s=%s' % (col, v))
            for i, r in enumerate(recs):
                X[i].append(1.0 if keyfn(r) == v else 0.0)

    X = np.asarray(X, dtype=float)
    y = np.asarray([r['abstain'] for r in recs], dtype=int)
    sc = StandardScaler().fit(X)
    Xs = sc.transform(X)
    C = 1e6 if not ridge else 1.0
    lr = LogisticRegression(penalty='l2', C=C, max_iter=5000, solver='lbfgs')
    lr.fit(Xs, y)

    skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=0)
    aucs = []
    for tr, te in skf.split(Xs, y):
        m = LogisticRegression(penalty='l2', C=C, max_iter=5000, solver='lbfgs')
        m.fit(Xs[tr], y[tr])
        aucs.append(roc_auc_score(y[te], m.predict_proba(Xs[te])[:, 1]))

    print('\n' + '=' * 78)
    print('%s   n=%d  弃权率=%.1f%%' % (title, len(y), 100.0 * y.mean()))
    print('  AUC = %.3f ± %.3f (5 折)' % (np.mean(aucs), np.std(aucs)))
    print('  %-26s %10s %10s' % ('特征（标准化）', '系数 β', 'OR/1SD'))
    coef = {}
    for nm, b in zip(names, lr.coef_[0]):
        coef[nm] = float(b)
        print('  %-26s %10.3f %10.3f' % (nm, b, math.exp(b)))
    print('  %-26s %10.3f' % ('截距', lr.intercept_[0]))
    return coef, float(np.mean(aucs))


def main():
    recs = build()
    print('总记录数 %d' % len(recs))
    fam = collections.Counter((r['fam'], r['ds']) for r in recs)
    for k, v in sorted(fam.items()):
        print('   %-16s %-8s %5d' % (k[0], k[1], v))

    res = {}

    # ---- 拟合 1：真实图像，只看 px/obj 与个数 ----
    r1 = [r for r in recs if r['fam'] == 'scalestep']
    c1, a1 = fit(r1, ['log_pxob', 'log_n'],
                 [('dataset', lambda r: r['ds'], 'st_a')],
                 '拟合1｜真实图像尺度阶梯（ST-A + UCF）')
    res['fit1_scalestep'] = dict(coef=c1, auc=a1, n=len(r1))

    # ---- 拟合 2：合成点场（剂量臂），含模糊与个数 ----
    r2 = [r for r in recs if r['fam'] in ('causal', 'blur')]
    c2, a2 = fit(r2, ['log_pxob', 'sigma', 'log_n'],
                 [('arm', lambda r: r['arm'], 'base'),
                  ('stim', lambda r: r['fam'], 'causal')],
                 '拟合2｜合成点场（causal + blur，三提示词臂）')
    res['fit2_synthetic'] = dict(coef=c2, auc=a2, n=len(r2))

    # ---- 拟合 3：遮挡/模糊析因，含 overlap ----
    r3 = [r for r in recs if r['fam'] == 'occl']
    c3, a3 = fit(r3, ['log_pxob', 'sigma', 'overlap'],
                 [('stim', lambda r: r['ds'], 'small')],
                 '拟合3｜遮挡/模糊析因（含实测 overlap）')
    res['fit3_occl'] = dict(coef=c3, auc=a3, n=len(r3))

    # ---- 拟合 4：全部受控数据池化（overlap 缺失补 0，加缺失哑变量）----
    r4 = recs
    c4, a4 = fit(r4, ['log_pxob', 'sigma', 'overlap', 'log_n'],
                 [('arm', lambda r: r['arm'], 'base'),
                  ('fam', lambda r: r['fam'], 'scalestep')],
                 '拟合4｜全部受控数据池化')
    res['fit4_pooled'] = dict(coef=c4, auc=a4, n=len(r4))

    # ---- 剂量反应：用拟合4的分辨率系数构造 Legibility，分箱看弃权率 ----
    b_px = c4.get('log_pxob', 0.0)
    print('\n' + '=' * 78)
    print('Legibility 得分与弃权率的剂量反应（L = log_pxob，按拟合4的 β_pxob 定向）')
    print('  β_pxob = %.3f  →  %s' % (b_px, '像素/目标越少越易弃权（符合预期）'
                                      if b_px < 0 else '※ 方向与预期相反，需如实报告'))
    vals = sorted(set(r['log_pxob'] for r in recs))
    qs = np.quantile([r['log_pxob'] for r in recs], [0, .2, .4, .6, .8, 1.0])
    print('  %-22s %8s %8s %8s' % ('log(px/obj) 区间', 'n', '弃权数', '弃权率'))
    curve = []
    for i in range(5):
        lo, hi = qs[i], qs[i + 1]
        sel = [r for r in recs if (lo - 1e-9) <= r['log_pxob'] <= (hi + 1e-9)] if i == 4 else \
              [r for r in recs if (lo - 1e-9) <= r['log_pxob'] < hi]
        if not sel:
            continue
        k = sum(r['abstain'] for r in sel)
        print('  [%7.2f, %7.2f]        %8d %8d %7.1f%%' % (lo, hi, len(sel), k, 100.0 * k / len(sel)))
        curve.append(dict(lo=lo, hi=hi, n=len(sel), k=k, rate=k / len(sel)))
    res['dose_response'] = curve

    json.dump(res, open(OUTJ, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('\n已写 %s' % OUTJ)


if __name__ == '__main__':
    main()
