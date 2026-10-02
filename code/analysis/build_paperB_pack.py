# -*- coding: utf-8 -*-
"""build_paperB_pack.py — 组装 PaperB 的**盲审包**（本轮 = 修订版评分表 + 改稿后的英文送审件）。

包结构（与上一轮 01d 逐段同构，便于跨轮比较）：
    <!-- ===== 材料自述 ===== -->                       （由本脚本生成：长度事实 + **本轮变化块**）
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
  ④ ★ **"本轮变化块"不再硬编码在本脚本里**。根因见 2026-09-26 审计件
     `..\发射前审计_v0562_发现两处陈旧_20260926.md`：该块曾是常量，于是 v0557–v0562
     **连续六枚 pin 逐字节相同**，评审被"告知"的是早已审过的 v0542–v0545 改动。
     现改为从 `02f_本轮变化块_<tag>.md` 读入，并**三重断言**：
     (a) 文件首行的 `change-block-round` == 本轮 tag；
     (b) 块内不含**上一轮特有**的陈旧串；
     (c) 该块确实进了包。任一不满足即**拒绝出包**（先校验、后落盘）。

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
CHANGE_SRC = os.path.join(NR('review_pkg_20260919'), '02f_本轮变化块_%s.md' % TAG)
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

# —— 材料自述（写给审稿人看的"这份材料是什么"）——
prose = len(re.findall(r'\S+', re.sub(r'(?m)^\|.*$', '', manu)))   # \S+ 口径：不含表格行
withtab = len(re.findall(r'\S+', manu))                             # \S+ 口径：含表格行
nref = len(re.findall(r'(?m)^\d+\.\s', manu[manu.index('## References'):]))

# —— 纪律④：读入"本轮变化块"并断言它**确实是本轮的** ——
if not os.path.exists(CHANGE_SRC):
    sys.exit('!! 找不到本轮变化块 %s ⇒ 拒绝出包（纪律④：该块必须按轮提供，不得沿用旧块）'
             % os.path.basename(CHANGE_SRC))
change = rd(CHANGE_SRC).strip('\n')
_m = re.search(r'^<!--\s*change-block-round:\s*(\S+?)\s*-->', change)
if not _m:
    sys.exit('!! %s 首行缺少 `<!-- change-block-round: <tag> -->` ⇒ 无法判定它属于哪一轮，拒绝出包'
             % os.path.basename(CHANGE_SRC))
if _m.group(1) != TAG:
    sys.exit('!! 变化块声明轮次 %s ≠ 本轮 tag %s ⇒ 拒绝出包'
             '（这正是 v0557–v0562 连续六枚 pin 陈旧的那个失效模式）' % (_m.group(1), TAG))
# 剥掉开头两段 HTML 注释（change-block-round 标记 + 写给维护者的说明），只留评审可见正文
_b = re.sub(r'^\s*<!--.*?-->\s*', '', change, flags=re.S)
_b = re.sub(r'^\s*<!--.*?-->\s*', '', _b, flags=re.S)
BODY = _b.strip('\n')
if not BODY:
    sys.exit('!! %s 剥掉注释后没有正文 ⇒ 拒绝出包' % os.path.basename(CHANGE_SRC))

# 陈旧串黑名单：这些是**上一轮（v0547）**特有的说法，出现在"本轮变化块"里即为沿用旧块。
STALE = ['跨口径相减被查出并更正', 'zero-channel precision', '12.7% vs 48.7%',
         '18 次起服 / 21,600 次调用', 'M.40 新增逐项 2×2 表', 'within-family paired']
_hit = [s for s in STALE if s in BODY]
if _hit:
    sys.exit('!! 本轮变化块里出现**上一轮特有**的陈旧串 %r ⇒ 拒绝出包' % _hit)

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
       hashlib.md5(supp.encode('utf-8')).hexdigest()) + BODY + '\n'

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
# 断言 2：本轮变化块确实进了包，且声明轮次 == 本轮 tag
assert BODY in pack, '本轮变化块未进包'
assert _m.group(1) == TAG, '变化块轮次不符'
print('本轮变化块来自 %s，声明轮次 %s ✓' % (os.path.basename(CHANGE_SRC), _m.group(1)))
# 断言 3：页数上限（超限必须当场失败，不许"先写盘再发现"）
assert pages <= 35, '主稿超页数上限（实测 %d 页）' % pages

# 断言 4（★ 2026-10-02，v0625 新增）：**计数族**的双向闸门。
#   起因（本轮 3 家评审）：02d 的 Q4 手写「主稿实测 11,552 词」，而材料自述是脚本算的 11,596 词 ——
#   差 44 词，评审一核就报。v0624 补的双向闸门只管 `本轮 vNNNN` 串（Hy4 逐字指出了这个漏项：
#   "该行不在双向闸门的覆盖范围内（闸门只管 `本轮 vNNNN` 串）"）。
#   判据：**框架文字**里每一个「<N> 词」都必须 ∈ {主稿实测词数, 补充材料词数, round(0.1 × 主稿词数)}。
#   ★ 扫描对象要**正好是**"材料自述 + 02 + 02d"，**不含变化块** —— 变化块按设计必须能引用旧值来
#     叙述"原写 X ⇒ 改为 Y"（README #22：允许历史值存在，判据看的是"现值必须在"）。
#     本闸门第一版就是栽在这一点上：它把变化块里的 `11,552` 当成陈旧串（`76` 号：判据要对上对象）。
_HEAD = pack.split('【本轮相对')[0]                                   # 材料自述（变化块之前）
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
