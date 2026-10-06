# -*- coding: utf-8 -*-
"""build_paperB_pack.py — 组装 PaperB 的**盲审包**（本轮 = 修订版评分表 + 改稿后的英文送审件）。

包结构（与上一轮 01d 逐段同构，便于跨轮比较）：
    <!-- ===== 材料自述 ===== -->                       （由本脚本生成：长度事实；★ v0652 起**不含**变化块）
    <!-- ===== 以下为 02_评审提示词.txt ===== -->        （提示词 + 内联的 8 维评分表附录）
    <!-- ===== 以下为 02d_问句集_PR版.txt ===== -->
    <!-- ===== 以下为 06_英文稿_EN.md ===== -->
    <!-- ===== 以下为 08_英文补充材料_Supplementary.md ===== -->

★ 四条纪律：
  ① **材料自述必须是被测量的**：页数/词数从 `measurement_pr_docx.json` 读，不手写、不折算；
  ② **同构写入**：包里的 06/08 与工作区权威稿同时落盘并核对 md5，避免"包里印的是旧稿"；
     并且**四段全部**断言"包内 == 源"——2026-09-26 审计发现旧版只断言了"四段存在"，
     而 `en_check.py` 的 [I] 只覆盖 06/08 ⇒ **02d 陈旧了一整个轮次而门禁全绿**。
  ③ 附录是否计入页数上限**不由我方断言**（官方原文自相矛盾），只写事实。
  ④ ★ **"本轮变化块"自 v0652 起不进评审面**（上级裁定 (乙)：撤出评审面）。历史根因见 2026-09-26
     审计件 `..\发射前审计_v0562_发现两处陈旧_20260926.md`：该块曾是本脚本里的硬编码常量，于是
     v0557–v0562 **连续六枚 pin 逐字节相同**，预注册条款被"告知"的是早已审过的前两轮改动。
     v0563 起改为从 `02f_本轮变化块_<tag>.md` 读入并**三重断言**（首行轮次 == tag、无上一轮陈旧串、
     确已进包）；**v0652 起该块彻底撤出评审面** —— 它只作**作者侧内部台账**（按轮写、不进包、
     不进任务书），本脚本**不再读它**，并改为**反向断言**：包里**不得出现** `【本轮相对`。
     任一不满足即**拒绝出包**（先校验、后落盘）。

用法：
    python build_paperB_pack.py [tag] [date]      # tag 缺省 = 已有最大编号 +1
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
import glob
import hashlib
import io
import json
import os
import re
import sys
import time

sys.stdout.reconfigure(encoding='utf-8')
ROOT = NR()
PKG = NR('review_pkg_20260919')


def next_tag():
    """与 final_gates.py 同源：取已有 pin 的最大编号 +1（**不要**再写死 tag）。"""
    nums = []
    for f in glob.glob(NR('review_pkg_20260919', '03_评审包_v05*_*.md')):
        m = re.search(r'_v(\d{4})_\d{8}\.md$', os.path.basename(f))
        if m:
            nums.append(int(m.group(1)))
    return 'v%04d' % (max(nums) + 1) if nums else 'v0001'


TAG = sys.argv[1] if len(sys.argv) > 1 else next_tag()
DATE = sys.argv[2] if len(sys.argv) > 2 else time.strftime('%Y%m%d')
OUT = os.path.join(NR('review_pkg_20260919'), '03_评审包_%s_%s.md' % (TAG, DATE))
print('本轮 tag = %s（%s）；输出 %s'
      % (TAG, '命令行给定' if len(sys.argv) > 1 else '自动取已有最大编号 +1', os.path.basename(OUT)))

PARTS = [('02_评审提示词.txt', '02_评审提示词.txt'),
         ('02d_问句集_PR版.txt', '02d_问句集_PR版.txt'),
         ('06_英文稿_EN.md', 'PaperB_英文稿_PR_20260919.md'),
         ('08_英文补充材料_Supplementary.md', 'PaperB_英文补充材料_PR_20260919.md')]
# 每段的名字 → 权威源路径（前两段属 review_pkg，后两段属工作区）
SRC_PATH = {}


def _bind():
    for name, src in PARTS:
        SRC_PATH[name] = os.path.join(NR('review_pkg_20260919'), src) if src == name else os.path.join(NR(), src)


_bind()


def rd(p):
    return io.open(p, encoding='utf-8', newline='\n').read()


def md5s(s):
    return hashlib.md5(s.encode('utf-8')).hexdigest()


meas = json.loads(rd(RP('measurement_pr_docx.json')))
pages = meas['result']['pages']
words_word = meas['result']['words']            # ★ Word COM 实测（权威）
md_md5 = meas['inputs']['markdown_md5']

manu = rd(os.path.join(NR(), PARTS[2][1]))
supp = rd(os.path.join(NR(), PARTS[3][1]))
prompt = rd(os.path.join(NR('review_pkg_20260919'), PARTS[0][0]))
qset = rd(os.path.join(NR('review_pkg_20260919'), PARTS[1][0]))

# —— 材料自述（写给评审人看的"这份材料是什么"）——
prose = len(re.findall(r'\S+', re.sub(r'(?m)^\|.*$', '', manu)))   # \S+ 口径：不含表格行
withtab = len(re.findall(r'\S+', manu))                             # \S+ 口径：含表格行
nref = len(re.findall(r'(?m)^\d+\.\s', manu[manu.index('## References'):]))

# —— 纪律④（★ v0652 取反）：**不再读入"本轮变化块"** ——
#   上级裁定 (乙)：把变化块**撤出评审面**。它只作**作者侧内部台账**（`02f_本轮变化块_<tag>.md`，
#   按轮写；留在 review_pkg_20260919\ 或 `_p3_发射件\_变化块台账\`，**不进包、不进任务书**）。
#   判据随之取反：旧版是"该块必须在包里"（三重断言 + 上一轮陈旧串黑名单）；现在改为
#   **反向断言"包里不得出现 `【本轮相对`"**（见下方断言 2）。原 4 处 `sys.exit` 与 STALE 黑名单
#   的判断对象已不存在，故整块删除（不是放宽——是没有被判断的对象了）。

HEADER = """<!-- ===== 材料自述（由 build_paperB_pack.py 生成；数字全部来自测量，不手写）===== -->

【本轮送审材料】主稿（英文送审件）+ 补充材料（附录 A–M 与 Z）。
主稿与补充材料是**两个文件**；以下把它们按顺序拼进同一个包，仅为便于一次读完。

【对象】Pattern Recognition（Elsevier）投稿件。评审方式为**单盲**（官方 L23）。

【长度事实（不可由字数折算，以下为实测）】
- 主稿（Word 实测版式件里 **%d 张图 / %d 张表**，其中 6 张带编号题注；**%d 条参考文献**）按官方 Word 版式（A4 单栏 / 1.5 倍行距 /
  Times New Roman 10 pt，表格 10 pt、图注 8 pt / 页边距 上4.3 右4.8 下4.3 左4.8 cm /
  两端对齐 / 有页码）实测 **%d 页**（Word 自身分页引擎，含阳性对照：注入 600 词后页数必须变化）。
  上限为 20–35 页。
- 主稿词数：**Word 实测 %d 词**（口径 = Word 16.0 COM `ComputeStatistics`，与页数同一把尺子；
  本包各处引用的"实测词数"一律指这个数）。另有 `\\S+` 计数属**另一套口径**，仅供交叉参考、
  **勿与上数互换**：含表格行 **%d**、不含表格行 **%d**。
- 补充材料词数：**%d 词**（口径与 `en_check.py` 相同：`[A-Za-z][A-Za-z'-]*`）。**期刊对补充材料无词数上限**，
  我们也不再自订上限（历轮自订护栏 20000→…→24500 已于 2026-09-24 撤除）；此数**仅作记录**，不作判据。
- 补充材料**另文件提交**。官方文本在"附录是否计入页数上限"上**自相矛盾**
  （L567 同句先说 incl. appendices、紧接说 Appendices are not included；L799 说 including appendices），
  故本包**不代为断言**，只报事实：主稿本身在 35 页内。
- 主稿 md5 `%s`；提示词 md5 `%s`；补充材料 md5 `%s`。

""" % (meas['layout']['inline_shapes'], meas['layout']['tables'], nref,
       pages, words_word, withtab, prose,
       len(re.findall(r"[A-Za-z][A-Za-z'\-]*", supp)),
       md_md5,
       hashlib.md5(prompt.encode('utf-8')).hexdigest(),
       hashlib.md5(supp.encode('utf-8')).hexdigest()) + '\n'

buf = []
buf.append(HEADER)
buf.append('\n<!-- ===== 以下为 %s ===== -->\n\n' % PARTS[0][0])
buf.append(prompt.rstrip('\n') + '\n')
buf.append('\n<!-- ===== 以下为 %s ===== -->\n\n' % PARTS[1][0])
buf.append(qset.rstrip('\n') + '\n')
buf.append('\n<!-- ===== 以下为 %s ===== -->\n\n' % PARTS[2][0])
buf.append(manu.rstrip('\n') + '\n')
buf.append('\n<!-- ===== 以下为 %s ===== -->\n\n' % PARTS[3][0])
buf.append(supp.rstrip('\n') + '\n')
pack = ''.join(buf)

# 同构写入：包里的 06/08 与权威稿必须逐字一致（防止"包里是旧稿"）
for name, src in PARTS:
    src_text = rd(SRC_PATH[name])
    dst = os.path.join(NR('review_pkg_20260919'), name)
    if os.path.abspath(dst) != os.path.abspath(SRC_PATH[name]):
        io.open(dst, 'w', encoding='utf-8', newline='').write(src_text)

# —— 先校验、后落盘（README #51②：不得先写盘再检查，否则失败会留下"看起来像成品"的文件）——
# 断言 1：**四段全部**都在，且逐段与权威源逐字一致
for name, src in PARTS:
    seg = pack.split('<!-- ===== 以下为 %s ===== -->' % name)[-1]
    seg = seg.split('<!-- =====')[0].strip('\n')
    origin = rd(SRC_PATH[name])
    assert seg == origin.strip('\n'), '包内 %s 与源文件不一致' % name
print('四段齐全且与源文件逐字一致 ✓（含 02 提示词 / 02d 问句集——旧版门禁只查 06/08）')
# 断言 2（★ v0652 **反向**）：**评审面不得含"本轮变化块"**。
#   上级裁定 (乙)：该块撤出评审面 ⇒ 判据从"它必须在包里"取反为"包里不得出现它"。
#   轮次一致性的**其余部分**保留：包文件名必须带本轮 tag（TAG 是 OUT 名字的唯一来源，
#   而 ⑤b `pack_sync_check.py` 另核"包 tag == 核验 tag == 内部台账自报轮次"）。
assert '【本轮相对' not in pack, '评审面不得含变化块（v0652 起撤出评审面）'
assert TAG in os.path.basename(OUT), '包文件名必须带本轮 tag（轮次一致性）'
print('反向断言 ✓：包内**不含**「本轮变化块」；包名带本轮 tag %s' % TAG)
# 断言 3：页数上限（超限必须当场失败，不许"先写盘再发现"）
assert pages <= 35, '主稿超页数上限（实测 %d 页）' % pages

# 断言 4（★ 2026-10-02，v0625 新增）：**计数族**的双向闸门。
#   起因（本轮预注册条款）：02d 的 Q4 手写「主稿实测 11,552 词」，而材料自述是脚本算的 11,596 词 ——
#   差 44 词，预注册条款一核就报。上一轮补的双向闸门只管 `本轮 vNNNN` 串（Hy4 逐字指出了这个漏项：
#   "该行不在双向闸门的覆盖范围内（闸门只管 `本轮 vNNNN` 串）"）。
#   判据：**框架文字**里每一个「<N> 词」都必须 ∈ {主稿实测词数, 补充材料词数, round(0.1 × 主稿词数)}。
#   ★ 扫描对象要**正好是**"材料自述 + 02 + 02d"，**不含变化块** —— 变化块按设计必须能引用旧值来
#     叙述"原写 X ⇒ 改为 Y"（README #22：允许历史值存在，判据看的是"现值必须在"）。
#     本闸门第一版就是栽在这一点上：它把变化块里的 `11,552` 当成陈旧串（`76` 号：判据要对上对象）。
#     ★ v0652 起变化块**已不在包内**（反向断言见上）⇒ 扫描对象天然只剩"材料自述 + 02 + 02d"；
#       `_HEAD` 不再需要按「【本轮相对」切分（该串按断言 2 必须不存在），直接取 HEADER。
_HEAD = HEADER                                                        # 材料自述
_M02 = '<!-- ===== 以下为 %s ===== -->' % PARTS[0][0]
_M06 = '<!-- ===== 以下为 %s ===== -->' % PARTS[2][0]
_MID = pack.split(_M02)[1].split(_M06)[0] if _M02 in pack and _M06 in pack else ''
_FRAME = _HEAD + _MID                                                 # 材料自述 + 02 + 02d
_suppwords = len(re.findall(r"[A-Za-z][A-Za-z'\-]*", supp))
_allowed = {words_word, _suppwords, int(round(words_word * 0.10))}
_hits = [(m.group(1), m.group(0).strip()) for m in re.finditer(r'([\d,]{4,7})\s*词', _FRAME)]
_bad = [(v, s) for v, s in _hits if int(v.replace(',', '')) not in _allowed]
if _bad:
    sys.exit('!! 框架文字里的词数不在实测允许集 %s 内：%s ⇒ 拒绝出包（计数族守卫）'
             % (sorted(_allowed), _bad[:6]))
print('框架词数闸门：%d 处 "<N> 词" 全部 ∈ 实测集 %s ✓' % (len(_hits), sorted(_allowed)))

io.open(OUT, 'w', encoding='utf-8', newline='').write(pack)
print('输出 %s' % OUT)
print('  字符 %d  md5 %s' % (len(pack), md5s(pack)))
print('  主稿 %d 页（Word 实测）/ %d 词（Word 实测；\\S+ 含表 %d、不含表 %d）；参考文献 %d 条'
      % (pages, words_word, withtab, prose, nref))
print('BUILD_PACK_OK')
