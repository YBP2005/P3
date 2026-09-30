# -*- coding: utf-8 -*-
"""synthetic_grid_cells.py — 干净合成圆点网格的**逐格冻结值**，以及 §5.7 / 补充材料 J.8 的口径校验。

背景（2026-09-27，v0585 轮）
----------------------------------------------------------------------------
`20–43%` 这个数在 v0584 及以前**印在主稿三处**（§1、§5.7 Mode A、§5.7 解耦段），
但它的生产件 `PaperB_合成网格准确性_20260911.md` **不在送审件内**，因此盲审无法溯源
（v0582 轮 glm53flash 的 F2 指控成立）。

本脚本做三件事：
  ① 持有 base 臂 **20 格冻结值**（逐字取自上述记录，并断言该记录的 md5），
     现算：全 20 格 ρ 范围 / |ρ|≥20% 的子集范围 / 按 n 的平均 ρ / |ρ| 中位数；
  ② `--check`：从**现行补充材料**的 J.8 表重读 20 格，逐格与冻结值比对，
     并断言三条口径事实（弃权率全 0；|ρ| 最大 = 42.5%；|ρ|≥20% 的格子数 = 14）；
  ③ 打印 §5.7 现在印的 `up to 42.5%` 与冻结值的关系（该值即源表逐格最大值，**不做向上取整**）。

**为什么 20–43% → up to 42.5%**：`20–43%` 是 |ρ|≥20% 那 14 格的范围；全 20 格是 +0.0% ~ −42.5%，
其中 n=100 一行含 +0.0% 与 −9.3% 两格。故主稿改为无限的 `up to 42.5%`（逐字为真，且**不做向上
取整**；v0585–v0600 印过 `up to 43%`，那是 42.5% 的向上取整，第 2 轮 R1 已改回 42.5%），
把 14/20 的口径写在 J.8 里。

只读。用法：
    python synthetic_grid_cells.py            # 打印全部派生量
    python synthetic_grid_cells.py --check    # 校验补充材料 J.8 表（失败退出码 1）
    python synthetic_grid_cells.py --selftest # 阴性对照：注入一个错值，校验器必须报错
"""
import hashlib
import io
import os
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')

ROOT = r'<WORKDIR>\PaperB'
RECORD = os.path.join(ROOT, 'PaperB_合成网格准确性_20260911.md')
RECORD_MD5 = '209ca8458b4ba1c1469ad457c91a4cdf'      # 2026-09-27 实测；记录改动即失败
SUP = os.path.join(ROOT, 'PaperB_英文补充材料_PR_20260919.md')
EN = os.path.join(ROOT, 'PaperB_英文稿_PR_20260919.md')
# 发布件里的名字：脚本随 sync_repro.py 进 code/analysis/
RELEASE_NAME = 'synthetic_grid_cells.py'

# ---------------------------------------------------------------- 冻结值（base 臂，20 格）
# 逐字取自 PaperB_合成网格准确性_20260911.md 的「## base 臂」表。
# 列：n, r(px), px/obj, 弃权率(%), 平均预测, ρ(%)
FROZEN = [
    (50, 2, 16, 0.0, 40, -19.5),
    (50, 4, 64, 0.0, 40, -20.0),
    (50, 8, 256, 0.0, 40, -20.0),
    (50, 16, 1024, 0.0, 40, -20.6),
    (100, 2, 16, 0.0, 100, +0.0),
    (100, 4, 64, 0.0, 85, -15.4),
    (100, 8, 256, 0.0, 91, -9.3),
    (100, 16, 1024, 0.0, 84, -16.2),
    (200, 2, 16, 0.0, 115, -42.5),
    (200, 4, 64, 0.0, 145, -27.6),
    (200, 8, 256, 0.0, 174, -12.8),
    (200, 16, 1024, 0.0, 160, -20.2),
    (400, 2, 16, 0.0, 251, -37.3),
    (400, 4, 64, 0.0, 255, -36.2),
    (400, 8, 256, 0.0, 255, -36.2),
    (400, 16, 1024, 0.0, 287, -28.2),
    (800, 2, 16, 0.0, 490, -38.8),
    (800, 4, 64, 0.0, 460, -42.5),
    (800, 8, 256, 0.0, 525, -34.4),
    (800, 16, 1024, 0.0, 605, -24.4),
]
assert len(FROZEN) == 20, 'base 臂必须是 20 格'


def derived(cells=FROZEN):
    """从逐格值现算全部派生量（不手抄）。"""
    rho = [c[5] for c in cells]
    abso = sorted(abs(v) for v in rho)
    ge20 = [v for v in abso if v >= 20.0]
    by_n = {}
    for c in cells:
        by_n.setdefault(c[0], []).append(c[5])
    med = (abso[9] + abso[10]) / 2.0                     # 20 个值的中位数
    return dict(
        cells=len(cells),
        abst_max=max(c[3] for c in cells),
        abst_all_zero=all(c[3] == 0.0 for c in cells),
        rho_min=min(rho), rho_max=max(rho),
        abs_min=abso[0], abs_max=abso[-1],
        median_abs=med,
        n_ge20=len(ge20), ge20_min=min(ge20), ge20_max=max(ge20),
        by_n={k: sum(v) / len(v) for k, v in sorted(by_n.items())},
    )


def report():
    d = derived()
    print('=' * 88)
    print('干净合成圆点网格（base 臂，%d 格）—— 冻结件 PaperB_合成网格准确性_20260911.md' % d['cells'])
    print('=' * 88)
    print('  弃权率全部为 0        : %s（最大 %.1f%%）' % (d['abst_all_zero'], d['abst_max']))
    print('  ρ 范围（全 20 格）    : %+.1f%% .. %+.1f%%' % (d['rho_min'], d['rho_max']))
    print('  |ρ| 范围             : %.1f%% .. %.1f%%' % (d['abs_min'], d['abs_max']))
    print('  |ρ| 中位数           : %.1f%%' % d['median_abs'])
    print('  |ρ|>=20%% 的格子      : %d / %d，其范围 %.1f%% .. %.1f%%  <- 这就是「20–43%%」'
          % (d['n_ge20'], d['cells'], d['ge20_min'], d['ge20_max']))
    print('  按 n 的平均 ρ         : ' + '  '.join('n=%d:%+.1f%%' % (k, v) for k, v in d['by_n'].items()))
    print()
    print('  ⇒ 主稿现印 "up to 42.5%%"：它就是最大 |ρ| %.1f%% 本身，**不做向上取整**。'
          % d['abs_max'])
    print('  ⇒ 旧的 "20–43%%" 只是那 %d 格的范围；全 %d 格含 +0.0%% 与 −9.3%% 两格。'
          % (d['n_ge20'], d['cells']))


# ------------------------------------------------------------------ J.8 表校验（重算型锚点）
ROW = re.compile(r'^\|\s*(\d+)\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\|\s*([\d.]+)%\s*\|\s*(\d+)\s*\|\s*'
                 r'([+−-])([\d.]+)%\s*\|\s*$')


def parse_j8(sup):
    """从补充材料 J.8 小节里重读 20 格。范围：J.8 标题 → 下一个 ### 标题。"""
    m = re.search(r'(?m)^###\s+J\.8\b.*?$', sup)
    if not m:
        return None, '找不到 J.8 小节标题'
    seg = sup[m.end():]
    nxt = re.search(r'(?m)^#{2,4}\s+\S', seg)
    if nxt:
        seg = seg[:nxt.start()]
    rows = []
    for line in seg.split('\n'):
        mm = ROW.match(line.strip())
        if mm:
            n, r, px, abst, pred, sign, rho = mm.groups()
            val = float(rho) if sign == '+' else -float(rho)
            rows.append((int(n), int(r), int(px), float(abst), int(pred), val))
    return rows, ('J.8 里解析到 %d 行' % len(rows))


def check(inject=None):
    sup = io.open(SUP, encoding='utf-8', newline='').read()
    rows, why = parse_j8(sup)
    fails = []
    if rows is None:
        print('FAIL  %s' % why)
        return 1
    exp = list(FROZEN)
    if inject is not None:
        i, col, val = inject
        e = list(exp[i])
        e[col] = val
        exp[i] = tuple(e)
    print('J.8 表：%s（期望 20 行）' % why)
    if len(rows) != 20:
        fails.append('J.8 表行数 %d ≠ 20' % len(rows))
    for i, (got, want) in enumerate(zip(rows, exp)):
        if got != want:
            fails.append('第 %d 行不符：表中 %s ≠ 冻结 %s' % (i + 1, got, want))
    d = derived(exp)
    if not d['abst_all_zero']:
        fails.append('弃权率并非全 0')
    if abs(d['abs_max'] - 42.5) > 1e-9:
        fails.append('最大 |ρ| = %.1f ≠ 42.5' % d['abs_max'])
    if d['n_ge20'] != 14:
        fails.append('|ρ|>=20% 的格子数 = %d ≠ 14' % d['n_ge20'])
    # 主稿：不得再出现并集式的 20–43%；必须印 up to 42.5%（且不得退回向上取整的 43%）
    en = io.open(EN, encoding='utf-8', newline='').read()
    if '20–43%' in en:
        fails.append('主稿仍在印 20–43%（应已改为 up to 42.5%）')
    if 'up to 43%' in en:
        fails.append('主稿仍在印 up to 43%（应已改为 up to 42.5%）')
    if 'up to 42.5%' not in en:
        fails.append('主稿找不到 up to 42.5%')
    print('-' * 88)
    if fails:
        for f in fails:
            print('  FAIL  %s' % f)
        return 1
    print('  OK    J.8 的 20 格与冻结值逐格一致；弃权率全 0；最大 |ρ| = 42.5%；|ρ|>=20% 共 14 格')
    print('  OK    主稿已无 20–43%，且印有 up to 42.5%（42.5% = 源表逐格最大值，不做向上取整）')
    return 0


def main():
    if os.path.exists(RECORD):
        h = hashlib.md5(io.open(RECORD, 'rb').read()).hexdigest()
        tag = 'OK  ' if h == RECORD_MD5 else 'FAIL'
        print('[%s] 冻结件 md5 %s（期望 %s）' % (tag, h, RECORD_MD5))
        if h != RECORD_MD5:
            print('       ⇒ 生产件已改动；本脚本内嵌的冻结值必须先复核再更新。')
            return 1
    else:
        print('[warn] 冻结件不在本机；跳过 md5 断言（发布件以本脚本内嵌值为准）')

    if '--selftest' in sys.argv:
        print('\n阴性对照 ①：把 J.8 第 9 行的 ρ 从 −42.5 改成 −40.0（校验器必须报错）')
        rc = check(inject=(8, 5, -40.0))
        print('  ⇒ 退出码 %d（期望 1）' % rc)
        print('\n阴性对照 ②：把 J.8 第 1 行的弃权率改成 5.0（校验器必须报错）')
        rc2 = check(inject=(0, 3, 5.0))
        print('  ⇒ 退出码 %d（期望 1）' % rc2)
        ok = (rc == 1 and rc2 == 1)
        print('\nSELFTEST_%s' % ('PASS' if ok else 'FAIL'))
        return 0 if ok else 1

    report()
    if '--check' in sys.argv:
        print()
        print('=' * 88)
        print('校验补充材料 J.8（重算型锚点）')
        print('=' * 88)
        rc = check()
        print()
        print('CHECK_%s' % ('PASS' if rc == 0 else 'FAIL'))
        return rc
    return 0


if __name__ == '__main__':
    sys.exit(main())
