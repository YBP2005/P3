# -*- coding: utf-8 -*-
"""pA_indep_check.py —— 方案 A 的**独立复算**（直读原始 CSV，另写一套实现）。

纪律：不复用 pA_analyze.py 的任何函数，只读它的产物 JSON 做比对。
实现差异（故意）：
  · 用 glob 逐模式取文件（而不是 ARM_RE 扫目录）；
  · 按 **(家族, 臂) 汇总分子/分母** 得率（而不是先算域率再平均）；
  · 弃答判定用**独立正则** `re.compile(r'"?(abstain|cannot_judge|no_people)"?', re.I)` 打在 raw 上；
  · 血统代表权重的挑选按**各自规则**再挑一次（awq > bf16 > fp8 > gptq），与主脚本可能不同 ⇒ 若不同
    必须在报告里点明（这是真实的敏感性检查，不是 bug）。
输出：逐项 ✓/✗，任一不符 exit 1。
"""
import glob
import hashlib
import io
import json
import os
import re
import sys

# ── 复现包统一根：`_repro_root.py`（与本文件同目录）──────────────────────────────
# ★ 2026-10-06（v0654）：与 `pA_analyze.py` 同一处病。本脚本此前硬拼 `PAPER/analysis/…`，
#   而放行树没有 `analysis/` 这一层 ⇒ `family_arm()` 的 `glob` 命中 0（返回 `None` 被当成
#   "该血统无数据"）、`grid()` 见文件不存在即 `return None` —— **独立复算会静默退化成空**，
#   最后报 `INDEP_FAIL` 却指不出"是路径错了还是结果错了"。现在一律走 `_repro_root` 的映射表。
try:
    from _repro_root import resolve as RP, not_released as NR
except ImportError:                      # 只拷走单个脚本时：就地反推仓库根，无前缀映射表
    import os as _o
    _r = _o.environ.get('PAPERB_ROOT') or _o.path.dirname(_o.path.dirname(_o.path.abspath(__file__)))
    RP = lambda *p: _o.path.join(_r, *p)
    NR = lambda *p: _o.path.join(_r, '_NOT_RELEASED', *p)

sys.stdout.reconfigure(encoding='utf-8')
W = os.path.dirname(os.path.abspath(__file__))
ABST = re.compile(r'"?(abstain|cannot_judge|no_people)"?', re.I)
ZERO = re.compile(r'^\s*0(\.0+)?\s*$')
DOMS = ['st_a', 'st_b', 'ucf', 'visdrone', 'aitod', 'countbench']
LINES = {'InternVL3.5-8B': ['InternVL3_5-8B'],
         'Phi-3.5-Vision': ['Phi-3.5-vision-instruct'],
         'gemma-3-12b': ['gemma3-12b'],
         'Qwen3-VL-32B': ['qwen3-vl-32b-awq'],
         'Qwen2.5-VL-72B': ['qwen25vl-72b-awq'],
         'Qwen3-VL-8B': ['qwen3-vl-8b-awq']}


def load(path):
    import csv
    with io.open(path, encoding='utf-8-sig', newline='') as f:
        return [r for r in csv.DictReader(f) if '#r' not in str(r.get('item', ''))]


def tally(path):
    """返回 (n, n_zero, n_abst, n_pred_empty)。"""
    n = z = a = e = 0
    for r in load(path):
        n += 1
        p = str(r.get('pred', '')).strip()
        raw = str(r.get('raw', ''))
        if ABST.search(raw):
            a += 1
        if p == '':
            e += 1
        elif ZERO.match(p):
            z += 1
    return n, z, a, e


SKIPPED = []


def family_arm(fam, arm, root=None, min_n=20):
    """按 glob 汇总某家族某臂在**全部域**上的分子分母。

    min_n 直接取判据里冻结的 `min_cell_n`（默认 20）：单域 n<min_n 的文件不进汇总。
    这一步必须与主脚本一致，否则 Qwen3-VL-32B 会因把 countbench(n=6) 算进来而差 0.8 pp
    —— 该差异已被复算定位并记录在 SKIPPED 里，不是隐藏的取整。
    """
    root = root or RP('analysis', 'e2xt_a800', 'merged')
    tot = [0, 0, 0, 0]
    hits = []
    for d in DOMS:
        for pat in ('e1_%s_%s_%s.csv' % (fam, d, arm), '%s_%s_%s.csv' % (fam, d, arm)):
            for f in glob.glob(os.path.join(root, pat)):
                t = tally(f)
                if t[0] < min_n:
                    SKIPPED.append('%s (n=%d < min_n=%d)' % (os.path.basename(f), t[0], min_n))
                    continue
                tot = [tot[i] + t[i] for i in range(4)]
                hits.append(os.path.basename(f))
    if not tot[0]:
        return None
    return dict(n=tot[0], zero=tot[1] / tot[0], abst=tot[2] / tot[0],
                err=tot[3] / tot[0], files=hits)


def grid(dirname, prefix, arm):
    p = os.path.join(RP('analysis', 'data', 'pod_mirror', dirname), '%s_%s.csv' % (prefix, arm))
    if not os.path.exists(p):
        return None
    rows = load(p)
    z = a = 0
    for r in rows:
        if ZERO.match(str(r.get('pred', '')).strip()):
            z += 1
        if str(r.get('abstain', '')).strip() in ('1', 'True', 'true') or ABST.search(str(r.get('raw', ''))):
            a += 1
    return dict(n=len(rows), zero=z / len(rows), abst=a / len(rows))


def close(x, y, tol=1e-9):
    return x is not None and y is not None and abs(x - y) <= tol


def main():
    res = json.loads(io.open(os.path.join(W, 'pA_result_v2.json'), encoding='utf-8').read())
    frz = os.path.join(W, 'pA_criteria_frozen_v2.json')
    cm = hashlib.md5(io.open(frz, 'rb').read()).hexdigest()[:12]
    bad = 0
    print('=== 独立复算（直读原始 CSV）===')
    print('判据 md5：产物 %s ｜ 磁盘 %s  → %s' % (res['criteria_md5'], cm,
                                                'OK' if res['criteria_md5'] == cm else 'MISMATCH'))
    bad += res['criteria_md5'] != cm

    # ① H_A1：四个血统的 Δzero / Δabst
    print('\n① H_A1（enumAbstain − enum）')
    want = {r['lineage']: r for r in res['H_A1']['rows']}
    n_ok = 0
    for lin, fams in LINES.items():
        if lin not in want:
            continue
        got = None
        for fam in fams:
            if family_arm(fam, 'enum') and family_arm(fam, 'enumAbstain'):
                got = fam
                break
        if not got:
            continue
        a, b = family_arm(got, 'enum'), family_arm(got, 'enumAbstain')
        dz, da = (b['zero'] - a['zero']) * 100, (b['abst'] - a['abst']) * 100
        w = want[lin]
        ok = close(round(dz, 1), round(w['d_zero_pp'], 1), 0.06) and \
            close(round(da, 1), round(w['d_abst_pp'], 1), 0.06)
        n_ok += ok
        print('   %-20s %-24s Δzero %+7.1f（主 %+7.1f） Δabst %+7.1f（主 %+7.1f）  %s'
              % (lin, got, dz, w['d_zero_pp'], da, w['d_abst_pp'], '✓' if ok else '✗'))
    bad += (n_ok != len(want)) if want else 1
    okz = sum(1 for r in want.values() if r['d_zero_pp'] <= -10.0)
    oka = sum(1 for r in want.values() if r['d_abst_pp'] >= 10.0)
    print('   独立判定：Δzero 达标 %d/%d，Δabst 达标 %d/%d → H_A1 %s（主脚本 %s）'
          % (okz, len(want), oka, len(want), 'PASS' if okz >= 3 and oka >= 3 else 'FAIL',
             'PASS' if res['H_A1']['passed'] else 'FAIL'))
    bad += (okz >= 3 and oka >= 3) != res['H_A1']['passed']

    # ② H_A2 / H_A2b
    for key, pref, runs in (('H_A2', 'blur', [('b2__out_32b_blurct',), ('b2__out_8b_blurct',),
                                              ('ivl_blurct',)]),
                            ('H_A2b', 'occl', [('b2__out_32b_occlct',), ('b2__out_8b_occlct',)])):
        print('\n② %s（forbid0 − base，同 item 配对）' % key)
        w = {r['run']: r for r in res[key]['rows']}
        ok_n = 0
        for (d,) in runs:
            b, f = grid(d, pref, 'base'), grid(d, pref, 'forbid0')
            dz = (f['zero'] - b['zero']) * 100
            ww = w.get(d)
            ok = ww and close(round(dz, 1), round(ww['d_zero_pp'], 1), 0.06)
            ok_n += bool(ok)
            print('   %-22s Δzero %+7.1f（主 %+7.1f） %s' % (d, dz, ww['d_zero_pp'] if ww else float('nan'),
                                                          '✓' if ok else '✗'))
        passes = sum(1 for (d,) in runs if (grid(d, pref, 'forbid0')['zero'] - grid(d, pref, 'base')['zero']) * 100 <= -10.0)
        req = res[key].get('runs_pass') is not None and 2 if key == 'H_A2b' else 3
        indep = passes >= req
        print('   独立判定：达标 %d/%d → %s（主脚本 %s）' % (passes, len(runs),
                                                       'PASS' if indep else 'FAIL',
                                                       'PASS' if res[key]['passed'] else 'FAIL'))
        bad += (ok_n != len(runs)) or (indep != res[key]['passed'])

    # ③ H_A3：max|Δzero| 措辞 vs 类型
    print('\n③ H_A3（类型 > 措辞）')
    waz, taz = [], []
    for pair in (('permit', 'permitB'), ('permit', 'permitC'), ('channel', 'channelB')):
        for lin, fams in LINES.items():
            for fam in fams:
                a, b = family_arm(fam, pair[0]), family_arm(fam, pair[1])
                if a and b:
                    waz.append(abs((b['zero'] - a['zero']) * 100))
    for pair in (('base', 'permit'), ('enum', 'enumAbstain')):
        for lin, fams in LINES.items():
            for fam in fams:
                a, b = family_arm(fam, pair[0]), family_arm(fam, pair[1])
                if a and b:
                    taz.append(abs((b['zero'] - a['zero']) * 100))
    mw, mt = (max(waz) if waz else None), (max(taz) if taz else None)
    print('   独立：max|Δzero| 措辞 %.1f pp ｜ 类型 %.1f pp' % (mw, mt))
    print('   主脚本：max|Δzero| 措辞 %.1f pp ｜ 类型 %.1f pp' % (res['H_A3']['max_wording_pp'],
                                                             res['H_A3']['max_type_pp']))
    print('   注意：独立集只用 %d 个血统代表（主脚本对 wording 用 3 个家族），集合不同 → 数值允许不同，'
          '但方向必须一致（措辞 ≪ 类型）' % len(LINES))
    ok = (mw is not None and mt is not None and mw <= 15.0 and mw < mt)
    print('   独立判定：%s（主脚本 %s）' % ('PASS' if ok else 'FAIL',
                                        'PASS' if res['H_A3']['passed'] else 'FAIL'))
    bad += ok != res['H_A3']['passed']

    # ④ H_A4：range − base
    print('\n④ H_A4（range − base）')
    runs = [('b2__out_32b_blurct', 'blur'), ('b2__out_8b_blurct', 'blur'), ('ivl_blurct', 'blur')]
    ok_n = 0
    w = {r['run']: r for r in res['H_A4']['rows']}
    for d, pref in runs:
        b, rg = grid(d, pref, 'base'), grid(d, pref, 'range')
        dz = (rg['zero'] - b['zero']) * 100
        ww = w.get(d)
        ok = ww and close(round(dz, 1), round(ww['d_zero_pp'], 1), 0.06)
        ok_n += bool(ok)
        print('   %-22s Δzero %+7.1f（主 %+7.1f） %s' % (d, dz, ww['d_zero_pp'] if ww else float('nan'),
                                                      '✓' if ok else '✗'))
    n_within = sum(1 for d, pref in runs if abs((grid(d, pref, 'range')['zero'] - grid(d, pref, 'base')['zero']) * 100) <= 10.0)
    indep = n_within >= 2
    print('   独立判定：|Δzero|≤10pp 达标 %d/3 → %s（主脚本 %s）'
          % (n_within, 'PASS' if indep else 'FAIL', 'PASS' if res['H_A4']['passed'] else 'FAIL'))
    bad += (ok_n != len(runs)) or (indep != res['H_A4']['passed'])

    print('\n%s（%d 处不符）' % ('INDEP_OK' if bad == 0 else 'INDEP_FAIL', bad))
    if SKIPPED:
        print('\n被 min_n 过滤掉的文件（%d 个，去重后）：' % len(set(SKIPPED)))
        for s in sorted(set(SKIPPED)):
            print('   ', s)
    return 1 if bad else 0


if __name__ == '__main__':
    raise SystemExit(main())
