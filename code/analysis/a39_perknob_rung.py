# -*- coding: utf-8 -*-
"""a39_perknob_rung.py — 【S12 闭环】补上校准阶梯**缺的中间那一档**：per-knob（跨域池化）。

## 为什么写这个脚本
两家评审独立指出：M.37 的校准阶梯只量了两个**端点** ——
"**一张全局共享映射**"（Cg）与"**逐单元重拟合**"（C1u）；**中间那一档从没量过**：
"**按 knob 池化、每个 knob 一张映射**"。另一位评审另加一句：M.37 报了各校准器下的**排序**（Spearman），
**从没报过逐单元标定之后的跨度大小**。

## 本脚本的纪律（最关键的一条：**先复现，再加臂**）
新增一档只有在**同一脚本、同一协议**下才有可比性。所以：
  1. **逐字复制** `a39_unit_calib_heldout.py` 的单元构建与协议（随机 1/3 标定折、seed 20260923、200 次分割）；
  2. 先算**原有六臂**，与冻结件 `a39_unit_calib_heldout_result.json`（M.37 的 36-unit 列就是它）**逐臂比对**；
     **对不上就退出**，不继续加臂；
  3. 复现通过后才加新臂：
       · **Ck**   = **按 knob 池化**拟合**一张**仿射 (a,b)，对该 knob 的全部 unit 应用 —— ★ 缺的那一档
       · **SISOk**= 按 knob 池化拟合**一张保序**映射（评审说 "if feasible" 的那半）
       · **SISOg**= 全局一张保序映射（把保序族的**上端点**也补上，与 SISOk 夹出"全局↔逐knob"）
   ⚠ **不设 "按 knob × 逐档" 这一臂**：knob 内各 unit 的档位标签并不共享
     （例如 tiling 的 `whole/2x2/tile3/tile4` 与密度阶梯的 `value` 不是同一把尺），
     故"knob 的第 i 档"**无定义**。宁可少一格，不发明定义。
  4. 另加两项 M.37 没有的量：
       · **knob 内 / knob 间排序分解**（per-knob 档的结构性预测：knob 内精确保序，只有 knob 间被 |a_k| 缩放）
       · **标定后的跨度大小**（每 unit 每档下的 span 及其保留率）—— 第二位评审要的那半。

## 定义对齐（与既有档一致）
  fit_a(P,G) = lstsq([P,1],G) ⇒ pred′ = a·pred + b（回归 G on P，可部署；A39 定义）
  ρ(l) = 100·(Σpred − Σgt)/Σgt，在该 unit 各档的**公共 item 交集**上算 ⇒ Σgt 与 n 跨档不变
  span = max_l ρ(l) − min_l ρ(l)
  ⇒ 系数与档位无关时 ρ′(l) = a·ρ(l) + c（c 与档位无关）⇒ **span′ = |a|·span 精确成立**

用法：python -u a39_perknob_rung.py
输出：a39_perknob_rung_result.json（新文件）+ 屏幕报告
"""
import collections
import csv
import glob
import hashlib
import io
import json
import os
import random
import re
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

W = r'<WORKDIR>\PaperB\analysis\work'
PM = r'<WORKDIR>\PaperB\analysis\data\pod_mirror'
WW = r'E:\Edu_workplace\work'
B = os.path.join(WW, 'b_harvest_20260917')
FROZEN36 = os.path.join(W, 'a39_unit_calib_heldout_result.json')
OUT = os.path.join(W, 'a39_perknob_rung_result.json')
ANOM, SENT = 1e5, 1234567890
NSPLIT = 200
SEED = 20260923
CAL_FRAC = 1 / 3.0
MIN_ITEMS = 20

# F.2（补充材料 L300–L307）的**六个 knob**；单元名前缀决定归属。
KNOBS = [('K1 detection·threshold τ × input size', 'det·'),
         ('K2 density regression·input scale', 'density·'),
         ('K3 VLM·output contract', 'VLM·output contract'),
         ('K4 VLM·prompt family', 'VLM·prompt family'),
         ('K5 VLM·tiling level', 'VLM·tiling'),
         ('K6 VLM·pixel budget', 'VLM·pixel budget')]
KL = [lab for lab, _ in KNOBS]


def knob_of(name):
    for lab, pref in KNOBS:
        if name.startswith(pref):
            return lab
    return None


def load(p):
    return list(csv.DictReader(io.open(p, encoding='utf-8-sig', errors='replace')))


def fn(s):
    try:
        return float(s)
    except Exception:
        return None


def unitize(rows, dims, pcol):
    out = collections.defaultdict(dict)
    for r in rows:
        g = fn(r.get('gt')); p = fn(r.get(pcol))
        if g is None or g <= 0 or p is None or p >= ANOM or p == SENT:
            continue
        try:
            key = tuple(str(r[d]).strip() for d in dims)
        except KeyError:
            continue
        out[key][str(r['item']).strip()] = (g, float(p))
    return out


UNITS = {}
SRC = set()


def add_unit(name, bylevel, src):
    lv = sorted(bylevel)
    if len(lv) < 3:
        return
    common = set.intersection(*[set(bylevel[s]) for s in lv])
    if len(common) < MIN_ITEMS:
        return
    UNITS[name] = dict(levels=[(s, bylevel[s]) for s in lv], keys=sorted(common))
    SRC.add(src)


# ================= 一、单元集（逐字复制 a39_unit_calib_heldout.py） =================
for lab, path, pcol in (
        ('det·in-domain/VisDrone', os.path.join(PM, 'A', 'det_yolo_ladder_visdrone_det.csv'), 'n_det_person'),
        ('det·zero-shot COCO', os.path.join(PM, 'A', 'det_yolo_ladder_yolo12n.csv'), 'n_det_person'),
        ('det·in-domain(micro)/BBBC005', os.path.join(B, 'bbbc_eval', 'ladder.csv'), 'n_det')):
    if not os.path.exists(path):
        continue
    u = unitize(load(path), ['tau', 'imgsz'], pcol)
    add_unit(lab + ' (full grid)', {k: v for k, v in u.items()}, path)
    for sz in sorted({k[1] for k in u if len(k) > 1}):
        add_unit('%s / tau@%s' % (lab, sz), {k: v for k, v in u.items() if len(k) > 1 and k[1] == sz}, path)

p = os.path.join(WW, 'dm_ladder.csv')
if os.path.exists(p):
    u = unitize(load(p), ['dataset', 'protocol', 'value'], 'pred')
    for ds in sorted({k[0] for k in u}):
        add_unit('density·official DM-Count / %s' % ds, {k: v for k, v in u.items() if k[0] == ds}, p)
for lab, path in (('density·CSRNet', os.path.join(PM, 'A', 'csrsta_ladder_st_a.csv')),
                  ('density·CSRNet', os.path.join(PM, 'A', 'csrucf_ladder_ucf.csv'))):
    if os.path.exists(path):
        u = unitize(load(path), ['protocol', 'value'], 'pred')
        add_unit('%s / %s' % (lab, os.path.basename(path).split('_')[-2]), {k: v for k, v in u.items()}, path)

for mdl in ('ivl', 'q32'):
    for f in sorted(glob.glob(os.path.join(PM, 'res_ctrl__%s' % mdl, 'res_ctrl_*.csv'))):
        ds = os.path.basename(f)[len('res_ctrl_'):-4]
        u = unitize(load(f), ['budget'], 'pred')
        add_unit('VLM·pixel budget / %s / %s' % (mdl, ds), {k: v for k, v in u.items()}, f)

for sub, mdl in (('tile_results', 'Qwen32B'), ('b2__out_32b_ctile', 'Qwen32B(ctile)'),
                 ('b2__out_8b_ctile', 'Qwen8B(ctile)')):
    d = os.path.join(PM, sub)
    if not os.path.isdir(d):
        continue
    groups = collections.defaultdict(dict)
    for f in sorted(os.listdir(d)):
        m = re.match(r'^vlm_([a-z0-9]+)_(base|over|under|[a-z0-9]+)_(whole|tile\d+)\.csv$', f)
        if not m:
            continue
        dom, arm, lvl = m.groups()
        d2 = {}
        for r in load(os.path.join(d, f)):
            g = fn(r.get('gt')); pp = fn(r.get('pred'))
            if g is None or g <= 0 or pp is None or pp >= ANOM or pp == SENT:
                continue
            d2[str(r['item']).strip()] = (g, float(pp))
        groups[(dom, arm)][lvl] = d2
    for (dom, arm), bl in sorted(groups.items()):
        add_unit('VLM·tiling / %s / %s / %s' % (mdl, dom, arm), bl, d)

for mdl, pth in (('ivl', os.path.join(PM, 'b2__out_ivl', 'E1.csv')),
                 ('q32', os.path.join(PM, 'b2__out_q32', 'E1.csv'))):
    if os.path.exists(pth):
        u = unitize(load(pth), ['arm'], 'pred')
        add_unit('VLM·output contract / %s' % mdl, {k: v for k, v in u.items()}, pth)

for sub, mdl in (('dense_prompt_results', 'Qwen32B'), ('ivl_dense_prompt_results', 'IVL')):
    d = os.path.join(PM, sub)
    if not os.path.isdir(d):
        continue
    groups = collections.defaultdict(dict)
    for f in sorted(os.listdir(d)):
        m = re.match(r'^([a-z0-9]+)_(base|over|under)_(V\d+)_([a-z_]+)\.csv$', f)
        if not m:
            continue
        dom, arm, lvl, _ = m.groups()
        d2 = {}
        for r in load(os.path.join(d, f)):
            g = fn(r.get('gt')); pp = fn(r.get('pred'))
            if g is None or g <= 0 or pp is None or pp >= ANOM or pp == SENT:
                continue
            d2[str(r['item']).strip()] = (g, float(pp))
        groups[(dom, arm)][lvl] = d2
    for (dom, arm), bl in sorted(groups.items()):
        add_unit('VLM·prompt family / %s / %s / %s' % (mdl, dom, arm), bl, d)


# ================= 二、工具（与既有脚本逐字一致） =================
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


def md5(p):
    if os.path.isdir(p):      # 目录型来源（tile_results / dense_prompt_results）：列出文件名再取摘要
        h = hashlib.md5()
        for f in sorted(os.listdir(p)):
            h.update(f.encode('utf-8'))
            h.update(hashlib.md5(io.open(os.path.join(p, f), 'rb').read()).hexdigest().encode())
        return h.hexdigest() + ' (dir)'
    return hashlib.md5(io.open(p, 'rb').read()).hexdigest()


# ================= 三、跑：先复现，再加臂 =================
units = sorted(UNITS)
knob = {u: knob_of(u) for u in units}
unknown = [u for u in units if knob[u] is None]
grp = collections.defaultdict(list)
for u in units:
    grp[knob[u]].append(u)

RETIRED = ['density·CSRNet / st', 'density·CSRNet / ladder']   # M.37 自己判为"已退役实现缺陷"的两个 unit
DROPRET = '--drop-retired' in sys.argv
if DROPRET:
    units = [u for u in units if u not in RETIRED]
    grp = collections.defaultdict(list)
    for u in units:
        grp[knob[u]].append(u)
    globals()['OUT'] = OUT.replace('.json', '_drop2retired.json')

print('=' * 116)
print('■ 单元集：%d 个（A39 规则：档位≥3 且各档 item 交集≥%d）｜knob 划分按补充材料 F.2（L300–L307）%s'
      % (len(units), MIN_ITEMS, '｜**已剔除 M.37 判为退役的两个 CSRNet 复现**' if DROPRET else ''))
print('=' * 116)
for lab in KL:
    print('  %-42s %2d units' % (lab, len(grp[lab])))
if unknown:
    sys.exit('!! 归不进 knob 的 unit：%s' % unknown)
assert len(units) == (34 if DROPRET else 36), '单元数 %d ≠ %d，与 M.37 的 36-unit 列不同源' % (
    len(units), 34 if DROPRET else 36)

for u in units:
    seq = [rho([d[k] for k in UNITS[u]['keys']]) for _, d in UNITS[u]['levels']]
    UNITS[u]['span_full'] = max(seq) - min(seq)
ref = [UNITS[u]['span_full'] for u in units]

ARMS = ['C0e', 'C1u', 'C2l', 'Cg', 'ISO', 'QNT', 'Ck', 'SISOk', 'SISOg']
R = {k: [] for k in ARMS}
Rk = {k: {lab: [] for lab in KL} for k in ARMS}
Rknob = {k: [] for k in ARMS}
kA = {lab: [] for lab in KL}
knobA_abs = {lab: [] for lab in KL}
relCK = {lab: [] for lab in KL}
relCg = []
absA = {u: [] for u in units}
span_post = {u: {k: [] for k in ARMS} for u in units}

rng = random.Random(SEED)
for _ in range(NSPLIT):
    cal, ev = {}, {}
    for u in units:
        ks = list(UNITS[u]['keys'])
        rng.shuffle(ks)
        nc = max(2, int(round(len(ks) * CAL_FRAC)))
        ck, ek = set(ks[:nc]), set(ks[nc:])
        cal[u] = {lb: [d[k] for k in ck] for lb, d in UNITS[u]['levels']}
        ev[u] = {lb: [d[k] for k in ek] for lb, d in UNITS[u]['levels']}
    C1 = {u: fit_a([x for lb in cal[u] for x in cal[u][lb]]) for u in units}
    Cg = fit_a([x for u in units for lb in cal[u] for x in cal[u][lb]])
    SISOg = fit_iso([x for u in units for lb in cal[u] for x in cal[u][lb]])
    Ck, SISOk = {}, {}
    for lab in KL:
        pool = [x for u in grp[lab] for lb in cal[u] for x in cal[u][lb]]
        Ck[lab] = fit_a(pool)
        SISOk[lab] = fit_iso(pool)
        kA[lab].append(Ck[lab][0])
    sp_unit = {k: {} for k in ARMS}
    for u in units:
        lab = knob[u]
        v = {k: [] for k in ARMS}
        for lb, _ in UNITS[u]['levels']:
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
        s0 = max(v['C0e']) - min(v['C0e'])
        for k in ARMS:
            s = max(v[k]) - min(v[k])
            sp_unit[k][u] = s
            span_post[u][k].append(s)
    # ★ knob 内 / 全局 的 span 比极差必须在**本分割全部 unit 填完之后**算
    for lab2 in KL:
        _r = [sp_unit['Ck'][x] / sp_unit['C0e'][x] for x in grp[lab2] if sp_unit['C0e'][x] > 1e-9]
        if len(_r) >= 2:
            relCK[lab2].append(max(_r) - min(_r))
    _rs = [sp_unit['Cg'][x] / sp_unit['C0e'][x] for x in units if sp_unit['C0e'][x] > 1e-9]
    if len(_rs) >= 2:
        relCg.append(max(_rs) - min(_rs))
    for k in ARMS:
        R[k].append(spearman(ref, [sp_unit[k][u] for u in units]))
        # ★ knob 层面（6 点）的排序：knob 内被抹平 ⇒ 只剩 knob **之间**的排序
        _mk = [q([sp_unit[k][u] for u in grp[lab]], .5) for lab in KL]
        _rk = [q([UNITS[u]['span_full'] for u in grp[lab]], .5) for lab in KL]
        Rknob[k].append(spearman(_rk, _mk))
        for lab in KL:
            if len(grp[lab]) >= 3:
                Rk[k][lab].append(spearman([UNITS[u]['span_full'] for u in grp[lab]],
                                           [sp_unit[k][u] for u in grp[lab]]))

# ---------- 复现闸门 ----------
fz = json.load(io.open(FROZEN36, encoding='utf-8'))['arms']
print('\n' + '=' * 116)
print('■ 复现闸门：本脚本的原六臂 vs 冻结件 %s' % os.path.basename(FROZEN36))
print('=' * 116)
gate_ok = True
for k in ('C0e', 'C1u', 'C2l', 'Cg', 'ISO', 'QNT'):
    mine, theirs = q(R[k], .5), fz[k]['median']
    ok = abs(mine - theirs) < 5e-4
    gate_ok &= ok
    print('  %-6s 本脚本 %.4f ｜ 冻结 %.4f ｜ Δ %+.4f  %s' % (k, mine, theirs, mine - theirs, '✓' if ok else '✗'))
if not gate_ok:
    sys.exit('!! 复现闸门未过 ⇒ 两侧不同源，**不允许**在此基础上加臂')
print('  复现闸门 6/6 全过 ⇒ 新臂与既有臂同源同协议（同文件、同资格规则、同 seed、同 200 次分割）。')


def line(v):
    if any(x != x for x in v):
        return '   nan(退化)'
    return '%9.3f %13s %8.0f%% %8.0f%%' % (
        q(v, .5), '%.3f–%.3f' % (q(v, .05), q(v, .95)),
        100 * sum(1 for x in v if x >= .9) / len(v), 100 * sum(1 for x in v if x >= .8) / len(v))


NAMES = [('○ C0e 对照：留出但不校准（= 全局档同值）', 'C0e'),
         ('★ Cg  全局单组 (a,b)          ← **上端点**', 'Cg'),
         ('★★ Ck  按 knob 池化一组 (a,b)   ← **新·缺的中间档**', 'Ck'),
         ('★★ SISOk 按 knob 池化一张保序映射 ← **新**', 'SISOk'),
         ('★★ SISOg 全局一张保序映射      ← **新（上端点对照）**', 'SISOg'),
         ('★ C1u 逐 unit 一组 (a,b)       ← **下端点**', 'C1u'),
         ('★ C2l 逐 unit 逐档 (a,b)', 'C2l'),
         ('★ ISO 逐 unit 逐档保序', 'ISO'),
         ('★ QNT 逐 unit 逐档分位数映射', 'QNT')]

print('\n' + '=' * 116)
print('■ 排序保持性：%d units、%d 次分割、标定集 1/3、seed %d（参照序 = 全 item 跨度序）'
      % (len(units), NSPLIT, SEED))
print('=' * 116)
print('  %-48s %9s %13s %9s %9s' % ('臂', '中位 ρ', '5–95%', 'P(≥0.9)', 'P(≥0.8)'))
for nm, k in NAMES:
    print('  %-48s %s' % (nm, line(R[k])))
print('\n  论文自己的门槛 ≥0.9：Cg %s ｜ **Ck %s** ｜ C1u %s'
      % ('过' if q(R['Cg'], .5) >= .9 else '不过',
         '过' if q(R['Ck'], .5) >= .9 else '**不过**',
         '过' if q(R['C1u'], .5) >= .9 else '不过'))

print('\n' + '=' * 116)
print('■ knob 层面（6 点：knob 内先取中位、再排 6 个 knob 的序）—— Ck 的结构性后果')
print('=' * 116)
print('  %-48s %11s %13s' % ('臂', '36-unit ρ', 'knob6 ρ'))
for nm, k in NAMES:
    print('  %-48s %11.3f %13.3f' % (nm, q(R[k], .5), q(Rknob[k], .5)))

print('\n' + '=' * 116)
print('■ 结构分解（新臂的理论预测）：knob **内**精确保序、只有 knob **之间**被 |a_k| 缩放')
print('=' * 116)
print('  %-8s %-42s %10s %10s' % ('臂', 'knob', 'knob内中位ρ', 'units'))
for k in ('C0e', 'Cg', 'Ck', 'SISOk', 'SISOg', 'C1u'):
    for lab in KL:
        if Rk[k][lab]:
            print('  %-8s %-42s %10.3f %10d' % (k, lab, q(Rk[k][lab], .5), len(grp[lab])))
    print()

print('=' * 116)
print('■ 标定后的**跨度大小**（第二位评审要的那半）：每 unit 在该档下的 span（中位，pp）')
print('=' * 116)
print('  %-48s %9s %9s %9s %11s' % ('臂', 'span中位', 'span最小', 'span最大', '保留率极差'))
summary_mag = {}
for k in ('C0e', 'Cg', 'Ck', 'SISOk', 'SISOg', 'C1u', 'C2l', 'ISO', 'QNT'):
    meds = [q(span_post[u][k], .5) for u in units]
    rets = [q(span_post[u][k], .5) / UNITS[u]['span_full'] for u in units]
    spread = max(rets) / min(rets) if min(rets) > 0 else float('nan')
    summary_mag[k] = dict(span_median_over_units=q(meds, .5), span_min=min(meds), span_max=max(meds),
                          retention_min=min(rets), retention_max=max(rets), retention_spread_x=spread)
    print('  %-48s %9.1f %9.1f %9.1f %10s'
          % (k, q(meds, .5), min(meds), max(meds), ('%.0f×' % spread) if spread == spread else 'nan'))

print('\n' + '=' * 116)
print('■ knob 级缩放因子 |a_k|（Ck 档）：**knob 内所有 unit 共用同一因子 ⇒ knob 内精确保序**')
print('=' * 116)
kfac = {}
for lab in KL:
    a = kA[lab]
    kfac[lab] = dict(a_median=q(a, .5), a_p05=q(a, .05), a_p95=q(a, .95),
                     within_knob_span_ratio_max_range=max(relCK[lab]), n_units=len(grp[lab]))
    print('  %-42s |a| 中位 %6.3f（5–95%% %6.3f–%6.3f）｜knob 内 span 比极差 %.2e ｜ %2d units'
          % (lab, q(a, .5), q(a, .05), q(a, .95), max(relCK[lab]), len(grp[lab])))
_av = [kfac[lab]['a_median'] for lab in KL]
_au = [x for u in units for x in absA[u]]
print('  ⇒ **knob 间** |a_k| 跨 %.3f–%.3f（**%.1f×**）' % (min(_av), max(_av), max(_av) / min(_av)))
print('  ⇒ **unit 间** |a_u| 跨 %.3f–%.3f（**%.1f×**）' % (min(_au), max(_au), max(_au) / min(_au)))
print('  ⇒ 全局单因子（Cg）：一个数；逐 unit 跨度比极差 %.2e（= 冻结件的同一定理）' % max(relCg))

json.dump(dict(
    script='a39_perknob_rung.py',
    unit_set='A39 per-item sources (a39_unit_calib_heldout.py same files and same unit definitions)',
    eligibility='>=3 levels and >=20 common items (A39 rule)',
    protocol=dict(nsplit=NSPLIT, seed=SEED, calib_frac=CAL_FRAC,
                  split='random 1/3 per unit via rng.shuffle, drawn once and reused across levels'),
    knobs={lab: grp[lab] for lab in KL},
    n_units=len(units),
    arms={k: dict(median=q(R[k], .5), p05=q(R[k], .05), p95=q(R[k], .95),
                  frac_ge_090=sum(1 for x in v if x >= .9) / len(v),
                  frac_ge_080=sum(1 for x in v if x >= .8) / len(v)) for k, v in R.items()},
    replication_gate=dict(frozen=os.path.basename(FROZEN36), frozen_md5=md5(FROZEN36),
                          max_abs_delta=max(abs(q(R[k], .5) - fz[k]['median'])
                                            for k in ('C0e', 'C1u', 'C2l', 'Cg', 'ISO', 'QNT'))),
    knob_level_spearman={k: dict(median=q(Rknob[k], .5), p05=q(Rknob[k], .05), p95=q(Rknob[k], .95)) for k in ARMS},
    within_knob_spearman={k: {lab: dict(median=q(Rk[k][lab], .5), n=len(grp[lab]))
                              for lab in KL if Rk[k][lab]} for k in ('C0e', 'Cg', 'Ck', 'SISOk', 'SISOg', 'C1u')},
    knob_scale_factors=kfac,
    magnitudes=summary_mag,
    unit_span_full={u: UNITS[u]['span_full'] for u in units},
    unit_span_post_calibration={u: {k: q(span_post[u][k], .5) for k in ARMS} for u in units},
), io.open(OUT, 'w', encoding='utf-8', newline='\n'), ensure_ascii=False, indent=2)
print('\n已写出 %s' % OUT)
print('\n【输入件 md5】')
for pth in sorted(SRC):
    print('  %-56s %s' % (os.path.basename(pth), md5(pth)))
print('  %-56s %s' % (os.path.basename(FROZEN36), md5(FROZEN36)))
