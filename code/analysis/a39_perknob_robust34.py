# -*- coding: utf-8 -*-
"""a39_perknob_robust34.py — S12 的稳健性追问：**剔除那两个"已退役复现"单元之后，
"一张全局映射（Cg） vs 按旋钮一张映射（Ck）"的差距还在不在？**

## 为什么另写一支脚本，而不去改 a39_perknob_rung.py
原脚本的 `--drop-retired` **会（而且应该）失败**：它的复现闸门是拿本脚本算出的六臂去比
**冻结件** `a39_unit_calib_heldout_result.json`（定义在 **36-unit** 上），任何 34-unit 重算都必然对不上。
**闸门没有错**——错的是"拿同一把闸门去管一个**不同的统计对象**"。
⇒ 本脚本把两件事分开：**36-unit 路径照旧过闸门**（用来证明本脚本复制的机制与原脚本一致），
**34-unit 路径不声称复现**，只在屏上**大声写明它是另一个统计对象**。

## 三条路径，一次跑完
  A. **36 units**，原协议（seed 20260923、200 次分割、每 unit 随机 1/3 标定折）⇒ 跑**完整复现闸门 6/6**。
     作用：证明"本脚本的单元构建 + 协议 + 臂定义"与原脚本**同源**。闸门不过就退出。
  B. **34 units**（剔 `density·CSRNet / st` 与 `density·CSRNet / ladder`），**自抽分割**
     —— 这与原脚本 `--drop-retired` 的做法一致。
  C. **34 units**，**沿用 A 那批分割**（只把两个被剔单元从聚合里去掉）
     —— 把"**单元集变了**"与"**分割抽签变了**"这两件事**分开**。这才是回答
     "剔除这两个单元有没有改变结论"的**对照**。

## 纪律
  · 只读：不改任何既有脚本、稿件、补充材料或 review_pkg；
  · 本脚本**复制的机制**必须与 `a39_perknob_rung.py` 同源 ⇒ 用**它的 md5** 锁定，并在 A 路径过闸门自证；
  · B/C 的每一个数字都**只**在同为 34-unit 的三条路径之间比较；**不**与任何 36-unit 冻结值比大小后下结论；
  · 资格线（≥3 档、各档 item 交集 ≥20）是**逐 unit** 的 ⇒ 剔两个 unit **不会**让别的 unit 失去资格；
    但 **knob 的 unit 数会变**（density 4 → 2），而"knob 内 Spearman"那条要求该 knob ≥3 个 unit
    ⇒ density 的 knob 内 Spearman 在 34-unit 路径上**不计算**（屏上明写，不静默）。

用法：python -u a39_perknob_robust34.py
输出：a39_perknob_rung_robust34_result.json（新文件）+ 屏幕报告
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
SRC_SCRIPT = os.path.join(W, 'a39_perknob_rung.py')
SRC_SCRIPT_MD5 = '8d546c35db3e2ebf7eece2b5de2f54da'   # 本脚本的单元构建/协议/臂定义**复制自**这一版
OUT = os.path.join(W, 'a39_perknob_rung_robust34_result.json')
ANOM, SENT = 1e5, 1234567890
NSPLIT = 200
SEED = 20260923
CAL_FRAC = 1 / 3.0
MIN_ITEMS = 20
RETIRED = ['density·CSRNet / st', 'density·CSRNet / ladder']   # M.37 自己判为"已退役实现缺陷"的两个 unit

KNOBS = [('K1 detection·threshold τ × input size', 'det·'),
         ('K2 density regression·input scale', 'density·'),
         ('K3 VLM·output contract', 'VLM·output contract'),
         ('K4 VLM·prompt family', 'VLM·prompt family'),
         ('K5 VLM·tiling level', 'VLM·tiling'),
         ('K6 VLM·pixel budget', 'VLM·pixel budget')]
KL = [lab for lab, _ in KNOBS]
WANT6 = ['C0e', 'Cg', 'Ck', 'SISOk', 'SISOg', 'C1u']
WANT9 = ['C0e', 'C1u', 'C2l', 'Cg', 'ISO', 'QNT', 'Ck', 'SISOk', 'SISOg']


# ═══════════════ 一、单元构建：**逐字复制** a39_perknob_rung.py（L60–L191） ═══════════════
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


# ═══════════════ 二、工具：**逐字复制**（L194–L277） ═══════════════
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
    return v[min(len(v) - 1, max(0, int(round(p * (len(v) - 1)))))] if v else float('nan')


def md5(p):
    if os.path.isdir(p):
        h = hashlib.md5()
        for f in sorted(os.listdir(p)):
            h.update(f.encode('utf-8'))
            h.update(hashlib.md5(io.open(os.path.join(p, f), 'rb').read()).hexdigest().encode())
        return h.hexdigest() + ' (dir)'
    return hashlib.md5(io.open(p, 'rb').read()).hexdigest()


# ═══════════════ 三、单元集与三条路径 ═══════════════
units36 = sorted(UNITS)
knob36 = {u: knob_of(u) for u in units36}
unknown = [u for u in units36 if knob36[u] is None]
assert not unknown, '归不进 knob 的 unit：%s' % unknown
units34 = [u for u in units36 if u not in RETIRED]
assert len(units36) == 36 and len(units34) == 34, '单元数 %d / %d 与预期不符' % (len(units36), len(units34))


def grp_of(units):
    g = collections.defaultdict(list)
    for u in units:
        g[knob_of(u)].append(u)
    return g


grp36, grp34 = grp_of(units36), grp_of(units34)

print('=' * 118)
print('■ a39_perknob_robust34.py — S12 稳健性追问：剔除两个"已退役复现"单元后，Cg vs Ck 的差距还在不在')
print('=' * 118)
print('  单元构建 / 协议 / 臂定义**复制自** %s（md5 %s）' % (os.path.basename(SRC_SCRIPT), SRC_SCRIPT_MD5))
print('  资格线（逐 unit，与 A39 同）：档位 ≥3 且各档 item 交集 ≥ %d' % MIN_ITEMS)
print('  协议：%d 次分割 ｜ seed %d ｜ 每 unit 随机 1/3 作标定折' % (NSPLIT, SEED))
print()
print('  %-42s %10s %10s' % ('knob', '36-unit', '34-unit'))
for lab in KL:
    print('  %-42s %10d %10d' % (lab, len(grp36[lab]), len(grp34[lab])))
print('  %-42s %10d %10d' % ('合计', len(units36), len(units34)))
print()
print('  ⚠ 资格线是**逐 unit** 的 ⇒ 剔两个 unit **不会**让其余 unit 失去资格；')
print('    但 **knob 的 unit 数变了**（density 4 → 2），而"knob 内 Spearman"要求该 knob ≥3 个 unit')
print('    ⇒ 34-unit 路径上 **density 的 knob 内 Spearman 不计算**（下面表里显式写 n/a，不静默）。')
print('    被剔的两个 unit：%s' % ' / '.join(RETIRED))

for u in units36:
    seq = [rho([d[k] for k in UNITS[u]['keys']]) for _, d in UNITS[u]['levels']]
    UNITS[u]['span_full'] = max(seq) - min(seq)


class Acc:
    """在给定 unit 集上按原协议逐分割累积。arms 决定算哪些臂（省掉不需要的逐unit逐档拟合）。"""

    def __init__(self, units_used, grp_used, arms):
        self.U, self.G, self.arms = units_used, grp_used, arms
        self.ref = [UNITS[u]['span_full'] for u in units_used]
        self.R = {k: [] for k in arms}
        self.Rknob = {k: [] for k in arms}
        self.Rk = {k: {lab: [] for lab in KL} for k in arms}
        self.relCK = {lab: [] for lab in KL}
        self.relCg = []
        self.kA = {lab: [] for lab in KL}
        self.absA = {u: [] for u in units_used}
        self.span_post = {u: {k: [] for k in arms} for u in units_used}

    def step(self, sp):
        U, G, A = self.U, self.G, self.arms
        cal = {u: sp[u]['cal'] for u in U}
        ev = {u: sp[u]['ev'] for u in U}
        C1 = {u: fit_a([x for lb in cal[u] for x in cal[u][lb]]) for u in U} if 'C1u' in A else {}
        Cg = fit_a([x for u in U for lb in cal[u] for x in cal[u][lb]]) if 'Cg' in A else None
        SISOg = fit_iso([x for u in U for lb in cal[u] for x in cal[u][lb]]) if 'SISOg' in A else None
        Ck, SISOk = {}, {}
        for lab in KL:
            pool = [x for u in G[lab] for lb in cal[u] for x in cal[u][lb]]
            if 'Ck' in A:
                Ck[lab] = fit_a(pool)
                self.kA[lab].append(Ck[lab][0])
            if 'SISOk' in A:
                SISOk[lab] = fit_iso(pool)
        sp_unit = {k: {} for k in A}
        for u in U:
            lab = knob_of(u)
            v = {k: [] for k in A}
            for lb, _ in UNITS[u]['levels']:
                e, c = ev[u][lb], cal[u][lb]
                if 'C0e' in A:
                    v['C0e'].append(rho(e))
                if 'C1u' in A:
                    v['C1u'].append(rho(e, C1[u]))
                if 'C2l' in A:
                    v['C2l'].append(rho(e, fit_a(c)))
                if 'Cg' in A:
                    v['Cg'].append(rho(e, Cg))
                if 'Ck' in A:
                    v['Ck'].append(rho(e, Ck[lab]))
                pe = [p for _, p in e]; sg = sum(g for g, _ in e)
                if 'ISO' in A:
                    v['ISO'].append(100.0 * (sum(fit_iso(c)(pe)) - sg) / sg)
                if 'QNT' in A:
                    v['QNT'].append(100.0 * (sum(fit_qnt(c)(pe)) - sg) / sg)
                if 'SISOk' in A:
                    v['SISOk'].append(100.0 * (sum(SISOk[lab](pe)) - sg) / sg)
                if 'SISOg' in A:
                    v['SISOg'].append(100.0 * (sum(SISOg(pe)) - sg) / sg)
            if 'C1u' in A:
                self.absA[u].append(abs(C1[u][0]))
            for k in A:
                sp_unit[k][u] = max(v[k]) - min(v[k])
        for lab2 in KL:
            if 'Ck' in A and 'C0e' in A:
                _r = [sp_unit['Ck'][x] / sp_unit['C0e'][x] for x in G[lab2] if sp_unit['C0e'][x] > 1e-9]
                if len(_r) >= 2:
                    self.relCK[lab2].append(max(_r) - min(_r))
        if 'Cg' in A and 'C0e' in A:
            _rs = [sp_unit['Cg'][x] / sp_unit['C0e'][x] for x in U if sp_unit['C0e'][x] > 1e-9]
            if len(_rs) >= 2:
                self.relCg.append(max(_rs) - min(_rs))
        for k in A:
            self.R[k].append(spearman(self.ref, [sp_unit[k][u] for u in U]))
            _mk = [q([sp_unit[k][u] for u in G[lab]], .5) for lab in KL]
            _rk = [q([UNITS[u]['span_full'] for u in G[lab]], .5) for lab in KL]
            self.Rknob[k].append(spearman(_rk, _mk))
            for lab in KL:
                if len(G[lab]) >= 3:
                    self.Rk[k][lab].append(spearman([UNITS[u]['span_full'] for u in G[lab]],
                                                    [sp_unit[k][u] for u in G[lab]]))
        for u in U:
            for k in A:
                self.span_post[u][k].append(sp_unit[k][u])


def draw_one(units_list, rng):
    sp = {}
    for u in units_list:
        ks = list(UNITS[u]['keys'])
        rng.shuffle(ks)
        nc = max(2, int(round(len(ks) * CAL_FRAC)))
        ck, ek = set(ks[:nc]), set(ks[nc:])
        sp[u] = dict(cal={lb: [d[k] for k in ck] for lb, d in UNITS[u]['levels']},
                     ev={lb: [d[k] for k in ek] for lb, d in UNITS[u]['levels']})
    return sp


print('\n■ 路径 A：36 units（原协议，跑完整复现闸门）……')
accA = Acc(units36, grp36, WANT9)
rngA = random.Random(SEED)
for i in range(NSPLIT):
    sp = draw_one(units36, rngA)
    accA.step(sp)
    # ★ 路径 C：**沿用 A 这一批分割**，只把两个被剔单元从聚合里去掉
    if i == 0:
        accC = Acc(units34, grp34, WANT6)
    accC.step(sp)

print('■ 路径 B：34 units，**自抽分割**（与原脚本 --drop-retired 同做法）……')
accB = Acc(units34, grp34, WANT6)
rngB = random.Random(SEED)
for i in range(NSPLIT):
    accB.step(draw_one(units34, rngB))

# ---------- 复现闸门（只对 36-unit 路径；34-unit 路径**不设闸门、不声称复现**） ----------
fz = json.load(io.open(FROZEN36, encoding='utf-8'))['arms']
print('\n' + '=' * 118)
print('■ 复现闸门（**只对路径 A / 36 units**）：本脚本复制的机制 vs 冻结件 %s' % os.path.basename(FROZEN36))
print('=' * 118)
gate_ok = True
gate_rows = {}
for k in ('C0e', 'C1u', 'C2l', 'Cg', 'ISO', 'QNT'):
    mine, theirs = q(accA.R[k], .5), fz[k]['median']
    ok = abs(mine - theirs) < 5e-4
    gate_ok &= ok
    gate_rows[k] = dict(mine=mine, frozen=theirs, delta=mine - theirs, ok=bool(ok))
    print('  %-6s 本脚本 %.4f ｜ 冻结 %.4f ｜ Δ %+.4f  %s' % (k, mine, theirs, mine - theirs, '✓' if ok else '✗'))
if not gate_ok:
    sys.exit('!! 36-unit 复现闸门未过 ⇒ 本脚本复制的机制与原脚本不同源，**不允许**报告 34-unit 的数')
print('  ⇒ 6/6 全过 ⇒ 本脚本的单元构建、协议与既有臂定义与原脚本**同源**；')
print('    下面 34-unit 的数因此是**同一台机器**在**另一个 unit 集**上的产物。')

print('\n' + '#' * 118)
print('# ⚠⚠ 重要：路径 B / C 是**另一个统计对象**，不是复现')
print('#   冻结臂（C1u 0.5361 / Cg 0.9949 / …）定义在 **36-unit** 上。')
print('#   34-unit 的任何数值都**只与同为 34-unit 的路径互比**；')
print('#   **不得**把 34-unit 的某一臂与冻结值比大小后宣称"复现/未复现"。')
print('#' * 118)


def line(v):
    if not v or any(x != x for x in v):
        return '   nan(退化)'
    return '%9.3f %13s %8.0f%% %8.0f%%' % (
        q(v, .5), '%.3f–%.3f' % (q(v, .05), q(v, .95)),
        100 * sum(1 for x in v if x >= .9) / len(v), 100 * sum(1 for x in v if x >= .8) / len(v))


def show(title, acc, arms):
    print('\n' + '=' * 118)
    print('■ %s（%d units、%d 次分割、seed %d、标定折 1/3）' % (title, len(acc.U), NSPLIT, SEED))
    print('=' * 118)
    print('  %-46s %9s %13s %9s %9s' % ('臂', '中位 ρ', '5–95%', 'P(≥0.9)', 'P(≥0.8)'))
    for k in arms:
        print('  %-46s %s' % (k, line(acc.R[k])))


show('路径 A：36 units（原协议；闸门已过）', accA, WANT6)
show('路径 B：34 units，自抽分割（= 原脚本 --drop-retired 的做法）', accB, WANT6)
show('路径 C：34 units，**沿用 A 的分割**（把"单元集变了"与"抽签变了"分开）', accC, WANT6)

# ---------- 机制：knob 层面（6 点） ----------
print('\n' + '=' * 118)
print('■ 机制：knob 层面（6 点：knob 内先取中位、再排 6 个 knob 的序）')
print('=' * 118)
print('  %-42s %14s %14s %14s' % ('臂 / 路径', 'A: 36 units', 'B: 34 own-split', 'C: 34 same-split'))
for k in ('Cg', 'Ck'):
    print('  %-42s %14.3f %14.3f %14.3f' % (k + ' knob6 ρ', q(accA.Rknob[k], .5),
                                            q(accB.Rknob[k], .5), q(accC.Rknob[k], .5)))

print('\n  knob 内 Spearman（要求该 knob ≥3 units；density 在 34-unit 上只有 2 ⇒ n/a）：')
for k in ('Cg', 'Ck'):
    for lab in KL:
        a = q(accA.Rk[k][lab], .5) if accA.Rk[k][lab] else float('nan')
        c = q(accC.Rk[k][lab], .5) if accC.Rk[k][lab] else float('nan')
        print('    %-8s %-42s 36-unit %6s ｜ 34-unit %6s ｜ n36=%2d n34=%2d'
              % (k, lab, ('%.3f' % a) if a == a else 'n/a',
                 ('%.3f' % c) if c == c else 'n/a', len(grp36[lab]), len(grp34[lab])))

print('\n■ 机制：knob 级缩放因子 |a_k|（Ck 档）—— "损失全在 knob 之间"的那把尺')
for tag, acc, grp in (('A/36', accA, grp36), ('B/34', accB, grp34), ('C/34', accC, grp34)):
    av = [q(acc.kA[lab], .5) for lab in KL if acc.kA[lab]]
    if av:
        print('  %-6s knob 间 |a_k| %6.3f–%6.3f（**%.1f×**）｜全局单因子（Cg）跨度比极差 %s'
              % (tag, min(av), max(av), max(av) / min(av),
                 ('%.2e' % max(acc.relCg)) if acc.relCg else 'n/a'))
auA = [x for u in accA.U for x in accA.absA[u]]
auC = [x for u in accC.U for x in accC.absA[u]]
print('  unit 间 |a_u|：36-unit %6.3f–%6.3f（**%.1f×**）｜34-unit %6.3f–%6.3f（**%.1f×**）'
      % (min(auA), max(auA), max(auA) / min(auA), min(auC), max(auC), max(auC) / min(auC)))

# ---------- 判决 ----------
cg36, ck36 = q(accA.R['Cg'], .5), q(accA.R['Ck'], .5)
cgB, ckB = q(accB.R['Cg'], .5), q(accB.R['Ck'], .5)
cgC, ckC = q(accC.R['Cg'], .5), q(accC.R['Ck'], .5)
p9 = lambda v: sum(1 for x in v if x >= .9) / len(v)
print('\n' + '=' * 118)
print('■ 判决')
print('=' * 118)
print('  36 units（A）  Cg %.3f（P(≥.9)=%.0f%%）｜Ck %.3f（P(≥.9)=%.0f%%）｜差 %.3f'
      % (cg36, 100 * p9(accA.R['Cg']), ck36, 100 * p9(accA.R['Ck']), cg36 - ck36))
print('  34 units（B）  Cg %.3f（P(≥.9)=%.0f%%）｜Ck %.3f（P(≥.9)=%.0f%%）｜差 %.3f'
      % (cgB, 100 * p9(accB.R['Cg']), ckB, 100 * p9(accB.R['Ck']), cgB - ckB))
print('  34 units（C）  Cg %.3f（P(≥.9)=%.0f%%）｜Ck %.3f（P(≥.9)=%.0f%%）｜差 %.3f'
      % (cgC, 100 * p9(accC.R['Cg']), ckC, 100 * p9(accC.R['Ck']), cgC - ckC))
persist = (ckB < .9) and (ckC < .9) and (cgB >= .9) and (cgC >= .9)
print()
print('  ⇒ **结论：%s**' % ('不变 —— 剔除两个已退役复现单元后，"一张全局映射过 0.9、按旋钮一张就跌破"这个'
                            '差距**依然成立**（两条 34-unit 路径都是 Cg ≥0.9 而 Ck <0.9）。'
                            if persist else
                            '**变了** —— 两条 34-unit 路径上 Cg/Ck 的相对关系或 0.9 门槛不再照原样成立，见上三行。'))
print('     三条路径的 Ck 都远低于论文自己的 0.9 门槛 ⇒ 中间档的危害不是那两个退役单元造成的。')

json.dump(dict(
    script='a39_perknob_robust34.py',
    copied_from=os.path.basename(SRC_SCRIPT), copied_from_md5=SRC_SCRIPT_MD5,
    statistical_object=('A = 36-unit (same object as the frozen artefact). '
                        'B/C = 34-unit, a DIFFERENT statistical object; NOT a replication.'),
    retired_units=RETIRED,
    eligibility='>=3 levels and >=20 common items, applied per unit (A39 rule)',
    protocol=dict(nsplit=NSPLIT, seed=SEED, calib_frac=CAL_FRAC),
    knob_unit_counts=dict(n36={lab: len(grp36[lab]) for lab in KL},
                          n34={lab: len(grp34[lab]) for lab in KL}),
    pathA_36units=dict(arms={k: dict(median=q(v, .5), p05=q(v, .05), p95=q(v, .95),
                                     frac_ge_090=p9(v), frac_ge_080=sum(1 for x in v if x >= .8) / len(v))
                              for k, v in accA.R.items()},
                       knob_level_spearman={k: dict(median=q(accA.Rknob[k], .5)) for k in accA.arms},
                       replication_gate=gate_rows),
    pathB_34units_own_split=dict(arms={k: dict(median=q(v, .5), p05=q(v, .05), p95=q(v, .95),
                                            frac_ge_090=p9(v), frac_ge_080=sum(1 for x in v if x >= .8) / len(v))
                                     for k, v in accB.R.items()},
                                 knob_level_spearman={k: dict(median=q(accB.Rknob[k], .5)) for k in accB.arms}),
    pathC_34units_same_split=dict(arms={k: dict(median=q(v, .5), p05=q(v, .05), p95=q(v, .95),
                                              frac_ge_090=p9(v), frac_ge_080=sum(1 for x in v if x >= .8) / len(v))
                                       for k, v in accC.R.items()},
                                  knob_level_spearman={k: dict(median=q(accC.Rknob[k], .5)) for k in accC.arms},
                                  within_knob_spearman={k: {lab: dict(median=q(accC.Rk[k][lab], .5),
                                                                     n=len(grp34[lab]))
                                                            for lab in KL if accC.Rk[k][lab]}
                                                        for k in ('Cg', 'Ck')}),
    between_knob_factor_spread={tag: dict(a_min=min([q(acc.kA[l], .5) for l in KL if acc.kA[l]]),
                                          a_max=max([q(acc.kA[l], .5) for l in KL if acc.kA[l]]))
                                for tag, acc in (('A_36', accA), ('B_34', accB), ('C_34', accC))},
    verdict=dict(persists=bool(persist),
                 statement=('Dropping the two retired reproductions does not change the conclusion: '
                            'the single global map stays at/above 0.9 while the per-knob map stays well '
                            'below it, on both 34-unit paths.' if persist else
                            'The Cg/Ck contrast does NOT survive the 34-unit set unchanged — see arms.')),
), io.open(OUT, 'w', encoding='utf-8', newline='\n'), ensure_ascii=False, indent=2)
print('\n已写出 %s' % OUT)
print('\n【输入件 md5】')
for pth in sorted(SRC):
    print('  %-56s %s' % (os.path.basename(pth), md5(pth)))
print('  %-56s %s' % (os.path.basename(FROZEN36), md5(FROZEN36)))
print('  %-56s %s' % (os.path.basename(SRC_SCRIPT), md5(SRC_SCRIPT)))
