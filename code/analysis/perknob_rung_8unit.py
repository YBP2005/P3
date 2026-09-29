# -*- coding: utf-8 -*-
"""perknob_rung_8unit.py — 【S12 的第二列】在**冻结排序对象**（8-unit）上补 per-knob 那一档。

M.37 的表有**两列**：8-unit 列（冻结排序对象，逐位复现 `span_equalcount_result.json`）与 36-unit 列。
`a39_perknob_rung.py` 补的是 36-unit 列。本脚本补 8-unit 列，方法完全对称：
  1. **逐字复制** `per_unit_affine_heldout.py` 的载入、复现闸门与协议（seed 20260923、200 次分割、1/3 留出）；
  2. 先复现原六臂，与冻结件 `per_unit_affine_heldout_result.json` 逐臂比对，对不上就退出；
  3. 再加 **Ck**（按 knob 池化一张 (a,b)）、**SISOk**（按 knob 池化一张保序）、**SISOg**（全局保序）。

⚠ 本单元集的"knob"只有 **2 个**（`pxbudget(res_ctrl)` 与 `tiling`）—— 这是**冻结排序对象本身的构成**，
不是我的选择。故本列的 per-knob 档比 36-unit 列粗糙得多，报告里必须一并说明。

用法：python -u perknob_rung_8unit.py
输出：perknob_rung_8unit_result.json（新文件）
"""
import collections
import csv
import glob
import hashlib
import io
import json
import os
import random
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

ROOT = r'<WORKDIR>\PaperB'
WORK = os.path.join(ROOT, 'analysis', 'work')
PM = os.path.join(ROOT, 'analysis', 'data', 'pod_mirror')
FROZEN_SPAN = os.path.join(WORK, 'span_equalcount_result.json')
FROZEN_ARMS = os.path.join(WORK, 'per_unit_affine_heldout_result.json')
OUT = os.path.join(WORK, 'perknob_rung_8unit_result.json')
ANOM = 1e5
NSPLIT = 200
SEED = 20260923
CAL_FRAC = 1 / 3.0


def _kv(rows):
    out = {}
    for r in rows:
        try:
            gt, pr = float(r['gt']), float(r['pred'])
        except (TypeError, ValueError):
            continue
        if pr >= ANOM or gt <= 0:
            continue
        out[str(r['item'])] = (gt, pr)
    return out


def load_csv(p):
    with io.open(p, encoding='utf-8-sig') as f:
        return _kv([r for r in csv.DictReader(f) if '#r' not in str(r.get('item') or '')])


def load_csv_level(p, key, val):
    with io.open(p, encoding='utf-8-sig') as f:
        rows = [r for r in csv.DictReader(f) if '#r' not in str(r.get('item') or '')]
    return _kv([r for r in rows if r.get(key) == val])


LADDERS = {}
SRC = set()


def add(unit, levels, src):
    keys = None
    for _, d in levels:
        keys = set(d) if keys is None else (keys & set(d))
    keys = sorted(keys)
    if len(levels) >= 3 and keys:
        LADDERS[unit] = dict(levels=levels, keys=keys)
        SRC.add(src)


for mdl in ('q32', 'ivl'):
    for f in sorted(glob.glob(os.path.join(PM, 'res_ctrl__%s' % mdl, 'res_ctrl_*.csv'))):
        ds = os.path.basename(f)[len('res_ctrl_'):-4]
        with io.open(f, encoding='utf-8-sig') as fh:
            buds = sorted(set(r['budget'] for r in csv.DictReader(fh)), key=float)
        add('pxbudget(res_ctrl) / %s / %s' % (mdl, ds),
            [('budget=%s' % b, load_csv_level(f, 'budget', b)) for b in buds], f)

for ds in ('st_a', 'ucf', 'visdrone'):
    files = sorted(glob.glob(os.path.join(PM, 'tile_results', 'vlm_%s_base_tile*.csv' % ds)))
    if files:
        add('tiling / %s / base' % ds,
            [(os.path.basename(f).split('tile')[1][0], load_csv(f)) for f in files],
            os.path.join(PM, 'tile_results'))


def knob_of(name):
    return 'K6 VLM·pixel budget' if name.startswith('pxbudget') else 'K5 VLM·tiling level'


# ---------------- A39 族（逐字复制 per_unit_affine_heldout.py） ----------------
def rho(pairs, ab=None):
    if ab is not None:
        a, b = ab
        pairs = [(g, a * p + b) for g, p in pairs]
    sg = sum(g for g, _ in pairs)
    return 100.0 * (sum(p for _, p in pairs) - sg) / sg if sg else None


def fit_a(pairs):
    n = len(pairs)
    if n < 2:
        return 1.0, 0.0
    P = [p for _, p in pairs]; G = [g for g, _ in pairs]
    mp, mg = sum(P) / n, sum(G) / n
    spp = sum((x - mp) ** 2 for x in P)
    if spp == 0:
        return 0.0, mg
    a = sum((P[i] - mp) * (G[i] - mg) for i in range(n)) / spp
    return a, mg - a * mp


def fit_iso(pairs):
    from sklearn.isotonic import IsotonicRegression
    ir = IsotonicRegression(out_of_bounds='clip')
    ir.fit([p for _, p in pairs], [g for g, _ in pairs])
    return lambda P: [float(x) for x in ir.predict(P)]


def fit_qnt(pairs):
    cg = sorted(g for g, _ in pairs)
    cp = sorted(p for _, p in pairs)

    def f(P):
        out = []
        for x in P:
            lo, hi = 0, len(cp)
            while lo < hi:
                mid = (lo + hi) // 2
                if cp[mid] < x:
                    lo = mid + 1
                else:
                    hi = mid
            out.append(cg[min(lo, len(cg) - 1)])
        return out
    return f


def spearman(x, y):
    def rank(v):
        s = sorted(range(len(v)), key=lambda i: v[i])
        r = [0.0] * len(v)
        i = 0
        while i < len(s):
            j = i
            while j + 1 < len(s) and v[s[j + 1]] == v[s[i]]:
                j += 1
            avg = (i + j) / 2.0 + 1
            for t in range(i, j + 1):
                r[s[t]] = avg
            i = j + 1
        return r
    ra, rb = rank(x), rank(y)
    n = len(x)
    ma, mb = sum(ra) / n, sum(rb) / n
    num = sum((ra[i] - ma) * (rb[i] - mb) for i in range(n))
    da = sum((ra[i] - ma) ** 2 for i in range(n)) ** 0.5
    db = sum((rb[i] - mb) ** 2 for i in range(n)) ** 0.5
    return num / (da * db) if da and db else float('nan')


def q(v, p):
    v = sorted(v)
    return v[min(len(v) - 1, max(0, int(round(p * (len(v) - 1)))))]


# ---------------- 复现闸门（冻结跨度必须逐位相等） ----------------
fz_span = {r['unit']: r['span'] for r in json.load(io.open(FROZEN_SPAN, encoding='utf-8'))['units']}
print('=' * 112)
print('■ 复现闸门 A：重建的全 item 跨度 vs 冻结 span_equalcount_result.json')
print('=' * 112)
bad = []
for u in sorted(LADDERS):
    seq = [rho([d[k] for k in LADDERS[u]['keys']]) for _, d in LADDERS[u]['levels']]
    LADDERS[u]['span_full'] = max(seq) - min(seq)
    f = fz_span.get(u)
    ok = f is not None and abs(LADDERS[u]['span_full'] - f) < 1e-6
    if not ok:
        bad.append(u)
    print('  %-46s %12.4f %12s %s' % (u, LADDERS[u]['span_full'],
                                      ('%.4f' % f) if f is not None else '—', '✓' if ok else '✗'))
if bad:
    sys.exit('\n!! 闸门 A 未过：%s ⇒ 不进入下一步' % bad)
units = sorted(LADDERS)
print('  闸门 A 全过（%d units）' % len(units))
knob = {u: knob_of(u) for u in units}
grp = collections.defaultdict(list)
for u in units:
    grp[knob[u]].append(u)
for lab in sorted(grp):
    print('    %-26s %d units：%s' % (lab, len(grp[lab]), ', '.join(grp[lab])))
ref = [LADDERS[u]['span_full'] for u in units]

ARMS = ['C0e', 'C1u', 'C2l', 'Cg', 'ISO', 'QNT', 'Ck', 'SISOk', 'SISOg']
R = {k: [] for k in ARMS}
Rk = {k: {lab: [] for lab in grp} for k in ARMS}
kA = collections.defaultdict(list)
absA = {u: [] for u in units}
span_post = {u: {k: [] for k in ARMS} for u in units}
relCK = collections.defaultdict(list)
relCg = []

rng = random.Random(SEED)
for _ in range(NSPLIT):
    cal, ev = {}, {}
    for u in units:
        ks = list(LADDERS[u]['keys'])
        rng.shuffle(ks)
        nc = max(2, int(round(len(ks) * CAL_FRAC)))
        ck, ek = set(ks[:nc]), set(ks[nc:])
        cal[u] = {lb: [d[k] for k in ck] for lb, d in LADDERS[u]['levels']}
        ev[u] = {lb: [d[k] for k in ek] for lb, d in LADDERS[u]['levels']}
    C1 = {u: fit_a([x for lb in cal[u] for x in cal[u][lb]]) for u in units}
    Cg = fit_a([x for u in units for lb in cal[u] for x in cal[u][lb]])
    SISOg = fit_iso([x for u in units for lb in cal[u] for x in cal[u][lb]])
    Ck, SISOk = {}, {}
    for lab in grp:
        pool = [x for u in grp[lab] for lb in cal[u] for x in cal[u][lb]]
        Ck[lab] = fit_a(pool); SISOk[lab] = fit_iso(pool); kA[lab].append(Ck[lab][0])
    sp_unit = {k: {} for k in ARMS}
    for u in units:
        lab = knob[u]
        v = {k: [] for k in ARMS}
        for lb, _ in LADDERS[u]['levels']:
            e, c = ev[u][lb], cal[u][lb]
            v['C0e'].append(rho(e)); v['C1u'].append(rho(e, C1[u]))
            v['C2l'].append(rho(e, fit_a(c))); v['Cg'].append(rho(e, Cg))
            v['Ck'].append(rho(e, Ck[lab]))
            pe = [p for _, p in e]; sg = sum(g for g, _ in e)
            v['ISO'].append(100.0 * (sum(fit_iso(c)(pe)) - sg) / sg)
            v['QNT'].append(100.0 * (sum(fit_qnt(c)(pe)) - sg) / sg)
            v['SISOk'].append(100.0 * (sum(SISOk[lab](pe)) - sg) / sg)
            v['SISOg'].append(100.0 * (sum(SISOg(pe)) - sg) / sg)
            absA[u].append(abs(C1[u][0]))
        for k in ARMS:
            s = max(v[k]) - min(v[k])
            sp_unit[k][u] = s
            span_post[u][k].append(s)
    for lab in grp:
        _r = [sp_unit['Ck'][x] / sp_unit['C0e'][x] for x in grp[lab] if sp_unit['C0e'][x] > 1e-9]
        if len(_r) >= 2:
            relCK[lab].append(max(_r) - min(_r))
    _rs = [sp_unit['Cg'][x] / sp_unit['C0e'][x] for x in units if sp_unit['C0e'][x] > 1e-9]
    if len(_rs) >= 2:
        relCg.append(max(_rs) - min(_rs))
    for k in ARMS:
        R[k].append(spearman(ref, [sp_unit[k][u] for u in units]))
        for lab in grp:
            if len(grp[lab]) >= 3:
                Rk[k][lab].append(spearman([LADDERS[u]['span_full'] for u in grp[lab]],
                                           [sp_unit[k][u] for u in grp[lab]]))

fz_arms = json.load(io.open(FROZEN_ARMS, encoding='utf-8'))['arms']
print('\n' + '=' * 112)
print('■ 复现闸门 B：本脚本原六臂 vs 冻结件 per_unit_affine_heldout_result.json（= M.37 的 8-unit 列）')
print('=' * 112)
ok_all = True
for k in ('C0e', 'C1u', 'C2l', 'Cg', 'ISO', 'QNT'):
    mine, theirs = q(R[k], .5), fz_arms[k]['median']
    ok = abs(mine - theirs) < 5e-4
    ok_all &= ok
    print('  %-6s 本脚本 %.4f ｜ 冻结 %.4f ｜ Δ %+.4f  %s' % (k, mine, theirs, mine - theirs, '✓' if ok else '✗'))
if not ok_all:
    sys.exit('!! 闸门 B 未过 ⇒ 不允许加臂')
print('  闸门 B 6/6 全过。')


def line(v):
    return '%9.3f %13s %8.0f%% %8.0f%%' % (
        q(v, .5), '%.3f–%.3f' % (q(v, .05), q(v, .95)),
        100 * sum(1 for x in v if x >= .9) / len(v), 100 * sum(1 for x in v if x >= .8) / len(v))


NAMES = [('○ C0e 对照：留出但不校准', 'C0e'),
         ('★ Cg  全局单组 (a,b)              ← 上端点', 'Cg'),
         ('★★ Ck  按 knob 池化一组 (a,b)       ← **新·缺的中间档**', 'Ck'),
         ('★★ SISOk 按 knob 池化一张保序映射     ← **新**', 'SISOk'),
         ('★★ SISOg 全局一张保序映射           ← **新（上端点对照）**', 'SISOg'),
         ('★ C1u 逐 unit 一组 (a,b)           ← 下端点', 'C1u'),
         ('★ C2l 逐 unit 逐档 (a,b)', 'C2l'),
         ('★ ISO 逐 unit 逐档保序', 'ISO'),
         ('★ QNT 逐 unit 逐档分位数映射', 'QNT')]

print('\n' + '=' * 112)
print('■ 8-unit 冻结排序对象：排序保持性（%d 次分割、1/3 留出、seed %d）' % (NSPLIT, SEED))
print('=' * 112)
print('  %-46s %9s %13s %9s %9s' % ('臂', '中位 ρ', '5–95%', 'P(≥0.9)', 'P(≥0.8)'))
for nm, k in NAMES:
    print('  %-46s %s' % (nm, line(R[k])))
print('  ⚠ 本列只有 **2 个 knob**（pxbudget 6 + tiling 2）⇒ per-knob 与 per-unit 的差别比 36-unit 列小得多。')

print('\n' + '=' * 112)
print('■ 标定后的跨度大小（本列）')
print('=' * 112)
print('  %-46s %9s %9s %9s %11s' % ('臂', 'span中位', 'span最小', 'span最大', '保留率极差'))
mag = {}
for k in ('C0e', 'Cg', 'Ck', 'SISOk', 'SISOg', 'C1u', 'C2l', 'ISO', 'QNT'):
    meds = [q(span_post[u][k], .5) for u in units]
    rets = [q(span_post[u][k], .5) / LADDERS[u]['span_full'] for u in units]
    sp = max(rets) / min(rets) if min(rets) > 0 else float('nan')
    mag[k] = dict(span_median=q(meds, .5), span_min=min(meds), span_max=max(meds),
                  retention_spread_x=sp)
    print('  %-46s %9.2f %9.2f %9.2f %10s' % (k, q(meds, .5), min(meds), max(meds),
                                              ('%.0f×' % sp) if sp == sp else 'nan'))
print('\n  knob 级 |a_k|：%s' % '；'.join('%s = %.3f（knob 内 span 比极差 %.1e）'
                                        % (lab, q(kA[lab], .5), max(relCK[lab])) for lab in sorted(grp)))
print('  全局单因子：逐 unit 跨度比极差 %.2e' % max(relCg))

json.dump(dict(
    script='perknob_rung_8unit.py',
    unit_set='frozen ordering object (8 units: pxbudget(res_ctrl) 6 + tiling 2)',
    protocol=dict(nsplit=NSPLIT, seed=SEED, calib_frac=CAL_FRAC),
    knobs={lab: grp[lab] for lab in sorted(grp)},
    n_units=len(units),
    arms={k: dict(median=q(R[k], .5), p05=q(R[k], .05), p95=q(R[k], .95),
                  frac_ge_090=sum(1 for x in v if x >= .9) / len(v),
                  frac_ge_080=sum(1 for x in v if x >= .8) / len(v)) for k, v in R.items()},
    replication_gate=dict(frozen=os.path.basename(FROZEN_ARMS),
                          frozen_md5=hashlib.md5(io.open(FROZEN_ARMS, 'rb').read()).hexdigest(),
                          max_abs_delta=max(abs(q(R[k], .5) - fz_arms[k]['median'])
                                            for k in ('C0e', 'C1u', 'C2l', 'Cg', 'ISO', 'QNT'))),
    within_knob_spearman={k: {lab: q(Rk[k][lab], .5) for lab in grp if Rk[k][lab]}
                          for k in ('C0e', 'Cg', 'Ck', 'C1u')},
    knob_scale_factors={lab: dict(a_median=q(kA[lab], .5), within_knob_span_ratio_max_range=max(relCK[lab]))
                        for lab in sorted(grp)},
    magnitudes=mag,
    unit_span_full={u: LADDERS[u]['span_full'] for u in units},
), io.open(OUT, 'w', encoding='utf-8', newline='\n'), ensure_ascii=False, indent=2)
print('\n已写出 %s' % OUT)
print('  %-56s %s' % (os.path.basename(FROZEN_SPAN),
                      hashlib.md5(io.open(FROZEN_SPAN, 'rb').read()).hexdigest()))
print('  %-56s %s' % (os.path.basename(FROZEN_ARMS),
                      hashlib.md5(io.open(FROZEN_ARMS, 'rb').read()).hexdigest()))
for p in sorted(SRC):
    if os.path.isfile(p):
        print('  %-56s %s' % (os.path.basename(p),
                              hashlib.md5(io.open(p, 'rb').read()).hexdigest()))
