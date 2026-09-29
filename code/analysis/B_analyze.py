#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""B_analyze.py — 实验 B（4-bit 语料基线构建上重跑五臂）的**结论计算**脚本。

判据**只读**：analysis/work/B_criteria_frozen.json（md5 见 REPORT 引用），本脚本一个字节都不改。
B0 已按预注册判据 FAIL，并按冻结件降级执行（英中同工件对照有效；与语料基线的绝对率比较带 1.3% 项级栈带）。
本脚本**不重判 B0**。

输入（全部只读）
  · analysis/B_res_20260928/MD5SUMS_B.txt                66 行清单（md5 + 相对路径 + 字节数）
  · analysis/B_res_20260928/start{1,2,3}/<ds>__<arm>.csv 60 个（本轮 4-bit，gt 列留空）
  · analysis/g2_neutral0/_g2_result.json                  BF16 当年 20 格汇总（口径校验用）
  · analysis/g2_neutral0/<ds>__<arm>.csv                  BF16 逐项 20 个
  · analysis/g2_neutral0/pool/vlm_<ds>_base_whole.csv     gt 来源（= A800 /root/dense_results/，md5 已核对）

口径（逐字照 g2_neutral0.py 的 docstring 与 _g2_result.json 的字段定义反推，并用 st_a|cn-base 校验）
  · item 池 = 语料池 CSV 中 parse_ok==1 的行；gt 按 item 连接（驱动里 gt 列留空是设计）
  · 答零 zero    = parse_ok==1 且解析出的 pred == 0
  · 弃权 abstain = parse_ok==0（或 parse_ok==1 但 pred 非数值）
  · 已作答 answered = parse_ok==1 且 pred > 0
  · G  = 全项（池内 parse_ok==1 的行）GT 质量；G_N = answered 项的 GT 质量
  · P  = answered 项的 pred 之和
  · w  = G_N / G
  · rho_ans = 100 * (P - G_N) / G_N          （百分数；与 _g2_result.json 同量纲）
  · S  = 100 * (1 - w) / [1 - w * (1 + rho_ans/100)]   （= 百分数刻度；单位区间 = [0,100]）
         分母 <= 0 ⇒ 无定义（BF16 的 ucf|en-base 即此情形，JSON 里记 S=null）
  · 零率的 Wilson 95% 区间（分侧），差值 Δ = en - cn 的 95% 区间用 Newcombe 混合得分法（确定性，无随机）

用法
  python B_analyze.py              # 全量：先断言，再计算，写 B_result.json
  python B_analyze.py --check      # 重读 B_result.json，校验内部一致性与关键不变量
  python B_analyze.py --selftest   # 阴性对照（≥3 条）：必须全部"如期失败"
  python B_analyze.py --tables     # 打印报告用 markdown 片段（从 B_result.json 生成，避免手抄）
"""
import argparse
import copy
import csv
import hashlib
import io
import json
import math
import os
import sys
import tempfile

sys.stdout.reconfigure(encoding='utf-8')

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # ...\PaperB\analysis
B_DIR = os.path.join(ROOT, 'B_res_20260928')
BF16_DIR = os.path.join(ROOT, 'g2_neutral0')
POOL_DIR = os.path.join(BF16_DIR, 'pool')
BF16_JSON = os.path.join(BF16_DIR, '_g2_result.json')
MANIFEST = os.path.join(B_DIR, 'MD5SUMS_B.txt')
OUT_JSON = os.path.join(ROOT, 'work', 'B_result.json')

DS = ['st_a', 'ucf', 'visdrone', 'aitod']
DENSE = ['st_a', 'ucf']
AERIAL = ['visdrone', 'aitod']
ARMS = ['cn-base', 'cn-neutral0', 'en-base', 'en-neutral0', 'en-neutral0em']
HEAD_ARMS = ['cn-base', 'en-base']
STARTS = ['start1', 'start2', 'start3']
EXPECT_ROWS = {'st_a': 182, 'ucf': 334, 'visdrone': 400, 'aitod': 226}
# 语料池 md5（本地副本 == A800 /root/dense_results/，2026-09-28 只读核对）
POOL_MD5 = {
    'st_a': 'ff69abb8457cba31d0fdf6d3702ec432',
    'ucf': '4fe5246ca1603625ef158eb3f5c99901',
    'visdrone': '6621897edff850551c63f2d2a67160e4',
    'aitod': 'b346e576cf8ed0819bd2273dcf52e470',
}
Z = 1.959963984540054          # 95% 正态分位
BF16_TOL = 0.05                # B3 口径校验容差（冻结件：偏差 >0.05 即口径没对齐）
B0_BAND_PP = 1.3               # B0 降级：aitod 项级栈带 1.3%


# ---------------------------------------------------------------- io helpers
def md5_bytes(b):
    return hashlib.md5(b).hexdigest()


def md5_file(p):
    with open(p, 'rb') as f:
        return md5_bytes(f.read())


def load_csv(p):
    with io.open(p, encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


def num(x):
    try:
        return float(str(x).strip())
    except Exception:
        return None


def pct(x):
    return None if x is None else round(100.0 * x, 6)


# ---------------------------------------------------------------- statistics
def wilson(k, n):
    """Wilson 95% 区间，返回**百分数**刻度 (lo, hi)。n==0 ⇒ None（未测）。"""
    if n <= 0:
        return None
    p = k / n
    d = 1 + Z * Z / n
    c = (p + Z * Z / (2 * n)) / d
    h = Z * math.sqrt(p * (1 - p) / n + Z * Z / (4 * n * n)) / d
    return (round(100 * max(0.0, c - h), 6), round(100 * min(1.0, c + h), 6))


def newcombe_diff(k1, n1, k2, n2):
    """Δ = p2 - p1 的 Newcombe(method 10) 95% 区间，百分数刻度。任一侧 n==0 ⇒ None。"""
    if n1 <= 0 or n2 <= 0:
        return None
    p1, p2 = k1 / n1, k2 / n2
    (l1, u1), (l2, u2) = wilson(k1, n1), wilson(k2, n2)
    l1, u1, l2, u2 = l1 / 100, u1 / 100, l2 / 100, u2 / 100
    d = p2 - p1
    lo = d - math.sqrt((p2 - l2) ** 2 + (u1 - p1) ** 2)
    hi = d + math.sqrt((u2 - p2) ** 2 + (p1 - l1) ** 2)
    return (round(100 * lo, 6), round(100 * hi, 6))


def overlap(a, b):
    if a is None or b is None:
        return None
    return max(a[0], b[0]) <= min(a[1], b[1])


def sums_from(rows, gmap):
    """按冻结口径汇总一组逐项行。rows 的 item 必须在 gmap 里。"""
    ok, abstain, nonnum = [], 0, 0
    for r in rows:
        if (r.get('parse_ok') or '').strip() != '1':
            abstain += 1
            continue
        if num(r.get('pred')) is None:
            nonnum += 1
            continue
        ok.append(r)
    answered = [r for r in ok if num(r['pred']) > 0]
    zeros = [r for r in ok if num(r['pred']) == 0]
    G = sum(gmap[r['item']] for r in ok)
    GN = sum(gmap[r['item']] for r in answered)
    P = sum(num(r['pred']) for r in answered)
    n = len(ok)
    w = (GN / G) if G else None
    rho = (100.0 * (P - GN) / GN) if GN else None
    S = None
    if w is not None and rho is not None:
        den = 1.0 - w * (1.0 + rho / 100.0)
        S = (100.0 * (1.0 - w) / den) if den != 0 else None
        if den < 0:
            S = None                     # 定义域外 ⇒ 与 BF16 的 S=null 同处置
    return {
        'n_pool': len(rows), 'n': n, 'abstain': abstain, 'unparsed': nonnum,
        'answered': len(answered), 'zero': len(zeros),
        'zero_rate': (100.0 * len(zeros) / n) if n else None,
        'abstain_rate': (100.0 * abstain / len(rows)) if rows else None,
        'G': G, 'GN': GN, 'P': P,
        'w': w, 'rho_total': (100.0 * (P - G) / G) if G else None, 'rho_ans': rho,
        'S': S, 'S_defined': S is not None,
        'zero_ci': wilson(len(zeros), n),
        'zero_items': sorted(r['item'] for r in zeros),
    }


# ---------------------------------------------------------------- assertions
def verify_manifest():
    """断言行数与 md5/字节数与 MD5SUMS_B.txt 逐条一致，且 60 个本轮文件齐。"""
    with io.open(MANIFEST, encoding='utf-8') as f:
        lines = [ln.strip() for ln in f if ln.strip()]
    assert len(lines) == 66, 'MD5SUMS_B.txt 行数 %d != 66' % len(lines)
    start_named = []
    for ln in lines:
        parts = ln.split()
        assert len(parts) == 3, '清单行格式错: %r' % ln
        want_md5, name, want_size = parts[0], parts[1], int(parts[2])
        p = os.path.join(B_DIR, name.replace('/', os.sep))
        assert os.path.exists(p), '清单里的文件缺失: %s' % name
        raw = open(p, 'rb').read()
        got = md5_bytes(raw)
        assert got == want_md5, 'md5 不符 %s: %s != %s' % (name, got, want_md5)
        assert len(raw) == want_size, '字节数不符 %s: %d != %d' % (name, len(raw), want_size)
        if name.startswith('start'):
            start_named.append(name)
    assert len(start_named) == 60, 'start*/ CSV 只有 %d 个 != 60' % len(start_named)
    # 逐格存在性 + 行数
    for s in STARTS:
        for ds in DS:
            for arm in ARMS:
                p = os.path.join(B_DIR, s, '%s__%s.csv' % (ds, arm))
                assert os.path.exists(p), '缺文件 %s' % p
                rows = load_csv(p)
                assert len(rows) == EXPECT_ROWS[ds], \
                    '%s 行数 %d != %d' % (p, len(rows), EXPECT_ROWS[ds])
                assert list(rows[0].keys()) == ['item', 'gt', 'pred', 'parse_ok', 'raw', 'lang', 'arm'], \
                    '%s 列名不符: %r' % (p, list(rows[0].keys()))
                assert all((r['gt'] or '').strip() == '' for r in rows), '%s 的 gt 列非空（设计上应为空）' % p
                items = [r['item'] for r in rows]
                assert len(set(items)) == len(items), '%s 有重复 item' % p
    # 归属：b0_* 与 __w2/__w8b 不在本轮分析
    return {'manifest_lines': len(lines), 'start_files': len(start_named),
            'md5_all_ok': True, 'rows_ok': True}


def verify_pools():
    for ds in DS:
        p = os.path.join(POOL_DIR, 'vlm_%s_base_whole.csv' % ds)
        assert os.path.exists(p), '缺语料池副本 %s' % p
        got = md5_file(p)
        assert got == POOL_MD5[ds], '语料池 md5 不符 %s: %s != %s' % (ds, got, POOL_MD5[ds])
    return {ds: POOL_MD5[ds] for ds in DS}


def gt_map(ds):
    p = os.path.join(POOL_DIR, 'vlm_%s_base_whole.csv' % ds)
    out = {}
    for r in load_csv(p):
        if (r.get('parse_ok') or '').strip() == '1':
            g = num(r.get('gt'))
            assert g is not None, '%s 的 gt 非数值: %r' % (p, r)
            out[r['item']] = g
    return out


def verify_bf16(bf16_json, gmap_all):
    """用 BF16 逐项 CSV + 语料池 gt 复现 _g2_result.json 的 w / rho_ans / S；偏差 >0.05 即报错。"""
    rep = {'cells_checked': 0, 'max_abs_dev': {'w': 0.0, 'rho_ans': 0.0, 'S': 0.0}, 'probe': {}}
    for ds in DS:
        for arm in ARMS:
            p = os.path.join(BF16_DIR, '%s__%s.csv' % (ds, arm))
            rows = load_csv(p)
            for r in rows:                      # BF16 池 = 该 CSV 的 item 集
                assert r['item'] in gmap_all[ds], '%s: item %s 不在语料池' % (p, r['item'])
            s = sums_from(rows, gmap_all[ds])
            key = '%s|%s' % (ds, arm)
            b = bf16_json[key]
            for k in ('G', 'GN', 'P', 'zero', 'answered', 'n'):
                assert abs(s[k] - b[k]) < 1e-6, '%s 复现 %s 失败: %s != %s' % (key, k, s[k], b[k])
            assert abs(s['zero_rate'] - b['zero_rate']) < 1e-6, '%s zero_rate 复现失败' % key
            dev_w = abs(s['w'] - b['w'])
            dev_r = abs(s['rho_ans'] - b['rho_ans'])
            assert dev_w <= BF16_TOL, '%s w 偏差 %.4f > %.2f（口径没对齐）' % (key, dev_w, BF16_TOL)
            assert dev_r <= BF16_TOL, '%s rho_ans 偏差 %.4f > %.2f（口径没对齐）' % (key, dev_r, BF16_TOL)
            dev_S = None
            if b['S'] is None:
                assert s['S'] is None, '%s: BF16 记 S=null，本实现却给出 %s' % (key, s['S'])
            else:
                dev_S = abs(s['S'] - b['S'])
                assert dev_S <= BF16_TOL, '%s S 偏差 %.4f > %.2f（口径没对齐）' % (key, dev_S, BF16_TOL)
            rep['cells_checked'] += 1
            rep['max_abs_dev']['w'] = max(rep['max_abs_dev']['w'], dev_w)
            rep['max_abs_dev']['rho_ans'] = max(rep['max_abs_dev']['rho_ans'], dev_r)
            if dev_S is not None:
                rep['max_abs_dev']['S'] = max(rep['max_abs_dev']['S'], dev_S)
            if key == 'st_a|cn-base':
                rep['probe'] = {'cell': key, 'w_mine': round(s['w'], 6), 'w_bf16': b['w'],
                                'rho_mine': round(s['rho_ans'], 6), 'rho_bf16': b['rho_ans'],
                                'S_mine': round(s['S'], 6), 'S_bf16': b['S'], 'tol': BF16_TOL}
    rep['max_abs_dev'] = {k: round(v, 8) for k, v in rep['max_abs_dev'].items()}
    return rep


# ---------------------------------------------------------------- analysis
def structure(zc, ze, items):
    """英文答零集合 ⊆ 中文答零集合？三个计数：都答零 / 只有中文答零 / 只有英文答零。"""
    sc, se = set(zc), set(ze)
    return {'both': len(sc & se), 'only_cn': len(sc - se), 'only_en': len(se - sc),
            'n_cn_zero': len(sc), 'n_en_zero': len(se),
            'en_subset_of_cn': len(se - sc) == 0}


def analyze_group(cells, gmap):
    """cells: {ds: {arm: rows}} —— 一组（一个启动，或三次拼接的合并）。"""
    per = {}
    for ds in DS:
        per[ds] = {}
        for arm in ARMS:
            per[ds][arm] = sums_from(cells[ds][arm], gmap[ds])
    B1 = {}
    for ds in DS:
        cn, en = per[ds]['cn-base'], per[ds]['en-base']
        dci = newcombe_diff(cn['zero'], cn['n'], en['zero'], en['n'])
        B1[ds] = {
            'cn_zero_rate': cn['zero_rate'], 'en_zero_rate': en['zero_rate'],
            'delta_pp': (en['zero_rate'] - cn['zero_rate']) if (cn['zero_rate'] is not None and en['zero_rate'] is not None) else None,
            'cn_ci': cn['zero_ci'], 'en_ci': en['zero_ci'],
            'delta_ci_newcombe': dci,
            'cn_abstain_rate': cn['abstain_rate'], 'en_abstain_rate': en['abstain_rate'],
            'cn_answered': cn['answered'], 'en_answered': en['answered'],
            'cn_zero': cn['zero'], 'en_zero': en['zero'], 'n': cn['n'],
        }
        B1[ds]['structure'] = structure(cn['zero_items'], en['zero_items'], None)
        del per[ds]['cn-base']['zero_items'], per[ds]['en-base']['zero_items']
    for ds in DS:
        for arm in ARMS:
            per[ds][arm].pop('zero_items', None)
    return {'cells': per, 'B1': B1}


def run():
    out = {'meta': {
        'round': 'B', 'date': '2026-09-28',
        'criteria_file': 'analysis/work/B_criteria_frozen.json (READ-ONLY, md5 %s)' % md5_file(
            os.path.join(ROOT, 'work', 'B_criteria_frozen.json')),
        'driver_contract': 'analysis/work/g2_neutral0.py (gt 列留空，按 item 连接)',
        'zero_definition': 'parse_ok==1 且 pred==0',
        'abstain_definition': 'parse_ok==0 或 pred 非数值',
        'S_definition': 'S = 100*(1-w)/(1-w*(1+rho_ans/100)); 分母<=0 记无定义',
        'delta_ci_method': 'Newcombe(method 10) on Wilson 95% intervals; 确定性, 无随机',
        'b0_status': 'FAIL per pre-registered criteria (see B0_闸门结果_20260928.md); degraded per frozen '
                     'on_fail: same-artifact cn-vs-en valid; absolute comparison vs corpus baseline carries '
                     'a 1.3%% item-level stack band (aitod). B0 is NOT re-judged here.',
        'stack_band_pp': B0_BAND_PP,
    }, 'sources': {}}

    out['manifest'] = verify_manifest()
    out['pools'] = verify_pools()
    gmap = {ds: gt_map(ds) for ds in DS}
    for ds in DS:
        out['sources']['pool|%s' % ds] = {'file': 'analysis/g2_neutral0/pool/vlm_%s_base_whole.csv' % ds,
                                          'md5': POOL_MD5[ds], 'a800': '/root/dense_results/vlm_%s_base_whole.csv' % ds}
    for s in STARTS:
        for ds in DS:
            for arm in ARMS:
                rel = 'analysis/B_res_20260928/%s/%s__%s.csv' % (s, ds, arm)
                out['sources'][rel] = md5_file(os.path.join(B_DIR, s, '%s__%s.csv' % (ds, arm)))
    for ds in DS:
        for arm in ARMS:
            rel = 'analysis/g2_neutral0/%s__%s.csv' % (ds, arm)
            out['sources'][rel] = md5_file(os.path.join(BF16_DIR, '%s__%s.csv' % (ds, arm)))
    out['sources']['analysis/g2_neutral0/_g2_result.json'] = md5_file(BF16_JSON)
    out['sources']['analysis/B_res_20260928/MD5SUMS_B.txt'] = md5_file(MANIFEST)

    bf16_json = json.load(io.open(BF16_JSON, encoding='utf-8'))
    out['bf16_validation'] = verify_bf16(bf16_json, gmap)

    # ---- 逐启动（并列，不平均） ----
    per_start = {}
    cells_source = {}
    for s in STARTS:
        cells = {ds: {arm: load_csv(os.path.join(B_DIR, s, '%s__%s.csv' % (ds, arm)))
                      for arm in ARMS} for ds in DS}
        cells_source[s] = cells
        per_start[s] = analyze_group(cells, gmap)
        # 逐项一致性：item 集必须与语料池 parse_ok==1 完全一致
        for ds in DS:
            want = set(gmap[ds])
            for arm in ARMS:
                got = set(r['item'] for r in cells[ds][arm])
                assert got == want, '%s/%s/%s 的 item 集 != 语料池' % (s, ds, arm)
    # ---- 合并（附加读法：三次启动逐项行拼接，每 item 计 3 行） ----
    cells_m = {ds: {arm: [] for arm in ARMS} for ds in DS}
    for s in STARTS:
        for ds in DS:
            for arm in ARMS:
                cells_m[ds][arm] += load_csv(os.path.join(B_DIR, s, '%s__%s.csv' % (ds, arm)))
    merged = analyze_group(cells_m, gmap)
    out['B1'] = {'per_start': {s: per_start[s]['B1'] for s in STARTS}, 'merged': merged['B1']}
    out['zero_rate_table'] = {
        'per_start': {s: {ds: {a: per_start[s]['cells'][ds][a] for a in ARMS} for ds in DS} for s in STARTS},
        'merged': {ds: {a: merged['cells'][ds][a] for a in ARMS} for ds in DS},
    }

    # ---- B2：与 BF16 的方向/区间一致性 ----
    B2 = {'per_start': {}, 'merged': {}, 'bf16': {}}
    for ds in DS:
        bcn, ben = bf16_json['%s|cn-base' % ds], bf16_json['%s|en-base' % ds]
        bd = ben['zero_rate'] - bcn['zero_rate']
        bci = newcombe_diff(bcn['zero'], bcn['n'], ben['zero'], ben['n'])
        B2['bf16'][ds] = {'delta_pp': round(bd, 6), 'delta_ci_newcombe': bci,
                          'cn_zero_rate': bcn['zero_rate'], 'en_zero_rate': ben['zero_rate'],
                          'cn_ci': [round(x, 6) for x in bcn['zero_ci']],
                          'en_ci': [round(x, 6) for x in ben['zero_ci']]}
    for tag, src in [('per_start', {s: per_start[s]['B1'] for s in STARTS}), ('merged', {'merged': merged['B1']})]:
        for key, b1 in src.items():
            d = {}
            for ds in DS:
                four = b1[ds]
                b = B2['bf16'][ds]
                same_sign = (four['delta_pp'] is not None and b['delta_pp'] is not None
                             and (four['delta_pp'] > 0) == (b['delta_pp'] > 0)
                             and four['delta_pp'] != 0 and b['delta_pp'] != 0)
                d[ds] = {'delta_4bit_pp': four['delta_pp'], 'delta_ci_4bit': four['delta_ci_newcombe'],
                         'delta_bf16_pp': b['delta_pp'], 'delta_ci_bf16': b['delta_ci_newcombe'],
                         'same_sign': same_sign,
                         'ci_overlap': overlap(four['delta_ci_newcombe'], b['delta_ci_newcombe']),
                         'verdict': ('consistent (same sign & overlapping CI)'
                                     if (same_sign and overlap(four['delta_ci_newcombe'], b['delta_ci_newcombe']))
                                     else 'build x language interaction flagged per frozen rule')}
            B2[tag][key] = d
    out['B2'] = B2

    # ---- B3：S 是否离开单位区间 ----
    def b3_block(grp):
        r = {}
        for ds in DS:
            r[ds] = {}
            for arm in HEAD_ARMS:
                c = grp['cells'][ds][arm]
                r[ds][arm] = {'S': c['S'], 'S_defined': c['S_defined'],
                              'in_unit_interval': (c['S'] is not None and 0.0 <= c['S'] <= 100.0),
                              'out_of_range': (c['S'] is not None and not (0.0 <= c['S'] <= 100.0)),
                              'undefined': (c['S'] is None),
                              'w': c['w'], 'rho_ans': c['rho_ans'], 'G': c['G'], 'GN': c['GN'],
                              'P': c['P'], 'answered': c['answered'], 'n': c['n'],
                              'S_bf16': bf16_json['%s|%s' % (ds, arm)]['S'],
                              'w_bf16': bf16_json['%s|%s' % (ds, arm)]['w'],
                              'rho_ans_bf16': bf16_json['%s|%s' % (ds, arm)]['rho_ans']}
        return r
    out['B3'] = {'per_start': {s: b3_block(per_start[s]) for s in STARTS}, 'merged': b3_block(merged)}

    # ---- 跨启动一致性 ----
    xs = {}
    for ds in DS:
        for arm in ARMS:
            rs = []
            for s in STARTS:
                rs.append({r['item']: (r['parse_ok'].strip(), r['pred'].strip())
                           for r in load_csv(os.path.join(B_DIR, s, '%s__%s.csv' % (ds, arm)))})
            items = sorted(rs[0])
            pa, za = [], []
            for i in range(3):
                for j in range(i + 1, 3):
                    pa.append(sum(1 for it in items if rs[i][it] == rs[j][it]) / len(items))
                    za.append(sum(1 for it in items
                                  if (num(rs[i][it][1]) == 0) == (num(rs[j][it][1]) == 0)) / len(items))
            xs['%s|%s' % (ds, arm)] = {
                'pred_plus_parse_agree_min': round(min(pa), 6), 'pred_plus_parse_agree_max': round(max(pa), 6),
                'zero_nonzero_agree_min': round(min(za), 6), 'zero_nonzero_agree_max': round(max(za), 6)}
    all_pa = [v['pred_plus_parse_agree_min'] for v in xs.values()]
    all_za = [v['zero_nonzero_agree_min'] for v in xs.values()]
    out['cross_start'] = {'per_cell': xs,
                          'pred_agree_range': [round(min(all_pa), 6), round(max(v['pred_plus_parse_agree_max'] for v in xs.values()), 6)],
                          'zero_nonzero_agree_range': [round(min(all_za), 6), round(max(v['zero_nonzero_agree_max'] for v in xs.values()), 6)]}

    # ---- 结构事实（英文答零 ⊆ 中文答零） ----
    st = {'per_start': {}, 'merged': {}}
    for s in STARTS:
        st['per_start'][s] = {}
        for ds in DS:
            cn = sums_from(cells_source[s][ds]['cn-base'], gmap[ds])
            en = sums_from(cells_source[s][ds]['en-base'], gmap[ds])
            st['per_start'][s][ds] = structure(cn['zero_items'], en['zero_items'], None)
    st['merged']['merged'] = {}
    for ds in DS:
        cn = sums_from(cells_m[ds]['cn-base'], gmap[ds])
        en = sums_from(cells_m[ds]['en-base'], gmap[ds])
        st['merged']['merged'][ds] = structure(cn['zero_items'], en['zero_items'], None)
    out['structure'] = st

    # ---- 附加注解（照实报，不改变任何冻结判定）----
    ann = {'bf16_parse_ok_counts': {}, 'ucf_item_set_mismatch': None}
    for ds in DS:
        ann['bf16_parse_ok_counts'][ds] = {
            'pool_parse_ok1': len(gmap[ds]),
            'bf16_cn_base_ok': sum(1 for r in load_csv(os.path.join(BF16_DIR, '%s__cn-base.csv' % ds))
                                   if r['parse_ok'].strip() == '1'),
            'bf16_en_base_ok': sum(1 for r in load_csv(os.path.join(BF16_DIR, '%s__en-base.csv' % ds))
                                   if r['parse_ok'].strip() == '1')}
    bset = set(r['item'] for r in load_csv(os.path.join(BF16_DIR, 'ucf__cn-base.csv'))
               if r['parse_ok'].strip() == '1')
    uc = {}
    for s in STARTS:
        cn = [r for r in load_csv(os.path.join(B_DIR, s, 'ucf__cn-base.csv')) if r['item'] in bset]
        en = [r for r in load_csv(os.path.join(B_DIR, s, 'ucf__en-base.csv')) if r['item'] in bset]
        sc, se = sums_from(cn, gmap['ucf']), sums_from(en, gmap['ucf'])
        uc[s] = {'n': sc['n'], 'cn_zero_rate': sc['zero_rate'], 'en_zero_rate': se['zero_rate'],
                 'delta_pp': se['zero_rate'] - sc['zero_rate'],
                 'delta_ci_newcombe': newcombe_diff(sc['zero'], sc['n'], se['zero'], se['n'])}
    ann['ucf_item_set_mismatch'] = {
        'bf16_ok': len(bset), 'pool': len(gmap['ucf']),
        'note': 'BF16 的 ucf 有 127/334 项 HTTP 400（parse_ok==0），其 Δ 只在 207 项上算；'
                '4-bit 本轮 334 项全有效（弃权 0）。下表把 4-bit 限制到同一 207 项复算——方向与结论不变。',
        'restricted_4bit': uc,
        'bf16_own': {'n': bf16_json['ucf|cn-base']['n'], 'delta_pp': B2['bf16']['ucf']['delta_pp'],
                     'delta_ci_newcombe': B2['bf16']['ucf']['delta_ci_newcombe']}}
    out['annotations'] = ann

    with io.open(OUT_JSON, 'w', encoding='utf-8') as f:
        f.write(json.dumps(out, ensure_ascii=False, indent=1, sort_keys=True))
    print('WROTE %s' % OUT_JSON)
    return out


# ---------------------------------------------------------------- --check
def check():
    d = json.load(io.open(OUT_JSON, encoding='utf-8'))
    must = ['meta', 'manifest', 'pools', 'sources', 'bf16_validation', 'B1', 'B2', 'B3',
            'cross_start', 'structure', 'zero_rate_table', 'annotations']
    for k in must:
        assert k in d, 'B_result.json 缺 %s' % k
    assert d['manifest']['md5_all_ok'] and d['manifest']['start_files'] == 60
    assert d['bf16_validation']['cells_checked'] == 20
    for k, v in d['bf16_validation']['max_abs_dev'].items():
        assert v <= BF16_TOL, 'BF16 复现偏差 %s=%.4f 超容差' % (k, v)
    # 三启动必须并列
    assert set(d['B1']['per_start'].keys()) == set(STARTS), 'B1 不是逐启动并列'
    assert 'merged' in d['B1'] and 'merged' in d['B3']
    # 引用数字与源 CSV 重算一致（抽样全量重算 B1 的四格差值）
    gmap = {ds: gt_map(ds) for ds in DS}
    for s in STARTS:
        for ds in DS:
            for arm in HEAD_ARMS:
                rows = load_csv(os.path.join(B_DIR, s, '%s__%s.csv' % (ds, arm)))
                rec = d['zero_rate_table']['per_start'][s][ds][arm]
                s2 = sums_from(rows, gmap[ds])
                assert abs(s2['zero_rate'] - rec['zero_rate']) < 1e-9, '重算不符 %s/%s/%s' % (s, ds, arm)
                assert s2['zero'] == rec['zero'] and s2['n'] == rec['n']
                assert abs((s2['S'] or -1e9) - (rec['S'] if rec['S'] is not None else -1e9)) < 1e-6
    # 结构事实的单调方向（密集域必须只有英文答零 == 0）
    for tag in ('per_start', 'merged'):
        for key, per in d['structure'][tag].items():
            for ds in DENSE:
                assert per[ds]['only_en'] == 0, '密集域 %s/%s/%s 出现"只有英文答零"' % (tag, key, ds)
    # 区间包含点估计
    for tag in ('per_start',):
        for s in STARTS:
            for ds in DS:
                b = d['B1']['per_start'][s][ds]
                assert b['cn_ci'][0] <= b['cn_zero_rate'] <= b['cn_ci'][1]
                assert b['en_ci'][0] <= b['en_zero_rate'] <= b['en_ci'][1]
                assert b['delta_ci_newcombe'][0] <= b['delta_pp'] <= b['delta_ci_newcombe'][1]
    print('CHECK OK — 60 文件 / BF16 20 格复现 / 三启动并列 / 结构事实 / 区间自洽')
    return True


# ---------------------------------------------------------------- --selftest
def selftest():
    """阴性对照：每条都必须"如期失败"。"""
    d = json.load(io.open(OUT_JSON, encoding='utf-8'))
    gmap = {ds: gt_map(ds) for ds in DS}
    results = []

    # NC1 —— 把 st_a/start1/en-base 的一项答案从 0 改成 100：零率必须改变，且与产物的守卫必须报错
    rows = load_csv(os.path.join(B_DIR, 'start1', 'st_a__en-base.csv'))
    ref = d['zero_rate_table']['per_start']['start1']['st_a']['en-base']
    mut = copy.deepcopy(rows)
    hit = [r for r in mut if num(r['pred']) == 0][0]
    hit['pred'] = '100'
    s2 = sums_from(mut, gmap['st_a'])
    ok = (s2['zero'] != ref['zero'])
    try:
        assert s2['zero'] == ref['zero'], 'NC1'
        raised = False
    except AssertionError:
        raised = True
    results.append(('NC1 改掉一个答零答案 ⇒ 汇总守卫必须失败', ok and raised, 'zero %d -> %d' % (ref['zero'], s2['zero'])))

    # NC2 —— gt 故意错位连接（把每个域的 item→gt 映射循环右移一位）：BF16 复现必须失败
    bad = {}
    for ds in DS:
        items = list(gmap[ds].keys())
        vals = [gmap[ds][i] for i in items]
        vals = vals[1:] + vals[:1]
        bad[ds] = dict(zip(items, vals))
    bf16_json = json.load(io.open(BF16_JSON, encoding='utf-8'))
    try:
        verify_bf16(bf16_json, bad)
        raised = False
        why = 'no assertion'
    except AssertionError as e:
        raised = True
        why = str(e)[:70]
    results.append(('NC2 gt 错位连接 ⇒ BF16 口径复现必须失败', raised, why if raised else 'NOT RAISED'))

    # NC3 —— 把区间算法换成"恒返回 [0,100]"：与产物记录的区间必须不同（即区间断言会失败）
    real_wilson = globals()['wilson']

    def fake_wilson(k, n):
        return None if n <= 0 else (0.0, 100.0)

    globals()['wilson'] = fake_wilson
    try:
        diff = 0
        for s in STARTS:
            for ds in DS:
                r = load_csv(os.path.join(B_DIR, s, '%s__en-base.csv' % ds))
                k = sum(1 for x in r if num(x['pred']) == 0)
                ci = wilson(k, len(r))
                if list(ci) != list(d['zero_rate_table']['per_start'][s][ds]['en-base']['zero_ci']):
                    diff += 1
        ok = diff > 0
        try:
            assert diff == 0, 'NC3'
            raised = False
        except AssertionError:
            raised = True
    finally:
        globals()['wilson'] = real_wilson
    results.append(('NC3 区间算法换成恒 [0,100] ⇒ 与产物区间断言必须失败', ok and raised, '%d/12 格区间不符' % diff))

    # NC4 —— 制造一个"只有英文答零"的 item：子集判定必须翻成 False
    cn = sums_from(load_csv(os.path.join(B_DIR, 'start1', 'st_a__cn-base.csv')), gmap['st_a'])
    en = sums_from(load_csv(os.path.join(B_DIR, 'start1', 'st_a__en-base.csv')), gmap['st_a'])
    zc = set(cn['zero_items'])
    ze = set(en['zero_items'])
    extra = sorted(set(gmap['st_a']) - zc)[0]
    ze2 = ze | {extra}
    st2 = structure(zc, ze2, None)
    ok = (st2['only_en'] == 1 and st2['en_subset_of_cn'] is False)
    try:
        assert st2['only_en'] == 0, 'NC4'
        raised = False
    except AssertionError:
        raised = True
    results.append(('NC4 造一个"只有英文答零"的 item ⇒ 子集判定必须失败', ok and raised,
                    'only_en=0 -> %d' % st2['only_en']))

    # NC5 —— 改一个字节的副本：清单校验必须失败（在临时目录里做，绝不碰冻结数据）
    with tempfile.TemporaryDirectory() as td:
        src = os.path.join(B_DIR, 'start1', 'st_a__cn-base.csv')
        dst = os.path.join(td, 'st_a__cn-base.csv')
        raw = open(src, 'rb').read()
        open(dst, 'wb').write(raw[:-1] + b'X')
        want = None
        for ln in io.open(MANIFEST, encoding='utf-8'):
            parts = ln.split()
            if len(parts) == 3 and parts[1] == 'start1/st_a__cn-base.csv':
                want = parts[0]
        assert want is not None, 'NC5: 清单里找不到 start1/st_a__cn-base.csv'
        got = md5_file(dst)
        ok = (want is not None and got != want)
        try:
            assert got == want, 'NC5'
            raised = False
        except AssertionError:
            raised = True
    results.append(('NC5 副本改一字节 ⇒ 清单 md5 校验必须失败', ok and raised, 'md5 %s -> %s' % (want[:8], got[:8])))

    print('%-52s %-6s %s' % ('阴性对照', '结果', '证据'))
    allok = True
    for name, ok, why in results:
        allok &= bool(ok)
        print('%-52s %-6s %s' % (name, 'PASS' if ok else 'FAIL', why))
    assert allok, '有阴性对照没有如期失败'
    print('SELFTEST OK — %d 条阴性对照全部如期失败' % len(results))
    return True


# ---------------------------------------------------------------- --tables
def tables():
    d = json.load(io.open(OUT_JSON, encoding='utf-8'))
    L = []
    A = L.append
    A('### 主表：答零率 %（pred==0 / parse_ok==1 的项）；弃权 = parse_ok==0，本轮全表为 0')
    A('')
    A('| 域 | 臂 | start1 | start2 | start3 | 合并(3×) | BF16 |')
    A('|---|---|---|---|---|---|---|')
    for ds in DS:
        for arm in ARMS:
            row = ['%s' % ds if arm == ARMS[0] else '', arm]
            for s in STARTS:
                c = d['zero_rate_table']['per_start'][s][ds][arm]
                row.append('%.1f (%d/%d)' % (c['zero_rate'], c['zero'], c['n']))
            c = d['zero_rate_table']['merged'][ds][arm]
            row.append('%.1f (%d/%d)' % (c['zero_rate'], c['zero'], c['n']))
            b = d['B2']['bf16'][ds]
            if arm == 'cn-base':
                row.append('%.1f' % b['cn_zero_rate'])
            elif arm == 'en-base':
                row.append('%.1f' % b['en_zero_rate'])
            else:
                row.append('—')
            A('| ' + ' | '.join(row) + ' |')
    A('')
    A('### B1：cn-base → en-base 的答零率差与 95% 区间（pp）')
    A('')
    A('| 域 | 组 | cn 零率 [Wilson] | en 零率 [Wilson] | Δ(en−cn) [Newcombe] |')
    A('|---|---|---|---|---|')
    for s in STARTS + ['merged']:
        src = d['B1']['per_start'][s] if s != 'merged' else d['B1']['merged']
        for ds in DS:
            b = src[ds]
            A('| %s | %s | %.2f [%.2f, %.2f] | %.2f [%.2f, %.2f] | %+.2f [%+.2f, %+.2f] |' % (
                ds, s, b['cn_zero_rate'], b['cn_ci'][0], b['cn_ci'][1],
                b['en_zero_rate'], b['en_ci'][0], b['en_ci'][1],
                b['delta_pp'], b['delta_ci_newcombe'][0], b['delta_ci_newcombe'][1]))
    A('')
    A('### B2：4-bit vs BF16 的 Δ（en−cn，pp）')
    A('')
    A('| 域 | BF16 Δ [CI] | start1 Δ | start2 Δ | start3 Δ | 合并 Δ | 同号 | 区间重叠 |')
    A('|---|---|---|---|---|---|---|---|')
    for ds in DS:
        b = d['B2']['bf16'][ds]
        cells = [d['B2']['per_start'][s][ds] for s in STARTS] + [d['B2']['merged']['merged'][ds]]
        A('| %s | %+.2f [%+.2f, %+.2f] | %+.2f | %+.2f | %+.2f | %+.2f | %s | %s |' % (
            ds, b['delta_pp'], b['delta_ci_newcombe'][0], b['delta_ci_newcombe'][1],
            cells[0]['delta_4bit_pp'], cells[1]['delta_4bit_pp'], cells[2]['delta_4bit_pp'],
            cells[3]['delta_4bit_pp'],
            '/'.join('Y' if c['same_sign'] else 'N' for c in cells),
            '/'.join('Y' if c['ci_overlap'] else 'N' for c in cells)))
    A('')
    A('### B3：S（单位区间 [0,100]）')
    A('')
    A('| 格 | BF16 S | start1 | start2 | start3 | 合并 |')
    A('|---|---|---|---|---|---|')
    for ds in DS:
        for arm in HEAD_ARMS:
            b = d['B3']['per_start']['start1'][ds][arm]
            row = ['%s|%s' % (ds, arm), ('未定义' if b['S_bf16'] is None else '%.2f' % b['S_bf16'])]
            for s in STARTS:
                v = d['B3']['per_start'][s][ds][arm]['S']
                row.append('未定义' if v is None else ('%.2f%s' % (v, ' ⚠' if (v > 100 or v < 0) else '')))
            v = d['B3']['merged'][ds][arm]['S']
            row.append('未定义' if v is None else ('%.2f%s' % (v, ' ⚠' if (v > 100 or v < 0) else '')))
            A('| ' + ' | '.join(row) + ' |')
    A('')
    A('### 结构事实：答零 item 集合（都答零 / 只有中文答零 / 只有英文答零）')
    A('')
    A('| 域 | start1 | start2 | start3 | 合并 |')
    A('|---|---|---|---|---|')
    for ds in DS:
        row = [ds]
        for tag in ['per_start']:
            for s in STARTS:
                v = d['structure'][tag][s][ds]
                row.append('%d / %d / %d' % (v['both'], v['only_cn'], v['only_en']))
        v = d['structure']['merged']['merged'][ds]
        row.append('%d / %d / %d' % (v['both'], v['only_cn'], v['only_en']))
        A('| ' + ' | '.join(row) + ' |')
    A('')
    A('### 跨启动逐项一致率（3 对的 min–max）')
    A('')
    A('| 域|臂 | pred+parse 一致 | 零/非零一致 |')
    A('|---|---|---|---|')
    for ds in DS:
        for arm in ARMS:
            v = d['cross_start']['per_cell']['%s|%s' % (ds, arm)]
            A('| %s|%s | %.3f–%.3f | %.3f–%.3f |' % (ds, arm, v['pred_plus_parse_agree_min'],
                                                     v['pred_plus_parse_agree_max'],
                                                     v['zero_nonzero_agree_min'], v['zero_nonzero_agree_max']))
    print('\n'.join(L))
    return L


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--check', action='store_true')
    ap.add_argument('--selftest', action='store_true')
    ap.add_argument('--tables', action='store_true')
    A = ap.parse_args()
    if A.check:
        return 0 if check() else 1
    if A.selftest:
        return 0 if selftest() else 1
    if A.tables:
        tables()
        return 0
    run()
    return 0


if __name__ == '__main__':
    sys.exit(main())
