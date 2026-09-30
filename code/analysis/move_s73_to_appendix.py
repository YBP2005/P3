# -*- coding: utf-8 -*-
"""路线 A 第二刀：把 §7.3 的"统计结构"与"标定"两段**逐字迁入附录 M.25**，
正文只留节标题 + 序稳健性 + 可用性判据（即读者真正要用的两句）。
理由：正文 36 页、硬上限 35；这两段的完整论证已在 F.3/F.8/F.10/F.11，迁移只挪位置、不改数字。
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
SUP = RP('PaperB_英文补充材料_PR_20260919.md')
en = io.open(EN, encoding='utf-8', newline='').read()

A = '**Statistical structure.** For the ten (knob × domain) units'
B = '**The ordering of the spectrum is stable under the two obvious deflations.**'
C = '**Calibration cannot remove the achievable span.**'
D = '**An availability criterion exists; a magnitude predictor does not.**'
ia, ib, ic, id_ = en.index(A), en.index(B), en.index(C), en.index(D)
p_stat = en[ia:ib]            # 统计结构段
p_cal = en[ic:id_]            # 标定段
print('迁移两段：统计结构 %d 字符；标定 %d 字符' % (len(p_stat), len(p_cal)))

appendix = ('\n---\n\n### M.25 The response spectrum\'s statistical structure and its calibration check '
            '(moved verbatim from §7.3)\n\n'
            'The main text keeps the two sentences a reader needs — the ordering survives the obvious\n'
            'deflations, and availability is decidable while magnitude is not. The full arguments, with the\n'
            'split-point enumeration, the noise-floor comparison and the calibration analysis, are below,\n'
            'verbatim; the frozen numbers they quote are in Appendices F.3, F.8, F.10 and F.11.\n\n'
            '#### M.25.1 Statistical structure\n\n' + p_stat.rstrip() + '\n\n'
            '#### M.25.2 Calibration cannot remove the achievable span\n\n' + p_cal.rstrip() + '\n')
if '--apply' in sys.argv:           # ★ 2026-09-30 v0610：默认**只读**，写回须显式 --apply
    io.open(SUP, 'a', encoding='utf-8', newline='\n').write(appendix)
    print('已追加 M.25（%d 字符）' % len(appendix))
else:
    print('（dry run：将追加 M.25（%d 字符），**未**写回补充材料；加 --apply 才写）'
          % len(appendix))

# 正文：删掉两段，并把 §7.3 标题改为只讲"序与可用性"
new_en = en[:ia] + en[ib:ic] + en[id_:]
new_en = new_en.replace('### 7.3 The response spectrum of knobs, and its statistical structure',
                        "### 7.3 The response spectrum of knobs: the ordering, and what is not predicted", 1)
if '--apply' in sys.argv:           # ★ 2026-09-30 v0610：默认**只读**，写回须显式 --apply
    io.open(EN + '.bak_pre_m25', 'w', encoding='utf-8', newline='').write(en)
    io.open(EN, 'w', encoding='utf-8', newline='').write(new_en)
    print('正文：%d → %d 字符（净减 %d）' % (len(en), len(new_en), len(en) - len(new_en)))
else:
    print('（dry run：正文 %d → %d（净减 %d），**未**写回主稿、**未**落 .bak；加 --apply 才写）'
          % (len(en), len(new_en), len(en) - len(new_en)))
