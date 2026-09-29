# -*- coding: utf-8 -*-
"""① 修 §8.1 披露里的同一术语（four classes → four knob sides；披露内容不变，只消歧）；
   ② remeasure：只刷新 measurement.json（不再碰 en_check.py —— finish_measure.py 会覆盖 [G]..[H] 段，
      把 G2 判据冲掉，故另立此脚本）。"""
import io, os, re, sys, json, hashlib
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, r'<WORKDIR>\PaperB\analysis\work')
ROOT = r'<WORKDIR>\PaperB'
EN = os.path.join(ROOT, 'PaperB_英文稿_PR_20260919.md')
MEAS = os.path.join(ROOT, 'measurement.json')

# ---- ① ----
en = io.open(EN, encoding='utf-8', newline='').read()
OLD = '**Statistical power for the spectrum is low** (four classes, ten units);'
NEW = '**Statistical power for the spectrum is low** (four knob sides, ten units);'
if OLD in en:
    io.open(EN, 'w', encoding='utf-8', newline='\n').write(en.replace(OLD, NEW, 1))
    en = en.replace(OLD, NEW, 1)
    print('① §8.1 披露已消歧：four classes → four knob sides（披露内容不变）')
else:
    print('① 形状不同，跳过（已修或措辞不同）')
assert 'four classes' not in en, '仍残留 four classes'
print('   复验：four classes 残留 %d 次' % en.count('four classes'))

# ---- ② 重测 ----
import measure_pages as mp
import measure_fix as mf
md = io.open(EN, encoding='utf-8', newline='').read()
os.makedirs(mp.OUT_RTF, exist_ok=True)
res, diag = {}, {}
for cm in [None, 6.0, 7.5, 9.0]:
    bl, _ = mf.build(md, cm)
    tag = 'none' if cm is None else ('%.1fcm' % cm)
    p = os.path.join(mp.OUT_RTF, 'fix_%s.rtf' % tag)
    mf.render(bl, p, 0)
    pages, words = mp.word_pages(p)
    res[tag] = dict(fig_cm=cm, pages=pages, words=words, rtf_md5=mp.md5f(p))
    r = io.open(p, encoding='ascii', errors='replace').read()
    diag = dict(trowd=r.count('\\trowd'), cells=r.count('\\cell'), figure_slots=r.count('[Figure'))
FILLER = ('Injected control paragraph for measurement validity. ' * 100).strip()
bl, _ = mf.build(md, 7.5, extra=FILLER)
pc = os.path.join(mp.OUT_RTF, 'control.rtf')
mf.render(bl, pc, 0)
cp, _ = mp.word_pages(pc)
ctl = dict(injected_words=len(FILLER.split()), pages_before=res['7.5cm']['pages'],
           pages_after=cp, responded=cp != res['7.5cm']['pages'])
rg = {'refs27': res['7.5cm']['pages']}
for n in (35, 45):
    extra = ' '.join('Author %d, A. A representative title of a counting paper. Journal %d(%d), %d–%d.'
                     % (i, i, i, i, i + 12) for i in range(n - 27))
    bl, _ = mf.build(md, 7.5, extra=extra)
    p = os.path.join(mp.OUT_RTF, 'refs%d.rtf' % n)
    mf.render(bl, p, 0)
    rg['refs%d' % n] = mp.word_pages(p)[0]
out = dict(measured_at='2026-09-20', tool='Word COM ComputeStatistics(2)',
           layout=dict(page='A4', columns=1, spacing='double', body_pt=12, margin_cm=2.54,
                       table_pt=9, table_spacing='single',
                       figure_placement='after the §3.9 paragraph'),
           inputs=dict(en=EN, en_md5=mp.md5f(EN), sup=mp.SUP, sup_md5=mp.md5f(mp.SUP)),
           variants=res, positive_control=ctl, reference_growth=rg, diagnostics=diag)
io.open(MEAS, 'w', encoding='utf-8', newline='\n').write(json.dumps(out, ensure_ascii=False, indent=2))
print('\n② 重测完成')
for k, v in res.items():
    print('   %-7s %d 页 %s' % (k, v['pages'], '✓' if v['pages'] <= 35 else '✗ 超上限'))
print('   阳性对照：%s（+%d 词 ⇒ %d→%d）' % (ctl['responded'], ctl['injected_words'],
                                          ctl['pages_before'], ctl['pages_after']))
print('   参考文献 27/35/45 条 = %s/%s/%s 页' % (rg['refs27'], rg['refs35'], rg['refs45']))
print('   渲染诊断：trowd=%d cell=%d 图位=%d' % (diag['trowd'], diag['cells'], diag['figure_slots']))
print('   英文稿 md5 %s' % mp.md5f(EN)[:12])
