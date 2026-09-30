# -*- coding: utf-8 -*-
"""按 PR **官方 Word 版式**实测页数（把 26 号文 §5.3 的假设变成测量）。

官方条款（the journal's submission-webpage notes；该原文**未随包发布**）：
  L567  single-column, **1.5 spaced when writing in Word**, fully-justified, numbered pages
  L569  **Times New Roman**; Font size of text **incl. tables 10pt**; **footnotes and captions 8pt**
  L571  Margins should be 4.3cm, 4.8cm, 4.3cm, 4.8cm **(Top, Right, Bottom, Left)**

⇒ 版心宽 = 21.0 − 4.8 − 4.8 = 11.4 cm；版心高 = 29.7 − 4.3 − 4.3 = 21.1 cm。

同时给出两个变体以夹住区间（标题字号官方未规定，故两种都测）：
  A：标题 12pt 粗体（偏保守，页数偏多）
  B：标题 10pt 粗体（下界）
图件高度仍走 none / 7.5cm 两档（图件真实高度是未定参数）。
阳性对照：注入 600 词，确认页数会变（不随内容变化的测量不是测量）。
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
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, RP('analysis', 'work'))
import measure_pages as mp

ROOT = NR()
EN = RP('PaperB_英文稿_PR_20260919.md')
OUT_RTF = os.path.join(mp.OUT_RTF, 'pr')
OUT_JSON = NR('measurement_pr_layout.json')

CM = 566.9291338582677           # 1 cm → twips（1 inch = 1440 twips = 2.54 cm）
PAGE_W_TW, PAGE_H_TW = 11906, 16838
MT, MR, MB, ML = (int(4.3 * CM), int(4.8 * CM), int(4.3 * CM), int(4.8 * CM))
BODY_FS = 20                     # 10 pt（RTF 半磅）
BODY_LINE = 360                  # 1.5 倍（单倍=240）
TBL_FS = 20                      # 表格同为 10 pt（官方明说 incl. tables）
TBL_LINE = 240                   # 表格单倍
CAP_FS = 16                      # 图注 8 pt
H1_FS_A, H2_FS_A = 24, 20        # 变体 A：一级 12pt、其余 10pt
H1_FS_B, H2_FS_B = 20, 20        # 变体 B：全部 10pt


def para_pr(txt, fs=BODY_FS, line=BODY_LINE, bold=False, justify=True):
    body = mp.inline(txt)
    if bold:
        body = '\\b ' + body + '\\b0'
    q = '\\qj ' if justify else ''
    return '{\\%s\\sl%d\\slmult1\\fs%d %s\\par}\n' % (q, line, fs, body)


def table_pr(rows):
    """10 pt 单倍、无竖线（官方：不用竖线）的表格。"""
    ncol = max(len(r) for r in rows)
    width = (PAGE_W_TW - ML - MR) // ncol
    out = []
    for ri, row in enumerate(rows):
        out.append('\\trowd\\trgaph60\\trleft0')
        for ci in range(ncol):
            out.append('\\cellx%d' % (width * (ci + 1)))
        out.append('\n')
        for ci in range(ncol):
            cell = row[ci] if ci < len(row) else ''
            b = '\\b ' if ri == 0 else ''
            e = '\\b0' if ri == 0 else ''
            out.append('{\\intbl\\sl%d\\slmult1\\fs%d %s%s%s\\cell}\n'
                       % (TBL_LINE, TBL_FS, b, mp.inline(cell), e))
        out.append('\\row\n')
    return ''.join(out)


def build(md, fig_cm, variant, extra=None):
    blocks = mp.parse(md)
    body = ['{\\rtf1\\ansi\\ansicpg1252\\deff0',
            '{\\fonttbl{\\f0\\froman Times New Roman;}}',
            '\\paperw%d\\paperh%d\\margl%d\\margr%d\\margt%d\\margb%d\\f0'
            % (PAGE_W_TW, PAGE_H_TW, ML, MR, MT, MB)]
    h1, h2 = (H1_FS_A, H2_FS_A) if variant == 'A' else (H1_FS_B, H2_FS_B)
    fig_tw = int(fig_cm / 2.54 * 1440) if fig_cm else 0
    nfig = 0
    for b in blocks:
        if b[0] == 'hr':
            body.append(para_pr('— — —', fs=CAP_FS, line=240))
        elif b[0] == 'h':
            lvl, txt = b[1], b[2]
            body.append(para_pr(txt, fs=h1 if lvl <= 2 else h2, line=BODY_LINE, bold=True))
        elif b[0] == 'tbl':
            body.append(table_pr(b[1]))
            body.append(para_pr('', fs=CAP_FS, line=240, justify=False))
        elif b[0] == 'p':
            body.append(para_pr(b[1]))
            # ⚠ 教训：不能用 `Figures?\s+\d` 匹配 —— 正文写的是 "Figures **1–4**"，
            # "Figures " 之后是 "**" 而非数字，那样会插入 0 个图位而页数看似"合规"。
            # 故与 measure_fix.py 一致，用正文声明的归属段落作锚点。
            if fig_tw and ('Figures **1–4**' in b[1] or 'Figures 1–4' in b[1]):
                for _ in range(4):
                    nfig += 1
                    body.append('{\\sl%d\\slmult0\\fs%d [Figure %d reserved %.1f cm]\\par}\n'
                                % (fig_tw, CAP_FS, nfig, fig_cm))
    if extra:
        body.append(para_pr(extra))
    body.append('}')
    return ''.join(body)


def main():
    os.makedirs(OUT_RTF, exist_ok=True)
    md = io.open(EN, encoding='utf-8', newline='').read()
    print('=' * 104)
    print('PR 官方 Word 版式实测：A4／单栏／1.5 倍行距／正文含表 10pt／图注 8pt')
    print('  边距 上%.1f 右%.1f 下%.1f 左%.1f cm（官方原文顺序 Top,Right,Bottom,Left）'
          % (MT / CM, MR / CM, MB / CM, ML / CM))
    print('  版心 %.1f × %.1f cm' % ((PAGE_W_TW - ML - MR) / CM, (PAGE_H_TW - MT - MB) / CM))
    print('  输入 %s  md5 %s' % (os.path.basename(EN), mp.md5f(EN)[:12]))
    print('=' * 104)
    print('  %-8s %-10s %8s %9s %12s' % ('标题字号', '图件', '页数', '词数', '与 35 页'))
    res = {}
    for variant, desc in (('A', '12/10pt'), ('B', '10/10pt')):
        for cm in (None, 7.5):
            tag = 'title%s_fig%s' % (variant, 'none' if cm is None else '%.1f' % cm)
            rtf = build(md, cm, variant)
            p = os.path.join(OUT_RTF, 'pr_%s.rtf' % tag)
            io.open(p, 'w', encoding='ascii', errors='replace', newline='\r\n').write(rtf)
            pages, words = mp.word_pages(p)
            res[tag] = dict(variant=variant, fig_cm=cm, pages=pages, words=words,
                            rtf_md5=mp.md5f(p))
            print('  %-8s %-10s %8d %9d %12s'
                  % (desc, 'none' if cm is None else '%.1fcm' % cm, pages, words,
                     '✓ 合规' if pages <= 35 else '✗ 超 %d 页' % (pages - 35)))

    # 阳性对照：注入 600 词，页数必须变化
    FILLER = ('Injected control paragraph for measurement validity. ' * 100).strip()
    rtf = build(md, 7.5, 'A', extra=FILLER)
    p = os.path.join(OUT_RTF, 'pr_control.rtf')
    io.open(p, 'w', encoding='ascii', errors='replace', newline='\r\n').write(rtf)
    cp, _ = mp.word_pages(p)
    before = res['titleA_fig7.5']['pages']
    print()
    print('  阳性对照：注入 %d 词 ⇒ %d 页 → %d 页  %s'
          % (len(FILLER.split()), before, cp, '✓ 测量有效' if cp != before else '⚠ 未响应！'))

    out = dict(
        measured_at='2026-09-21', tool='Word COM ComputeStatistics(2)',
        layout_source='PR submission-webpage template notes, L567/L569/L571 (source file not released)',
        layout=dict(page='A4', columns=1, spacing='1.5 (Word)', body_pt=10, table_pt=10,
                    caption_pt=8, justify=True,
                    margins_cm=dict(top=4.3, right=4.8, bottom=4.3, left=4.8),
                    text_area_cm=[round((PAGE_W_TW - ML - MR) / CM, 2),
                                  round((PAGE_H_TW - MT - MB) / CM, 2)]),
        inputs=dict(en=EN, en_md5=mp.md5f(EN)),
        variants=res,
        positive_control=dict(injected_words=len(FILLER.split()), pages_before=before,
                              pages_after=cp, responded=cp != before))
    io.open(OUT_JSON, 'w', encoding='utf-8', newline='\n').write(
        json.dumps(out, ensure_ascii=False, indent=2))
    print('  已冻结：%s' % OUT_JSON)


main()
