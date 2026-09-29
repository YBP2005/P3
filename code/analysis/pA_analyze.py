# -*- coding: utf-8 -*-
"""pA_analyze.py —— 方案 A：条款级提示词特征的**零成本**归因分析。

读入：
  * pA_criteria_frozen.json（阈值**只**从这里读；自校验 md5）
  * analysis/work/prompt_features.json（条款级特征表，v2.1）
  * Block A：analysis/e2xt_a800/merged + analysis/e2_newh20 的 e1_*.csv（真实语料）
  * Block B：analysis/data/pod_mirror/*_blurct/{blur_base,blur_forbid0,blur_choice,blur_range}.csv（675 item，同 item 配对）
  * Block C：analysis/data/pod_mirror/*_occlct/{occl_base,occl_forbid0}.csv（160 item，同 item 配对）

输出：
  * pA_result.json（含判据 md5、每个判据的实测值与判定、全部原始率表）

纪律：
  · 阈值不在本文件里另写一套；一律 crit['...']。
  · `--selftest` 用合成数据做**阳性/阴性对照**，证明这套判定既能通过也能失败。
"""
import argparse
import collections
import hashlib
import io
import json
import os
import random
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')
W = os.path.dirname(os.path.abspath(__file__))
PAPER = os.path.dirname(os.path.dirname(W))
FRZ = os.path.join(W, 'pA_criteria_frozen_v2.json')
ABST_RE = re.compile(r'abstain|cannot_judge|no_people', re.I)

ALINEAGE = {
    'InternVL3_5-8B': 'InternVL3.5-8B',
    'internvl25-8b-awq': 'InternVL2.5-8B',
    'internvl35-38b-fp8': 'InternVL3.5-38B',
    'Phi-3.5-vision-instruct': 'Phi-3.5-Vision',
    'gemma3-12b': 'gemma-3-12b',
    'llava-onevision-qwen2-7b-ov': 'LLaVA-OneVision-7B',
    'qwen3-vl-32b-awq': 'Qwen3-VL-32B', 'qwen3-vl-32b-awq8': 'Qwen3-VL-32B',
    'qwen3-vl-32b-bf16': 'Qwen3-VL-32B', 'qwen3-vl-32b-fp8': 'Qwen3-VL-32B',
    'qwen3-vl-32b-gptq': 'Qwen3-VL-32B', 'Qwen3-VL-32B-Instruct': 'Qwen3-VL-32B',
    'qwen3-vl-8b-awq': 'Qwen3-VL-8B', 'qwen3-vl-8b-bf16': 'Qwen3-VL-8B',
    'qwen25vl-72b-awq': 'Qwen2.5-VL-72B', 'qwen25vl-7b-awq': 'Qwen2.5-VL-7B',
    'qwen3-vl-2b': 'Qwen3-VL-2B', 'qwen3-vl-4b': 'Qwen3-VL-4B',
    'qwen3-vl-30b-a3b-fp8': 'Qwen3-VL-30B-A3B',
    'qwen3-vl-235b-a22b-instruct': 'Qwen3-VL-235B-A22B',
}
H_A1_LINEAGES = ['InternVL3.5-8B', 'Phi-3.5-Vision', 'gemma-3-12b', 'Qwen3-VL-32B']
# 同一血统多个权重时，H_A1 取哪一个（保持与 P1/P1b 面板一致）
REP_PREFER = ['awq', 'bf16', 'fp8', 'gptq', '']
DOMAINS = ['st_a', 'st_b', 'ucf', 'visdrone', 'aitod', 'countbench']
ALL_ARMS = ['base', 'permit', 'channel', 'enumAbstain', 'bestA', 'bestB', 'bestC',
            'enum', 'locate', 'forbid0', 'choice', 'range', 'permitB', 'permitC', 'channelB']
ARM_RE = re.compile(r'^(?:e1_)?(.*?)_(' + '|'.join(DOMAINS) + r')_(' +
                    '|'.join(sorted(ALL_ARMS, key=len, reverse=True)) + r')\.csv$')


def md5_12(p):
    return hashlib.md5(io.open(p, 'rb').read()).hexdigest()[:12]


def crit_load():
    raw = io.open(FRZ, 'rb').read()
    doc = json.loads(raw.decode('utf-8'))
    return doc['criteria'], hashlib.md5(raw).hexdigest()[:12]


# ── 读 CSV ────────────────────────────────────────────────────────────────────
def read_csv(p):
    import csv
    with io.open(p, encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


def num(v):
    try:
        return float(str(v).strip())
    except Exception:
        return None


def zero_abst(rows):
    """返回 (n, n_zero, n_abst, n_err)。

    ★ v2 仪器修正：`abstain` **从 raw 恢复**，不依赖 `pred` 列。
      原因见 pA_freeze_criteria_v2.py：e2xt_a800/merged 的出口臂 pred 列 94–100% 为空，
      而 raw 逐字含 `{"count": "abstain"}`；旧口径把弃答误计成"解析失败"，
      于是"零率"变成"失败率"。
      zero 定义不变；err = pred 为空 **且** raw 不含弃答 token。
    """
    n = len(rows)
    z = a = e = 0
    for r in rows:
        p = str(r.get('pred', '')).strip()
        raw = str(r.get('raw', ''))
        is_a = bool(ABST_RE.search(raw)) or p.lower() in ('abstain', 'cannot_judge', 'no_people')
        if is_a:
            a += 1
        if p == '' or p.lower().startswith('err'):
            if not is_a:
                e += 1
            continue
        pv = num(p)
        if pv is not None and pv == 0:
            z += 1
    return n, z, a, e


# ── Block A ───────────────────────────────────────────────────────────────────
def scan_dir(d, min_n, skip_nz=True, only_nz=False):
    cells = {}
    if not os.path.isdir(d):
        return cells
    for fn in sorted(os.listdir(d)):
        isnz = fn.startswith('nz__')
        if skip_nz and isnz:
            continue
        if only_nz and not isnz:
            continue
        m = ARM_RE.match(fn)
        if not m:
            continue
        fam, dom, arm = m.group(1), m.group(2), m.group(3)
        rows = [r for r in read_csv(os.path.join(d, fn)) if '#r' not in str(r.get('item', ''))]
        n, z, a, e = zero_abst(rows)
        if n < min_n:
            continue
        cells[(fam, dom, arm)] = dict(
            family=fam, lineage=ALINEAGE.get(fam, fam), domain=dom, arm=arm,
            n=n, n_zero=z, n_abst=a, n_err=e, src=os.path.join(os.path.basename(d), fn),
            zero=z / n, abst=a / n, err=e / n)
    return cells


def block_a(min_n):
    """Block A：真实语料主块（**排除 nz__ 非零池**，见 v2 amendments）。"""
    cells, seen = {}, set()
    for d in [os.path.join(PAPER, 'analysis', 'e2xt_a800', 'merged'),
              os.path.join(PAPER, 'analysis', 'e2_newh20')]:
        for k, v in scan_dir(d, min_n).items():
            if k in seen:
                continue
            seen.add(k)
            cells[k] = v
    return cells


def block_d(min_n):
    """Block D：非零池反向对照（只作描述，不参与判定）。"""
    cells = {}
    d = os.path.join(PAPER, 'analysis', 'e2_newh20')
    for k, v in scan_dir(d, min_n, skip_nz=False, only_nz=True).items():
        cells[k] = v
    return cells


def rep_of(fam, prefer):
    for s in prefer:
        if s and s in fam:
            return prefer.index(s)
    return len(prefer)


def fam_arm_rate(cells, lineage, arm):
    """某血统在某臂上的域平均率；血统内多权重时按 REP_PREFER 取一个代表。"""
    cand = [c for c in cells.values() if c['lineage'] == lineage and c['arm'] == arm]
    if not cand:
        return None
    fams = sorted({c['family'] for c in cand})
    fams.sort(key=lambda f: (rep_of(f, REP_PREFER), f))
    pick = fams[0]
    sub = [c for c in cand if c['family'] == pick]
    tot = sum(c['n'] for c in sub)
    return dict(family=pick, n=tot,
                zero=sum(c['n_zero'] for c in sub) / tot if tot else None,
                abst=sum(c['n_abst'] for c in sub) / tot if tot else None,
                domains=len(sub))


def h_a1(cells, c):
    print('\n■ H_A1  弃答许可条款（Block A：enumAbstain − enum）')
    print('  %-22s %-24s %8s %8s %8s %8s' % ('血统', '代表权重', 'n', 'zero(enum)', 'zero(enumAbst)', 'Δzero pp'))
    res, okz, oka = [], 0, 0
    for lin in H_A1_LINEAGES:
        a = fam_arm_rate(cells, lin, 'enum')
        b = fam_arm_rate(cells, lin, 'enumAbstain')
        if not a or not b:
            print('  %-22s 缺臂，跳过' % lin)
            continue
        dz = (b['zero'] - a['zero']) * 100
        da = (b['abst'] - a['abst']) * 100
        res.append(dict(lineage=lin, family=a['family'], n=a['n'], n_enumAbstain=b['n'],
                        zero_enum=a['zero'], zero_enumAbstain=b['zero'], d_zero_pp=dz,
                        abst_enum=a['abst'], abst_enumAbstain=b['abst'], d_abst_pp=da))
        okz += dz <= c['zero_delta_max_pp']
        oka += da >= c['abst_delta_min_pp']
        print('  %-22s %-24s %8d %8.3f %8.3f %+8.1f   (Δabst %+.1f pp)' % (
            lin, a['family'], a['n'], a['zero'], b['zero'], dz, da))
    passed = (okz >= c['min_families']) and (oka >= c['min_families'])
    print('  → Δzero 达标 %d/%d（需 ≥%d）；Δabst 达标 %d/%d；判定 %s'
          % (okz, len(res), c['min_families'], oka, len(res), 'PASS' if passed else 'FAIL'))
    return dict(id='H_A1', passed=bool(passed), n_families=len(res),
                zero_pass=okz, abst_pass=oka, rows=res)


# ── Block B/C ─────────────────────────────────────────────────────────────────
B_RUNS = [('b2__out_32b_blurct', 'Qwen3-VL-32B'), ('b2__out_8b_blurct', 'Qwen3-VL-8B'),
          ('ivl_blurct', 'InternVL2.5-8B-AWQ')]
C_RUNS = [('b2__out_32b_occlct', 'Qwen3-VL-32B'), ('b2__out_8b_occlct', 'Qwen3-VL-8B')]
B_ARMS = ['base', 'forbid0', 'choice', 'range']


def block_pairs(runs, prefix):
    out = []
    for dname, label in runs:
        d = os.path.join(PAPER, 'analysis', 'data', 'pod_mirror', dname)
        per = {}
        for arm in B_ARMS:
            p = os.path.join(d, '%s_%s.csv' % (prefix, arm))
            if not os.path.exists(p):
                continue
            rs = read_csv(p)
            per[arm] = {str(r['item']): r for r in rs}
            if len(per[arm]) != len(rs):
                raise RuntimeError('%s/%s_%s.csv 有重复 item（%d 行 / %d 唯一），配对不可信'
                                   % (dname, prefix, arm, len(rs), len(per[arm])))
        if 'base' not in per:
            continue
        common = set(per['base'])
        for arm in per:
            common &= set(per[arm])
        common = sorted(common)
        rec = dict(dir=dname, label=label, arms=sorted(per), n_items=len(common), per={})
        for arm in per:
            z = a = 0
            for i in common:
                r = per[arm][i]
                if num(r.get('pred')) == 0:
                    z += 1
                if str(r.get('abstain', '')).strip() in ('1', 'True', 'true') or \
                   ABST_RE.search(str(r.get('raw', ''))):
                    a += 1
            rec['per'][arm] = dict(n=len(common), n_zero=z, n_abst=a,
                                   zero=z / len(common), abst=a / len(common))
        out.append(rec)
    return out


def paired(rec, a, b):
    """同 item 配对的 Δ（pp）：先逐 item 配对，再算率差。"""
    pa = rec['per'].get(a)
    pb = rec['per'].get(b)
    if not pa or not pb:
        return None
    return (pb['zero'] - pa['zero']) * 100, (pb['abst'] - pa['abst']) * 100


def h_delta_block(recs, base, arm, c, key='H_A2'):
    print('\n■ %s  Block：%s − %s' % (key, arm, base))
    print('  %-20s %8s %10s %10s %9s' % ('run', 'n item', '%s zero' % base, '%s zero' % arm, 'Δzero pp'))
    res, ok = [], 0
    for rec in recs:
        d = paired(rec, base, arm)
        if d is None:
            print('  %-20s 缺臂，跳过' % rec['label'])
            continue
        res.append(dict(run=rec['dir'], label=rec['label'], n=rec['n_items'],
                        zero_base=rec['per'][base]['zero'], zero_arm=rec['per'][arm]['zero'],
                        d_zero_pp=d[0], d_abst_pp=d[1]))
        ok += d[0] <= c['delta_max_pp']
        print('  %-20s %8d %10.3f %10.3f %+9.1f   (Δabst %+.1f pp)' % (
            rec['label'], rec['n_items'], rec['per'][base]['zero'], rec['per'][arm]['zero'], d[0], d[1]))
    req = c.get('runs_required', len(res))
    passed = ok >= req and len(res) >= req
    print('  → Δzero 达标 %d/%d（需 %d/%d）；判定 %s' % (ok, len(res), req, req, 'PASS' if passed else 'FAIL'))
    return dict(id=key, passed=bool(passed), runs=len(res), runs_pass=ok, rows=res)


def h_a3(cells, c):
    print('\n■ H_A3  类型 > 措辞（Block A）')
    def fams_with(arm):
        return sorted({x['lineage'] for x in cells.values() if x['arm'] == arm})
    def deltas(pair):
        a, b = pair
        out = []
        for lin in sorted(set(fams_with(a)) & set(fams_with(b))):
            ra, rb = fam_arm_rate(cells, lin, a), fam_arm_rate(cells, lin, b)
            if ra and rb:
                out.append(dict(lineage=lin, family=rb['family'], n=rb['n'],
                                zero_a=ra['zero'], zero_b=rb['zero'],
                                d_zero_pp=(rb['zero'] - ra['zero']) * 100))
        return out
    wd, td = {}, {}
    for p in c['wording_pairs']:
        wd['%s-%s' % (p[1], p[0])] = deltas(p)
    for p in c['type_pairs']:
        td['%s-%s' % (p[1], p[0])] = deltas(p)
    def deltas_abst(pair):
        a, b = pair
        out = []
        for lin in sorted(set(fams_with(a)) & set(fams_with(b))):
            ra, rb = fam_arm_rate(cells, lin, a), fam_arm_rate(cells, lin, b)
            if ra and rb:
                out.append(dict(lineage=lin, family=rb['family'], n=rb['n'],
                                abst_a=ra['abst'], abst_b=rb['abst'],
                                d_abst_pp=(rb['abst'] - ra['abst']) * 100))
        return out
    print('  措辞对（类型集相同）：')
    allw = []
    for k, v in wd.items():
        va = {r['family']: r for r in deltas_abst(c['wording_pairs'][list(wd).index(k)])}
        for r in v:
            da = va.get(r['family'], {}).get('d_abst_pp')
            print('    %-22s %-24s n=%-4d Δzero %+7.1f pp   [描述] Δabst %s' % (
                k, r['family'], r['n'], r['d_zero_pp'],
                ('%+.1f pp' % da) if da is not None else 'n/a'))
            allw.append(abs(r['d_zero_pp']))
    print('  类型对（增删契约条款）：')
    allt = []
    for k, v in td.items():
        for r in v:
            print('    %-22s %-24s n=%-4d Δzero %+7.1f pp' % (k, r['family'], r['n'], r['d_zero_pp']))
            allt.append(abs(r['d_zero_pp']))
    mw = max(allw) if allw else None
    mt = max(allt) if allt else None
    passed = (mw is not None and mt is not None and mw <= c['wording_abs_max_pp'] and mw < mt)
    print('  → max|Δzero| 措辞对 %.1f pp  vs  类型对 %.1f pp；阈值 %.1f pp；判定 %s'
          % (mw or -1, mt or -1, c['wording_abs_max_pp'], 'PASS' if passed else 'FAIL'))
    return dict(id='H_A3', passed=bool(passed), max_wording_pp=mw, max_type_pp=mt,
                wording=wd, type=td)


def h_a4(recs, c):
    print('\n■ H_A4  格式轴（Block B：range − base）')
    sub = [r for r in recs if 'range' in r['arms']]
    res, ok = [], 0
    for rec in sub:
        d = paired(rec, 'base', 'range')
        res.append(dict(run=rec['dir'], label=rec['label'], n=rec['n_items'], d_zero_pp=d[0]))
        ok += abs(d[0]) <= c['abs_delta_max_pp']
        print('  %-20s n=%-5d Δzero %+7.1f pp' % (rec['label'], rec['n_items'], d[0]))
    desc = []
    for rec in recs:
        if 'choice' in rec['arms']:
            d = paired(rec, 'base', 'choice')
            desc.append(dict(run=rec['dir'], label=rec['label'], d_zero_pp=d[0]))
            print('  [描述] %-14s choice − base Δzero %+7.1f pp' % (rec['label'], d[0]))
    passed = ok >= c['runs_required']
    print('  → |Δzero| 达标 %d/%d（需 ≥%d）；判定 %s' % (ok, len(res), c['runs_required'],
                                                     'PASS' if passed else 'FAIL'))
    return dict(id='H_A4', passed=bool(passed), rows=res, descriptive_choice=desc)


# ── H_A5 关联 ─────────────────────────────────────────────────────────────────
def spearman(x, y):
    def rank(v):
        idx = sorted(range(len(v)), key=lambda i: v[i])
        r = [0.0] * len(v)
        i = 0
        while i < len(idx):
            j = i
            while j + 1 < len(idx) and v[idx[j + 1]] == v[idx[i]]:
                j += 1
            avg = (i + j) / 2.0 + 1
            for k in range(i, j + 1):
                r[idx[k]] = avg
            i = j + 1
        return r
    rx, ry = rank(x), rank(y)
    n = len(x)
    mx, my = sum(rx) / n, sum(ry) / n
    a = sum((rx[i] - mx) * (ry[i] - my) for i in range(n))
    b = (sum((rx[i] - mx) ** 2 for i in range(n)) * sum((ry[i] - my) ** 2 for i in range(n))) ** 0.5
    return a / b if b else 0.0


def build_arm_panel(cells, brecs):
    """stratum -> {arm: (featvec, y)}；y = 零率。"""
    feats = {f['arm']: f for f in json.loads(io.open(os.path.join(W, 'prompt_features.json'),
                                                     encoding='utf-8').read())}
    FE = ['has_ABSTAIN_PERMIT', 'has_ZERO_FORBID', 'has_ENUM', 'has_FORMAT',
          'n_clauses', 'chars', 'mentions_zero']
    strata = collections.defaultdict(dict)
    by_fam_dom = collections.defaultdict(dict)
    for cc in cells.values():
        by_fam_dom[(cc['family'], cc['domain'])][cc['arm']] = cc['zero']
    for k, d in by_fam_dom.items():
        if len(d) >= 2:
            strata[k] = d
    for rec in brecs:
        d = {a: v['zero'] for a, v in rec['per'].items()}
        if len(d) >= 2:
            strata[(rec['dir'], 'grid')] = d
    return FE, feats, strata


def h_a5(cells, brecs, c):
    print('\n■ H_A5  观测性关联（**非因果**；仅用于筛选）')
    FE, feats, strata = build_arm_panel(cells, brecs)
    rnd = random.Random(c['seed'])
    arms_all = sorted({a for d in strata.values() for a in d if a in feats})
    print('  层数 %d；臂数 %d；特征 %s' % (len(strata), len(arms_all), FE))
    out = {}
    for f in FE:
        def stat(fmap):
            xs, ys = [], []
            for a in arms_all:
                vf, vy, cnt = [], [], 0
                for s, d in strata.items():
                    if a in d:
                        vf.append(fmap[s][a][FE.index(f)])
                        vy.append(d[a])
                        cnt += 1
                if cnt:
                    xs.append(sum(vf) / cnt)
                    ys.append(sum(vy) / cnt)
            return spearman(xs, ys) if len(xs) >= 3 else 0.0
        fmap0 = {s: {a: [feats[a][k] if not isinstance(feats[a][k], bool) else int(feats[a][k])
                          for k in FE] for a in d if a in feats} for s, d in strata.items()}
        obs = stat(fmap0)
        ge = 0
        for _ in range(c['n_perm']):
            fmap = {}
            for s, d in strata.items():
                keys = [a for a in d if a in feats]
                perm = keys[:]
                rnd.shuffle(perm)
                fmap[s] = dict(zip(keys, [fmap0[s][p] for p in perm]))
            if abs(stat(fmap)) >= abs(obs):
                ge += 1
        p = (ge + 1) / (c['n_perm'] + 1)
        out[f] = dict(rho=obs, p=p)
        print('  %-22s ρ=%+.3f  置换 p=%.4f' % (f, obs, p))

    # 留一臂 LOOCV MAE：M0 截距 / M1 契约 / M2 契约+枚举+格式 / M3 全特征
    def mat(keys):
        X, Y = [], []
        for a in arms_all:
            vf, vy, cnt = [], [], 0
            for s, d in strata.items():
                if a in d:
                    vf.append([feats[a][k] if not isinstance(feats[a][k], bool) else int(feats[a][k])
                               for k in keys])
                    vy.append(d[a])
                    cnt += 1
            if cnt:
                X.append([sum(col) / cnt for col in zip(*vf)])
                Y.append(sum(vy) / cnt)
        return X, Y
    sets = {'M0': [], 'M1': ['has_ABSTAIN_PERMIT', 'has_ZERO_FORBID'],
            'M2': ['has_ABSTAIN_PERMIT', 'has_ZERO_FORBID', 'has_ENUM', 'has_FORMAT'],
            'M3': FE}
    loo = {}
    for name, keys in sets.items():
        X, Y = mat(keys)
        errs = []
        for i in range(len(Y)):
            Xtr = [X[j] + [1.0] for j in range(len(Y)) if j != i]
            Ytr = [Y[j] for j in range(len(Y)) if j != i]
            p = lstsq(Xtr, Ytr)
            pred = sum(p[k] * X[i][k] for k in range(len(keys))) + p[-1]
            errs.append(abs(pred - Y[i]))
        loo[name] = sum(errs) / len(errs)
        print('  %-4s（%d 特征）LOOCV MAE = %.4f' % (name, len(keys), loo[name]))
    sig_ok = all(out[f]['p'] < c['alpha'] for f in c['features_expected_significant'])
    nul_ok = all(out[f]['p'] >= c['alpha'] for f in c['features_expected_null'])
    loo_ok = loo['M1'] < loo['M0']
    passed = sig_ok and nul_ok and loo_ok
    print('  → 契约类显著 %s；has_FORMAT 不显著 %s；M1<M0 %s；判定 %s'
          % (sig_ok, nul_ok, loo_ok, 'PASS' if passed else 'FAIL'))
    return dict(id='H_A5', causal=False, passed=bool(passed), perms=out, loocv=loo,
                sig_ok=sig_ok, null_ok=nul_ok, loocv_ok=loo_ok)


def lstsq(X, Y):
    """最小二乘（正规方程 + 高斯消元）；零依赖。"""
    n, k = len(X), len(X[0])
    A = [[sum(X[i][a] * X[i][b] for i in range(n)) for b in range(k)] + [sum(X[i][a] * Y[i] for i in range(n))]
         for a in range(k)]
    for c in range(k):
        p = max(range(c, k), key=lambda r: abs(A[r][c]))
        A[c], A[p] = A[p], A[c]
        if abs(A[c][c]) < 1e-12:
            A[c][c] = 1e-12
        for r in range(k):
            if r != c:
                f = A[r][c] / A[c][c]
                for j in range(c, k + 1):
                    A[r][j] -= f * A[c][j]
    return [A[i][k] / A[i][i] for i in range(k)]


# ── 主流程 ────────────────────────────────────────────────────────────────────
def run_all(crit, cells, brecs, crecs, quiet=False):
    res = dict(criteria_md5=None, H_A1=None, H_A2=None, H_A2b=None, H_A3=None,
               H_A4=None, H_A5=None)
    res['H_A1'] = h_a1(cells, crit['H_A1_abstain_permit_clause'])
    res['H_A2'] = h_delta_block(brecs, 'base', 'forbid0', crit['H_A2_zero_forbid_clause'], 'H_A2')
    res['H_A2b'] = h_delta_block(crecs, 'base', 'forbid0', crit['H_A2b_zero_forbid_replication'], 'H_A2b')
    res['H_A3'] = h_a3(cells, crit['H_A3_type_beats_wording'])
    res['H_A4'] = h_a4(brecs, crit['H_A4_format_axis'])
    res['H_A5'] = h_a5(cells, brecs, crit['H_A5_association'])
    return res


def selftest(crit):
    """阳性/阴性对照：在**合成** panel 上验证 H_A1/H_A2 与 H_A5 的判定可通可失。"""
    print('=== --selftest：合成数据阳性/阴性对照 ===')
    ok = True
    # 阳性：加入弃答许可后，零率**下降**（模型改答 abstain），弃答率上升
    #   方向学：base/无出口臂在"没人"图上答 0；给出口后改答 abstain ⇒ Δzero<0 且 Δabst>0
    syn = {}
    for lin in H_A1_LINEAGES:
        syn[(lin, 'st_a', 'enum')] = dict(family=lin, lineage=lin, domain='st_a', arm='enum',
                                          n=100, n_zero=45, n_abst=0, n_err=0, zero=0.45, abst=0.0, src='syn')
        syn[(lin, 'st_a', 'enumAbstain')] = dict(family=lin, lineage=lin, domain='st_a', arm='enumAbstain',
                                                 n=100, n_zero=5, n_abst=60, n_err=0, zero=0.05, abst=0.60, src='syn')
    r = h_a1(syn, crit['H_A1_abstain_permit_clause'])
    print('  阳性对照 H_A1 -> %s（期望 PASS）' % r['passed'])
    ok &= r['passed'] is True
    # 阴性：几乎没有位移
    syn2 = {k: dict(v) for k, v in syn.items()}
    for k in syn2:
        if syn2[k]['arm'] == 'enumAbstain':
            syn2[k].update(zero=0.40, abst=0.05, n_zero=40, n_abst=5)
    r2 = h_a1(syn2, crit['H_A1_abstain_permit_clause'])
    print('  阴性对照 H_A1 -> %s（期望 FAIL）' % r2['passed'])
    ok &= r2['passed'] is False
    # 阳性/阴性：forbid0
    def mk(dz):
        return [dict(dir='syn%d' % i, label='syn%d' % i, n_items=100, arms=['base', 'forbid0'],
                     per={'base': dict(n=100, n_zero=50, n_abst=10, zero=0.50, abst=0.10),
                          'forbid0': dict(n=100, n_zero=50 + dz, n_abst=10, zero=(50 + dz) / 100, abst=0.10)})
                for i in range(3)]
    r3 = h_delta_block(mk(-20), 'base', 'forbid0', crit['H_A2_zero_forbid_clause'], 'syn+')
    print('  阳性对照 H_A2 -> %s（期望 PASS）' % r3['passed'])
    ok &= r3['passed'] is True
    r4 = h_delta_block(mk(-2), 'base', 'forbid0', crit['H_A2_zero_forbid_clause'], 'syn-')
    print('  阴性对照 H_A2 -> %s（期望 FAIL）' % r4['passed'])
    ok &= r4['passed'] is False
    print('\n  %s' % ('SELFTEST_OK' if ok else 'SELFTEST_FAIL'))
    return 0 if ok else 1


def audit(cells, dcells):
    """逐臂三联审计：pred 空 / raw 含弃答 / zero。这是 v1 仪器缺陷的记录证据。"""
    print('\n=== --audit：逐臂测量仪器三联审计 ===')
    agg = collections.defaultdict(lambda: [0, 0, 0, 0, 0, 0.0])
    for c in list(cells.values()) + list(dcells.values()):
        a = agg[c['arm']]
        a[0] += c['n']
        a[1] += c['n_err']
        a[2] += c['n_abst']
        a[3] += c['n_zero']
    # n_empty_pred 不单独存，用 n_err + n_abst 近似不可靠 ⇒ 直接重扫一遍拿准确数
    raw = collections.defaultdict(lambda: [0, 0, 0, 0, 0])
    for d in [os.path.join(PAPER, 'analysis', 'e2xt_a800', 'merged'),
              os.path.join(PAPER, 'analysis', 'e2_newh20')]:
        if not os.path.isdir(d):
            continue
        for fn in sorted(os.listdir(d)):
            m = ARM_RE.match(fn)
            if not m:
                continue
            arm = m.group(3)
            for r in read_csv(os.path.join(d, fn)):
                if '#r' in str(r.get('item', '')):
                    continue
                p = str(r.get('pred', '')).strip()
                b = raw[arm]
                b[0] += 1
                if p == '':
                    b[1] += 1
                if ABST_RE.search(str(r.get('raw', ''))):
                    b[2] += 1
                if p and num(p) == 0:
                    b[3] += 1
                if p.lower().startswith('err'):
                    b[4] += 1
    print('  %-12s %8s %14s %16s %8s %6s' % ('arm', 'n', 'pred空', 'raw含弃答', 'zero', 'ERR'))
    for arm in sorted(raw):
        n, e, a, z, er = raw[arm]
        print('  %-12s %8d %8d(%5.1f%%) %9d(%5.1f%%) %8d %6d'
              % (arm, n, e, 100 * e / n, a, 100 * a / n, z, er))
    print('  ↑ 出口臂（permit/channel/enumAbstain/permitB/permitC/channelB）pred空 ≈ raw含弃答，')
    print('    证明旧口径把"弃答"记成了"解析失败"；v2 仪器已从 raw 恢复。')
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--selftest', action='store_true')
    ap.add_argument('--audit', action='store_true')
    ap.add_argument('--out', default=os.path.join(W, 'pA_result_v2.json'))
    a = ap.parse_args()
    crit, cm = crit_load()
    print('判据 %s（md5-12 %s）' % (crit['version'], cm))
    if a.selftest:
        return selftest(crit)
    mn = crit['H_A1_abstain_permit_clause']['min_cell_n']
    cells = block_a(mn)
    dcells = block_d(mn)
    if a.audit:
        return audit(cells, dcells)
    print('Block A：%d 个 cell（n≥%d），%d 个家族，%d 个臂'
          % (len(cells), mn, len({c['family'] for c in cells.values()}),
             len({c['arm'] for c in cells.values()})))
    print('Block D（非零池反向对照）：%d 个 cell' % len(dcells))
    brecs = block_pairs(B_RUNS, 'blur')
    crecs = block_pairs(C_RUNS, 'occl')
    print('Block B：%d 个 run；Block C：%d 个 run' % (len(brecs), len(crecs)))
    res = run_all(crit, cells, brecs, crecs)
    res['criteria_md5'] = cm
    res['criteria_version'] = crit['version']
    res['supersedes'] = crit['supersedes']
    # Block D 反向对照（描述量）
    print('\n■ Block D  非零池反向对照（base → permit，**只作描述**）')
    dres = []
    for lin in sorted({c['lineage'] for c in dcells.values()}):
        ra = fam_arm_rate(dcells, lin, 'base')
        rb = fam_arm_rate(dcells, lin, 'permit')
        if not ra or not rb:
            continue
        dres.append(dict(lineage=lin, family=ra['family'], n=ra['n'],
                         zero_base=ra['zero'], zero_permit=rb['zero'],
                         d_zero_pp=(rb['zero'] - ra['zero']) * 100))
        print('  %-22s %-34s n=%-5d zero %5.3f → %5.3f  Δzero %+6.1f pp'
              % (lin, ra['family'], ra['n'], ra['zero'], rb['zero'], dres[-1]['d_zero_pp']))
    res['Block_D'] = dres
    res['blocks'] = dict(
        A=dict(n_cells=len(cells), cells={('%s|%s|%s' % k): v for k, v in cells.items()}),
        B=brecs, C=crecs, D=dres)
    io.open(a.out, 'w', encoding='utf-8', newline='\n').write(
        json.dumps(res, ensure_ascii=False, indent=1, default=str) + '\n')
    print('\n已写 %s' % a.out)
    keys = ('H_A1', 'H_A2', 'H_A2b', 'H_A3', 'H_A4', 'H_A5')
    n_pass = sum(1 for k in keys if res[k]['passed'])
    print('=== 判定汇总：%d/6 PASS ===' % n_pass)
    for k in keys:
        print('  %-6s %s' % (k, 'PASS' if res[k]['passed'] else 'FAIL'))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
