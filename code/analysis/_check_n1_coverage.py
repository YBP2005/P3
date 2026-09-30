# -*- coding: utf-8 -*-
"""N1 门禁在"改写前/改写后"各能覆盖多少个附录引用？（证明改写是**加固**而非纯装饰）

对同一套正则（与 en_check.py [C] 段逐字一致）分别跑：
  ① 上一枚 pin（v0541）里嵌的主稿副本  = 改写前
  ② 当前盘上的主稿                      = 改写后
print 引用数、未解析数，以及**新进入校验范围**的那批引用。
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
import io, re, sys
sys.stdout.reconfigure(encoding='utf-8')
PACK = NR('review_pkg_20260919', '03_评审包_v0541_20260924.md')
EN = RP('PaperB_英文稿_PR_20260919.md')
SUP = RP('PaperB_英文补充材料_PR_20260919.md')
M = re.compile(r'以下为 06_英文稿_EN\.md ===== -->(.*?)<!-- ===== ', re.S)

pack = io.open(PACK, encoding='utf-8').read()
old = M.search(pack).group(1)
new = io.open(EN, encoding='utf-8', newline='').read()
sup = io.open(SUP, encoding='utf-8', newline='').read()
supheads = set(re.findall(r'^#{2,4}\s+(?:Appendix\s+)?([A-M](?:\.\d+)*)[\.\s]', sup, re.M))


def refs_of(en):
    r = set(re.findall(r'Appendix\s+([A-M](?:\.\d+)*)', en))
    r |= set(re.findall(r'\(([A-M](?:\.\d+)+)\)', en))
    return r


ro, rn = refs_of(old), refs_of(new)
for tag, r in (('改写前（v0541 包内副本）', ro), ('改写后（当前盘）', rn)):
    un = sorted(x for x in r if x not in supheads)
    print('%-24s 引用 %d 个，未解析 %d %s' % (tag, len(r), len(un), un or ''))
print('\n新进入 N1 校验范围的引用：%s' % (sorted(rn - ro) or '（无）'))
print('退出 N1 校验范围的引用：%s' % (sorted(ro - rn) or '（无）'))
print('⇒ 集合比较：改写后是改写后的**超集**吗？%s' % (rn >= ro))
