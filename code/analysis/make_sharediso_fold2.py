# -*- coding: utf-8 -*-
"""make_sharediso_fold2.py — 生成 #27 的分析脚本：**另一个 holdout 子集** + **shared-isotonic 对照臂**。

做法（最小风险）：把已有的 `a39_unit_calib_heldout.py`（可信的数据加载与单元定义）**复制**一份，
只改三处：
  ① 输出名换成 `a39_sharediso_fold2_result.json`（**绝不覆盖**已冻结的 M.37 结果）；
  ② 折的取法由"每次随机抽 1/3"换成**三个互不相交的三分之一轮换**（split 编号决定）——即 dsflash 要的
     "把 1/3 holdout 改成另一个子集"；
  ③ 新增 **SISO 臂**：在**全部 unit 的标定折池化**后拟合**一个**保序映射，再逐 unit 应用
     （与 Cg"一个仿射参数"对应的"一个保序映射"对照）。
"""
import hashlib
import io
import os
import shutil
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
W = r'<WORKDIR>\PaperB\analysis\work'
SRC = os.path.join(W, 'a39_unit_calib_heldout.py')
DST = os.path.join(W, 'a39_sharediso_fold2.py')

src = io.open(SRC, encoding='utf-8').read()
out = src

R1_OLD = "OUT = r'D:\\deepseek\\PaperB\\analysis\\work\\a39_unit_calib_heldout_result.json'"
R1_NEW = "OUT = r'D:\\deepseek\\PaperB\\analysis\\work\\a39_sharediso_fold2_result.json'"
assert out.count(R1_OLD) == 1, 'OUT 锚点 count=%d' % out.count(R1_OLD)
out = out.replace(R1_OLD, R1_NEW)

R2_OLD = """rng = random.Random(SEED)
R = {k: [] for k in ('C0e', 'C1u', 'C2l', 'Cg', 'ISO', 'QNT')}"""
R2_NEW = """rng = random.Random(SEED)
# ★ 与 M.37 的差别（本条分析的目的）：标定折不再是"每次随机抽 1/3"，而是**三个互不相交的三分之一轮换**
#   —— split 编号决定用哪一份 ⇒ 每次用到的是**另一个子集**，且三轮覆盖全部 item。
R = {k: [] for k in ('C0e', 'C1u', 'C2l', 'Cg', 'ISO', 'QNT', 'SISO')}"""
assert out.count(R2_OLD) == 1, 'R 初始化锚点 count=%d' % out.count(R2_OLD)
out = out.replace(R2_OLD, R2_NEW)

R3_OLD = """for _ in range(NSPLIT):
    sp = {k: [] for k in R}
    cal, ev = {}, {}
    for u in units:
        ks = list(UNITS[u]['keys'])
        rng.shuffle(ks)
        nc = max(2, int(round(len(ks) * CAL_FRAC)))
        ck, ek = set(ks[:nc]), set(ks[nc:])
        cal[u] = {lb: [d[k] for k in ck] for lb, d in UNITS[u]['levels']}
        ev[u] = {lb: [d[k] for k in ek] for lb, d in UNITS[u]['levels']}
    C1 = {u: fit_a([x for lb in cal[u] for x in cal[u][lb]]) for u in units}
    Cg = fit_a([x for u in units for lb in cal[u] for x in cal[u][lb]])"""
R3_NEW = """for _sp in range(NSPLIT):
    sp = {k: [] for k in R}
    cal, ev = {}, {}
    _seg = _sp % 3                      # ★ 轮换互不相交的三分之一
    for u in units:
        ks = sorted(UNITS[u]['keys'])
        ck = set([k for i, k in enumerate(ks) if i % 3 == _seg])
        ek = set(ks) - ck
        cal[u] = {lb: [d[k] for k in ck] for lb, d in UNITS[u]['levels']}
        ev[u] = {lb: [d[k] for k in ek] for lb, d in UNITS[u]['levels']}
    C1 = {u: fit_a([x for lb in cal[u] for x in cal[u][lb]]) for u in units}
    Cg = fit_a([x for u in units for lb in cal[u] for x in cal[u][lb]])
    # ★ SISO：把**所有 unit 的标定折**池化后拟合**一个**保序映射，再逐 unit 应用
    SISO = fit_iso([x for u in units for lb in cal[u] for x in cal[u][lb]])"""
assert out.count(R3_OLD) == 1, '折与臂锚点 count=%d' % out.count(R3_OLD)
out = out.replace(R3_OLD, R3_NEW)

R4_OLD = """        vC0, vC1, vC2, vCg, vISO, vQNT = [], [], [], [], [], []"""
R4_NEW = """        vC0, vC1, vC2, vCg, vISO, vQNT, vSISO = [], [], [], [], [], [], []"""
assert out.count(R4_OLD) == 1, '局部列表锚点 count=%d' % out.count(R4_OLD)
out = out.replace(R4_OLD, R4_NEW)

R5_OLD = """            vISO.append(100.0 * (sum(fit_iso(c)(pe)) - sg) / sg)"""
R5_NEW = """            vISO.append(100.0 * (sum(fit_iso(c)(pe)) - sg) / sg)
            vSISO.append(100.0 * (sum(SISO(pe)) - sg) / sg)"""
assert out.count(R5_OLD) == 1, 'ISO 行锚点 count=%d' % out.count(R5_OLD)
out = out.replace(R5_OLD, R5_NEW)

R6_OLD = """        for k, v in (('C1u', vC1), ('C2l', vC2), ('Cg', vCg), ('ISO', vISO), ('QNT', vQNT)):"""
R6_NEW = """        for k, v in (('C1u', vC1), ('C2l', vC2), ('Cg', vCg), ('ISO', vISO), ('QNT', vQNT), ('SISO', vSISO)):"""
assert out.count(R6_OLD) == 1, '臂汇总锚点 count=%d' % out.count(R6_OLD)
out = out.replace(R6_OLD, R6_NEW)

R7_OLD = """         ('○ C0e 对照：留出但不校准', 'C0e')]"""
R7_NEW = """         ('★ SISO 全局单张保序映射（“一个单调重标定”）', 'SISO'),
         ('○ C0e 对照：留出但不校准', 'C0e')]"""
assert out.count(R7_OLD) == 1, 'NAMES 锚点 count=%d' % out.count(R7_OLD)
out = out.replace(R7_OLD, R7_NEW)

R8_OLD = """    n_units=len(units), units=units, nsplit=NSPLIT, seed=SEED, calib_frac=CAL_FRAC,"""
R8_NEW = """    variant='rotating disjoint thirds (split index mod 3) + shared-isotonic arm — the #27 control',
    n_units=len(units), units=units, nsplit=NSPLIT, seed=SEED, calib_frac=CAL_FRAC,"""
assert out.count(R8_OLD) == 1, 'json 头锚点 count=%d' % out.count(R8_OLD)
out = out.replace(R8_OLD, R8_NEW)

compile(out, DST, 'exec')
io.open(DST, 'w', encoding='utf-8', newline='\n').write(out)
print('已生成 %s（%d 字节，md5 %s）' % (os.path.basename(DST), len(out),
                                        hashlib.md5(out.encode('utf-8')).hexdigest()[:12]))
