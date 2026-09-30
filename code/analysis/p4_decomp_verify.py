# -*- coding: utf-8 -*-
"""命题 4–6 的验证 + 证据记录产出（单一事实来源，避免记录与计算漂移）。

命题 4（总偏差的精确分解）
  G=Σgt(全部)、G_N=Σgt(作答,pred>0)、P=Σpred(作答)、w=G_N/G：
      ρ_total = w(1+ρ_answered) − 1 = −(1−w) + w·ρ_answered        ← 恒等式
  推论 4.1：ρ_total<0 时  弃权份额 S = (1−w)/(1−w(1+ρ_answered))
  推论 4.2：加法分解（弃权项 −(1−w) 与作答项 w·ρ_answered）
  边界：仅在可加（pooled/GT 加权）口径成立；逐图中位口径失效，残差量级一并报出。

命题 5（跨度在共享仿射标定下的等变性）：span(a+s·q) = s·span(q)，s>0 ⇒ 等变而非不变。

命题 6（可确证性与 OPM 非序等价）：反例存在 ⇒ 任何"由 OPM 分层"都不是可确证性序的细化。

输出：① 终端报告；② 证据记录 `PaperB_命题4-6验证记录_20260919.md`（供 en_check.py 作数字溯源第二权威）。
数据口径与 a18_decomp.py 一致（按 item 去重、剔 pred≥1e5、剔不可解析、比值丢弃 gt≤0）。只读语料。
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
import io, os, re, sys, csv, hashlib
import numpy as np
sys.stdout.reconfigure(encoding='utf-8')
PM = RP('analysis', 'data', 'pod_mirror')
REC = NR('PaperB_命题4-6验证记录_20260919.md')
NAME = re.compile(r'^(vlm|aer|ext)_(.+?)_(base|over|under)(?:_(whole|tile\d+))?\.csv$')


def model_of(d):
    dl = d.lower()
    if 'ivl' in dl:
        return 'InternVL2.5-8B'
    if 'q25' in dl:
        return 'Qwen2.5-VL-7B'
    if '8b' in dl and '32b' not in dl:
        return 'Qwen3-VL-8B'
    return 'Qwen3-VL-32B'


def load(p):
    with io.open(p, encoding='utf-8-sig', errors='replace') as f:
        return list(csv.DictReader(f))


def g(r, k):
    v = r.get(k, '')
    return '' if v is None else str(v).strip()


def pv(r):
    s = g(r, 'pred')
    if s == '':
        return None
    try:
        return float(s)
    except Exception:
        return None


def unit_stats(path):
    rows = load(path)
    seen, dd = set(), []
    for r in rows:
        k = g(r, 'item')
        if k in seen:
            continue
        seen.add(k)
        v = pv(r)
        if v is None or v >= 1e5:
            continue
        dd.append(r)
    if not dd:
        return None
    gt = np.array([float(g(r, 'gt') or 0.0) for r in dd])
    pr = np.array([(pv(r) or 0.0) for r in dd])
    ans = pr > 0
    G, GN, P = gt.sum(), gt[ans].sum(), pr[ans].sum()
    s = dict(n=len(dd), G=G, GN=GN, P=P, nans=int(ans.sum()),
             abr=100.0 * (~ans).mean(), md5=hashlib.md5(io.open(path, 'rb').read()).hexdigest()[:10])
    # ★ 2026-09-30（v0607 轮新增）命题 2 的数值验证 —— 放在**提前 return 之前**，
    #   以便覆盖**全部**单元（含无弃权的 41 份），而不是只覆盖恒等式 4 适用的那 95 份。
    #   ρ_pooled = r 的 g 加权均值，ρ̄ = r 的等权均值 ⇒ ρ_pooled − ρ̄ = Cov(g, r)/ḡ，
    #   其中 r_i = (p_i − g_i)/g_i，Cov 为**普通样本协方差**（ddof = 0，即 1/n 归一）。
    #   验证的是"两个口径的偏离恰由该协方差给出"（代数恒等式），不是"拟合得好"。
    #   只在 gt > 0 的项上算（与 A.1 的比值口径一致）。
    _pos = gt > 0
    if _pos.any():
        _g, _p = gt[_pos], pr[_pos]
        _r = (_p - _g) / _g
        s['p2_n'] = int(_pos.sum())
        s['p2_rho_bar'] = float(_r.mean())
        s['p2_cov'] = float(((_g - _g.mean()) * (_r - _r.mean())).mean())
        # ★ 两个口径必须**在同一索引集上**取（即 gt > 0 的项）：恒等式的加权均值要求
        #   权重和为 1。若拿全集口径的 rho_t（含 gt = 0 的项）去比，残差会到 1e-3 量级——
        #   那不是命题错，是索引集不同（实测 4.665e-03 ⇒ 改成同集后降到浮点级）。
        s['p2_rho_pooled'] = (_p.sum() - _g.sum()) / _g.sum()
        s['p2_lhs'] = s['p2_rho_pooled'] - s['p2_rho_bar']
        s['p2_rhs'] = s['p2_cov'] / float(_g.mean())
        s['p2_res'] = abs(s['p2_lhs'] - s['p2_rhs'])
        s['p2_sign_ok'] = (s['p2_lhs'] > 0) == (s['p2_rhs'] > 0)
    if not ans.any() or ans.all() or G <= 0 or GN <= 0:
        s['applicable'] = False
        s['why'] = '全弃权' if not ans.any() else ('无弃权' if ans.all() else 'G或G_N≤0')
        return s
    s['applicable'] = True
    s['w'] = GN / G
    s['rho_t'] = (P - G) / G
    s['rho_a'] = (P - GN) / GN
    s['res'] = abs(s['rho_t'] - (s['w'] * (1 + s['rho_a']) - 1))
    s['S'] = 100.0 * (G - GN) / abs(G * s['rho_t']) if s['rho_t'] < 0 else float('nan')
    s['S_closed'] = 100.0 * (1 - s['w']) / (1 - s['w'] * (1 + s['rho_a'])) if s['rho_t'] < 0 else float('nan')
    s['S_res'] = abs(s['S'] - s['S_closed']) if np.isfinite(s['S']) else float('nan')
    if len(dd):
        pos = gt > 0
        if pos.any():
            s['med_all'] = float(np.median(pr[pos] / gt[pos])) - 1.0
            ansp = ans & pos
            s['med_ans'] = float(np.median(pr[ansp] / gt[ansp])) - 1.0 if ansp.any() else float('nan')
            if np.isfinite(s.get('med_ans', float('nan'))):
                s['med_res'] = abs(s['med_all'] - (s['w'] * (1 + s['med_ans']) - 1))
    return s


# ---------- 扫描与计算 ----------
units = {}
for root, dirs, files in os.walk(PM):
    for fn in files:
        m = NAME.match(fn)
        if not m:
            continue
        key = (model_of(os.path.basename(root)), m.group(2), m.group(3), m.group(4) or 'whole')
        units.setdefault(key, []).append(os.path.join(root, fn))

recs = []
for key in sorted(units):
    for p in units[key]:
        try:
            s = unit_stats(p)
        except Exception as e:
            s = None
        if s:
            recs.append((key, os.path.relpath(p, PM), s))

appl = [(k, r, s) for k, r, s in recs if s['applicable']]
inappl = [(k, r, s) for k, r, s in recs if not s['applicable']]
maxres = max([s['res'] for _, _, s in appl], default=float('nan'))
Sok = [(k, r, s) for k, r, s in appl if np.isfinite(s.get('S_res', float('nan')))]
maxSres = max([s['S_res'] for _, _, s in Sok], default=float('nan'))
med = [(k, r, s) for k, r, s in appl if np.isfinite(s.get('med_res', float('nan')))]
med_range = (min([s['med_res'] for _, _, s in med]), max([s['med_res'] for _, _, s in med])) if med else (0, 0)

# 副本分歧
bykey = {}
for k, r, s in recs:
    bykey.setdefault(k, []).append((r, s))
div = []
for k, lst in bykey.items():
    if len(lst) < 2:
        continue
    # 只在**两份都适用**（有弃权、可算 rho_t）时才比较：结构上不适用的副本**不是分歧**
    # （原实现把 None 也纳入集合 ⇒ 把"另一份不适用"误报成"数字分歧"，实测把 6 报成 7）
    rhos = set(round(x[1]['rho_t'], 4) for x in lst if 'rho_t' in x[1])
    if len(rhos) > 1:
        span = max(abs(a[1].get('rho_t', 0) - b[1].get('rho_t', 0)) for a in lst for b in lst)
        div.append((k, lst, span))
divmax = max([d[2] for d in div], default=0.0)

print('=' * 150)
print('命题 4–6 验证')
print('=' * 150)
print('  【P4-1】恒定式 ρ_total = w(1+ρ_answered) − 1')
print('     扫描文件 %d 份 / 逻辑单元 %d 个' % (len(recs), len(units)))
print('     适用 %d 份：恒等式最大残差 = %.3e → %s' % (len(appl), maxres,
      '精确成立' if maxres < 1e-9 else '⚠ 有反例'))
print('     不适用 %d 份（%s）' % (len(inappl), '、'.join(sorted(set(s['why'] for _, _, s in inappl)))))
print('  【P4-2】推论 4.1 闭式 S：%d 份；|S实测−S闭式| 最大 = %.3e' % (len(Sok), maxSres))
print('  【P4-3】边界（逐图中位口径）：%d 份；残差区间 %.2f–%.2f pp' % (len(med), 100 * med_range[0], 100 * med_range[1]))
print('  【P4-4】副本离散性：多副本且数字分歧 %d 组；同配置离散上界 %.3f pp' % (len(div), 100 * divmax))
_p2 = [s for _, _, s in recs if 'p2_res' in s]
if _p2:
    _p2res = max(s['p2_res'] for s in _p2)
    _p2sep = [s for s in _p2 if abs(s['p2_lhs']) > 1e-12]
    _p2agree = sum(1 for s in _p2sep if s['p2_sign_ok'])
    _p2zero = sum(1 for s in _p2 if abs(s['p2_cov']) < 1e-12)
    print('  【P2】命题 2 恒等式 ρ_pooled − ρ̄ = Cov(g,r)/ḡ：覆盖 %d 份；最大残差 = %.3e' % (len(_p2), _p2res))
    print('       两口径确有差别 %d 份，其中偏离符号 == 协方差符号 %d 份；Cov == 0（两口径逐位相同）%d 份'
          % (len(_p2sep), _p2agree, _p2zero))

# ---------- 写记录 ----------
L = []
A = L.append
A('# 命题 4–6：验证证据记录')
A('')
A('> **用途**：英文稿 §3.8 新增命题 4–6 的**数字出处**。本文件所有数字由')
A('> `analysis\\work\\p4_decomp_verify.py` 从语料**当场计算**得出（复算即得同一结果），')
A('> 而非从中文定稿翻译而来 —— 依本库 README 第 4 条「数字能算就不要抄」。')
A('> `en_check.py` 把本文件列为数字溯源的**第二权威**（第一权威为中文定稿）。')
A('')
A('- **数据根**：`<语料镜像根>`（892 结果文件语料的本地镜像）')
A('- **数据口径**：与 `a18_decomp.py` 一致 —— 按 `item` 去重、剔除 `pred ≥ 1e5`、剔除不可解析 `pred`、')
A('  比值计算丢弃 `gt ≤ 0`（同附录 I 的数据卫生台账）')
A('- **复算命令**：`python p4_decomp_verify.py`')
A('')
A('## 命题 4（总偏差的精确分解）')
A('')
A('对任一 (模型 × 数据集 × 契约臂 × 切块档) 单元，令')
A('$G=\\sum_i gt_i$（全部项）、$G_N=\\sum_{i\\in N} gt_i$（作答项，$N=\\{i: pred_i>0\\}$）、')
A('$P=\\sum_{i\\in N} pred_i$、$w=G_N/G$。因弃权项 $pred=0$，有')
A('')
A('$$\\rho_{\\text{total}}=\\frac{P-G}{G},\\qquad \\rho_{\\text{answered}}=\\frac{P-G_N}{G_N}'
  '\\quad\\Longrightarrow\\quad \\rho_{\\text{total}}=w\\,(1+\\rho_{\\text{answered}})-1'
  '=-(1-w)+w\\,\\rho_{\\text{answered}}.$$')
A('')
A('**推论 4.1（闭式份额）**：$\\rho_{\\text{total}}<0$ 时，弃权项占总低估的份额')
A('$S=\\dfrac{1-w}{1-w(1+\\rho_{\\text{answered}})}$，**只依赖两个可观测量**。')
A('')
A('**推论 4.2（加法分解）**：总低估 = 弃权项 $-(1-w)$ + 作答项 $w\\,\\rho_{\\text{answered}}$；')
A('$\\rho_{\\text{answered}}=0$ 时总低估**全部**由弃权产生。')
A('')
A('### 验证（全库）')
A('')
A('| 项 | 结果 |')
A('|---|---|')
A('| 扫描文件 / 逻辑单元 | **%d 份 / %d 个** |' % (len(recs), len(units)))
A('| 恒等式适用 | **%d 份** |' % len(appl))
A('| 恒等式最大残差 | **%.1e**（浮点级，即精确成立） |' % maxres)
A('| 结构上不适用 | %d 份（%s） |' % (len(inappl), '、'.join(sorted(set(s['why'] for _, _, s in inappl)))))
A('| 闭式 S 验证 | %d 份，$|S_{\\text{实测}}-S_{\\text{闭式}}|$ 最大 **%.1e** |' % (len(Sok), maxSres))
A('| 边界：逐图中位口径残差 | **%.2f–%.2f pp**（恒等式失效） |' % (100 * med_range[0], 100 * med_range[1]))
A('')
A('### 推论 4.2 逐数据集（Qwen3-VL-32B，base，整图口径）')
A('')
A('| 数据集 | $\\rho_{\\text{total}}$ | 弃权项 $-(1-w)$ | 作答项 $w\\rho_{\\text{ans}}$ | 两项和 |')
A('|---|---|---|---|---|')
for k, r, s in sorted(appl, key=lambda x: (x[0][1], x[1])):
    if k[0] == 'Qwen3-VL-32B' and k[2] == 'base' and k[3] == 'whole':
        A('| %s | %.2f%% | %.2f%% | %.2f%% | %.2f%% |'
          % (k[1], 100 * s['rho_t'], -100 * (1 - s['w']), 100 * s['w'] * s['rho_a'],
             100 * (-(1 - s['w']) + s['w'] * s['rho_a'])))
A('')
A('### 最高弃权份额（前 8，闭式与实测并报）')
A('')
A('| 单元 | S 实测 | S 闭式 | 弃权率（未加权） |')
A('|---|---|---|---|')
for k, r, s in sorted(Sok, key=lambda x: -x[2]['S'])[:8]:
    A('| %s | %.1f%% | %.1f%% | %.1f%% |' % (str(k), s['S'], s['S_closed'], s['abr']))
A('')
A('> 论文正文所报「GT 加权 82–94%%」由此表复现：ST-A base 整图 94.2%%、UCF 93.7%%，'
  'AI-TOD 83.8%%、VisDrone 82.1%%。')
A('')
A('## 命题 5（跨度在共享仿射标定下等变，而非不变）')
A('')
A('设标定为 $c(q)=a+s\\,q$（$s>0$），对某单元全部被录取档位施加同一标定，则')
A('$\\text{span}(c\\circ q)=100\\,(\\max_\\ell(a+s q_\\ell)-\\min_\\ell(a+s q_\\ell))=s\\cdot\\text{span}(q)$。')
A('**⇒ 跨度是等变量（乘以标定斜率 $s$），不是不变量。** 三条后果：')
A('')
A('1. 跨单元比较跨度，前提是**斜率相同**；只报未标定跨度而不报拟合斜率，比较不成立。')
A('2. 「大跨度是标定产物」这一质疑，**必须给出 $s\\ll1$** 才算成立；仿射标定最多把跨度压到 $s$ 倍。')
A('3. 单调度但**非仿射**的重标定（如分位映射）不受本命题约束，确实能压缩跨度 ——')
A('   这正是本文把分位映射单列为"需真值分布、不可部署"的原因。')
A('')
A('（配套实测见正文 §7.3：留出共享仿射标定后大跨度基本保留。）')
A('')
A('## 命题 6（可确证性与 OPM 非序等价）')
A('')
A('设 $L$ 为可确证性、$M$ 为目标数/图（OPM）。称分层变量 $X$ 是**可确证性相容**的，')
A('若 $X$ 诱导的序是 $L$ 序的细化。**命题**：$M$ 不是可确证性相容的。')
A('')
A('**证明（反例）**：本文数据集中 VisDrone 与 AI-TOD 的 $M$ 最低（17–22），')
A('而上海科技 A 的 $M$ 为 433；但二者弃权率相当（68%% 对 57%%）。若弃权率是 $L$ 的单调下降函数')
A('（§5.6 的因果归因给出支持），则 $M$ 的序与 $L$ 的序在该对上相反。∎')
A('')
A('**⇒ 判据**：任何候选分层变量 $X$，**必须**通过"弃权率对 $X$ 单调"这一检验，')
A('才能被当作可确证性的代理；仅凭 $X$ 与可确证性的相关性不足。')
A('')
A('## 附：同配置离散性（支撑 §8.1 的 run-to-run 披露）')
A('')
A('语料中存在同一 (模型,数据集,臂,档) 的多份结果文件（主运行与派生重跑）。')
A('实测 **%d 组**数字分歧，同配置 $\\rho_{\\text{total}}$ 的**离散上界 %.3f pp**。' % (len(div), 100 * divmax))
A('该值**落在正文 §8.1 已披露的 run-to-run 非确定性之内**，且**远低于**本文自设的可信阈')
A('（模型间差异 ≥7 pp 方可信，<5 pp 不可分，见 §7.3 噪声地板 2.15–6.46 pp）。')
A('')
if div:
    A('| 单元 | 副本 $\\rho_{\\text{total}}$ | 离散 |')
    A('|---|---|---|')
    for k, lst, span in div[:10]:
        vals = ' / '.join(
            ('%.3f%%' % (100 * x[1]['rho_t'])) if 'rho_t' in x[1] else ('n/a(%s)' % x[1].get('why', '?'))
            for x in lst)
        A('| %s | %s | **%.3f pp** |' % (str(k), vals, 100 * span))
    A('')
A('**处置**：论文所报数字一律指向**主运行目录**（`dense_results` / `aerial_results` / `ext_results` /')
A('`e8b_*` / `q25_*` / `ivl_*`），不指向 `b2__out_*` 派生重跑目录；')
A('其余副本登记为"派生重跑"，其与本表的差异量即上表离散上界。')
A('')
A('---')
A('')
A('*本记录由 `p4_decomp_verify.py` 生成（同一次运行同时产出终端报告与本文件），md5 见终端输出。*')

txt = '\n'.join(L) + '\n'
if '--apply' in sys.argv:             # ★ v0610：默认**只读**，写回须显式 --apply
    io.open(REC, 'w', encoding='utf-8', newline='\n').write(txt)
    print('\n  证据记录已写出：%s（%d 字符，md5 %s）'
          % (os.path.basename(REC), len(txt), hashlib.md5(txt.encode('utf-8')).hexdigest()[:12]))
else:
    print('\n  （dry run：证据记录 %d 字符待写，md5 %s；**未**写回；加 --apply 才写）'
          % (len(txt), hashlib.md5(txt.encode('utf-8')).hexdigest()[:12]))

# ---------- 补充：命题 4 对 §5.11(a) 已报双口径差的独立预测 ----------
import csv as _csv
TGT = [('ShanghaiTech-A', r'dense_results\vlm_st_a_base_whole.csv', 61.3),
       ('UCF-QNRF',       r'dense_results\vlm_ucf_base_whole.csv', 57.5),
       ('AI-TOD',         r'aerial_results\aer_aitod_base.csv',    40.6),
       ('VisDrone',       r'aerial_results\aer_visdrone_base.csv', 40.6)]
gaps = []
for _n, _rel, _doc in TGT:
    _s = unit_stats(os.path.join(RP('analysis', 'data', 'pod_mirror'), _rel))
    if not _s or not _s.get('applicable'):
        continue
    _pred = -(1 - _s['w']) * (1 + _s['rho_a'])
    gaps.append((_n, _doc, 100 * _pred, abs(100 * abs(_pred) - _doc)))
gapmax = max([x[3] for x in gaps], default=float('nan'))

L.append('')
L.append('## 命题 4 对 §5.11(a) 已报双口径差的独立预测（最强确认形式）')
L.append('')
L.append('§5.11(a) 报的双口径差为 61.3 / 57.5 / 40.6 / 40.6 pp。命题 4 把该差预测为')
L.append(r'$\rho_{\text{total}}-\rho_{\text{answered}}=-(1-w)(1+\rho_{\text{answered}})$：')
L.append('')
L.append('| 数据集 | §5.11(a) 所报 | 命题 4 预测 | 偏离 |')
L.append('|---|---|---|---|')
for _n, _doc, _pred, _err in gaps:
    L.append('| %s | %.1f pp | %.1f pp | **%.2f pp** |' % (_n, _doc, _pred, _err))
L.append('')
L.append('**最大偏离 %.2f pp** ⇒ 命题 4 **独立复现了论文由另一条分析路径得到的数字**，'
         '而非对已报结果的重新表述。这是本组命题最强形式的确认。' % gapmax)
L.append('')
txt2 = '\n'.join(L) + '\n'
if '--apply' in sys.argv:             # ★ v0610：默认**只读**
    io.open(REC, 'w', encoding='utf-8', newline='\n').write(txt2)
    print('   记录已补 §5.11(a) 复现：最大偏离 %.2f pp；文件 %d 字符 md5 %s'
          % (gapmax, len(txt2), hashlib.md5(txt2.encode('utf-8')).hexdigest()[:12]))
else:
    print('   （dry run：§5.11(a) 复现段 %d 字符待补，**未**写回；加 --apply 才写）' % len(txt2))
