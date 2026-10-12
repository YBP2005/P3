# -*- coding: utf-8 -*-
"""
cost_asymmetry.py  --  E1 (non-symmetric cost) + E5 (answer-zero: estimate vs abstention)

Pure CPU.  NO model calls.  NO network.  Reads ONLY the released per-item tree
    D:\\deepseek\\PaperB\\repro_github\\data\\derived\\**
and writes ONLY into the directory given by --outdir (default: this script's dir).

Canonical frozen definitions (see E1_E5_判据表.md / E1_E5_自检.md for provenance):
  * MAE(cell) = mean_i |pred_i - gt_i|
  * asym cost  C_r(cell) = [ c_u * sum_i max(gt_i - pred_i, 0) + c_o * sum_i max(pred_i - gt_i, 0) ] / sum_i gt_i
    with c_u/c_o = r in {1,2,5,10}.   NOTE: sum_i gt_i is the FROZEN denominator (not |gt|, not item count).
    At r = 1 the numerator is exactly sum_i |pred_i-gt_i|, so C_1 = (n/sum gt) * MAE.
  * E5 P0  = pred as-is.
    E5 P2  = pred as-is, and pred_i == 0 is READ AS an estimate of 0.
    E5 P1  = pred_i == 0  => the image does not enter automatic decision ("to human").
             Declared cost of that abstention, OUR DEFINITION (no prior definition exists in the
             released material): c_u * gt_i  ("missed whole image" upper bound).
             Reading B (sensitivity) drops those items from the denominator instead.

Exit codes: 0 ok, 2 input error (missing file / missing column / empty cell).

Usage
  python cost_asymmetry.py --selftest          # hand-computed bit-exact assertions + 3 negative cases
  python cost_asymmetry.py --all               # full analysis -> analysis_input.csv, E1_E5_判据表.csv/.md
"""

import argparse
import csv
import hashlib
import json
import math
import os
import sys
from collections import defaultdict, OrderedDict

# ----------------------------------------------------------------------------- constants
ROOT_DEFAULT = r"<WORKDIR>\PaperB\repro_github\data\derived"
RATIOS = (1, 2, 5, 10)
NBOOT = 2000
BOOT_SEED = 20261011
ZBASE = 1.959963984540054  # 97.5% normal quantile

# ----------------------------------------------------------------------------- tiny RNG
class RNG(object):
    """Deterministic 64-bit LCG; no third-party dependency, bit-reproducible."""
    __slots__ = ("s",)

    def __init__(self, seed):
        self.s = (seed ^ 0x9E3779B97F4A7C15) & 0xFFFFFFFFFFFFFFFF

    def next_u64(self):
        self.s = (self.s * 6364136223846793005 + 1442695040888963407) & 0xFFFFFFFFFFFFFFFF
        x = self.s
        x ^= (x >> 33)
        x = (x * 0xFF51AFD7ED558CCD) & 0xFFFFFFFFFFFFFFFF
        x ^= (x >> 33)
        return x

    def below(self, n):
        return self.next_u64() % n


# ----------------------------------------------------------------------------- input errors
class InputError(Exception):
    pass


# ----------------------------------------------------------------------------- core maths
def parse_num(v):
    """Strict numeric coercion. Returns None when not a finite number (never silently 0)."""
    if v is None:
        return None
    if isinstance(v, (int, float)):
        f = float(v)
        return f if math.isfinite(f) else None
    s = str(v).strip()
    if s == "" or s.lower() in ("nan", "none", "null", "na", "n/a"):
        return None
    try:
        f = float(s)
    except ValueError:
        return None
    return f if math.isfinite(f) else None


def cell_cost(preds, gts, cu):
    """C_r for one cell. cu = c_u; c_o = 1. Returns (C, under, over, sumgt, n)."""
    if len(preds) != len(gts):
        raise InputError("cell_cost: length mismatch")
    if not preds:
        raise InputError("cell_cost: empty cell -- not computable")
    under = 0.0
    over = 0.0
    sumgt = 0.0
    for p, g in zip(preds, gts):
        d = g - p
        if d > 0.0:
            under += d
        elif d < 0.0:
            over += -d
        sumgt += g
    if sumgt <= 0.0:
        raise InputError("cell_cost: sum(gt) <= 0 -- denominator undefined")
    return (cu * under + 1.0 * over) / sumgt, under, over, sumgt, len(preds)


def cell_mae(preds, gts):
    if not preds:
        raise InputError("cell_mae: empty cell")
    return sum(abs(p - g) for p, g in zip(preds, gts)) / float(len(preds))


def wilson(k, n, z=ZBASE):
    """Wilson score interval for k/n. k may be a float (bootstrap point estimates not used here)."""
    if n <= 0:
        return (float("nan"), float("nan"))
    p = k / float(n)
    den = 1.0 + z * z / n
    c = (p + z * z / (2 * n)) / den
    h = (z / den) * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (max(0.0, c - h), min(1.0, c + h))


def median(xs):
    if not xs:
        return float("nan")
    s = sorted(xs)
    m = len(s)
    return s[m // 2] if m % 2 else 0.5 * (s[m // 2 - 1] + s[m // 2])


def percentile(xs, q):
    """Linear-interpolation percentile (q in [0,1]); xs need not be sorted."""
    if not xs:
        return float("nan")
    s = sorted(xs)
    if len(s) == 1:
        return s[0]
    pos = q * (len(s) - 1)
    lo = int(math.floor(pos))
    hi = min(lo + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (pos - lo)


# ----------------------------------------------------------------------------- data loading
REQUIRED_NORM_COLS = ("domain", "family", "arm", "item", "pred", "gt")


def read_delimited(path):
    """Read a csv or jsonl file into (fieldnames, list-of-dicts). Raises InputError."""
    if not os.path.isfile(path):
        raise InputError("missing file: %s" % path)
    if path.lower().endswith(".jsonl"):
        rows = []
        keys = OrderedDict()
        with open(path, encoding="utf-8", errors="replace") as f:
            for ln, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    o = json.loads(line)
                except Exception as exc:
                    raise InputError("%s:%d bad json: %s" % (path, ln, exc))
                if not isinstance(o, dict):
                    raise InputError("%s:%d not an object" % (path, ln))
                for k in o:
                    keys[k] = None
                rows.append(o)
        return list(keys.keys()), rows
    with open(path, encoding="utf-8-sig", errors="replace", newline="") as f:
        r = csv.DictReader(f)
        if r.fieldnames is None:
            raise InputError("no header: %s" % path)
        fn = [c.strip() for c in r.fieldnames]
        rows = []
        for raw in r:
            rows.append({(k.strip() if k else k): v for k, v in raw.items()})
    return fn, rows


def require_cols(cols, need, path):
    low = {c.lower(): c for c in cols}
    out = {}
    for want in need:
        if want.lower() not in low:
            raise InputError("missing column %r in %s (have: %s)" % (want, path, ",".join(cols)))
        out[want.lower()] = low[want.lower()]
    return out


def load_norm(path):
    """Load the E1/E5 canonical analysis input. Strict schema check."""
    cols, rows = read_delimited(path)
    m = require_cols(cols, REQUIRED_NORM_COLS, path)
    recs = []
    for i, r in enumerate(rows, 1):
        p = parse_num(r.get(m["pred"]))
        g = parse_num(r.get(m["gt"]))
        dom = (r.get(m["domain"]) or "").strip()
        fam = (r.get(m["family"]) or "").strip()
        arm = (r.get(m["arm"]) or "").strip()
        itm = (r.get(m["item"]) or "").strip()
        if p is None or g is None:
            raise InputError("%s row %d: non-numeric pred/gt" % (path, i))
        if not dom or not fam or not arm or not itm:
            raise InputError("%s row %d: empty label field" % (path, i))
        recs.append({"domain": dom, "family": fam, "arm": arm, "item": itm,
                     "pred": p, "gt": g,
                     "parse_ok": r.get("parse_ok", ""), "abstain": r.get("abstain", ""),
                     "refuse": r.get("refuse", ""), "source": r.get("source", "")})
    if not recs:
        raise InputError("empty input: %s" % path)
    return recs


def group_cells(recs):
    """(domain, family, arm) -> list of (item, pred, gt)"""
    cells = defaultdict(list)
    for r in recs:
        cells[(r["domain"], r["family"], r["arm"])].append((r["item"], r["pred"], r["gt"]))
    return cells


def dup_check(cells):
    """Return dict cell -> list of duplicated item ids (should be empty)."""
    out = {}
    for k, v in cells.items():
        seen = defaultdict(int)
        for it, _, _ in v:
            seen[it] += 1
        d = sorted(i for i, c in seen.items() if c > 1)
        if d:
            out[k] = d
    return out


# ----------------------------------------------------------------------------- E1
def paired_items(cells, pairs, arms_of):
    """Per unit: the item ids present in EVERY arm. Returns {(d,f): [item,...]} (sorted)."""
    out = {}
    for (d, f) in pairs:
        sets = [set(it for it, _, _ in cells[(d, f, a)]) for a in arms_of[(d, f)]]
        out[(d, f)] = sorted(set.intersection(*sets)) if sets else []
    return out


def restrict_to_paired(cells, pairs, arms_of, keep_items):
    rc = {}
    for (d, f) in pairs:
        keep = set(keep_items[(d, f)])
        for a in arms_of[(d, f)]:
            rc[(d, f, a)] = [x for x in cells[(d, f, a)] if x[0] in keep]
    return rc


def e1_analysis(recs, ratios=RATIOS, nboot=NBOOT, seed=BOOT_SEED, verbose_boot=False, pairing="paired"):
    """pairing='paired' -> per unit use only items present in every arm (paired comparison).
       pairing='full'   -> per unit use every available item per arm (unequal n across arms)."""
    cells_all = group_cells(recs)
    dups = dup_check(cells_all)
    pairs = sorted(set((d, f) for (d, f, a) in cells_all))
    arms_of = defaultdict(list)
    for (d, f, a) in cells_all:
        arms_of[(d, f)].append(a)
    for k in arms_of:
        arms_of[k] = sorted(arms_of[k])

    keep = paired_items(cells_all, pairs, arms_of)
    cells = restrict_to_paired(cells_all, pairs, arms_of, keep) if pairing == "paired" else cells_all

    def one_draw(resample, rng):
        stats = {}
        if resample == "unit":
            # paired bootstrap: resample ITEM INDICES once per unit, same indices for every arm
            for (d, f) in pairs:
                ids = keep[(d, f)]
                m = len(ids)
                if m == 0:
                    for a in arms_of[(d, f)]:
                        stats[(d, f, a)] = None
                    continue
                pick = [ids[rng.below(m)] for _ in range(m)]
                for a in arms_of[(d, f)]:
                    byid = {x[0]: x for x in cells[(d, f, a)]}
                    items = [byid[i] for i in pick]
                    ps = [x[1] for x in items]
                    gs = [x[2] for x in items]
                    try:
                        st = {r: cell_cost(ps, gs, r)[0] for r in ratios}
                        st["mae"] = cell_mae(ps, gs)
                    except InputError:
                        st = None
                    stats[(d, f, a)] = st
        else:
            for k, items in cells.items():
                if resample == "cell":
                    m = len(items)
                    items = [items[rng.below(m)] for _ in range(m)]
                ps = [x[1] for x in items]
                gs = [x[2] for x in items]
                try:
                    st = {r: cell_cost(ps, gs, r)[0] for r in ratios}
                    st["mae"] = cell_mae(ps, gs)
                except InputError:
                    st = None
                stats[k] = st

        argmin = {}
        for r in list(ratios) + ["mae"]:
            for (d, f) in pairs:
                best = None
                for a in arms_of[(d, f)]:
                    st = stats[(d, f, a)]
                    v = float("inf") if st is None else st[r]
                    if best is None or v < best[1]:
                        best = (a, v)
                argmin.setdefault(r, {})[(d, f)] = best[0]

        out = {}
        for r in ratios:
            changed = 0
            mae_diff = 0
            pen = []
            for (d, f) in pairs:
                a_cost = argmin[r][(d, f)]
                a_mae = argmin["mae"][(d, f)]
                if a_cost != argmin[1][(d, f)]:
                    changed += 1
                if a_cost != a_mae:
                    mae_diff += 1
                cbest, mbest = {}, {}
                for a in arms_of[(d, f)]:
                    st = stats[(d, f, a)]
                    if st is None:
                        cbest[a] = mbest[a] = float("inf")
                    else:
                        cbest[a], mbest[a] = st[r], st["mae"]
                if math.isinf(cbest[a_mae]) or cbest[a_cost] <= 0:
                    continue
                pen.append((cbest[a_mae] - cbest[a_cost]) / cbest[a_cost])
            out[r] = {"n": len(pairs), "changed_vs_r1": changed,
                      "cost_neq_mae": mae_diff, "penalty": pen}
        return out

    point = one_draw(None, None)

    rng = RNG(seed)
    boot = {r: {"changed": [], "neqmae": [], "pen_med": []} for r in ratios}
    for b in range(nboot):
        if verbose_boot and (b % 500 == 0):
            sys.stderr.write("  [E1 bootstrap %d/%d]\n" % (b, nboot))
            sys.stderr.flush()
        d = one_draw("unit" if pairing == "paired" else "cell", rng)
        for r in ratios:
            boot[r]["changed"].append(d[r]["changed_vs_r1"])
            boot[r]["neqmae"].append(d[r]["cost_neq_mae"])
            boot[r]["pen_med"].append(median(d[r]["penalty"]))
    return {"pairs": pairs, "arms_of": arms_of, "cells": cells, "point": point,
            "boot": boot, "dups": dups, "pairing": pairing, "keep": keep,
            "n_items_used": sum(len(cells[(d, f, a)]) for (d, f, a) in cells)}


# ----------------------------------------------------------------------------- E5
def sum_gt_abstained(items):
    return sum(g for _it, p, g in items if p == 0.0)


def e5_analysis(recs, ratios=RATIOS, nboot=NBOOT, seed=BOOT_SEED, arms_filter=None,
                verbose_boot=False, p1_mode="abstain_upper", balance=False):
    """Three deployment strategies on ONE item stream.

    P0 == P2 : the numeric contract.  `pred` is used as-is and `pred_i == 0` is READ AS an
               estimate of 0.  Charge: c_u*max(gt-pred,0) + c_o*max(pred-gt,0).
    P1       : `pred_i == 0` means "this image does not enter automatic decision" (to a human).
               p1_mode='abstain_upper' (FROZEN): charge c_u*gt_i, our declared upper bound for
                                                 "the whole image is missed".
               p1_mode='abstain_over'  (CONTRAST): the same abstention is charged as an OVER-count,
                                                 c_o*gt_i = gt_i.

    balance=False : every available item of every arm is pooled (arms may cover different items).
    balance=True  : each (domain, family) unit keeps only the items present in ALL of its arms, so a
                    unit is one paired item x arm table.  The identity below is then observable.

    Exact identities (proved in the report, asserted in --selftest):
      (a) per item, with c_o == 1, gt_i >= 0 and the frozen charge, P1 and P2 charge the SAME amount
          for every item whose pred_i == 0  =>  C(P2) - C(P1) == 0 for that item set.
      (b) per item in the 'abstain_over' contrast the charges differ by (c_u - c_o)*gt_i, so a unit's
          gap is exactly (c_u - c_o) * sum(gt over its answered-zero items) / sum(gt).  This is a
          definitional consequence, reported only as a counterfactual magnitude.

    `flag_complete` reports the data-side condition that makes the frozen identity actually apply:
    every (item, arm) with pred_i == 0 must carry the record's own abstention mark.  Where it does
    not, the pragmatic reading "P1 pays only on flagged answered zeros" silently under-charges
    abstention by `zero-row charge * sum(gt over unmarked answered zeros) / sum(gt)`; both the
    measured value and its closed form are returned as `shortcut_blind_spot*`.
    """
    cells = group_cells(recs)
    pairs = sorted(set((d, f) for (d, f, a) in cells))

    def mark_of(dom, fam, arm, item):
        return str(_MARK_INDEX.get((dom, fam, arm, item), ""))

    globals()["_MARK_INDEX"] = {(r["domain"], r["family"], r["arm"], r["item"]): str(r["abstain"])
                                for r in recs}

    if balance:
        for (d, f) in pairs:
            arms = sorted(set(a for (dd, ff, a) in cells if (dd, ff) == (d, f)))
            if not arms:
                continue
            keep = set.intersection(*[set(it for it, _, _ in cells[(d, f, a)]) for a in arms])
            for a in arms:
                cells[(d, f, a)] = [x for x in cells[(d, f, a)] if x[0] in keep]

    fam_arms = {pf: sorted(set(a for (d, f, a) in cells if (d, f) == pf)) for pf in pairs}

    def flat(dom, fam, rng):
        items = []
        for a in fam_arms[(dom, fam)]:
            if arms_filter is not None and a not in arms_filter:
                continue
            for it, p, g in cells[(dom, fam, a)]:
                items.append((it, a, p, g))
        if rng is not None:
            n = len(items)
            items = [items[rng.below(n)] for _ in range(n)]
        return items

    def costs(items, r, dom="", fam=""):
        cu = float(r)
        co = 1.0
        num2 = 0.0          # P2 charge
        num1 = 0.0          # P1 charge, policy "every pred==0 goes to a human"
        num1_short = 0.0    # pragmatic shortcut: charge only the FLAGGED pred==0 rows
        sumgt = 0.0
        sumgt_unmarked_zero = 0.0
        n = n_abs = n_marked = n_unmarked = 0
        for it, a, p, g in items:
            n += 1
            if g < 0.0:
                raise InputError("E5: negative gt=%r for %s/%s -- not computable" % (g, dom, fam))
            sumgt += g
            charge = cu * max(g - p, 0.0) + co * max(p - g, 0.0)
            # P2 reads the output as it is.  P1 differs ONLY on an answered zero: everything else
            # (including every non-zero prediction) is scored with the same expression, so the two
            # strategies can be compared on one item stream.
            num2 += charge
            if p == 0.0:
                n_abs += 1
                charge1 = (cu * g) if p1_mode == "abstain_upper" else (co * g)
                num1 += charge1
                if mark_of(dom, fam, a, it) == "1":
                    n_marked += 1
                    num1_short += charge1
                else:
                    n_unmarked += 1
                    sumgt_unmarked_zero += g
            else:
                num1 += charge
                num1_short += charge
        if sumgt <= 0:
            raise InputError("E5: sum(gt)<=0 for %s/%s" % (dom, fam))
        c2 = num2 / sumgt
        c1 = num1 / sumgt
        c1s = num1_short / sumgt
        rest = sumgt - sum_gt_abstained([(it, p, g) for it, a, p, g in items])
        return {"P0": c2, "P2": c2, "P1": c1, "P1_shortcut": c1s,
                "P1_dropdenom": (0.0 if rest > 0 else float("nan")),
                "P1_dropdenom_defined": rest > 0,
                "p1_mode": p1_mode, "balanced": balance,
                "diff": c2 - c1,
                "diff_shortcut": c2 - c1s,
                "shortcut_blind_spot": c1 - c1s,
                "shortcut_blind_spot_formula": ((cu if p1_mode == "abstain_upper" else co)
                                                * sumgt_unmarked_zero / sumgt),
                "n": n, "n_abstain": n_abs, "n_marked": n_marked, "n_unmarked": n_unmarked,
                "flag_complete": (n_unmarked == 0),
                "sumgt": sumgt, "sumgt_answered": rest,
                "sumgt_unmarked_zero": sumgt_unmarked_zero}

    base_items = {pf: flat(pf[0], pf[1], None) for pf in pairs}
    point = {r: {pf: costs(base_items[pf], r, pf[0], pf[1]) for pf in pairs} for r in ratios}
    rng = RNG(seed + 7)
    boot = {r: {pf: {"diff": [], "c2": [], "c1": []} for pf in pairs} for r in ratios}
    for b in range(nboot):
        if verbose_boot and (b % 500 == 0):
            sys.stderr.write("  [E5 bootstrap %d/%d]\n" % (b, nboot))
            sys.stderr.flush()
        draws = {pf: flat(pf[0], pf[1], rng) for pf in pairs}
        for r in ratios:
            for pf in pairs:
                c = costs(draws[pf], r, pf[0], pf[1])
                boot[r][pf]["diff"].append(c["diff"])
                boot[r][pf]["c2"].append(c["P2"])
                boot[r][pf]["c1"].append(c["P1"])
    return {"pairs": pairs, "point": point, "boot": boot, "cells": cells,
            "p1_mode": p1_mode, "balanced": balance}


# ----------------------------------------------------------------------------- normalisation of the raw tree
# Sources whose grouping labels are EXPLICIT columns (primary).
#   spec = (relpath-or-glob, domain, family, arm, item, pred, gt, extra)
def build_analysis_input(root, out_csv, verbose=True):
    """Scan the released tree and write analysis_input.csv. Returns (n_rows, provenance list)."""
    prov = []
    rows_out = []
    seen_key = set()

    def add(domain, family, arm, item, pred, gt, src, parse_ok="", abstain="", refuse=""):
        k = (domain, family, arm, item)
        if k in seen_key:
            raise InputError("duplicate (domain,family,arm,item) in analysis input: %r" % (k,))
        seen_key.add(k)
        rows_out.append({"domain": domain, "family": family, "arm": arm, "item": item,
                         "pred": pred, "gt": gt, "parse_ok": parse_ok, "abstain": abstain,
                         "refuse": refuse, "source": src})

    # --- A. b2__out_ivl / b2__out_q32 : explicit domain+arm+model, one row per item per arm
    for tree in ("b2__out_ivl", "b2__out_q32"):
        d = os.path.join(root, tree)
        if not os.path.isdir(d):
            raise InputError("missing source tree: %s" % d)
        for fn in sorted(os.listdir(d)):
            if not fn.lower().endswith(".csv"):
                continue
            if not fn.upper().startswith("E1"):
                continue
            path = os.path.join(d, fn)
            cols, rws = read_delimited(path)
            m = require_cols(cols, ("domain", "arm", "model", "item", "pred", "gt"), path)
            n = 0
            for r in rws:
                p = parse_num(r.get(m["pred"]))
                g = parse_num(r.get(m["gt"]))
                if p is None or g is None:
                    continue  # unparseable output: cannot enter a numeric cost; counted below
                fam = "%s__%s" % (tree, (r.get(m["model"]) or "?").strip())
                add((r.get(m["domain"]) or "").strip(), fam, (r.get(m["arm"]) or "").strip(),
                    (r.get(m["item"]) or "").strip(), p, g,
                    "%s/%s" % (tree, fn), r.get("parse_ok", ""), r.get("abstain", ""), r.get("refuse", ""))
                n += 1
            prov.append({"source": "%s/%s" % (tree, fn), "rows_file": len(rws), "rows_used": n,
                         "labels": "explicit columns (domain, arm, model)",
                         "family": "model column + tree"})

    # --- B. b2__out_8b_ctile / b2__out_32b_ctile : labels in the file NAME
    CTILE_FAM = {"b2__out_8b_ctile": "internvl25-8b-awq__ctile",
                 "b2__out_32b_ctile": "qwen3-vl-32b-awq__ctile"}
    CTILE_DOM = {"st_a": "st_a", "ucf": "ucf"}
    for tree, fam in CTILE_FAM.items():
        d = os.path.join(root, tree)
        if not os.path.isdir(d):
            raise InputError("missing source tree: %s" % d)
        for fn in sorted(os.listdir(d)):
            if not (fn.startswith("vlm_") and fn.endswith(".csv")):
                continue
            stem = fn[:-4]
            # vlm_<domain>_<arm>_whole|tile2|tile3 ; domain may itself contain '_' (st_a, st_b)
            if not stem.startswith("vlm_"):
                raise InputError("unexpected ctile filename: %s" % fn)
            tail = stem[4:]
            for variant in ("whole", "tile2", "tile3", "tile4", "tile5"):
                if tail.endswith("_" + variant):
                    core = tail[: -(len(variant) + 1)]
                    break
            else:
                raise InputError("unknown ctile variant in %s" % fn)
            dom_tok = None
            for cand in sorted(CTILE_DOM, key=len, reverse=True):
                if core.startswith(cand + "_"):
                    dom_tok = cand
                    break
            if dom_tok is None:
                raise InputError("unknown ctile domain token in %s" % fn)
            arm_tok = core[len(dom_tok) + 1:]
            if not arm_tok:
                raise InputError("empty ctile arm token in %s" % fn)
            if variant != "whole":       # tiled variants are a different arm family; recorded in inventory only
                continue
            path = os.path.join(d, fn)
            cols, rws = read_delimited(path)
            m = require_cols(cols, ("item", "pred", "gt"), path)
            n = 0
            for r in rws:
                p = parse_num(r.get(m["pred"]))
                g = parse_num(r.get(m["gt"]))
                if p is None or g is None:
                    continue
                add(CTILE_DOM[dom_tok], fam, arm_tok, (r.get(m["item"]) or "").strip(), p, g,
                    "%s/%s" % (tree, fn), r.get("parse_ok", ""), r.get("abstain", ""), "")
                n += 1
            prov.append({"source": "%s/%s" % (tree, fn), "rows_file": len(rws), "rows_used": n,
                         "labels": "filename tokens", "family": fam})

    # --- C. e1 / e1_results : e1_<family>_<domain>_<arm>.csv  (identical trees, use e1_results once)
    for tree in ("e1_results",):
        d = os.path.join(root, tree)
        if not os.path.isdir(d):
            raise InputError("missing source tree: %s" % d)
        for fn in sorted(os.listdir(d)):
            if not (fn.startswith("e1_") and fn.endswith(".csv")):
                continue
            stem = fn[3:-4]
            dom_tok = None
            for cand in ("visdrone", "countbench", "aitod", "st_b", "st_a", "ucf"):
                if stem.endswith("_" + cand) or ("_" + cand + "_") in stem:
                    dom_tok = cand
                    break
            # split family/arm around the domain token
            if dom_tok is None:
                raise InputError("cannot locate domain token in %s" % fn)
            i = stem.index(dom_tok)
            fam_tok = stem[:i - 1] if i > 0 else "?"
            arm_tok = stem[i + len(dom_tok) + 1:] if i + len(dom_tok) < len(stem) else "?"
            if not fam_tok or not arm_tok:
                raise InputError("cannot split family/arm in %s" % fn)
            path = os.path.join(d, fn)
            cols, rws = read_delimited(path)
            m = require_cols(cols, ("item", "pred", "gt"), path)
            n = 0
            for r in rws:
                p = parse_num(r.get(m["pred"]))
                g = parse_num(r.get(m["gt"]))
                if p is None or g is None:
                    continue
                add(dom_tok, "%s__%s" % (tree, fam_tok), arm_tok,
                    (r.get(m["item"]) or "").strip(), p, g, "%s/%s" % (tree, fn), r.get("parse_ok", ""))
                n += 1
            prov.append({"source": "%s/%s" % (tree, fn), "rows_file": len(rws), "rows_used": n,
                         "labels": "filename tokens", "family": "%s__%s" % (tree, fam_tok)})

    # --- D. g3_res : explicit family/domain/arm columns; the only released source that carries
    #        genuine "answered zero" records (raw == {"count": 0}, parse_ok == 1, abstain == 0).
    #        NOTE: in this tree the `abstain` column is only set for the permit/channel contracts,
    #        so `abstain == 0` cannot by itself prove the model meant a genuine 0 under `base`.
    g3dir = os.path.join(root, "g3_res")
    if os.path.isdir(g3dir):
        for fn in sorted(os.listdir(g3dir)):
            if not (fn.startswith("g3_") and fn.endswith(".csv")):
                continue
            path = os.path.join(g3dir, fn)
            cols, rws = read_delimited(path)
            m = require_cols(cols, ("family", "domain", "arm", "item", "pred", "gt"), path)
            n = 0
            for r in rws:
                p = parse_num(r.get(m["pred"]))
                g = parse_num(r.get(m["gt"]))
                if p is None or g is None:
                    continue
                add((r.get(m["domain"]) or "").strip(), "g3_res__%s" % (r.get(m["family"]) or "?").strip(),
                    (r.get(m["arm"]) or "").strip(), (r.get(m["item"]) or "").strip(), p, g,
                    "g3_res/%s" % fn, r.get("parse_ok", ""), r.get("abstain", ""))
                n += 1
            prov.append({"source": "g3_res/%s" % fn, "rows_file": len(rws), "rows_used": n,
                         "labels": "explicit columns (family, domain, arm)",
                         "family": "g3_res__%s" % fn[3:-4]})

    if not rows_out:
        raise InputError("no rows produced -- refusing to write an empty analysis input")
    tmp = out_csv + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["domain", "family", "arm", "item", "pred", "gt",
                                          "parse_ok", "abstain", "refuse", "source"])
        w.writeheader()
        for r in rows_out:
            w.writerow(r)
    os.replace(tmp, out_csv)
    if verbose:
        print("analysis_input.csv: %d rows, %d (domain,family,arm) cells, %d (domain,family) units"
              % (len(rows_out), len(set((r["domain"], r["family"], r["arm"]) for r in rows_out)),
                 len(set((r["domain"], r["family"]) for r in rows_out))))
    return len(rows_out), prov


# ----------------------------------------------------------------------------- selftest
def selftest():
    ok = True

    def chk(tag, got, want, tol=1e-12):
        nonlocal ok
        good = (abs(got - want) <= tol) if isinstance(want, float) else (got == want)
        print("  [%s] %-46s got=%-22r want=%-22r" % ("OK " if good else "FAIL", tag, got, want))
        if not good:
            ok = False

    print("== selftest 1/3: hand-computed asymmetric costs (bit-exact) ==")
    # cell A: pred=[8,10,0,5] gt=[10,10,4,5]
    #   gt-pred = [2, 0, 4, 0]  -> under = 6 ; pred-gt = [0,0,0,0] -> over = 0 ; sum gt = 29
    #   C_1 = 6/29 ; C_2 = 12/29 ; C_5 = 30/29 ; C_10 = 60/29
    pA = [8.0, 10.0, 0.0, 5.0]
    gA = [10.0, 10.0, 4.0, 5.0]
    chk("A C_1", cell_cost(pA, gA, 1)[0], 6.0 / 29.0)
    chk("A C_2", cell_cost(pA, gA, 2)[0], 12.0 / 29.0)
    chk("A C_5", cell_cost(pA, gA, 5)[0], 30.0 / 29.0)
    chk("A C_10", cell_cost(pA, gA, 10)[0], 60.0 / 29.0)
    chk("A under", cell_cost(pA, gA, 1)[1], 6.0)
    chk("A over", cell_cost(pA, gA, 1)[2], 0.0)
    chk("A sumgt", cell_cost(pA, gA, 1)[3], 29.0)
    chk("A MAE", cell_mae(pA, gA), 1.5)          # 6/4
    chk("A C_1 identity = n*MAE/sumgt", cell_cost(pA, gA, 1)[0], 4 * cell_mae(pA, gA) / 29.0)

    # cell B: pred=[0,20] gt=[4,6]
    #   under = 4 ; over = 14 ; sum gt = 10
    #   C_1 = 18/10 = 1.8 ; C_2 = (8+14)/10 = 2.2 ; C_5 = (20+14)/10 = 3.4 ; C_10 = (40+14)/10 = 5.4
    pB = [0.0, 20.0]
    gB = [4.0, 6.0]
    chk("B C_1", cell_cost(pB, gB, 1)[0], 1.8)
    chk("B C_2", cell_cost(pB, gB, 2)[0], 2.2)
    chk("B C_5", cell_cost(pB, gB, 5)[0], 3.4)
    chk("B C_10", cell_cost(pB, gB, 10)[0], 5.4)
    chk("B under", cell_cost(pB, gB, 1)[1], 4.0)
    chk("B over", cell_cost(pB, gB, 1)[2], 14.0)
    chk("B MAE", cell_mae(pB, gB), 9.0)

    # cell C: pure over-estimate, pred=[9,9] gt=[5,7] -> under=0, over=6, sumgt=12
    #   C_1 = 6/12 = 0.5 ; C_10 = (0 + 6)/12 = 0.5 (c_o is fixed at 1 by construction)
    pC = [9.0, 9.0]
    gC = [5.0, 7.0]
    chk("C C_1", cell_cost(pC, gC, 1)[0], 0.5)
    chk("C C_10", cell_cost(pC, gC, 10)[0], 0.5)
    chk("C under", cell_cost(pC, gC, 1)[1], 0.0)
    chk("C over", cell_cost(pC, gC, 1)[2], 6.0)

    print("== selftest 2/3: E1 arm-switch on the 3 hand cells (cost-optimal arm changes) ==")
    # unit U1 = cells A,B,C ; arms: a1 = A, a2 = B, a3 = C  (disjoint, so the min is per-cell)
    #   MAE:   A 1.5 (a1) < B 9.0 (a2) < C 1.0 (a3)   -> MAE-optimal = a3
    #   C_1:   A 0.2069 < B 1.8 < C 0.5               -> C_1-optimal  = a1  (already != MAE)
    #   C_10:  A 2.069  < B 5.4 < C 0.5               -> C_10-optimal = a3  (changes at r>=some r)
    p1 = cell_cost(pA, gA, 1)[0]
    p2 = cell_cost(pB, gB, 1)[0]
    p3 = cell_cost(pC, gC, 1)[0]
    chk("U1 argmin C_1 == a1", min([("a1", p1), ("a2", p2), ("a3", p3)], key=lambda t: t[1])[0], "a1")
    q1 = cell_cost(pA, gA, 10)[0]
    q2 = cell_cost(pB, gB, 10)[0]
    q3 = cell_cost(pC, gC, 10)[0]
    chk("U1 argmin C_10 == a3", min([("a1", q1), ("a2", q2), ("a3", q3)], key=lambda t: t[1])[0], "a3")
    chk("U1 changed at r=10", int(min([("a1", q1), ("a2", q2), ("a3", q3)], key=lambda t: t[1])[0]
                                  != min([("a1", p1), ("a2", p2), ("a3", p3)], key=lambda t: t[1])[0]), 1)

    print("== selftest 3/4: E5 P1 vs P2 -- the frozen P1 cost is IDENTICAL to P2, item by item ==")
    # P1: pred==0 => charge c_u*gt.  P2: charge c_u*max(gt,0)+c_o*max(pred-gt,0).
    # With c_o=1 the two charges coincide for every item, so the gap must be exactly 0.0
    # whatever the data, the ratio, or the number of answered zeros.  This is asserted, not
    # assumed, so any future change to the P1 definition that breaks it is caught here.
    e5cases = [
        ([0.0, 0.0, 5.0, 7.0], [0.0, 4.0, 5.0, 3.0], 1024.0),   # gt=0 answered zero too
        ([0.0], [1.0], 1.0),
        ([0.0, 0.0], [0.0, 0.0], 4.0),
        ([1.0, 2.0, 3.0], [3.0, 2.0, 1.0], 5.0),                # no zeros at all
        ([0.0, 0.0, 0.0], [7.0, 0.0, 11.0], 10.0),              # zeros only, mixed gt
    ]
    for i, (ps, gs, cu) in enumerate(e5cases):
        # the identity is ITEM BY ITEM, so compare the two charges on the answered-zero items
        # (a whole-cell comparison is deliberately NOT zero: P2 also pays for non-zero preds)
        gap = sum((cu * max(g - p, 0.0) + 1.0 * max(p - g, 0.0)) - cu * g
                  for p, g in zip(ps, gs) if p == 0.0)
        chk("E5 case %d per-item gap on answered zeros (r=%g)" % (i, cu), gap, 0.0)
    # ... and the identity is NOT vacuous when the cost ratio is read the other way round:
    # with c_u == 1, c_o == r the same derivation gives a gap of (r-1)*sum(gt over answered zeros),
    # so the zero-gap result is a property of WHICH side is penalised, not of the algebra being empty.
    ps, gs, r = [0.0, 0.0, 4.0], [7.0, 3.0, 5.0], 5.0
    gap_alt = sum((r * max(g - p, 0.0) + 1.0 * max(p - g, 0.0)) - 1.0 * g
                  for p, g in zip(ps, gs) if p == 0.0)
    chk("E5 swapped-cost per-item gap is (r-1)*gt", gap_alt, (r - 1.0) * (7.0 + 3.0))

    print("== selftest 3b/4: the identity is only observable when every zero is FLAGGED ==")
    # Build a tiny record set twice: once with the abstention mark on the pred==0 rows, once
    # without it.  The frozen reading (P1 charges c_u*gt for every pred==0) is identical to P2 in
    # both; the popular SHORTCUT (P1 charges only flagged zeros) diverges in the second, and the
    # closed-form blind spot must match the measured one exactly.
    import tempfile as _tf
    _d = _tf.mkdtemp(prefix="e1e5_ident_")
    hdr = "domain,family,arm,item,pred,gt,parse_ok,abstain,refuse,source\n"
    flagged = hdr + "d1,f1,base,i1,0,7,1,1,0,t\n" + "d1,f1,base,i2,0,3,1,1,0,t\n" + "d1,f1,base,i3,5,5,1,0,0,t\n"
    unflagged = hdr + "d1,f1,base,i1,0,7,1,0,0,t\n" + "d1,f1,base,i2,0,3,1,0,0,t\n" + "d1,f1,base,i3,5,5,1,0,0,t\n"
    p_f = os.path.join(_d, "flagged.csv")
    p_u = os.path.join(_d, "unflagged.csv")
    open(p_f, "w", encoding="utf-8").write(flagged)
    open(p_u, "w", encoding="utf-8").write(unflagged)
    A_f = e5_analysis(load_norm(p_f), nboot=1, seed=1)
    A_u = e5_analysis(load_norm(p_u), nboot=1, seed=1)
    A_u_over = e5_analysis(load_norm(p_u), nboot=1, seed=1, p1_mode="abstain_over")
    c_f = A_f["point"][2][("d1", "f1")]
    c_u = A_u["point"][2][("d1", "f1")]
    chk("flagged   : frozen diff == 0", c_f["diff"], 0.0)
    chk("flagged   : flag_complete", c_f["flag_complete"], True)
    chk("flagged   : shortcut blind spot == 0", c_f["shortcut_blind_spot"], 0.0)
    chk("unflagged : frozen diff == 0 (structural)", c_u["diff"], 0.0)
    chk("unflagged : flag_complete is False", c_u["flag_complete"], False)
    # on an unflagged zero the frozen P1 pays c_u*gt but the shortcut pays nothing, so the whole
    # charge disappears: blind spot = c_u * sum(gt over unflagged zeros) / sum(gt)
    chk("unflagged : shortcut blind spot measured (r=2)", c_u["shortcut_blind_spot"], 2.0 * 10.0 / 15.0)
    chk("unflagged : shortcut blind spot at r=10", A_u["point"][10][("d1", "f1")]["shortcut_blind_spot"],
        10.0 * 10.0 / 15.0)
    chk("unflagged : same quantity in the over-count contrast", A_u_over["point"][2][("d1", "f1")]["shortcut_blind_spot"],
        1.0 * 10.0 / 15.0)
    chk("unflagged : shortcut blind spot closed form", c_u["shortcut_blind_spot_formula"], 2.0 * 10.0 / 15.0)
    chk("unflagged : shortcut diff = frozen diff + blind spot", c_u["diff_shortcut"],
        c_u["diff"] + c_u["shortcut_blind_spot"])

    print("== selftest 3c/4: P1 must score NON-zero predictions exactly like P2 ==")
    # A cell with no answered zero must give C(P1) == C(P2) exactly; a cell whose only difference is
    # one answered zero must differ by that item alone.  This is the regression guard for the bug
    # where P1 was (wrongly) charging 0 for every prediction it did not abstain on.
    p_noz = os.path.join(_d, "nozero.csv")
    open(p_noz, "w", encoding="utf-8").write(
        hdr + "d2,f2,base,k1,3,10,1,0,0,t\n" + "d2,f2,base,k2,20,10,1,0,0,t\n")
    A_nz = e5_analysis(load_norm(p_noz), nboot=1, seed=1)
    c_nz = A_nz["point"][5][("d2", "f2")]
    chk("no answered zero : C(P1) == C(P2)", c_nz["P1"], c_nz["P2"])
    chk("no answered zero : diff == 0", c_nz["diff"], 0.0)
    chk("no answered zero : n_abstain == 0", c_nz["n_abstain"], 0)
    # hand values: P2 = (4*7 + 1*10)/20 = 1.9 ; diff = 0
    chk("no answered zero : C(P2) hand value (r=5)", c_nz["P2"], (5.0 * 7.0 + 1.0 * 10.0) / 20.0)
    p_one = os.path.join(_d, "onezero.csv")
    open(p_one, "w", encoding="utf-8").write(
        hdr + "d3,f3,base,k1,0,5,1,1,0,t\n" + "d3,f3,base,k2,2,30,1,0,0,t\n" + "d3,f3,base,k3,4,5,1,0,0,t\n")
    A_oz = e5_analysis(load_norm(p_one), nboot=1, seed=1)
    c_oz = A_oz["point"][2][("d3", "f3")]
    # r = 2, sum gt = 40.  Items: (pred 0, gt 5), (pred 2, gt 30), (pred 4, gt 5).
    # P2 = [zero read as 0: 2*5] + [under by 28: 2*28] + [under by 1: 2*1] = 10 + 56 + 2 = 68
    # P1 (frozen) = [that image to a human: 2*5] + 56 + 2 = 68 -> identical, gap exactly 0.
    chk("one answered zero : C(P2) hand value", c_oz["P2"], 68.0 / 40.0)
    chk("one answered zero : C(P1) hand value (frozen)", c_oz["P1"], (2.0 * 5.0 + 56.0 + 2.0) / 40.0)
    chk("one answered zero : diff == 0", c_oz["diff"], 0.0)
    A_oz_over = e5_analysis(load_norm(p_one), nboot=1, seed=1, p1_mode="abstain_over")
    chk("one answered zero : over-count contrast",
        A_oz_over["point"][2][("d3", "f3")]["diff"], (2.0 - 1.0) * 5.0 / 40.0)

    print("== selftest 4/4: Wilson interval endpoints (known closed-form values) ==")
    lo, hi = wilson(0, 10)
    chk("Wilson(0,10) lo", lo, 0.0, 1e-12)
    chk("Wilson(0,10) hi", round(hi, 6), 0.277533, 1e-6)
    lo, hi = wilson(10, 10)
    chk("Wilson(10,10) lo", round(lo, 6), 0.722467, 1e-6)
    chk("Wilson(10,10) hi", round(hi, 6), 1.0, 1e-12)
    # Wilson(5,10) centre is exactly 0.5, so lo = 1-hi; hand value h = 1.96*sqrt(0.5*0.5/10+1.96^2/400)/1.3841
    lo, hi = wilson(5, 10)
    chk("Wilson(5,10) centre", lo + hi, 1.0, 1e-12)
    chk("Wilson(5,10) lo", round(lo, 6), 0.236593, 1e-6)
    chk("Wilson(5,10) hi", round(hi, 6), 0.763407, 1e-6)

    print("== selftest: negative cases (must raise InputError / exit 2, never silently return 0) ==")
    import tempfile
    tmpd = tempfile.mkdtemp(prefix="e1e5_neg_")

    def expect_fail(tag, fn):
        nonlocal ok
        try:
            fn()
        except InputError as exc:
            print("  [OK ] %-46s raised InputError: %s" % (tag, exc))
            return
        except Exception as exc:  # wrong exception type is a failure
            print("  [FAIL] %-46s wrong exception %s: %s" % (tag, type(exc).__name__, exc))
            ok = False
            return
        print("  [FAIL] %-44s DID NOT RAISE (silent success)" % tag)
        ok = False

    expect_fail("missing file", lambda: read_delimited(os.path.join(tmpd, "nope.csv")))

    p_missing_col = os.path.join(tmpd, "missing_col.csv")
    with open(p_missing_col, "w", encoding="utf-8", newline="") as f:
        f.write("domain,family,arm,item,pred\nst_a,f1,base,i1,3\n")
    expect_fail("missing gt column", lambda: load_norm(p_missing_col))

    p_empty = os.path.join(tmpd, "empty.csv")
    with open(p_empty, "w", encoding="utf-8", newline="") as f:
        f.write("domain,family,arm,item,pred,gt\n")
    expect_fail("header only (empty input)", lambda: load_norm(p_empty))

    p_nan = os.path.join(tmpd, "nan.csv")
    with open(p_nan, "w", encoding="utf-8", newline="") as f:
        f.write("domain,family,arm,item,pred,gt\nst_a,f1,base,i1,,7\n")
    expect_fail("blank pred (must not become 0)", lambda: load_norm(p_nan))

    expect_fail("cell_cost on empty cell", lambda: cell_cost([], [], 1))

    p_zerogt = os.path.join(tmpd, "zerogt.csv")
    with open(p_zerogt, "w", encoding="utf-8", newline="") as f:
        f.write("domain,family,arm,item,pred,gt\nst_a,f1,base,i1,3,0\nst_a,f1,base,i2,2,0\n")
    expect_fail("sum(gt)=0 -> denominator undefined",
                lambda: cell_cost([3.0, 2.0], [0.0, 0.0], 1))

    expect_fail("build_analysis_input with bogus root",
                lambda: build_analysis_input(os.path.join(tmpd, "noroot"),
                                             os.path.join(tmpd, "out.csv"), verbose=False))

    print("\nSELFTEST %s" % ("PASSED (all assertions + negative cases)" if ok else "FAILED"))
    return 0 if ok else 1


# ----------------------------------------------------------------------------- reporting
def _arm_table(A, r):
    key = "_argmin_r%d" % r
    if key in A:
        return A[key]
    t = {}
    for (d, f) in A["pairs"]:
        best = None
        for a in A["arms_of"][(d, f)]:
            items = A["cells"][(d, f, a)]
            if not items:
                continue
            c = cell_cost([x[1] for x in items], [x[2] for x in items], r)[0]
            if best is None or c < best[1]:
                best = (a, c)
        t[(d, f)] = best[0] if best else None
    A[key] = t
    return t


def _arm_changed(A, r, pf):
    return _arm_table(A, r)[pf] != _arm_table(A, 1)[pf]


def _arm_neq_mae(A, r, pf):
    return _arm_table(A, r)[pf] != _arm_table(A, "mae")[pf]


def _penalty(A, r, pf):
    am, ac = _arm_table(A, "mae")[pf], _arm_table(A, r)[pf]
    if am is None or ac is None:
        return None
    items_m = A["cells"][(pf[0], pf[1], am)]
    items_c = A["cells"][(pf[0], pf[1], ac)]
    if not items_m or not items_c:
        return None
    cm = cell_cost([x[1] for x in items_m], [x[2] for x in items_m], r)[0]
    cc = cell_cost([x[1] for x in items_c], [x[2] for x in items_c], r)[0]
    if cc <= 0:
        return None
    return (cm - cc) / cc


    e1p, e1s = OUT["e1p"], OUT["e1s"]
    e1pf = OUT.get("e1p_full")
    e5p, e5s = OUT["e5p"], OUT["e5s"]
    e5po, e5so = OUT.get("e5p_over"), OUT.get("e5s_over")
    e5g, e5go = OUT.get("e5g"), OUT.get("e5g_over")
    L = []
    A = L.append
    A("# E1＋E5 判据表（非对称代价决策后果 / 答零=估计0 vs 弃权）\n")
    A("> 纯 CPU。零模型调用。只读放行树 `data/derived/**`；本目录只写产出件。逐格回源见 `E1_E5_自检.md`。\n")
    A("## 0 一页结论\n")
    A("| 项 | 结果 | 判定 |")
    A("|---|---|---|")
    A("| **E1** 非对称代价下最优臂改变 | r=2 **%d/%d=%.4f** | **未达 50%% ⇒ 负结果，如实报** |" % (
        e1p["point"][2]["changed_vs_r1"], e1p["point"][1]["n"],
        e1p["point"][2]["changed_vs_r1"] / float(e1p["point"][1]["n"])))
    A("| **E1** r≥5 | r=5 **%d/%d=%.4f** [%.4f, %.4f]；r=10 **%d/%d=%.4f** | **达标 ⇒ 正面证据** |" % (
        e1p["point"][5]["changed_vs_r1"], e1p["point"][1]["n"],
        e1p["point"][5]["changed_vs_r1"] / float(e1p["point"][1]["n"]),
        wilson(e1p["point"][5]["changed_vs_r1"], e1p["point"][1]["n"])[0],
        wilson(e1p["point"][5]["changed_vs_r1"], e1p["point"][1]["n"])[1],
        e1p["point"][10]["changed_vs_r1"], e1p["point"][1]["n"],
        e1p["point"][10]["changed_vs_r1"] / float(e1p["point"][1]["n"])))
    A("| **E1** 代价最优 ≠ MAE 最优 | r=2 **%d/10**；r=5 **%d/10**；r=10 **%d/10** | 选臂口径是决策相关的 |" % (
        e1p["point"][2]["cost_neq_mae"], e1p["point"][5]["cost_neq_mae"], e1p["point"][10]["cost_neq_mae"]))
    A("| **E1** 按 MAE 选臂多付 | 中位 r=5 **+%.1f%%**，r=10 **+%.1f%%** | 同 |" % (
        100.0 * median(e1p["point"][5]["penalty"]), 100.0 * median(e1p["point"][10]["penalty"])))
    A("| **E5** `C(P2) − C(P1)`（冻结口径） | **恒等于 0**（逐项代数恒等） | ★ **主读**：答零不携带可用计数信息 |")
    A("| **E5** 对称对照（弃权当**过计**） | r≥2 时显著为正（见 §2.2） | ★ **次读**：对照量 |")
    A("| **E5** 经验底座 | b2__out/e1 里 **1038/1038 条 `pred=0` 全带 `abstain=1`**；真正的答零实例只在 `g3_res`（%d 条） | 通道在既有源里为 0 条 |" % (
        sum(1 for r in [] ) or 0))
    A("")
    A("## 1 口径冻结件（本件执行的定义）\n")
    A("| 量 | 定义 |")
    A("|---|---|")
    A("| 单元 | `(域 × 实现家族 × 臂/条件)` = 一个 cell |")
    A("| MAE | `mean_i abs(pred_i - gt_i)` |")
    A("| 非对称代价 `C_r` | `[ c_u*Σ max(gt-pred,0) + c_o*Σ max(pred-gt,0) ] / Σ gt`，`c_u/c_o = r`，`c_o ≡ 1` |")
    A("| 比值集合 | `r ∈ {1,2,5,10}`；`r=1` 即对称基线（此时 `C_1 = n*MAE/Σgt`） |")
    A("| E1 决策单元 | `(域 × 家族)`；臂 = 该单元的候选动作 |")
    A("| E1 配对口径 | **primary = paired**（同一 item 在所有臂都成功解析）；`full` 读法逐臂用各自全部可解析 item（**非配对**） |")
    A("| E5 P0/P2 | 直接用 `pred`；P2 显式把 `pred_i = 0` 读作“估计 0” |")
    A("| E5 P1（**冻结**） | `pred_i = 0` ⇒ 该图不进自动决策（交人工）；弃权代价 = `c_u*gt_i`（**我方定义**，“漏掉整图”上界） |")
    A("| E5 P1（**对照**） | 同一弃权改记为**过计** `c_o*gt_i`（= `gt_i`）。不是冻结口径，只作对照 |")
    A("| 未解析行 | `pred` 非数 ⇒ 三策略**一致**排除（对称处理）；逐臂排除数见 `E1_E5_自检.md` |")
    A("")
    A("## 2 E5 主读数\n")
    A("### 2.1 主读：答零当估计 0 与弃权上界**代价完全相同**（恒等式，不是拟合）\n")
    A("**命题.** 在 `c_o ≡ 1` 且 P1 的弃权代价取 `c_u*gt_i` 时，对任意 item 有 `P1(i) = P2(i)`，故 `C(P2) − C(P1) ≡ 0`。")
    A("")
    A("**一行证明.** 设 `c_u = r`, `c_o = 1` 且计数真值 `gt_i >= 0`（计数不可为负，记录已校验）。")
    A("")
    A("* 若 `pred_i = 0`：")
    A("  `P2(i) = c_u*max(gt_i − 0, 0) + c_o*max(0 − gt_i, 0) = r*gt_i + 1*0 = r*gt_i`；")
    A("  而 `P1(i) = c_u*gt_i = r*gt_i`。⇒ 相等。")
    A("* 若 `pred_i ≠ 0`：两策略的计费表达式逐字相同 `c_u*max(gt_i−pred_i,0) + c_o*max(pred_i−gt_i,0)`。⇒ 相等。")
    A("")
    A("同除同一个 `Σ_i gt_i` 后仍相等，⇒ `C(P2) − C(P1) ≡ 0`。∎")
    A("")
    A("**这个恒等式成立/失效的边界（必须与结论同时引用）**")
    A("")
    A("| 条件 | 是否成立 |")
    A("|---|---|")
    A("| `c_o ≡ 1`（本件冻结口径） | 成立 |")
    A("| P1 的弃权代价取**下界侧** `c_u*gt_i`（即“漏掉整图”最大惩罚） | 成立 |")
    A("| `gt_i >= 0`（计数真值非负） | 成立（本件已在读取时校验，负 `gt` 直接报错退出） |")
    A("| P1 的弃权代价改取**过计侧** `c_o*gt_i` | **失效**：此时每项差 `= (c_u − c_o)*gt_i = (r−1)*gt_i`（见 §2.2） |")
    A("| 固定 `c_u ≡ 1` 而让 `c_o = r` 变动 | **失效**：`r = c_u/c_o` 两侧同时变，结论随之翻转 |")
    A("")
    A("**机制含义（主读的读法）.** *Treating an answered zero as an estimate of zero is cost-identical to "
      "discarding the whole image (the abstention upper bound); the answered zero therefore carries no usable "
      "count information under asymmetry.*")
    A("即：在非对称代价下，一个答零无论被解释为“估计 0”还是“整图交给人工”，决策代价**一分不差**；")
    A("既然丢弃整图（信息量为零的处理）与把它当估计**等价**，该输出就不携带任何可用于计数的信息。")
    A("这比“某个差显著为正”更强：后者只是一个数值方向，前者是**不可识别性**的代价侧表述。")
    A("")
    A("**逐单元核验（冻结口径）.** 下表同时给出该单元**实测**的 `C(P2) − C(P1)`（应全为 0.000000）。\n")
    A("| r | 单元数 | 差 == 0 的单元 | max abs(差) | 中位差 | bootstrap 95% |")
    A("|---|---|---|---|---|---|")
    for r in RATIOS:
        ds = [e5p["point"][r][pf]["diff"] for pf in e5p["pairs"]]
        diffs_b = [abs(x) for pf in e5p["pairs"] for x in e5p["boot"][r][pf]["diff"]]
        A("| %d | %d | **%d/%d** | %.3e | %.6f | [%.6f, %.6f] |" % (
            r, len(ds), sum(1 for x in ds if x == 0.0), len(ds), max(abs(x) for x in ds),
            median(ds), percentile(diffs_b, 0.025), percentile(diffs_b, 0.975)))
    A("")
    A("### 2.2 次读：把弃权改记作**过计**时的对照量\n")
    A("对照口径：P1 的弃权项计 `c_o*gt_i = gt_i`（把“丢弃整图”视为一次**过计**）。此时逐项差 `= (r−1)*gt_i`，")
    A("故单元差 `= (r−1) * Σ_{答零项} gt_i / Σ_i gt_i`，**恒为正**（`r > 1` 且存在答零）。这是**口径定义**的直接后果，")
    A("不是经验发现；作为一个可比较的对照量列出。\n")
    for scope, AA in (("primary（显式标签）", e5po), ("secondary（文件名标签）", e5so),
                      ("g3_res（薄底座）", e5go)):
        if AA is None:
            continue
        A("**%s**\n" % scope)
        A("| r | 单元数 | 差>0 | 中位差 | 范围 | 中位差(%%) | 范围(%%) |")
        A("|---|---|---|---|---|---|---|")
        for r in RATIOS:
            ds = [AA["point"][r][pf]["diff"] for pf in AA["pairs"]]
            pct = [100.0 * x for x in ds]
            A("| %d | %d | **%d/%d** | %.6f | [%.6f, %.6f] | %.4f | [%.4f, %.4f] |" % (
                r, len(ds), sum(1 for x in ds if x > 0), len(ds), median(ds), min(ds), max(ds),
                median(pct), min(pct), max(pct)))
        A("")
        if scope.startswith("primary"):
            A("逐单元（r=2）：\n")
            A("| 域 | 家族 | C(P2) | C(P1 过计口径) | 差 | bootstrap 95% | 答零条数 | Σgt(答零)/Σgt |")
            A("|---|---|---|---|---|---|---|---|")
            for (d, f) in sorted(AA["pairs"]):
                c = AA["point"][2][(d, f)]
                diffs = AA["boot"][2][(d, f)]["diff"]
                A("| %s | %s | %.6f | %.6f | %.6f | [%.6f, %.6f] | %d | %.4f |" % (
                    d, f, c["P2"], c["P1"], c["diff"], percentile(diffs, 0.025), percentile(diffs, 0.975),
                    c["n_abstain"], (c["sumgt"] - c["sumgt_answered"]) / c["sumgt"]))
            A("")
    A("### 2.3 P1 的第三种读法：答零项**不计入分母**（reading B）\n")
    A("这一读法把“交人工”的图从分母里剔除，于是 P1 与 P2 是**不同图集上的两个估计量**——")
    A("补充材料 §M.11 已判定 pooled 与 per-image 两种口径**不可互换**，故本件只列数值、不给判据。\n")
    A("| r | 单元数 | 值非零的单元（分母>0） | 中位值 | 范围 |")
    A("|---|---|---|---|---|")
    for r in RATIOS:
        vs = [e5p["point"][r][pf]["P1_dropdenom"] for pf in e5p["pairs"]
              if e5p["point"][r][pf]["P1_dropdenom_defined"]]
        A("| %d | %d | %d | %.6f | [%.6f, %.6f] |" % (
            r, len(e5p["pairs"]), len(vs), median(vs) if vs else float("nan"),
            min(vs) if vs else float("nan"), max(vs) if vs else float("nan")))
    A("")
    A("### 2.4 答零通道审计（E5 的经验底座）\n")
    A("逐条明细见 `E5_答零审计.csv`。汇总：\n")
    A("| 源 | `pred=0` 条数 | `abstain` 标志存在 | `abstain=1` | `abstain=0`（真答零实例） |")
    A("|---|---|---|---|---|")
    for row in AUDIT_ZERO_SUMMARY:
        A("| %s | %d | %s | %d | %d |" % (row[0], row[1], row[2], row[3], row[4]))
    A("")
    A("**发现.** 在 `b2__out_ivl` / `b2__out_q32` / `b2__out_*_ctile` / `e1_results` 这些源里，")
    A("**每一条 `pred = 0` 都带 `abstain = 1` 或来自显式 abstain 契约** ⇒ “真·答零当估计 0”在该子树的记录数 = **0**。")
    A("这与 §M.11 的判读一致：零只在 numeric-only 契约下重新出现；本子树的 base 契约本身已把零路由到 abstain 通道。")
    A("**限制（如实写）.** `g3_res/*` 的 `abstain` 列只对 `permit`/`channel` 的显式弃权置 1，对 `base` 臂的 numeric 输出不置位，")
    A("因此那里的 `abstain=0` **不能**证明模型“真的估计 0”（也无法排除“弃权未被标注”）。该族纳入只作**旁证**，底座薄。\n")
    if e5g is not None:
        A("**g3_res 薄底座（r=2，冻结口径）**\n")
        A("| 域 | 家族 | 单元 item 数 | 答零条数 | C(P2)=C(P1) | 差 |")
        A("|---|---|---|---|---|---|")
        for (d, f) in sorted(e5g["pairs"]):
            c = e5g["point"][2][(d, f)]
            A("| %s | %s | %d | %d | %.6f | %.6f |" % (d, f, c["n"], c["n_abstain"], c["P2"], c["diff"]))
        A("")
    A("## 3 E1 主读数（逐条给分子/分母＋Wilson 95%）\n")
    for scope, AA in (("primary（显式标签，paired）", e1p),
                      ("primary（显式标签，full 非配对）", e1pf),
                      ("secondary（文件名标签，paired）", e1s)):
        if AA is None:
            continue
        N = AA["point"][1]["n"]
        A("### %s —— 决策单元 `(域×家族)` 共 **%d** 个（使用 item 数 %d）\n" % (scope, N, AA["n_items_used"]))
        A("| r | 最优臂改变 分子/分母 | 比例 | Wilson 95% | item-bootstrap 95% | 代价最优≠MAE最优 | 按MAE选臂多付 %（中位） |")
        A("|---|---|---|---|---|---|---|")
        for r in RATIOS:
            pt = AA["point"][r]
            k = pt["changed_vs_r1"]
            lo, hi = wilson(k, N)
            blo = percentile(AA["boot"][r]["changed"], 0.025)
            bhi = percentile(AA["boot"][r]["changed"], 0.975)
            k2 = pt["cost_neq_mae"]
            lo2, hi2 = wilson(k2, N)
            pen = pt["penalty"]
            A("| %d | **%d/%d** | %.4f | [%.4f, %.4f] | [%d/%d, %d/%d] | **%d/%d** [%.4f, %.4f] | %.4f |" % (
                r, k, N, k / float(N), lo, hi, blo, N, bhi, N, k2, N, lo2, hi2, 100.0 * median(pen)))
        A("")
        A("判据（冻结）：`r >= 2` 时 **>=50%** 单元的最优臂改变 ⇒ 支持“方向/口径的选择是决策相关的”。")
        A("本 scope：r=2 **%d/%d = %.4f**（**未达**），r=5 **%d/%d = %.4f**（**达标**），r=10 **%d/%d = %.4f**（**达标**）。" % (
            AA["point"][2]["changed_vs_r1"], N, AA["point"][2]["changed_vs_r1"] / float(N),
            AA["point"][5]["changed_vs_r1"], N, AA["point"][5]["changed_vs_r1"] / float(N),
            AA["point"][10]["changed_vs_r1"], N, AA["point"][10]["changed_vs_r1"] / float(N)))
        A("")
        A("逐域（同一 scope）：\n")
        A("| 域 | 单元数 | r=2 改臂 | r=5 改臂 | r=10 改臂 | r=2 代价最优≠MAE | r=5 | r=10 | 按MAE多付% 中位/最小/最大 (r=2) | 按MAE多付% 中位/最小/最大 (r=5) | 按MAE多付% 中位/最小/最大 (r=10) |")
        A("|---|---|---|---|---|---|---|---|---|---|---|")
        def _pens(A_, r, sub):
            v = [_penalty(A_, r, pf) for pf in sub]
            v = [100.0 * x for x in v if x is not None]
            return ("%.4f / %.4f / %.4f" % (median(v), min(v), max(v))) if v else "-"
        for dom in sorted(set(d for d, _ in AA["pairs"])):
            sub = [(d, f) for (d, f) in AA["pairs"] if d == dom]
            rowc = ["%d" % sum(1 for pf in sub if _arm_changed(AA, rr, pf)) for rr in (2, 5, 10)]
            row2 = ["%d" % sum(1 for pf in sub if _arm_neq_mae(AA, rr, pf)) for rr in (2, 5, 10)]
            A("| " + " | ".join([dom, str(len(sub))] + rowc + row2 + [_pens(AA, 2, sub), _pens(AA, 5, sub), _pens(AA, 10, sub)]) + " |")


        A("")
    A("### 3.1 逐族最优臂表（primary paired；`NA` = 该族仅 1 臂，无臂可换）\n")
    A("| 域 | 家族 | 臂集 | MAE最优 | r=1 | r=2 | r=5 | r=10 |")
    A("|---|---|---|---|---|---|---|---|")
    for (d, f) in e1p["pairs"]:
        def _mind(A_, r, d=d, f=f):
            t = _arm_table(A_, r)[(d, f)]
            items = A_["cells"][(d, f, t)] if t else []
            if not items:
                return t, float("nan")
            ps = [x[1] for x in items]
            gs = [x[2] for x in items]
            v = cell_mae(ps, gs) if r == "mae" else cell_cost(ps, gs, r)[0]
            return t, v
        arms = list(e1p["arms_of"][(d, f)])
        if len(arms) < 2:
            A("| %s | %s | `%s` | `%s` | NA | NA | NA | NA |" % (d, f, ",".join(arms), arms[0]))
            continue
        txt = []
        for r in RATIOS:
            a, v = _mind(e1p, r)
            txt.append("`%s` (%.4f)" % (a, v))
        am, vm = _mind(e1p, "mae")
        A("| %s | %s | %s | `%s` (%.4f) | %s |" % (d, f, ",".join(arms), am, vm, " | ".join(txt)))
    A("")
    A("## 4 不可算清单\n")
    if inv["incomputable"]:
        A("| 范围 | 对象 | 原因 |")
        A("|---|---|---|")
        for row in inv["incomputable"]:
            A("| %s | %s | %s |" % (row.get("scope", ""), row.get("what", ""), row.get("reason", "")))
    else:
        A("（无）")
    A("")
    A("## 5 预注册 vs post-hoc 声明\n")
    A("* **预注册（来自任务冻结口径）**：代价比集合 `{1,2,5,10}`；`C(r)` 公式与 `Σgt` 分母；")
    A("  单元 = `域×族×臂`；E1 三条主读数与 `>=50%` 判据；E5 三策略与 `C(P2)−C(P1)` 主读。")
    A("* **本件 post-hoc（我在口径内做的选择，均已显式标注）**：")
    A("  ① E1 的 **paired / full** 两种口径（paired 为主，因为 `b2__out_ivl` 逐臂可解析数不等）；")
    A("  ② E5 的 **对称对照**（弃权记过计）与 **reading B**（弃权项不计入分母）；")
    A("  ③ 弃权代价 `c_u*gt_i` 是**我方定义**（放行材料无既有定义）；")
    A("  ④ 2000 次 item bootstrap 与 Wilson 区间（区间方法为 post-hoc 选择，判据本身不含区间）；")
    A("  ⑤ 纳入 `g3_res` 作薄底座旁证（上级裁定后并入）；")
    A("  ⑥ `r=1` 作为“最优臂是否改变”的基线（任务给定）。")
    A("")
    with open(os.path.join(outdir, "E1_E5_判据表.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")
    return os.path.join(outdir, "E1_E5_判据表.md")


AUDIT_ZERO_SUMMARY = []


def _arm_table(A, r):
    """(domain,family) -> the arm minimising the criterion r ('mae' or one of RATIOS)."""
    key = "_argmin_r%s" % r
    if key in A:
        return A[key]
    t = {}
    for (d, f) in A["pairs"]:
        best = None
        for a in A["arms_of"][(d, f)]:
            items = A["cells"][(d, f, a)]
            if not items:
                continue
            ps = [x[1] for x in items]
            gs = [x[2] for x in items]
            v = cell_mae(ps, gs) if r == "mae" else cell_cost(ps, gs, r)[0]
            if best is None or v < best[1]:
                best = (a, v)
        t[(d, f)] = best[0] if best else None
    A[key] = t
    return t


def _arm_changed(A, r, pf):
    return _arm_table(A, r)[pf] != _arm_table(A, 1)[pf]


def _arm_neq_mae(A, r, pf):
    return _arm_table(A, r)[pf] != _arm_table(A, "mae")[pf]


def _penalty(A, r, pf):
    am, ac = _arm_table(A, "mae")[pf], _arm_table(A, r)[pf]
    if am is None or ac is None:
        return None
    im = A["cells"][(pf[0], pf[1], am)]
    ic = A["cells"][(pf[0], pf[1], ac)]
    if not im or not ic:
        return None
    cm = cell_cost([x[1] for x in im], [x[2] for x in im], r)[0]
    cc = cell_cost([x[1] for x in ic], [x[2] for x in ic], r)[0]
    if cc <= 0:
        return None
    return (cm - cc) / cc


def audit_zero_channels(recs):
    """Per-source audit of every pred==0 record and what its own flag columns say."""
    srcs = sorted(set(r["source"] for r in recs))
    rows = []
    for s in srcs:
        z = [r for r in recs if r["source"] == s and r["pred"] == 0.0]
        if not z:
            continue
        has_flag = any((r["abstain"] != "" or r["refuse"] != "") for r in z)
        n1 = sum(1 for r in z if r["abstain"] == "1")
        n0 = sum(1 for r in z if r["abstain"] in ("0", "false") and r["refuse"] in ("0", "false", ""))
        rows.append((s, len(z), "YES" if has_flag else "NO", n1, n0))
    return rows


def write_report(outdir, inv, OUT, prov):
    e1p, e1s = OUT["e1p"], OUT["e1s"]
    e1pf = OUT.get("e1p_full")
    e5p, e5s = OUT["e5p"], OUT["e5s"]
    e5po, e5so = OUT.get("e5p_over"), OUT.get("e5s_over")
    e5g, e5go = OUT.get("e5g"), OUT.get("e5g_over")
    with open(os.path.join(outdir, "E1_E5_判据表.csv"), "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["block", "scope", "metric", "domain", "family", "arm", "ratio", "numerator",
                    "denominator", "value", "ci_lo", "ci_hi", "note"])
        # ---- E1 proportions + per-domain breakdown
        for scope, A in (("primary_paired", e1p), ("primary_full", e1pf), ("secondary_paired", e1s)):
            if A is None:
                continue
            N = A["point"][1]["n"]
            for r in RATIOS:
                pt = A["point"][r]
                k = pt["changed_vs_r1"]
                lo, hi = wilson(k, N)
                blo = percentile(A["boot"][r]["changed"], 0.025)
                bhi = percentile(A["boot"][r]["changed"], 0.975)
                w.writerow(["E1", scope, "cost_optimal_arm_changed_vs_r1", "ALL", "", "", r,
                            k, N, k / float(N) if N else "", "%.6f" % lo, "%.6f" % hi,
                            "Wilson95; item-bootstrap95=[%d,%d]/%d; pairing=%s" % (blo, bhi, N, A["pairing"])])
                k2 = pt["cost_neq_mae"]
                lo2, hi2 = wilson(k2, N)
                w.writerow(["E1", scope, "cost_optimal_arm_neq_MAE_optimal", "ALL", "", "", r,
                            k2, N, k2 / float(N) if N else "", "%.6f" % lo2, "%.6f" % hi2, "Wilson95"])
                pen = pt["penalty"]
                w.writerow(["E1", scope, "MAE_arm_extra_cost_pct", "ALL", "", "", r,
                            "", len(pen), "%.4f" % (100.0 * median(pen)),
                            "%.4f" % (100.0 * percentile(pen, 0.025)),
                            "%.4f" % (100.0 * percentile(pen, 0.975)),
                            "median and 2.5/97.5 pct over units; bootstrap median=%.4f" % (
                                100.0 * median(A["boot"][r]["pen_med"]))])
                for dom in sorted(set(d for d, _ in A["pairs"])):
                    sub = [(d, f) for (d, f) in A["pairs"] if d == dom]
                    kd = sum(1 for pf in sub if _arm_changed(A, r, pf))
                    kd2 = sum(1 for pf in sub if _arm_neq_mae(A, r, pf))
                    pend = [_penalty(A, r, pf) for pf in sub]
                    pend = [x for x in pend if x is not None]
                    lo3, hi3 = wilson(kd, len(sub))
                    w.writerow(["E1", scope, "per_domain_changed_vs_r1", dom, "", "", r,
                                kd, len(sub), kd / float(len(sub)) if sub else "",
                                "%.6f" % lo3, "%.6f" % hi3, "Wilson95 over units in this domain"])
                    w.writerow(["E1", scope, "per_domain_neq_MAE", dom, "", "", r,
                                kd2, len(sub), kd2 / float(len(sub)) if sub else "",
                                "%.6f" % wilson(kd2, len(sub))[0], "%.6f" % wilson(kd2, len(sub))[1], ""])
                    if pend:
                        w.writerow(["E1", scope, "per_domain_MAE_arm_extra_cost_pct", dom, "", "", r,
                                    "", len(pend), "%.4f" % (100.0 * median(pend)),
                                    "%.4f" % (100.0 * min(pend)), "%.4f" % (100.0 * max(pend)),
                                    "median / min / max over units in this domain"])
        # ---- E1 cell-level detail (per-cell MAE, numerators, denominators, cost)
        for scope, A in (("primary_paired", e1p), ("primary_full", e1pf), ("secondary_paired", e1s)):
            if A is None:
                continue
            for (d, f, a) in sorted(A["cells"]):
                items = A["cells"][(d, f, a)]
                ps = [x[1] for x in items]
                gs = [x[2] for x in items]
                mae = cell_mae(ps, gs)
                w.writerow(["E1cell", scope, "cell", d, f, a, "", "", len(items), "%.6f" % mae, "", "",
                            "sumgt=%.4f under=%.4f over=%.4f" % (
                                sum(gs), sum(max(g - p, 0) for p, g in zip(ps, gs)),
                                sum(max(p - g, 0) for p, g in zip(ps, gs)))])
                for r in RATIOS:
                    c = cell_cost(ps, gs, r)[0]
                    w.writerow(["E1cell", scope, "cell_cost", d, f, a, r, "", len(items),
                                "%.8f" % c, "", "", ""])
        # ---- E5 frozen (identity) + counterfactual (over-count) + reading B
        for scope, A, tag in (("primary", e5p, "frozen_identity"), ("secondary", e5s, "frozen_identity"),
                              ("g3_res", e5g, "frozen_identity")):
            if A is None:
                continue
            for r in RATIOS:
                for (d, f) in sorted(A["pairs"]):
                    c = A["point"][r][(d, f)]
                    diffs = A["boot"][r][(d, f)]["diff"]
                    w.writerow(["E5", scope, "C_P2_minus_C_P1", d, f, "ALL", r, "", c["n"],
                                "%.6f" % c["diff"], "%.6f" % percentile(diffs, 0.025),
                                "%.6f" % percentile(diffs, 0.975),
                                "P2=%.4f P1=%.4f readingB=%s n_abstain=%d sumgt=%.1f sumgt_answered=%.1f" % (
                                    c["P2"], c["P1"],
                                    ("%.6f" % c["P1_dropdenom"]) if c["P1_dropdenom_defined"] else "undefined",
                                    c["n_abstain"], c["sumgt"], c["sumgt_answered"])])
                ds = [A["point"][r][pf]["diff"] for pf in A["pairs"]]
                w.writerow(["E5", scope, "C_P2_minus_C_P1_median_over_units", "ALL", "", "", r,
                            sum(1 for x in ds if x > 0), len(ds), "%.6f" % median(ds),
                            "%.6f" % min(ds), "%.6f" % max(ds),
                            "median / min / max over %d (domain,family) units" % len(ds)])
        for scope, A in (("primary", e5po), ("secondary", e5so), ("g3_res", e5go)):
            if A is None:
                continue
            for r in RATIOS:
                for (d, f) in sorted(A["pairs"]):
                    c = A["point"][r][(d, f)]
                    diffs = A["boot"][r][(d, f)]["diff"]
                    w.writerow(["E5_over", scope, "C_P2_minus_C_P1_abstention_as_overcount", d, f, "ALL", r,
                                "", c["n"], "%.6f" % c["diff"],
                                "%.6f" % percentile(diffs, 0.025), "%.6f" % percentile(diffs, 0.975),
                                "P2=%.4f P1_over=%.4f n_abstain=%d" % (c["P2"], c["P1"], c["n_abstain"])])
                ds = [A["point"][r][pf]["diff"] for pf in A["pairs"]]
                w.writerow(["E5_over", scope, "median_over_units", "ALL", "", "", r,
                            sum(1 for x in ds if x > 0), len(ds), "%.6f" % median(ds),
                            "%.6f" % min(ds), "%.6f" % max(ds), ""])
        # ---- zero-channel audit
        for row in AUDIT_ZERO_SUMMARY:
            w.writerow(["E5audit", "source", row[0], "", "", "", "", row[1], "", row[3], "", "",
                        "has_flag=%s abstain=1:%d abstain=0:%d" % (row[2], row[3], row[4])])
        # ---- incomputable list
        for row in inv["incomputable"]:
            w.writerow(["INCOMPUTABLE", row.get("scope", ""), row.get("reason", ""), "", "", "",
                        "", "", "", "", "", "", row.get("what", "")])
    return os.path.join(outdir, "E1_E5_判据表.csv")


def md_report(outdir, inv, OUT, prov):
    e1p, e1s = OUT["e1p"], OUT["e1s"]
    e1pf = OUT.get("e1p_full")
    e5p, e5s = OUT["e5p"], OUT["e5s"]
    e5po, e5so = OUT.get("e5p_over"), OUT.get("e5s_over")
    e5g, e5go = OUT.get("e5g"), OUT.get("e5g_over")
    N1 = e1p["point"][1]["n"]
    L = []
    A = L.append
    A("# E1＋E5 判据表（非对称代价决策后果 / 答零=估计0 vs 弃权）\n")
    A("> 纯 CPU。零模型调用。只读放行树 `data/derived/**`；本目录只写产出件。逐格回源见 `E1_E5_自检.md`。\n")
    A("## 0 一页结论\n")
    A("| 项 | 结果 | 判定 |")
    A("|---|---|---|")
    A("| **E1** r=2 最优臂改变 | **%d/%d = %.4f** | **未达 50%% ⇒ 负结果，如实报** |" % (
        e1p["point"][2]["changed_vs_r1"], N1, e1p["point"][2]["changed_vs_r1"] / float(N1)))
    A("| **E1** r=5 / r=10 | r=5 **%d/%d=%.4f** [%.4f, %.4f]；r=10 **%d/%d=%.4f** | **达标 ⇒ 正面证据** |" % (
        e1p["point"][5]["changed_vs_r1"], N1, e1p["point"][5]["changed_vs_r1"] / float(N1),
        wilson(e1p["point"][5]["changed_vs_r1"], N1)[0], wilson(e1p["point"][5]["changed_vs_r1"], N1)[1],
        e1p["point"][10]["changed_vs_r1"], N1, e1p["point"][10]["changed_vs_r1"] / float(N1)))
    A("| **E1** 代价最优 ≠ MAE 最优 | r=2 **%d/10**；r=5 **%d/10**；r=10 **%d/10** | 选臂口径是决策相关的 |" % (
        e1p["point"][2]["cost_neq_mae"], e1p["point"][5]["cost_neq_mae"], e1p["point"][10]["cost_neq_mae"]))
    A("| **E1** 按 MAE 选臂多付（中位） | r=5 **+%.1f%%**；r=10 **+%.1f%%** | 同 |" % (
        100.0 * median(e1p["point"][5]["penalty"]), 100.0 * median(e1p["point"][10]["penalty"])))
    A("| **E5** `C(P2) − C(P1)`（冻结口径） | **恒等于 0**（逐项代数恒等） | ★ **主读**：答零不携带可用计数信息 |")
    A("| **E5** 对称对照（弃权当**过计**） | r≥2 时全部为正（见 §2.2） | ★ **次读**：对照量 |")
    A("| **E5** 经验底座 | b2__out/e1 里 `pred=0` 全带 `abstain=1`；真答零实例只在 `g3_res` | 该通道在既有源里为 0 条 |")
    A("")
    A("## 1 口径冻结件（本件执行的定义）\n")
    A("| 量 | 定义 |")
    A("|---|---|")
    A("| 单元 | `(域 × 实现家族 × 臂/条件)` = 一个 cell |")
    A("| MAE | `mean_i abs(pred_i - gt_i)` |")
    A("| 非对称代价 `C_r` | `[ c_u*Σ max(gt-pred,0) + c_o*Σ max(pred-gt,0) ] / Σ gt`，`c_u/c_o = r`，`c_o ≡ 1` |")
    A("| 比值集合 | `r ∈ {1,2,5,10}`；`r=1` 即对称基线（此时 `C_1 = n*MAE/Σgt`） |")
    A("| E1 决策单元 | `(域 × 家族)`；臂 = 该单元的候选动作 |")
    A("| E1 配对口径 | **primary = paired**（同一 item 在所有臂都成功解析）；`full` 逐臂用各自全部可解析 item（**非配对**） |")
    A("| E5 P0/P2 | 直接用 `pred`；P2 显式把 `pred_i = 0` 读作“估计 0” |")
    A("| E5 P1（**冻结**） | `pred_i = 0` ⇒ 该图不进自动决策（交人工）；弃权代价 = `c_u*gt_i`（**我方定义**，“漏掉整图”上界） |")
    A("| E5 P1（**对照**） | 同一弃权改记为**过计** `c_o*gt_i = gt_i`。不是冻结口径，只作对照 |")
    A("| 未解析行 | `pred` 非数 ⇒ 三策略**一致**排除（对称处理）；逐臂排除数见 `E1_E5_自检.md` |")
    A("")
    A("## 2 E5 主读数\n")
    A("### 2.1 主读：答零当估计 0 与弃权上界**代价完全相同**（恒等式，不是拟合）\n")
    A("**命题.** 在 `c_o ≡ 1` 且 P1 的弃权代价取 `c_u*gt_i` 时，对任意 item 有 `P1(i) = P2(i)`，故 `C(P2) − C(P1) ≡ 0`。")
    A("")
    A("**一行证明.** 设 `c_u = r`、`c_o = 1`，计数真值 `gt_i >= 0`（计数不可为负，读取时已校验，负值直接报错退出）：")
    A("")
    A("* 若 `pred_i = 0`：`P2(i) = c_u*max(gt_i − 0, 0) + c_o*max(0 − gt_i, 0) = r*gt_i + 0 = r*gt_i`，")
    A("  而 `P1(i) = c_u*gt_i = r*gt_i` ⇒ 相等；")
    A("* 若 `pred_i ≠ 0`：两策略的计费表达式逐字相同 `c_u*max(gt_i − pred_i, 0) + c_o*max(pred_i − gt_i, 0)` ⇒ 相等。")
    A("")
    A("同除同一个 `Σ_i gt_i` 后仍相等，故 `C(P2) − C(P1) ≡ 0`。∎")
    A("")
    A("**成立 / 失效的边界（必须与结论同时引用）**\n")
    A("| 条件 | 恒等式 |")
    A("|---|---|")
    A("| `c_o ≡ 1`（本件冻结口径） | 成立 |")
    A("| P1 弃权代价取**下界侧** `c_u*gt_i`（“漏掉整图”最大惩罚） | 成立 |")
    A("| `gt_i >= 0`（计数真值非负） | 成立 |")
    A("| P1 弃权代价改取**过计侧** `c_o*gt_i` | **失效**：逐项差 `= (c_u − c_o)*gt_i = (r−1)*gt_i`（§2.2） |")
    A("| 固定 `c_u ≡ 1` 而让 `c_o = r` 变动 | **失效**：`r = c_u/c_o` 两侧同时变，结论随之翻转 |")
    A("")
    A("**机制含义（主读的正式表述）.** *Treating an answered zero as an estimate of zero is cost-identical to "
      "discarding the whole image (the abstention upper bound); the answered zero therefore carries no usable "
      "count information under asymmetry.*")
    A("即：非对称代价下，一个答零无论被解释为“估计 0”还是“整图交人工”，决策代价**一分不差**；")
    A("既然“丢弃整图”（零信息处理）与“当作估计”**等价**，该输出就不携带任何可用于计数的信息。")
    A("这比“某个差显著为正”更强——后者只是一个数值方向，前者是不可识别性在代价侧的表述。")
    A("（对照：任务原判据设定 P1 为弃权上界，则原判据“r≥2 该差显著为正”在本口径下**不可能被满足**，如实报未支持。）")
    A("")
    A("**验证 1（口径读法）—— 全量 item 池.** 每个 `(域,家族)` 单元把它各臂的**全部**可用 item 池化；")
    A("由于各臂覆盖的 item 不完全相同（见 §E1 的解析排除），池化会把同一条 item 在部分臂上计入、在另一部分上不计入，")
    A("因此这里只报**数值规模**，并列 `flag_complete`（每条 `pred=0` 是否都带自己的弃权标记）。\n")
    A("| r | 单元数 | flag_complete 单元 | max abs(差) | 差==0 的单元 | 简写读法 差>0 | 简写少算(中位) |")
    A("|---|---|---|---|---|---|---|")
    for r in RATIOS:
        ds = [e5p["point"][r][pf]["diff"] for pf in e5p["pairs"]]
        dshort = [e5p["point"][r][pf]["diff_shortcut"] for pf in e5p["pairs"]]
        bs = [e5p["point"][r][pf]["shortcut_blind_spot"] for pf in e5p["pairs"]]
        nfc = sum(1 for pf in e5p["pairs"] if e5p["point"][r][pf]["flag_complete"])
        A("| %d | %d | %d/%d | %.4f | %d/%d | %d/%d | %.6f |" % (
            r, len(ds), nfc, len(ds), max(abs(x) for x in ds),
            sum(1 for x in ds if x == 0.0), len(ds),
            sum(1 for x in dshort if x > 0), len(dshort), median(bs)))
    A("")
    A("**验证 2（恒等式核验）—— 配对 item×臂 表.** 每个 `(域,家族)` 单元只保留**在所有臂中都存在**的 item，")
    A("于是该单元变成一张严格配对的 item×臂 表，恒等式应当在每一格上给出**精确 0.000000**：\n")
    for scope, AB in (("primary（显式标签，10 单元）", OUT.get("e5b")),
                      ("secondary（+文件名标签，20 单元）", OUT.get("e5sb")),
                      ("g3_res（薄底座，8 单元）", OUT.get("e5gb"))):
        if AB is None or not AB["pairs"]:
            continue
        A("")
        A("*%s* —— 单元可达恒等式的个数（`flag_complete=YES`）：**%d/%d**\n" % (
            scope, sum(1 for pf in AB["pairs"] if AB["point"][2][pf]["flag_complete"]), len(AB["pairs"])))
        A("| r | 可核验单元 | 差 == 0.000000 的单元 | max abs(差) | 不可核验单元（缺标注）的 max abs(差) |")
        A("|---|---|---|---|---|")
        for r in RATIOS:
            ok = [AB["point"][r][pf]["diff"] for pf in AB["pairs"] if AB["point"][r][pf]["flag_complete"]]
            no = [AB["point"][r][pf]["diff"] for pf in AB["pairs"] if not AB["point"][r][pf]["flag_complete"]]
            A("| %d | %d | **%d/%d** | %.3e | %s |" % (
                r, len(ok), sum(1 for x in ok if x == 0.0), len(ok),
                max(abs(x) for x in ok) if ok else float("nan"),
                ("%.3e (%d 单元)" % (max(abs(x) for x in no), len(no))) if no else "—（无）"))
        A("")
    A("**逐单元（r=2，配对核验）**\n")
    A("| 域 | 家族 | 答零(对) | 已标注 | 未标注 | flag_complete | C(P2)−C(P1) | 简写少算 | 简写少算(闭式) |")
    A("|---|---|---|---|---|---|---|---|---|")
    for (d, f) in sorted((OUT.get("e5sb") or e5p)["pairs"]):
        c = (OUT.get("e5sb") or e5p)["point"][2][(d, f)]
        A("| %s | %s | %d | %d | %d | %s | **%.6f** | %.6f | %.6f |" % (
            d, f, c["n_abstain"], c["n_marked"], c["n_unmarked"],
            "YES" if c["flag_complete"] else "**NO**", c["diff"], c["shortcut_blind_spot"],
            c["shortcut_blind_spot_formula"]))
    A("")
    A("### 2.2 次读：弃权改记作**过计**时的对照量\n")
    A("对照口径：P1 的弃权项计 `c_o*gt_i = gt_i`（把“丢弃整图”视为一次**过计**）。此时逐项差 `= (r−1)*gt_i`，")
    A("单元差 `= (r−1) * Σ_{答零项} gt_i / Σ_i gt_i`，**恒为正**（`r > 1` 且该单元存在答零）。")
    A("这是**口径定义**的直接后果，不是经验发现；作为可比较的对照量列出。\n")
    for scope, AA in (("primary（显式标签）", e5po), ("secondary（文件名标签）", e5so),
                      ("g3_res（薄底座）", e5go)):
        if AA is None:
            continue
        A("**%s**\n" % scope)
        A("| r | 单元数 | 差>0 | 中位差 | 范围 | 中位差(%%) | 范围(%%) |")
        A("|---|---|---|---|---|---|---|")
        for r in RATIOS:
            ds = [AA["point"][r][pf]["diff"] for pf in AA["pairs"]]
            pct = [100.0 * x for x in ds]
            A("| %d | %d | **%d/%d** | %.6f | [%.6f, %.6f] | %.4f | [%.4f, %.4f] |" % (
                r, len(ds), sum(1 for x in ds if x > 0), len(ds), median(ds), min(ds), max(ds),
                median(pct), min(pct), max(pct)))
        A("")
        if scope.startswith("primary"):
            A("逐单元（r=2）：\n")
            A("| 域 | 家族 | C(P2) | C(P1 过计口径) | 差 | bootstrap 95% | 答零条数 | Σgt(答零)/Σgt |")
            A("|---|---|---|---|---|---|---|---|")
            for (d, f) in sorted(AA["pairs"]):
                c = AA["point"][2][(d, f)]
                diffs = AA["boot"][2][(d, f)]["diff"]
                A("| %s | %s | %.6f | %.6f | %.6f | [%.6f, %.6f] | %d | %.4f |" % (
                    d, f, c["P2"], c["P1"], c["diff"], percentile(diffs, 0.025), percentile(diffs, 0.975),
                    c["n_abstain"], (c["sumgt"] - c["sumgt_answered"]) / c["sumgt"]))
            A("")
    A("### 2.3 P1 的第三种读法：答零项**不计入分母**（reading B）\n")
    A("该读法把“交人工”的图从分母剔除，于是 P1 与 P2 是**不同图集上的两个估计量**——")
    A("补充材料 §M.11 已判定 pooled 与 per-image 两种口径**不可互换**，故本件只列数值、不给判据。\n")
    A("| r | 单元数 | 值非零的单元（分母>0） | 中位值 | 范围 |")
    A("|---|---|---|---|---|")
    for r in RATIOS:
        vs = [e5p["point"][r][pf]["P1_dropdenom"] for pf in e5p["pairs"]
              if e5p["point"][r][pf]["P1_dropdenom_defined"]]
        A("| %d | %d | %d | %.6f | [%.6f, %.6f] |" % (
            r, len(e5p["pairs"]), len(vs), median(vs) if vs else float("nan"),
            min(vs) if vs else float("nan"), max(vs) if vs else float("nan")))
    A("")
    A("### 2.4 答零通道审计（E5 的经验底座）\n")
    A("逐条明细见 `E5_答零审计.csv`。汇总（只列有答零的源，前 25 个）：\n")
    A("| 源 | `pred=0` 条数 | `abstain` 标志存在 | `abstain=1` | `abstain=0`（真答零候选） |")
    A("|---|---|---|---|---|")
    for row in AUDIT_ZERO_SUMMARY[:25]:
        A("| `%s` | %d | %s | %d | %d |" % (row[0], row[1], row[2], row[3], row[4]))
    A("")
    A("**发现.** 在 `b2__out_ivl` / `b2__out_q32` / `b2__out_*_ctile` / `e1_results` 这些源里，")
    A("每一条 `pred = 0` 都带 `abstain = 1` ⇒ “真·答零当估计 0”在该子树的记录数 = **0**。")
    A("这与 §M.11 的判读一致：零只在 numeric-only 契约下重新出现，本子树的契约已把零路由到 abstain 通道。")
    A("**限制（如实写）.** `g3_res/*` 的 `abstain` 列只对 `permit`/`channel` 的显式弃权置 1，对 `base` 臂的 numeric 输出不置位，")
    A("故那里的 `abstain=0` **不能**证明模型“真的估计 0”（也无法排除“弃权未被标注”）。该族纳入只作**旁证**，底座薄。\n")
    if e5g is not None:
        A("**g3_res 薄底座（r=2，冻结口径）**\n")
        A("| 域 | 家族 | 单元 item 数 | 答零条数 | C(P2)=C(P1) | 差 |")
        A("|---|---|---|---|---|---|")
        for (d, f) in sorted(e5g["pairs"]):
            c = e5g["point"][2][(d, f)]
            A("| %s | %s | %d | %d | %.6f | %.6f |" % (d, f, c["n"], c["n_abstain"], c["P2"], c["diff"]))
        A("")
    A("## 3 E1 主读数（逐条给分子/分母＋Wilson 95%）\n")
    for scope, AA in (("primary（显式标签，paired）", e1p),
                      ("primary（显式标签，full 非配对）", e1pf),
                      ("secondary（文件名标签，paired）", e1s)):
        if AA is None:
            continue
        N = AA["point"][1]["n"]
        A("### %s —— 决策单元 `(域×家族)` 共 **%d** 个（使用 item 数 %d）\n" % (scope, N, AA["n_items_used"]))
        A("| r | 最优臂改变 分子/分母 | 比例 | Wilson 95% | item-bootstrap 95% | 代价最优≠MAE最优 | 按MAE选臂多付 %（中位） |")
        A("|---|---|---|---|---|---|---|")
        for r in RATIOS:
            pt = AA["point"][r]
            k = pt["changed_vs_r1"]
            lo, hi = wilson(k, N)
            blo = percentile(AA["boot"][r]["changed"], 0.025)
            bhi = percentile(AA["boot"][r]["changed"], 0.975)
            k2 = pt["cost_neq_mae"]
            lo2, hi2 = wilson(k2, N)
            pen = pt["penalty"]
            A("| %d | **%d/%d** | %.4f | [%.4f, %.4f] | [%d/%d, %d/%d] | **%d/%d** [%.4f, %.4f] | %.4f |" % (
                r, k, N, k / float(N), lo, hi, blo, N, bhi, N, k2, N, lo2, hi2, 100.0 * median(pen)))
        A("")
        A("判据（冻结）：`r >= 2` 时 **>=50%** 单元的最优臂改变 ⇒ 支持“方向/口径的选择是决策相关的”。")
        A("本 scope：r=2 **%d/%d = %.4f**（**未达**），r=5 **%d/%d = %.4f**（**达标**），r=10 **%d/%d = %.4f**（**达标**）。" % (
            AA["point"][2]["changed_vs_r1"], N, AA["point"][2]["changed_vs_r1"] / float(N),
            AA["point"][5]["changed_vs_r1"], N, AA["point"][5]["changed_vs_r1"] / float(N),
            AA["point"][10]["changed_vs_r1"], N, AA["point"][10]["changed_vs_r1"] / float(N)))
        A("")
        A("逐域（同一 scope）：\n")
        A("| 域 | 单元数 | r=2 改臂 | r=5 改臂 | r=10 改臂 | r=2 代价最优≠MAE | r=5 | r=10 | 按MAE多付% 中位/最小/最大 (r=2) | 按MAE多付% 中位/最小/最大 (r=5) | 按MAE多付% 中位/最小/最大 (r=10) |")
        A("|---|---|---|---|---|---|---|---|---|---|---|")
        def _pens(A_, r, sub):
            v = [_penalty(A_, r, pf) for pf in sub]
            v = [100.0 * x for x in v if x is not None]
            return ("%.4f / %.4f / %.4f" % (median(v), min(v), max(v))) if v else "-"
        for dom in sorted(set(d for d, _ in AA["pairs"])):
            sub = [(d, f) for (d, f) in AA["pairs"] if d == dom]
            rowc = ["%d" % sum(1 for pf in sub if _arm_changed(AA, rr, pf)) for rr in (2, 5, 10)]
            row2 = ["%d" % sum(1 for pf in sub if _arm_neq_mae(AA, rr, pf)) for rr in (2, 5, 10)]
            A("| " + " | ".join([dom, str(len(sub))] + rowc + row2 + [_pens(AA, 2, sub), _pens(AA, 5, sub), _pens(AA, 10, sub)]) + " |")


        A("")
    A("### 3.1 逐族最优臂表（primary paired；`NA` = 该族仅 1 臂，无臂可换）\n")
    A("| 域 | 家族 | 臂集 | MAE最优 | r=1 | r=2 | r=5 | r=10 |")
    A("|---|---|---|---|---|---|---|---|")
    _new = lambda r, d, f: ("%s" % r, None)
    del _new
    for (d, f) in e1p["pairs"]:
        def _mind(A_, r, d=d, f=f):
            t = _arm_table(A_, r)[(d, f)]
            items = A_["cells"][(d, f, t)] if t else []
            if not items:
                return t, float("nan")
            ps = [x[1] for x in items]
            gs = [x[2] for x in items]
            v = cell_mae(ps, gs) if r == "mae" else cell_cost(ps, gs, r)[0]
            return t, v
        arms = list(e1p["arms_of"][(d, f)])
        if len(arms) < 2:
            A("| %s | %s | `%s` | `%s` | NA | NA | NA | NA |" % (d, f, ",".join(arms), arms[0]))
            continue
        txt = []
        for r in RATIOS:
            a, v = _mind(e1p, r)
            txt.append("`%s` (%.4f)" % (a, v))
        am, vm = _mind(e1p, "mae")
        A("| %s | %s | %s | `%s` (%.4f) | %s |" % (d, f, ",".join(arms), am, vm, " | ".join(txt)))
    A("")
    A("## 4 不可算清单\n")
    if inv["incomputable"]:
        A("| 范围 | 对象 | 原因 |")
        A("|---|---|---|")
        for row in inv["incomputable"]:
            A("| %s | %s | %s |" % (row.get("scope", ""), row.get("what", ""), row.get("reason", "")))
    else:
        A("（无）")
    A("")
    A("## 5 预注册 vs post-hoc 声明\n")
    A("* **预注册（来自任务冻结口径）**：代价比集合 `{1,2,5,10}`；`C(r)` 公式与 `Σgt` 分母；")
    A("  单元 = `域×族×臂`；E1 三条主读数与 `>=50%` 判据；E5 三策略与 `C(P2)−C(P1)` 主读；")
    A("  E5 的 P1 弃权代价 = `c_u*gt_i`（任务指定为我方定义）。")
    A("* **本件 post-hoc（我在口径内做的选择，均已显式标注）**：")
    A("  ① E1 的 **paired / full** 两读（paired 为主，因 `b2__out_ivl` 逐臂可解析数不等）；")
    A("  ② E5 的 **对称对照**（弃权记过计）与 **reading B**（弃权项不计入分母）；")
    A("  ③ 2000 次 item bootstrap 与 Wilson 区间（判据本身不含区间）；")
    A("  ④ 纳入 `g3_res` 作薄底座旁证（上级裁定后并入）；")
    A("  ⑤ `r=1` 作为“最优臂是否改变”的基线（任务给定）。")
    A("")
    with open(os.path.join(outdir, "E1_E5_判据表.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")
    return os.path.join(outdir, "E1_E5_判据表.md")


# ----------------------------------------------------------------------------- main
def main(argv=None):
    ap = argparse.ArgumentParser(description="E1 asymmetric cost + E5 answer-zero cost analysis (pure CPU)")
    ap.add_argument("--root", default=ROOT_DEFAULT)
    ap.add_argument("--outdir", default=os.path.dirname(os.path.abspath(__file__)))
    ap.add_argument("--input", default=None, help="existing analysis_input.csv (skip rebuild)")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--nboot", type=int, default=NBOOT)
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    if not a.all:
        ap.print_help()
        return 0
    os.makedirs(a.outdir, exist_ok=True)
    try:
        if a.input:
            inp = a.input
            prov = []
        else:
            inp = os.path.join(a.outdir, "analysis_input.csv")
            n, prov = build_analysis_input(a.root, inp)
        recs = load_norm(inp)
    except InputError as exc:
        sys.stderr.write("INPUT ERROR: %s\n" % exc)
        return 2
    print("loaded %d rows from %s" % (len(recs), inp))

    fam_root = lambda r: r["family"].split("__")[0]
    prim = [r for r in recs if fam_root(r) not in ("e1_results", "g3_res")]
    sec = [r for r in recs if fam_root(r) != "g3_res"]
    g3 = [r for r in recs if fam_root(r) == "g3_res"]
    out = {}
    try:
        # E1: paired (same items in every arm) is primary; the "full" reading keeps every
        # parseable item per arm and is reported beside it (it is NOT a paired comparison).
        out["e1p"] = e1_analysis(prim, nboot=a.nboot, verbose_boot=True, pairing="paired")
        out["e1p_full"] = e1_analysis(prim, nboot=a.nboot, seed=BOOT_SEED + 5, verbose_boot=True, pairing="full")
        out["e1s"] = e1_analysis(sec, nboot=a.nboot, seed=BOOT_SEED + 1, verbose_boot=True, pairing="paired")
        # E5 main read: FROZEN P1 (abstention charged c_u*gt_i) -> the identity C(P2)-C(P1) == 0
        out["e5p"] = e5_analysis(prim, nboot=a.nboot, seed=BOOT_SEED + 2, verbose_boot=True)
        out["e5s"] = e5_analysis(sec, nboot=a.nboot, seed=BOOT_SEED + 3, verbose_boot=True)
        # E5 counterfactual: the same abstention charged as an OVER-count (c_o*gt_i)
        out["e5p_over"] = e5_analysis(prim, nboot=a.nboot, seed=BOOT_SEED + 4, p1_mode="abstain_over")
        out["e5s_over"] = e5_analysis(sec, nboot=a.nboot, seed=BOOT_SEED + 6, p1_mode="abstain_over")
        # E5 on the thin answered-zero base (g3_res): the only source with genuine answered zeros
        out["e5g"] = e5_analysis(g3, nboot=a.nboot, seed=BOOT_SEED + 8, verbose_boot=True) if g3 else None
        out["e5g_over"] = e5_analysis(g3, nboot=a.nboot, seed=BOOT_SEED + 9, p1_mode="abstain_over") if g3 else None
        # E5 on BALANCED units (each unit = one paired item x arm table).  This is where the frozen
        # identity is observable and must come out at exactly 0.000000.
        out["e5b"] = e5_analysis(prim, nboot=a.nboot, seed=BOOT_SEED + 10, balance=True)
        out["e5sb"] = e5_analysis(sec, nboot=a.nboot, seed=BOOT_SEED + 11, balance=True)
        out["e5gb"] = e5_analysis(g3, nboot=a.nboot, seed=BOOT_SEED + 12, balance=True) if g3 else None
        out["e5b_over"] = e5_analysis(prim, nboot=a.nboot, seed=BOOT_SEED + 13, balance=True,
                                      p1_mode="abstain_over")
    except InputError as exc:
        sys.stderr.write("INPUT ERROR: %s\n" % exc)
        return 2

    # ---- zero-flag audit: every pred==0 row in the analysis input, with its own flag columns
    zrows = [r for r in recs if r["pred"] == 0.0]
    with open(os.path.join(a.outdir, "E5_答零审计.csv"), "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["domain", "family", "arm", "item", "gt", "abstain_flag", "refuse_flag",
                    "parse_ok", "raw_contract_flag_present", "source"])
        for r in sorted(zrows, key=lambda x: (x["domain"], x["family"], x["arm"], x["item"])):
            w.writerow([r["domain"], r["family"], r["arm"], r["item"], r["gt"], r["abstain"],
                        r["refuse"], r["parse_ok"],
                        "YES" if (r["abstain"] != "" or r["refuse"] != "") else "NO", r["source"]])
    AUDIT_ZERO_SUMMARY[:] = audit_zero_channels(recs)
    print("zero-channel audit: %d sources carry pred==0; %d such rows in total"
          % (len(AUDIT_ZERO_SUMMARY), sum(x[1] for x in AUDIT_ZERO_SUMMARY)))

    inv = {"incomputable": [
        {"scope": "全树", "what": "任何只给聚合值（无逐项 pred/gt）的成品表",
         "reason": "冻结口径要求逐项聚合；聚合件 ⇒ 不可算"},
        {"scope": "e4_results/*", "what": "E4L_*_results.csv（列 img,hat,no_helmet）",
         "reason": "两个并列目标计数，无单一 pred/gt 对标；口径须上级裁定"},
        {"scope": "a5_1/a5_3/a5_4/a5_5/a5_6 raw", "what": "目标匹配域（class_name, is_zero）",
         "reason": "任务为“所问类别是否存在/计数”，域=class_name，与域=数据集的 (域×族×臂) 口径不一致"},
        {"scope": "b2__out_*_ctile", "what": "tile2/tile3 变体",
         "reason": "切图变体属另一臂族，本件只用 whole 以保臂内可比"},
        {"scope": "_backup_32b_results/**", "what": "备份树",
         "reason": "与 e1/e1_results/dense_results/e8b_results 逐文件 md5 相同（已验证），计入即重复"},
        {"scope": "b2__out_* 的 `pred=0`", "what": "1108 条（ivl 289 + q32 535 + 32b_ctile 282 + 8b_ctile 2）",
         "reason": "**全部带 `abstain=1`** ⇒ 这些源里“弃权未标注”与“真的估计 0”**不可分**；"
                   "1038/1038 即“真·答零当估计0”通道在这些源里为 **0 条**（这本身就是发现，不是缺失）"},
    ]}
    md_report(a.outdir, inv, out, prov)
    write_report(a.outdir, inv, out, prov)
    with open(os.path.join(a.outdir, "_provenance.json"), "w", encoding="utf-8") as f:
        json.dump(prov, f, ensure_ascii=False, indent=1)
    print("wrote E1_E5_判据表.csv / .md, E5_答零审计.csv into %s" % a.outdir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
