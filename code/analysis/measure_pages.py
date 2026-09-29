# -*- coding: utf-8 -*-
"""真分页实测：Markdown → RTF（A4／单栏／双倍行距／12 pt／2.54 cm）→ Word COM ComputeStatistics(2)。

依 `19_送审材料的自述文字与测量保真度.md` §3 的三条纪律：
  ① **表格必须显式按 9 pt 单倍渲染**，不能落进"双倍行距正文"分支（该偏差能值一整页）；
  ② **"位置"也是测量的一部分** —— 图件插在"首次引用它的段落后"，并在结果里记录该位置；
  ③ 实测结果连同**全部输入的 md5** 冻结进 measurement.json。

同时给出**变体阶梯**，因为"图件多高"本身是未定参数：
  none / 6cm / 7.5cm / 9cm  ×  （表格 9pt 单倍，已固定）
真页数由 Word 的分页引擎给出，不再用词数折算。
"""
import io, os, re, sys, json, hashlib, subprocess
sys.stdout.reconfigure(encoding='utf-8')

ROOT = r'<WORKDIR>\PaperB'
EN = os.path.join(ROOT, 'PaperB_英文稿_PR_20260919.md')
SUP = os.path.join(ROOT, 'PaperB_英文补充材料_PR_20260919.md')
WORK = os.path.join(ROOT, 'analysis', 'work')
OUT_RTF = os.path.join(WORK, '_measure')
OUT_JSON = os.path.join(ROOT, 'measurement.json')

# ---- 版式常量（单一真相源；改版式只改这里）----
PAGE_W_TW, PAGE_H_TW = 11906, 16838          # A4
MARGIN_TW = 1440                              # 2.54 cm
BODY_FS = 24                                  # 12 pt
BODY_LINE = 480                               # 双倍行距（12pt 单倍 = 240）
TBL_FS = 18                                   # 9 pt
TBL_LINE = 220                                # 单倍（9pt）
FIG_HEIGHTS_CM = [None, 6.0, 7.5, 9.0]        # None = 不留图位

MATH = [('\\rho', 'ρ'), ('\\sigma', 'σ'), ('\\tau', 'τ'), ('\\kappa', 'κ'), ('\\ell', 'ℓ'),
        ('\\lambda', 'λ'), ('\\mu', 'μ'), ('\\alpha', 'α'), ('\\delta', 'δ'), ('\\Delta', 'Δ'),
        ('\\times', '×'), ('\\approx', '≈'), ('\\ge', '≥'), ('\\le', '≤'), ('\\pm', '±'),
        ('\\cdot', '·'), ('\\to', '→'), ('\\sum', 'Σ'), ('\\qed', '□'), ('\\infty', '∞'),
        ('\\lvert', '|'), ('\\rvert', '|'), ('\\bar\\rho', 'ρ̄'), ('\\big/', '/'),
        ('\\max', 'max'), ('\\min', 'min'), ('\\mid', '|'), ('\\;', ' '), ('\\,', ' '),
        ('\\!', ''), ('\\ ', ' '), ('\\text', ''), ('\\operatorname', ''), ('\\mathrm', '')]


def demath(s):
    s = s.replace('$$', '').replace('$', '')
    for a, b in MATH:
        s = s.replace(a, b)
    s = re.sub(r'\\frac\{([^{}]*)\}\{([^{}]*)\}', r'\1/\2', s)
    s = re.sub(r'\\[a-zA-Z]+', '', s)
    s = s.replace('{', '').replace('}', '')
    return s


def esc(s):
    s = demath(s)
    s = s.replace('\\', '\\\\').replace('{', '\\{').replace('}', '\\}')
    out = []
    for ch in s:
        o = ord(ch)
        if o < 128:
            out.append(ch)
        elif o <= 0xFFFF:
            out.append('\\u%d?' % o)
        else:
            out.append('\\u%d?' % (o - 0x10000))
    return ''.join(out)


def inline(s):
    """**粗体** / `代码` / *斜体* → RTF 行内标记。"""
    s = esc(s)
    s = re.sub(r'\*\*(.+?)\*\*', r'\\b \1\\b0 ', s)
    s = re.sub(r'(?<!\\)\*(?!\s)(.+?)(?<!\s)\*', r'\\i \1\\i0 ', s)
    s = s.replace('`', '')
    return s


def para(txt, fs=BODY_FS, line=BODY_LINE, bold=False, exact=None):
    body = inline(txt)
    if bold:
        body = '\\b ' + body + '\\b0'
    if exact:
        return '{\\sl%d\\slmult0\\fs%d %s\\par}\n' % (exact, fs, body)
    return '{\\sl%d\\slmult1\\fs%d %s\\par}\n' % (line, fs, body)


def table_rtf(rows):
    """9 pt 单倍行距的 RTF 表格（§3 纪律①）。"""
    ncol = max(len(r) for r in rows)
    width = (PAGE_W_TW - 2 * MARGIN_TW) // ncol
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
            out.append('{\\intbl\\sl%d\\slmult1\\fs%d %s%s%s\\cell}\n' % (TBL_LINE, TBL_FS, b, inline(cell), e))
        out.append('\\row\n')
    return ''.join(out)


def parse(md):
    """→ block 列表：('h',level,text) / ('p',text) / ('tbl',rows) / ('fig',n) / ('hr',)"""
    lines = md.split('\n')
    blocks, i = [], 0
    while i < len(lines):
        ln = lines[i]
        s = ln.strip()
        if not s:
            i += 1
            continue
        if re.match(r'^-{3,}$', s):
            blocks.append(('hr',)); i += 1; continue
        m = re.match(r'^(#{1,4})\s+(.*)$', s)
        if m:
            blocks.append(('h', len(m.group(1)), m.group(2))); i += 1; continue
        if s.startswith('|'):
            rows = []
            while i < len(lines) and lines[i].strip().startswith('|'):
                cells = [c.strip() for c in lines[i].strip().strip('|').split('|')]
                if not re.match(r'^[\s\-:|]+$', lines[i].strip().strip('|')):
                    rows.append(cells)
                i += 1
            blocks.append(('tbl', rows)); continue
        if s.startswith('$$') and not s.endswith('$$'):
            buf = [s]
            i += 1
            while i < len(lines) and '$$' not in lines[i]:
                buf.append(lines[i].strip()); i += 1
            if i < len(lines):
                buf.append(lines[i].strip()); i += 1
            blocks.append(('p', ' '.join(buf))); continue
        if re.match(r'^[-*]\s+', s):
            blocks.append(('p', '• ' + re.sub(r'^[-*]\s+', '', s))); i += 1; continue
        if re.match(r'^\d+\.\s+', s):
            blocks.append(('p', s)); i += 1; continue
        if s.startswith('>'):
            blocks.append(('p', re.sub(r'^>\s*', '', s))); i += 1; continue
        buf = [s]
        i += 1
        while i < len(lines) and lines[i].strip() and not re.match(
                r'^(#{1,4}\s|\||-{3,}$|[-*]\s|\d+\.\s|>|\$\$)', lines[i].strip()):
            buf.append(lines[i].strip()); i += 1
        blocks.append(('p', ' '.join(buf)))
    return blocks


def build_rtf(md, fig_cm):
    blocks = parse(md)
    body = ['{\\rtf1\\ansi\\ansicpg1252\\deff0',
            '{\\fonttbl{\\f0\\froman Times New Roman;}{\\f1\\fswiss Arial;}}',
            '\\paperw%d\\paperh%d\\margl%d\\margr%d\\margt%d\\margb%d\\f0'
            % (PAGE_W_TW, PAGE_H_TW, MARGIN_TW, MARGIN_TW, MARGIN_TW, MARGIN_TW)]
    fig_h_tw = int(fig_cm / 2.54 * 1440) if fig_cm else 0
    placed = set()
    for b in blocks:
        if b[0] == 'hr':
            body.append(para('— — —', fs=18, line=240))
        elif b[0] == 'h':
            lvl, txt = b[1], b[2]
            if lvl <= 2:
                body.append(para(txt, fs=28, line=560, bold=True))
            else:
                body.append(para(txt, fs=24, line=480, bold=True))
        elif b[0] == 'tbl':
            body.append(table_rtf(b[1]))
            body.append(para('', fs=18, line=220))
        elif b[0] == 'p':
            body.append(para(b[1]))
            # 图件放在"首次引用它的段落"之后（§3 纪律②）
            if fig_h_tw:
                for n in re.findall(r'\bFigures?\s+(\d)', b[1]):
                    n = int(n)
                    if 1 <= n <= 4 and n not in placed:
                        placed.add(n)
                        body.append('{\\sl%d\\slmult0\\fs24 [Figure %d — %.1f cm]\\par}\n'
                                    % (fig_h_tw, n, fig_cm))
    body.append('}')
    return ''.join(body), sorted(placed)


def word_pages(rtf_path):
    ps = subprocess.run(
        ['powershell', '-NoProfile', '-Command',
         '$ErrorActionPreference="Stop";'
         '$w=New-Object -ComObject Word.Application;'
         '$w.Visible=$false; $w.DisplayAlerts=0;'
         '$d=$w.Documents.Open("%s",$false,$true);'
         '$p=$d.ComputeStatistics(2); $wd=$d.ComputeStatistics(0);'
         '$d.Close($false); $w.Quit();'
         'Write-Output "$p|$wd"' % rtf_path.replace('\\', '\\\\')],
        capture_output=True, text=True, timeout=300)
    out = (ps.stdout or '').strip()
    if '|' not in out:
        raise RuntimeError('Word COM 失败：%s / %s' % (out[:200], (ps.stderr or '')[:300]))
    a, b = out.split('|')
    return int(a), int(b)


def md5f(p):
    return hashlib.md5(io.open(p, 'rb').read()).hexdigest()


def main():
    os.makedirs(OUT_RTF, exist_ok=True)
    md = io.open(EN, encoding='utf-8', newline='').read()
    # 正文不含"文末 Appendix C 指针"之外的内容；参考文献一并计入（投稿件确实含它）
    print('=' * 104)
    print('真分页实测（Word 分页引擎；A4／单栏／双倍行距／12 pt／2.54 cm；表格 9 pt 单倍）')
    print('=' * 104)
    print('  输入：%s' % os.path.basename(EN))
    print('  输入 md5：英文稿 %s ；补充材料 %s' % (md5f(EN)[:12], md5f(SUP)[:12]))
    print()
    print('  %-10s %8s %10s %12s %10s' % ('图件高度', '页数', '词数', '含图页数', '与 35 页'))
    res = {}
    for cm in FIG_HEIGHTS_CM:
        rtf, placed = build_rtf(md, cm)
        tag = 'none' if cm is None else ('%.1fcm' % cm)
        rp = os.path.join(OUT_RTF, 'en_%s.rtf' % tag)
        io.open(rp, 'w', encoding='ascii', errors='replace', newline='\r\n').write(rtf)
        pages, words = word_pages(rp)
        res[tag] = dict(fig_cm=cm, pages=pages, words=words, figures_placed=placed,
                        rtf_md5=md5f(rp), rtf_bytes=os.path.getsize(rp))
        print('  %-10s %8d %10d %12s %10s' % (tag, pages, words, '—',
              '✓ 合规' if pages <= 35 else '✗ 超 %d 页' % (pages - 35)))
    print()
    base = res['none']['pages']
    for tag, d in res.items():
        if d['fig_cm']:
            print('  图件成本（%s）：%d 页 → %+d 页' % (tag, d['pages'], d['pages'] - base))
    out = dict(measured_at='2026-09-20', tool='Word COM ComputeStatistics(2)',
               inputs=dict(en=EN, en_md5=md5f(EN), sup=SUP, sup_md5=md5f(SUP)),
               layout=dict(page='A4', columns=1, spacing='double', body_pt=12, margin_cm=2.54,
                           table_pt=9, table_spacing='single'),
               variants=res)
    io.open(OUT_JSON, 'w', encoding='utf-8', newline='\n').write(json.dumps(out, ensure_ascii=False, indent=2))
    print('\n  已冻结：%s' % OUT_JSON)
    return res


if __name__ == '__main__':
    main()
