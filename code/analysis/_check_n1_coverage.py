# -*- coding: utf-8 -*-
"""N1 门禁在"改写前/改写后"各能覆盖多少个附录引用？（证明改写是**加固**而非纯装饰）

对同一套正则（与 en_check.py [C] 段逐字一致）分别跑：
  ① 上一枚 pin（v0541）里嵌的主稿副本  = 改写前
  ② 当前盘上的主稿                      = 改写后
print 引用数、未解析数，以及**新进入校验范围**的那批引用。
"""
import io, re, sys
sys.stdout.reconfigure(encoding='utf-8')
PACK = r'<WORKDIR>\PaperB\review_pkg_20260919\03_评审包_v0541_20260924.md'
EN = r'<WORKDIR>\PaperB\PaperB_英文稿_PR_20260919.md'
SUP = r'<WORKDIR>\PaperB\PaperB_英文补充材料_PR_20260919.md'
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
