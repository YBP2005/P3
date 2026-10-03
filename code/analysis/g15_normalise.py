# -*- coding: utf-8 -*-
"""g15_normalise.py —— 【G15 主脚本】把每个单元的**跨度**除以它所属旋钮的**动程**，看排序活不活得下来。

替代解释（[external-review]独立提出）：
   "某个旋钮的跨度（span）也许只是该旋钮**允许的输出动程**（travel）的单调函数，不是模型行为的属性。"
   他们举的证据：检测 τ 扫 0.02→0.90（≈45×），像素预算只走 100%→15%（≈6.7×）；
                F.10 只排除了**档数**与**端点**，从未排除**量程**。

三种检验，**主检验是"限在可归一单元上"的那一种**（替代解释只对"有动程"的旋钮作预测）：
  A 限域检验：只在**可辩护地定义了 R** 的单元集内重排；
  B 全域检验（敏感性）：把类别型旋钮按 **R = 1** 塞进同一张排名（**这是一个很强的假设**，故只作敏感性）；
  C 旋钮级检验：每族的中位/最大跨度 vs 该族 R —— 替代解释的**直接**预测是 Spearman ≈ +1。

只读：不写、不改任何已有文件。
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
import collections
import hashlib
import io
import json
import os
import re
import statistics as st
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
ROOT = NR()
W = RP('analysis', 'work')
SUPP = RP('PaperB_英文补充材料_PR_20260919.md')


def spearman(a, b):
    def rank(x):
        order = sorted(range(len(x)), key=lambda i: x[i])
        r = [0.0] * len(x)
        i = 0
        while i < len(order):
            j = i
            while j + 1 < len(order) and x[order[j + 1]] == x[order[i]]:
                j += 1
            avg = (i + j) / 2.0 + 1.0
            for k in range(i, j + 1):
                r[order[k]] = avg
            i = j + 1
        return r
    ra, rb = rank(a), rank(b)
    n = len(a)
    ma, mb = sum(ra) / n, sum(rb) / n
    num = sum((ra[i] - ma) * (rb[i] - mb) for i in range(n))
    den = (sum((v - ma) ** 2 for v in ra) * sum((v - mb) ** 2 for v in rb)) ** .5
    return num / den if den else float('nan')


# ───────── 动程表（每条的出处见 g15_levels.py 的输出，源文件逐条列在 src） ─────────
TRAVEL = {
    'det': dict(R=10.0,
                why='τ 实际只扫 {0.05,0.1,0.15,0.2,0.25,0.3,0.4,0.5}（8 档）⇒ 0.5/0.05 = **10.0×**',
                src='analysis/data/pod_mirror/A/det_yolo_ladder_visdrone_det.csv、'
                    'det_yolo_ladder_yolo12n.csv、<not released: '
                    'work/b_harvest_20260917/bbbc_eval/ladder.csv>（tau 列）'),
    'density_mult': dict(R=4.0, why='protocol=mult：value ∈ {0.5,0.75,1,1.25,1.5,2} ⇒ 2/0.5 = **4.0×**',
                         src='<not released: work/dm_ladder.csv>、analysis/data/pod_mirror/A/csrsta_ladder_st_a.csv、'
                             'csrucf_ladder_ucf.csv（protocol+value 列）'),
    'density_short': dict(R=1024 / 384, why='protocol=short：value ∈ {384,512,768,1024} px ⇒ 1024/384 = **2.667×**',
                          src='同上（short 行）'),
    'budget_nonzero': dict(R=1048576 / 200000.0,
                           why='budget ∈ {0,2e5,4e5,8e5,1048576}；**最小档 = 0 ⇒ 相对动程不可按比例定义**；'
                               '退化的非零段 = 1048576/200000 = **5.242×**',
                           src='analysis/data/pod_mirror/res_ctrl__{q32,ivl}/res_ctrl_*.csv（budget 列）'),
    'tiling_side': dict(R=6.0, why='档位 whole/tile2…tile6 ⇒ 网格边长 1…6 ⇒ **6×**（边长口径）',
                        src='analysis/data/pod_mirror/{tile_results,b2__out_32b_ctile,b2__out_8b_ctile}/*.csv（文件名档位）'),
    'tiling_count': dict(R=36.0, why='同族按**块数**口径：6²÷1² = **36×**（与边长口径差 6 倍，纯口径歧义）', src='同上'),
    'det_reviewer45': dict(R=0.90 / 0.02,
                           why='★ **评审所引的口径**：τ 0.02→0.90 ⇒ **45×**。'
                               '该区间出自 §4.3 的**可达性细网格**（177 点），**不是**跨度阶梯的区间 ⇒ 见 §未核实/§结论',
                           src='主稿 §4.3（细网格扫描）；与 det 的冻结阶梯文件**不是同一个测量**'),
    'categorical': dict(R=None, why='**类别型，没有可辩护的连续动程**（输出契约 4 臂；提示词族 V1–V5 五种指令）',
                        src='analysis/data/pod_mirror/b2__out_{ivl,q32}/E1.csv（arm 列）、dense_prompt_results/*_V*.csv'),
}


def knob_of(u):
    if u.startswith('det·'):
        return 'det'
    if u.startswith('density·'):
        return 'density'
    if u.startswith('VLM·pixel budget'):
        return 'budget'
    if u.startswith('VLM·tiling'):
        return 'tiling'
    if u.startswith('VLM·output contract'):
        return 'contract'
    if u.startswith('VLM·prompt family'):
        return 'prompt'
    # —— F.9 用的是英文行标签（"Detection, in-domain / VisDrone" 等），单独映射 ——
    if u.startswith('Detection'):
        return 'det'
    if u.startswith('Density regression'):
        return 'density'
    if u.startswith('VLM, pixel budget'):
        return 'budget'
    if u.startswith('VLM, output contract'):
        return 'contract'
    if u.startswith('VLM, prompt'):
        return 'prompt'
    if u.startswith('Tiling'):
        return 'tiling'
    return 'unknown'


def R_of(knob, v):
    if knob == 'det':
        return TRAVEL['det_reviewer45' if v.get('det45') else 'det']['R']
    if knob == 'density':
        return {'mult': TRAVEL['density_mult']['R'],
                'short': TRAVEL['density_short']['R']}.get(v.get('density'))
    if knob == 'budget':
        return TRAVEL['budget_nonzero']['R'] if v.get('budget', True) else None
    if knob == 'tiling':
        return {'side': TRAVEL['tiling_side']['R'],
                'count': TRAVEL['tiling_count']['R']}.get(v.get('tiling'))
    return None          # contract / prompt：类别型


VARIANTS = [
    ('主口径（密度=mult 4.0×；tiling=边长 6×）', dict(density='mult', tiling='side')),
    ('变体 A：密度=short 2.667×', dict(density='short', tiling='side')),
    ('变体 B：tiling=块数 36×', dict(density='mult', tiling='count')),
    ('变体 C：密度与 tiling 都排除', dict(density=None, tiling=None)),
    ('变体 D：★ 按评审口径 τ=45×', dict(density='mult', tiling='side', det45=True)),
]


def build(units, v, cat_R=None):
    rows = []
    for u, s in units:
        k = knob_of(u)
        R = R_of(k, v)
        if R is None and cat_R is not None and k in ('contract', 'prompt'):
            R = cat_R
        rows.append(dict(u=u, span=s, R=R, norm=(s / R if R else None), knob=k))
    return rows


def report(units, title, note):
    print()
    print('=' * 108)
    print('【%s】%s' % (title, note))
    print('=' * 108)
    for tag, v in VARIANTS:
        rows = build(units, v)
        use = [r for r in rows if r['norm'] is not None]
        if len(use) < 3:
            print('  %-38s 可归一单元不足（%d）⇒ 跳过' % (tag, len(use)))
            continue
        o0 = sorted(use, key=lambda r: -r['span'])
        o1 = sorted(use, key=lambda r: -r['norm'])
        r0 = {r['u']: i for i, r in enumerate(o0)}
        r1 = {r['u']: i for i, r in enumerate(o1)}
        names = [r['u'] for r in o0]
        sp = spearman([r0[n] for n in names], [r1[n] for n in names])
        bud = [r for r in use if r['knob'] == 'budget']
        budtxt = ''
        if bud:
            budtxt = ' ｜ budget 位次 %s→%s' % (sorted(r0[r['u']] + 1 for r in bud),
                                                sorted(r1[r['u']] + 1 for r in bud))
        print('  %-38s n=%-3d Spearman=%+.3f ｜ top: %s → %s%s'
              % (tag, len(use), sp, o0[0]['u'][:34], o1[0]['u'][:34], budtxt))
        if tag.startswith('主口径'):
            print()
            print('    %-52s %9s %8s %9s  %s' % ('unit（主口径下按 span 降序）', 'span', 'R', 'span/R', '旋钮'))
            for r in o0:
                print('    %-52s %9.1f %8.3f %9.2f  %s'
                      % (r['u'][:52], r['span'], r['R'], r['norm'], r['knob']))
            print('    ── 归一后重排（同 28 个单元）──')
            for r in o1:
                print('      %-52s span/R = %8.2f  (%s)' % (r['u'][:52], r['norm'], r['knob']))

    # B 全域（类别型按 R=1）
    print('\n  ── 敏感性 B：把类别型旋钮按 **R = 1** 塞进同一张排名（强假设，仅作敏感性）──')
    for tag, v in (VARIANTS[0], VARIANTS[4]):
        rows = build(units, v, cat_R=1.0)
        for r in rows:                      # 变体里被排除的族也按 R=1 塞进来（同样只作敏感性）
            if r['norm'] is None:
                r['R'] = 1.0
                r['norm'] = r['span']
        o0 = sorted(rows, key=lambda r: -r['span'])
        o1 = sorted(rows, key=lambda r: -r['norm'])
        r0 = {r['u']: i for i, r in enumerate(o0)}
        r1 = {r['u']: i for i, r in enumerate(o1)}
        sp = spearman([r0[r['u']] for r in o0], [r1[r['u']] for r in o0])
        print('    %-38s n=%d Spearman=%+.3f ｜ top: %s → %s'
              % (tag, len(rows), sp, o0[0]['u'][:30], o1[0]['u'][:30]))

    # C 旋钮级
    print('\n  ── 检验 C：旋钮级（替代解释的直接预测：动程越大、跨度越大）──')
    byk = collections.defaultdict(list)
    for u, s in units:
        byk[knob_of(u)].append(s)
    tab = []
    for k in ('det', 'density', 'tiling', 'budget', 'contract', 'prompt'):
        if k not in byk:
            continue
        R = R_of(k, dict(density='mult', tiling='side'))
        tab.append((k, len(byk[k]), st.median(byk[k]), max(byk[k]), R))
    for k, n, med, mx, R in tab:
        print('    %-10s n=%-3d 中位 span=%8.1f ｜ 最大 span=%8.1f ｜ R=%s'
              % (k, n, med, mx, ('%.3f' % R) if R else '—（类别型）'))
    ok = [t for t in tab if t[4]]
    if len(ok) >= 3:
        print('    ⇒ 有 R 的 %d 族：Spearman(中位 span, R) = %+.3f ｜ Spearman(最大 span, R) = %+.3f'
              % (len(ok), spearman([t[2] for t in ok], [t[4] for t in ok]),
                 spearman([t[3] for t in ok], [t[4] for t in ok])))

    # D 披露用表
    print('\n  ── 供披露用：span per unit of relative travel（主口径，限可归一单元）──')
    rows = build(units, VARIANTS[0][1])
    for r in sorted([x for x in rows if x['norm'] is not None], key=lambda x: -x['norm']):
        print('    %-52s %8.1f pp ÷ %6.3f = %8.2f pp/×' % (r['u'][:52], r['span'], r['R'], r['norm']))

    # E 族间是否还分得开（论文的排序主张实质是"像素预算族在其余族之下"）
    print('\n  ── 检验 E：归一后**族间还分不分得开**（论文的排序主张＝低响应簇在其余之下）──')
    for tag, v in (VARIANTS[0], VARIANTS[4]):
        rows = [r for r in build(units, v) if r['norm'] is not None]
        by = collections.defaultdict(list)
        for r in rows:
            by[r['knob']].append(r['norm'])
        bud = by.get('budget')
        if not bud:
            continue
        print('    [%s]' % tag)
        for k in ('density', 'tiling', 'det', 'budget', 'contract', 'prompt'):
            if k in by:
                v_ = sorted(by[k])
                print('      %-9s n=%-3d 归一后 span/R ∈ [%.2f, %.2f]' % (k, len(v_), v_[0], v_[-1]))
        top_bud = max(bud)
        for k in ('det', 'density', 'tiling'):
            if k in by:
                below = sum(1 for x in by[k] if x < top_bud)
                print('      ⇒ %-8s 中落在最高像素预算单元（%.2f）**之下**的：%d / %d'
                      % (k, top_bud, below, len(by[k])))

    # F 与论文口径一致：剔除两个已退役的 CSRNet 单元
    print('\n  ── 检验 F：剔除论文自己已退役的两个 CSRNet 单元（§K 判为实现缺陷）后重算 ──')
    sub = [(u, s) for u, s in units if not u.startswith('density·CSRNet')]
    for tag, v in (VARIANTS[0], VARIANTS[4]):
        rows = [r for r in build(sub, v) if r['norm'] is not None]
        o0 = sorted(rows, key=lambda r: -r['span'])
        o1 = sorted(rows, key=lambda r: -r['norm'])
        r0 = {r['u']: i for i, r in enumerate(o0)}
        r1 = {r['u']: i for i, r in enumerate(o1)}
        sp = spearman([r0[r['u']] for r in o0], [r1[r['u']] for r in o0])
        print('    %-38s n=%d Spearman=%+.3f ｜ top: %s → %s'
              % (tag, len(rows), sp, o0[0]['u'][:32], o1[0]['u'][:32]))


# ───────── 取值 ─────────
src36 = RP('analysis', 'work', 'equalcount36_result.json')
d36 = json.loads(io.open(src36, encoding='utf-8').read())
U36 = [(u['unit'], float(u['span'])) for u in d36['units']]
h36 = hashlib.md5(io.open(src36, 'rb').read()).hexdigest()

txt = io.open(SUPP, encoding='utf-8', newline='').read().split('\n')
i9 = next(i for i, l in enumerate(txt) if l.startswith('### F.9 '))
U10, l10 = [], []
for j in range(i9, len(txt)):
    l = txt[j]
    if l.startswith('### F.10'):
        break
    if l.startswith('|') and '---' not in l and 'Unit (knob' not in l:
        c = [x.strip() for x in l.strip('|').split('|')]
        if len(c) >= 3:
            try:
                U10.append((c[0], float(re.sub(r'[^0-9.]', '', c[2]))))
                l10.append(j + 1)
            except ValueError:
                pass

print('=' * 108)
print('【表 0】跨度来源（不重算，直接用冻结/印刷件）')
print('=' * 108)
print('  M.37 36 单元：analysis/work/equalcount36_result.json ｜ md5 %s ｜ unit_set=%r'
      % (h36[:12], d36['unit_set']))
print('    （M.37 正文那张表由 gen_m37_unit_table.py 从**本冻结件**生成，非手打）')
print('  F.9 十行：PaperB_英文补充材料_PR_20260919.md L%d–L%d ｜ ⚠ F.9 自述为 **transcription**，'
      '不得承重' % (i9 + 1, l10[-1]))

report(U36, 'A. M.37 的 36 单元（可复算集 = 承重版）', '')
report(U10, 'B. F.9 的 10 单元（transcription，仅并列）', '')

print()
print('=' * 108)
print('【动程定义与出处】')
print('=' * 108)
for k, v in TRAVEL.items():
    print('  %-16s R = %s' % (k, ('%.3f' % v['R']) if v['R'] else 'None'))
    print('       理由：%s' % v['why'])
    print('       出处：%s' % v['src'])
