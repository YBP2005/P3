#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v0589 fix: give every cell of the M.21.9 table a Wilson 95% interval.

Why: the M.40 true-zero table states the paper's convention -- "Every cell carries a
Wilson 95% interval, the zero cells and the non-zero cells alike ... quoting `97.1%` bare
while quoting `0.0%` with a bound would imply the two sides were held to different
standards".  The M.21.9 table (four builds x two external pools, n = 150 each) prints bare
rates, so the paper asserts a convention it does not apply everywhere.  This script reads
the printed rates, recovers the integer counts behind them, asserts the round-trip, and
writes the Wilson interval into each cell -- no number here is typed by hand.

Usage:
  python _v0589_fix_m219_wilson.py --check      # verify the file agrees with the script
  python _v0589_fix_m219_wilson.py --selftest   # negative controls
  python _v0589_fix_m219_wilson.py --apply      # patch the supplement
"""
import argparse
import math
import sys
from pathlib import Path

SUPP = Path(r"<WORKDIR>\PaperB\PaperB_英文补充材料_PR_20260919.md")
N_PER_POOL = 150
Z = 1.959963984540054

# build, base S-1, base S-2, permit S-1, permit S-2, channel S-1, channel S-2
ROWS = [
    ("Qwen3-VL-32B-Instruct", "100.0", "99.3", "1.3", "97.3", "100", "100"),
    ("InternVL3.5-8B",        "98.0", "100.0", "0",   "0",   "100", "100"),
    ("Phi-3.5-Vision",        "99.3", "65.3",  "0",   "0",   "100", "100"),
    ("gemma-3-12b",           "34.0", "88.7",  "0",   "0",   "100", "99.3"),
]
CELLS = ("base_s1", "base_s2", "permit_s1", "permit_s2", "channel_s1", "channel_s2")
BOLD = {("Qwen3-VL-32B-Instruct", "permit_s2")}


def wilson(k, n, z=Z):
    if n <= 0:
        raise ValueError("n must be positive")
    if not (0 <= k <= n):
        raise ValueError("k out of range")
    p = k / n
    denom = 1.0 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = (z / denom) * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return max(0.0, centre - half) * 100.0, min(1.0, centre + half) * 100.0


def count_from_rate(printed, n=N_PER_POOL):
    rate = float(printed)
    k = int(round(rate / 100.0 * n))
    if abs(k / n * 100.0 - rate) > 0.051:
        raise AssertionError(
            "printed rate %s%% is not an integer count on n=%d (nearest %d -> %.2f%%)"
            % (printed, n, k, k / n * 100.0))
    return k


def cell(printed, tag, build):
    k = count_from_rate(printed)
    lo, hi = wilson(k, N_PER_POOL)
    val = "%s%%" % printed
    if (build, tag) in BOLD:
        val = "**%s**" % val
    return "%s [%.2f, %.2f]" % (val, lo, hi), k


def new_row(row):
    b = row[0]
    parts = [cell(v, t, b)[0] for v, t in zip(row[1:], CELLS)]
    return "| %s | %s | %s | %s / %s | %s / %s |" % (
        b, parts[0], parts[1], parts[2], parts[3], parts[4], parts[5])


def old_row(row):
    b, b1, b2, p1, p2, c1, c2 = row
    p2 = ("**%s%%**" % p2) if (b, "permit_s2") in BOLD else ("%s%%" % p2)
    return "| %s | %s%% | %s%% | %s%% / %s | %s%% / %s%% |" % (b, b1, b2, p1, p2, c1, c2)


NOTE = ("**Each cell carries a Wilson 95% interval on its own $n$ (150 per pool), the same "
        "convention as §M.40** — the intervals are quoted on the saturated cells as well as on "
        "the zero cells, so that a cell reading `0%` is not held to a stricter standard than one "
        "reading `100%`, and each is computed from the integer count behind the printed rate. "
        "Reproduction: `m219_wilson_bounds.py`.")


def m219_block(text):
    """The M.21.9 section only -- these builds appear in other tables too."""
    start = text.index("#### M.21.9")
    nxt = text.find("\n#### ", start + 1)
    return text[start:nxt if nxt != -1 else len(text)]


def check():
    text = SUPP.read_text(encoding="utf-8")
    block = m219_block(text)
    fails = []
    for row in ROWS:
        want = new_row(row)
        got = [ln for ln in block.splitlines() if ln.startswith("| %s |" % row[0])]
        if len(got) != 1:
            fails.append("%s: expected 1 row in M.21.9, found %d" % (row[0], len(got)))
        elif got[0].strip() != want.strip():
            fails.append("%s: row mismatch\n  want %s\n  got  %s" % (row[0], want, got[0]))
    if NOTE not in block:
        fails.append("convention note missing from M.21.9")
    return fails


def selftest():
    ctl = []
    lo, hi = wilson(0, 150)
    ctl.append(("wilson(0,150) keeps a non-zero upper bound (%.2f)" % hi, lo < 0.05 and hi > 2.0))
    try:
        count_from_rate("97.1")
        ctl.append(("non-integral rate on n=150 rejected", False))
    except AssertionError:
        ctl.append(("non-integral rate on n=150 rejected", True))
    ctl.append(("Qwen permit S-2 recovers 146/150", count_from_rate("97.3") == 146))
    ctl.append(("gemma base S-1 recovers 51/150", count_from_rate("34.0") == 51))
    ctl.append(("bare-rate row is rejected by the checker",
                old_row(ROWS[3]) != new_row(ROWS[3])))
    ok = True
    for name, passed in ctl:
        print("  [%s] %s" % ("PASS" if passed else "FAIL", name))
        ok = ok and passed
    print("SELFTEST: %s" % ("PASS" if ok else "FAIL"))
    return ok


def apply():
    text = SUPP.read_text(encoding="utf-8")
    for row in ROWS:
        o, n = old_row(row), new_row(row)
        if text.count(o) != 1:
            print("ABORT: row not found exactly once:\n%s" % o)
            return 1
        text = text.replace(o, n)
    anchor = new_row(ROWS[-1]) + "\n"
    if NOTE not in text:
        text = text.replace(anchor, anchor + "\n" + NOTE + "\n", 1)
    SUPP.write_text(text, encoding="utf-8")
    print("patched %d rows + note" % len(ROWS))
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        sys.exit(0 if selftest() else 1)
    if a.apply:
        sys.exit(apply())
    if a.check:
        f = check()
        for x in f:
            print("MISSING: %s" % x)
        print("M21.9 WILSON CHECK: %s" % ("PASS" if not f else "FAIL"))
        sys.exit(0 if not f else 1)
    ap.print_help()
