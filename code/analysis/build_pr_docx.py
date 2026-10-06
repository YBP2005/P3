# -*- coding: utf-8 -*-
"""把英文稿 Markdown 渲染成 **PR 官方版式的 .docx**（官方只收 .docx/.tex，故这是真实交付件）。

版式（官方 L567/L569/L571，与 measure_pr_layout.py 同一套常量）：
  A4 单栏 / 1.5 倍行距 / Times New Roman / 正文含表 10 pt / 图注 8 pt /
  边距 上 4.3 右 4.8 下 4.3 左 4.8 cm（原文顺序 Top, Right, Bottom, Left）/ 页码

图件位置按项目纪律：插在**首次引用该图的段落之后**（位置本身也要被测到）。
生成后用 Word COM 读真实页数，而不是用词数折算。
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
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, RP('analysis', 'work'))
import measure_pages as mp
from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

ROOT = NR()
SRC = RP('PaperB_英文稿_PR_20260919.md')
OUT = NR('PaperB_英文稿_PR.docx')
FIGDIR = RP('analysis', 'figures')
# ★ 2026-10-04（v0646，B6）：图号与 **Appendix D.4 / I.2 的图题**对齐 ——
#   此前 Fig.2/3/4 依次挂 F11/F12/F8，与 D.4 的「Fig.2 提示强度剂量-响应 / Fig.3 阈值清洗 /
#   Fig.4 两失效模式的四面板分离」整体错位。按包内图题（F12 的 suptitle=提示词强度剂量-响应、
#   F8 = 阈值清洗、F11_v2 的 suptitle=弃权与低估两种可分离失效模式）更正。
FIGS = [('F6b_abstention_vs_tile.png', 'Fig. 1'),
        ('F12_prompt_dose.png', 'Fig. 2'),
        ('F8_tau_cleaning.png', 'Fig. 3'),
        ('F11_abstention_vs_undercount.png', 'Fig. 4')]
FIGFILE = dict((label, fn) for fn, label in FIGS)
# ★ 2026-10-06（v0657）：**图题注**。此前 Table 1–6 有正文题注（`**Table N.** …` 段）而
#   Fig. 1–4 **只有图、没有任何题注段**（实测：`w:drawing` = 4，`Fig.\s*\d` 的 4 次命中
#   **全是正文引用**）。现在每张图的**首次引用段之后**紧跟一条 `**Fig. N.** …` 题注段。
#   版式：官方版式给的是「图注 8 pt」（见文件头），故按 `CAP_PT` 渲染，与正文 10 pt 区分。
#
#   ★ 两处落点（缺一即下一轮重建就丢）：
#     · **源稿**（`PaperB_英文稿_PR_20260919.md`）里那四段 `**Fig. N.** …` —— 题注的**正文副本**；
#     · **本表** —— 构建期的**权威副本 + 同名断言**：每遇到一个题注段，就断言它与本表**逐字相等**，
#       不等即**抛错停链**（防"改了源稿忘了这里"或反之而两份悄悄漂移）。
#   两处**不是重复排版**：docx 里只出现一次（正文那份被本表校验后原地渲染）。
FIGCAPS = {
    'Fig. 1': 'Tiling removes the ShanghaiTech-A abstention without harming direction.',
    'Fig. 2': 'The prompt-strength dose–response: relaxation also drives abstention to zero, '
              'but flips $\\rho$ from −82% to +234%…+345%.',
    'Fig. 3': 'The threshold-cleaning curve separating reachable from unreachable levels.',
    'Fig. 4': 'The four-panel separation of the two failure modes: abstention and under-count decouple.',
}
assert set(FIGCAPS) == set(FIGFILE), 'FIGCAPS 与 FIGS 的图号不是一一对应'
RE_CAP = re.compile(r'^\*\*(Fig\.\s*\d+)\.\*\*\s*(.+)$')
# ★ 2026-09-23：正文 35 页顶格，插图宽度 11.4 → 10.4 cm（约省 4 cm 高 ≈ 0.12 页）
# ★ 2026-09-24：为拿回页数余量 10.4 → 9.4 cm（图件 aspect 0.62–0.73 ⇒ 四张合计省约 2.7 cm 高）。
# ★ 2026-09-24：为收回"文字项批次"顶出的页数，10.4 → 9.4 → 9.0 → 8.2 cm（内容不改，只改排版高度）。
# ★ 2026-09-27（v0585）：8.2 → 7.6 cm。起因是补引 [55] 使参考文献列表多出一个段落、
#   末页溢出 1 页；**内容一字未删**，只按本节既有做法下调图件高度（此前 10.4 → 9.4 → 9.0 → 8.2）。
TEXT_W_CM = 7.6
BODY_PT, TBL_PT, CAP_PT = 10, 10, 8
H1_PT, H2_PT, H3_PT = 12, 11, 10


def style_font(st, size, bold=None):
    st.font.name = 'Times New Roman'
    st.font.size = Pt(size)
    if bold is not None:
        st.font.bold = bold
    st.element.rPr.rFonts.set(qn('w:eastAsia'), 'Times New Roman')
    pf = st.paragraph_format
    pf.space_before = Pt(0)
    pf.space_after = Pt(0)
    pf.line_spacing = 1.5


def set_cell_borders(tbl):
    """官方：表格不用竖线。只留上下框线与表头下横线。"""
    tblPr = tbl._tbl.tblPr
    borders = OxmlElement('w:tblBorders')
    for edge in ('top', 'bottom', 'insideH'):
        el = OxmlElement('w:%s' % edge)
        el.set(qn('w:val'), 'single')
        el.set(qn('w:sz'), '4')
        el.set(qn('w:color'), '000000')
        borders.append(el)
    for edge in ('left', 'right', 'insideV'):
        el = OxmlElement('w:%s' % edge)
        el.set(qn('w:val'), 'none')
        el.set(qn('w:sz'), '0')
        borders.append(el)
    tblPr.append(borders)


def add_page_number(footer_par):
    run = footer_par.add_run()
    fld = OxmlElement('w:fldSimple')
    fld.set(qn('w:instr'), 'PAGE')
    run._r.addnext(fld)
    footer_par.alignment = WD_ALIGN_PARAGRAPH.CENTER
    for r in footer_par.runs:
        r.font.size = Pt(CAP_PT)
        r.font.name = 'Times New Roman'


INLINE = re.compile(r'(\*\*.+?\*\*|\*[^*\n]+?\*|`[^`]+?`|\[[^\]]+\]\([^)]+\))')


def add_inline(par, text, size=BODY_PT, bold_all=False):
    """**粗体** / *斜体* / `代码` / [文字](链接) / $公式$ → 若干 run。"""
    for piece in INLINE.split(text):
        if not piece:
            continue
        bold, italic, code = bold_all, False, False
        s = piece
        m = re.fullmatch(r'\*\*(.+?)\*\*', piece, re.S)
        if m:
            s, bold = m.group(1), True
        else:
            m = re.fullmatch(r'\*(.+?)\*', piece, re.S)
            if m:
                s, italic = m.group(1), True
            else:
                m = re.fullmatch(r'`([^`]+?)`', piece, re.S)
                if m:
                    s, code = m.group(1), True
                else:
                    m = re.fullmatch(r'\[([^\]]+)\]\(([^)]+)\)', piece, re.S)
                    if m:
                        s = '%s (%s)' % (m.group(1), m.group(2))
        r = par.add_run(mp.demath(s))
        r.bold = bold
        r.italic = italic or code
        r.font.size = Pt(size)
        r.font.name = 'Times New Roman'
    return par


def build(md, path):
    blocks = mp.parse(md)
    doc = Document()
    sec = doc.sections[0]
    sec.page_width, sec.page_height = Cm(21.0), Cm(29.7)
    sec.top_margin, sec.bottom_margin = Cm(4.3), Cm(4.3)
    sec.left_margin, sec.right_margin = Cm(4.8), Cm(4.8)
    st = doc.styles['Normal']
    style_font(st, BODY_PT)
    st.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    for name, size in (('Heading 1', H1_PT), ('Heading 2', H2_PT), ('Heading 3', H3_PT),
                       ('Heading 4', H3_PT)):
        try:
            style_font(doc.styles[name], size, bold=True)
            doc.styles[name].font.color.rgb = RGBColor(0, 0, 0)
        except KeyError:
            pass
    add_page_number(sec.footer.paragraphs[0])

    fig_used = set()
    cap_done = []

    def place_fig(label):
        """把 `label` 的图件插成**居中、单倍行距、宽度 TEXT_W_CM** 的独立段落。

        返回 True 表示真的插了图（图件缺失时静默不插，保持既有行为）。
        """
        fp = os.path.join(RP('analysis', 'figures'), FIGFILE[label])
        if not os.path.exists(fp):
            return False
        ip = doc.add_paragraph()
        ip.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER
        ip.paragraph_format.line_spacing = 1.0
        ip.add_run().add_picture(fp, width=Cm(TEXT_W_CM))
        return True

    for b in blocks:
        if b[0] == 'hr':
            p = doc.add_paragraph()
            p.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER
            add_inline(p, '— — —', CAP_PT)
        elif b[0] == 'h':
            lvl, txt = b[1], b[2]
            p = doc.add_heading(level=min(lvl, 4))
            add_inline(p, txt, size=(H1_PT if lvl <= 2 else H3_PT), bold_all=True)
        elif b[0] == 'tbl':
            rows = b[1]
            ncol = max(len(r) for r in rows)
            t = doc.add_table(rows=0, cols=ncol)
            set_cell_borders(t)
            for ri, row in enumerate(rows):
                cells = t.add_row().cells
                for ci in range(ncol):
                    txt = row[ci] if ci < len(row) else ''
                    par = cells[ci].paragraphs[0]
                    par.paragraph_format.line_spacing = 1.0
                    par.paragraph_format.space_after = Pt(0)
                    add_inline(par, txt, size=TBL_PT, bold_all=(ri == 0))
            doc.add_paragraph()
        elif b[0] == 'p':
            _mc = RE_CAP.match(b[1].strip())
            if _mc and _mc.group(1) in FIGCAPS:
                # ★ v0657：题注段 —— 先把图件插在它**上面**，再把它按 `CAP_PT` 渲染成题注。
                _lab = _mc.group(1)
                _txt = ' '.join(_mc.group(2).split())
                assert _txt == FIGCAPS[_lab], (
                    '图题注两处不一致 ⇒ 停链：源稿 md 为 %r，build_pr_docx.FIGCAPS 为 %r'
                    % (_txt, FIGCAPS[_lab]))
                if _lab not in fig_used:
                    fig_used.add(_lab)
                    place_fig(_lab)
                _cp = doc.add_paragraph()
                add_inline(_cp, '**%s.** %s' % (_lab, _txt), size=CAP_PT)
                cap_done.append(_lab)
                continue
            p = doc.add_paragraph()
            add_inline(p, b[1])
            # 图件插在**首次引用该图**的段落之后（不是插在文末）
            for fn, label in FIGS:
                if label in fig_used:
                    continue
                if re.search(r'\b%s\b' % re.escape(label), b[1]):
                    fig_used.add(label)
                    place_fig(label)
    assert sorted(cap_done) == sorted(set(FIGCAPS)), (
        '缺图题注 ⇒ 停链：已渲染 %s，期望 %s（每张图必须恰有一条 `**Fig. N.** …` 题注段）'
        % (sorted(cap_done), sorted(FIGCAPS)))
    doc.save(path)
    return len(blocks), sorted(fig_used), sorted(cap_done)


def main():
    md = io.open(SRC, encoding='utf-8', newline='').read()
    n, used, caps = build(md, OUT)
    print('blocks=%d  已插图=%s  已渲染题注=%s' % (n, used, caps))
    print('输出 %s（%d B）' % (OUT, os.path.getsize(OUT)))
    missing = [l for _, l in FIGS if l not in used]
    if missing:
        print('⚠ 正文未引用（未插图）：%s' % missing)
    import win32com.client as w
    app = w.Dispatch('Word.Application')
    app.Visible = False
    d = app.Documents.Open(OUT, ReadOnly=True)
    try:
        d.Repaginate()
        pages = d.ComputeStatistics(2)
        words = d.ComputeStatistics(0)
        print('Word 实测：%d 页 / %d 词  ⇒ %s（上限 35 页）'
              % (pages, words, '✓ 合规' if pages <= 35 else '✗ 超 %d 页' % (pages - 35)))
    finally:
        d.Close(False)
        app.Quit()


# ★ 用 `if __name__ == '__main__'` 而不是裸调用：本模块的行内解析与页面设置要被
#   build_coverletter_docx.py **import 复用**，裸调用会在 import 时重建一次正文 docx。
if __name__ == '__main__':
    main()
