#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""_p0a_recompute.py —— 从**放行的逐格记录**复算补充材料 §M.19.17.1 的每一个数字。

放行布局（本文件位于 `data/derived/p0a_a800/env/`）：

    ../P0A_<arm>_<pool>_start<S>.csv        32 件逐格记录（本目录的上一级）
    _p0a_cls.py                             行级判读（同目录）
    ../e2/e1_internvl35-38b-bf16_dense{zero,nonzero}_s1.csv   被对照的存档起点（§M.19.17）

用法：  python3 _p0a_recompute.py            # 打印判据表 + 语言表 + 阳性对照；断言不符即退非 0
        python3 _p0a_recompute.py --quiet    # 只打印汇总与结论

★ 两个弃答口径**都打印**（见 §M.19.17.1）：
    narrow = 放行分析器用的三词表（abstain / cannot_judge / no_people）
    broad  = 再加中文与散文弃答（`_p0a_cls.py` 的类型优先 + 宽词表兜底）
★ 与口径无关的一条：本仪器 `parse_ok=0` 等价于"整段回复里没有任何数字"
  （`pf_p0_probe.py::parse()` 在 `count` 键不中时会回退搜 `-?\\d+`）。
"""
import csv
import glob
import io
import math
import os
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from _p0a_cls import classify, fnum, wilson  # noqa: E402

UP = os.path.dirname(HERE)


def _first_dir_with(pattern, cands):
    for c in cands:
        if glob.glob(os.path.join(c, pattern)):
            return c
    return cands[0]


DATA = _first_dir_with('P0A_*.csv', [UP, HERE, os.path.join(HERE, '_p0a')])
# 被对照的存档起点：放行布局下在 `../e2/`（本脚本位于 `data/derived/p0a_a800/env/`）。
# 也可用环境变量 `P0A_ARCH` 直接指定目录；找不到就跳过阳性对照那一段（不猜测、不静默改口径）。
_arch_env = os.environ.get('P0A_ARCH')
ARCH = _first_dir_with('e1_internvl35-38b-bf16_densezero_s1.csv',
                       [p for p in [_arch_env,
                                    os.path.join(os.path.dirname(UP), 'e2'),
                                    os.path.join(UP, 'e2')] if p])
NARROW = ('abstain', 'cannot_judge', 'no_people')
EXP = {'zero': 253, 'nonzero': 229}
BAD = []


def rows(p):
    return list(csv.DictReader(io.open(p, encoding='utf-8-sig', newline='')))


def narrow_abst(r):
    raw = (r.get('raw') or '').lower()
    return any(k in raw for k in NARROW)


def stats(rs):
    st = dict(n=len(rs), num=0, abst=0, bad=0, narrow=0, zero=0, mismatch=0)
    for r in rs:
        k, v, _ = classify(r)
        if k == 'num':
            st['num'] += 1
            if v == 0:
                st['zero'] += 1
            p = fnum(r.get('pred'))
            if p is not None and p != v:
                st['mismatch'] += 1
        elif k == 'abst':
            st['abst'] += 1
        else:
            st['bad'] += 1
        if narrow_abst(r):
            st['narrow'] += 1
    st['answered'] = st['num']
    return st


def pct(k, n):
    return float('nan') if not n else 100.0 * k / n


def main():
    quiet = '--quiet' in sys.argv
    files = sorted(glob.glob(os.path.join(DATA, 'P0A_*.csv')))
    print('数据目录 %s ｜ 逐格记录 %d 件' % (DATA, len(files)))
    assert len(files) == 32, '须 32 件（16 个 253 项池 + 16 个 229 项池），实得 %d' % len(files)

    # ---- C1：逐件计数 ----
    cell = {}
    for p in files:
        base = os.path.basename(p)[:-4].replace('P0A_', '')
        arm, pool, start = base.rsplit('_', 2)
        start = start[5:] if start.startswith('start') else start
        rs = rows(p)
        if len(rs) != EXP[pool]:
            BAD.append('C1 行数不符：%s 得 %d 期望 %d' % (base, len(rs), EXP[pool]))
        cell[(arm, pool, start)] = stats(rs)

    arms = ('cn_base', 'cn_permit', 'cn_channel', 'en_base', 'en_permit', 'en_channel')
    if not quiet:
        print('\n== C1/C5 逐格（n, 数值答案, 弃答broad, 真格式失败, 弃答narrow, 答零, pred互校）==')
        for a in arms:
            for pool in ('zero', 'nonzero'):
                for s in ('1', '2', '3'):
                    k = (a, pool, s)
                    if k not in cell:
                        continue
                    t = cell[k]
                    print('  %-12s %-7s s%s  n=%3d num=%3d abst=%3d bad=%d narrow=%3d zero=%3d mism=%d'
                          % (a, pool, s, t['n'], t['num'], t['abst'], t['bad'], t['narrow'], t['zero'],
                             t['mismatch']))
                    if t['mismatch']:
                        BAD.append('口径互校失败：%s' % str(k))
                    if t['bad']:
                        BAD.append('真格式失败 %d 行：%s' % (t['bad'], str(k)))
        print('  注：cn_base 按设计只有 start1（阳性对照，不在 5 臂循环里）')

    # ---- C2：跨起服极差 ----
    print('\n== C2 跨起服极差（253 项零池）==')
    for a in arms:
        zs = [cell[(a, 'zero', s)] for s in ('1', '2', '3') if (a, 'zero', s) in cell]
        if len(zs) < 2:
            continue
        rz = [100.0 * t['zero'] / t['n'] for t in zs]
        ra = [pct(t['abst'], t['n']) for t in zs]
        print('  %-12s 答零率 %s 极差 %.2f pp ｜ 弃答率(broad) %s 极差 %.2f pp'
              % (a, ['%.2f' % x for x in rz], max(rz) - min(rz), ['%.2f' % x for x in ra],
                 max(ra) - min(ra)))

    # ---- C3：语言（start1 配对）----
    print('\n== C3 base 臂语言（start1，同一 253 项）==')
    cnz, enz = cell[('cn_base', 'zero', '1')], cell[('en_base', 'zero', '1')]
    for nm, t in (('中文 base', cnz), ('英文 base', enz)):
        lo, hi = wilson(t['zero'], t['n'])
        print('  %-8s 答零 %d/%d = %.2f%% [%.1f, %.1f] ｜ 已答分母 %d/%d = %.2f%% ｜ '
              '弃答 broad %d = %.2f%% ｜ narrow %d = %.2f%% ｜ 数值答案 %d'
              % (nm, t['zero'], t['n'], pct(t['zero'], t['n']), lo, hi,
                 t['zero'], t['answered'], pct(t['zero'], t['answered']),
                 t['abst'], pct(t['abst'], t['n']), t['narrow'], pct(t['narrow'], t['n']), t['num']))
    assert cnz['zero'] == 25 and enz['zero'] == 1, 'C3 头条不符：cn=%d en=%d' % (cnz['zero'], enz['zero'])
    assert enz['abst'] == 97 and enz['narrow'] == 0, \
        'C3 两口径不符：broad=%d narrow=%d（窄词表对本构建的弃答应命中 0 行）' % (enz['abst'], enz['narrow'])
    assert enz['num'] == 156, 'C3 数值答案数不符：%d' % enz['num']
    wd = {}
    for r in rows(os.path.join(DATA, 'P0A_en_base_zero_start1.csv')):
        k, _, w = classify(r)
        if k == 'abst':
            wd[w] = wd.get(w, 0) + 1
    print('  英文弃答 97 行的措辞分解：%s' % wd)
    print('  ⇒ 三词表口径 **0/253 = 0.00%%**（97 行全部读不出）；宽口径 **97/253 = 38.34%%**')

    # ---- C4：家族（对照 §M.19.17 印值 64.03%）----
    print('\n== C4 家族（与 Qwen3-VL-32B-BF16 已印 64.03% 之差）==')
    for nm, t in (('cn_base', cnz), ('en_base', enz)):
        print('  %-8s %.2f%% -> 差 %+.2f pp' % (nm, pct(t['zero'], t['n']), pct(t['zero'], t['n']) - 64.03))
    for a in ('cn_permit', 'cn_channel', 'en_permit', 'en_channel'):
        t = cell[(a, 'zero', '1')]
        print('  %-12s 零池弃答(broad) %.2f%% ｜ 数值答案 %d（§M.18.5 已印密集非零池带 88.6–100%%）'
              % (a, pct(t['abst'], t['n']), t['num']))

    # ---- 阳性对照 ----
    ref = os.path.join(ARCH, 'e1_internvl35-38b-bf16_densezero_s1.csv')
    print('\n== 阳性对照：本机 cn_base/zero/start1 对存档起点 ==')
    if not os.path.exists(ref):
        print('  （未找到 %s ⇒ 跳过；判据件预注册该项必须比对）' % ref)
        BAD.append('阳性对照参照件缺失')
    else:
        a_rows, b_rows = rows(os.path.join(DATA, 'P0A_cn_base_zero_start1.csv')), rows(ref)
        B = {r['item']: r for r in b_rows}
        same = 0
        diffs = []
        for r in a_rows:
            o = B[r['item']]
            ka, va, _ = classify(r)
            kb, vb, _ = classify(o)
            if ka == kb and (ka != 'num' or va == vb):
                same += 1
            else:
                diffs.append((r['item'], ka, va, kb, vb))
        ta = stats(a_rows)
        tb = stats(b_rows)
        print('  本次 %d/%d = %.2f%% ｜ 存档 %d/%d = %.2f%% ｜ 差 %+.2f pp'
              % (ta['zero'], ta['n'], pct(ta['zero'], ta['n']), tb['zero'], tb['n'],
                 pct(tb['zero'], tb['n']), pct(ta['zero'], ta['n']) - pct(tb['zero'], tb['n'])))
        print('  逐项完全一致 %d/%d = %.2f%% ｜ 类型一致 %d/%d ｜ 取值差异 %d 项'
              % (same, len(a_rows), pct(same, len(a_rows)),
                 len(a_rows) - sum(1 for d in diffs if d[1] != d[3]), len(a_rows), len(diffs)))
        print('  ⇒ 预注册的"复现 24/251"按字面**未复现（FAIL）**；存档三起服自身为 24/21/23 of 251。')

    print('\n== 结论 ==')
    if BAD:
        print('  不合格项 %d 条：' % len(BAD))
        for b in BAD:
            print('   - %s' % b)
        return 1
    print('  32/32 件行数正确；真格式失败 0 行；口径互校 0 不一致；')
    print('  语言读数复现：密集零池答零 25/253 = 9.88%%（中）→ 1/253 = 0.40%%（英）；')
    print('  英文弃答两口径：0.00%%（三词表，97 行全读不出）／ 38.34%%（宽口径）；英文数值答案 156/253。')
    print('  P0A_RECOMPUTE_OK')
    return 0


if __name__ == '__main__':
    sys.exit(main())
