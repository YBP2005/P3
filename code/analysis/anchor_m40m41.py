# -*- coding: utf-8 -*-
"""anchor_m40m41.py — 补充材料 M.40 / M.41 的**锚点校验器**（常设门禁，只读）。

## 为什么需要它
这两节里有一百多个数字：率的由分析器生成（有冻结件），但**常数与引用值**此前只存在于"我说过"
（例如发布件 6,146 张、池 306 张、每档 300 张、54 格）。本库纪律是"**能算就不要抄**"，
所以两节里的每个数都应当落进下面三类之一，且**新加的数不得绕过登记**：

  ① **由冻结件重算**：`ea2_z0_result.json` / `ea2_contrast_result.json` / `fsc_res_result.json` /
     `e1_qc.json` / `m40m41_facts.json` 里真实存在的值（脚本从产物**收集**出"取值宇宙"，
     再要求正文里出现的每个数都落在其中 ⇒ 新写的数一旦与产物不符就会失败）；
  ② **结构恒等**：如 54 = 3 构建 × 3 档 × 6 臂、459 = 153 × 3、180 = 30 目录 × 6 —— 由脚本当场算；
  ③ **引用正文**：如 10 pp / 32.0 pp（§5.12）、2.15–6.46 pp（§A.3）、0.6 % / 9.1 %（§5.7）——
     脚本要求在**主稿**里确实出现，避免"引了一个正文里没有的数"。

另外一条**反面护栏**：`359` 那种"`ls` 行数冒充文件数"的数字必须不可能再出现——
本脚本对"文件/目录计数"一律要求等于**现场重数**的值。

用法：python -u anchor_m40m41.py        # 失败以非零退出，便于串进门禁
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
import collections
import glob
import io
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
W = os.path.dirname(os.path.abspath(__file__))
PAPER = NR()
SUP = RP('PaperB_英文补充材料_PR_20260919.md')
EN = RP('PaperB_英文稿_PR_20260919.md')

fails, notes = [], []


def chk(label, ok, detail=''):
    (notes if ok else fails).append('%s %s' % ('OK  ' if ok else 'FAIL', label))
    print('  [%s] %-58s %s' % ('OK  ' if ok else 'FAIL', label, detail))


# ── 0. 读入 ────────────────────────────────────────────────────────────────
sup = io.open(SUP, encoding='utf-8-sig').read()
manu = io.open(EN, encoding='utf-8-sig').read()


def section(tag):
    i = sup.index(tag)
    nxt = re.search(r'(?m)^### ', sup[i + 1:])
    return sup[i:i + 1 + nxt.start() if nxt else len(sup)]


M40, M41 = section('### M.40 '), section('### M.41 ')
print('M.40 %d 字符 ｜ M.41 %d 字符' % (len(M40), len(M41)))


def load(name):
    p = os.path.join(W, name)
    return json.loads(io.open(p, encoding='utf-8').read()) if os.path.exists(p) else None


z0 = load('ea2_z0_result.json')
con = load('ea2_contrast_result.json')
fsc = load('fsc_res_result.json')
qc = load('e1_qc.json')
facts = load('m40m41_facts.json')
# ★ 2026-09-24 夜：M.40 新增的**逐项 2×2 表**（出口 × 图像类型）由 `gen_m40_2x2.py` 冻结在此。
#   它必须进"取值宇宙"，否则 2×2 里的计数/百分比会被本门禁判为"无出处"。
x2 = load('m40_2x2_result.json')
assert x2, 'M.40 的 2×2 冻结件缺失：m40_2x2_result.json（跑 gen_m40_2x2.py --apply）'
# ★ 2026-09-24 夜（多条在册条目的 D1d）：逐构建表**每格**都配了 Wilson 95% 区间
#   （原先只给零格），冻结在 `m40_wilson_result.json`。同样必须进取值宇宙。
wil = load('m40_wilson_result.json')
assert wil, 'M.40 的逐构建区间冻结件缺失：m40_wilson_result.json（跑 gen_m40_wilson.py --apply）'
# ★ 2026-09-24 深夜（S1）：M.41 的**服务栈对照**（`--max-model-len` 4096 vs 8192，各 3 次全新起服）
#   的独立重算件 —— 48.8/12.4/0.3/0.4/36.37/4.6/最大历史差 0.27 等值都出自它（**不是**分析器输出）。
ctx = load('ctxctrl_indep_result.json')
assert ctx, 'S1 独立重算冻结件缺失：ctxctrl_indep_result.json（跑 _ctxctrl_indep_check.py）'

# ── 1. 由冻结件收集"取值宇宙"─────────────────────────────────────────────────
UNIV = collections.defaultdict(list)


def norm(x):
    s = ('%g' % float(x))
    return s


def harvest(obj, tag):
    if isinstance(obj, dict):
        for k, v in obj.items():
            harvest(v, '%s.%s' % (tag, k))
    elif isinstance(obj, list):
        for v in obj:
            harvest(v, tag)
    elif isinstance(obj, (int, float)) and not isinstance(obj, bool):
        UNIV[norm(obj)].append(tag)
        if float(obj).is_integer():
            UNIV[str(int(obj))].append(tag)


for obj, tag in ((z0, 'ea2_z0'), (con, 'ea2_contrast'), (fsc, 'fsc_res'), (qc, 'e1_qc'), (facts, 'facts'),
                 (x2, 'm40_2x2'), (wil, 'm40_wilson'), (ctx, 'ctxctrl')):
    if obj:
        harvest(obj, tag)
print('取值宇宙：%d 个不同数值（来自 8 份冻结件）' % len(UNIV))

# ── 2. 结构恒等（当场算）──────────────────────────────────────────────────
STRUCT = {}
STRUCT['54'] = 3 * 3 * 6            # E1：3 构建 × 3 档 × 6 臂
STRUCT['459'] = 153 * 3             # 每层 153 张 × 3 次服务
STRUCT['180'] = 30 * 6              # E2：30 个目录 × 6 个 CSV
STRUCT['60'] = 5 * 3 * 2 * 2 * 1    # E2 条件：构建×服务×语言×层×（臂按条件计）——见下说明
for k, v in STRUCT.items():
    UNIV[k].append('struct(%s=%d)' % (k, v))

# ── 3. 现场重数：本地 E2 产物（比"脚本自报"可靠）─────────────────────────────
ea2d = RP('analysis', 'ea2_z0')
dirs = [d for d in os.listdir(ea2d) if os.path.isdir(os.path.join(RP('analysis', 'ea2_z0'), d))]
csvs = [f for d in dirs for f in os.listdir(os.path.join(RP('analysis', 'ea2_z0'), d)) if f.endswith('.csv')]
fscd = RP('analysis', 'fsc_res')
n384 = len(glob.glob(RP('analysis', 'fsc_res', '384', '*.csv')))
n256 = len(glob.glob(RP('analysis', 'fsc_res', '256', '*.csv')))
n768 = len(glob.glob(RP('analysis', 'fsc_res', '768up', '*.csv')))
nfroz = len(glob.glob(RP('analysis', 'fsc_res', 'frozen384', '*.csv')))
print('现场重数：E2 %d 目录 / %d CSV ｜ E1 %d+%d+%d（冻结面板 %d）' % (len(dirs), len(csvs), n384, n256, n768, nfroz))
for v in (len(dirs), len(csvs), n384, n256, n768, nfroz, n384 + n256 + n768 + nfroz):
    UNIV[str(v)].append('counted-on-disk')

# ── 4. 引用正文的常数：要求在**主稿**里确实出现 ─────────────────────────────
QUOTED = {'10': '§5.12 合同旋钮比分辨率旋钮多动的下限（pp）',
          '32.0': '§5.12 分辨率旋钮单独的最大位移（pp）',
          '2.15': '§A.3 跨重复带下沿（pp）', '6.46': '§A.3 跨重复带上沿（pp）',
          '0.6': '§5.7 同图缩放下的弃权率（%）', '9.1': '§5.7 同图模糊下的弃权率（%）', '15': '§5.7 缩放到的像素比例（%）'}
MQUOTED = {'47': '§M.38 报的 easy 层下沿（%）', '87': '§M.38 报的 easy 层上沿（%）',
           '39': '§M.38 报的 hard 层下沿（%）', '90': '§M.38 报的 hard 层上沿（%）'}
m38 = section('### M.38 ')
for v, why in MQUOTED.items():
    chk('引用值 %-5s 在 §M.38 中存在（%s）' % (v, why),
        re.search(r'(?<![\d.])%s(?![\d])' % v, m38) is not None)
    UNIV[v].append('quoted-M38:%s' % why)

# ── 4b. Wilson 95% 上限：由 (0, n) 当场重算，而不是当成"抄来的数" ─────────────
def wilson_hi(k, n, z=1.959964):
    if not n:
        return 0.0
    p = k / float(n)
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    h = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5)
    return 100.0 * (c + h) / d


_ns = set()
if con:
    _ns |= {v.get('n') for v in con['nonzero'].values() if v.get('n')}
_ns.add(153 * 3)                      # 真零池：153 张 × 3 次服务
_wilson = {norm(round(wilson_hi(0, n), 1)): 'Wilson95 upper for 0/%d' % n for n in _ns if n}
for v, why in _wilson.items():
    UNIV[v].append(why)
print('Wilson 上限（0/n，n ∈ %s）：%s' % (sorted(x for x in _ns if x), sorted(_wilson)))
for v, why in _wilson.items():
    if re.search(r'≤\s*%s\s*%%' % re.escape(v), M40):
        chk('Wilson 上限 %s%% 出现在 M.40 的零单元格（%s）' % (v, why), True)
_wilson_used = [v for v in _wilson if re.search(r'≤\s*%s\s*%%' % re.escape(v), M40)]
chk('M.40 的零单元格确实带上了 Wilson 上限（%d 个不同值）' % len(_wilson_used), bool(_wilson_used),
    str(sorted(_wilson_used)))
chk('M.40 不含"裸 0.0%"的非零侧单元格',
    not re.search(r'\|\s*0\.0%\s*\|', M40), '（应写成 0.0% (≤x%)）')

for v, why in QUOTED.items():
    chk('引用值 %-5s 在主稿中存在（%s）' % (v, why), re.search(r'(?<![\d.])%s(?![\d])' % re.escape(v), manu) is not None)
    UNIV[norm(float(v))].append('quoted:%s' % why)
    UNIV[v].append('quoted:%s' % why)

# ── 5. 抽取两节里的每个"像量"的数字，逐个要求在宇宙内 ────────────────────────
# ★ 抽取前先**屏蔽非量**：附录编号（M.40/M.41/M.38）、节号（§5.12/§A.3/§6.5）、
#   模型规模后缀（8B/32B）、模型与数据集名（FSC-147、gemma-3-12b …）。
#   不屏蔽就会把"M.40"里的 40、"FSC-147"里的 147 当成数字去要出处（首版就是这么误报的）。
MASK = [r'M\.\d+(?:\.\d+)?', r'§[A-Z]?(?:\d+)(?:\.\d+)*', r'\d+\s?B\b',
        r'\{[\d,]+\}',                       # 花括号里的编号列表，如 {384,256,768}（含逗号，先于千分位处理）
        r'[\w./]+\.(?:py|sh|json|md|csv)',   # 脚本/文件名（其中数字不是"量"）
        r'FSC-147', r'UCF-QNRF', r'BBBC005', r'Phi-3\.5', r'InternVL3\.5', r'InternVL2\.5',
        r'Qwen3-VL-32B', r'Qwen3-VL-30B', r'Qwen2\.5', r'LLaVA-OneVision-7B', r'gemma3?-3?-12b',
        r'TallyQA', r'CountBench', r'images_384_VarV2', r'no\\_people']
# ⚠ 屏蔽规则必须**只吃名字、不吃量**：首版里有一条 `\.5\b` 是为了匹配 "Phi-3.5"，
#   结果把 "37.5%" 的 ".5" 也吃掉了 ⇒ 正文变成 "37 %"，报出假缺号。这里改成整名屏蔽。
DESIGN = {  # 设计常数：不是"从数据算出来的"，而是**实验设计**的一部分（写明出处）
    '3': '同层 3 次全新服务启动 / E1 三档 / 每目录 3 臂', '5': 'E2 五个构建', '2': '双语言 / 双分层',
    '31': '§M.40/M.37 的 31 单元设定（设计常数）', '20': '§M.40 的 20 预算设定（设计常数）',
    '6': 'E1 每档六臂', '24': '--max-num-seqs', '128': 'max_tokens', '4096': '冻结面板 --max-model-len',
    '8192': '本轮 --max-model-len', '300': '每档样本数 / 构建间的可比样本', '153': '每个分层的真零图数',
    '256': '短边档（下采样）', '384': '发布件短边（线性尺度）', '768': '短边档（上采样）',
    '0.667': '短边 256 的线性缩放比', '0.444': '短边 256 的面积比', '4.000': '短边 768 的面积比',
    '30': 'E2 目录数', '180': 'E2 本批 CSV 数', '60': 'E2 条件数', '459': '池化观测数（153×3）',
    '54': 'E1 格数（3×3×6）', '306': '真零池图数', '307': 'gt_z0.csv 行数（含表头）',
    '6146': '发布件图像条目数', '1918': '发布件长边上界', '1229': '样本长边上界', '514': '样本长边中位',
    '0.5': '复现紧密度判据（|Δ| ≤ 0.5 pp）', '9': '差 ≤0.5 pp 的格数', '12': '可比格数',
    '1.5': '与 §M.38 的最宽端点差（由该节引用的区间与本节算得区间相减）',
    '0.85': '--gpu-memory-utilization', '1': '每提示一张图（--limit-mm-per-prompt）',
    # ★ 2026-10-01（v0621）：§M.40 的"按起服聚类"检查的两个设计常数（E5）。
    #   重抽次数与 seed 都是**跑前写死**的（见放行件 code/analysis/p3r2_plan_m40_cluster.py 的头部），
    #   不是从数据算出来的量；登记方式与本表其它设计常数一致。
    '2000': 'E5 簇自助的重抽次数（按起服为簇，B=2000）',
    '20260930': 'E5 簇自助所用固定 seed（20260930）',
}
for v, why in DESIGN.items():
    UNIV[v].append('design:%s' % why)


def unmask(seg):
    # 千分位先规范化：`6,146` 必须先变成 `6146`，否则会被切成 `6` 和 `146` 两个记号（首版踩过）。
    seg = re.sub(r'(?<=\d),(?=\d{3}\b)', '', seg)
    for p in MASK:
        seg = re.sub(p, ' ', seg)
    return seg


TOK = re.compile(r'(?<![\w.])(\d+(?:\.\d+)?)(?![\w])')
for tag, seg in (('M.40', M40), ('M.41', M41)):
    masked = unmask(seg)
    unknown = []
    for m in TOK.finditer(masked):
        raw = m.group(1)
        v = norm(float(raw))
        if v not in UNIV and str(int(float(raw))) not in UNIV:
            unknown.append((raw, masked[max(0, m.start() - 45):m.start() + 25].replace('\n', ' ')))
    chk('%s 全部数字都有出处（%d 个记号）' % (tag, len(TOK.findall(masked))), not unknown,
        '' if not unknown else '未登记 %d 个：%s' % (len(unknown), unknown[:6]))

# ── 6. 针对性重算：把"关键量"与冻结件逐一对上 ───────────────────────────────
if fsc:
    dz = [abs(v['zero']) for v in fsc['delta_vs_384'].values()]
    da = [abs(v['abstain']) for v in fsc['delta_vs_384'].values()]
    con_arms = ('base', 'permit', 'channel', 'enumAbstain')
    cvals = [max(abs(v['zero']), abs(v['abstain'])) for k, v in fsc['delta_vs_384'].items()
             if k.split('|')[2] in con_arms]
    evals = [abs(v['abstain']) for k, v in fsc['delta_vs_384'].items() if k.split('|')[2].startswith('exemplar')]
    repl = fsc.get('replication_384_vs_frozen', {})
    tight = [k for k, v in repl.items() if max(abs(v['d_zero']), abs(v['d_abstain'])) <= 0.5]
    worst = max(repl.items(), key=lambda kv: max(abs(kv[1]['d_zero']), abs(kv[1]['d_abstain'])))
    chk('E1 合同臂最大位移 = 文中 2.0 pp', abs(max(cvals) - 2.0) < 0.05, '算得 %.1f' % max(cvals))
    chk('E1 示例臂最大弃权位移 = 文中 10.7 pp', abs(max(evals) - 10.7) < 0.05, '算得 %.1f' % max(evals))
    chk('E1 复现 ≤0.5 pp 的格数 = 文中 9 / 12', len(tight) == 9 and len(repl) == 12,
        '算得 %d / %d' % (len(tight), len(repl)))
    wv = max(abs(worst[1]['d_zero']), abs(worst[1]['d_abstain']))
    chk('E1 最大复现差 = 文中 36.0 pp', abs(wv - 36.0) < 0.05, '算得 %.1f（%s）' % (wv, worst[0]))
if con:
    np_easy = [v['pct']['no_people'] for k, v in con['z0'].items() if k.split('|')[1] == 'cn'
               and k.split('|')[2] == 'z0easy' and k.split('|')[3] == 'channel']
    chk('E2 真零 no_people 区间 = 文中 47.9–86.9 %',
        abs(min(np_easy) - 47.9) < 0.05 and abs(max(np_easy) - 86.9) < 0.05,
        '算得 %.1f–%.1f' % (min(np_easy), max(np_easy)))
if z0:
    rng = [v['range_pp']['no_people'] for v in z0['serving_noise'].values()]
    chk('E2 服务间极差上界 = M.40 文中 %s pp' % ('2.6' if '**2.6 pp**' in M40 else '?'),
        '**%.1f pp**' % max(rng) in M40, '算得 %.1f（全 %d 条的上界）' % (max(rng), len(rng)))
    chk('E2 服务间「多数 ≤0.7」也成立', sum(1 for r in rng if r <= 0.7) >= len(rng) * 0.8,
        '%d/%d 条 ≤0.7 pp' % (sum(1 for r in rng if r <= 0.7), len(rng)))
    chk('E2 条件数 = 文中 60', len(z0['serving_noise']) == 60, '算得 %d' % len(z0['serving_noise']))
if facts:
    chk('发布件条目 = 文中 6,146', facts['release']['entries'] == 6146, str(facts['release']['entries']))
    chk('短边恒 384（全部条目）', facts['release']['short_is_384'] == facts['release']['entries'])
    chk('长边区间 = 文中 384–1918', (facts['release']['long_min'], facts['release']['long_max']) == (384, 1918))
    chk('样本长边中位 = 文中 514', facts['sample']['long_median'] == 514)
    chk('真零池 = 文中 306 张 / 307 行', facts['pool']['images'] == 306 and facts['pool']['gt_rows'] == 307)

# ── 7. 反面护栏：杜绝"ls 行数冒充文件数"这类数 ───────────────────────────────
# ★ 用**词边界**判断，别用 `in`：`0.2359` 里也含 "359" 子串，会误报（首版就是这么误报的）。
chk('两节与主稿均不含假计数 359',
    all(re.search(r'(?<![\d.])359(?![\d.])', t) is None for t in (M40, M41, sup)))
chk('E2 文件数为现场重数（本批 180）', len(csvs) == 180 and len(dirs) == 30,
    '现场 %d 目录 / %d CSV' % (len(dirs), len(csvs)))
chk('E1 格数 = 现场重数 %d（文中 54）' % (n384 + n256 + n768), n384 + n256 + n768 == 54)

print('\n' + '=' * 96)
print('锚点校验：%d 通过 ｜ %d 失败' % (len(notes), len(fails)))
for f in fails:
    print('   ' + f)
print('=' * 96)
sys.exit(0 if not fails else 1)
