#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""p2e_protocol_check.py —— **G1 闸门**：把"输入尺度"约定**实测锁死**在既有 ladder 上。

为什么必须有这一步：density knob 的两支口径（官方 DM-Count / 既有 CSRNet）要"同一把尺"，
否则两支之差会混进"缩放约定之差"。既有的 `csrsta_ladder_st_a.csv` 逐行记了 `in_w,in_h,in_px`，
所以**约定是可以被反解出来的**：

    protocol = mult , value = v   ⇒  in_w ≈ round(W*v),  in_h ≈ round(H*v)
    protocol = short, value = v   ⇒  s = v / min(W,H);  in_w ≈ round(W*s), in_h ≈ round(H*s)

判据（判据件 gates.G1_protocol_conformance）：某条候选约定在某 (protocol,value) 上
**≥99% 的行 |Δ| ≤ 1 px** 才算对上；**全部 (protocol,value) 都对上**才 G1_PASS。
若两条约定都能对上（或都对不上）⇒ 报出来，**不猜**，由执行者定夺（exit 3）。

用法：python3 p2e_protocol_check.py
需要：--ladder（默认既有 CSRNet/st_a ladder）、--sizes（提供原图 W/H 的件）
"""
import collections
import io
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from p2e_common import fnum, load_csv  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
# ★ 放行版：作者机路径一律不写死。默认取环境变量，取不到就要求显式传参（run_all 就是这么调的）。
DEF_LADDER = os.environ.get('P2E_LADDER')
DEF_SIZES = os.environ.get('P2E_SIZES')


def norm(it):
    it = str(it).strip()
    for e in ('.jpg', '.jpeg', '.png', '.JPG'):
        if it.endswith(e):
            it = it[:-len(e)]
    return it


def main():
    a = sys.argv[1:]
    ladder = a[a.index('--ladder') + 1] if '--ladder' in a else DEF_LADDER
    sizes = a[a.index('--sizes') + 1] if '--sizes' in a else DEF_SIZES
    if not ladder or not sizes:
        print('!! 需要 --ladder 与 --sizes（或环境变量 P2E_LADDER / P2E_SIZES）')
        return 2
    for p in (ladder, sizes):
        if not os.path.exists(p):
            print('!! 缺文件：%s' % p)
            return 2
    S = {}
    for r in load_csv(sizes):
        w, h = fnum(r.get('W')), fnum(r.get('H'))
        if w and h:
            S[norm(r['item'])] = (w, h)
    rows = load_csv(ladder)
    print('既有 ladder：%s（%d 行）' % (os.path.basename(ladder), len(rows)))
    print('原图尺寸源：%s（%d 项）' % (os.path.basename(sizes), len(S)))

    groups = collections.defaultdict(list)
    for r in rows:
        it = norm(r['item'])
        if it not in S:
            continue
        iw, ih = fnum(r.get('in_w')), fnum(r.get('in_h'))
        v = fnum(r.get('value'))
        if None in (iw, ih, v):
            continue
        W, H = S[it]
        cand = {
            'mult': (W * v, H * v),
            'short': ((W * v / min(W, H)), (H * v / min(W, H))),
        }
        for name, (ew, eh) in cand.items():
            ok = abs(ew - iw) <= 1.0 and abs(eh - ih) <= 1.0
            groups[(r['protocol'], v, name)].append(ok)

    verdict = {}
    for (proto, v, name), oks in sorted(groups.items()):
        rate = 100.0 * sum(oks) / len(oks)
        verdict[(proto, v, name)] = rate
        print('   protocol=%-6s value=%-7s 约定=%-6s 命中 %6.2f%%（n=%d）' % (proto, v, name, rate, len(oks)))

    # 对每条真实存在的 protocol：哪种约定能对上**它全部**的 value？
    protos = sorted({p for p, _, _ in verdict})
    chosen = {}
    for p in protos:
        names = sorted({n for pp, _, n in verdict if pp == p})
        good = []
        for n in names:
            rates = [r for (pp, vv, nn), r in verdict.items() if pp == p and nn == n]
            if rates and all(r >= 99.0 for r in rates):
                good.append(n)
        chosen[p] = good
        print('   ⇒ protocol=%-6s 候选约定里 ≥99%% 全档命中：%s' % (p, good or '无'))

    unresolved = [p for p, g in chosen.items() if len(g) != 1]
    if unresolved:
        print('G1_UNRESOLVED：这些 protocol 的约定不唯一或无 → %s ⇒ 报出、不猜，由执行者定夺' % unresolved)
        return 3
    print('G1_PASS：约定唯一锁定 → %s' % chosen)
    return 0


if __name__ == '__main__':
    sys.exit(main())
