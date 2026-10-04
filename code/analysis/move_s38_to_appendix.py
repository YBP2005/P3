# -*- coding: utf-8 -*-
"""路线 A 第一刀：把正文 §3.8（命题框架，约 7.9k 字符）**逐字迁往补充材料**，
正文只留一份紧凑版（保留全部结论性数字与"不把它当发现"的定位）。

为什么这么迁：
  · [external-review] 4/4 家就"恒等式/定义性内容占据正文贡献权重"提出意见（合计约 −41）；
  · 正文卡在 35/35 页硬上限，而 E3 需要进正文当主实验 ⇒ 必须等量腾页。
逐字迁移由脚本完成（读原文 → 写附录 → 替换正文），避免手抄出错；原文备份为 .bak_pre_m21。
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
import io
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')
EN = RP('PaperB_英文稿_PR_20260919.md')
SUP = RP('PaperB_英文补充材料_PR_20260919.md')

en = io.open(EN, encoding='utf-8', newline='').read()
sup = io.open(SUP, encoding='utf-8', newline='').read()

START = '### 3.8 Formal framework: what is identifiable from outputs'
END = '### 3.9 Figures and tables'
i = en.index(START)
j = en.index(END, i)
body = en[i:j].rstrip() + '\n'
print('原 §3.8 字符数：%d' % len(body))

# ---- ① 写进补充材料（作为 M.21，放在 M.20 之后 / 文件末尾）----
appendix = (
    '\n---\n\n### M.21 The formal framework in full (moved verbatim from §3.8)\n\n'
    '§3.8 in the main text now states only what each statement *buys* the reader. The full statements,\n'
    'derivations, verification records and scope notes are reproduced **verbatim** below; nothing here is\n'
    'new, and none of it is offered as an empirical finding — the six statements are either identities of\n'
    'the reporting convention (2, 4, 8), decidability statements about observable quantities (1, 3),\n'
    'equivariance statements (5), or a monotonicity argument that licenses a stratifier (6).\n\n'
    + body.replace('### 3.8 Formal framework: what is identifiable from outputs',
                   '#### M.21.1 Statements 1–8')
)
assert 'M.21.1' in appendix
if '--apply' in sys.argv:           # ★ 2026-09-30 v0610：默认**只读**，写回须显式 --apply
    io.open(SUP, 'a', encoding='utf-8', newline='\n').write(appendix)
    print('已追加附录 M.21（%d 字符）' % len(appendix))
else:
    print('（dry run：将追加附录 M.21（%d 字符），**未**写回补充材料；加 --apply 才写）'
          % len(appendix))

# ---- ② 正文替换为紧凑版 ----
compact = '''### 3.8 Formal framework: what is identifiable from outputs

Six statements are used later. All are **either identities of the reporting convention or decidability
statements** — we do **not** offer them as empirical findings — so they are stated compactly here, with the
full statements, derivations, verification records and scope notes moved verbatim to **Appendix M.21**.

**(1) Abstention is not identified from outputs alone**: `y = 0` is produced both by abstaining and by
estimating zero, so identification needs an auxiliary channel. We use
$\\kappa=\\#\\{y=0\\}/\\#\\{\\text{textual refusals}\\}$ and report the measured value — contamination
**0.18%** for Qwen3-VL-32B ($\\kappa = 550.6$) and **30.31%** for InternVL2.5-8B ($\\kappa = 2.3$) — which is
the arithmetic reason §3.6 reports the two lineages separately rather than pooled.

**(2) The two conventions diverge exactly when the per-image ratio correlates with ground truth**
($\\rho_{\\text{pooled}}-\\bar\\rho=\\operatorname{Cov}_g(g,r)/\\bar g$), and abstention is itself GT-dependent,
so the covariance is non-zero in dense domains by construction. Both conventions are therefore always
reported — and §5.12 measures what a single convention costs.

**(3) Span is a functional of the admitted level set**, so any candidate predictor built from its extremes
is a **component of the definition** (partial correlation exactly $\\pm1$). That is why we withdraw our own
candidate and claim **availability** — decidable from the same quantities, since it holds iff
$\\max_\\ell q_\\ell \\ge 1$ at the loosest admitted level — but **not magnitude**.

**(4) The aggregate bias decomposes exactly**: $\\rho_{\\text{total}}=-(1-w)+w\\,\\rho_{\\text{answered}}$ with
$w=G_N/G$, and the abstention share of the under-count has the closed form
$S=(1-w)/[1-w(1+\\rho_{\\text{answered}})]$. This is the identity behind the **82–94%** of §5.5, and the reason
the separation asserted in §5.7 is a matter of construction rather than of observation.

**(5) Span is equivariant, not invariant, under shared affine calibration**
($\\text{span}\\mapsto s\\cdot\\text{span}$), so the objection that a large span is a calibration artefact
requires exhibiting $s\\ll1$.

**(6) Targets-per-image is not a legibility-consistent stratifier** — VisDrone and AI-TOD have the fewest
targets (17–22) yet abstain as often as ShanghaiTech-A (433) — which is what licenses stratifying by
legibility rather than by density.

**(7)** *(read the identification error of the answered-zero channel from (1))*: it is exactly
$f=1/(\\kappa+1)$, a known function of a measured quantity.
**(8)** *(read the dual-convention gap from (4))*: it is $-(1-w)(1+\\rho_{\\text{answered}})$, i.e. **zero iff
$w=1$ or $\\rho_{\\text{answered}}=-1$**, and it survives an unbiased answered subset — so a single-convention
report is not merely incomplete but uninterpretable.

'''
new_en = en[:i] + compact + en[j:]
if '--apply' in sys.argv:           # ★ 2026-09-30 v0610：默认**只读**，写回须显式 --apply
    io.open(EN + '.bak_pre_m21', 'w', encoding='utf-8', newline='').write(en)
    io.open(EN, 'w', encoding='utf-8', newline='').write(new_en)
    print('正文：%d → %d 字符（净减 %d）' % (len(en), len(new_en), len(en) - len(new_en)))
else:
    print('（dry run：正文 %d → %d（净减 %d），**未**写回主稿、**未**落 .bak；加 --apply 才写）'
          % (len(en), len(new_en), len(en) - len(new_en)))
