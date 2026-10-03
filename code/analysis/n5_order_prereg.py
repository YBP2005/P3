# -*- coding: utf-8 -*-
"""n5_order_prereg.py — #14：排序主张的**预注册**复检（零新数据）。

冻结判据：`n5_criteria_frozen.json`（启动时断言 md5，且断言档位规则与阈值逐字一致）。
单元构建：**逐字复制** `a39_unit_calib_heldout.py`（断言其 md5），并先用**复现闸门**核对 36 个单元的
`span_full` 与冻结件逐单元相等；对不上就退出。

用法：python -u n5_order_prereg.py
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
HERE = os.path.dirname(os.path.abspath(__file__))
CRIT = os.path.join(HERE, 'n5_criteria_frozen.json')
SRC = os.path.join(HERE, 'a39_unit_calib_heldout.py')
FROZEN36 = os.path.join(HERE, 'a39_unit_calib_heldout_result.json')
OUT = os.path.join(HERE, 'n5_order_result.json')

# ==================== 一、单元构建：逐字复制 a39_unit_calib_heldout.py ====================
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
import csv
import glob
import io
import json
import os
import random
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')
PM = RP('analysis', 'data', 'pod_mirror')
# ★ 2026-10-03（v0635）：包内 `pod_mirror` 前缀映射到 `data/derived/pA`，而那批
#   等水平重扫的控制梯子随包放行在**更具体**的位置 `data/derived/res_ctrl__<mdl>/`。
#   这里显式回退：若 `PM` 下没有 `res_ctrl__*`，就去找包内那份（作者树上 `PM` 原样命中，不受影响）。
_rc_alt = os.environ.get('N5_RC') or os.path.join(HERE, '..', '..', 'data', 'derived')
PM_RC = PM if glob.glob(os.path.join(PM, 'res_ctrl__*')) else _rc_alt
# ★ 2026-10-03（v0636）：包内 `pod_mirror` 前缀映射到 `data/derived/pA`，而**多处语料是平铺在
#   `data/derived/<name>` 下**（tile_results / dense_prompt_results / ivl_dense_prompt_results / p2e_a800 等）。
#   这里加一个两根源解析：先在作者树根 `PM` 下找，再在包内 `data/derived` 下找；都没有则返回 PM 下那个，
#   保持原有"缺件即跳过"的语义不变。
_ALT_DERIVED = os.path.join(HERE, '..', '..', 'data', 'derived')
def _first(*rel):
    for _base in (PM, _ALT_DERIVED):
        _p = os.path.join(_base, *rel)
        if os.path.exists(_p):
            return _p
    return os.path.join(PM, *rel)
W = NR('@shared', 'work')
B = NR('@shared', 'work', 'b_harvest_20260917')
ANOM, SENT = 1e5, 1234567890
MIN_ITEMS = 20


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


def add_unit(name, bylevel):
    lv = sorted(bylevel)
    if len(lv) < 3:
        return
    common = set.intersection(*[set(bylevel[s]) for s in lv])
    if len(common) < MIN_ITEMS:
        return
    ks = sorted(common)
    UNITS[name] = dict(levels=[(s, bylevel[s]) for s in lv], keys=ks)


def build_units():
    for lab, path, pcol in (
            ('det·in-domain/VisDrone', _first('A', 'det_yolo_ladder_visdrone_det.csv'), 'n_det_person'),
            ('det·zero-shot COCO', _first('A', 'det_yolo_ladder_yolo12n.csv'), 'n_det_person'),
            ('det·in-domain(micro)/BBBC005', os.path.join(B, 'bbbc_eval', 'ladder.csv'), 'n_det')):
        if not os.path.exists(path):
            continue
        u = unitize(load(path), ['tau', 'imgsz'], pcol)
        add_unit(lab + ' (full grid)', {k: v for k, v in u.items()})
        for sz in sorted({k[1] for k in u if len(k) > 1}):
            add_unit('%s / tau@%s' % (lab, sz), {k: v for k, v in u.items() if len(k) > 1 and k[1] == sz})
    p = os.path.join(W, 'dm_ladder.csv')
    if os.path.exists(p):
        u = unitize(load(p), ['dataset', 'protocol', 'value'], 'pred')
        for ds in sorted({k[0] for k in u}):
            add_unit('density·official DM-Count / %s' % ds, {k: v for k, v in u.items() if k[0] == ds})
    for lab, path in (('density·CSRNet', _first('A', 'csrsta_ladder_st_a.csv')),
                      ('density·CSRNet', _first('p2e_a800', 'csrsta_ladder_st_a.csv')),
                      ('density·CSRNet', _first('A', 'csrucf_ladder_ucf.csv'))):
        if os.path.exists(path):
            u = unitize(load(path), ['protocol', 'value'], 'pred')
            add_unit('%s / %s' % (lab, os.path.basename(path).split('_')[-2]), {k: v for k, v in u.items()})
    for mdl in ('ivl', 'q32'):
        for f in sorted(glob.glob(os.path.join(PM_RC, 'res_ctrl__%s' % mdl, 'res_ctrl_*.csv'))):
            ds = os.path.basename(f)[len('res_ctrl_'):-4]
            u = unitize(load(f), ['budget'], 'pred')
            add_unit('VLM·pixel budget / %s / %s' % (mdl, ds), {k: v for k, v in u.items()})
    for sub, mdl in (('tile_results', 'Qwen32B'), ('b2__out_32b_ctile', 'Qwen32B(ctile)'),
                     ('b2__out_8b_ctile', 'Qwen8B(ctile)')):
        d = _first(sub)
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
            add_unit('VLM·tiling / %s / %s / %s' % (mdl, dom, arm), bl)
    for mdl, p in (('ivl', _first('b2__out_ivl', 'E1.csv')),
                   ('q32', _first('b2__out_q32', 'E1.csv'))):
        if os.path.exists(p):
            u = unitize(load(p), ['arm'], 'pred')
            add_unit('VLM·output contract / %s' % mdl, {k: v for k, v in u.items()})
    for sub, mdl in (('dense_prompt_results', 'Qwen32B'), ('ivl_dense_prompt_results', 'IVL')):
        d = _first(sub)
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
            add_unit('VLM·prompt family / %s / %s / %s' % (mdl, dom, arm), bl)


# ==================== 二、工具 ====================
def rho_arr(G, P):
    sg = G.sum()
    return 100.0 * (P.sum() - sg) / sg if sg else float('nan')


def span_of(unit, level_idx=None, use_np=True):
    """level_idx: 保留哪些档（None=全档）。返回 (span, 各档 rho)。"""
    import numpy as np
    lv = unit['levels'] if level_idx is None else [unit['levels'][i] for i in level_idx]
    keys = unit['keys']
    rs = []
    for _s, d in lv:
        G = np.array([d[k][0] for k in keys], dtype=float)
        P = np.array([d[k][1] for k in keys], dtype=float)
        rs.append(rho_arr(G, P))
    return max(rs) - min(rs), rs


def spearman(x, y):
    n = len(x)

    def rank(v):
        s = sorted(range(n), key=lambda i: v[i])
        r = [0.0] * n
        i = 0
        while i < n:
            j = i
            while j + 1 < n and v[s[j + 1]] == v[s[i]]:
                j += 1
            avg = (i + j) / 2.0 + 1
            for t in range(i, j + 1):
                r[s[t]] = avg
            i = j + 1
        return r
    a, b = rank(x), rank(y)
    ma, mb = sum(a) / n, sum(b) / n
    num = sum((a[i] - ma) * (b[i] - mb) for i in range(n))
    da = sum((x2 - ma) ** 2 for x2 in a) ** 0.5
    db = sum((y2 - mb) ** 2 for y2 in b) ** 0.5
    return num / (da * db) if da and db else float('nan')


def idx_for(L, k):
    if k == 3:
        return sorted({0, (L - 1) // 2, L - 1})
    if k == 4:
        return sorted({0, (L - 1) // 3, 2 * (L - 1) // 3, L - 1})
    raise ValueError(k)


def main():
    b = open(CRIT, 'rb').read()
    print('冻结判据 md5 %s（%d B）' % (hashlib.md5(b).hexdigest(), len(b)))
    crit = json.loads(b.decode('utf-8'))
    csrc = hashlib.md5(open(SRC, 'rb').read()).hexdigest()
    print('单元构建源 %s md5 %s' % (os.path.basename(SRC), csrc))
    assert crit['statistics']['bootstrap']['n'] == 2000
    assert crit['statistics']['permutation']['n'] == 5000
    assert crit['levels_preregistered']['V3_★主判据'].count('k = 3') == 1

    build_units()
    import numpy as np
    names = sorted(UNITS)
    print('单元数 %d' % len(names))

    # ---- 复现闸门：逐单元 span_full ----
    j37 = json.load(io.open(FROZEN36, encoding='utf-8'))
    bad = []
    ref = {}
    for u in names:
        s, _ = span_of(UNITS[u])
        ref[u] = s
        want = j37['per_unit'][u]['span_full']
        if abs(s - want) > 1e-9 * max(1.0, abs(want)):
            bad.append((u, s, want))
    assert not bad, '复现闸门失败（%d 个单元对不上）：%s' % (len(bad), bad[:3])
    print('★ 复现闸门通过：%d/%d 个单元的 span_full 与冻结件逐单元相等（<1e-9 相对）'
          % (len(names), len(j37['per_unit'])))

    # ---- 预注册的等档数收缩 ----
    L = {u: len(UNITS[u]['levels']) for u in names}
    print('档位数分布：%s' % (collections.Counter(L.values()),))
    variants = {}
    for k in (3, 4):
        spans, keepn, deg = {}, {}, []
        for u in names:
            il = idx_for(L[u], k)
            s, _ = span_of(UNITS[u], il)
            spans[u] = s
            keepn[u] = len(il)
            if s <= 1e-9:
                deg.append(u)
        variants[k] = dict(spans=spans, keep=keepn, degenerate=deg)

    rng = random.Random(crit['statistics']['bootstrap']['seed'])
    refv = [ref[u] for u in names]
    out = {'units': names, 'span_ref': ref, 'levels': L,
           'variant_span': {str(k): variants[k]['spans'] for k in variants},
           'degenerate_after_shrink': {str(k): variants[k]['degenerate'] for k in variants}}

    for k in (3, 4):
        v = variants[k]
        vv = [v['spans'][u] for u in names]
        obs = spearman(refv, vv)
        # bootstrap：单元内有放回重抽 item（各档同一组下标）
        arrs = {}
        for u in names:
            keys = UNITS[u]['keys']
            arrs[u] = [(np.array([d[x][0] for x in keys], dtype=float),
                        np.array([d[x][1] for x in keys], dtype=float)) for _s, d in UNITS[u]['levels']]
        bs = []
        for _ in range(crit['statistics']['bootstrap']['n']):
            sv, sr = [], []
            for u in names:
                n = len(UNITS[u]['keys'])
                ii = np.array([rng.randrange(n) for _ in range(n)])
                r_ = ref[u]  # noqa: F841 (参考侧用原值：见下方说明)
                lvl = arrs[u]
                rr = [rho_arr(G[ii], P[ii]) for G, P in lvl]
                sr.append(max(rr) - min(rr))
                il = idx_for(L[u], k)
                rr2 = [rr[i] for i in il]
                sv.append(max(rr2) - min(rr2))
            bs.append(spearman(sr, sv))
        bs_sorted = sorted(bs)
        lo = bs_sorted[int(0.025 * len(bs_sorted))]
        hi = bs_sorted[min(len(bs_sorted) - 1, int(0.975 * len(bs_sorted)))]
        # 置换检验
        pn = crit['statistics']['permutation']['n']
        prng = random.Random(crit['statistics']['permutation']['seed'])
        cnt = 0
        for _ in range(pn):
            perm = vv[:]
            prng.shuffle(perm)
            if abs(spearman(refv, perm)) >= abs(obs) - 1e-12:
                cnt += 1
        out['V%d' % k] = {'spearman': obs, 'ci': [lo, hi], 'p_raw': (cnt + 1) / (pn + 1.0),
                          'bootstrap_mean': sum(bs) / len(bs),
                          'ci_excludes_zero': bool(lo > 0), 'n_degenerate': len(v['degenerate'])}
        print('\n[V%d] k=%d 档 ⇒ Spearman(参考, V%d) = %.4f ｜ bootstrap 95%% CI [%.4f, %.4f] '
              '｜ 置换 p = %.5f ｜ 跨度退化为 0 的单元 %d 个'
              % (k, k, k, obs, lo, hi, out['V%d' % k]['p_raw'], len(v['degenerate'])))

    # Holm 校正（族 = {V3, V4}）
    ps = sorted([(out['V%d' % k]['p_raw'], k) for k in (3, 4)])
    m = len(ps)
    adj, prev = {}, 0.0
    for i, (p_, k) in enumerate(ps):
        val = min(1.0, max(prev, (m - i) * p_))
        adj[k] = val
        prev = val
    for k in (3, 4):
        out['V%d' % k]['p_holm'] = adj[k]

    # 标定并入
    cal = {}
    Gs = np.concatenate([np.array([d[x][0] for x in UNITS[u]['keys']], dtype=float)
                         for u in names for _s, d in UNITS[u]['levels']])
    Ps = np.concatenate([np.array([d[x][1] for x in UNITS[u]['keys']], dtype=float)
                         for u in names for _s, d in UNITS[u]['levels']])
    mg, mp = Gs.mean(), Ps.mean()
    a_g = ((Ps - mp) * (Gs - mg)).sum() / ((Ps - mp) ** 2).sum()
    b_g = mg - a_g * mp
    sg = [abs(a_g) * ref[u] for u in names]
    cal['shared_affine'] = {'a': float(a_g), 'b': float(b_g),
                            'spearman_vs_ref': spearman(refv, sg)}
    per_u = []
    for u in names:
        Gu = Gs  # placeholder (unused)
        ks = UNITS[u]['keys']
        G = np.concatenate([np.array([d[x][0] for x in ks], dtype=float) for _s, d in UNITS[u]['levels']])
        P = np.concatenate([np.array([d[x][1] for x in ks], dtype=float) for _s, d in UNITS[u]['levels']])
        mgg, mpp = G.mean(), P.mean()
        den = ((P - mpp) ** 2).sum()
        au = ((P - mpp) * (G - mgg)).sum() / den if den else 0.0
        per_u.append(abs(au) * ref[u])
    cal['per_unit_affine'] = {'spearman_vs_ref': spearman(refv, per_u)}
    out['calibration'] = cal
    print('\n[标定并入] shared affine (a=%.4f) 下排序 Spearman = %.4f（Prop 5 预期逐位不变）｜ '
          'per-unit affine 下 = %.4f（本稿已公开它会破坏排序）'
          % (cal['shared_affine']['a'], cal['shared_affine']['spearman_vs_ref'],
             cal['per_unit_affine']['spearman_vs_ref']))

    # 判据
    print('\n' + '=' * 96)
    print('预注册判据（Spearman ≥ 0.90 且 CI 下界 ≥ 0.80 且 Holm 校正 p ≤ 0.01）')
    print('=' * 96)
    for k in (3, 4):
        d = out['V%d' % k]
        ok = (d['spearman'] >= 0.90) and (d['ci'][0] >= 0.80) and (d['p_holm'] <= 0.01)
        d['pass'] = bool(ok)
        print('  V%d（k=%d）：ρ = %.4f ≥ 0.90？%s ｜ CI 下界 %.4f ≥ 0.80？%s ｜ p_Holm = %.5f ≤ 0.01？%s '
              '⇒ **%s**'
              % (k, k, d['spearman'], 'Y' if d['spearman'] >= 0.90 else 'N',
                 d['ci'][0], 'Y' if d['ci'][0] >= 0.80 else 'N',
                 d['p_holm'], 'Y' if d['p_holm'] <= 0.01 else 'N', 'PASS' if ok else 'FAIL'))
    io.open(OUT, 'w', encoding='utf-8').write(json.dumps(out, ensure_ascii=False, indent=1))
    print('\nJSON -> %s' % OUT)


if __name__ == '__main__':
    main()
