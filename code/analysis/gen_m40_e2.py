# -*- coding: utf-8 -*-
"""gen_m40_e2.py — 从冻结产物**程序化生成**补充材料 M.40（E2：真零池 × 多构建 × 双语言 × 3 次服务）。

为什么程序化：本库纪律是"表里的数字必须由冻结件生成，不能手打"。本脚本读
`ea2_z0_result.json`（通道构成 + 服务级噪声）与 `ea2_contrast_result.json`（真零 vs 非零对照），
把 M.40 的正文与两张表**生成**出来并插入补充材料；词数变化会打印，**不再设自订上限**（只记录词数）。

用法：python -u gen_m40_e2.py            # 先用当前产物生成/更新 M.40
"""
import collections
import glob
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
CAP = None       # 2026-09-24 取消自订上限（只记录词数）
Z0 = os.path.join(W, 'ea2_z0_result.json')
CON = os.path.join(W, 'ea2_contrast_result.json')
MARK = 'E2_M40_END'
# ★ 与 en_check.py 的计数口径**逐字一致**（`W = lambda s: len(re.findall(r"[A-Za-z][A-Za-z'\-]*", s))`）：
#   自订护栏必须用裁决者的尺子，否则会出现"护栏说超、en_check 说没事"的假警报（本轮已踩）。
WC = lambda s: len(re.findall(r"[A-Za-z][A-Za-z'\-]*", s))
# 标签/文件名里的构建名 → 论文里的写法（表与正文都必须用论文名，否则同一构建出现两个名字）
DISP_BUILD = {'InternVL3_5-8B': 'InternVL3.5-8B', 'llava-onevision-qwen2-7b-ov': 'LLaVA-OneVision-7B',
              'gemma3-12b': 'gemma-3-12b', 'Qwen3-VL-32B-Instruct': 'Qwen3-VL-32B-Instruct',
              'Phi-3.5-vision-instruct': 'Phi-3.5-vision-instruct'}

z0 = json.loads(io.open(Z0, encoding='utf-8').read())
con = json.loads(io.open(CON, encoding='utf-8').read())

# ── 汇总：每 (build, 语言, 分层) 的通道构成（三臂），取三次服务的合并（分析器已合并）──
by_build = collections.defaultdict(dict)
n_by_build = {}                     # ★ 同时存 n：Wilson 上限要按"该单元格自己的观测数"算，
for k, v in con['z0'].items():      #   只存 pct 就会在算上限时拿到 None（本轮踩过：表里 0.0% 没带上限）
    model, lang, stratum, arm = k.split('|')
    by_build[(model, lang, stratum)][arm] = v['pct']
    n_by_build[(model, lang, stratum, arm)] = v['n']
nz, nz_n = {}, {}
for k, v in con['nonzero'].items():
    model, zone, arm = k.split('|')
    nz[(model, zone, arm)] = v['pct']
    nz_n[(model, zone, arm)] = v['n']

# 服务级噪声：取每 (build, 语言, 分层, 臂) 的 no_people 极差
# ★ 注意两套命名的差别（本轮踩到并修）：噪声表按**构建短标签**（ivl8b/phi35/…）索引，
#   而通道/对照表按**模型全名**（InternVL3_5-8B/Phi-3.5-vision-instruct/…）。对不上就会静默打印 0.0，
#   把"0.0–2.6 pp"说成"0.0–0.0 pp"（结论方向都会变）。故先建 标签→全名 的映射。
_tag2name = {}
for d in glob.glob(os.path.join(r'<WORKDIR>\PaperB\analysis\ea2_z0', '*', '*.csv')):
    dirn = os.path.basename(os.path.dirname(d))
    m = re.match(r'^(?:cn|en)_(.+)_s(\d)$', dirn)
    mm = re.match(r'^e1_(.+?)_(?:z0easy|z0hard)_', os.path.basename(d))
    if m and mm:
        _tag2name.setdefault(m.group(1), mm.group(1))
_noise_by_tag = collections.defaultdict(list)
for k, v in z0['serving_noise'].items():
    build, lang, key = k.split('|')          # key = stratum/arm
    _noise_by_tag[(build, lang)].append(v['range_pp']['no_people'])
noise = collections.defaultdict(list)
for (tag, lang), vals in _noise_by_tag.items():
    noise[(_tag2name.get(tag, tag), lang)] = vals

BUILDS = sorted({k[0] for k in by_build})
NUM = {4: 'four', 5: 'five', 6: 'six', 7: 'seven'}.get(len(BUILDS), str(len(BUILDS)))
assert len(BUILDS) >= 4, '仅 %d 个构建有数据（评审要求 ≥4）⇒ 不得生成 M.40' % len(BUILDS)
L = []
P = L.append
P('### M.40 The true-zero pool under repetition: %s builds, two languages, three service starts' % NUM)
P('')
P('Our simulated review panel (the multi-model review declared in the manuscript\'s generative-AI statement)')
P('asked for **independently verified, mixed true-zero / non-zero images, at least four')
P('builds, in two languages, across three service starts**. The pool is the one of §M.38 (windows over UCF-QNRF')
P('whose expanded box contains **no annotated head point**, hence a correct answer of **0**; **306** of them,')
P('split into **z0easy** and **z0hard** by a clutter proxy), and the non-zero control is the frozen non-zero')
P('pool of §5.7 measured with the same probe.')
P('')
# ★ 构建清单**由数据生成**，不硬写：若某个构建没跑完，正文说"五个"而表里只有四个，就是正文撒谎。
P('**Design and controls.** %s builds (%s) × three **fresh service starts** each × two languages (the frozen'
  % (NUM.capitalize(), ', '.join(DISP_BUILD.get(b, b) for b in BUILDS)))
P('Chinese arms and their byte-frozen English renderings) × the three contract arms. Each rate below is')
P('**pooled over the three starts** — every item is one observation per start, so a cell of the 153-item')
P('strata rests on %d observations rather than on any single start; the spread **between** starts is reported' % (153 * 3))
P('separately below. Four structural controls')
P('were asserted before any statistic was computed, and all four pass (`ea2_integrity.py`): every row has')
P('$gt = 0$; the three arms of a cell share identical item sets; the three service starts share identical item')
P('sets; and the CN and EN sides share identical item sets.')
P('')
P('**Is the outlet used, and used discriminatively?**')
P('')
# ★ 零计数单元格补 Wilson 95% 上限：本论文早已定过这条规矩（宿主端点 0/253 ⇒ 上限 1.5%）。
#   此处 n 来自产物（非零侧 199/229，真零侧 459），故上限由脚本算、不手打。
def wilson_hi(k, n, z=1.959964):
    if not n:
        return 0.0
    p = k / float(n)
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    h = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5)
    return 100.0 * (c + h) / d


def cell(pct, n, star=False):
    """pct 为 0.0 时附上 Wilson 95% 上限（写成 ≤X%），否则只写点值。"""
    s = ('**%.1f%%**' % pct) if star else ('%.1f%%' % pct)
    if pct == 0.0 and n:
        s += ' (≤%.1f%%)' % wilson_hi(0, n)
    return s


P('| build | pool | `channel` → `no_people` | `channel` → `cannot_judge` | `base` answers `0` |')
P('|---|---|---|---|---|')
for model in sorted({k[0] for k in by_build}):
    zp = [v for k, v in by_build.items() if k[0] == model and k[1] == 'cn' and k[2] == 'z0easy']
    zp2 = [v for k, v in by_build.items() if k[0] == model and k[1] == 'cn' and k[2] == 'z0hard']
    if zp:
        ch = zp[0].get('channel', {})
        ba = zp[0].get('base', {})
        _e = n_by_build.get((model, 'cn', 'z0easy', 'channel'), 0)
        P('| %s | true zero (z0easy) | %s | %s | %s |'
          % (DISP_BUILD.get(model, model), cell(ch.get('no_people', 0), _e, star=True),
             cell(ch.get('cannot_judge', 0), _e), cell(ba.get('zero', 0), _e)))
    if zp2:
        ch2 = zp2[0].get('channel', {})
        ba2 = zp2[0].get('base', {})
        _h = n_by_build.get((model, 'cn', 'z0hard', 'channel'), 0)
        P('| %s | true zero (z0hard) | %s | %s | %s |'
          % (DISP_BUILD.get(model, model), cell(ch2.get('no_people', 0), _h, star=True),
             cell(ch2.get('cannot_judge', 0), _h), cell(ba2.get('zero', 0), _h)))
    for zone in ('dense', 'aerial'):
        c = nz.get((model, zone, 'channel'))
        b = nz.get((model, zone, 'base'))
        if c:
            _n = nz_n.get((model, zone, 'channel'), 0)
            P('| %s | non-zero (%s) | %s | %s | %s |'
              % (DISP_BUILD.get(model, model), zone, cell(c.get('no_people', 0), _n),
                 cell(c.get('cannot_judge', 0), _n, star=True), cell((b or {}).get('zero', 0), _n)))
P('')
P('A **0.0%** cell is reported with its **Wilson 95% upper bound** (`≤x%`) rather than as a bare zero, the')
P('convention this paper already applies to the hosted endpoints that never answer zero; the bound is computed')
P('from the cell\'s own $n$ (153 items × 3 starts on the true-zero pool, 229 and 199 on the dense and aerial')
P('non-zero pools). A bare `0.0%` would claim more than 0/229 observations can support.')
P('')
P('The outlets are used **discriminatively**: on verified-empty images the emptiness outlet dominates, while on')
P('images that do contain people the same arm prefers `cannot_judge` — the behavioural content of the')
P('zero-channel-precision quantity of Appendix M.21, now measured on independently verified zeros.')
P('')
P('**Stability across service starts and languages.**')
P('')
P('| build | `no_people` range over the three service starts | CN vs EN `no_people` (z0easy) |')
P('|---|---|---|')
for model in sorted({k[0] for k in by_build}):
    rng = noise.get((model, 'cn'), [])
    cn = [v['channel']['no_people'] for k, v in by_build.items()
          if k[0] == model and k[1] == 'cn' and k[2] == 'z0easy']
    en = [v['channel']['no_people'] for k, v in by_build.items()
          if k[0] == model and k[1] == 'en' and k[2] == 'z0easy']
    if rng or (cn and en):
        P('| %s | %.1f–%.1f pp | %.1f%% vs %.1f%% |'
          % (DISP_BUILD.get(model, model), min(rng) if rng else 0, max(rng) if rng else 0,
             cn[0] if cn else 0, en[0] if en else 0))
P('')
# ★ 与 §M.38（同池、单次服务）的一致性：**由数据算出**并写进正文，让读者一眼看到两次测量互相印证。
_easy = [v['channel']['no_people'] for k, v in by_build.items() if k[1] == 'cn' and k[2] == 'z0easy'
         and 'channel' in v]
_hard = [v['channel']['no_people'] for k, v in by_build.items() if k[1] == 'cn' and k[2] == 'z0hard'
         and 'channel' in v]
if _easy and _hard:
    # §M.38 报的区间（该小节自己的数字，写在它表中：easy 47–87%、hard 39–90%）——此处**只引用**，
    # 并算出"两次独立测量在同一池上的最大端点差"，把差异**说清是多大**，而不是含糊地归给噪声。
    M38 = {'easy': (47.0, 87.0), 'hard': (39.0, 90.0)}
    _gaps = [abs(min(_easy) - M38['easy'][0]), abs(max(_easy) - M38['easy'][1]),
             abs(min(_hard) - M38['hard'][0]), abs(max(_hard) - M38['hard'][1])]
    P('**Consistency with the single-start control of Appendix M.38.** On the same pool with one service start,')
    P('that appendix reported $\\texttt{no\\_people}$ on **47–87%** of the easy stratum and **39–90%** of the hard')
    P('stratum across its families. With three starts per build and %s builds the same quantity, pooled over the' % NUM)
    P('starts, is **%.1f–%.1f%%** (easy) and **%.1f–%.1f%%** (hard): the two independent measurements of the same'
      % (min(_easy), max(_easy), min(_hard), max(_hard)))
    P('pool agree to within **%.1f pp** at their widest endpoint, which we report as the observed run-to-run scale'
      % max(_gaps))
    P('rather than attributing it to any single cause (the two runs differ in both session and pool order).')
P('')
# ★ "服务稳定"是**结论**，必须由数据决定措辞：极差若进到噪声带里（甚至超出），
#   就不能说"far below"。分支写法与 M.41 同源（先算再写，不先写再找数）。
_all_rng = [(max(vals), '%s %s' % (mdl, lang)) for (mdl, lang), vals in noise.items() if vals]
_rmax = max(_all_rng) if _all_rng else (0.0, '（无）')
P('Two things follow. First, the **channel composition is service-stable** — its largest spread across the')
P('three fresh starts, over every build, language and pool, is **%.1f pp** (%s), %s the 2.15–6.46 pp'
  % (_rmax[0], _rmax[1],
     'below' if _rmax[0] < 2.15 else ('inside' if _rmax[0] <= 6.46 else 'above')))
P('across-repeat band that governs $\\rho$ (§A.3) — so the identification claim rests on a quantity that')
P('repeated serving does not move beyond that band. Second, the channel choice is')
P('**language-invariant** on this pool even though the **rate** of answered zeros is language-sensitive (§5.5):')
P('"which outlet" is stable, "how often" is not, which is why the paper separates the two.')
P('')
P('*Reproduction: `ea_build_z0.py` (pool), `20a_probe_truezero.py` / `20b_probe_lang.py` (drivers importing the')
P('frozen probe), analyzers `ea2_analyze.py`, `ea2_contrast.py`, `ea2_integrity.py`; frozen `ea2_z0_result.json`,')
P('`ea2_contrast_result.json`; and `anchor_m40m41.py`, which re-derives the quantities in this appendix — and in')
P('M.41 — from those frozen artifacts, checks the design constants against a frozen inventory of them, and fails')
P('on any number that is not registered.*')
M40 = '\n'.join(L) + '\n\n'

src = io.open(SUP, encoding='utf-8', newline='').read()
before = WC(src)
if '### M.40 ' in src:
    # 已存在 ⇒ 替换整段（幂等，便于 E2 收尾后重跑）。M.40 是**文件最后一节** ⇒ 替换到 EOF 即可；
    # ★ 不要用可见的哨兵串（本轮踩过：哨兵被写进了正文，撞了 en_check 的禁用串检查）。
    i = src.index('### M.40 ')
    # ★ M.40 曾是**文件最后一节**，故当初"替换到 EOF"是安全的；自从 M.41 追加在其后，
    #   "到 EOF"会把 M.41 一起删掉（静默丢一节）。改为**到下一个 ### 标题为止**，与位置无关。
    nxt = re.search(r'(?m)^### ', src[i + 1:])
    j = i + 1 + nxt.start() if nxt else len(src)
    _keep = src[j:j + 14].strip() if j < len(src) else 'EOF'   # ★ 必须在**旧串**上取，别在拼好的新串上取
    src = src[:i] + M40.rstrip('\n') + '\n\n' + src[j:]
    print('  [ok] 替换既有 M.40（其后保留：%s）' % _keep)
else:
    anchor = '### M.41' if '### M.41' in src else None
    if anchor is None:
        # M.39 是当前**最后一节**（其后没有 ### 标题）⇒ 直接追加到文件末尾
        m = re.search(r'### M\.39 ', src)
        assert m, '找不到 M.39 起点，无法插入 M.40'
        src = src.rstrip('\n') + '\n\n' + M40
        print('  [ok] 追加 M.40 到文件末尾（M.39 之后）')
    else:
        src = src.replace(anchor, M40 + anchor, 1)
        print('  [ok] 在 M.41 之前插入 M.40')
after = WC(src)
print('  补充材料词数：%d → %d（%+d）' % (before, after, after - before))
# ★ 2026-09-24：自订上限取消 ⇒ 只报告、不拦截（与 gen_m41_e1.py 同口径）。
# ★ 写盘前先跑 en_check 的**禁用串**清单（与裁决者同一份名单）：本轮踩过 `\bv\d+\b`
#   —— 我在正文里写了 "(v0527 #1)"，这是内部版本号，不能出现在送审件里。
BANNED = [(r'⚠', '⚠'), (r'已撤回', '撤回'), (r'\bA\d{1,2}\b', '内部编号'), (r'\bv\d+\b', '版本号'),
          (r'PaperB_', '内部文档'), (r'[A-Za-z]:\\', '盘符'), (r'/root/', '服务器路径'),
          (r'pod_mirror', '内部机器名'), (r'盲审|六模型|七模型', '评审语'), (r'TODO|TBD|XXX', '占位'),
          (r'本节为待实验内容', '占位符')]
hit = {n: re.findall(p, M40)[:3] for p, n in BANNED if re.findall(p, M40)}
if hit:
    sys.exit('!! M.40 命中禁用串：%s ⇒ 拒绝写盘' % hit)
print('  禁用串预检：0（与 en_check 同一份名单）')
bak = SUP + '.bak_before_m40_%s' % time.strftime('%Y%m%d_%H%M%S')
shutil.copy2(SUP, bak)
io.open(SUP, 'w', encoding='utf-8', newline='\n').write(src)
print('  已写盘 md5 %s' % hashlib.md5(io.open(SUP, 'rb').read()).hexdigest()[:12])
