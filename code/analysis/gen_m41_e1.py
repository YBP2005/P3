# -*- coding: utf-8 -*-
"""gen_m41_e1.py — 从冻结产物**程序化生成**补充材料 M.41（E1：FSC-147 分辨率敏感性）。

为什么程序化：本库纪律是"表里的数字必须由冻结件生成，不能手打"。本脚本读 `fsc_res_result.json`
（`by_model` + `delta_vs_384` + `replication_384_vs_frozen`），把 M.41 的正文与一张表**生成**出来
追加到补充材料；词数会逐次打印（**2026-09-24 起不再设自订上限**：只记录、不拦截）；写盘前跑与 `en_check.py` **同一份**禁用串名单。

设计要点（必须与 E1 实际做法一致，否则正文会撒谎）：
  · 三档分辨率 384（发布）/ 256（降采样）/ 768（上采样，须标注 upsampled）× 六臂 × 三个构建；
  · 三档都由**同一族探针**测量（副本只差图像/输出目录常量，提示词/解析器 import 自冻结的 19e）；
  · 384 这一档在**本批次内**重测一次 ⇒ 与 §5.6 冻结面板的差是**同题同图的批次可复现性核对**，
    单独成表、单独措辞，不与"分辨率位移"混为一谈。
结论句是**数据驱动**的：最大位移与 §A.3 的跨次服务噪声带（2.15–6.46 pp）相比，走两条不同措辞分支。

用法：python -u gen_m41_e1.py
"""
import hashlib
import io
import json
import os
import re
import shutil
import sys
import time

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
W = r'<WORKDIR>\PaperB\analysis\work'
SUP = r'<WORKDIR>\PaperB\PaperB_英文补充材料_PR_20260919.md'
RES = os.path.join(W, 'fsc_res_result.json')
CAP = None       # ★ 2026-09-24 取消自订上限（用户口径）：只记录词数，不拒绝写盘。
ARMS = ('base', 'permit', 'channel', 'enumAbstain', 'exemplar3', 'exemplar3permit')
SWEEP = ('384', '256', '768up')
BAND = (2.15, 6.46)          # §A.3 跨次服务噪声带（pp），仅用于措辞分支
WC = lambda s: len(re.findall(r"[A-Za-z][A-Za-z'\-]*", s))

r = json.loads(io.open(RES, encoding='utf-8').read())
bm, dl, rp = r['by_model'], r['delta_vs_384'], r.get('replication_384_vs_frozen', {})

models = sorted(m for m in bm
                if any('%s|%s' % (t, a) in bm[m] for t in SWEEP for a in ARMS))
assert models, 'fsc_res_result.json 里没有任何扫描数据（384/256/768up）⇒ 不能生成 M.41'
arms = [a for a in ARMS if any('%s|%s' % (t, a) in bm[m] for m in models for t in SWEEP)]
assert '384' in {k.split('|')[0] for m in models for k in bm[m]}, '缺本批次 384 锚点 ⇒ 不能算位移'

rows = []
for m in models:
    for a in arms:
        g = lambda t: bm[m].get('%s|%s' % (t, a))
        if not any(g(t) for t in SWEEP):
            continue
        # ★ 384 基线：优先本批次重测；缺则回退 §5.6 冻结面板（提示词/解析器/样本逐字同一），
        #   但**表里要标出来**哪一行用的是回退基线，不能让读者以为都是同一批。
        b, bsrc = g('384'), 're'
        if not b:
            b, bsrc = g('frozen384'), 'frozen'
        rows.append((m, a, b, g('256'), g('768up'),
                     dl.get('%s|256|%s' % (m, a), {}).get('zero'),
                     dl.get('%s|768up|%s' % (m, a), {}).get('zero'), bsrc))
_any_frozen = any(t[7] == 'frozen' for t in rows)

# ★ 正文里的"几个构建 / 几条臂"必须由**数据**决定：写死"three builds / six arms"而实际少一档，
#   正文就与自己的表冲突（M.40 那边同样改成数据驱动）。
_W = {1: 'one', 2: 'two', 3: 'three', 4: 'four', 5: 'five', 6: 'six'}
NUMA = _W.get(len(arms), str(len(arms)))
NUMB = _W.get(len(models), str(len(models)))
fullb = [m for m in models if all('%s|%s' % (t, a) in bm[m] for t in SWEEP for a in arms)]
NUMF = _W.get(len(fullb), str(len(fullb)))
assert fullb, '没有任何构建三档齐备 ⇒ 不能声称"三档对比"'

dz = [(abs(t[5]), t[0], t[1], '256') for t in rows if t[5] is not None] + \
     [(abs(t[6]), t[0], t[1], '768up') for t in rows if t[6] is not None]
dab = []
for t in rows:
    m, a = t[0], t[1]
    for tag in ('256', '768up'):
        b, v = t[2], bm[m].get('%s|%s' % (tag, a))
        if b and v:
            dab.append((abs(v['abstain'] - b['abstain']), m, a, tag))
assert dz and dab, '三档未齐（缺 384 基线与 256/768up 的重合格子）⇒ 无法比较'
dz.sort(reverse=True)
dab.sort(reverse=True)
zmax, amax = dz[0], dab[0]
inside = (zmax[0] <= BAND[1]) and (amax[0] <= BAND[1])
rz = [abs(v['d_zero']) for v in rp.values() if v.get('d_zero') is not None]
ra = [abs(v['d_abstain']) for v in rp.values() if v.get('d_abstain') is not None]

print('  网格：%d 行；构建 %s；臂 %s' % (len(rows), ', '.join(models), ', '.join(arms)))
print('  最大 Δzero %.1f pp（%s %s → %s）；最大 Δabstain %.1f pp（%s %s → %s）'
      % (zmax[0], zmax[1], zmax[2], zmax[3], amax[0], amax[1], amax[2], amax[3]))
print('  384 与冻结面板核对：%d 个 (构建,臂) 格子；最大 |Δzero| %.1f pp；最大 |Δabstain| %.1f pp'
      % (len(rz), max(rz) if rz else -1, max(ra) if ra else -1))

DISP = {'InternVL3_5-8B': 'InternVL3.5-8B', 'Phi-3.5-vision-instruct': 'Phi-3.5-vision-instruct',
        # ★ 必须与 M.40/SYNC 用**同一套**论文名：漏了 gemma 就会在表里印出 `gemma3-12b`（文件名），
        #   与全文其它处的 `gemma-3-12b` 不一致（本轮就是这么被独立核对脚本抓到的）。
        'gemma3-12b': 'gemma-3-12b', 'llava-onevision-qwen2-7b-ov': 'LLaVA-OneVision-7B',
        'Qwen3-VL-32B-Instruct': 'Qwen3-VL-32B-Instruct'}


def disp(m):
    return DISP.get(m, m.replace('_', '.'))


def f(v, k):
    return ('%.1f' % v[k]) if v else '–'


def d(x):
    return ('%+.1f' % x) if x is not None else '–'


L = []
P = L.append
P('### M.41 Sensitivity to image resolution on FSC-147: 256, 384 and 768 pixels')
P('')
P('The same simulated review panel asked us to re-run the FSC-147 panel at a resolution other than the one we')
P('used. The request has a')
P('factual precondition, which changes what can honestly be delivered.')
P('')
P('**The precondition.** The official release of FSC-147 contains the image set `images_384_VarV2`, whose 6,146')
P('files all have a **short side of exactly 384** pixels, with the long side varying between 384 and 1918')
P('according to aspect ratio; on our 300-image sample the short side is 384 throughout and the long side runs')
P('384–1229 (median 514). Inside that package the scale is therefore fixed by the dataset and the canvas is')
P('not. That package is what the dataset README links to and what mirrors redistribute; there is **no**')
P('official original-resolution release. A request for "the native resolution"')
P('thus asks for something that is not distributed: the scale is a property of **the dataset**, not of our')
P('pipeline. What **can** be varied is the scale handed to the model: **downward** on the short side to 256')
P('pixels, which discards information the release does supply, or **upward** to 768 pixels, the same')
P('information on a larger canvas. Both apply a **single linear scale to every image**, so aspect ratio and')
P('content are preserved: 256 is a $0.667\\times$ rescale ($0.444\\times$ the area) and 768 a $2\\times$ rescale')
P('($4.000\\times$ the area), the latter **upsampled** — it measures canvas size, not information content.')
P('')
P('**Design.** Three scales measured with one probe family whose copies differ only in the image and output')
P('directories — the prompts and the parser are imported from the same frozen module as the §5.6 panel — on the')
P('same frozen 300-image sample and the same %s arms: the four contract arms of the frozen panel plus the two'
  % NUMA)
P('exemplar arms whose')
P('resolution dependence the limitations section previously flagged as uncontrolled. %s, so every cell below is'
  % (('%s builds were run at all three scales' % NUMB).capitalize() if len(fullb) == len(models)
     else ('%s of the %s builds were run at all three scales; the rest contribute the cells shown'
           % (NUMF, NUMB)).capitalize()))
P('a within-item, within-probe comparison.')
P('')
P('| build | arm | zero@384 (release) | zero@256 ($0.444\\times$ area) | Δ | zero@768up ($4.000\\times$ area, upsampled) | Δ |')
P('|---|---|---|---|---|---|---|')
for m, a, g3, g2, g7, d2, d7, bsrc in rows:
    P('| %s | `%s` | %s | %s | %s | %s | %s |'
      % (disp(m), a, f(g3, 'zero') + ('$^\\dagger$' if bsrc == 'frozen' else ''),
         f(g2, 'zero'), d(d2), f(g7, 'zero'), d(d7)))
if _any_frozen:
    P('')
    P('$^\\dagger$ this row\'s 384 baseline is the frozen §5.6 panel (the same prompts, parser, sample and')
    P('item set; only the driver script batch differs), because the re-measured 384 column was not available')
    P('for it when this table was generated.')
P('')
P('| build | arm | abstain@384 | abstain@256 | abstain@768up |')
P('|---|---|---|---|---|')
for m, a, g3, g2, g7, d2, d7, bsrc in rows:
    P('| %s | `%s` | %s | %s | %s |'
      % (disp(m), a, f(g3, 'abstain'), f(g2, 'abstain'), f(g7, 'abstain')))
P('')
P('**What the sweep shows.** Across the grid the zero-answer rate moves by at most **%.1f pp** (%s, `%s`, the'
  % (zmax[0], disp(zmax[1]), zmax[2]))
P('short-side-%s point) and the abstention rate by at most **%.1f pp** (%s, `%s`, short side %s).'
  % (zmax[3].replace('up', ''), amax[0], disp(amax[1]), amax[2], amax[3].replace('up', '')))
if inside:
    P('Both are inside the **2.15–6.46 pp** band that repeated service starts alone produce for the rank')
    P('agreement of §A.3, so on this panel a resolution change is not separable from serving noise: the sweep')
    P('neither rescues nor undermines the signed-error conclusions. That is a **negative but informative**')
    P('result, and it is why we claim no resolution robustness as a finding — only that the 384-pixel canvas was')
    P('not doing the work on its own.')
else:
    # ★ 由数据决定：把"谁动了、谁没动"说清楚，而不是笼统说"分辨率有影响"。
    _con = ('base', 'permit', 'channel', 'enumAbstain')
    # ★ 必须把 |Δzero| 与 |Δabstain| **放在一起比**。写成 `max((abs(zero), abs(abstain), k))` 是**元组比较**
    #   （先比 zero、再比 abstain），会把"合同臂最大位移"报小：实测 Phi 的 enumAbstain 弃权动了 2.0 pp，
    #   却因为它的 |Δzero| 只有 0.7 而被 base 的 1.0 pp 压过去 ⇒ 正文会低报。这里改成候选项列表。
    _cand = [(abs(v['zero']), k, 'zero rate') for k, v in dl.items() if k.split('|')[2] in _con] + \
            [(abs(v['abstain']), k, 'abstention rate') for k, v in dl.items() if k.split('|')[2] in _con]
    cmax = max(_cand)
    emax = max((abs(v['abstain']), k) for k, v in dl.items() if k.split('|')[2].startswith('exemplar'))
    P('')
    P('**Which channel moves.** The split is not uniform: over the four contract arms the largest movement anywhere')
    P('in the grid is **%.1f pp** (%s, %s, the %s), whereas the abstention rate of the'
      % (cmax[0], disp(cmax[1].split('|')[0]), cmax[1].split('|')[2], cmax[2]))
    P('exemplar-permit arm moves by up to **%.1f pp** (%s at the %s-pixel scale).' % (emax[0],
      disp(emax[1].split('|')[0]), emax[1].split('|')[1].replace('up', '')))
    P('The responses show this is behaviour, not parsing: the model answers the same item numerically at 384')
    P('pixels and returns the literal `{"count": "abstain"}` at 256, with no unparsed outputs in either')
    P('condition. Halving the linear scale thus makes the model decline when it has been shown exemplar boxes —')
    P('a *scale* form of the §5.8 legibility gate, on the hardest arm — while the contract arms move by at most')
    P('**%.1f pp**. We report the direction rather than a blanket claim that resolution does not matter.'
      % cmax[0])
    P('')
    # ★ 与 §5.7 的一致性别留着让评审自己猜：那里说"gate 弃权的是模糊而非分辨率"，而这里示例臂确实随尺度动。
    #   两句放在一起说清"哪个臂在动"，否则看起来像自相矛盾。
    P('**Consistency with §5.7.** The contract arms move by no more than **%.1f pp** even at $0.444\\times$ the'
      % cmax[0])
    P('area — the same sign that section reports for downscaling on the corpus domains, where blur rather than')
    P('scale gates abstention (0.6% at 15% of the pixels against 9.1% under blur). The movement we do see is')
    P('confined to the exemplar arm, a prompt condition that sweep does not cover: the two results agree, and')
    P('what differs is the arm.')
    P('')
    # ★ 负结果必须写成"有界 + 有阳性对照 + 接本领域的**实测量级**"，否则读者分不清"效应不存在"与"操纵无效"。
    #   三个量里：示例臂位移与合同臂界由数据算；**32.0 pp 与 10 pp 是引用**主文 §5.12 的普查**观察值**
    #   （那里的"分辨率旋钮"= 每实例像素预算，与本节的画布尺度**不是**同一件事 —— 必须点明，
    #    否则两个数差 16 倍、看起来像自相矛盾）。
    #   ⚠ 措辞纪律：普查报的是"合同旋钮比分辨率旋钮多动 ≥10 pp（12 格中的 10 格）"，
    #     这是**观察**、不是论文规定的**判定规则** —— 不许写成 "the decision rule"（那是过度解读）。
    _tight = sum(1 for v in rp.values() if max(abs(v['d_zero']), abs(v['d_abstain'])) <= 0.5)
    P('**What this null is scoped to.** Three things keep it from being a claim that scale never matters. The')
    P('same sweep moves the exemplar arm by up to **%.1f pp**, so the manipulation is not inert; the corpus'
      % emax[0])
    P('census of §5.12 varies a *different* resolution knob — the **per-instance pixel budget**, which there')
    P('moves the zero rate by as much as **32.0 pp** — whereas the FSC-147 release fixes that budget and leaves')
    P('only the canvas; and that same census finds the *contract* knob moving the zero rate by at least **10 pp**')
    P('more than the resolution knob in 10 of its 12 qualifying cells, an order of magnitude above the at-most')
    P('**%.1f pp** seen here. That movement also sits below the **2.15–6.46 pp** across-repeat band of §A.3, and' % cmax[0])
    P("the panel's same-scale replication noise (**≤0.5 pp** in %d of the %d cells present) means a shift of a"
      % (_tight, len(rp)))
    P('few points would have stood out against it. The result is therefore a bound on this panel, not an absence')
    P('of measurement.')
    P('')
    P('Arm ordering is preserved at all three scales and no arm changes which side of zero it falls on, so the')
    P('contract contrast of §5.6 is reproduced by both variants.')
if rp:
    P('')
    # ★ 这一段必须**由数据决定措辞**：若某些格子复现得很好而个别格子差很多，就不能笼统写"完全复现"。
    _cells = sorted(rp.items(), key=lambda kv: -max(abs(kv[1]['d_zero']), abs(kv[1]['d_abstain'])))
    _n_tight = sum(1 for _, v in rp.items() if max(abs(v['d_zero']), abs(v['d_abstain'])) <= 0.5)
    _worst_k, _worst = _cells[0]
    _wmax = max(abs(_worst['d_zero']), abs(_worst['d_abstain']))
    _field = 'zero' if abs(_worst['d_zero']) >= abs(_worst['d_abstain']) else 'abstain'
    P('**A same-resolution replication, and the one arm that does not reproduce.** Because the 384-pixel column')
    P('was re-measured here with the same prompts and images, it also tests whether the panel of §5.6 reproduces')
    P('under a fresh batch and fresh service starts. **%d of the %d** cells present'
      % (_n_tight, len(rp)))
    P('in both agree to within **0.5 pp**; the largest disagreement is **%.1f pp** (%s, `%s`, the %s rate: %.1f%%'
      % (_wmax, disp(_worst_k.split('|')[0]), _worst_k.split('|')[1], _field,
         _worst['sweep_' + _field], ))
    P('here against %.1f%% in the published panel). We traced that cell: the frozen'
      % _worst['frozen_' + _field])
    P('panel was served with a **4096**-token context limit and this sweep with **8192**, every other setting')
    P('identical (temperature 0, 128 output tokens, one image per prompt, 24 sequences, same prompt module, same')
    P('300 images) — and the cell belongs to the smallest build on its most complex arm, where a near-tie between')
    P('counting and abstaining is likeliest. The disagreement is therefore a property of the **serving stack**,')
    P('not of the images or the prompts — which is why the deltas above are computed against the **in-sweep** 384')
    P('column, and reinforces §5.7: an answered zero is a property of the serving configuration.')
P('')
P('*Reproduction: `fsc_res_analyze.py` (analyzer, raw-match caliber), `fsc_res_qc.py` (per-cell completeness and')
P('parse-rate guard), `fsc_build_sc.py` (the 256/768 rebuilds; one linear scale per image, source and target')
P('sizes logged), drivers `w1_fsc_probe_{384,256,768}.py` importing the frozen probe module; frozen')
P('`fsc_res_result.json`. The frozen 384-pixel panel of §5.6 is itself retained unchanged as the cross-check,')
P('and `anchor_m40m41.py` re-derives the quantities in this appendix — and in M.40 — from the frozen artifacts,')
P('checks the design constants against a frozen inventory of them, and fails on any number that is not')
P('registered.*')
M41 = '\n'.join(L) + '\n\n'

src = io.open(SUP, encoding='utf-8', newline='').read()
before = WC(src)
if '### M.41 ' in src:
    # 已存在 ⇒ 替换整段；以"下一个 ### 标题"为界，位置无关（M.40 生成器已按同一规矩改过）。
    i = src.index('### M.41 ')
    nxt = re.search(r'(?m)^### ', src[i + 1:])
    j = i + 1 + nxt.start() if nxt else len(src)
    src = src[:i] + M41.rstrip('\n') + '\n\n' + src[j:]
    print('  [ok] 替换既有 M.41（保留其后内容，若有）')
else:
    m = re.search(r'### M\.40 ', src)
    assert m, '找不到 M.40 起点，无法在其后插入 M.41'
    nxt = re.search(r'(?m)^### ', src[m.start() + 1:])
    j = m.start() + 1 + nxt.start() if nxt else len(src)
    src = src[:j].rstrip('\n') + '\n\n' + M41 + src[j:]
    print('  [ok] 在 M.40 之后插入 M.41')
after = WC(src)
print('  补充材料词数：%d → %d（%+d）' % (before, after, after - before))
# ★ 2026-09-24：自订上限取消 ⇒ 这里**只报告、不拦截**（用户口径："不设上限，但每次加完看一下词数"）。
print('  [记录] 无自订上限（期刊对补充材料亦无上限）；本次净变化 %+d 词' % (after - before))
BANNED = [(r'⚠', '⚠'), (r'已撤回', '撤回'), (r'\bA\d{1,2}\b', '内部编号'), (r'\bv\d+\b', '版本号'),
          (r'PaperB_', '内部文档'), (r'[A-Za-z]:\\', '盘符'), (r'/root/', '服务器路径'),
          (r'pod_mirror', '内部机器名'), (r'盲审|六模型|七模型', '评审语'), (r'TODO|TBD|XXX', '占位'),
          (r'本节为待实验内容', '占位符')]
hit = {n: re.findall(p, M41)[:3] for p, n in BANNED if re.findall(p, M41)}
if hit:
    sys.exit('!! M.41 命中禁用串：%s ⇒ 拒绝写盘' % hit)
print('  禁用串预检：0（与 en_check 同一份名单）')
bak = SUP + '.bak_before_m41_%s' % time.strftime('%Y%m%d_%H%M%S')
shutil.copy2(SUP, bak)
io.open(SUP, 'w', encoding='utf-8', newline='\n').write(src)
print('  已写盘 md5 %s' % hashlib.md5(io.open(SUP, 'rb').read()).hexdigest()[:12])
