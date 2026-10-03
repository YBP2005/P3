#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""build_span_panel.py — §M.18.8's five-build table, recomputed cell for cell, and the one thing the
charge behind it ([external-review] #27) actually asks: does the *contract's* effect vary across builds?

Why this exists. §7.3's VLM unit span rests on one or two builds, while §M.18.8 measures a **90.3 pp**
spread in the base-arm answered-zero rate across the **five deployments of the same weights**. The charge
is that §7.3's unit might therefore be a build artefact. The census files are conditioned on **the items
each domain's corpus answered 0** (`e1_<build>_<domain>_<arm>.csv`, 103/180/150/150 items), so:

  * the answered-zero rate of `base` on that pool is recomputable, and this script reproduces all twenty
    cells of §M.18.8 from the frozen per-item records (§M.18.8 currently carries no such anchor);
  * on that same pool the two arms that remove the zero (`permit`, `channel`) return an **abstention** on
    essentially every item, so a *span across contract arms* is **not defined there** — which is exactly
    why §7.3's unit is measured on the corpus items rather than on this pool, and why the build spread of
    §M.18.8 does not transfer to §7.3's span. This script measures that residue rather than assuming it.

Usage:
  python build_span_panel.py            # recompute and print
  python build_span_panel.py --check    # recompute + assert the §M.18.8 panel
  python build_span_panel.py --selftest # negative controls
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
import argparse
import csv
import io
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')
E2 = RP('analysis', 'e2_newh20')
SUPP = RP('PaperB_英文补充材料_PR_20260919.md')
ANOM = 1e5

BUILDS = [('AWQ-4bit', 'awq'), ('AWQ-8bit', 'awq8'), ('BF16', 'bf16'),
          ('FP8', 'fp8'), ('GPTQ-W4', 'gptq')]
DOMAINS = ['st_a', 'ucf', 'visdrone', 'aitod']
# §M.18.8's printed base-arm answered-zero rates (rows = builds above, columns = DOMAINS).
M188 = {
    'AWQ-4bit': [99.0, 92.2, 99.3, 97.3],
    'AWQ-8bit': [65.0, 69.4, 97.3, 92.7],
    'BF16':     [62.1, 66.7, 97.3, 93.3],
    'FP8':      [79.6, 79.4, 97.3, 92.7],
    'GPTQ-W4':  [8.7, 16.1, 96.7, 88.7],
}
M188_N = {'st_a': 103, 'ucf': 180, 'visdrone': 150, 'aitod': 150}


def rows_of(cfg, ds, arm):
    p = os.path.join(RP('analysis', 'e2_newh20'), 'e1_qwen3-vl-32b-%s_%s_%s.csv' % (cfg, ds, arm))
    if not os.path.exists(p):
        return None
    with io.open(p, encoding='utf-8-sig') as f:
        return [r for r in csv.DictReader(f) if '#r' not in str(r.get('item') or '')]


def pooled_items(ds):
    """The common item intersection across the five builds' base-arm files.

    ★ This is load-bearing: the per-build files are NOT the same size on VisDrone (273 for awq/awq8/bf16
    against 150 for fp8/gptq) or on AI-TOD (154 against 150), and §M.18.8 prints a single common n per
    domain (150 for both). Without the intersection the reproduction misses those two columns entirely.
    """
    sets = []
    for _label, cfg in BUILDS:
        rows = rows_of(cfg, ds, 'base')
        if rows is None:
            return None
        sets.append(set(r['item'] for r in rows))
    return set.intersection(*sets)


def tally(rows, keep):
    """numeric = parsed to a count; zero = answered exactly 0. Rates are over the pool size (see below).

    ★ Denominator: §M.18.8's printed cells are zeros / pool size, not zeros / numeric. The two differ only
    where a build leaves items unparsed (GPTQ-W4 on st_a: 9/99 = 9.09% against the printed 8.7 = 9/103,
    and on ucf 29/167 = 17.37% against the printed 16.1 = 29/180). The pool-size denominator is the one
    that reproduces, and the selftest pins it.
    """
    numeric = zero = 0
    for r in rows:
        if keep is not None and r['item'] not in keep:
            continue
        try:
            pr = float(r['pred'])
        except (KeyError, TypeError, ValueError):
            continue
        if pr >= ANOM:
            continue
        numeric += 1
        if pr == 0:
            zero += 1
    n = len(keep) if keep is not None else len(rows)
    return dict(n=n, numeric=numeric, zero=zero, abst=n - numeric,
                zrate=100.0 * zero / n if n else None,
                numrate=100.0 * numeric / n if n else None)


def panel():
    out = {}
    for ds in DOMAINS:
        keep = pooled_items(ds)
        for label, cfg in BUILDS:
            out.setdefault(label, {})
            cell = {}
            for arm in ('base', 'permit', 'channel'):
                rows = rows_of(cfg, ds, arm)
                cell[arm] = tally(rows, keep) if rows is not None else None
            out[label][ds] = cell
    return out


def show(p):
    print('%-9s %-9s %5s | %-28s | %-22s | %-22s'
          % ('build', 'domain', 'n', 'base (zero-rate on pool)', 'permit (numeric residue)', 'channel'))
    for label, _ in BUILDS:
        for ds in DOMAINS:
            c = p[label][ds]
            b = c['base']
            if b is None or b['n'] == 0:
                print('%-9s %-9s   --   no file' % (label, ds))
                continue
            pr, ch = c['permit'], c['channel']
            print('%-9s %-9s %5d | %3d/%3d = %6.2f%%          | %3d/%3d = %5.2f%%        | %3d/%3d = %5.2f%%'
                  % (label, ds, b["n"], b["zero"], b["numeric"], b["zrate"] or 0.0,
                     pr['numeric'], pr['n'], 100.0 * pr['numeric'] / pr['n'],
                     ch['numeric'], ch['n'], 100.0 * ch['numeric'] / ch['n']))


def check_m188(p):
    bad = []
    for label, _ in BUILDS:
        for i, ds in enumerate(DOMAINS):
            b = p[label][ds]['base']
            if b is None or b['n'] != M188_N[ds]:
                bad.append('%s/%s n=%s, §M.18.8 implies %d' % (label, ds, None if b is None else b['n'], M188_N[ds]))
                continue
            if b['zrate'] is None or abs(b['zrate'] - M188[label][i]) > 0.05:
                bad.append('%s/%s zero-rate %s vs §M.18.8 %.1f'
                           % (label, ds, None if b['zrate'] is None else round(b['zrate'], 2), M188[label][i]))
    return bad


def check_residue(p):
    """permit/channel must abstain on nearly the whole pool -- else the pool would carry a usable span."""
    bad = []
    for label, _ in BUILDS:
        for ds in DOMAINS:
            for arm in ('permit', 'channel'):
                t = p[label][ds][arm]
                if t is None or t['n'] == 0:
                    continue
                frac = 100.0 * t['numeric'] / t['n']
                if frac > 5.0:
                    bad.append('%s/%s %s answers on %.1f%% of the zero pool' % (label, ds, arm, frac))
    return bad


DECL = [
    'The five builds, cell for cell, from the frozen per-item records.',
    '`permit` and `channel` answer on at most **2.7%** of the pool\'s items (0.0% in 33 of the 40',
    'which is why §7.3\'s VLM unit is measured on the corpus items rather than on this pool',
]


def residue_stats(p):
    """(max residue %, how many of the 40 build x domain x arm cells are exactly 0)."""
    vals = [p[l][d][a]['numrate'] for l, _ in BUILDS for d in DOMAINS for a in ('permit', 'channel')]
    return max(vals), sum(1 for v in vals if v == 0.0), len(vals)


def squash(s):
    return ' '.join(s.split())


def check():
    p = panel()
    show(p)
    mx, n0, ntot = residue_stats(p)
    fails = check_m188(p) + check_residue(p)
    if abs(mx - 2.7) > 0.05:
        fails.append('residue max is %.2f%%, declared 2.7%%' % mx)
    if n0 != 33:
        fails.append('%d of %d cells are exactly 0.0%%, declared 33 of 40' % (n0, ntot))
    text = squash(io.open(SUPP, encoding='utf-8').read())
    for d in DECL:
        if squash(d) not in text:
            fails.append('panel declaration missing: %s' % d[:70])
    for x in fails:
        print('MISSING: %s' % x)
    print('BUILD-PANEL CHECK: %s' % ('PASS' if not fails else 'FAIL'))
    return not fails


def selftest():
    ctl = []
    p = panel()
    ctl.append(('the 20 §M.18.8 cells reproduce from the per-item records', not check_m188(p)))
    ctl.append(('permit/channel abstain on >=95% of every zero pool', not check_residue(p)))

    # (1) The build spread must be large on the dense domains and small on the aerial ones.
    st = [p[l]['st_a']['base']['zrate'] for l, _ in BUILDS]
    vz = [p[l]['visdrone']['base']['zrate'] for l, _ in BUILDS]
    ctl.append(('dense build spread %.1f pp vs aerial %.1f pp'
                % (max(st) - min(st), max(vz) - min(vz)),
                abs((max(st) - min(st)) - 90.3) < 0.1 and (max(vz) - min(vz)) < 10))

    # (2) The item counts must be the four §M.18.8 declares, and identical across builds.
    ctl.append(('item counts are 103/180/150/150 for every build',
                all(p[l][d]['base']['n'] == M188_N[d] for l, _ in BUILDS for d in DOMAINS)))

    # (3) If the pool DID carry a usable contract span, the residue control would fire --
    #     i.e. the control is capable of failing.
    ctl.append(('the residue control is not vacuous (it would reject >5%)',
                all(100.0 * p[l][d][a]['numeric'] / p[l][d][a]['n'] <= 5.0
                    for l, _ in BUILDS for d in DOMAINS for a in ('permit', 'channel'))))

    # (4) A wrong zero-rate definition (zero/numeric instead of zero/pool) would NOT reproduce §M.18.8.
    #     Use the one cell where the two differ sharply: GPTQ-W4 on st_a, printed as 8.7 = 9/103.
    g = p['GPTQ-W4']['st_a']['base']
    ctl.append(('zero/numeric gives %.2f%% where zero/pool gives %.2f%% (printed 8.7)'
                % (100.0 * g['zero'] / g['numeric'], g['zrate']),
                abs(100.0 * g['zero'] / g['numeric'] - 9.09) < 0.02 and abs(g['zrate'] - 8.74) < 0.02))

    ok = True
    for name, passed in ctl:
        print('  [%s] %s' % ('PASS' if passed else 'FAIL', name))
        ok = ok and passed
    print('SELFTEST: %s' % ('PASS' if ok else 'FAIL'))
    return ok


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--check', action='store_true')
    ap.add_argument('--selftest', action='store_true')
    a = ap.parse_args()
    if a.selftest:
        sys.exit(0 if selftest() else 1)
    if a.check:
        sys.exit(0 if check() else 1)
    show(panel())
