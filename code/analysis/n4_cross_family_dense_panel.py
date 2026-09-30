# -*- coding: utf-8 -*-
"""n4_cross_family_dense_panel.py — N4（只读）：评审要的"跨家族密集域频率面板"是否**已经在手**？

═══════════════════════════════════════════════════════════════════════════════════════
【评审的请求（逐字大意）】
  5 个**非 Qwen** 家族 × {ShanghaiTech-A, UCF-QNRF} × 各 150 项 × {`base`, `permit`, `channel`}
  ≈ 4,500 次调用；判据：**至少 2/5 家族**同时满足 base 答零率 ≥ 30% 且弃答份额 $S \ge 50\%$，
  且 Wilson 95% **下界** > 20%。评审预期："有些家族不会复现密集域的零"。

【为什么我认为它已经在手】
  补充材料 §M.19.2（7 家族 × base/permit 配对）与 §M.19.3（7 家族 × dense/aerial 的 base 答零率
  + Wilson CI，同 item 交集）。**唯一没被印出的量是 $S$** —— 本脚本算它。

【$S$ 的定义与权威实现（与 `s15_five_build_S.py` 逐字同源）】
  · 主稿命题 4：`ρ_total = −(1−w) + w·ρ_answered`，`w = G_N/G`，`S = (1−w)/[1−w(1+ρ_answered)]`
  · 闭式：**`S = (G − G_N)/(G − P)`** = 弃答项承载的 GT 质量 ÷ 总欠计；
    **仅当 `ρ_total < 0`** 时有定义（否则该格是净过计，比值不是份额）
  · 数据口径（补充材料 J.1 前言 = 附录 I 台账）：按 `item` 去重、剔 `pred ≥ 1e5`、
    **剔除不可解析的 `pred`**（口径 A；口径 B 把它们当弃答，本脚本两种都报）

【★ 本目录的**关键结构**（不查清就会算错，实测）】
  · 池：`e2xt_a800/merged/` = **zero pool**（语料答 0 的项）；`e2xt_a800/nonzero/` = **non-zero pool**。
  · ★★ 锚家族的 `merged/` 文件里**混着带 `#r` 后缀的重复行**：
    例 `e1_qwen3-vl-32b-awq_st_a_base.csv` 共 **412** 行，其中 **309** 行的 `item` 含 `#r`。
    论文的口径（`analysis/work/a5_report.py::load()`）是 **`'#r' not in item`** ⇒ 只留 **103** 行
    （102 个答零）—— 这正是 §M.19.2 印的 `st_a 0/102`。**不过滤 `#r` 会得到 407，与论文不符。**
  · 跨家族比较用**同 item 交集**（§M.19.3 的 frozen 报告纪律）。

用法：python -u n4_cross_family_dense_panel.py
═══════════════════════════════════════════════════════════════════════════════════════
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
import csv
import glob
import hashlib
import io
import math
import os
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
E3 = RP('analysis', 'e2xt_a800')
ZDIR, NZDIR = RP('analysis', 'e2xt_a800', 'merged'), RP('analysis', 'e2xt_a800', 'nonzero')
ANCHORS = {'qwen3-vl-32b-awq', 'qwen25vl-72b-awq', 'internvl25-8b-awq'}   # 论文点名的三个锚
# ★ 评审说的"5 个非 Qwen 家族"= 本材料里**非 Qwen** 的五个（两个 Qwen 锚除外）：
NONQWEN = ['gemma3-12b', 'InternVL3_5-8B', 'Phi-3.5-vision-instruct',
           'llava-onevision-qwen2-7b-ov', 'internvl25-8b-awq']
QWEN = ['qwen3-vl-32b-awq', 'qwen25vl-72b-awq']
E3NEW = ['gemma3-12b', 'InternVL3_5-8B', 'Phi-3.5-vision-instruct', 'llava-onevision-qwen2-7b-ov']
FAMS = ['gemma3-12b', 'InternVL3_5-8B', 'Phi-3.5-vision-instruct', 'llava-onevision-qwen2-7b-ov',
        'qwen3-vl-32b-awq', 'qwen25vl-72b-awq', 'internvl25-8b-awq']
# ★ 题面把 4 个 E3 新家族写成 "5 个非 Qwen 家族"：实际的非锚家族是这 4 个（+3 个锚）
DOMAINS = ['st_a', 'ucf', 'visdrone', 'aitod']
DENSE, AERIAL = ['st_a', 'ucf'], ['visdrone', 'aitod']
ABSTAIN_WORDS = ('abstain', 'cannot_judge', 'no_people')


def md5f(p):
    return hashlib.md5(io.open(p, 'rb').read()).hexdigest()


def items(path):
    """★ 同 item 交集必须建在**原始 item 集**上：只剔 `#r` 重复行，**不**剔异常值。
    （实测：若把 `pred ≥ 1e5` 的异常行也从 item 集里剔掉，Phi 的 st_a 会从 103 掉到 81、
     跨家族交集从 253 掉到 205，与 §M.19.3 印的 n=253 不符 ⇒ 说明论文的交集建在原始 item 集上。）"""
    out = set()
    if not os.path.exists(path):
        return out
    with io.open(path, encoding='utf-8-sig', errors='replace') as f:
        for r in csv.DictReader(f):
            k = (r.get('item') or '').strip()
            if k and '#r' not in k:
                out.add(k)
    return out


def load(path):
    """论文口径：剔 `item` 含 `#r` 的重复行；pred 空/非数保留为 None（口径 A 丢、B 当弃答）；
    `pred ≥ 1e5` 的**异常行剔除**（= `reporting.exclusions`，与 `p4_decomp_verify.py` 同源）。"""
    out, seen = [], set()
    if not os.path.exists(path):
        return out
    with io.open(path, encoding='utf-8-sig', errors='replace') as f:
        for r in csv.DictReader(f):
            k = (r.get('item') or '').strip()
            if not k or '#r' in k:            # ★ 论文口径（a5_report.py::load）
                continue
            if k in seen:
                continue
            seen.add(k)
            s = (r.get('pred') or '').strip()
            v = None
            if s != '':
                try:
                    v = float(s)
                except ValueError:
                    v = None
            if v is not None and v >= 1e5:    # 异常值剔除
                continue
            out.append((k, float(r.get('gt') or 0), v))
    return out


def stats(rows, mode='A'):
    if mode == 'A':
        rows = [(i, g, p) for (i, g, p) in rows if p is not None]
    else:
        rows = [(i, g, (0.0 if p is None else p)) for (i, g, p) in rows]
    n = len(rows)
    G = sum(g for _, g, _ in rows)
    ans = [(g, p) for _, g, p in rows if p > 0]
    nz = sum(1 for _, _, p in rows if p == 0)
    st = dict(n=n, n_ans=len(ans), G=G, GN=sum(g for g, _ in ans), P=sum(p for _, p in ans),
              zeros=nz, zerorate=(100.0 * nz / n) if n else float('nan'),
              S=None, w=None, rt=None, ra=None, why='')
    if n == 0:
        st['why'] = '空集'; return st
    if st['n_ans'] == 0:
        st['why'] = '全弃答（G_N=0）'; return st
    if st['n_ans'] == n:
        st['why'] = '无弃答 ⇒ ρ_total ≥ 0 ⇒ S 无定义'; return st
    if G <= 0 or st['GN'] <= 0:
        st['why'] = 'G 或 G_N ≤ 0'; return st
    w, rt, ra = st['GN'] / G, (st['P'] - G) / G, (st['P'] - st['GN']) / st['GN']
    st.update(w=w, rt=rt, ra=ra)
    if rt < 0:
        st['S'] = 100.0 * (G - st['GN']) / abs(G * rt)
        st['S_closed'] = 100.0 * (1 - w) / (1 - w * (1 + ra))
    else:
        st['why'] = 'ρ_total = %+.2f%% ≥ 0 ⇒ S 无定义' % (100 * rt)
    return st


def wilson(k, n, z=1.959963985):
    if n == 0:
        return (float('nan'), float('nan'))
    p = k / float(n)
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return ((c - h) / d, (c + h) / d)


def cell(fam, dom, arm='base'):
    """返回该家族该域该臂的 (zero-pool rows, non-zero-pool rows)。"""
    return (load(os.path.join(ZDIR, 'e1_%s_%s_%s.csv' % (fam, dom, arm))),
            load(os.path.join(NZDIR, 'e1_%s_%s_%s.csv' % (fam, dom, arm))))


def fx(v, nd=2, suf='%'):
    return 'n/a' if v is None else ('%.*f%s' % (nd, v, suf))


def main():
    print('=' * 118)
    print('【0】文件清单与 md5（零池 base 文件）；同时打印池规模（★ 已按论文口径剔掉 `#r` 重复行）')
    print('=' * 118)
    inv = {}
    for fam in FAMS:
        row = '  %-30s' % fam
        for dom in DOMAINS:
            p = os.path.join(ZDIR, 'e1_%s_%s_base.csv' % (fam, dom))
            raw = items(p)
            kept = load(p)
            nanom = len(raw) - len(kept)
            inv[(fam, dom)] = md5f(p) if os.path.exists(p) else 'MISSING'
            row += ' %s=%d%s' % (dom, len(kept), ('(-%d异常)' % nanom) if nanom else '')
        print(row)
    print('  ⇒ 7 个家族 × 4 个域**全部存在**（含 `base`；`permit`/`channel` 见【1】）。')
    print('  ⇒ 上表是**用于统计**的行数（已剔异常值）；同 item 交集另用**原始 item 集**，见【1】。')
    print()
    print('  md5（zero pool / nonzero pool 的 `base` 文件，全 28×2 个）：')
    for fam in FAMS:
        for dom in DOMAINS:
            pz = os.path.join(ZDIR, 'e1_%s_%s_base.csv' % (fam, dom))
            pn = os.path.join(NZDIR, 'e1_%s_%s_base.csv' % (fam, dom))
            print('     %-30s %-9s zero=%s nz=%s'
                  % (fam, dom, md5f(pz)[:16] if os.path.exists(pz) else 'MISSING',
                     md5f(pn)[:16] if os.path.exists(pn) else 'MISSING'))

    print()
    print('=' * 118)
    print('【1】评审要的三条臂是否都在？（zero pool 文件计数）')
    print('=' * 118)
    for arm in ('base', 'permit', 'channel'):
        n_fam = sum(1 for fam in FAMS for dom in DOMAINS
                    if os.path.exists(os.path.join(ZDIR, 'e1_%s_%s_%s.csv' % (fam, dom, arm))))
        n_nz = sum(1 for fam in FAMS for dom in DOMAINS
                   if os.path.exists(os.path.join(NZDIR, 'e1_%s_%s_%s.csv' % (fam, dom, arm))))
        print('  %-8s zero-pool 文件 %2d/28 ｜ non-zero-pool 文件 %2d/28' % (arm, n_fam, n_nz))

    # ---- item 集 ----
    Z, NZ = {}, {}
    for fam in FAMS:
        for dom in DOMAINS:
            Z[(fam, dom)] = items(os.path.join(ZDIR, 'e1_%s_%s_base.csv' % (fam, dom)))
            NZ[(fam, dom)] = items(os.path.join(NZDIR, 'e1_%s_%s_base.csv' % (fam, dom)))
    print()
    print('  pool 不相交性（zero ∩ non-zero 应为空）：',
          all(not (Z[(f, d)] & NZ[(f, d)]) for f in FAMS for d in DOMAINS))
    interZ = {d: set.intersection(*[Z[(f, d)] for f in FAMS]) for d in DOMAINS}
    interNZ = {d: set.intersection(*[NZ[(f, d)] for f in FAMS]) for d in DOMAINS}
    interU = {d: set.intersection(*[Z[(f, d)] | NZ[(f, d)] for f in FAMS]) for d in DOMAINS}
    print('  同 item 交集（跨 7 家族）：')
    for d in DOMAINS:
        print('     %-9s zero=%-4d non-zero=%-4d union=%-4d' % (d, len(interZ[d]), len(interNZ[d]), len(interU[d])))
    print('     dense(st_a+ucf) 交集 zero=%d non-zero=%d union=%d ｜ aerial=%d/%d/%d'
          % (len(interZ['st_a']) + len(interZ['ucf']), len(interNZ['st_a']) + len(interNZ['ucf']),
             len(interU['st_a']) + len(interU['ucf']),
             len(interZ['visdrone']) + len(interZ['aitod']),
             len(interNZ['visdrone']) + len(interNZ['aitod']),
             len(interU['visdrone']) + len(interU['aitod'])))

    print()
    print('=' * 118)
    print('【2】口径复核：我的流水线能否逐位复现 §M.19.2 与 §M.19.3？')
    print('=' * 118)
    M192 = {'gemma3-12b': (0, 0, 5, 4), 'InternVL3_5-8B': (1, 1, 95, 59),
            'Phi-3.5-vision-instruct': (0, 0, 92, 105), 'llava-onevision-qwen2-7b-ov': (0, 0, 134, 101),
            'qwen3-vl-32b-awq': (102, 166, 268, 149), 'qwen25vl-72b-awq': (0, 0, 121, 93),
            'internvl25-8b-awq': (0, 0, 128, 102)}
    ok192 = True
    for fam in FAMS:
        got = []
        for dom in DOMAINS:
            got.append(sum(1 for _, _, p in cell(fam, dom)[0] if p == 0))
        ok = tuple(got) == M192[fam]
        ok192 &= ok
        print('  §M.19.2 base zeros %-28s 得 %-22s 期望 %-22s %s'
              % (fam, str(tuple(got)), str(M192[fam]), 'OK' if ok else '!!'))
    M193 = {'gemma3-12b': 0.0, 'InternVL3_5-8B': 0.8, 'Phi-3.5-vision-instruct': 0.0,
            'llava-onevision-qwen2-7b-ov': 0.0, 'qwen3-vl-32b-awq': 95.3,
            'qwen25vl-72b-awq': 0.0, 'internvl25-8b-awq': 0.0}
    ok193 = True
    for fam in FAMS:
        rows = [r for d in DENSE for r in cell(fam, d)[0] if r[0] in interZ[d]]
        z = sum(1 for _, _, p in rows if p == 0)
        n = len(rows)
        got = 100.0 * z / n if n else float('nan')
        ok = abs(got - M193[fam]) < 0.06
        ok193 &= ok
        print('  §M.19.3 dense  rate   %-28s 得 %6.2f%% (n=%d) 期望 %5.1f%% %s'
              % (fam, got, n, M193[fam], 'OK' if ok else '!!'))
    print('  ⇒ §M.19.2 %s ｜ §M.19.3 %s' % ('**逐位一致**' if ok192 else '**不一致**',
                                            '**逐位一致**' if ok193 else '**不一致**'))
    if not (ok192 and ok193):
        sys.exit('!! 口径未对齐，后续数字不可用')

    print()
    print('=' * 118)
    print('【3】★ 评审要的那张表：7 家族 × (dense, aerial)')
    print('      ★ 两个**分母不同**的量必须分开报（这正是评审把两件事写进一条判据时容易混的地方）：')
    print('        · zero-pool rate = 「语料答 0 的项里，该家族也答 0」的比例 = §M.19.3 印的那个量（分母=zero 池交集）')
    print('        · overall rate    = 「该域全部项里该家族答 0」的比例（分母=两池并集交集）')
    print('        · $S$ 必须用**整集**（两池并集），因为 ρ_total 定义在全项上')
    print('=' * 118)

    def cellstats(fam, doms, which='union'):
        rows = []
        for d in doms:
            keep = interZ[d] if which == 'zero' else (interU[d] if which == 'union' else interNZ[d])
            z, nz = cell(fam, d)
            rows += [(i, g, p) for (i, g, p) in z + nz if i in keep]
        return stats(rows)

    print('  %-30s %10s %10s %10s %9s' % ('DENSE (st_a+ucf)', 'zero-pool%', 'overall%', 'S%', 'n(zero/union)'))
    for fam in FAMS:
        zp = cellstats(fam, DENSE, 'zero')
        ov = cellstats(fam, DENSE, 'union')
        tag = '  (anchor)' if fam in ANCHORS else ''
        print('  %-30s %9.2f%% %9.2f%% %10s %9s%s'
              % (fam, zp['zerorate'], ov['zerorate'], fx(ov['S']),
                 '%d/%d' % (zp['n'], ov['n']), tag))
    print()
    print('  %-30s %10s %10s %10s %9s' % ('AERIAL (VisDrone+AI-TOD)', 'zero-pool%', 'overall%', 'S%', 'n(zero/union)'))
    for fam in FAMS:
        zp = cellstats(fam, AERIAL, 'zero')
        ov = cellstats(fam, AERIAL, 'union')
        tag = '  (anchor)' if fam in ANCHORS else ''
        print('  %-30s %9.2f%% %9.2f%% %10s %9s%s'
              % (fam, zp['zerorate'], ov['zerorate'], fx(ov['S']),
                 '%d/%d' % (zp['n'], ov['n']), tag))
    print()
    print('  $S$ 无定义的原因（dense）：')
    for fam in FAMS:
        ov = cellstats(fam, DENSE, 'union')
        if ov['S'] is None:
            print('     %-30s %s' % (fam, ov['why']))

    print()
    print('=' * 118)
    print('【4】★ 逐条评估评审自己的判据（在**非锚家族**上）')
    print('     判据：base 答零率 ≥ 30% 且 $S \\ge 50\\%$；Wilson 95% **下界** > 20%')
    print('=' * 118)
    nonanchor = NONQWEN
    print('  评审要的"非 Qwen 家族"= **%d 个**：%s' % (len(nonanchor), ', '.join(nonanchor)))
    print('  （本材料共 7 个家族；另 2 个是 Qwen 锚：%s。' % ', '.join(QWEN))
    print('   ★ 注意：论文写"3 个锚"，但按"非 Qwen"分组时 InternVL2.5-8B-AWQ 属**非 Qwen** ⇒ 5 个。）')
    print('  ★★ **$S$ 一律用整集（两池并集）算** —— 它定义在全项上（ρ_total 的分母是全部 GT）。')
    print('     把 $S$ 只算在 zero 池上会得到虚高的值（例：LLaVA aerial 71.50% vs 正确的 28.78%）。')
    for lab, doms in (('DENSE', DENSE), ('AERIAL', AERIAL)):
        for rate_lab, which in (('zero-pool', 'zero'), ('overall', 'union')):
            print()
            print('  —— %s ／ rate 用 %s（$S$ 仍用整集）——' % (lab, rate_lab))
            print('  %-30s %10s %9s %8s %9s %8s %-7s' % ('family', 'rate%', 'Wilson lo', 'lo>20%', 'S%', 'S≥50%', 'PASS'))
            npass = 0
            for fam in nonanchor:
                st = cellstats(fam, doms, which)
                sv = cellstats(fam, doms, 'union')
                lo, hi = wilson(st['zeros'], st['n'])
                c1 = st['zerorate'] >= 30.0
                c2 = sv['S'] is not None and sv['S'] >= 50.0
                c3 = (100 * lo) > 20.0
                p = c1 and c2 and c3
                if p:
                    npass += 1
                print('  %-30s %9.2f%% %8.2f%% %8s %9s %8s %-7s'
                      % (fam, st['zerorate'], 100 * lo, c1, fx(sv['S']), c2, 'PASS' if p else 'fail'))
            print('  ⇒ **%s ／ %s rate**：满足全部三条的家族数 = **%d / %d**（判据要求 ≥ 2/5）'
                  % (lab, rate_lab, npass, len(nonanchor)))
    print()
    print('  （对照：两个 Qwen 锚 —— 它们不是评审要的"非 Qwen"家族，列此仅供参考）')
    for lab, doms in (('DENSE', DENSE), ('AERIAL', AERIAL)):
        for fam in QWEN:
            st = cellstats(fam, doms, 'zero')
            sv = cellstats(fam, doms, 'union')
            lo, hi = wilson(st['zeros'], st['n'])
            c1, c2, c3 = st['zerorate'] >= 30.0, (sv['S'] is not None and sv['S'] >= 50.0), (100 * lo) > 20.0
            print('     %-6s %-28s zero-pool=%6.2f%% Wilson lo=%6.2f%% S(整集)=%8s ⇒ %s'
                  % (lab, fam, st['zerorate'], 100 * lo, fx(sv['S']), 'PASS' if (c1 and c2 and c3) else 'fail'))

    print()
    print('=' * 118)
    print('【5】敏感性：口径 B（不可解析 pred 当弃答）与逐域（不合并；★ 逐域 rate 用 zero 池、$S$ 用整集）')
    print('=' * 118)
    for fam in FAMS:
        def rows_of(doms, which):
            out = []
            for d in doms:
                keep = interZ[d] if which == 'zero' else interU[d]
                z, nz = cell(fam, d)
                out += [(i, g, p) for (i, g, p) in z + nz if i in keep]
            return out
        a = stats(rows_of(DENSE, 'union'), 'A')
        b = stats(rows_of(DENSE, 'union'), 'B')
        dd = []
        for dom in DOMAINS:
            zr = stats(rows_of([dom], 'zero'))
            sr = stats(rows_of([dom], 'union'))
            dd.append('%s z=%5.2f%% S=%s' % (dom, zr['zerorate'], fx(sr['S'])))
        print('  %-30s dense S(A)=%-8s S(B)=%-8s' % (fam, fx(a['S']), fx(b['S'])))
        print('      ' + ' ｜ '.join(dd))

    print()
    print('=' * 118)
    print('【6】总调用量核算：评审要 ≈4,500 次（5 家族 × 2 域 × 150 项 × 3 臂）')
    print('=' * 118)
    tot = {}
    for arm in ('base', 'permit', 'channel'):
        n = 0
        for fam in FAMS:
            for dom in DOMAINS:
                p = os.path.join(ZDIR, 'e1_%s_%s_%s.csv' % (fam, dom, arm))
                n += len(load(p))
        tot[arm] = n
    print('  实际在手（zero pool，7 家族 × 4 域）：base=%d ｜ permit=%d ｜ channel=%d ｜ 合计 %d 次'
          % (tot['base'], tot['permit'], tot['channel'], sum(tot.values())))
    n4 = sum(1 for fam in FAMS for dom in DOMAINS for arm in ('base', 'permit', 'channel')
             if os.path.exists(os.path.join(ZDIR, 'e1_%s_%s_%s.csv' % (fam, dom, arm))))
    print('  另加 non-zero pool 3 臂 × %d 格。' % n4)
    print()
    print('  —— 只数**评审点名的那一子集**：5 个非 Qwen 家族 × {st_a, ucf} × 3 臂 ——')
    sub = 0
    for fam in NONQWEN:
        per = []
        for dom in DENSE:
            k = 0
            for arm in ('base', 'permit', 'channel'):
                p = os.path.join(ZDIR, 'e1_%s_%s_%s.csv' % (fam, dom, arm))
                k += len(items(p))
            per.append('%s=%d×3臂(%d/臂)' % (dom, k, k // 3))
            sub += k
        print('     %-30s %s' % (fam, ' ｜ '.join(per)))
    print('     小计 = **%d 次**（评审估 ≈4,500）' % sub)
    print('     ⚠ 差异：st_a 的池是 **103** 项（不是 150），ucf 是 150–180；'
          '且这 5 家里 Phi 的 st_a/ucf 各剔了 22/26 个异常值后才参与统计。')


if __name__ == '__main__':
    main()
