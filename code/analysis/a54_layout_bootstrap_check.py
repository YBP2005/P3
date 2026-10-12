# -*- coding: utf-8 -*-
"""a54_layout_bootstrap_check.py — 布局聚类 bootstrap 的**独立复核器**（只读，不写盘）。

## 为什么需要它
补充材料 §M.11.2.1 的「Cluster-aware intervals for the new readings」那一句印了一个读数：
*布局聚类 bootstrap（放行驱动自己的聚类变量，**648** 簇，在**冻结种子**上重抽 **200** 次）
给出池化共同斜率 **[−0.8281, −0.5774]**，同样不满足 C4*。
这句话**此前没有任何入口点复现过它**：被正文点名的那支入口点只复用了放行驱动的 `fit_rows`，
从未调用它的 `cluster_bootstrap`。本件把那条读数**接回来**，并把它登记为**断言对象**。

## 本件做什么
* 只读**已放行**的逐项记录（`data/derived/a52_api_six_20261007/`），路径只经 `_repro_root` 解析；
* **调用放行驱动自己的** `cluster_bootstrap`（导入复用，**不重实现**），在册口径：
  簇 = `layout_id`、重抽 **200** 次、种子 = 驱动自己的**冻结种子**；
* 逐位比对在册区间 **[−0.8281, −0.5774]**（四位小数印出口径，容差 5e-5）；
* 另核：簇数 = **648**、有效重抽 = **200**、C4 判决 = **FAIL**（区间不落在 ±0.2 内）；
* **阴性对照**：只把重抽次数换掉，必须给出**不同**的区间 —— 否则上面那条断言可能是**永真**的。

## 纪律
* 缺件即**明确报错**（退出码 3），不静默返回空结果；
* 本件**不写任何文件**、**不改任何已印数字**、不新增任何模型调用（纯 CPU）。

用法：
    python a54_layout_bootstrap_check.py --selftest    # 负例自测
    python a54_layout_bootstrap_check.py               # 全量：重抽 200 次并逐位比对
"""
# ── 复现包统一根：`_repro_root.py`（与本文件同目录）──────────────────────────────
try:
    from _repro_root import resolve as RP
except ImportError:                      # 只拷走单个脚本时：就地反推仓库根
    import os as _o
    _r = _o.environ.get('PAPERB_ROOT') or _o.path.dirname(_o.path.dirname(_o.path.abspath(__file__)))
    RP = lambda *p: _o.path.join(_r, *p)
import argparse
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
DRIVER = os.path.join(A52DIR, '_a52_api_analyze.py')

# 在册口径（与补充材料那句逐字对应）
BOOT_B = 200                       # 重抽次数；★ 放行驱动的**默认值是 500**，此处按在册数显式传 200
CLUSTERS = 648                     # 簇 = 布局（`layout_id`）
PRINTED_CI = (-0.8281, -0.5774)    # 在册区间（补充材料 §M.11.2.1）
TOL = 5e-5                         # 四位小数印出口径：容差只吸收浮点末位
BAND = 0.2                         # C4 判据带
NEG_B = BOOT_B * 2 + 100           # 阴性对照用的重抽次数（与在册值不同即可）


def die(msg):
    sys.stderr.write('a54_layout_bootstrap_check: FAIL — %s\n' % msg)
    raise SystemExit(3)


def load_mod(name, path):
    if not os.path.isfile(path):
        die('缺件：%s' % path)
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


def md5f(p):
    return hashlib.md5(io.open(p, 'rb').read()).hexdigest()


def matches(ci, want, tol=TOL):
    """逐位比对（四位小数印出口径）。"""
    return (ci is not None and len(ci) == 2
            and abs(ci[0] - want[0]) <= tol and abs(ci[1] - want[1]) <= tol)


def c4_fails(ci):
    """C4 判据：区间落在 ±0.2 之内才算通过。"""
    return not (ci[0] > -BAND and ci[1] < BAND)


def served_rows(D):
    """已放行逐项记录；`http==200` 的服务行即本件的作用集。"""
    man = D.load_manifest()
    rows, missing = D.load_api(man)
    served = [r for r in rows if r['http'] == 200]
    return served, missing


def fmt(ci):
    return '[%+.4f, %+.4f]' % (ci[0], ci[1]) if ci else 'None'


# ══════════════════════ 全量 ══════════════════════
def run():
    D = load_mod('a54drv', DRIVER)
    print('放行驱动 = %s（md5 %s）' % (DRIVER, md5f(DRIVER)))
    print('在册口径 = 簇 layout_id ｜ 重抽 %d 次 ｜ 种子 = 驱动自己的冻结种子 %d'
          % (BOOT_B, D.BOOT_SEED))

    served, missing = served_rows(D)
    print('行数 = %d ｜ http==200 = %d ｜ 未服务 = %d' % (len(served) + len(missing),
                                                     len(served), len(missing)))
    n_cl = len(set(r['layout_id'] for r in served))
    print('布局簇 = %d（在册 %d）%s' % (n_cl, CLUSTERS, 'OK' if n_cl == CLUSTERS else '<-- 不符'))

    r = D.cluster_bootstrap(served, B=BOOT_B, seed=D.BOOT_SEED)
    ci = tuple(r.get('ci') or ())
    n_ok = r.get('n_ok', 0)
    print('实得：有效重抽 %d / %d ｜ 区间 %s ｜ 中位 %+.4f'
          % (n_ok, BOOT_B, fmt(ci), r.get('median', float('nan'))))
    print('在册：%s' % fmt(PRINTED_CI))

    alt = D.cluster_bootstrap(served, B=NEG_B, seed=D.BOOT_SEED)
    ci_alt = tuple(alt.get('ci') or ())
    print('阴性对照（重抽 %d 次，同种子）：%s' % (NEG_B, fmt(ci_alt)))

    ctl = [
        ('簇数 = %d' % CLUSTERS, n_cl == CLUSTERS),
        ('有效重抽 = %d' % BOOT_B, n_ok == BOOT_B),
        ('在册区间逐位复现 %s' % fmt(PRINTED_CI), matches(ci, PRINTED_CI)),
        ('C4 判决 = FAIL（区间不落在 ±%.1f 内）' % BAND, bool(ci) and c4_fails(ci)),
        ('阴性对照给出**不同**区间（断言非永真）', bool(ci_alt) and not matches(ci_alt, PRINTED_CI, 1e-4)),
    ]
    ok = True
    print('')
    for name, passed in ctl:
        print('  [%s] %s' % ('PASS' if passed else 'FAIL', name))
        ok = ok and passed
    print('\n%s' % ('LAYOUT_BOOTSTRAP: PASS' if ok else 'LAYOUT_BOOTSTRAP: FAIL'))
    return 0 if ok else 1


# ══════════════════════ 负例自测 ══════════════════════
def selftest():
    """★ 负例自测：①缺件必须明确报错；②小重抽次数**不得**蒙对在册区间；
    ③同参数必须**可重复**；④路径解析与工作目录无关。"""
    print('a54_layout_bootstrap_check --selftest（负例自测）')
    ctl = [('放行驱动实存', os.path.isfile(DRIVER))]
    D = load_mod('a54drv_st', DRIVER)
    ctl.append(('驱动自带冻结种子（实得 %s）' % getattr(D, 'BOOT_SEED', None),
                isinstance(getattr(D, 'BOOT_SEED', None), int)))

    # ① 缺件 ⇒ SystemExit(3)
    import tempfile
    import shutil
    tmp = tempfile.mkdtemp(prefix='a54_selftest_')
    try:
        try:
            load_mod('nope', os.path.join(tmp, '__nope__.py'))
            ctl.append(('缺件 ⇒ 明确报错（退出码 3）', False))
        except SystemExit as e:
            ctl.append(('缺件 ⇒ 明确报错（退出码 3）', e.code == 3))

        served, _missing = served_rows(D)
        ctl.append(('作用集 = 34,950 行已服务纪录', len(served) == 34950))
        ctl.append(('簇数 = %d' % CLUSTERS, len(set(r['layout_id'] for r in served)) == CLUSTERS))

        # ② 小重抽次数**不得**蒙对在册区间（否则全量那条断言可能是永真的）
        r5 = D.cluster_bootstrap(served, B=5, seed=D.BOOT_SEED)
        ci5 = tuple(r5.get('ci') or ())
        ctl.append(('小重抽（B=5）得 %s，**不**等于在册区间' % fmt(ci5),
                    bool(ci5) and not matches(ci5, PRINTED_CI, 1e-4)))

        # ③ 同参数可重复（随机数发生器按种子独立起）
        a = D.cluster_bootstrap(served, B=5, seed=D.BOOT_SEED).get('ci')
        b = D.cluster_bootstrap(served, B=5, seed=D.BOOT_SEED).get('ci')
        ctl.append(('同参数两次调用给出同一区间（%s）' % fmt(tuple(a or ())),
                    a is not None and list(a) == list(b or [])))

        # ④ 工作目录无关
        cwd0 = os.getcwd()
        try:
            os.chdir(tmp)
            same = os.path.isfile(DRIVER)
        finally:
            os.chdir(cwd0)
        ctl.append(('路径解析与工作目录无关', same))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    ok = True
    for name, passed in ctl:
        print('  [%s] %s' % ('PASS' if passed else 'FAIL', name))
        ok = ok and passed
    print('SELFTEST: %s' % ('PASS' if ok else 'FAIL'))
    return 0 if ok else 1


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description='布局聚类 bootstrap 的独立复核器（只读）')
    ap.add_argument('--selftest', action='store_true')
    a = ap.parse_args()
    sys.exit(selftest() if a.selftest else run())
