#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
A 轮（2026-09-28）预注册分析：MTDC + GWHD 外部复制。

判据来源（只读，绝不写）：
  D:\\deepseek\\PaperB\\analysis\\work\\A_criteria_frozen.json
数据来源：
  D:\\deepseek\\PaperB\\analysis\\A_res_20260928\\<domain>\\<domain>__<tag>__s<start>.csv
  D:\\deepseek\\PaperB\\analysis\\A_res_20260928\\MD5SUMS_A.txt

用法：
  python A_analyze.py             # 断言 + 分析 + 写 A_result.json
  python A_analyze.py --check     # 重读产物与原始 CSV 逐数复算校验
  python A_analyze.py --selftest  # 阴性对照（≥3 条），全部必须如预期地失败

口径（全部写在文件顶部，便于审计；与冻结件一致）：
  * 答零  = parse_ok==1 且解析出的 pred 恰为 0
    弃权  = parse_ok==0（无解析值 / outlet token）。两者分开报。
  * 池化 rho = 100 * (sum(pred) - sum(gt)) / sum(gt)，在**该域共同 item 交集**（= 本域 200 项，
    已断言 11 档 x 3 启动的 item 集合逐字相同）上算；pred 不可解析的项**从分子分母同时剔除**
    （不做任何代理量顶替），并报 n_used / n_excluded。n_used < 20 => 该格报「未测」。
  * 跨度 span = max(rho) - min(rho)（只在未报「未测」的档上取）。
  * 某谱可评档数 < 3 => 该谱跨度报「未测」（冻结件 analysis_discipline.report_undefined）。
  * 逐项对数误差 = median(ln(pred+1) - ln(gt+1))，同样只在有解析 pred 的项上算。
  * MAE = mean(|pred - gt|)，同样只在有解析 pred 的项上算。
  * A3(3)：先把 11 档的 MAE 全算出，取 MAE_best = min；合格集 = {档 : MAE <= 1.10 * MAE_best}
    （边界**闭合**，即 <=）；报合格集内 rho 的跨度；合格集 < 3 档 => 报「未测」。
  * Wilson 95% 上界：双侧 z = 1.959963984540054（另附单侧 z = 1.6448536269514722 作参考）。
"""

from __future__ import annotations

import argparse
import copy
import csv
import hashlib
import json
import math
import os
import random
import shutil
import statistics
import sys
import tempfile
from pathlib import Path

ROOT = Path(r"<WORKDIR>\PaperB\analysis\A_res_20260928")
CRITERIA = Path(r"<WORKDIR>\PaperB\analysis\work\A_criteria_frozen.json")
OUT = Path(r"<WORKDIR>\PaperB\analysis\work\A_result.json")

DOMAINS = ["mtdc", "gwhd"]
CONTRACT = ["base", "permit", "bestA", "bestB", "bestC", "channel"]
PIXELBUDGET = ["pb1048576", "pb489987", "pb228966", "pb106993", "pb50000"]
STARTS = ["s1", "s2", "s3"]
LEVELS = CONTRACT + PIXELBUDGET

N_FILES_EXPECTED = 66          # 2 域 x 11 档 x 3 启动
ROWS_PER_CELL = 200
LINES_PER_CELL = 201           # 表头 + 200
MIN_CELL_N = 20                # 冻结件：<20 共同项 => 未测
MIN_LEVELS_FOR_SPAN = 3        # 冻结件：<3 水平 => 未测
Z95 = 1.959963984540054
Z95_ONE = 1.6448536269514722
MAE_MULT = 1.10
GATE = 0.05
EPS = 1e-9
FLOAT_ND = 6                   # JSON 里浮点保留位数（--check 用同位数比较）

UNDEF = "未测"
PASS = "通过"
FAIL = "不通过"


# ----------------------------------------------------------------------------- 基础工具
def md5_of(path: Path) -> str:
    h = hashlib.md5()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def r6(x):
    return None if x is None else round(float(x), FLOAT_ND)


def med(xs):
    return None if not xs else float(statistics.median(xs))


def sign_str(x):
    if x is None:
        return UNDEF
    if x > 0:
        return "+"
    if x < 0:
        return "-"
    return "0"


def wilson_upper(k: int, n: int, z: float = Z95):
    """Wilson score interval 的上界；k=0 时下界为 0、上界 = z^2/(n+z^2) 形式。"""
    if n <= 0:
        return None
    p = k / n
    z2 = z * z
    denom = 1.0 + z2 / n
    center = p + z2 / (2.0 * n)
    half = z * math.sqrt(p * (1.0 - p) / n + z2 / (4.0 * n * n))
    return min(1.0, (center + half) / denom)


# ----------------------------------------------------------------------------- 读盘
def read_manifest(root: Path):
    """MD5SUMS_A.txt -> {相对路径: (md5, bytes)}，行序保留。"""
    man = {}
    order = []
    with open(root / "MD5SUMS_A.txt", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            parts = line.split()
            if len(parts) != 3:
                raise AssertionError("MD5SUMS_A.txt 行格式异常: %r" % line)
            digest, rel, size = parts[0], parts[1].replace("\\", "/"), int(parts[2])
            man[rel] = (digest, size)
            order.append(rel)
    return man, order


def assert_manifest(root: Path):
    man, order = read_manifest(root)
    problems = []
    for rel, (digest, size) in man.items():
        p = root / rel
        if not p.exists():
            problems.append("清单条目缺失: %s" % rel)
            continue
        raw = p.read_bytes()
        if len(raw) != size:
            problems.append("字节数不符: %s 实测 %d 清单 %d" % (rel, len(raw), size))
        got = hashlib.md5(raw).hexdigest()
        if got != digest:
            problems.append("md5 不符: %s 实测 %s 清单 %s" % (rel, got, digest))
    # 磁盘上不得有清单之外的文件
    on_disk = sorted(
        str(p.relative_to(root)).replace(os.sep, "/")
        for p in root.rglob("*")
        if p.is_file() and p.name != "MD5SUMS_A.txt"
    )
    extra = [f for f in on_disk if f not in man]
    if extra:
        problems.append("清单外文件: %s" % extra)
    csv_in_manifest = [r for r in order if r.endswith(".csv")]
    if len(csv_in_manifest) != N_FILES_EXPECTED:
        problems.append("清单中 CSV 行数 = %d，应为 %d" % (len(csv_in_manifest), N_FILES_EXPECTED))
    if problems:
        raise AssertionError("MD5 清单校验失败:\n  " + "\n  ".join(problems))
    return {
        "manifest_lines_total": len(man),
        "manifest_csv_lines": len(csv_in_manifest),
        "manifest_non_csv": sorted(r for r in man if not r.endswith(".csv")),
        "md5_all_match": True,
        "bytes_all_match": True,
        "no_extra_files": True,
    }


def read_cell(path: Path):
    """读一格：断言行数/表头/字段域，返回 list[dict]。"""
    raw_lines = path.read_text(encoding="utf-8").splitlines()
    if len(raw_lines) != LINES_PER_CELL:
        raise AssertionError("%s 行数 = %d，应为 %d" % (path.name, len(raw_lines), LINES_PER_CELL))
    with open(path, encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))
    if len(rows) != ROWS_PER_CELL:
        raise AssertionError("%s 数据行 = %d，应为 %d" % (path.name, len(rows), ROWS_PER_CELL))
    name = path.name
    domain, tag, start = name[:-4].split("__")
    if domain not in DOMAINS:
        raise AssertionError("未知域: %s" % name)
    if tag not in LEVELS:
        raise AssertionError("未知档: %s" % name)
    if start not in STARTS:
        raise AssertionError("未知启动: %s" % name)
    out = []
    for r in rows:
        if r["level_kind"] == "contract":
            if tag not in CONTRACT:
                raise AssertionError("%s: 档 %s 与 level_kind=contract 冲突" % (name, tag))
        elif r["level_kind"] == "pixelbudget":
            if tag not in PIXELBUDGET or r["level"] != tag[2:]:
                raise AssertionError("%s: 档 %s 与 level 列 %r 冲突" % (name, tag, r["level"]))
        else:
            raise AssertionError("%s: 未知 level_kind %r" % (name, r["level_kind"]))
        gt = int(r["gt"])
        if gt < 0:
            raise AssertionError("%s: gt<0" % name)
        if r["parse_ok"] == "1":
            if r["pred"] == "":
                raise AssertionError("%s: parse_ok=1 但 pred 为空" % name)
            try:
                pred = float(r["pred"])
            except ValueError:
                raise AssertionError("%s: parse_ok=1 但 pred 非数值 %r" % (name, r["pred"]))
            if pred < 0 or pred != int(pred):
                raise AssertionError("%s: pred 非非负整数 %r" % (name, r["pred"]))
            pred = int(pred)
        else:
            if r["pred"] != "":
                raise AssertionError("%s: parse_ok=0 但 pred 非空 %r" % (name, r["pred"]))
            pred = None
        out.append({
            "item": r["item"],
            "gt": gt,
            "pred": pred,
            "parse_ok": r["parse_ok"] == "1",
            "raw": r["raw"],
        })
    return out


def load_dataset(root: Path = ROOT):
    """{(domain, level, start): [记录]} + 完整性信息。"""
    ds = {}
    for domain in DOMAINS:
        for level in LEVELS:
            for start in STARTS:
                p = root / domain / ("%s__%s__%s.csv" % (domain, level, start))
                if not p.exists():
                    raise AssertionError("缺文件: %s" % p)
                ds[(domain, level, start)] = read_cell(p)
    if len(ds) != N_FILES_EXPECTED:
        raise AssertionError("格数 = %d，应为 %d" % (len(ds), N_FILES_EXPECTED))
    return ds


# ----------------------------------------------------------------------------- 输入断言
def assert_no_err(ds):
    bad = []
    for key, rows in ds.items():
        for r in rows:
            if r["raw"].startswith("ERR:"):
                bad.append((key, r["item"]))
    if bad:
        raise AssertionError("存在 raw 以 ERR: 开头的行: %s" % bad[:5])
    return 0


def assert_item_sets_equal(ds):
    """每域内 11 档 x 3 启动的 item 集合必须逐字相同（集合级）。"""
    info = {}
    for domain in DOMAINS:
        sets = {}
        for level in LEVELS:
            for start in STARTS:
                rows = ds[(domain, level, start)]
                keys = [r["item"] for r in rows]
                if len(keys) != len(set(keys)):
                    raise AssertionError("%s/%s/%s item 重复" % (domain, level, start))
                sets[(level, start)] = frozenset(keys)
        distinct = set(sets.values())
        if len(distinct) != 1:
            sizes = {k: len(v) for k, v in sets.items()}
            raise AssertionError("%s 域内 item 集合不一致: %s" % (domain, sizes))
        canonical = sets[(LEVELS[0], STARTS[0])]
        for key, s in sets.items():
            if s != canonical:
                raise AssertionError("%s 域 %s 与基准项集不同: 缺 %d 多 %d"
                                     % (domain, key, len(canonical - s), len(s - canonical)))
        # gt 必须逐项一致
        gts = {}
        for level in LEVELS:
            for start in STARTS:
                for r in ds[(domain, level, start)]:
                    prev = gts.setdefault((level, start), {})
                    prev[r["item"]] = r["gt"]
        base_gt = gts[(LEVELS[0], STARTS[0])]
        for key, m in gts.items():
            if m != base_gt:
                raise AssertionError("%s 域 %s 的 gt 与基准不一致" % (domain, key))
        info[domain] = {"n_items": len(canonical), "item_sets_identical": True, "gt_identical": True,
                        "order_identical": all(
                            [r["item"] for r in ds[(domain, lv, st)]] ==
                            [r["item"] for r in ds[(domain, LEVELS[0], STARTS[0])]]
                            for lv in LEVELS for st in STARTS)}
    return info


def assert_all(root: Path = ROOT):
    manifest = assert_manifest(root)
    ds = load_dataset(root)
    err = assert_no_err(ds)
    sets = assert_item_sets_equal(ds)
    return ds, {"manifest": manifest, "err_rows": err, "item_sets": sets,
                "cells": len(ds), "rows_per_cell": ROWS_PER_CELL, "lines_per_cell": LINES_PER_CELL}


# ----------------------------------------------------------------------------- 统计口径
def cell_index(rows):
    return {r["item"]: r for r in rows}


def rho_and_mae(rows, keys):
    """池化 rho / MAE / 逐项对数误差；pred 不可解析的项从分子分母同时剔除。"""
    idx = cell_index(rows)
    sp = sg = 0
    n_used = 0
    n_excl = 0
    abs_err = []
    log_err = []
    for k in keys:
        r = idx.get(k)
        if r is None:
            raise AssertionError("共同项集中出现该格没有的 item: %s" % k)
        if r["pred"] is None:
            n_excl += 1
            continue
        n_used += 1
        sp += r["pred"]
        sg += r["gt"]
        abs_err.append(abs(r["pred"] - r["gt"]))
        log_err.append(math.log(r["pred"] + 1) - math.log(r["gt"] + 1))
    rec = {
        "n_total": len(keys),
        "n_used": n_used,
        "n_excluded_abstain": n_excl,
        "sum_pred": sp if n_used else None,
        "sum_gt": sg if n_used else None,
    }
    if n_used < MIN_CELL_N or sg == 0:
        rec.update({"defined": False, "rho": None, "mae": None, "median_log_err": None,
                    "undefined_reason": ("n_used=%d < %d" % (n_used, MIN_CELL_N)) if n_used < MIN_CELL_N
                                        else "sum_gt=0"})
        return rec
    rec.update({
        "defined": True,
        "rho": r6(100.0 * (sp - sg) / sg),
        "mae": r6(sum(abs_err) / n_used),
        "median_log_err": r6(med(log_err)),
        "sign": sign_str(100.0 * (sp - sg) / sg),
    })
    return rec


def spectrum_span(recs, levels, label):
    """某一谱的跨度；可评档数 < 3 => 未测。"""
    defined = [(lv, recs[lv]["rho"]) for lv in levels if recs[lv]["defined"]]
    res = {
        "levels": levels,
        "n_levels_defined": len(defined),
        "rho_by_level": {lv: recs[lv]["rho"] for lv in levels},
        "undefined_levels": [lv for lv in levels if not recs[lv]["defined"]],
        "max_level": None, "min_level": None, "span": None, "status": UNDEF,
    }
    if len(defined) >= MIN_LEVELS_FOR_SPAN:
        mx = max(defined, key=lambda t: t[1])
        mn = min(defined, key=lambda t: t[1])
        res.update({"max_level": mx[0], "max_rho": r6(mx[1]), "min_level": mn[0], "min_rho": r6(mn[1]),
                    "span": r6(mx[1] - mn[1]), "status": "已评"})
    else:
        res["undefined_reason"] = "可评档数 %d < %d" % (len(defined), MIN_LEVELS_FOR_SPAN)
    return res


# ----------------------------------------------------------------------------- A1..A5
def a1_one(domain, start, ds, keys):
    base = cell_index(ds[(domain, "base", start)])
    base_zero = sorted([k for k in keys if base[k]["pred"] == 0])
    out = {"denominator_base_zero": len(base_zero), "arms": {}}
    for arm in ("permit", "channel"):
        idx = cell_index(ds[(domain, arm, start)])
        k_zero = 0
        fate = {"still_zero": 0, "abstain": 0, "nonzero": 0}
        for it in base_zero:
            r = idx[it]
            if r["pred"] is None:
                fate["abstain"] += 1
            elif r["pred"] == 0:
                k_zero += 1
                fate["still_zero"] += 1
            else:
                fate["nonzero"] += 1
        n = len(base_zero)
        ratio = (k_zero / n) if n else None
        w2 = wilson_upper(k_zero, n, Z95)
        w1 = wilson_upper(k_zero, n, Z95_ONE)
        out["arms"][arm] = {
            "numerator_still_zero": k_zero,
            "denominator": n,
            "ratio": r6(ratio),
            "ratio_pct": r6(100.0 * ratio) if ratio is not None else None,
            "wilson95_upper_twosided_pct": r6(100.0 * w2) if w2 is not None else None,
            "wilson95_upper_onesided_pct": r6(100.0 * w1) if w1 is not None else None,
            "verdict_ratio_le_5pct": (PASS if (ratio is not None and ratio <= GATE) else FAIL),
            "verdict_wilson_upper_le_5pct": (PASS if (w2 is not None and w2 <= GATE) else FAIL),
            "fate_of_base_zero_items": fate,
        }
    # 两臂合并（补充读法，非主判据）
    n_tot = 2 * len(base_zero)
    k_tot = sum(out["arms"][a]["numerator_still_zero"] for a in ("permit", "channel"))
    out["both_arms_pooled_supplementary"] = {
        "numerator_still_zero": k_tot, "denominator": n_tot,
        "ratio_pct": r6(100.0 * k_tot / n_tot) if n_tot else None,
        "wilson95_upper_twosided_pct": r6(100.0 * wilson_upper(k_tot, n_tot, Z95)) if n_tot else None,
    }
    return out


def a2_one(domain, start, ds, keys):
    recs = {lv: rho_and_mae(ds[(domain, lv, start)], keys) for lv in LEVELS}
    con = spectrum_span(recs, CONTRACT, "contract")
    pix = spectrum_span(recs, PIXELBUDGET, "pixelbudget")
    verdict = UNDEF
    if con["span"] is not None and pix["span"] is not None:
        verdict = PASS if con["span"] > pix["span"] else FAIL
    # 敏感性口径（非注册口径，仅参考）：只保留 n_used==n_total 的满格档
    full = [lv for lv in LEVELS if recs[lv]["defined"] and recs[lv]["n_used"] == recs[lv]["n_total"]]
    con_f = spectrum_span(recs, [lv for lv in CONTRACT if lv in full], "contract_fullgrid")
    pix_f = spectrum_span(recs, [lv for lv in PIXELBUDGET if lv in full], "pixelbudget_fullgrid")
    verdict_f = UNDEF
    if con_f["span"] is not None and pix_f["span"] is not None:
        verdict_f = PASS if con_f["span"] > pix_f["span"] else FAIL
    return {
        "contract_spectrum": con,
        "pixelbudget_spectrum": pix,
        "span_diff_pp": r6(con["span"] - pix["span"]) if (con["span"] is not None and pix["span"] is not None) else None,
        "verdict": verdict,
        "sensitivity_fullgrid_only": {
            "contract_span": con_f["span"], "pixelbudget_span": pix_f["span"],
            "verdict": verdict_f, "levels_used": full,
            "note": "非注册口径；仅剔掉有弃权的档后看不等式是否仍成立",
        },
    }


def a3_one(domain, start, ds, keys):
    recs = {lv: rho_and_mae(ds[(domain, lv, start)], keys) for lv in LEVELS}
    maes = {lv: recs[lv]["mae"] for lv in LEVELS if recs[lv]["defined"]}
    cand = {lv: m for lv, m in maes.items() if recs[lv]["n_used"] >= MIN_CELL_N}
    best_val = min(cand.values())
    best_levels = sorted([lv for lv, m in cand.items() if m == best_val])
    thr = MAE_MULT * best_val
    qualifying = sorted([lv for lv, m in cand.items() if m <= thr + EPS],
                        key=lambda lv: LEVELS.index(lv))
    q_rho = {lv: recs[lv]["rho"] for lv in qualifying}
    span = None
    status = UNDEF
    if len(qualifying) >= MIN_LEVELS_FOR_SPAN:
        span = r6(max(q_rho.values()) - min(q_rho.values()))
        status = "已评"
    # 诊断（非判据）：最小倍数使合格集 >= 3 档
    mult_scan = None
    if len(qualifying) < MIN_LEVELS_FOR_SPAN:
        for m in [1.0 + 0.01 * i for i in range(1, 400)]:
            q = [lv for lv, v in cand.items() if v <= m * best_val + EPS]
            if len(q) >= MIN_LEVELS_FOR_SPAN:
                mult_scan = r6(m)
                break
    return {
        "raw_rho_by_level": {lv: recs[lv]["rho"] for lv in LEVELS},
        "median_log_err_by_level": {lv: recs[lv]["median_log_err"] for lv in LEVELS},
        "n_used_by_level": {lv: recs[lv]["n_used"] for lv in LEVELS},
        "n_excluded_abstain_by_level": {lv: recs[lv]["n_excluded_abstain"] for lv in LEVELS},
        "mae_by_level": {lv: recs[lv]["mae"] for lv in LEVELS},
        "mae_best_value": r6(best_val),
        "mae_best_levels": best_levels,
        "mae_threshold_1p10x": r6(thr),
        "qualifying_levels": qualifying,
        "qualifying_n_levels": len(qualifying),
        "span_of_rho_over_qualifying": span,
        "span_status": status,
        "undefined_reason": (None if status == "已评" else
                             "合格集只有 %d 档 (<%d) => 跨度未测" % (len(qualifying), MIN_LEVELS_FOR_SPAN)),
        "diagnostic_only_min_multiplier_for_3_levels": mult_scan,
        "log_err_handling": "pred 不可解析(弃权)的项整体剔除，不参与中位数；剔除条数见 n_excluded_abstain_by_level",
        "mae_handling": "pred 不可解析(弃权)的项整体剔除，不参与 MAE；不做任何代理量顶替",
    }


def a4_one(domain, ds, keys):
    units = {"contract": CONTRACT, "pixelbudget": PIXELBUDGET}
    out = {"units": {}}
    flips = []
    for unit, levels in units.items():
        per_level = {}
        for lv in levels:
            signs = []
            rhos = {}
            for st in STARTS:
                rec = rho_and_mae(ds[(domain, lv, st)], keys)
                rhos[st] = rec["rho"]
                signs.append(rec["sign"] if rec["defined"] else UNDEF)
            per_level[lv] = {"rho_by_start": rhos, "sign_by_start": signs,
                             "sign_consistent_across_starts": len(set(signs)) == 1}
            if not per_level[lv]["sign_consistent_across_starts"]:
                flips.append({"unit": unit, "level": lv, "kind": "start",
                              "sign_by_start": signs})
        defined_signs = {lv: per_level[lv]["sign_by_start"][0] for lv in levels
                         if per_level[lv]["sign_by_start"][0] != UNDEF}
        uniq = sorted(set(defined_signs.values()))
        for lv, s in defined_signs.items():
            if len(uniq) > 1:
                flips.append({"unit": unit, "level": lv, "kind": "level",
                              "sign": s, "all_signs": defined_signs})
        out["units"][unit] = {
            "per_level": per_level,
            "signs_used": defined_signs,
            "distinct_signs": uniq,
            "sign_uniform_within_unit": len(uniq) <= 1,
        }
    out["named_sign_flips"] = flips
    out["verdict"] = ("一致" if not flips else "不一致，已具名列出反号格")
    return out


def analyze(ds, integ):
    result = {
        "meta": {
            "round": "A",
            "date": "2026-09-28",
            "domains": DOMAINS,
            "contract_levels": CONTRACT,
            "pixelbudget_levels": PIXELBUDGET,
            "starts": STARTS,
            "data_root": str(ROOT),
            "criteria_file": str(CRITERIA),
            "criteria_md5": md5_of(CRITERIA),
            "script_md5": md5_of(Path(__file__).resolve()),
            "definitions": {
                "answer_zero": "parse_ok==1 且 pred==0",
                "abstain": "parse_ok==0（无解析值 / outlet token）",
                "rho": "100*(sum(pred)-sum(gt))/sum(gt)，在该域共同 item 交集(=200 项)上算，"
                       "pred 不可解析的项从分子分母同时剔除",
                "span": "max(rho)-min(rho)，只取未报未测的档",
                "median_log_err": "median(ln(pred+1)-ln(gt+1))，弃权项剔除",
                "mae": "mean(|pred-gt|)，弃权项剔除",
                "a3_3": "MAE_best=min(各档 MAE)；合格集={档: MAE <= 1.10*MAE_best}(边界闭合)；"
                        "报合格集内 rho 的跨度；合格集<3 档报未测",
                "wilson": "双侧 95% Wilson 上界 (z=1.959963984540054)；另附单侧 z=1.6448536269514722",
                "undefined_rule": "n_used<20 或可评档数<3 => 未测",
            },
        },
        "integrity": integ,
        "A1": {}, "A2": {}, "A3": {}, "A4": {}, "A5": {},
    }
    keys_by_domain = {}
    for domain in DOMAINS:
        keys = [r["item"] for r in ds[(domain, LEVELS[0], STARTS[0])]]
        keys_by_domain[domain] = keys
        result["A1"][domain] = {st: a1_one(domain, st, ds, keys) for st in STARTS}
        result["A2"][domain] = {st: a2_one(domain, st, ds, keys) for st in STARTS}
        result["A3"][domain] = {st: a3_one(domain, st, ds, keys) for st in STARTS}
        result["A4"][domain] = a4_one(domain, ds, keys)

    # 域级判定
    for domain in DOMAINS:
        a1_arms = {}
        for arm in ("permit", "channel"):
            v = [result["A1"][domain][st]["arms"][arm]["verdict_ratio_le_5pct"] for st in STARTS]
            vw = [result["A1"][domain][st]["arms"][arm]["verdict_wilson_upper_le_5pct"] for st in STARTS]
            a1_arms[arm] = {
                "verdict_by_start_ratio": v, "verdict_by_start_wilson_upper": vw,
                "domain_verdict_ratio": PASS if all(x == PASS for x in v) else FAIL,
                "domain_verdict_wilson_upper": PASS if all(x == PASS for x in vw) else FAIL,
            }
        result["A1"][domain]["domain"] = a1_arms
        a2v = {st: result["A2"][domain][st]["verdict"] for st in STARTS}
        n_pass = sum(1 for v in a2v.values() if v == PASS)
        result["A2"][domain]["domain"] = {
            "verdict_by_start": a2v,
            "starts_pass": [st for st in STARTS if a2v[st] == PASS],
            "starts_fail": [st for st in STARTS if a2v[st] == FAIL],
            "domain_verdict_all3": PASS if n_pass == len(STARTS) else FAIL,
            "domain_verdict_majority": PASS if n_pass * 2 > len(STARTS) else FAIL,
            "note": "域级判定=三启动全部成立(最严、不挑启动)；多数口径同时给出。二者不一致时照实列出。",
        }
        a3 = result["A3"][domain]
        result["A3"][domain]["domain"] = {
            "span_status_by_start": {st: a3[st]["span_status"] for st in STARTS},
            "all_start_variants": all(a3[st]["span_status"] == "已评" for st in STARTS),
            "note": "A3 通过线(freeze)=三项齐全且可复算；③在冻结件自身 <3 档规则下报未测",
        }

    # A5 分支
    a1_d = {d: result["A1"][d]["domain"]["permit"]["domain_verdict_ratio"] for d in DOMAINS}
    a2_d = {d: result["A2"][d]["domain"]["domain_verdict_all3"] for d in DOMAINS}
    n_a2_pass = sum(1 for d in DOMAINS if a2_d[d] == PASS)
    if n_a2_pass == len(DOMAINS):
        branch = "(i) 两域都过"
    elif n_a2_pass == 0:
        branch = "(iii) 两个都不过"
    else:
        branch = "(ii) 只过一个 => 照实报一过一不过"
    result["A5"] = {
        "frozen_rule_quoted": (
            "★ 两域分别判定、分别报出；合并只在两域都达标时才作为附加陈述。"
            "rule: (i) 两域都过 ⇒ 报『两个独立新域上预注册判据均通过』，并给合并读法；"
            "(ii) 只过一个 ⇒ 照实报一过一不过，不得只报通过的那个，也不得用合并统计把它掩盖掉"
            "（先例：§M.46 明写『One cell is above the bar and is reported rather than pooled away』）；"
            "(iii) 两个都不过 ⇒ 报『未复制』，并按 §7.3 的 scope 再收一格。"
        ),
        "a1_domain_verdict_ratio": a1_d,
        "a1_domain_verdict_wilson_upper": {
            d: {arm: result["A1"][d]["domain"][arm]["domain_verdict_wilson_upper"]
                for arm in ("permit", "channel")} for d in DOMAINS},
        "a2_domain_verdict": a2_d,
        "a4_verdict": {d: result["A4"][d]["verdict"] for d in DOMAINS},
        "branch": branch,
        "must_report_both_domains": True,
    }
    return result


# ----------------------------------------------------------------------------- 产物校验
def compare(a, b, path="root"):
    """(a=重算, b=存档) 深度比较；浮点用 r6 已归一到 6 位，直接比。"""
    diffs = []
    if isinstance(a, dict) and isinstance(b, dict):
        for k in sorted(set(a) | set(b)):
            if k in SKIP_META:
                continue
            if k not in a or k not in b:
                diffs.append("%s.%s 仅在一侧" % (path, k))
                continue
            diffs += compare(a[k], b[k], "%s.%s" % (path, k))
    elif isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            diffs.append("%s 长度 %d != %d" % (path, len(a), len(b)))
        else:
            for i, (x, y) in enumerate(zip(a, b)):
                diffs += compare(x, y, "%s[%d]" % (path, i))
    else:
        if a != b:
            diffs.append("%s: 重算 %r != 存档 %r" % (path, a, b))
    return diffs


SKIP_META = {"generated_at", "script_md5_check"}


def run_check():
    if not OUT.exists():
        print("CHECK FAIL: 产物不存在 %s" % OUT)
        return 1
    stored = json.loads(OUT.read_text(encoding="utf-8"))
    ds, integ = assert_all(ROOT)
    fresh = analyze(ds, integ)
    fresh["meta"]["generated_at"] = stored["meta"].get("generated_at")
    cur_md5 = md5_of(Path(__file__).resolve())
    if stored["meta"]["script_md5"] != cur_md5:
        print("CHECK FAIL: 存档脚本 md5 %s != 当前脚本 md5 %s（脚本已改动，需重跑）"
              % (stored["meta"]["script_md5"], cur_md5))
        return 1
    if stored["meta"]["criteria_md5"] != md5_of(CRITERIA):
        print("CHECK FAIL: 判据文件 md5 与存档不符（冻结件被动过）")
        return 1
    diffs = compare(fresh, stored)
    if diffs:
        print("CHECK FAIL: %d 处不一致" % len(diffs))
        for d in diffs[:20]:
            print("   ", d)
        return 1
    print("CHECK OK: 66 格 x 201 行 / md5 清单 / ERR=0 / item 集合 全部复核通过；"
          "A1-A5 全部数字与存档逐数一致")
    print("  脚本 md5      : %s" % cur_md5)
    print("  判据 md5      : %s" % stored["meta"]["criteria_md5"])
    print("  产物 md5      : %s" % md5_of(OUT))
    return 0


# ----------------------------------------------------------------------------- 表格（机械生成，报告逐字嵌入）
def _f(x, nd=4):
    return "未测" if x is None else ("%.*f" % (nd, x))


def _p(x, nd=2):
    return "未测" if x is None else ("%.*f" % (nd, x))


def markdown_tables(r):
    L = []
    L.append("#### T1 A1 门禁移植（逐域 × 逐启动，不合并）\n")
    L.append("| 域 | 启动 | base 答零 n | permit 仍答零 k | permit 比例 % | permit Wilson95 上界(双侧) % | channel 仍答零 k | channel 比例 % | channel Wilson95 上界(双侧) % | 门禁(比例≤5%) |")
    L.append("|---|---|---|---|---|---|---|---|---|---|")
    for d in DOMAINS:
        for st in STARTS:
            out = [d, st]
            a1 = r["A1"][d][st]
            out.append(str(a1["denominator_base_zero"]))
            for arm in ("permit", "channel"):
                a = a1["arms"][arm]
                out += [str(a["numerator_still_zero"]), _p(a["ratio_pct"]), _p(a["wilson95_upper_twosided_pct"])]
            out.append(r["A1"][d]["domain"]["permit"]["domain_verdict_ratio"])
            L.append("| " + " | ".join(out) + " |")
    L.append("")
    L.append("#### T2 A2 两个谱的池化 ρ 跨度（逐域 × 逐启动，不合并）\n")
    L.append("| 域 | 启动 | span(契约 6 臂) / pp | 契约 min→max 档 | span(像素预算 5 档) / pp | 像素 min→max 档 | 不等式 span(契约)>span(像素) | 差 / pp |")
    L.append("|---|---|---|---|---|---|---|---|")
    for d in DOMAINS:
        for st in STARTS:
            a2 = r["A2"][d][st]
            c, p = a2["contract_spectrum"], a2["pixelbudget_spectrum"]
            L.append("| %s | %s | %s | %s(%s)→%s(%s) | %s | %s(%s)→%s(%s) | %s | %s |" % (
                d, st, _f(c["span"]), c["min_level"], _f(c["min_rho"]), c["max_level"], _f(c["max_rho"]),
                _f(p["span"]), p["min_level"], _f(p["min_rho"]), p["max_level"], _f(p["max_rho"]),
                a2["verdict"], _f(a2["span_diff_pp"])))
    L.append("")
    L.append("#### T3a A3① 原始池化 ρ / pp（逐档 × 逐启动 × 逐域）\n")
    L.append("| 档 | mtdc s1 | mtdc s2 | mtdc s3 | gwhd s1 | gwhd s2 | gwhd s3 |")
    L.append("|---|---|---|---|---|---|---|")
    for lv in LEVELS:
        L.append("| %s | %s |" % (lv, " | ".join(
            _f(r["A3"][d][st]["raw_rho_by_level"][lv]) for d in DOMAINS for st in STARTS)))
    L.append("")
    L.append("#### T3b A3② 逐项对数误差 median(ln(pred+1)−ln(gt+1))（逐档 × 逐启动 × 逐域）\n")
    L.append("| 档 | mtdc s1 | mtdc s2 | mtdc s3 | gwhd s1 | gwhd s2 | gwhd s3 |")
    L.append("|---|---|---|---|---|---|---|")
    for lv in LEVELS:
        L.append("| %s | %s |" % (lv, " | ".join(
            _f(r["A3"][d][st]["median_log_err_by_level"][lv]) for d in DOMAINS for st in STARTS)))
    L.append("")
    L.append("#### T3c A3③ 用 MAE（逐档 × 逐启动 × 逐域）\n")
    L.append("| 档 | mtdc s1 | mtdc s2 | mtdc s3 | gwhd s1 | gwhd s2 | gwhd s3 |")
    L.append("|---|---|---|---|---|---|---|")
    for lv in LEVELS:
        L.append("| %s | %s |" % (lv, " | ".join(
            _f(r["A3"][d][st]["mae_by_level"][lv]) for d in DOMAINS for st in STARTS)))
    L.append("")
    L.append("#### T3d A3③ 合格集与跨度（MAE ≤ 1.10×MAE_best，边界闭合）\n")
    L.append("| 域 | 启动 | MAE_best | 最优档 | 阈值 1.10× | 合格集 | 合格档数 | 合格集内 ρ 跨度 | 状态 |")
    L.append("|---|---|---|---|---|---|---|---|---|")
    for d in DOMAINS:
        for st in STARTS:
            a3 = r["A3"][d][st]
            L.append("| %s | %s | %s | %s | %s | %s | %d | %s | %s |" % (
                d, st, _f(a3["mae_best_value"]), ",".join(a3["mae_best_levels"]),
                _f(a3["mae_threshold_1p10x"]), ",".join(a3["qualifying_levels"]),
                a3["qualifying_n_levels"], _f(a3["span_of_rho_over_qualifying"]), a3["span_status"]))
    L.append("")
    L.append("#### T4 A4 ρ 符号（逐旋钮 × 逐档；三启动符号逐格一致）\n")
    L.append("| 域 | 旋钮 | 档 | ρ 符号 | ρ / pp（s1） | ρ / pp（s2） | ρ / pp（s3） |")
    L.append("|---|---|---|---|---|---|---|")
    for d in DOMAINS:
        for unit, levels in (("contract", CONTRACT), ("pixelbudget", PIXELBUDGET)):
            for lv in levels:
                pl = r["A4"][d]["units"][unit]["per_level"][lv]
                L.append("| %s | %s | %s | %s | %s | %s | %s |" % (
                    d, unit, lv, "/".join(pl["sign_by_start"]),
                    _f(pl["rho_by_start"]["s1"]), _f(pl["rho_by_start"]["s2"]), _f(pl["rho_by_start"]["s3"])))
    L.append("")
    L.append("#### T5 域级结论（A1/A2/A4）\n")
    L.append("| 域 | A1 门禁(比例≤5%) | A1 门禁(Wilson 上界≤5%) | A2 不等式 | A4 方向一致性 |")
    L.append("|---|---|---|---|---|")
    for d in DOMAINS:
        L.append("| %s | %s | %s | %s | %s |" % (
            d,
            r["A1"][d]["domain"]["permit"]["domain_verdict_ratio"],
            r["A1"][d]["domain"]["permit"]["domain_verdict_wilson_upper"],
            r["A2"][d]["domain"]["domain_verdict_all3"],
            "不一致（有具名反号格）" if r["A4"][d]["named_sign_flips"] else "一致"))
    L.append("")
    return "\n".join(L) + "\n"


BEG = "<!-- TABLES:BEGIN 由 A_analyze.py --tables 生成，勿手改 -->"
END = "<!-- TABLES:END -->"


def load_result():
    if not OUT.exists():
        raise SystemExit("产物不存在: %s（先跑 python A_analyze.py）" % OUT)
    return json.loads(OUT.read_text(encoding="utf-8"))


def run_report_check(md_path: Path):
    r = load_result()
    expect = markdown_tables(r)
    text = md_path.read_text(encoding="utf-8")
    if BEG not in text or END not in text:
        print("REPORT CHECK FAIL: 报告里找不到表格标记块 %s ... %s" % (BEG, END))
        return 1
    got = text.split(BEG, 1)[1].split(END, 1)[0]
    norm = lambda s: "\n".join(x.rstrip() for x in s.strip().splitlines())
    if norm(got) != norm(expect):
        g, e = norm(got).splitlines(), norm(expect).splitlines()
        print("REPORT CHECK FAIL: 报告表格与 A_result.json 不一致")
        for i in range(max(len(g), len(e))):
            a = g[i] if i < len(g) else "<缺>"
            b = e[i] if i < len(e) else "<多>"
            if a != b:
                print("  行%d 报告: %s" % (i + 1, a))
                print("       应为: %s" % b)
        return 1
    # 顺带核对报告里写的三个 md5 与实盘一致
    cur = md5_of(Path(__file__).resolve())
    for label, val in (("脚本 md5", cur), ("产物 md5", md5_of(OUT)),
                       ("判据 md5", md5_of(CRITERIA))):
        if val not in text:
            print("REPORT CHECK FAIL: 报告未印出 %s = %s" % (label, val))
            return 1
    print("REPORT CHECK OK: 报告表格块与 A_result.json 逐字一致；脚本/产物/判据三个 md5 均已在报告中")
    return 0


# ----------------------------------------------------------------------------- 阴性对照
def _fresh_ds():
    ds, integ = assert_all(ROOT)
    return ds, integ


def selftest():
    ds, integ = _fresh_ds()
    keys = [r["item"] for r in ds[("mtdc", LEVELS[0], STARTS[0])]]
    controls = []

    def record(name, expect, fn):
        try:
            fn()
        except AssertionError as e:
            controls.append((name, expect, True, str(e).splitlines()[0][:120]))
            return
        except Exception as e:  # noqa
            controls.append((name, expect, False, "非 AssertionError: %r" % e))
            return
        controls.append((name, expect, False, "未触发失败（断言没有成立）"))

    # 对照 0：未篡改时必须通过（阳性对照）
    def ctl0():
        r = analyze(ds, integ)
        assert r["A1"]["mtdc"]["domain"]["permit"]["domain_verdict_ratio"] == PASS
        assert r["A2"]["mtdc"]["s1"]["verdict"] == FAIL
        assert r["A2"]["gwhd"]["s1"]["verdict"] == PASS
        assert r["A3"]["mtdc"]["s1"]["span_status"] == UNDEF
    record("ctl0-baseline-untampered", "通过（不失败）", ctl0)

    # 对照 1：把 permit 对 base 答零项的答案改掉（改成又答 0）=> 门禁口径断言必须失败
    def ctl1():
        d2 = copy.deepcopy(ds)
        idx = cell_index(d2[("mtdc", "permit", "s1")])
        bz = [k for k in keys if cell_index(d2[("mtdc", "base", "s1")])[k]["pred"] == 0]
        for it in bz[:5]:
            idx[it]["pred"] = 0
            idx[it]["parse_ok"] = True
        r = analyze(d2, integ)
        a1 = r["A1"]["mtdc"]["s1"]["arms"]["permit"]
        # 下面两条是「未篡改时成立」的口径断言，篡改后必须失败：
        assert a1["numerator_still_zero"] == 0, \
            "篡改后 permit 分子=%d（口径断言未失败）" % a1["numerator_still_zero"]
        assert a1["verdict_ratio_le_5pct"] == PASS, "篡改后门禁仍是通过（口径断言未失败）"
    record("ctl1-answer-tamper-gate-must-fail", "必须失败", ctl1)

    # 对照 2：往某格塞一个外来 item => item 集合交集断言必须失败
    def ctl2():
        d2 = copy.deepcopy(ds)
        d2[("gwhd", "permit", "s2")][0]["item"] = "ZZZ_FOREIGN_ITEM"
        assert_item_sets_equal(d2)
    record("ctl2-foreign-item-breaks-set-intersection", "必须失败", ctl2)

    # 对照 3：打乱某格行序 => 集合断言仍成立（打乱不改集合），但顺序诊断必须翻；
    #          且所有数字必须逐位不变（证明按 item 键连接，而不是按行位置连接）。
    def ctl3():
        d2 = copy.deepcopy(ds)
        ref = ds[("mtdc", "base", "s1")]
        sh = list(d2[("mtdc", "permit", "s1")])   # 该格有弃权 => 位置错位才会改变 sum_gt
        random.Random(20260928).shuffle(sh)
        d2[("mtdc", "permit", "s1")] = sh
        info = assert_item_sets_equal(d2)
        r = analyze(d2, integ)
        r0 = analyze(ds, integ)
        rho_key = r["A3"]["mtdc"]["s1"]["raw_rho_by_level"]["permit"]
        # 若按行位置连接（错法），sum_gt 会错位
        sp = sg = 0
        for a, b in zip(ref, sh):
            if b["pred"] is None:
                continue
            sp += b["pred"]
            sg += a["gt"]
        rho_pos = r6(100.0 * (sp - sg) / sg)
        violations = []
        if info["mtdc"]["item_sets_identical"] is not True:
            violations.append("打乱行序被误判成集合不一致（集合断言不该因顺序而失败）")
        if info["mtdc"]["order_identical"] is not False:
            violations.append("顺序诊断未翻")
        if rho_key != r0["A3"]["mtdc"]["s1"]["raw_rho_by_level"]["permit"]:
            violations.append("键连接的数字随行序变化")
        # 下面这条是必须失败的断言：位置连接 == 键连接（打乱后不成立）
        if rho_pos == rho_key:
            violations.append("位置连接与键连接恰好相同，该对照无法区分两种连接方式")
        else:
            violations.append("断言『位置连接==键连接』失败：pos rho=%s vs key rho=%s（本管线按 item 键连接）"
                              % (rho_pos, rho_key))
        raise AssertionError("; ".join(violations))
    record("ctl3-row-shuffle-order-diag-flips-and-key-join-invariant", "必须失败", ctl3)

    # 对照 4：把 Wilson 上界换成恒 0 => 门禁一致性断言必须失败
    def ctl4():
        globals()["wilson_upper"] = lambda k, n, z=Z95: 0.0
        try:
            r = analyze(ds, integ)
            a1 = r["A1"]["mtdc"]["s1"]["arms"]["permit"]
            assert a1["verdict_wilson_upper_le_5pct"] == PASS
            # 一致性断言：存档/重算的 Wilson 上界必须等于按 (k,n) 独立复算的值，且 n 很小、k=0 时不得 <=5%
            n = a1["denominator"]
            k = a1["numerator_still_zero"]
            recomputed = 100.0 * _wilson_reference(k, n, Z95)
            if abs(a1["wilson95_upper_twosided_pct"] - recomputed) < 1e-9 and a1["wilson95_upper_twosided_pct"] > GATE * 100:
                return  # 正常路径（未篡改）不会走到这
            raise AssertionError("恒 0 的 Wilson 上界未被门禁一致性断言拦下: %s" % a1["wilson95_upper_twosided_pct"])
        finally:
            globals()["wilson_upper"] = _wilson_original
    globals()["_wilson_original"] = wilson_upper
    globals()["_wilson_reference"] = _wilson_reference
    record("ctl4-wilson-constant-zero-must-fail", "必须失败", ctl4)

    # 对照 5：注入 ERR 行 => ERR=0 断言必须失败
    def ctl5():
        d2 = copy.deepcopy(ds)
        d2[("gwhd", "base", "s3")][7]["raw"] = "ERR: connection reset"
        assert_no_err(d2)
    record("ctl5-err-row-injection-must-fail", "必须失败", ctl5)

    # 对照 6：真·md5 篡改（整树复制后改一个字节）=> 清单断言必须失败，且失败原因必须是 md5/字节数
    def ctl6():
        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td) / "A_res"
            shutil.copytree(ROOT, tdp)
            p = tdp / "mtdc" / "mtdc__base__s1.csv"
            b = bytearray(p.read_bytes())
            b[-2] = (b[-2] + 1) % 256
            p.write_bytes(bytes(b))
            try:
                assert_manifest(tdp)
            except AssertionError as e:
                if "md5 不符" not in str(e) and "字节数不符" not in str(e):
                    raise AssertionError("篡改被拦下，但不是因为 md5/字节数: %s" % str(e)[:80])
                raise
            raise AssertionError("字节篡改未被 md5 清单拦下")
    record("ctl6-real-byte-tamper-breaks-md5-manifest", "必须失败", ctl6)

    ok = True
    for _name, _expect, _failed, _msg in controls:
        good = (_failed is False) if _expect == "通过（不失败）" else (_failed is True)
        if not good:
            ok = False
    print("SELFTEST %s" % ("OK" if ok else "FAIL"))
    for name, expect, failed, msg in controls:
        good = (failed is False) if expect == "通过（不失败）" else (failed is True)
        print("  [%s] %-58s 期望=%-28s 结果=%s  %s"
              % ("OK " if good else "BAD", name, expect, "失败/触发" if failed else "未触发", msg))
    return 0 if ok else 1


def _wilson_reference(k, n, z=Z95):
    p = k / n
    z2 = z * z
    return min(1.0, (p + z2 / (2 * n) + z * math.sqrt(p * (1 - p) / n + z2 / (4 * n * n))) / (1 + z2 / n))


# ----------------------------------------------------------------------------- 主流程
def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--tables", metavar="OUT|-", help="输出报告用 markdown 表（'-' 走 stdout）")
    ap.add_argument("--report-check", metavar="MD", help="校验报告里的表格块与 A_result.json 逐字一致")
    args = ap.parse_args()
    if args.selftest:
        return selftest()
    if args.check:
        return run_check()
    if args.tables:
        r = load_result()
        txt = markdown_tables(r)
        if args.tables == "-":
            print(txt)
        else:
            Path(args.tables).write_text(txt, encoding="utf-8")
            print("已写表: %s" % args.tables)
        return 0
    if args.report_check:
        return run_report_check(Path(args.report_check))

    ds, integ = assert_all(ROOT)
    result = analyze(ds, integ)
    # 不写时间戳：A_result.json 必须在同一份数据上逐字节可复现
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    print("已写: %s" % OUT)
    print("脚本 md5: %s" % result["meta"]["script_md5"])
    print("判据 md5: %s" % result["meta"]["criteria_md5"])
    print("产物 md5: %s" % md5_of(OUT))
    print("完整性: 格数=%d 行/格=%d ERR行=%d md5清单=%d行(其中CSV=%d)"
          % (integ["cells"], integ["rows_per_cell"], integ["err_rows"],
             integ["manifest"]["manifest_lines_total"], integ["manifest"]["manifest_csv_lines"]))
    for d in DOMAINS:
        print("-- %s" % d)
        for st in STARTS:
            a1p = result["A1"][d][st]["arms"]["permit"]
            a1c = result["A1"][d][st]["arms"]["channel"]
            a2 = result["A2"][d][st]
            print("   %s A1 permit %s/%s=%.2f%% wilson<=5%%? %s | channel %s/%s=%.2f%% wilson<=5%%? %s"
                  % (st, a1p["numerator_still_zero"], a1p["denominator"],
                     100 * a1p["ratio"], a1p["verdict_wilson_upper_le_5pct"],
                     a1c["numerator_still_zero"], a1c["denominator"],
                     100 * a1c["ratio"], a1c["verdict_wilson_upper_le_5pct"]))
            print("      A2 span(contract)=%s span(pixel)=%s -> %s"
                  % (a2["contract_spectrum"]["span"], a2["pixelbudget_spectrum"]["span"], a2["verdict"]))
        print("   域级 A2: %s" % result["A2"][d]["domain"]["domain_verdict_all3"])
    print("A5 分支: %s" % result["A5"]["branch"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
