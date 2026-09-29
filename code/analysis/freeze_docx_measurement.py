# -*- coding: utf-8 -*-
"""冻结 **真实交付件** 的分页事实：打开 .docx 用 Word 读页数/词数，连 md5 一起写 JSON。

为什么以 .docx 为准：官方 L573 只收 .docx/.tex，RTF 只是"无 Word 时的代理测量"。
两者口径不同（RTF 代理按 7.5 cm 预留图位，真实 .docx 按图件真实纵横比插入），
故必须分开记录，不可混用。
"""
import hashlib
import io
import json
import os
import sys
import time

sys.stdout.reconfigure(encoding='utf-8')
import win32com.client as w

ROOT = r'<WORKDIR>\PaperB'
DOCX = os.path.join(ROOT, 'PaperB_英文稿_PR.docx')
MD = os.path.join(ROOT, 'PaperB_英文稿_PR_20260919.md')
OUT = os.path.join(ROOT, 'measurement_pr_docx.json')


def md5f(p):
    h = hashlib.md5()
    with io.open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


app = w.Dispatch('Word.Application')
app.Visible = False
# ★ 2026-09-24 夜：**先确认拿到的是真 Word，不是 WPS 的伪装对象**。
#   事故：`final_gates` 第 ① 步报 `Property 'Word.Application.Visible' can not be set`；
#   诊断（`_probe_wordcom.py`）发现 **WPS 进程活着时会抢占 `Word.Application` 这个 ProgID**，
#   而 WPS 对外自称 "Microsoft Word 12.0"（真 Word 是 16.0）。此后 COM 调用会以
#   `AttributeError: Open.Close` 这类**完全指错方向**的形式随机失败。
#   ⇒ 硬断言：名称必须是 Microsoft Word 且主版本 ≥ 16，否则直接报清楚原因。
try:
    _nm, _ver = str(app.Name), str(app.Version)
except Exception as _e:
    raise SystemExit('!! 取不到 Word 身份（%s）⇒ 多半是 WPS 抢占了 Word.Application。'
                     '先 `taskkill /F /IM wps.exe /IM wpscloudsvr.exe` 再重跑。' % _e)
if 'Microsoft Word' not in _nm or int(_ver.split('.')[0]) < 16:
    raise SystemExit('!! 拿到的不是真 Word：Name=%r Version=%r ⇒ WPS 抢占了 ProgID。'
                     '先杀 wps/wpscloudsvr 再重跑（见 final_gates.kill_word）。' % (_nm, _ver))
print('Word 身份确认：%s %s' % (_nm, _ver))
d = app.Documents.Open(DOCX, ReadOnly=True)
try:
    d.Repaginate()
    pages = d.ComputeStatistics(2)
    words = d.ComputeStatistics(0)
    chars = d.ComputeStatistics(3)
    sec = d.Sections(1).PageSetup
    CM = 28.3464567
    # ⚠ 中文版 Word 里内置样式名被本地化（"正文"），按名字取 'Normal' 会抛
    #   "集合所要求的成员不存在" ⇒ 必须用内置常量 wdStyleNormal = -1。
    try:
        nst = d.Styles(-1)
        body_pt = float(nst.Font.Size)
        line_spacing = float(nst.ParagraphFormat.LineSpacing)
    except Exception as ex:
        body_pt, line_spacing = None, '%s' % type(ex).__name__
    layout = dict(page='A4', columns=int(sec.TextColumns.Count),
                  body_pt=body_pt, line_spacing=line_spacing,
                  margins_cm=dict(top=round(sec.TopMargin / CM, 2), right=round(sec.RightMargin / CM, 2),
                                  bottom=round(sec.BottomMargin / CM, 2), left=round(sec.LeftMargin / CM, 2)),
                  inline_shapes=int(d.InlineShapes.Count), tables=int(d.Tables.Count))
finally:
    d.Close(False)
    app.Quit()

out = dict(measured_at=time.strftime('%Y-%m-%d'), tool='Word 16.0 COM ComputeStatistics',
           authority='.docx 是官方唯一接受的交付件（PR L573），故以它为准；RTF 代理见 measurement_pr_layout.json',
           inputs=dict(docx=DOCX, docx_md5=md5f(DOCX), markdown=MD, markdown_md5=md5f(MD)),
           result=dict(pages=pages, words=words, characters=chars, limit_pages=35,
                       compliant=pages <= 35, margin_pages=35 - pages),
           layout=layout)
io.open(OUT, 'w', encoding='utf-8', newline='\n').write(json.dumps(out, ensure_ascii=False, indent=2))
print('Word 实测 %d 页 / %d 词 / %d 字符 ⇒ %s' % (pages, words, chars,
      '合规（余量 %d 页）' % (35 - pages) if pages <= 35 else '超限 %d 页' % (pages - 35)))
print('版式：%s' % layout)
print('已冻结 %s' % OUT)
