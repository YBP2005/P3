# -*- coding: utf-8 -*-
"""测量保真度修正 + 阳性对照。

三件事：
  ① 诊断：确认 `\\trowd`（表格）与图位在 RTF 中真的存在（用文件脚本，避免内联转义把反斜杠吃掉）；
  ② 修图位：正文只以 "Figures **1–4**" 集合引用，故按正文声明的归属位置插入 4 个图位；
  ③ **阳性对照**：注入一个已知大小的块，确认页数**会变**——不随内容变化的测量不是测量
     （`02` 的原则：一条从不失败的守卫 = 冻结当时状态的负锚点）。
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
import io, os, re, sys, json, hashlib
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, RP('analysis', 'work'))
import measure_pages as mp

EN = mp.EN
FIG_POS = 'the numerosity-stimulus comparison of §2.5 is Table 2'
FIG_BLOCK_MARK = 'Figures **1–4** are carried in the main text'


def build(md, fig_cm, fig_count=4, extra=None):
    """在 §3.9 声明的段落之后插入 fig_count 个图位；extra 可注入额外段落做对照。"""
    blocks = mp.parse(md)
    out = []
    fig_h_tw = int(fig_cm / 2.54 * 1440) if fig_cm else 0
    inserted = 0
    for b in blocks:
        out.append(b)
        if b[0] == 'p' and FIG_BLOCK_MARK in b[1] and fig_h_tw:
            out.append(('figslot', fig_count, fig_cm))
            inserted = fig_count
    if extra:
        out.append(('p', extra))
    return out, inserted


def render(blocks, path, fig_h_tw):
    body = ['{\\rtf1\\ansi\\ansicpg1252\\deff0',
            '{\\fonttbl{\\f0\\froman Times New Roman;}{\\f1\\fswiss Arial;}}',
            '\\paperw%d\\paperh%d\\margl%d\\margr%d\\margt%d\\margb%d\\f0'
            % (mp.PAGE_W_TW, mp.PAGE_H_TW, mp.MARGIN_TW, mp.MARGIN_TW, mp.MARGIN_TW, mp.MARGIN_TW)]
    nfig = 0
    for b in blocks:
        if b[0] == 'hr':
            body.append(mp.para('— — —', fs=18, line=240))
        elif b[0] == 'h':
            lvl, txt = b[1], b[2]
            body.append(mp.para(txt, fs=28 if lvl <= 2 else 24, line=560 if lvl <= 2 else 480, bold=True))
        elif b[0] == 'tbl':
            body.append(mp.table_rtf(b[1]))
            body.append(mp.para('', fs=18, line=220))
        elif b[0] == 'figslot':
            cnt, cm = b[1], b[2]
            tw = int(cm / 2.54 * 1440)
            for _ in range(cnt):
                nfig += 1
                body.append('{\\sl%d\\slmult0\\fs24 [Figure %d reserved %.1f cm]\\par}\n' % (tw, nfig, cm))
        elif b[0] == 'p':
            body.append(mp.para(b[1]))
    body.append('}')
    io.open(path, 'w', encoding='ascii', errors='replace', newline='\r\n').write(''.join(body))
    return nfig


md = io.open(EN, encoding='utf-8', newline='').read()
os.makedirs(mp.OUT_RTF, exist_ok=True)

print('=' * 106)
print('① 诊断：RTF 中是否真有表格与图位')
print('=' * 106)
bl, _ = build(md, 7.5)
p_diag = os.path.join(mp.OUT_RTF, 'diag.rtf')
nf = render(bl, p_diag, 0)
rtf = io.open(p_diag, encoding='ascii', errors='replace').read()
print('  \\trowd（表格行）      : %d 次' % rtf.count('\\trowd'))
print('  \\cell（单元格）       : %d 次' % rtf.count('\\cell'))
print('  图位占位符            : %d 个' % rtf.count('[Figure'))
print('  \\sl3969（7.5cm 行高） : %d 次' % rtf.count('\\sl3969'))
print('  block 类型            : %s' % {t: sum(1 for x in bl if x[0] == t) for t in set(x[0] for x in bl)})

print()
print('=' * 106)
print('② 真分页实测（图位按 §3.9 声明的段落之后插入）')
print('=' * 106)
print('  %-10s %7s %10s %10s' % ('图件高度', '页数', '与 none', '与 35 页'))
res = {}
for cm in [None, 6.0, 7.5, 9.0]:
    bl, ins = build(md, cm)
    tag = 'none' if cm is None else ('%.1fcm' % cm)
    p = os.path.join(mp.OUT_RTF, 'fix_%s.rtf' % tag)
    nfig = render(bl, p, 0)
    pages, words = mp.word_pages(p)
    res[tag] = dict(fig_cm=cm, pages=pages, words=words, figures=nfig, rtf_md5=mp.md5f(p))
    print('  %-10s %7d %10s %10s' % (tag, pages, '—',
          '✓ 合规' if pages <= 35 else '✗ 超 %d' % (pages - 35)))
base = res['none']['pages']
for tag, d in res.items():
    if d['fig_cm']:
        print('  → 图件成本 %-8s : %+d 页（4 张 × %.1f cm）' % (tag, d['pages'] - base, d['fig_cm']))

print()
print('=' * 106)
print('③ 阳性对照：注入已知块，测量必须发生变化')
print('=' * 106)
FILLER = ('Injected control paragraph for measurement validity. ' * 40).strip()
bl, _ = build(md, 7.5, extra=FILLER)
p = os.path.join(mp.OUT_RTF, 'control.rtf')
render(bl, p, 0)
cp, cw = mp.word_pages(p)
same = res['7.5cm']['pages']
print('  注入 %d 词（约 %.1f 页）：%d 页 → %d 页' % (len(FILLER.split()), len(FILLER.split()) / 280,
                                              same, cp))
print('  ⇒ %s' % ('**测量随内容变化，测量有效**' if cp != same else '⚠ 页数未变，测量无效！'))

out = dict(measured_at='2026-09-19', tool='Word COM ComputeStatistics(2)',
           layout=dict(page='A4', columns=1, spacing='double', body_pt=12, margin_cm=2.54,
                       table_pt=9, table_spacing='single', figure_placement='after the §3.9 paragraph'),
           inputs=dict(en=EN, en_md5=mp.md5f(EN), sup=mp.SUP, sup_md5=mp.md5f(mp.SUP)),
           variants=res,
           positive_control=dict(injected_words=len(FILLER.split()), pages_before=same, pages_after=cp,
                                 responded=cp != same),
           diagnostics=dict(trowd=rtf.count('\\trowd'), cells=rtf.count('\\cell'),
                            figure_slots=rtf.count('[Figure')))
io.open(mp.OUT_JSON, 'w', encoding='utf-8', newline='\n').write(
    json.dumps(out, ensure_ascii=False, indent=2))
print('\n  已冻结：%s' % mp.OUT_JSON)
