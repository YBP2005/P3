# -*- coding: utf-8 -*-
"""对 PR 官方条款逐项体检本稿（只读）。
条款出处：E:\\workplace\\PR网页.txt（作者复制，875 行；含期刊专属 Writing and formatting 节）。
"""
import io
import os
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')
MS = r'<WORKDIR>\PaperB\PaperB_英文稿_PR_20260919.md'
SUP = r'<WORKDIR>\PaperB\PaperB_英文补充材料_PR_20260919.md'
HL = r'<WORKDIR>\PaperB\review_pkg_20260919\07_Highlights.md'
t = io.open(MS, encoding='utf-8').read()
sup = io.open(SUP, encoding='utf-8').read()
W = lambda s: len(re.findall(r"[A-Za-z][A-Za-z'\-]*", s))

print('=' * 92)
print('① 摘要 ≤250 词（条款 L310/L583）')
ab = t.split('## Abstract')[1].split('## 1. Introduction')[0]
ab = ab.split('**Keywords:**')[0]   # Keywords 不属摘要
print('   实测 %d 词  -> %s' % (W(ab), 'OK' if W(ab) <= 250 else '**超 %d 词**' % (W(ab) - 250)))

print('② 关键词 1–7 个（条款 L329/L583）')
kw = re.search(r'(?im)^(?:##\s*)?(?:\*\*)?keywords?(?:\*\*)?\s*[::]', t)
print('   %s' % ('找到: ' + t[kw.start():kw.start() + 90].replace('\n', ' ') if kw else '**未找到关键词段**'))

print('③ Highlights：必交、3–5 条、每条 ≤85 字符、文件名含 Highlights（条款 L334–L340/L597–L600）')
if os.path.exists(HL):
    h = io.open(HL, encoding='utf-8').read()
    # ★ 2026-09-22 修正：旧正则 `^\s*[-*•]|^\s*\d+[.)]` 会把**以 `**粗体**` 开头的说明行**当成第 6 条
    #   项目符号（"**为什么改了这一版**：…" 以 `*` 开头即命中），于是把 5 条 Highlights 报成 6 条。
    #   改为：项目符号后**必须跟空白**，且排除以 `**` 开头的行（那是粗体段落，不是列表项）。
    bullets = [l.strip() for l in h.split('\n')
               if re.match(r'^\s*(?:[-*•]\s+|\d+[.)]\s+)', l) and not l.strip().startswith('**')]
    over = [b for b in bullets if len(re.sub(r'^\s*[-*•\d.)]+\s*', '', b)) > 85]
    print('   文件存在；%d 条；超 85 字符的 %d 条' % (len(bullets), len(over)))
    for b in bullets[:6]:
        s = re.sub(r'^\s*[-*•\d.)]+\s*', '', b)
        print('      (%3d 字符) %s' % (len(s), s[:80]))
    if over:
        for b in over:
            print('      **超限**: %s' % b[:100])
else:
    print('   **缺文件** %s' % HL)

print('④ 标题建议 ≤10–15 词（条款 L581）')
title = t.split('\n')[0].lstrip('# ').strip()
print('   %d 词: %s' % (W(title), title[:110]))

print('⑤ 是否有 Conclusions 节（条款 L585–L586）')
heads = [l.strip() for l in t.split('\n') if l.strip().startswith('## ') or l.strip().startswith('### ')]
print('   顶层节: %s' % [h.lstrip('# ')[:28] for h in heads if h.startswith('## ')])
has_concl = any('conclusion' in h.lower() for h in heads)
print('   含 Conclusions 节: %s' % ('是' if has_concl else '**否**'))

print('⑥ 参考文献条数应在 35–55（条款 L721）')
nref = len(re.findall(r'(?m)^\d+\. ', t.split('## References')[1]))
print('   实测 %d 条 -> %s' % (nref, 'OK' if 35 <= nref <= 55 else '**越界**'))

print('⑦ 参考文献必须**按正文首次出现顺序**编号（条款 L693）')
body, refs = t.split('## References')[0], t.split('## References')[1]
first = {}
for m in re.finditer(r'\[(\d+(?:\s*,\s*\d+)*)\]', body):
    for n in re.findall(r'\d+', m.group(1)):
        first.setdefault(int(n), m.start())
order = [n for n, _ in sorted(first.items(), key=lambda kv: kv[1])]
print('   正文出现的编号顺序（前 20）: %s' % order[:20])
print('   编号总数 %d；顺序是否单调递增: %s' % (len(order), '是' if order == sorted(order) else '**否（列表需重排）**'))
missing = sorted(set(range(1, nref + 1)) - set(order))
print('   列表里有、正文未引: %s' % (missing or '无'))

print('⑧ 英文一致（条款 L863：美式或英式，不可混用）')
# ⚠ 2026-09-22 修正：旧正则 `\b\w+(?:ize|…)\w*\b` 会命中原生词（size/sizes）
#   与**参考文献里的原题名**（Localization / Generalized / Quantization），
#   于是把一份通篇英式拼写的稿子误报成"混用"。现改为：
#   ① 只查**逐对**变体词；② 剔除 References 段（题名须照录，不得改写）。
_body_ref = body.split('## References')[0]
PAIRS = [('behaviour', 'behavior'), ('modelling', 'modeling'), ('labelled', 'labeled'),
         ('analyse', 'analyze'), ('colour', 'color'), ('quantise', 'quantize'),
         ('localise', 'localize'), ('generalise', 'generalize'), ('normalise', 'normalize'),
         ('centre', 'center'), ('favour', 'favor')]
us_hits, uk_hits = [], []
for uk, us in PAIRS:
    n_us = len(re.findall(r'\b%s\w*\b' % us, _body_ref, re.I))
    n_uk = len(re.findall(r'\b%s\w*\b' % uk, _body_ref, re.I))
    if n_us:
        us_hits.append('%s ×%d（如 %s）' % (us, n_us, re.findall(r'\b%s\w*\b' % us, _body_ref, re.I)[:3]))
    if n_uk:
        uk_hits.append('%s ×%d' % (uk, n_uk))
print('   正文（不含 References）英式形 %d 种：%s' % (len(uk_hits), '、'.join(uk_hits) or '无'))
print('   正文美式形 %d 种：%s' % (len(us_hits), '、'.join(us_hits) or '无'))
print('   -> %s' % ('ok（未混用）' if not us_hits else '**混用，需统一**'))
_arts = re.findall(r'\b(Localization|Generalized|Quantization|Optimization)\b', t)
print('   （References 中的原题名拼写：%s —— 照录，不改）' % (sorted(set(_arts)) or '无'))

print('⑨ 是否有 Data availability / 数据声明（条款 L524–L527 Option C 必交）')
d = [h for h in heads if re.search(r'data (availability|statement)|availability of data', h, re.I)]
print('   %s' % (d or '**未找到数据可用性段**'))

print('⑩ 是否已有 CRediT / 生成式 AI 声明 / 致谢（条款 L632/L140–L166）')
for key, pat in (('CRediT', r'CRediT'), ('生成式 AI 声明', r'generative AI|AI-assisted technologies'),
                 ('Acknowledg', r'^#+ *Acknowledg')):
    print('   %-14s %s' % (key, '有' if re.search(pat, t, re.I | re.M) else '**无**'))
