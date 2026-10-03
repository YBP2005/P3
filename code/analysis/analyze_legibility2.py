# -*- coding: utf-8 -*-
"""analyze_legibility2.py — GLM P1 #5 正式版：可确证性得分与弃权的嵌套 logistic 检验

核心检验（可判定论文中心主张）：
  若"弃权由单实例可确证性驱动"，则在**加入可确证性协变量后，目标个数的系数应显著塌缩**。
  这正是把"跨域弃权率与个数无单调关系"这一**观测**升级为**机制解释**的关键一步。

嵌套模型：
  M0: log_n                     —— 只有个数
  M1: + log_pxob                —— 加"每实例像素数"（分辨率可确证性）
  M2: + sigma                   —— 加模糊
  M3: + overlap / 臂 / 数据源   —— 加遮挡与实验条件

并给出：
  · 真实图像的**图内配对**尺度梯度（同一图、同一个人数，只改分辨率）——最干净的因果证据
  · Legibility 得分 L 与弃权率的分箱剂量反应
  · 计数 vs 拥挤的**可识别性说明**（诚实边界）
"""
import os, csv, sys, json, math, warnings, collections
warnings.filterwarnings('ignore')
sys.stdout.reconfigure(encoding='utf-8')
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold
from sklearn.metrics import roc_auc_score
from sklearn.preprocessing import StandardScaler

D = r'<WORKDIR>\PaperB\analysis\data'
OUTJ = r'<WORKDIR>\analysis\work\_legibility2.json'


def load(rel):
    p = os.path.join(D, rel)
    if not os.path.exists(p):
        return []
    with open(p, encoding='utf-8-sig', errors='replace') as f:
        return list(csv.DictReader(f))


def fnum(r, k, d=None):
    try:
        return float((r.get(k) or '').strip())
    except ValueError:
        return d


def rows_ok(rows):
    out = []
    for r in rows:
        raw = (r.get('raw') or '')
        if (r.get('parse_ok') or '').strip() == '0' and ('HTTP' in raw or 'rror' in raw):
            continue
        out.append(r)
    return out


def build():
    recs = []
    for ds, rel in [('st_a', r'harvest_5090\abstain_results__scalestep_st_a.csv'),
                    ('ucf', r'harvest_5090\abstain_results__scalestep_ucf.csv')]:
        for r in rows_ok(load(rel)):
            px, gt = fnum(r, 'px_per_obj'), fnum(r, 'gt')
            w, h = fnum(r, 'img_w'), fnum(r, 'img_h')
            if not px or not gt or not w or not h or px <= 0 or gt <= 0:
                continue
            recs.append(dict(fam='scalestep', src=ds, arm='base',
                             log_n=math.log(gt), log_pxob=math.log(px),
                             log_area=math.log(w * h), sigma=0.0, overlap=0.0,
                             scale=fnum(r, 'scale'), item=r.get('item'),
                             abstain=int(fnum(r, 'abstain', 0) or 0)))
    for stem in ('causal', 'blur'):
        for arm in ('base', 'over', 'under'):
            for r in rows_ok(load(r'harvest_5090\abstain_results__%s_%s.csv' % (stem, arm))):
                n, rr = fnum(r, 'n'), fnum(r, 'r')
                px = fnum(r, 'px_per_obj') or (4.0 * rr * rr if rr else None)
                if not n or not px or n <= 0 or px <= 0:
                    continue
                recs.append(dict(fam=stem, src='syn', arm=arm,
                                 log_n=math.log(n), log_pxob=math.log(px),
                                 log_area=0.0, sigma=fnum(r, 'sigma', 0.0) or 0.0,
                                 overlap=0.0, scale=None, item=r.get('item'),
                                 abstain=int(fnum(r, 'abstain', 0) or 0)))
    seen = {}
    for rel in (r'harvest_5090\occl_results__occl_blur.csv',
                r'harvest_5090\occl2__occl_blur.csv',
                r'harvest_5090\occl_results_8b__occl_blur.csv',
                r'harvest_A\occl__occl_blur.csv'):
        rows = load(rel)
        if not rows:
            continue
        key = json.dumps(sorted((r.get('item'), r.get('pred'), r.get('abstain')) for r in rows))
        if key in seen:
            continue
        seen[key] = rel
        for r in rows_ok(rows):
            n, rr, ov = fnum(r, 'n'), fnum(r, 'r'), fnum(r, 'overlap')
            if not n or not rr or ov is None:
                continue
            recs.append(dict(fam='occl', src=('small' if rr <= 16 else 'large'),
                             arm='base', log_n=math.log(n),
                             log_pxob=math.log(4.0 * rr * rr), log_area=0.0,
                             sigma=fnum(r, 'sigma', 0.0) or 0.0, overlap=ov,
                             scale=None, item=r.get('item'),
                             abstain=int(fnum(r, 'abstain', 0) or 0)))
    return recs


def fitm(recs, feats, cats, title):
    X = [[r[f] for f in feats] for r in recs]
    names = list(feats)
    for col, key, ref in cats:
        for v in sorted(set(key(r) for r in recs)):
            if v == ref:
                continue
            names.append('%s=%s' % (col, v))
            for i, r in enumerate(recs):
                X[i].append(1.0 if key(r) == v else 0.0)
    X = np.asarray(X, float)
    y = np.asarray([r['abstain'] for r in recs], int)
    sc = StandardScaler().fit(X)
    Xs = sc.transform(X)
    m = LogisticRegression(C=1e6, max_iter=5000).fit(Xs, y)
    skf = StratifiedKFold(5, shuffle=True, random_state=0)
    auc = np.mean([roc_auc_score(y[te], LogisticRegression(C=1e6, max_iter=5000)
                                 .fit(Xs[tr], y[tr]).predict_proba(Xs[te])[:, 1])
                   for tr, te in skf.split(Xs, y)])
    print('\n  %-58s n=%d 弃权=%.1f%%  AUC=%.3f' % (title, len(y), 100 * y.mean(), auc))
    out = {}
    for nm, b in zip(names, m.coef_[0]):
        out[nm] = float(b)
        print('      %-24s β=%+8.3f   OR/1SD=%9.3f' % (nm, b, math.exp(b)))
    out['__auc__'] = float(auc)
    out['__n__'] = len(y)
    return out


def main():
    recs = build()
    print('总记录数 %d' % len(recs))
    for k, v in sorted(collections.Counter((r['fam'], r['src']) for r in recs).items()):
        print('   %-10s %-6s %5d' % (k[0], k[1], v))
    res = {}

    print('\n' + '=' * 82)
    print('【检验一】真实图像：加入"每实例像素数"后，个数系数是否塌缩？')
    R = [r for r in recs if r['fam'] == 'scalestep']
    res['real_M0'] = fitm(R, ['log_n'], [], 'M0 只有个数 log(GT)')
    res['real_M1'] = fitm(R, ['log_n', 'log_pxob'], [], 'M1 加 每实例像素数 log(px/obj)')
    res['real_M2'] = fitm(R, ['log_n', 'log_pxob'], [('ds', lambda r: r['src'], 'st_a')],
                          'M2 再加 数据源哑变量')
    res['real_M3'] = fitm(R, ['log_n', 'log_area'], [('ds', lambda r: r['src'], 'st_a')],
                          'M3 等价重参数化：log(GT) + log(图像面积)')

    print('\n' + '=' * 82)
    print('【检验二】合成点场：加分辨率与模糊后，个数系数是否塌缩？')
    S = [r for r in recs if r['fam'] in ('causal', 'blur')]
    res['syn_M0'] = fitm(S, ['log_n'], [], 'M0 只有个数 log(n)')
    res['syn_M1'] = fitm(S, ['log_n', 'log_pxob'], [], 'M1 加 log(px/obj)')
    res['syn_M2'] = fitm(S, ['log_n', 'log_pxob', 'sigma'], [], 'M2 加 模糊 sigma')
    res['syn_M3'] = fitm(S, ['log_n', 'log_pxob', 'sigma'],
                         [('arm', lambda r: r['arm'], 'base'),
                          ('stim', lambda r: r['fam'], 'causal')],
                         'M3 再加 提示词臂与刺激族')

    print('\n' + '=' * 82)
    print('【检验三】遮挡析因（人数固定 n=300）：实测 overlap 的作用')
    O = [r for r in recs if r['fam'] == 'occl']
    res['occl_M0'] = fitm(O, ['overlap'], [], 'M0 只有 overlap')
    res['occl_M1'] = fitm(O, ['overlap', 'log_pxob'], [], 'M1 加 log(px/obj)')
    res['occl_M2'] = fitm(O, ['overlap', 'log_pxob', 'sigma'],
                          [('stim', lambda r: r['src'], 'small')], 'M2 加 模糊与刺激尺度')

    # ---- 图内配对尺度梯度 ----
    print('\n' + '=' * 82)
    print('【检验四】图内配对尺度梯度（同一张图、人数不变，只改分辨率）——最干净的因果证据')
    par = {}
    for ds in ('st_a', 'ucf'):
        by_item = collections.defaultdict(dict)
        for r in recs:
            if r['fam'] == 'scalestep' and r['src'] == ds:
                by_item[r['item']][r['scale']] = r['abstain']
        scales = sorted(set(r['scale'] for r in recs if r['fam'] == 'scalestep' and r['src'] == ds))
        print('  --- %s（%d 张图）---' % (ds, len(by_item)))
        print('     %-8s %8s %9s %9s' % ('scale', 'n', '弃权数', '弃权率'))
        tab = []
        for s in scales:
            sel = [v[s] for v in by_item.values() if s in v]
            k = sum(sel)
            print('     %-8s %8d %9d %8.1f%%' % (s, len(sel), k, 100.0 * k / max(1, len(sel))))
            tab.append(dict(scale=s, n=len(sel), k=k, rate=k / max(1, len(sel))))
        par[ds] = tab
        # 配对翻转：scale=1.0 与最小 scale 都出现的图
        s0, s1 = scales[0], scales[-1]
        both = [v for v in by_item.values() if s0 in v and s1 in v]
        if both:
            a = sum(v[s0] for v in both)
            b = sum(v[s1] for v in both)
            only_hi = sum(1 for v in both if v[s0] == 1 and v[s1] == 0)
            only_lo = sum(1 for v in both if v[s0] == 0 and v[s1] == 1)
            print('     配对（scale %.2f vs %.2f，%d 张）：弃权 %d → %d；'
                  '仅低分辨率弃权 %d 张，仅高分辨率弃权 %d 张'
                  % (s0, s1, len(both), a, b, only_hi, only_lo))
            par[ds + '_paired'] = dict(lo=s0, hi=s1, n=len(both), lo_abstain=a,
                                       hi_abstain=b, only_lo=only_hi, only_hi=only_lo)
    res['paired_scale'] = par

    # ---- Legibility 得分剂量反应 ----
    print('\n' + '=' * 82)
    print('【检验五】Legibility 得分与弃权率的剂量反应')
    o = res['occl_M2']
    b_px, b_sg, b_ov = o.get('log_pxob', 0), o.get('sigma', 0), o.get('overlap', 0)
    print('  采用遮挡析因拟合（n=%d）的系数：β_pxob=%.3f  β_sigma=%.3f  β_overlap=%.3f'
          % (o['__n__'], b_px, b_sg, b_ov))
    print('  Legibility  L = −(%.3f·log(px/obj) + %.3f·sigma + %.3f·overlap)' % (b_px, b_sg, b_ov))
    for r in O:
        r['L'] = -(b_px * r['log_pxob'] + b_sg * r['sigma'] + b_ov * r['overlap'])
    Ls = np.array([r['L'] for r in O])
    ys = np.array([r['abstain'] for r in O])
    qs = np.quantile(Ls, np.linspace(0, 1, 6))
    print('     %-20s %6s %8s %9s' % ('L 区间', 'n', '弃权数', '弃权率'))
    curve = []
    for i in range(5):
        lo, hi = qs[i], qs[i + 1]
        sel = (Ls >= lo) & (Ls <= hi if i == 4 else Ls < hi)
        if sel.sum() == 0:
            continue
        k = int(ys[sel].sum())
        print('     [%7.3f,%7.3f] %6d %8d %8.1f%%' % (lo, hi, sel.sum(), k, 100.0 * k / sel.sum()))
        curve.append(dict(lo=float(lo), hi=float(hi), n=int(sel.sum()), k=k,
                          rate=float(k / sel.sum())))
    res['dose_response_L'] = curve
    res['coef_L'] = dict(pxob=b_px, sigma=b_sg, overlap=b_ov)

    json.dump(res, open(OUTJ, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('\n已写 %s' % OUTJ)


if __name__ == '__main__':
    main()
