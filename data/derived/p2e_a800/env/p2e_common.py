# -*- coding: utf-8 -*-
"""p2e_common.py —— P2-E 共用件（判据、估计器、单元资格、排序统计、路径与 md5）。

★ 估计器**逐字**沿用放行件 `code/analysis/a39_unit_calib_heldout.py` L183–184：
    dev(pairs) = 100 * (Σpred − Σgt) / Σgt        （在该档的**配对 item 交集**上算）
  span = 该 knob 各档 dev 的 max − min（与 §M.43 表里 343.55 = 245.1 − (−98.5) 同一算法）。
★ 单元资格沿用 A39 规则：**档位 ≥3 且各档 item 交集 ≥ MIN_ITEMS**（不放宽）。
★ 排序统计：Spearman（与 `eb2_equalcount36.py` 同口径）；判据阈值在判据件里。
"""
import csv
import hashlib
import io
import json
import os

MIN_ITEMS = 20
HERE = os.path.dirname(os.path.abspath(__file__))
CRIT = os.path.join(HERE, 'p2e_criteria_frozen.json')
OUT = os.path.join(HERE, 'out')


def load_csv(p):
    return list(csv.DictReader(io.open(p, encoding='utf-8-sig', newline='')))


def fnum(x):
    x = (x or '').strip()
    if x == '':
        return None
    try:
        return float(x)
    except Exception:
        return None


def md5f(p):
    h = hashlib.md5()
    with io.open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def dev(pairs):
    """pairs = [(gt, pred), ...] —— 逐字复刻 a39_unit_calib_heldout.py 的 dev。"""
    sg = sum(g for g, _ in pairs)
    if not sg:
        return None
    return 100.0 * (sum(p for _, p in pairs) - sg) / sg


def span_of(vals):
    v = [x for x in vals if x is not None]
    return (max(v) - min(v)) if len(v) >= 2 else None


def levels_from(by_level):
    """by_level: {level_label: {item: (gt, pred)}} -> 合格则返回 (levels, common_keys)，否则 None。"""
    lv = sorted(by_level)
    if len(lv) < 3:
        return None
    common = set.intersection(*[set(by_level[s]) for s in lv])
    if len(common) < MIN_ITEMS:
        return None
    return lv, sorted(common)


def level_devs(by_level):
    """→ (labels, [dev per level], common_keys) 或 None（不合格）。**交集口径**（A39 校准用）。"""
    r = levels_from(by_level)
    if not r:
        return None
    lv, keys = r
    return lv, [dev([by_level[s][k] for k in keys]) for s in lv], keys


def level_devs_pooled(by_level, min_items=20, keep_order=False):
    """★ **§M.43 口径**：每档在**该档自己的 item 集合**上池化算 dev，不取交集。

    2026-10-02 由 G0 自检实测锁定：对机上 G6 的 `g56_tile.csv` / `g56_budget.csv`，
    本函数逐档复现 §M.43 印值（−51.5/−55.2/−47.1/−44.5/−40.6 与 −54.0/−55.5/−74.2/−77.2/−85.6），
    而交集口径给出 −7.2/−40.9/… 与 −37.4/…（n 被压到 118/71）⇒ **交集口径不是印值用的口径**。
    （A39 的 36-unit **校准**工作用交集；M.43 的 rescan ρ 不用。两者不可混。）
    """
    lv = list(by_level) if keep_order else sorted(by_level)
    if len(lv) < 3:
        return None
    vals, ns = [], []
    for s in lv:
        ps = list(by_level[s].values())
        if len(ps) < min_items:
            return None
        vals.append(dev(ps))
        ns.append(len(ps))
    return lv, vals, ns


def spearman(xs, ys):
    n = len(xs)
    if n < 2:
        return None

    def rank(v):
        order = sorted(range(n), key=lambda i: v[i])
        r = [0.0] * n
        i = 0
        while i < n:
            j = i
            while j + 1 < n and v[order[j + 1]] == v[order[i]]:
                j += 1
            avg = (i + j) / 2.0 + 1
            for k in range(i, j + 1):
                r[order[k]] = avg
            i = j + 1
        return r

    rx, ry = rank(xs), rank(ys)
    mx, my = sum(rx) / n, sum(ry) / n
    num = sum((rx[i] - mx) * (ry[i] - my) for i in range(n))
    dx = sum((rx[i] - mx) ** 2 for i in range(n)) ** 0.5
    dy = sum((ry[i] - my) ** 2 for i in range(n)) ** 0.5
    return num / (dx * dy) if dx and dy else None


def criteria():
    return json.load(io.open(CRIT, encoding='utf-8'))


def w(path, header, rows):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with io.open(path, 'w', encoding='utf-8', newline='') as f:
        wr = csv.writer(f)
        wr.writerow(header)
        wr.writerows(rows)
    return path
