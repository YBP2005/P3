# -*- coding: utf-8 -*-
"""s15_five_build_S.py — S15：把**头条量 $S$** 算到五个 Qwen3-VL-32B 部署上（只读）。

═══════════════════════════════════════════════════════════════════════════════════════
【为什么有这个脚本】
多条在册条目（v0573）指出：附录 §M.18.8 的 5×4 表报的是 **answered-zero rate**，
而论文头条是 **$S$（ground-truth-weighted abstention share）** ⇒
"标题需要的是 $S$，不是答零率"，五部署比较**从未显示标题所依赖的那个量**。

【$S$ 的定义（逐字出处 + 行号）】
  · 主稿 `PaperB_英文稿_PR_20260919.md` **L386–391**（命题 4）：
      `ρ_total = −(1−w) + w·ρ_answered`，`w = G_N/G`，
      `S = (1−w)/[1−w(1+ρ_answered)]`；"it is the one behind the **82–94%** of §5.5
      for the **base contract arm**"
  · 主稿 **L516–521**（§5.5）：同式，"evaluated here it gives **82–94%** … (82.1–94.2%;
      unweighted abstention rate **53.9–68.2%**)"
  · 主稿 **L236**（§3.1）：弃答必须按**三元组**报 —— "the rate, ρ on answered items only,
      and the **abstention share of the total under-count**"
  · 补充材料 `PaperB_英文补充材料_PR_20260919.md` **J.1（L520–575）**：
      `ρ_total=(P−G)/G`、`ρ_answered=(P−G_N)/G_N`、`P=G_N(1+ρ_answered)`，
      **"abstained items contributing `pred=0`"**；并印出四格的 $S$ 与 unweighted rate
  · 补充材料 **J.1 前言 L515–518** 的数据口径（= 附录 I 台账）：
      "de-duplicate by `item`, drop `pred ≥ 1e5`, **drop unparseable `pred`**,
       drop `gt ≤ 0` from ratio computations"
  · 权威实现 `analysis/work/p4_decomp_verify.py::unit_stats()`：
      `S = 100·(G−G_N)/|G·ρ_total|`（**仅当 ρ_total<0**，否则 $S$ 无定义）；
      `G_N = Σgt(pred>0)`；`P = Σpred(pred>0)`；不可解析的 `pred` **整行剔除**。

    ⇒ $S$ = **弃答项所承载的 GT 质量 ÷ 总欠计**（两者都以 GT 为单位）：
       $S = (G-G_N)/(G-P)$。**它不是答零率**：分母是 GT 加权的欠计量，不是项数。

【我实测到的三个结构性事实（脚本内逐步断言）】
  ① 语料四格 base 单元 = `pod_mirror/dense_results/vlm_{st_a,ucf}_base_whole.csv` 与
     `pod_mirror/aerial_results/aer_{visdrone,aitod}_base.csv`；本脚本复算得
     $S$ = **94.24 / 93.69 / 82.13 / 83.79 %**，与 J.1 印出的 94.2/93.7/82.1/83.8 **逐位一致**
     （unweighted rate 亦一致：56.59/53.89/68.25/68.14）。
  ② `analysis/e2_newh20/` 的 census 文件**按池拆开**：
     `e1_..._base.csv` = **zero pool**，`nz__e1_..._base.csv` = **non-zero pool**，两者**无交集**。
  ③ **AWQ-4bit / BF16 的 zero 池比语料大**（st_a 412 vs 103、ucf 720 vs 180），
     而 VisDrone / AI-TOD 两池并集与语料单元**逐一相等**（400 / 226）
     ⇒ 五部署比较只能在**共同 item 集**上做。

【三个部署 × 域的口径分歧（不是同一件事，分开报）】
  A. **剔除**不可解析 `pred`（附录 I / `p4_decomp_verify.py` 的现行口径）
  B. 把不可解析 `pred` **当作弃答**（`pred=0`）
  两者只在 GPTQ-W4 上有差别（它有解析失败）。

用法：python -u s15_five_build_S.py
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
import io
import os
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

POD = RP('analysis', 'data', 'pod_mirror')
E2 = RP('analysis', 'e2_newh20')
BUILDS = [('AWQ-4bit', 'awq'), ('AWQ-8bit', 'awq8'), ('BF16', 'bf16'), ('FP8', 'fp8'), ('GPTQ-W4', 'gptq')]
DOMAINS = [('st_a', 'ShanghaiTech-A'), ('ucf', 'UCF-QNRF'), ('visdrone', 'VisDrone'), ('aitod', 'AI-TOD')]
CORPUS = {'st_a': (POD, 'dense_results', 'vlm_st_a_base_whole.csv'),
          'ucf': (POD, 'dense_results', 'vlm_ucf_base_whole.csv'),
          'visdrone': (POD, 'aerial_results', 'aer_visdrone_base.csv'),
          'aitod': (POD, 'aerial_results', 'aer_aitod_base.csv')}
J1 = {'st_a': (94.2, 56.6), 'ucf': (93.7, 53.9), 'visdrone': (82.1, 68.2), 'aitod': (83.8, 68.1)}


def load(path):
    """按附录 I 口径读一行的**原始**内容：按 item 去重、剔 pred≥1e5。
    不可解析/为空的 pred 保留为 None（口径 A 丢弃、口径 B 视为弃答 —— 由调用方决定）。"""
    out, seen = [], set()
    with io.open(path, encoding='utf-8-sig', errors='replace') as f:
        for r in csv.DictReader(f):
            k = (r.get('item') or '').strip()
            if not k or k in seen:
                continue
            seen.add(k)
            s = (r.get('pred') or '').strip()
            v = None
            if s != '':
                try:
                    v = float(s)
                except ValueError:
                    v = None
            if v is not None and v >= 1e5:
                continue
            out.append((k, float(r.get('gt') or 0), v))
    return out


def stats(rows, mode='A'):
    """mode='A' 剔除空 pred；mode='B' 空 pred 视为 pred=0（弃答）。"""
    if mode == 'A':
        rows = [(i, g, p) for (i, g, p) in rows if p is not None]
    else:
        rows = [(i, g, (0.0 if p is None else p)) for (i, g, p) in rows]
    n = len(rows)
    G = sum(g for _, g, _ in rows)
    ans = [(g, p) for _, g, p in rows if p > 0]
    zero = sum(1 for _, _, p in rows if p == 0)
    st = dict(n=n, n_ans=len(ans), G=G, GN=sum(g for g, _ in ans), P=sum(p for _, p in ans),
              zerorate=100.0 * zero / n if n else float('nan'),
              ansrate=100.0 * len(ans) / n if n else float('nan'),
              S=None, w=None, rt=None, ra=None, why='')
    if n == 0:
        st['why'] = '空集'
        return st
    if st['n_ans'] == 0:
        st['why'] = '全弃答（GN=0）'
        return st
    if st['n_ans'] == n:
        st['why'] = '无弃答（ρ_total≥0，S 无定义）'
        return st
    if G <= 0 or st['GN'] <= 0:
        st['why'] = 'G 或 G_N ≤ 0'
        return st
    w, rt, ra = st['GN'] / G, (st['P'] - G) / G, (st['P'] - st['GN']) / st['GN']
    st.update(w=w, rt=rt, ra=ra)
    if rt < 0:
        st['S'] = 100.0 * (G - st['GN']) / abs(G * rt)
        st['S_closed'] = 100.0 * (1 - w) / (1 - w * (1 + ra))
    else:
        st['why'] = 'ρ_total = %+.2f%% ≥ 0 ⇒ S 无定义' % (100 * rt)
    return st


def census(build, dom):
    return (load(os.path.join(RP('analysis', 'e2_newh20'), 'e1_qwen3-vl-32b-%s_%s_base.csv' % (build, dom))),
            load(os.path.join(RP('analysis', 'e2_newh20'), 'nz__e1_qwen3-vl-32b-%s_%s_base.csv' % (build, dom))))


def corpus_rows(dom):
    return load(os.path.join(*CORPUS[dom]))


def fx(v, nd=2, suf='%'):
    return 'n/a' if v is None else ('%.*f%s' % (nd, v, suf))


def main():
    print('=' * 120)
    print('【0】口径复核：语料四格 base 单元能否复算附录 J.1 印出的 $S$ 与 unweighted abstention rate')
    print('=' * 120)
    corpus = {}
    ok_all = True
    for dom, dn in DOMAINS:
        rows = corpus_rows(dom)
        corpus[dom] = rows
        s = stats(rows)
        tS, tab = J1[dom]
        ok = abs(s['S'] - tS) < 0.06 and abs(s['ansrate'] and (100 - s['ansrate']) - tab) < 0.06
        ok_all &= ok
        print('  %-13s n=%-4d 作答=%-4d  S=%6.2f%% (J.1 %5.1f%%)  abstention=%6.2f%% (J.1 %5.1f%%)  '
              'ρ_total=%7.2f%%  w=%.4f  ρ_ans=%7.2f%%  %s'
              % (dn, s['n'], s['n_ans'], s['S'], tS, 100 - s['ansrate'], tab,
                 100 * s['rt'], s['w'], 100 * s['ra'], 'OK' if ok else '!! 不符'))
    print('  ⇒ 复算与 J.1 %s；$S = (G−G_N)/(G−P)$ 与 `p4_decomp_verify.py` 的闭式互证。'
          % ('**逐位一致**' if ok_all else '**不一致 ⇒ 后续结论不可用**'))
    if not ok_all:
        sys.exit('口径未对齐，停止')

    print()
    print('=' * 120)
    print('【1】census 文件的池结构（zero / non-zero），以及它相对语料单元的覆盖')
    print('=' * 120)
    cells = {}
    for dom, dn in DOMAINS:
        cz = set(i for i, _, _ in corpus[dom])
        print('  %-13s 语料单元 n=%-4d' % (dn, len(cz)))
        for bn, b in BUILDS:
            z, nz = census(b, dom)
            cells[(b, dom)] = (z, nz)
            zi, ni = set(i for i, _, _ in z), set(i for i, _, _ in nz)
            raw = [x for x in (z + nz)]
            nempty = sum(1 for _, _, p in raw if p is None)
            print('     %-9s zero=%-4d nz=%-4d  ∩=%-3d  so-far空 pred=%-3d ｜ z∪nz ⊆ 语料? %s'
                  % (bn, len(zi), len(ni), len(zi & ni), nempty,
                     'YES' if (zi | ni) <= cz else 'NO(超集)'))
    print('  ⇒ 两池**无交集**（∩ 全为 0）；AWQ-4bit/BF16 的 zero 池在 st_a/ucf 上**大于**语料单元。')

    # ---- 可比 item 集：五 build 的**原始**（未剔空 pred 前）item 集的交集 ----
    common = {}
    for dom, dn in DOMAINS:
        sets = [set(i for i, _, _ in cells[(b, dom)][0]) | set(i for i, _, _ in cells[(b, dom)][1])
                for _, b in BUILDS]
        common[dom] = set.intersection(*sets)

    print()
    print('=' * 120)
    print('【2】五部署可比 item 集 = 五 build 原始 item 集的交集（对齐 M.18.8 的 "common item sets"）')
    print('=' * 120)
    for dom, dn in DOMAINS:
        zi = set.intersection(*[set(i for i, _, _ in cells[(b, dom)][0]) for _, b in BUILDS])
        ni = set.intersection(*[set(i for i, _, _ in cells[(b, dom)][1]) for _, b in BUILDS])
        print('  %-13s zero 交集=%-4d nz 交集=%-4d 并=%-4d（M.18.8 印 103/180/150/150 口径）'
              ' ｜ 语料单元 n=%-4d ｜ 语料∩可比集=%d'
              % (dn, len(zi), len(ni), len(common[dom]), len(corpus[dom]),
                 len(set(i for i, _, _ in corpus[dom]) & common[dom])))

    def cell_rows(b, dom):
        z, nz = cells[(b, dom)]
        return [(i, g, p) for (i, g, p) in z + nz if i in common[dom]]

    def grid(mode='A', key=None):
        out = {}
        for dom, dn in DOMAINS:
            out[dom] = {}
            for bn, b in BUILDS:
                out[dom][bn] = stats(cell_rows(b, dom), mode)
            out[dom]['_corpus'] = stats([r for r in corpus[dom] if r[0] in common[dom]], mode)
        return out

    A = grid('A')

    print()
    print('=' * 120)
    print('【2b】交集把语料单元截掉了多少？—— $S$ 只在同一 item 集上可比，这一步决定可比性的边界')
    print('=' * 120)
    print('  %-13s %10s %10s %16s %16s' % ('域', '语料 n', '可比集 n', '语料:零池GT占比', '可比集:零池GT占比'))
    for dom, dn in DOMAINS:
        cr = corpus[dom]
        keep = [r for r in cr if r[0] in common[dom]]
        def zero_mass(rows):
            G = sum(g for _, g, _ in rows)
            GZ = sum(g for _, g, p in rows if p == 0)
            return 100.0 * GZ / G if G else float('nan')
        print('  %-13s %10d %10d %15.2f%% %15.2f%%'
              % (dn, len(cr), len(keep), zero_mass(cr), zero_mass(keep)))

    print()
    print('=' * 120)
    print('【3】$S$（GT 加权弃答份额）5 部署 × 4 域，口径 A（剔除不可解析 pred —— 附录 I 现行口径）')
    print('=' * 120)
    print('  %-13s' % '域' + ''.join('%13s' % bn for bn, _ in BUILDS) + '%14s' % '语料(AWQ锚)')
    for dom, dn in DOMAINS:
        row = '  %-13s' % dn
        for bn, _ in BUILDS:
            v = A[dom][bn]['S']
            row += '%13s' % (fx(v) + ('**' if (v is not None and v > 100) else ''))
        cv = A[dom]['_corpus']['S']
        print(row + '%14s' % (fx(cv) + ('**' if (cv is not None and cv > 100) else '')))
    print('  （** = $S>100\\%$：M.39 已声明"比值越过 100% 时 $S$ 不再是份额"——这类格子不能当份额读。）')

    print()
    print('=' * 120)
    print('【3b】$S$ 的**条件数**：ρ_total（净欠计）。$S=(G−G_N)/(G−P)$，ρ_total→0 时 $S$ 病态。')
    print('=' * 120)
    print('  %-13s' % '域' + ''.join('%13s' % bn for bn, _ in BUILDS))
    for dom, dn in DOMAINS:
        row = '  %-13s' % dn
        for bn, _ in BUILDS:
            s = A[dom][bn]
            row += '%12s' % ('n/a' if s['rt'] is None else '%+.2f%%' % (100 * s['rt']))
        print(row)

    print()
    print('=' * 120)
    print('【4】同一格子上的 answered-zero rate（= M.18.8 现在报的量）')
    print('=' * 120)
    print('  %-13s' % '域' + ''.join('%13s' % bn for bn, _ in BUILDS) + '%14s' % '语料(AWQ锚)')
    for dom, dn in DOMAINS:
        row = '  %-13s' % dn
        for bn, _ in BUILDS:
            row += '%12.2f%%' % A[dom][bn]['zerorate']
        print(row + '%13.2f%%' % A[dom]['_corpus']['zerorate'])

    print()
    print('=' * 120)
    print('【5】$S$ 无定义的格子（ρ_total ≥ 0 ⇒ 该部署在该域**不是净欠计**，$S$ 按定义不存在）')
    print('=' * 120)
    undef = 0
    for dom, dn in DOMAINS:
        for bn, _ in BUILDS:
            s = A[dom][bn]
            if s['S'] is None and s['n'] and s['n_ans'] not in (0, s['n']):
                undef += 1
                print('  %-13s %-9s n=%-4d 作答=%-4d 零率=%6.2f%%  ρ_total=%+8.2f%%  ⇒ %s'
                      % (dn, bn, s['n'], s['n_ans'], s['zerorate'], 100 * s['rt'] if s['rt'] is not None else float('nan'), s['why']))
    print('  ⇒ 共 **%d/20** 格 $S$ 无定义。**这一条本身就是答案的一半**：'
          'M.18.8 用答零率之所以能填满 5×4，是因为答零率**即使不是净欠计也有定义**；'
          '$S$ 只在净欠计的格上存在。' % undef)

    print()
    print('=' * 120)
    print('【6】域内跨部署极差（pp）—— 头条 82–94% 只在**一个**部署上测过')
    print('=' * 120)
    print('  %-13s %6s %12s %12s %12s %14s %14s'
          % ('域', '#S有效', 'S 极差', 'S极差剔GPTQ', '零率极差', 'S 最小→最大', '零率最小→最大'))
    for dom, dn in DOMAINS:
        sv = sorted(A[dom][bn]['S'] for bn, _ in BUILDS if A[dom][bn]['S'] is not None)
        sg = sorted(A[dom][bn]['S'] for bn, b in BUILDS if b != 'gptq' and A[dom][bn]['S'] is not None)
        zv = sorted(A[dom][bn]['zerorate'] for bn, _ in BUILDS)
        print('  %-13s %6d %11s %11s %12.2f %14s %8.2f→%-6.2f'
              % (dn, len(sv), ('%.2f' % (sv[-1] - sv[0])) if len(sv) > 1 else 'n/a',
                 ('%.2f' % (sg[-1] - sg[0])) if len(sg) > 1 else 'n/a',
                 zv[-1] - zv[0],
                 ('%.2f→%.2f' % (sv[0], sv[-1])) if len(sv) > 1 else 'n/a', zv[0], zv[-1]))
    # 四域合并（只在共同集上，两池都算）
    pc = {}
    for bn, b in BUILDS:
        rows = []
        for dom, dn in DOMAINS:
            rows += cell_rows(b, dom)
        pc[bn] = stats(rows)
    sv = sorted(pc[bn]['S'] for bn, _ in BUILDS if pc[bn]['S'] is not None)
    zv = sorted(pc[bn]['zerorate'] for bn, _ in BUILDS)
    print('  %-13s %6d %13s %13.2f %14s %8.2f→%-6.2f'
          % ('四域合并', len(sv), ('%.2f' % (sv[-1] - sv[0])) if len(sv) > 1 else 'n/a', zv[-1] - zv[0],
             ('%.2f→%.2f' % (sv[0], sv[-1])) if len(sv) > 1 else 'n/a', zv[0], zv[-1]))
    print('  四域合并逐部署：')
    for bn, _ in BUILDS:
        print('     %-9s n=%-4d S=%-8s 零率=%6.2f%%  ρ_total=%+8.2f%%  w=%.4f  未定义原因=%s'
              % (bn, pc[bn]['n'], fx(pc[bn]['S']), pc[bn]['zerorate'],
                 100 * pc[bn]['rt'] if pc[bn]['rt'] is not None else float('nan'),
                 pc[bn]['w'] if pc[bn]['w'] is not None else float('nan'), pc[bn]['why'] or '—'))

    print()
    print('=' * 120)
    print('【7】排序稳定性：$S$ 与答零率 各自的名次（只在 $S$ 有定义的部署上比 $S$）')
    print('=' * 120)

    def order(dom, key):
        if key == 'S':
            v = [(A[dom][bn]['S'], bn) for bn, _ in BUILDS if A[dom][bn]['S'] is not None]
        else:
            v = [(A[dom][bn]['zerorate'], bn) for bn, _ in BUILDS]
        v.sort(reverse=True)
        return [b for _, b in v]

    for key, lab in (('S', '$S$'), ('Z', '答零率')):
        print('  %s 名次（高→低）：' % lab)
        for dom, dn in DOMAINS:
            print('     %-13s %s' % (dn, ' > '.join(order(dom, key))))
    print('  $S$ 的名次在四域上是否一致：',
          'YES（同一顺序）' if len(set(tuple(order(d, 'S')) for d, _ in DOMAINS)) == 1
          else 'NO ⇒ ' + ' ｜ '.join('%s: %s' % (dn, '>'.join(order(d, 'S'))) for d, dn in DOMAINS))
    print('  答零率的名次在四域上是否一致：',
          'YES（同一顺序）' if len(set(tuple(order(d, 'Z')) for d, _ in DOMAINS)) == 1
          else 'NO ⇒ ' + ' ｜ '.join('%s: %s' % (dn, '>'.join(order(d, 'Z'))) for d, dn in DOMAINS))
    # S 与零率在同一域内是否同序
    for dom, dn in DOMAINS:
        if tuple(order(dom, 'S')) == tuple(order(dom, 'Z')):
            print('     %-13s $S$ 与答零率**同序**' % dn)
        else:
            print('     %-13s $S$ 与答零率**不同序**：S=%s ｜ 零率=%s'
                  % (dn, '>'.join(order(dom, 'S')), '>'.join(order(dom, 'Z'))))

    print()
    print('=' * 120)
    print('【8】敏感性：不可解析 `pred` **剔除**（口径 A）vs **当作弃答**（口径 B）')
    print('=' * 120)
    B = grid('B')
    print('  %-13s %-10s %12s %12s %10s %8s' % ('域', 'build', 'S(A 剔除)', 'S(B 当弃答)', 'Δ(pp)', '空 pred'))
    worst = 0.0
    for dom, dn in DOMAINS:
        for bn, b in BUILDS:
            a, bb = A[dom][bn], B[dom][bn]
            ne = sum(1 for _, _, p in cell_rows(b, dom) if p is None)
            if ne == 0:
                continue
            da = (bb['S'] - a['S']) if (a['S'] is not None and bb['S'] is not None) else None
            if da is not None:
                worst = max(worst, abs(da))
            print('  %-13s %-10s %12s %12s %10s %8d'
                  % (dn, bn, fx(a['S'], 4), fx(bb['S'], 4),
                     ('%+.4f' % da) if da is not None else 'n/a', ne))
    print('  ⇒ 只有 GPTQ-W4 有空 `pred`（其余四家 0 项）⇒ 这是**单家敏感性**。'
          '最大 |Δ| = **%.4f pp**%s' % (worst, '（可忽略）' if worst < 0.05 else '（**不可忽略**）'))

    print()
    print('=' * 120)
    print('【9】$S$ 与答零率是否同一个量：同域内两者的名次一致性 + 极差对比（见【6】）')
    print('=' * 120)
    for dom, dn in DOMAINS:
        sv = sorted(A[dom][bn]['S'] for bn, _ in BUILDS if A[dom][bn]['S'] is not None)
        zv = sorted(A[dom][bn]['zerorate'] for bn, _ in BUILDS)
        print('  %-13s S 极差=%-8s  零率极差=%-7.2f  ⇒ 差 %.2f pp'
              % (dn, ('%.2f' % (sv[-1] - sv[0])) if len(sv) > 1 else 'n/a', zv[-1] - zv[0],
                 ((zv[-1] - zv[0]) - (sv[-1] - sv[0])) if len(sv) > 1 else float('nan')))


if __name__ == '__main__':
    main()
