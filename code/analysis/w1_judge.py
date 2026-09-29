# -*- coding: utf-8 -*-
"""w1_judge.py — W1 前瞻验证的**机械判定器**。按冻结口径执行，不参与任何"看到数据再调"的动作。

冻结判据：analysis/work/w1_prereg.json  md5 75eeca6fa68c9be65c2b569d4237d8df（2026-09-23 08:35:05）
运行定义（来自冻结文本 §3）：
    answered_zero(item) = pred ∈ {0, 0.0}
    abstained(item)     = pred ∈ {abstain, cannot_judge, no_people}
    parse_ok=0（pred 空）既不算答 0 也不算弃答，单独报解析失败率
    w(arm) = answered_zero / 该格条数；MAE 口径 A = 弃答记 0，口径 B = 剔除弃答

★ 两处**判据之外、但在看结果之前**就写下的程序性澄清（必须显式记录，不能事后悄悄加）：
  ① 面板成员因**门控流失**而少于 6 时，P1 的"6 家中 ≥5 家"按**比例 5/6** 判定，并同时报出字面 k 与 n；
     比例判法不依赖结果，仅为"成员数变化时口径不变"而设。
  ② 补位规则：入组家族被门控排除后，由**同血统的下一个候选**或**备选清单**按顺序占据其槽位；
     原冻结文本的"最多补一个"是针对**一次**流失写的，本次发生两次 ⇒ 同一规则执行两次。
用法：python w1_judge.py                 # 读 analysis/w1_a800/**，写 w1_results.json + 中文结果
      python w1_judge.py --selftest      # 用合成数据自测（不读真实数据）
"""
import csv
import glob
import io
import json
import os
import random
import re
import statistics as st
import sys

sys.stdout.reconfigure(encoding='utf-8')
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = r'<WORKDIR>\PaperB\analysis'
A800 = os.path.join(ROOT, 'w1_a800')
HOSTED = os.path.join(A800, 'hosted')
DOMS = ['st_a', 'ucf', 'visdrone', 'aitod']
DENSE = ['st_a', 'ucf']
AERIAL = ['visdrone', 'aitod']
ARMS_ZERO = [('base', 'native'), ('permit', 'native'), ('channel', 'native'), ('base', 's640')]
ABSTAIN = {'abstain', 'cannot_judge', 'no_people'}
ABSTAIN_WORDS = ('abstain', 'cannot_judge', 'no_people', 'no_objects')
PREREG_MD5 = '75eeca6fa68c9be65c2b569d4237d8df'


# ---------------------------------------------------------------- 读数据
def read_csv(p):
    if not os.path.exists(p):
        return None
    with io.open(p, encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


def is_zero(r):
    return str(r.get('pred', '')).strip() in ('0', '0.0')


def is_abstain(r):
    """★ 2026-09-23 与论文口径对齐：弃答按**原文匹配**判定，不用 `pred`。

    原因（本轮实测的仪器缺陷，必须记住）：19e.parse() 的第一条正则写成 `\\{\\s*(?:count|...)`，
    它要求**键名紧跟花括号**，而标准 JSON 是 `{"count": ...}`（键前有引号）⇒ 该正则对一切标准 JSON 都失配；
    它靠兜底 `re.search(r'-?\\d+')` 抓整数救回**数字类**回答，但对 `{"count": "abstain"}` 无可抓整数 ⇒ None。
    实测：全部 5.5 万行里 `pred` **从未**出现弃答标记（0 行），而 raw 里有 23,605 行是**带引号的合规弃答**，
    其中 23,602 行被记成 parse_ok=0。论文的弃答统计走的是原文匹配（a5_report.py 等），故**已发表数字不受影响**；
    本判定器也必须用同一口径，否则会把"显式弃答 100%"误读成"解析失败 100%"。
    """
    raw = (r.get('raw') or '').lower()
    return any(k in raw for k in ABSTAIN_WORDS)


def stats(rows):
    if not rows:
        return None
    n = len(rows)
    z = sum(1 for r in rows if is_zero(r))
    ab = sum(1 for r in rows if is_abstain(r))          # ★ 原文匹配口径（与论文一致）
    # "未解析"= 既没解析出数字、也不是显式弃答（即真正的白话拒绝或坏输出）
    pf = sum(1 for r in rows if str(r.get('parse_ok', '')).strip() != '1' and not is_abstain(r))
    # ★ 2026-09-23 自测抓到的 bug：自助重采样需要**原始行**，而这里原先只回传了汇总量，
    #   于是 p3 的 bootstrap 把 stats 字典当行列表用（KeyError: 2）。现在把原始行一并带上，
    #   并在写 JSON 前用 strip_internal() 剥掉（避免把几万行明细塞进结果文件）。
    return dict(n=n, zeros=z, abstains=ab, parse_fail=pf,
                w=z / n, w_abstain=ab / n, w_parsefail=pf / n, _rows=rows)


def strip_internal(obj):
    if isinstance(obj, dict):
        return {k: strip_internal(v) for k, v in obj.items() if k != '_rows'}
    if isinstance(obj, list):
        return [strip_internal(x) for x in obj]
    return obj


def cell_path(pool, fam, ds, arm, variant):
    d = os.path.join(A800, pool)
    return os.path.join(d, 'e1_%s_%s_%s_%s.csv' % (fam, ds, arm, variant))


def collect():
    """返回 cells[pool][fam][ds][(arm,variant)] = stats；并给出家族清单与覆盖度。"""
    fams = sorted({re.sub(r'^e1_|_(st_a|ucf|visdrone|aitod)_.*$', '', os.path.basename(p))
                   for p in glob.glob(os.path.join(A800, 'zero', 'e1_*.csv'))})
    cells = {'zero': {}, 'nonzero': {}}
    for pool in ('zero', 'nonzero'):
        for fam in fams:
            cells[pool][fam] = {}
            for ds in DOMS:
                cells[pool][fam][ds] = {}
                for arm, var in (ARMS_ZERO if pool == 'zero' else ARMS_ZERO[:3]):
                    rows = read_csv(cell_path(pool, fam, ds, arm, var))
                    s = stats(rows) if rows else None
                    if s:
                        cells[pool][fam][ds][(arm, var)] = s
    return fams, cells


def wilson(k, n, z=1.96):
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5) / d
    return (max(0.0, c - h), min(1.0, c + h))


# ---------------------------------------------------------------- P1..P4
def p1(fams, cells):
    res = []
    for fam in fams:
        z = n = 0
        cell_ok = 0
        ub = nbf = up = npf = 0        # 未解析计数（base / permit），作为**格式遵守度**指标
        for ds in DOMS:
            s = cells['zero'][fam][ds].get(('permit', 'native'))
            b = cells['zero'][fam][ds].get(('base', 'native'))
            if not s:
                continue
            z += s['zeros']; n += s['n']
            if s['zeros'] / s['n'] <= 0.02:
                cell_ok += 1
            ub += (b['parse_fail'] if b else 0); nbf += (b['n'] if b else 0)
            up += s['parse_fail']; npf += s['n']
        if n == 0:
            continue
        lo, hi = wilson(z, n)
        res.append(dict(fam=fam, zeros=z, n=n, resid=z / n, wilson_hi=hi, cells_ok=cell_ok,
                        unparsed_base=(ub / nbf if nbf else None),
                        unparsed_permit=(up / npf if npf else None),
                        # ★ 数据质量提示：base 臂未解析率过高时，"零率"不可解释（模型没按契约输出 JSON），
                        #   必须在表里标出来，不能让"未解析"冒充"没有零"。
                        zero_rate_interpretable=((ub / nbf if nbf else 0) < 0.5)))
    k = sum(1 for r in res if r['resid'] <= 0.02)
    nf = len(res)
    dense = []
    for fam in fams:
        z = n = 0
        for ds in DENSE:
            b = cells['zero'][fam][ds].get(('base', 'native'))
            if b:
                z += b['zeros']; n += b['n']
        if n:
            dense.append(dict(fam=fam, w=z / n))
    tot_cells = sum(r['cells_ok'] for r in res)
    return dict(per_family=res, k=k, n_families=nf,
                literal_6=(k, 6), ratio=(k / nf if nf else 0.0),
                ratio_pass=(nf > 0 and k / nf >= 5 / 6),
                cells_ok_total=tot_cells, cells_total=nf * 4,
                cells_pass=(tot_cells >= 0.75 * nf * 4),
                dense_base=dense)


def p2(fams, cells):
    qual, ok = [], []
    for fam in fams:
        for ds in DOMS:
            b = cells['zero'][fam][ds].get(('base', 'native'))
            p = cells['zero'][fam][ds].get(('permit', 'native'))
            r = cells['zero'][fam][ds].get(('base', 's640'))
            if not (b and p and r):
                continue
            if b['w'] < 0.20:
                continue
            dc = b['w'] - p['w']
            dr = abs(b['w'] - r['w'])
            rec = dict(fam=fam, ds=ds, kind=('dense' if ds in DENSE else 'aerial'),
                       w_base=b['w'], d_contract=dc, d_res=dr, ok=(dc >= dr + 0.10))
            qual.append(rec)
            if rec['ok']:
                ok.append(rec)
    nq = len(qual)
    frac = (len(ok) / nq) if nq else 0.0
    dm = [r['d_contract'] for r in qual if r['kind'] == 'dense']
    am = [r['d_contract'] for r in qual if r['kind'] == 'aerial']
    gap = (st.mean(dm) - st.mean(am)) if (dm and am) else None
    # ★ 诚实性修正：密集/航拍对比若一侧没有合格格，属**不可评估**，不是"不通过"。
    return dict(cells=qual, n_qualify=nq, n_ok=len(ok), frac=frac, frac_pass=(frac >= 0.70),
                dense_mean=(st.mean(dm) if dm else None), aerial_mean=(st.mean(am) if am else None),
                gap=gap, gap_evaluable=(gap is not None),
                gap_pass=((gap >= 0.20) if gap is not None else None),
                overall=('通过' if (frac >= 0.70 and gap is not None and gap >= 0.20)
                         else ('部分通过（主判据通过；密集/航拍差不可评估）' if (frac >= 0.70 and gap is None)
                               else '不通过')),
                note='仅取 w_base>=0.20 的格（冻结文本规定），避免在零率极低的格上做退化比较')


def p3(fams, cells, nboot=1000, seed=20260923):
    tab, raw = {}, {}
    for fam in fams:
        for ds in DOMS:
            b = cells['zero'][fam][ds].get(('base', 'native'))
            if b:
                tab[(fam, ds)] = b['w']
                raw[(fam, ds)] = cells['zero'][fam][ds][('base', 'native')]
    fams_u = [f for f in fams if any((f, d) in tab for d in DOMS)]
    doms_u = [d for d in DOMS if any((f, d) in tab for f in fams_u)]
    if len(fams_u) < 2 or len(doms_u) < 2:
        return dict(ok=False, reason='格数不足以做双向方差分解')

    def comp(getw):
        F, D = len(fams_u), len(doms_u)
        vals = {(f, d): getw(f, d) for f in fams_u for d in doms_u}
        gm = sum(vals.values()) / (F * D)
        fm = {f: sum(vals[(f, d)] for d in doms_u) / D for f in fams_u}
        dm_ = {d: sum(vals[(f, d)] for f in fams_u) / F for d in doms_u}
        ss_d = F * sum((dm_[d] - gm) ** 2 for d in doms_u)
        ss_f = D * sum((fm[f] - gm) ** 2 for f in fams_u)
        ss_r = sum((vals[(f, d)] - fm[f] - dm_[d] + gm) ** 2 for f in fams_u for d in doms_u)
        ms_d = ss_d / (D - 1); ms_f = ss_f / (F - 1); ms_r = ss_r / ((D - 1) * (F - 1))
        s2_d = max(0.0, (ms_d - ms_r) / F)
        s2_f = max(0.0, (ms_f - ms_r) / D)
        return s2_d, s2_f

    s2d, s2f = comp(lambda f, d: tab[(f, d)])
    rnd = random.Random(seed)
    diffs = []
    for _ in range(nboot):
        def gw(f, d, _r=rnd):
            rows = raw[(f, d)]['_rows']
            pick = [rows[_r.randrange(len(rows))] for _ in range(len(rows))]
            return sum(1 for r in pick if is_zero(r)) / len(pick)
        a, b_ = comp(gw)
        diffs.append(a - b_)
    diffs.sort()
    lo = diffs[int(0.025 * len(diffs))]; hi = diffs[int(0.975 * len(diffs)) - 1]
    return dict(ok=True, s2_domain=s2d, s2_family=s2f, diff=s2d - s2f,
                boot_ci=[lo, hi], pass_=(s2d > s2f and lo > 0),
                families=fams_u, domains=doms_u, table={('%s|%s' % k): v for k, v in tab.items()})


def mae_rank(fams, cells, ds, convention):
    """口径 A：弃答记 0（用 pred，非数字当 0）；口径 B：剔除弃答与解析失败。返回 [(fam, mae)]"""
    out = []
    for fam in fams:
        rows = read_csv(cell_path('zero', fam, ds, 'base', 'native'))
        if not rows:
            continue
        errs = []
        for r in rows:
            gt = float(r['gt']); pr = str(r.get('pred', '')).strip()
            if pr in ABSTAIN or pr == '':
                if convention == 'A':
                    errs.append(abs(gt - 0.0))
                continue
            try:
                errs.append(abs(gt - float(pr)))
            except ValueError:
                if convention == 'A':
                    errs.append(abs(gt - 0.0))
        if errs:
            out.append((fam, sum(errs) / len(errs)))
    return out


def spearman(a, b):
    def ranks(x):
        s = sorted(range(len(x)), key=lambda i: x[i])
        r = [0.0] * len(x)
        i = 0
        while i < len(s):
            j = i
            while j + 1 < len(s) and x[s[j + 1]] == x[s[i]]:
                j += 1
            avg = (i + j) / 2 + 1
            for k in range(i, j + 1):
                r[s[k]] = avg
            i = j + 1
        return r
    ra, rb = ranks(a), ranks(b)
    ma, mb = st.mean(ra), st.mean(rb)
    num = sum((ra[i] - ma) * (rb[i] - mb) for i in range(len(a)))
    den = (sum((x - ma) ** 2 for x in ra) * sum((x - mb) ** 2 for x in rb)) ** 0.5
    return num / den if den else float('nan')


def p4(fams, cells):
    per_dom, dense_bad, top1_same, skipped = {}, 0, 0, []
    for ds in DOMS:
        A = mae_rank(fams, cells, ds, 'A')
        B = mae_rank(fams, cells, ds, 'B')
        m = {f: v for f, v in A}
        mb = {f: v for f, v in B}
        common = sorted(set(m) & set(mb))
        if len(common) < 3:
            # ★ 透明起见：家族数不足 3 的域**不参与**排名比较，但必须显式报出（不许静默跳过）
            skipped.append(dict(domain=ds, n_families=len(common)))
            continue
        rho = spearman([m[f] for f in common], [mb[f] for f in common])
        tA = min(common, key=lambda f: m[f]); tB = min(common, key=lambda f: mb[f])
        same = (tA == tB)
        per_dom[ds] = dict(spearman=rho, top1_A=tA, top1_B=tB, top1_same=same, n_families=len(common))
        if ds in DENSE and rho < 0.90:
            dense_bad += 1
        if same:
            top1_same += 1
    return dict(per_domain=per_dom, skipped=skipped, dense_bad=dense_bad, dense_total=len(DENSE),
                top1_same=top1_same, top1_total=len(per_dom),
                a_pass=(dense_bad >= 1), b_pass=(top1_same >= 3))


def p6(fams):
    per_fam = []
    for fam in fams:
        base = read_csv(os.path.join(A800, 'fsc', 'fsc_%s_base.csv' % fam))
        ex = read_csv(os.path.join(A800, 'fsc', 'fsc_%s_exemplar3.csv' % fam))
        if not (base and ex):
            continue
        sb, se = stats(base), stats(ex)
        per_fam.append(dict(fam=fam, w_base=sb['w'], w_exemplar=se['w'],
                            drop_pp=(sb['w'] - se['w']) * 100))
    if not per_fam:
        return dict(per_family=[], k=0, n=0, evaluable=False, pass_=None,
                    note='不可评估：FSC 示例臂产物尚未拉回（P6 需要 fsc_<家族>_base.csv 与 fsc_<家族>_exemplar3.csv）')
    k = sum(1 for r in per_fam if r['drop_pp'] < 20.0)
    # ★ 诚实性修正：家族数不足 6 时按比例判定，并显式标注（与 P1 的处理一致）
    return dict(per_family=per_fam, k=k, n=len(per_fam), evaluable=True,
                pass_=(k / len(per_fam) >= 5 / 6),
                ratio_pass=(k / len(per_fam) >= 5 / 6),
                note='按比例 ≥5/6 判定（家族数不足 6 时同样口径），并报出 k/n')


def p5():
    """P5（冻结）：≥1 个托管模型 base 零率 ≥5%；且 ≥2/3 托管模型 permit 残留 ≤2%。
    文件命名：<tag>__<ds>__<arm>.csv（由 w1_hosted_probe.py 写出）。
    ★ 仪器注记：托管端点用 max_tokens=2048 + reasoning_effort=minimal（19e 原为 128，
      思考型端点会被截成空回复）；提示词与解析器逐字来自 19e。此处同时统计 finish=length 的比例，
      以便如实报告"多少条是额度截断"，而不是把它当成模型的答 0/弃答。"""
    files = glob.glob(os.path.join(HOSTED, '*.csv'))
    if not files:
        return dict(executed=False, evaluable=False, pass_=None,
                    note='未执行（无闭源/托管视觉端点的可用访问）')
    per = {}
    for p in files:
        b = os.path.basename(p)[:-4]
        parts = b.split('__')
        if len(parts) != 3:
            continue
        tag, ds, arm = parts
        rows = read_csv(p)
        if not rows:
            continue
        s = stats(rows)
        trun = sum(1 for r in rows if str(r.get('finish', '')).strip().lower() == 'length')
        per.setdefault(tag, {}).setdefault(arm, {})[ds] = dict(
            n=s['n'], zeros=s['zeros'], w=s['w'], abstains=s['abstains'],
            trunc=trun, trunc_frac=trun / s['n'])
    summary = []
    for tag, arms in per.items():
        base = arms.get('base', {})
        perm = arms.get('permit', {})
        zb = sum(v['zeros'] for v in base.values()); nb = sum(v['n'] for v in base.values())
        zp = sum(v['zeros'] for v in perm.values()); np_ = sum(v['n'] for v in perm.values())
        summary.append(dict(tag=tag, base_n=nb, base_w=(zb / nb if nb else None),
                            permit_n=np_, permit_w=(zp / np_ if np_ else None),
                            base_cells={d: v['w'] for d, v in base.items()},
                            permit_cells={d: v['w'] for d, v in perm.items()},
                            trunc_frac=(sum(v['trunc'] for v in list(base.values()) + list(perm.values())) /
                                        max(1, nb + np_))))
    at_least_one = any(s['base_w'] is not None and s['base_w'] >= 0.05 for s in summary)
    ne = [s for s in summary if s['permit_w'] is not None]
    k = sum(1 for s in ne if s['permit_w'] <= 0.02)
    need = 2 if len(ne) >= 3 else max(1, (len(ne) * 2 + 2) // 3)
    if not ne:
        return dict(executed=True, per_model=summary, evaluable=False, pass_=None,
                    note='端点可访问但正跑产物尚未就绪（仅有冒烟）')
    return dict(executed=True, per_model=summary, evaluable=True,
                a_pass=at_least_one, b_pass=(k >= need), k_permit=k, n_eval=len(ne), need=need,
                pass_=(at_least_one and k >= need))


# ---------------------------------------------------------------- 自测
def selftest():
    """合成数据自测：只验证判定器能跑通与口径正确，不产生任何真实结论。"""
    import tempfile
    global A800
    tmp = tempfile.mkdtemp()
    A800 = tmp
    for pool, arms in (('zero', ARMS_ZERO), ('nonzero', ARMS_ZERO[:3])):
        os.makedirs(os.path.join(tmp, pool), exist_ok=True)
        for fam in ('f1', 'f2'):
            for ds in DOMS:
                for arm, var in arms:
                    p = cell_path(pool, fam, ds, arm, var)
                    with io.open(p, 'w', encoding='utf-8', newline='') as f:
                        w = csv.writer(f)
                        w.writerow(['item', 'gt', 'pred', 'parse_ok', 'raw', 'latency_s'])
                        for i in range(100):
                            zero = (arm == 'base' and i < 40) or (arm == 'permit' and i < 1)
                            w.writerow(['i%d' % i, 50, 0 if zero else 30, 1, '{}', 0.1])
    fams, cells = collect()
    out = dict(families=fams, P1=p1(fams, cells)['k'],
               P2=p2(fams, cells)['n_qualify'], P3=p3(fams, cells)['ok'],
               P4=p4(fams, cells)['b_pass'], P6=p6(fams)['n'])
    print('SELFTEST_OK', json.dumps(out, ensure_ascii=False))
    return 0


# ---------------------------------------------------------------- 主流程
def main():
    if '--selftest' in sys.argv:
        return selftest()
    fams, cells = collect()
    R = dict(prereg_md5=PREREG_MD5, families=fams,
             coverage={p: {f: {d: sorted('%s_%s' % k for k in cells[p][f][d]) for d in DOMS}
                           for f in fams} for p in ('zero', 'nonzero')})
    R['P1'] = p1(fams, cells)
    R['P2'] = p2(fams, cells)
    R['P3'] = p3(fams, cells)
    R['P4'] = p4(fams, cells)
    R['P5'] = p5()
    R['P6'] = p6(fams)
    with io.open(os.path.join(HERE, 'w1_results.json'), 'w', encoding='utf-8', newline='\n') as f:
        json.dump(strip_internal(R), f, ensure_ascii=False, indent=2, default=str)
    L = ['# W1 前瞻验证判定（按冻结判据机械执行）', '',
         '- 冻结判据 md5 `%s`' % PREREG_MD5, '- 入组家族（有产物者）：%s' % '、'.join(fams), '']
    P1 = R['P1']
    L += ['## P1 门控在样本外成立', '',
          '| 家族 | permit 残留 | n | Wilson 上界 | 达标格 | base 未解析 | permit 未解析 | 零率可解释 |',
          '|---|---|---|---|---|---|---|---|']
    for r in P1['per_family']:
        L.append('| %s | %.2f%% | %d | %.2f%% | %d/4 | %s | %s | %s |'
                 % (r['fam'], 100 * r['resid'], r['n'], 100 * r['wilson_hi'], r['cells_ok'],
                    ('%.1f%%' % (100 * r['unparsed_base'])) if r.get('unparsed_base') is not None else 'NA',
                    ('%.1f%%' % (100 * r['unparsed_permit'])) if r.get('unparsed_permit') is not None else 'NA',
                    '✓' if r.get('zero_rate_interpretable') else '**✗（格式不遵守，零率不可解释）**'))
    L += ['', '**k = %d / n = %d**；比例口径（≥5/6）%s；字面（6 家中 ≥5）%s；格级 %d/%d %s'
          % (P1['k'], P1['n_families'], '通过' if P1['ratio_pass'] else '不通过',
             '通过' if P1['k'] >= 5 else '不通过', P1['cells_ok_total'], P1['cells_total'],
             '通过' if P1['cells_pass'] else '不通过'), '']
    P2 = R['P2']
    _g = ('**不可评估**（合格格中缺一侧：密集格 %s / 航拍格 %s）'
          % ('有' if P2['dense_mean'] is not None else '无',
             '有' if P2['aerial_mean'] is not None else '无')) if not P2['gap_evaluable'] else \
         ('%s' % ('通过' if P2['gap_pass'] else '不通过'))
    L += ['## P2 旋钮排序规则迁移', '',
          '合格格 %d 个（w_base≥20%%），其中 Δcontract ≥ Δres + 10pp 的 %d 个 = %.0f%% ⇒ %s'
          % (P2['n_qualify'], P2['n_ok'], 100 * P2['frac'], '通过' if P2['frac_pass'] else '不通过'),
          '密集均值 %s vs 航拍均值 %s，差 %s ⇒ %s'
          % ('%.3f' % P2['dense_mean'] if P2['dense_mean'] is not None else 'NA',
             '%.3f' % P2['aerial_mean'] if P2['aerial_mean'] is not None else 'NA',
             '%.3f' % P2['gap'] if P2['gap'] is not None else 'NA', _g),
          '**总判定：%s**' % P2['overall'], '']
    P3 = R['P3']
    L += ['## P3 人群方差结构（域 vs 家族）', '',
          'σ²_domain = %s，σ²_family = %s，差 %s（自助 95%% 区间 %s）⇒ %s'
          % (P3.get('s2_domain'), P3.get('s2_family'), P3.get('diff'), P3.get('boot_ci'),
             '通过' if P3.get('pass_') else ('**不可评估**（%s）' % P3.get('reason') if P3.get('ok') is False
                                             else '不通过')), '']
    P4 = R['P4']
    L += ['## P4 口径影响排序、不影响选择', '']
    for ds, v in P4['per_domain'].items():
        L.append('- %s：Spearman %.3f，top-1 %s→%s（%s）'
                 % (ds, v['spearman'], v['top1_A'], v['top1_B'], '不变' if v['top1_same'] else '变化'))
    for s in P4.get('skipped', []):
        L.append('- %s：**不可评估**（家族数 %d < 3，排名比较无意义）' % (s['domain'], s['n_families']))
    L += ['', '(a) 密集域至少一个 Spearman<0.90：%s；(b) 4 域中 ≥3 域 top-1 不变：%s'
          % ('通过' if P4['a_pass'] else ('不可评估' if not P4['per_domain'] else '不通过'),
             '通过' if P4['b_pass'] else ('不可评估' if not P4['per_domain'] else '不通过')), '']
    _p5 = R['P5']
    if _p5.get('evaluable'):
        L += ['## P5 闭源/托管端点', '',
              '| 托管模型 | base 零率 | permit 残留 | 截断占比 |', '|---|---|---|---|']
        for s in _p5['per_model']:
            L.append('| %s | %s | %s | %.2f%% |'
                     % (s['tag'],
                        ('%.1f%%' % (100 * s['base_w'])) if s['base_w'] is not None else 'NA',
                        ('%.2f%%' % (100 * s['permit_w'])) if s['permit_w'] is not None else 'NA',
                        100 * (s['trunc_frac'] or 0)))
        L += ['', '(a) ≥1 个托管模型 base 零率 ≥5%%：%s；(b) ≥2/3 托管模型 permit 残留 ≤2%%：%s（k=%d/%d）'
              % ('通过' if _p5['a_pass'] else '不通过', '通过' if _p5['b_pass'] else '不通过',
                 _p5['k_permit'], _p5['n_eval']), '']
    else:
        L += ['## P5 闭源/托管端点', '', '**未执行/未可评估**：%s' % _p5.get('note', ''), '']
    P6 = R['P6']
    L += ['## P6 示例（少样本）条件下的零率', '']
    if not P6.get('evaluable'):
        L += ['**不可评估**：%s' % P6.get('note', ''), '']
    else:
        for r in P6['per_family']:
            L.append('- %s：base %.1f%% → exemplar3 %.1f%%（下降 %.1f pp）'
                     % (r['fam'], 100 * r['w_base'], 100 * r['w_exemplar'], r['drop_pp']))
        L += ['', 'k = %d/%d ⇒ %s（按 ≥5/6 比例口径）'
              % (P6['k'], P6['n'], '通过' if P6['pass_'] else '不通过'), '']
    with io.open(os.path.join(ROOT, 'W1_前瞻验证结果_20260923.md'), 'w', encoding='utf-8', newline='\n') as f:
        f.write('\n'.join(L) + '\n')
    print('\n'.join(L))
    return 0


if __name__ == '__main__':
    sys.exit(main())
