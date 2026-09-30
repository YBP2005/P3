# -*- coding: utf-8 -*-
"""回语料重算 ShanghaiTech-A 的弃权率**按切块级别**的阶梯，据此定 §5.8(0.0%) 与 §1/§7.7(1.1%) 各属哪一级。
数据：analysis/m5090_archive/unpacked_all/root/{dense_results,tile_results}/*.csv + dense/shanghaitech/counts.csv
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
import io
import os
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')
ARC = NR('analysis', 'm5090_archive', 'unpacked_all', 'root')
CNT = RP('analysis', 'm5090_archive', 'unpacked', 'dense', 'shanghaitech', 'counts.csv')
gt = {}
for r in csv.DictReader(io.open(CNT, encoding='utf-8-sig')):
    if (r.get('part') or '') == 'part_A' and (r.get('split') or '') == 'test':
        gt[os.path.splitext(os.path.basename(r['file']))[0]] = int(r['count'])
print('st_a test 金标准 %d 项' % len(gt))

def rate(p):
    rows = [r for r in csv.DictReader(io.open(p, encoding='utf-8-sig')) if r.get('item') in gt]
    if not rows:
        return None, 0
    z = sum(1 for r in rows if (r.get('pred') or '').strip() in ('0', '0.0'))
    return z / len(rows) * 100, len(rows)

cands = [('whole', RP('analysis', 'm5090_archive', 'unpacked_all', 'root', 'dense_results', 'vlm_st_a_base_whole.csv'))]
for k in (2, 3, 4, 5):
    cands.append(('tile%d' % k, os.path.join(RP('analysis', 'm5090_archive', 'unpacked_all', 'root', 'tile_results'), 'vlm_st_a_base_tile%d.csv' % k)))
print()
print('%-8s %8s %6s  %s' % ('level', 'abstain%', 'n', 'file'))
got = {}
for nm, p in cands:
    if os.path.exists(p):
        v, n = rate(p)
        got[nm] = v
        print('%-8s %7.2f%% %6d  %s' % (nm, v if v is not None else -1, n, os.path.basename(p)))
    else:
        print('%-8s %8s %6s  （缺）%s' % (nm, '-', '-', os.path.basename(p)))

print()
ms = RP('PaperB_英文稿_PR_20260919.md')
t = io.open(ms, encoding='utf-8').read()
plan = []
if got.get('whole') and got.get('tile2'):
    ladder = ', '.join('%s: %.1f%%' % (k.replace('tile', '') + 'x' + k.replace('tile', ''),
                                       got[k]) for k in ('tile2', 'tile3', 'tile4') if got.get(k))
    # §1：把 1.1% 的级别写清
    # ★ 2026-09-30（v0609）：格式串里的**字面百分号**必须写成 `%%`。原文写成 `**56.6%**`，
    #   于是 `%` 紧跟 `*` 被当成宽度说明符 ⇒ 运行时 `TypeError: * wants int`，脚本**开箱即崩**。
    #   只改转义、不动任何数字与措辞：修好后打印出来的字符串与作者原意**逐字节相同**。
    old = 'drops the ShanghaiTech-A [30] abstention rate from **56.6%** to **1.1%** (2×2: 6.0%)'
    new = 'drops the ShanghaiTech-A [30] abstention rate from **56.6%%** to **1.1%%** (per level: %s)' % ladder
    if old in t:
        t = t.replace(old, new, 1); plan.append('§1 已补各级读数')
    # §5.8：把 0.0% 的级别写清
    old2 = 'reduces the ShanghaiTech-A abstention rate from **56.6%** to **0.0%**'
    new2 = ('reduces the ShanghaiTech-A abstention rate from **56.6%%** to **0.0%%** at the finest level measured '
            '(per level: %s)' % ladder)
    if old2 in t:
        t = t.replace(old2, new2, 1); plan.append('§5.8 已补级别')
    # ★ 2026-09-30（v0609，第二处）：写回主稿改为**显式 opt-in**。
    #   起因（实测）：修好格式串后脚本能跑到底，于是**走到了写回那一步**，而旧稿的 §5.8 句子
    #   仍命中 `old2` ⇒ 一次默认运行就把主稿改掉了（md5 3cdf8cb7… → a4d456c9…）。
    #   本脚本本是一次性 patch 工具；放行件里"跑一个复现脚本会改掉论文"是不可接受的行为。
    #   ⇒ 默认**只读**（打印它**会**改哪几处），加 `--apply` 才写回。
    if '--apply' in sys.argv:
        io.open(ms, 'w', encoding='utf-8', newline='\n').write(t)
        _writeback = '  已写回主稿（--apply）'
    elif plan:
        _writeback = '  （dry run：**未**写回主稿。以上为"若加 --apply 会改的处"）'
    else:
        _writeback = '  （dry run：主稿无可改锚点，未写回）'
else:
    _writeback = ''
for p in plan:
    print('  ', p)
if _writeback:
    print(_writeback)
print('（若上面某处显示 MISS，说明该句锚点形状不同，需人工补）')
