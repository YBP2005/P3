# -*- coding: utf-8 -*-
"""把英文稿 Markdown 渲染成 **PR 官方版式的 .docx**（官方只收 .docx/.tex，故这是真实交付件）。

版式（官方 L567/L569/L571，与 measure_pr_layout.py 同一套常量）：
  A4 单栏 / 1.5 倍行距 / Times New Roman / 正文含表 10 pt / 图注 8 pt /
  边距 上 4.3 右 4.8 下 4.3 左 4.8 cm（原文顺序 Top, Right, Bottom, Left）/ 页码

图件位置按项目纪律：插在**首次引用该图的段落之后**（位置本身也要被测到）。
生成后用 Word COM 读真实页数，而不是用词数折算。
"""
import io
import os
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, r'<WORKDIR>\PaperB\analysis\work')
import measure_pages as mp
from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

ROOT = r'<WORKDIR>\PaperB'
SRC = os.path.join(ROOT, 'PaperB_英文稿_PR_20260919.md')
OUT = os.path.join(ROOT, 'PaperB_英文稿_PR.docx')
FIGDIR = os.path.join(ROOT, 'analysis', 'figures')
FIGS = [('F6b_abstention_vs_tile.png', 'Fig. 1'),
        ('F11_abstention_vs_undercount.png', 'Fig. 2'),
        ('F12_prompt_dose.png', 'Fig. 3'),
        ('F8_tau_cleaning.png', 'Fig. 4')]
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
            p = doc.add_paragraph()
            add_inline(p, b[1])
            # 图件插在**首次引用该图**的段落之后（不是插在文末）
            for fn, label in FIGS:
                if label in fig_used:
                    continue
                if re.search(r'\b%s\b' % re.escape(label), b[1]):
                    fig_used.add(label)
                    fp = os.path.join(FIGDIR, fn)
                    if os.path.exists(fp):
                        ip = doc.add_paragraph()
                        ip.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER
                        ip.paragraph_format.line_spacing = 1.0
                        ip.add_run().add_picture(fp, width=Cm(TEXT_W_CM))
    doc.save(path)
    return len(blocks), sorted(fig_used)


def main():
    md = io.open(SRC, encoding='utf-8', newline='').read()
    n, used = build(md, OUT)
    print('blocks=%d  已插图=%s' % (n, used))
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
