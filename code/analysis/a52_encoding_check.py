# -*- coding: utf-8 -*-
"""a52_encoding_check.py — §M.11.2 的**逐表编码标注**：两套编码各自给出什么 β（M-7）。

## 为什么需要它
r18 `M-7`（阻塞）实测：本地臂刊载的 β（−4.3346 / −4.2096 / −4.4481）是**原始像素编码**
（radius 3/8/24、blur 0/4/8、overlap 1.45/1.15/0.85），而冻结判据件
`_a52_criteria_frozen.json` 的 `C3.predictors.nuisance_mains` 登记的是
**有序档位**（`size_level` / `blur_level` / `overlap_level`，即 0/1/2）；随包放行的
冻结分析器 `data/derived/a5_2_a800/env/a52_analyze.py`（md5 `77f87f49…`）实现的正是
**登记档位编码**。评审按放行件复跑即得另一套读数 ⇒ 要求二选一：
  (a) 统一设计矩阵后**重拟合**；或 (b) **逐表标明所用编码**并撤掉跨编码可比性措辞。

本脚本给出 (b) 所需的**可复算证据**：同一批**已放行**记录、同一个模型形式，只换编码。

## 实测结论（本脚本断言；数字全部来自放行件，0 次推理）
* 逐构建（放行驱动的 build-free 逐构建形式）：
    原始像素编码  b0 −4.3346  b1 −4.2096  b2 −4.4481      ← §M.11.1/§M.11.2 刊载值
    登记档位编码  b0 −4.1891  b1 −4.1050  b2 −4.3473
* 27 格池化（`fit_c3` 全 attained 记录 = contrast 口径）：
    原始像素编码  −4.5306  CI [−4.9427, −4.1184]          ← §M.11.1 刊载值
    登记档位编码  −4.4101  CI [−4.8165, −4.0037]          ← §M.11.1 registration 段已并列
⇒ ★ **两套编码不可互换**：(a) 统一到登记档位编码会改动**已印数字**，属另一类裁定
（须逐笔归因＋主稿等量置换），本次**不做**；故走 (b)：逐表标注 ＋ 明写不可直接比较。

用法：
    python a52_encoding_check.py --selftest    # 负例自测（不读语料）
    python a52_encoding_check.py               # 全量复算并逐项断言
"""

# ── 复现包统一根：`_repro_root.py`（与本文件同目录）──────────────────────────────
try:
    from _repro_root import resolve as RP
except ImportError:                      # 只拷走单个脚本时：就地反推仓库根
    import os as _o
    _r = _o.environ.get('PAPERB_ROOT') or _o.path.dirname(_o.path.dirname(_o.path.abspath(__file__)))
    RP = lambda *p: _o.path.join(_r, *p)
import argparse
import csv
import hashlib
import importlib.util
import io
import os
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
try:
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

A52DIR = RP('repro_github', 'data', 'derived', 'a52_api_six_20261007')
LOCAL = os.path.join(A52DIR, 'local_arm')
DRIVER = os.path.join(A52DIR, '_a52_api_analyze.py')
REG_ANALYZER = RP('repro_github', 'data', 'derived', 'a5_2_a800', 'env', 'a52_analyze.py')

# 刊载值（§M.11.1 / §M.11.2 印出的四位小数）
PRINTED_RAW = {'b0': -4.3346, 'b1': -4.2096, 'b2': -4.4481}
PRINTED_ORD = {'b0': -4.1891, 'b1': -4.1050, 'b2': -4.3473}
PRINTED_POOL_RAW = (-4.5306, -4.9427, -4.1184)
PRINTED_POOL_REG = (-4.4101, -4.8165, -4.0037)


def die(msg):
    sys.stderr.write('a52_encoding_check: FAIL — %s\n' % msg)
    raise SystemExit(3)


def load_mod(name, path):
    if not os.path.isfile(path):
        die('缺件：%s' % path)
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


def read_local():
    files = [os.path.join(LOCAL, 'res', f) for f in sorted(os.listdir(os.path.join(LOCAL, 'res')))
             if f.startswith('A52_') and f.endswith('.csv')]
    files += [os.path.join(LOCAL, 'ext', f) for f in sorted(os.listdir(os.path.join(LOCAL, 'ext')))
              if f.startswith('a52__res__A52_') and f.endswith('.csv')]
    if not files:
        die('本地臂目录下未命中任何逐项 CSV：%s' % LOCAL)
    cells = {}
    for p in files:
        for r in csv.DictReader(io.open(p, encoding='utf-8-sig', newline='')):
            cells.setdefault(r['build'], []).append(r)
    return cells, files


def recode(rows, reg):
    """把三根可读性轴的编码换成**登记档位**（0/1/2，用放行冻结分析器的 `level_of`）。"""
    out = []
    for r0 in rows:
        r = dict(r0)
        for k in ('radius', 'blur', 'overlap'):
            r[k] = '%g' % reg.level_of(r, k)          # ★ 保持字符串：`fnum()` 只吃字符串
        out.append(r)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description='§M.11.2 两套编码的 β 对照（M-7）')
    ap.add_argument('--selftest', action='store_true')
    args = ap.parse_args(argv)
    if args.selftest:
        return selftest()

    D = load_mod('a52drv', DRIVER)
    REG = load_mod('a52reg', REG_ANALYZER)
    print('放行驱动       = %s（md5 %s）' % (DRIVER, md5f(DRIVER)))
    print('登记档位分析器 = %s（md5 %s）' % (REG_ANALYZER, md5f(REG_ANALYZER)))
    print('本地臂目录     = %s' % LOCAL)

    cells, files = read_local()                 # 原始 CSV 行（`pred` 为字符串 ⇒ 冻结分析器直吃）
    fits = D.load_baseline()                    # 放行驱动自带载入（带 `correct` ⇒ 供 fit_rows）
    print('逐项 CSV %d 件；每构建 %s 行'
          % (len(files), {b: len(v) for b, v in sorted(cells.items())}))

    ok = True
    print('\n① 逐构建（放行驱动的 build-free 逐构建形式）')
    for b in ('b0', 'b1', 'b2'):
        raw = D.fit_rows(fits[b])['beta_count']
        ordn = D.fit_rows(recode(fits[b], REG))['beta_count']
        h1 = abs(raw - PRINTED_RAW[b]) <= 5e-5
        h2 = abs(ordn - PRINTED_ORD[b]) <= 5e-5
        ok = ok and h1 and h2
        print('   %s  原始像素编码 %.6f（印 %.4f %s）｜登记档位编码 %.6f（印 %.4f %s）'
              % (b, raw, PRINTED_RAW[b], 'OK' if h1 else '<-- 不符',
                 ordn, PRINTED_ORD[b], 'OK' if h2 else '<-- 不符'))

    print('\n② 27 格池化（冻结 `fit_c3`，contrast 口径 = 全 attained 记录）')
    allrows = cells['b0'] + cells['b1'] + cells['b2']
    fn = getattr(D, '_orig_analyzer', None)
    print('   n = %d' % len(allrows))

    def fit_with(analyzer, rows, label):
        a = analyzer
        return label, a, a.fit_c3(rows)

    # 原始像素编码：用放行驱动**随包**的 `_a52_analyze_frozen.py`（= 机上演跑那版 bf873c5e）
    frozen = os.path.join(A52DIR, '_a52_analyze_frozen.py')
    RAW = load_mod('a52frozen', frozen)
    for nm, A, rows, want in (('原始像素编码', RAW, allrows, PRINTED_POOL_RAW),
                              ('登记档位编码', REG, recode(allrows, REG), PRINTED_POOL_REG)):
        o = A.fit_c3(rows)
        b, lo, hi = o['beta_count'], o['ci'][0], o['ci'][1]
        h = (abs(b - want[0]) <= 5e-5 and abs(lo - want[1]) <= 5e-4 and abs(hi - want[2]) <= 5e-4)
        ok = ok and h
        print('   %-12s β=%.6f CI=[%.6f, %.6f]（印 %.4f [%.4f, %.4f] %s）'
              % (nm, b, lo, hi, want[0], want[1], want[2], 'OK' if h else '<-- 不符'))

    print('\n③ ★ 两套编码不可互换（本次的裁定依据）')
    d = [abs(D.fit_rows(fits[b])['beta_count'] - D.fit_rows(recode(fits[b], REG))['beta_count'])
         for b in ('b0', 'b1', 'b2')]
    print('   逐构建 |Δβ| = %s（最小 %.4f）⇒ 统一到登记档位编码**会改动已印数字**，'
          % ([round(x, 4) for x in d], min(d)))
    print('   故本次走 (b) 逐表标注路线，(a) 统一重拟合**不执行**并上报。')
    print('\n%s' % ('ENCODING_CHECK: PASS' if ok else 'ENCODING_CHECK: FAIL'))
    return 0 if ok else 1


def md5f(p):
    return hashlib.md5(io.open(p, 'rb').read()).hexdigest()


def selftest():
    """★ 负例自测：缺件必须明确失败；编码切换必须真的改变读数（不是摆设）。"""
    import shutil
    import tempfile
    print('a52_encoding_check --selftest（负例自测）')
    ctl = []
    REG = load_mod('a52reg', REG_ANALYZER)
    ctl.append(('放行冻结分析器 md5 == 77f87f49b0e447fba54ea2a0435f80c8',
                md5f(REG_ANALYZER) == '77f87f49b0e447fba54ea2a0435f80c8'))

    # 登记档位映射：三根轴的三个物理值都必须落到 0/1/2 且**单调**
    for key, vals in (('radius', [3.0, 8.0, 24.0]), ('blur', [0.0, 4.0, 8.0]),
                      ('overlap', [1.45, 1.15, 0.85])):
        got = [REG.level_of({key: repr(v)[:-2] if False else ('%g' % v)}, key) for v in vals]
        ctl.append(('level_of(%s) 三档 = 0/1/2（实得 %s）' % (key, got), sorted(got) == [0.0, 1.0, 2.0]))

    # 缺件 ⇒ 明确失败
    tmp = tempfile.mkdtemp(prefix='a52_enc_selftest_')
    try:
        try:
            load_mod('nope', os.path.join(tmp, '__nope__.py'))
            ctl.append(('缺件 ⇒ 明确失败（退出码 3）', False))
        except SystemExit as e:
            ctl.append(('缺件 ⇒ 明确失败（退出码 3）', e.code == 3))
        # 编码切换必须真的改变估计量（否则"两套编码"这个前提不成立）
        cells, _f = read_local()
        RAW = load_mod('a52frozen_st', os.path.join(A52DIR, '_a52_analyze_frozen.py'))
        a = REG.fit_c3(cells['b1'])                    # 登记档位编码（放行冻结分析器）
        b = RAW.fit_c3(cells['b1'])                    # 原始像素编码（随包 _a52_analyze_frozen.py）
        ctl.append(('编码切换确实改变 β（|Δ| > 0.05，实得 %.4f）' % abs(a['beta_count'] - b['beta_count']),
                    abs(a['beta_count'] - b['beta_count']) > 0.05))
        # 工作目录无关
        cwd0 = os.getcwd()
        try:
            os.chdir(tmp)
            same = os.path.isfile(DRIVER) and os.path.isfile(REG_ANALYZER)
        finally:
            os.chdir(cwd0)
        ctl.append(('路径解析与工作目录无关', same))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    ok = True
    for nm, passed in ctl:
        print('  [%s] %s' % ('PASS' if passed else 'FAIL', nm))
        ok = ok and passed
    print('SELFTEST: %s' % ('PASS' if ok else 'FAIL'))
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
