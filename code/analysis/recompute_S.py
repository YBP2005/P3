# -*- coding: utf-8 -*-
"""recompute_S.py — **四域统一入口**：从已放行语料复算每格「弃权占欠数份额」S。

    S = (1-w)/[1-w(1+rho_ans)],  w = G_ans/G（真值加权）,  rho_ans = (Σ pred_ans − G_ans)/G_ans

一次调用覆盖**附录 J.1 的全部四个 headline 域**：
  · 稠密域（st_a / st_b / ucf）：逐项 CSV 取自 `data/derived/corpus/`，金标准取自
    `data/gold/`（`shanghaitech_counts.csv` / `ucf_qnrf_counts.csv`）；
  · **航空两域（AI-TOD / VisDrone）**：逐项 CSV 取自 `data/derived/aerial_results/`
    （`aer_aitod_<arm>.csv` / `aer_visdrone_<arm>.csv`），`gt` **随行内**（该批记录自带 `gt` 列）。

同时打印 `w`、`rho_ans`、`rho_total`，便于与附录 J.1 的表逐格对账。

★ 2026-10-11（v0669，A8-3／M-6）：本脚本此前**只覆盖稠密三域**，航空两域的 `83.8%` / `82.1%`
  只能作为"冻结记录的读数"，不能由单一入口端到端复现（r18 A8-3 / r19 A8-3 两轮均指出）。
  两处改动，**判据与算术一字未改**：
  (1) **航空两域并入同一入口**（`--domain aerial` 或默认 `all`），`S` 的闭式与 `w`/`rho_ans`
      定义与稠密域**逐字相同**，只换数据来源与 `gt` 读法（行内列 vs 存档表）；
  (2) **路径解析显式化**：`pod_mirror` 的**子目录整段交给 RP()**（与 v0666 A8-5 对
      `n3_deployable_calibration.py` 的修法**同一风格**）。旧写法只解析父目录再 `os.path.join`
      子目录 ⇒ 放行树上落到兜底别名 `data/derived/pA/...`（不存在）。
  负例自测见 `--selftest`：缺输入 / 域参数非法 / 缺列 / 全弃权与无弃权（S 无定义）/
  任意工作目录运行 —— 各自给**明确失败**或**显式 `undefined`**，绝不静默报 0。
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
import glob
import io
import os
import re
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
try:
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

# ── 路径：★ 子目录整段交给 RP()（旧写法只解析父目录，放行树上必落空）──────────────
CORP = RP('analysis', 'e1_5090', 'corpus')                      # 稠密逐项 CSV（st_a/st_b/ucf）
AER = RP('analysis', 'data', 'pod_mirror', 'aerial_results')     # ★ 航空逐项 CSV（AI-TOD/VisDrone）
ARCH = NR('analysis', 'm5090_archive', 'unpacked', 'dense')

DENSE_PAT = re.compile(r'^vlm_(?P<ds>st_a|st_b|ucf)_(?P<arm>[a-z]+)_whole\.csv$')
AER_PAT = re.compile(r'^aer_(?P<ds>aitod|visdrone)_(?P<arm>[a-z]+)\.csv$')

# 显示名（与附录 J.1 的表一致）
DISP = {'st_a': 'ShanghaiTech-A', 'st_b': 'ShanghaiTech-B', 'ucf': 'UCF-QNRF',
        'aitod': 'AI-TOD', 'visdrone': 'VisDrone'}
HEADLINE = ('st_a', 'ucf', 'aitod', 'visdrone')                 # 四个 headline 域

ANOM = 1e5
SENT = 1234567890


def die(msg):
    """明确失败：打印可读原因并以退出码 3 结束（不静默返回空结果）。"""
    sys.stderr.write('recompute_S: FAIL — %s\n' % msg)
    raise SystemExit(3)


def gt_of_dense(ds, cache={}):
    """稠密域的存档金标准（st_a/st_b 用 shanghaitech，ucf 用 ucf_qnrf）。"""
    if ds in cache:
        return cache[ds]
    if ds in ('st_a', 'st_b'):
        f = RP('analysis', 'm5090_archive', 'unpacked', 'dense', 'shanghaitech', 'counts.csv')
        want = 'part_A' if ds == 'st_a' else 'part_B'
        g = {}
        if not os.path.exists(f):
            die('缺稠密金标准件：%s' % f)
        for r in csv.DictReader(io.open(f, encoding='utf-8-sig')):
            if (r.get('part') or '') == want and (r.get('split') or '') == 'test':
                g[os.path.splitext(os.path.basename(r['file']))[0]] = int(r['count'])
    else:
        f = RP('analysis', 'm5090_archive', 'unpacked', 'dense', 'ucf_qnrf', 'counts.csv')
        g = {}
        if not os.path.exists(f):
            die('缺稠密金标准件：%s' % f)
        for r in csv.DictReader(io.open(f, encoding='utf-8-sig')):
            if (r.get('split') or '') == 'Test':
                g[os.path.splitext(os.path.basename(r['file']))[0]] = int(r['count'])
    cache[ds] = g
    return g


def read_rows(path):
    """读一份逐项 CSV；缺必需列 ⇒ 明确失败（不静默跳过）。"""
    rows = list(csv.DictReader(io.open(path, encoding='utf-8-sig')))
    if not rows:
        die('%s 无数据行' % path)
    cols = set(rows[0].keys())
    if 'item' not in cols or 'pred' not in cols:
        die('%s 缺必需列（需要 item/pred；实得 %s）' % (path, sorted(cols)))
    return rows


def clean(pr):
    """与既有口径一致：不可解析 / 哨兵值 / ≥1e5 一律剔除。"""
    try:
        v = float(pr)
    except Exception:
        return None
    if abs(v) >= ANOM or int(v) == SENT:
        return None
    return v


def unit_stats(rows, gt_lookup):
    """→ (n, w, rho_ans, rho_tot, S)；S 在定义域外返回 None（显式 undefined）。"""
    recs = []
    for r in rows:
        it = str(r.get('item') or '').strip()
        g = gt_lookup(r, it)
        if g is None:
            continue
        p = clean(r.get('pred'))
        if p is None:
            continue
        recs.append((float(g), p))
    if not recs:
        return (0, None, None, None, None)
    G = sum(x[0] for x in recs)
    Gans = sum(x[0] for x in recs if x[1] != 0)
    Sans = sum(x[1] for x in recs if x[1] != 0)
    P = sum(x[1] for x in recs)
    if G <= 0 or Gans <= 0:
        return (len(recs), None, None, None, None)          # 全弃权 ⇒ S 无定义
    w = Gans / G
    rho_ans = (Sans - Gans) / Gans
    rho_tot = (P - G) / G
    den = 1 - w * (1 + rho_ans)
    # ★ 与既有算术**逐字相同**（`over` 臂 w=1 ⇒ S 恰为 0.0，必须保留）；只把原式会
    #   ZeroDivisionError 的退化点显式写成 undefined，不改变任何非退化格的读数。
    S = (1 - w) / den if abs(den) > 1e-15 else None
    return (len(recs), w, rho_ans, rho_tot, S)


def paths():
    """当前解析出的两处语料目录（供工作目录无关性自测调用）。"""
    return (RP('analysis', 'e1_5090', 'corpus'),
            RP('analysis', 'data', 'pod_mirror', 'aerial_results'))


def collect(which):
    """which ∈ {'dense','aerial','all'} ⇒ [(ds, arm, n, w, ra, rt, S, path), ...]"""
    out = []
    if which in ('dense', 'all'):
        if not os.path.isdir(CORP):
            die('缺稠密语料目录：%s' % CORP)
        for p in sorted(glob.glob(os.path.join(CORP, '*.csv'))):
            m = DENSE_PAT.match(os.path.basename(p))
            if not m:
                continue
            ds, arm = m.group('ds'), m.group('arm')
            g = gt_of_dense(ds)
            n, w, ra, rt, S = unit_stats(read_rows(p),
                                         lambda r, it, g=g: g.get(it))
            out.append((ds, arm, n, w, ra, rt, S, p))
    if which in ('aerial', 'all'):
        if not os.path.isdir(AER):
            die('缺航空语料目录：%s' % AER)
        for p in sorted(glob.glob(os.path.join(AER, '*.csv'))):
            m = AER_PAT.match(os.path.basename(p))
            if not m:
                continue
            ds, arm = m.group('ds'), m.group('arm')
            n, w, ra, rt, S = unit_stats(read_rows(p), inline_gt)
            out.append((ds, arm, n, w, ra, rt, S, p))
    if not out:
        die('未命中任何单元件（which=%s）' % which)
    return out


def inline_gt(r, it):
    """航空记录自带 `gt` 列。"""
    s = str(r.get('gt') or '').strip()
    if s == '':
        return None
    try:
        return float(s)
    except Exception:
        return None


def pct(x):
    return 'undefined' if x is None else '%9.2f%%' % (x * 100)


def report(rows, which):
    print('%-16s %-7s %7s %9s %10s %9s %9s' % ('ds', 'arm', 'n', 'w', 'rho_ans', 'rho_tot', 'S'))
    for ds, arm, n, w, ra, rt, S, _p in rows:
        print('%-16s %-7s %7d %9s %10s %9s %9s'
              % (DISP.get(ds, ds), arm, n,
                 'undefined' if w is None else '%.4f' % w,
                 pct(ra), pct(rt), pct(S)))
    print()
    base = {(d, a): s for d, a, n, w, ra, rt, s, _p in rows if a == 'base'}
    print('=== base 臂（对照 J.1 印出的 94.2 / 93.7 / 83.8 / 82.1）===')
    for d in (HEADLINE if which in ('aerial', 'all') else ('st_a', 'st_b', 'ucf')):
        k = (d, 'base')
        if k not in base:
            continue
        s = base[k]
        print('   %-16s %-5s S = %s' % (DISP.get(d, d), 'base', pct(s)))
    print()
    for arm in ('over', 'under'):
        got = ['%s %s' % (DISP.get(d, d), pct(s)) for d, a, n, w, ra, rt, s, _p in rows if a == arm]
        if got:
            print('%s 臂 S: %s' % (arm, got))
    print()
    print('=== 稠密域（st_a/ucf）逐格 S ===')
    for ds, arm, n, w, ra, rt, s, _p in sorted(rows):
        if ds in ('st_a', 'ucf'):
            print('   %-16s %-6s %s' % (DISP.get(ds, ds), arm, pct(s)))


def selftest():
    """★ 负例自测（不依赖真实语料）：明确失败 / 显式 undefined / 工作目录无关。"""
    global CORP
    import tempfile
    import shutil
    print('recompute_S --selftest（负例自测）')
    ctl = []

    def w_csv(path, header, rows):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with io.open(path, 'w', encoding='utf-8', newline='') as fh:
            fh.write(header + '\n')
            for r in rows:
                fh.write(r + '\n')

    tmp = tempfile.mkdtemp(prefix='recompute_S_selftest_')
    try:
        # (1) 域参数非法 ⇒ 明确失败（非静默 0）
        try:
            main(['--domain', 'bogus'])
            ctl.append(('域参数非法 ⇒ 明确失败', False))
        except SystemExit as e:
            ctl.append(('域参数非法 ⇒ 明确失败', e.code not in (0, None)))

        # (2) 缺输入目录 ⇒ die()（退出码 3，且信息里带路径）
        save, CORP = CORP, os.path.join(tmp, 'no_such_dir')
        try:
            collect('dense')
            ctl.append(('缺稠密语料目录 ⇒ 明确失败', False))
        except SystemExit as e:
            ctl.append(('缺稠密语料目录 ⇒ 明确失败', e.code == 3))
        CORP = save

        # (3) 缺必需列 ⇒ 明确失败
        bad = os.path.join(tmp, 'bad.csv')
        w_csv(bad, 'foo,bar', ['1,2'])
        try:
            read_rows(bad)
            ctl.append(('缺 item/pred 列 ⇒ 明确失败', False))
        except SystemExit as e:
            ctl.append(('缺 item/pred 列 ⇒ 明确失败', e.code == 3))

        # (4) 空文件 ⇒ 明确失败
        empty = os.path.join(tmp, 'empty.csv')
        w_csv(empty, 'item,pred', [])
        try:
            read_rows(empty)
            ctl.append(('空 CSV ⇒ 明确失败', False))
        except SystemExit as e:
            ctl.append(('空 CSV ⇒ 明确失败', e.code == 3))

        # (5) 全弃权 ⇒ S 显式 undefined（不是 0）
        rows = [{ 'item': 'a', 'pred': '0', 'gt': '10'}, {'item': 'b', 'pred': '0', 'gt': '20'}]
        n, w, ra, rt, S = unit_stats(rows, inline_gt)
        ctl.append(('全弃权 ⇒ S 显式 undefined', S is None and n == 2))

        # (6) 无弃权（w = 1）⇒ S 恰为 0.0（`over` 臂的既有读数；不得写成 undefined）
        rows = [{'item': 'a', 'pred': '5', 'gt': '10'}, {'item': 'b', 'pred': '30', 'gt': '20'}]
        _n, _w, _ra, _rt, _S = unit_stats(rows, inline_gt)
        ctl.append(('无弃权（w=1）⇒ S = 0.0', _w == 1.0 and _S == 0.0))

        # (7) 恒等式 rho_tot = w(1+rho_ans) − 1 与闭式一致
        rows = [{'item': 'a', 'pred': '0', 'gt': '100'},
                {'item': 'b', 'pred': '200', 'gt': '300'},
                {'item': 'c', 'pred': '120', 'gt': '100'}]
        n, w, ra, rt, S = unit_stats(rows, inline_gt)
        ctl.append(('恒等式 rho_tot = w(1+rho_ans) − 1',
                    abs(rt - (w * (1 + ra) - 1)) < 1e-12))
        ctl.append(('闭式 S = (1−w)/[1−w(1+rho_ans)]',
                    abs(S - (1 - w) / (1 - w * (1 + ra))) < 1e-12))

        # (8) 工作目录无关：从任意 CWD 解析出的路径与命中的单元集必须一致
        cwd0 = os.getcwd()
        try:
            os.chdir(tmp)
            p_from_tmp = paths()
            n_from_tmp = len(collect('all'))
            os.chdir(cwd0)
            ctl.append(('路径解析与工作目录无关', p_from_tmp == paths()))
            ctl.append(('单元集与工作目录无关', n_from_tmp == len(collect('all'))))
        except SystemExit:
            os.chdir(cwd0)
            ctl.append(('路径解析与工作目录无关', False))
            ctl.append(('单元集与工作目录无关', False))
        finally:
            os.chdir(cwd0)

        # (9) 四个 headline 域齐备（真实语料上）
        try:
            have = set(d for d, a, n, w, ra, rt, s, p in collect('all') if a == 'base')
            ctl.append(('四域统一入口齐备（base 臂四个 headline 域）',
                        set(HEADLINE) <= have))
        except SystemExit:
            ctl.append(('四域统一入口齐备（base 臂四个 headline 域）', False))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    ok = True
    for nm, passed in ctl:
        print('  [%s] %s' % ('PASS' if passed else 'FAIL', nm))
        ok = ok and passed
    print('SELFTEST: %s' % ('PASS' if ok else 'FAIL'))
    return 0 if ok else 1


def main(argv=None):
    ap = argparse.ArgumentParser(description='四域统一入口：复算弃权占欠数份额 S')
    ap.add_argument('--domain', choices=('dense', 'aerial', 'all'), default='all',
                    help='dense=稠密三域；aerial=航空两域；all=四域（默认）')
    ap.add_argument('--selftest', action='store_true')
    args = ap.parse_args(argv)
    if args.selftest:
        return selftest()
    print('corpus (dense) = %s' % CORP)
    print('corpus (aerial)= %s' % AER)
    print('domain         = %s' % args.domain)
    print()
    rows = collect(args.domain)
    report(rows, args.domain)
    return 0


if __name__ == '__main__':
    sys.exit(main())
