# -*- coding: utf-8 -*-
"""把紧凑版 §3.8 再改一版：**保留 Proposition 1–8 的标签**（正文别处有交叉引用，
删标签会让引用悬空），并给 82–94% 补上 base 臂限定（闸门会查）。
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
import sys

sys.stdout.reconfigure(encoding='utf-8')
EN = RP('PaperB_英文稿_PR_20260919.md')
t = io.open(EN, encoding='utf-8', newline='').read()
START = '### 3.8 Formal framework: what is identifiable from outputs'
END = '### 3.9 Figures and tables'
i = t.index(START)
j = t.index(END, i)

compact = '''### 3.8 Formal framework: what is identifiable from outputs

Eight statements are used later. All are **either identities of the reporting convention or decidability
statements** — we do **not** offer them as empirical findings — so they are stated compactly here, with the
full statements, derivations, verification records and scope notes moved verbatim to **Appendix M.21**.

**Proposition 1 (abstention is not identified by outputs alone).** `y = 0` is produced both by abstaining and
by estimating zero, so identification needs an auxiliary channel. We use
$\\kappa=\\#\\{y=0\\}/\\#\\{\\text{textual refusals}\\}$ and report the measured value — contamination
**0.18%** for Qwen3-VL-32B ($\\kappa = 550.6$) and **30.31%** for InternVL2.5-8B ($\\kappa = 2.3$) — which is
the arithmetic reason §3.6 reports the two lineages separately rather than pooled.

**Proposition 2 (the two conventions diverge exactly when the per-image ratio correlates with ground
truth).** $\\rho_{\\text{pooled}}-\\bar\\rho=\\operatorname{Cov}_g(g,r)/\\bar g$, and abstention is itself
GT-dependent, so the covariance is non-zero in dense domains by construction. Both conventions are therefore
always reported — and §5.12 measures what a single convention costs.

**Proposition 3 (span is a functional of the admitted level set).** Any candidate predictor built from its
extremes is a **component of the definition** (partial correlation exactly $\\pm1$). That is why we withdraw
our own candidate and claim **availability** — decidable from the same quantities, since it holds iff
$\\max_\\ell q_\\ell \\ge 1$ at the loosest admitted level — but **not magnitude**.

**Proposition 4 (the aggregate bias decomposes exactly).**
$\\rho_{\\text{total}}=-(1-w)+w\\,\\rho_{\\text{answered}}$ with $w=G_N/G$, and the abstention share of the
under-count has the closed form $S=(1-w)/[1-w(1+\\rho_{\\text{answered}})]$. This is the identity behind the
**82–94%** of §5.5 for the **base contract arm**, and the reason the separation asserted in §5.7 is a matter
of construction rather than of observation.

**Proposition 5 (span is equivariant, not invariant, under shared affine calibration).**
$\\text{span}\\mapsto s\\cdot\\text{span}$, so the objection that a large span is a calibration artefact
requires exhibiting $s\\ll1$.

**Proposition 6 (targets-per-image is not a legibility-consistent stratifier).** VisDrone and AI-TOD have the
fewest targets (17–22) yet abstain as often as ShanghaiTech-A (433), which is what licenses stratifying by
legibility rather than by density.

**Proposition 7 (the identification error of the answered-zero channel is exactly $1/(\\kappa+1)$).** It is a
known function of a measured quantity — **0.18%** for Qwen3-VL-32B and **30.31%** for InternVL2.5-8B — hence
the separate reporting of the two lineages.

**Proposition 8 (the dual-convention gap is bounded by the abstention mass).** From Proposition 4 the gap is
$-(1-w)(1+\\rho_{\\text{answered}})$, i.e. **zero iff $w = 1$ or $\\rho_{\\text{answered}}=-1$**, and it
survives an unbiased answered subset — so a single-convention report is not merely incomplete but
uninterpretable.

'''
new = t[:i] + compact + t[j:]
if '--apply' in sys.argv:           # ★ 2026-09-30 v0610：默认**只读**，写回须显式 --apply
    io.open(EN, 'w', encoding='utf-8', newline='').write(new)
    print('§3.8 紧凑版：%d 字符（含标签）' % len(compact))
    print('正文总字符：%d → %d' % (len(t), len(new)))
else:
    print('（dry run：§3.8 紧凑版 %d 字符；正文 %d → %d，**未**写回主稿；加 --apply 才写）'
          % (len(compact), len(t), len(new)))
