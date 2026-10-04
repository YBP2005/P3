# -*- coding: utf-8 -*-
"""英文稿统一校验器（合并 en_finalize3 的验收 + en_number_audit 的溯源 + 两条新增结构性断言）。

新增断言（教训 06_改动纪律与产物保全：结构性编辑必须有结构性断言）：
  N1 附录交叉引用可解析：正文每个 (Appendix X.Y) / Appendix X.Y 必须命中补充材料中的实际标题。
  N2 搬出内容仍在附录：从主文 §3.6 移走的五分类判据/去重协议必须在附录 B.1–B.2 找到。
只读，不改任何产物。退出码 0=全过，1=有失败项。
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
import io, os, re, sys, hashlib, json
sys.stdout.reconfigure(encoding='utf-8')

ROOT = NR()
PKG = NR('review_pkg_20260919')
EN = RP('PaperB_英文稿_PR_20260919.md')
SUP = RP('PaperB_英文补充材料_PR_20260919.md')
ZH = NR('PaperB_章节骨架_v3_可确证性_20260911.md')
# 第二数字权威：命题 4–6 的验证记录。其数字是**当场计算**得出（README 第 4 条
# 「数字能算就不要抄」），不是从中文定稿翻译来的，故单列为第二权威。
IDENTITY_AUTHORITY = NR('PaperB_命题4-6验证记录_20260919.md')
# 第三权威：参考文献取回记录。条目里的年份/编号等数字**来自 P40 上的 arXiv/Crossref 取回**，
# 不是从中文定稿翻译来的，故单列（同 IDENTITY_AUTHORITY 的道理）。
ARXIV_AUTHORITY = RP('analysis', 'work', '_arxiv_records.json')
ARXIV_AUTHORITY2 = RP('analysis', 'work', '_refs_inventory.json')
ARXIV_AUTHORITY3 = RP('analysis', 'work', '_refs_extra.json')
# 第四权威：E1 判别实验的证据记录（2026-09-20）。E1 的数字由 5090 上的实测产出
# （48 格、1591/1591、2.463–9.452、语料 2496 行），既非中文定稿的翻译、也非参考文献取回，
# 与 IDENTITY_AUTHORITY 同理单列。
E1_AUTHORITY = RP('PaperB_E1证据_20260920.md')
# 第四组：**E2 普查（09-22 收尾轮）** 的证据记录 —— §3.6(d) 改写、§5.7 普查段、§7.7 旁证与附录 M.18
# 里引用的数字（258/273、263/273、46/52、52/52、4.854–6.281、0.250/0.469/0.511/0.662/0.833、
# 36.1–92.9%、88.6–100% 等）全部来自这份记录，且由 `verify_s11.py` 逐条断言回原始 CSV。
# 它既不是中文定稿的翻译、也不是参考文献取回，故与前几组同理单列。
E2_AUTHORITY = NR('PaperB_E2证据_20260921.md')
# 第五组：**[external-review]对照证据（09-22）** —— 针对模拟[external-review]两条"可能致命"意见的正面检验：
# ① 跨度的等点数/去端点稳健性（Spearman 0.964/0.977/0.993、τ 单元降 2.2–5.0 倍）
# ② 答 0 率的构建×域两因素方差分解（38.7/33.9/27.4%、密集域构建极差 90.3 pp、航拍 2.7–8.7 pp）
# 正文 §5.7/§7.3/§9 引用的正是这些数字，故单列为权威。
RC_AUTHORITY = NR('PaperB_评审对照证据_20260922.md')
# ★ 2026-09-24：[external-review]修回证据（§7.3 的置换 CI／留出区间／功效等新数字的出处）。
#   与 E1/E2/RC/A5 同一机制：新算出的数字必须先进证据档，正文才允许引用。
V0527_AUTHORITY = NR('PaperB_盲审v0527修回证据_20260924.md')

en = io.open(EN, encoding='utf-8', newline='').read()
sup = io.open(SUP, encoding='utf-8', newline='').read()
zh = io.open(ZH, encoding='utf-8', newline='').read()
au = io.open(IDENTITY_AUTHORITY, encoding='utf-8', newline='').read() if os.path.exists(IDENTITY_AUTHORITY) else ''
ar = (io.open(ARXIV_AUTHORITY, encoding='utf-8', newline='').read() if os.path.exists(ARXIV_AUTHORITY) else '')
ar += (io.open(ARXIV_AUTHORITY2, encoding='utf-8', newline='').read() if os.path.exists(ARXIV_AUTHORITY2) else '')
ar += (io.open(ARXIV_AUTHORITY3, encoding='utf-8', newline='').read() if os.path.exists(ARXIV_AUTHORITY3) else '')
# 第三组：2026-09-20 补引用的取回记录（Crossref/OpenAlex，经 P40）——
# 新引用的年份、DOI、卷期等数字取自这些记录，故同列为权威。
for _rf in ('_pb_refs_out.json', '_pb_refs2_out.json', '_pb_refs34_out.json', '_pb_refs5_out.json',
            # ★ 2026-09-27（v0585）：补引 JHU-CROWD++（[55]）的取回记录。
            #   它引入了一个新 DOI 数字令牌（`2020.3035969`），[F] 段正确地把它报成"无法溯源"；
            #   本文件即那份溯源（arXiv abs + Crossref work，均 2026-09-27 实测）。
            '_pb_refs6_out.json',
            # ★ 2026-10-04（v0644）：本轮主稿新增的两篇**回归侧拒答先例**的取回记录。
            #   [3] Geifman & El-Yaniv, *SelectiveNet*（ICML 2019）——题录带**出版页码**
            #   `PMLR 97:2151-2159`，其中 `2151` / `2159` 是 [F] 段必须能溯源的新数字令牌；
            #   [4] Denis, Hebiri & Zaoui, *Regression with Reject Option and Application to kNN*
            #   （NeurIPS 2020，arXiv:2006.16597）。两页均在**写题录之前**实取
            #   （PMLR 页与 arXiv abs 页，2026-10-04，HTTP 200），逐字记入 `_pb_refs7_out.json`
            #   —— 与 v0585 的 JHU-CROWD++（[55]）同一机制：新引用带来的数字先落取回记录，正文才允许印。
            '_pb_refs7_out.json'):
    _rp = os.path.join(RP('analysis', 'work'), _rf)
    if os.path.exists(_rp):
        ar += io.open(_rp, encoding='utf-8', newline='').read()
e1n = (io.open(E1_AUTHORITY, encoding='utf-8', newline='').read() if os.path.exists(E1_AUTHORITY) else '')
e2n = (io.open(E2_AUTHORITY, encoding='utf-8', newline='').read() if os.path.exists(E2_AUTHORITY) else '')
assert e2n, 'E2 证据记录缺失：%s' % E2_AUTHORITY
rcn = (io.open(RC_AUTHORITY, encoding='utf-8', newline='').read() if os.path.exists(RC_AUTHORITY) else '')
assert rcn, '评审对照证据缺失：%s' % RC_AUTHORITY
v27n = (io.open(V0527_AUTHORITY, encoding='utf-8', newline='').read()
        if os.path.exists(V0527_AUTHORITY) else '')
assert v27n, 'v0527 修回证据缺失：%s' % V0527_AUTHORITY
# ★ 2026-09-22（同日二轮）：A5（正文中称 E3）的跨家族证据记录同列为数字权威——
#   §5.7/§8.2/M.19 的新数字（7/7、2.1%、81.3 pp、5.7 pp 等）出处就是它与其 `a5_*.json`。
A5_AUTHORITY = NR('PaperB_A5跨家族证据_20260922.md')
a5n = (io.open(A5_AUTHORITY, encoding='utf-8', newline='').read() if os.path.exists(A5_AUTHORITY) else '')
assert a5n, 'A5/E3 证据记录缺失：%s' % A5_AUTHORITY
# ★ 2026-09-22（三转）：无标注代理的实测结果（M.20）同列为数字权威——正文 §3.3 的
#   0.49–0.64 / 0.641 / 0.143 / −24.7 到 +65.1 等数字出处就是这两份冻结果。
for _lf in ('a_lightfree_result.json', 'a_lightfree_grid.json', 'a_lightfree_quoted.json',
            # ★ 2026-09-22（路线 A）：§5.12「单口径的代价」全部数字的出处
            'convention_rank_result.json', 'convention_rank_quoted.json',
            # ★ 2026-09-22（路线 A/B1）：§5.13 公开基准（FSC-147）数字的出处
            'b1_fsc_result.json', 'b1_fsc_quoted.json',
            # ★ 2026-09-22（B2 试跑，负结果）：M.23 数字的出处
            'b2_pilot_result.json', 'b2_pilot_phrasing_result.json',
            'b2_pilot_consensus_result.json',
            # ★ 2026-09-23（W1/W2 前瞻验证）：§5.14 引用的每个数字的出处。
            #   `w1_quoted.json` 由 `w1_quote.py` 从产物现算生成（本面板 6 家族 × 4 域 × 4 臂 +
            #   FSC 示例臂 + 三个托管端点），因此正文 §5.14 的数字全部可溯源，无手打值。
            'w1_quoted.json',
            # ★ 2026-09-23 第 8 轮：公开基准上的**口径修正**（回顾性重算；M.35 与 §5.14 末段的数字出处）
            'retro_quoted.json',
            # ★ 2026-09-23（八模型全量[external-review]后）：域/家族**方差分量各自的区间**（M.36 新增句的出处）
            'varcov_ci.json', 'w1_predict.json',
            # ★ 2026-09-23（接力会话）：§7.3 新句与 **M.37** 的全部数字出处——
            #   `calib_scale_quoted.json` 由 `calib_scale_quote.py` 从两份冻结结果**现算**（含正文字面使用的
            #   显示值 0.810/0.536/0.571/0.548/0.027/2.352）；`f9_quoted.json` 是 F.9 的**可核验转录记录**
            #   （路径 B：与中文骨架 §8.10 ③ 逐值比对，10 行 × 4 列全中；含不可独立复算的披露）。
            'calib_scale_quoted.json', 'f9_quoted.json',
            # ★ 2026-09-23（E-A 真零识别对照）：正文 §8.2 新增句与 **M.38** 的数字出处。
            #   `ea_truezero_result.json` 由 `ea_finalize.py` 从 A800 产物与本地 D0 对照**现算**，
            #   并带 `quoted_display`（正文字面使用的显示值），故正文数字可溯源、无手打。
            'ea_truezero_result.json',
            # 2026-09-23（E-C 语言对照 + 36-unit 可重算集）：M.38/M.39 与 M.37 补节的数字出处
            'ec_lang_result.json', 'equalcount36_result.json',
            # ★ 2026-09-26（本会话的零 GPU 分析）：正文 §7.3 与补充材料 M.18.9 / M.19.15 / M.21.9(e) / M.37
            #   本轮新引用的数字，全部出自下面这几份**由脚本现算并冻结**的结果件；
            #   与上面 `calib_scale_quoted.json` / `ec_lang_result.json` 同一机制：
            #   **新算出的数字先落冻结结果件，正文才允许引用**。
            #   · `n1*`：误差口径敏感性（0.629 / 0.595 / 0.965 / 0.983 …）
            #   · `n3_*`：可部署校准族全表（0.732 / 0.790 / 0.536 / 0.841 / 0.852 …）
            #   · `n4_*`：跨家族面板在头条量 S 上（0.00 / 0.79 / 1.43 / 19.56 …）
            #   · `a39_perknob*`：校准中间档及其 34 单元稳健性（0.790 / 0.722 / 0.994 …）
            #   · `g15_*`：动程归一（0.966 / 0.958 / 0.810 …）
            'n1_span_artefact_result.json', 'n1b_extras_result.json',
            'n3_deployable_calibration_result.json',
            'n4_cross_family_dense_panel.out.txt',
            'a39_perknob_rung_result.json', 'a39_perknob_rung_robust34_result.json',
            'g15_travel_extract.json', '_g15_norm.log',
            # ★ `n_quoted.json`：上面那些件存的是**全精度浮点**，而正文字面用的是**显示值**
            #   （如 0.732 / 0.790）。本件按 `calib_scale_quoted.json` 的同一先例登记显示值，
            #   **不放松判据**——它只把"正文的四舍五入形式"与"其来源"对上。
            'n_quoted.json',
            # ★ 2026-09-27（A800 第三批）：G1 行程匹配阶梯与 G5/G6 数字锚/等水平重扫。
            #   正文 §7.3 新增一句里只引了一个数（log-log 斜率 1.14），出自 `g3_result.json`；
            #   `g56_result.json` 供补充材料 M.43 与后续引用同源。
            'g3_result.json', 'g56_result.json',
            # ★ 2026-09-27（第四批：零新数据的两项排序复检）——#14 预注册排序统计量、#13 预算匹配跨度。
            #   正文 §7.3 新增的那句不含数字，此处登记只为**同源可复算**。
            'n5_order_result.json', 'n6_result.json'):
    _lp = os.path.join(RP('analysis', 'work'), _lf)
    if os.path.exists(_lp):
        a5n += io.open(_lp, encoding='utf-8', newline='').read()
# ★ 2026-09-23：W1 与 W2 的两份**记录**同列为数字权威（它们含逐格表与判定原文；
#   正文 §5.14/§8.2 引用的边界数值（如稀疏项 GT、未解析率）出处即在此）。
for _rf in ('W1_独立家族前瞻验证_结果_20260923.md', 'W2_闭源端点_结果_20260923.md'):
    _rp = os.path.join(NR(), _rf)
    if os.path.exists(_rp):
        a5n += io.open(_rp, encoding='utf-8', newline='').read()
W = lambda s: len(re.findall(r"[A-Za-z][A-Za-z'\-]*", s))

fails = []
def chk(name, ok, detail=''):
    print('  [%s] %-46s %s' % ('OK  ' if ok else 'FAIL', name, detail))
    if not ok:
        fails.append(name)

print('=' * 100)
print('英文稿统一校验')
print('=' * 100)

# ---------- A. 结构 ----------
print('\n[A] 结构完整性')
SEC = ['## Abstract', '## 1. Introduction', '## 2. Related Work', '## 3. Method', '## 4. Results I',
       '## 5. Results II', '## 6. Results III', '## 7. Discussion', '## 8. Limitations', '## References']
miss = [s for s in SEC if s not in en]
chk('章节 %d/%d' % (len(SEC) - len(miss), len(SEC)), not miss, str(miss or ''))

order = [int(m.group(1)) for m in re.finditer(r'^### 3\.(\d+) ', en, re.M)]
chk('§3 子节编号 1–9 连续', order == sorted(order) == list(range(1, 10)), str(order))

for chap, pat in [('2', r'^### 2\.(\d+) '), ('4', r'^### 4\.(\d+) '), ('5', r'^### 5\.(\d+) '),
                  ('7', r'^### 7\.(\d+) '), ('8', r'^### 8\.(\d+) ')]:
    o = [int(m.group(1)) for m in re.finditer(pat, en, re.M)]
    chk('§%s 子节编号连续（%d 节）' % (chap, len(o)), o == sorted(o) and o == list(range(1, len(o) + 1)), str(o))

# 10 个正文章节 + 1 个 Appendix C 指针段 + Abstract/keywords 之外的声明节 = 17 个 ## 标题
# ★ 2026-09-22：由 15 改为 17 —— 本轮按 PR 要求补上了 `## CRediT author contribution statement`
#   与 `## Acknowledgements`（官方 L627–L665 要求贡献声明，且致谢须独立成节、紧邻参考文献之前）。
#   这是**形式合规件**，不是内容膨胀；判据随之更新，并在此写明原因以便回溯。
h2 = re.findall(r'^## (.+)$', en, re.M)
chk('顶层标题 17 个（10 章 + 附录指针 + Abstract + PR 要求的 5 节声明/结论）',
    len(h2) == 17, '实际 %d' % len(h2))
chk('末位列 References 之后仅剩补充材料指针段',
    # ★ 2026-09-27（v0592）：本节的标题原为 `## Appendix C (separate supplementary file): migrated detail`，
    #   判据也写死成 `startswith('Appendix C')`。但补充材料里另有一个 `## Appendix C. The legibility
    #   proxy in full`，两者**同名不同物**；且"migrated detail"是迁移期的内部说法，[external-review]据此判为
    #   "迁移残留"（CONFIRMED）。现改名为 `## Supplementary material`，判据随之改绑该名。
    #   语义不变：它仍是 References 之后**唯一**的补充材料指针段（`h2[-2] == 'References'` 仍绑定）。
    h2[-1] == 'Supplementary material' and h2[-2] == 'References', str(h2[-2:]))

# ---------- B. 声称-限定对齐（§15.1 三方表） ----------
print('\n[B] 声称-限定对齐与形式要件')
DISC = ['Run-to-run non-determinism', 'Graded isolation', 'census of anomalous predictions',
        'Two runner defects', 'No attention-based criterion', 'Per-cell intervals are lower bounds',
        'optimal input fidelity was not located', 'attribution boundary is behavioural',
        'detector lineage is narrow', 'corpus is dominated by one lineage',
        'Domain composition is not systematic', 'not pre-registered as a whole',
        'power for the spectrum is low']
m2 = [d for d in DISC if d not in en]
chk('披露条目 %d/%d' % (len(DISC) - len(m2), len(DISC)), not m2, str(m2 or ''))

nprop = sum('Proposition %d' % k in en for k in (1, 2, 3, 4, 5, 6))
chk('命题 6/6（1–2 识别与口径，3–6 跨度/分解/标定/分层）', nprop == 6, '%d' % nprop)

# T1/A1/C1 降级后的措辞必须仍在（防止回退成泛化声称）
chk('A1 已降级为 open-weight + 血统限定', 'open-weight' in en and 'two lineages' in en)
chk('A2 已标注 GT 加权口径', 'ground-truth-weighted' in en)
chk('A7 实现效应 2–3.4×', '2–3.4' in en or '2-3.4' in en)
chk('P4 已声明与 §5.11(a) 的四格差值一致（措辞已改为一致性核对）',
    'Proposition 4 expresses this gap as' in en and 'consistency check on the numbers printed' in en)
chk('P5 已声明等变性（需 s≪1）', 's\\ll1' in en.replace('$\\ll$', '\\ll'))
chk('P6 已给出非序等价判据', 'legibility-consistent' in en)
chk('§8.1 已含实测离散上界 0.81 pp', '0.81 pp' in en)
chk('A8 同义反复已立为 Proposition 3',
    r'exactly $\pm 1$' in en and 'component of the' in en and 'magnitude is not predicted' in en)

# ---------- C. N1 附录交叉引用可解析 ----------
print('\n[C] 附录交叉引用可解析性（新增断言 N1）')
# ★ 2026-09-22：标题正则原为 `([A-M](?:\.\d+)?)`，**只能认到一层**（M.18），
#   于是正文新引用的二层小节（M.18.8）被判"未解析"。改为 `(?:\.\d+)*` 以接受 A.1.2 形式，
#   并把二层小节号（如 18.8）也加进结构号集合，避免它被当成"新造数字"。
supheads = set()
for m in re.finditer(r'^#{2,4}\s+(?:Appendix\s+)?([A-M](?:\.\d+)*)[\.\s]', sup, re.M):
    supheads.add(m.group(1))
refs = set(re.findall(r'Appendix\s+([A-M](?:\.\d+)*)', en))
refs |= set(re.findall(r'\(([A-M](?:\.\d+)+)\)', en))
unres = sorted(r for r in refs if r not in supheads)
chk('正文引用附录 %d 个，未解析 %d' % (len(refs), len(unres)), not unres,
    ('未解析: %s | 附录标题: %s' % (unres, sorted(supheads))) if unres else '')
chk('补充材料附录 A–M 齐全', set('ABCDEFGHIJKLM') <= set(h.split('.')[0] for h in supheads),
    str(sorted(set(h.split('.')[0] for h in supheads))))

# ---------- D. N2 搬出内容仍在附录 ----------
print('\n[D] 主文搬出内容仍在附录（新增断言 N2）')
MOVE = [('五分类名', 'answer_zero'), ('api_error 出分母', 'excluded from the denominator'),
        ('MD5 文件级去重', 'MD5'), ('条件身份行级去重', 'identity of the experimental condition'),
        ('逐 tile 解析', 'per tile'), ('238 条分歧', '238')]
bad_move = [n for n, s in MOVE if s not in sup]
chk('附录 B 承接搬出内容 %d/%d' % (len(MOVE) - len(bad_move), len(MOVE)), not bad_move, str(bad_move or ''))
chk('主文 §3.6 已指向附录 B.1–B.2', 'Appendix B.1–B.2' in en)

# ---------- E. 禁用串与语言 ----------
print('\n[E] 禁用串与语言纯净度')
#   ★ 2026-10-04（v0644）：「版本号」这一项加了 `(?<!/)` —— 对象是**我方内部版本号**（`v0617` 这类），
#     而新题录 [3] 的出版方 URL 里必然带 `/v97/`（PMLR 第 97 卷）。实测：未加该前缀排除时，
#     `press/v97/geifman19a.html` 会被判成"内部版本号"，属**判据没对上对象**（教训 07）。
#     URL 路径段不是内部版本号，故按"前面不是 `/`"排除；我方版本号从不出现在斜杠后。
BAD = [(r'⚠', '⚠'), (r'已撤回', '撤回'), (r'\bA\d{1,2}\b', '内部编号'),
       (r'(?<!/)\bv\d+\b', '版本号'),
       (r'PaperB_', '内部文档'), (r'[A-Za-z]:\\', '盘符'), (r'/root/', '服务器路径'),
       (r'pod_mirror', '内部机器名'), (r'盲审|六模型|七模型', '评审语'), (r'TODO|TBD|XXX', '占位'),
       (r'本节为待实验内容', '占位符'), (r'见\s*与|详见；', '悬空连接词')]
bad = {n: len(re.findall(p, en)) for p, n in BAD if re.findall(p, en)}
zh_res = len(re.findall(r'[\u4e00-\u9fff]', en))
chk('禁用串全 0', not bad, str(bad or '全 0'))
chk('中文残留 0', zh_res == 0, '%d' % zh_res)
chk('补充材料禁用串全 0', not [p for p, n in BAD if re.findall(p, sup)], '')
sup_zh_res = len(re.findall(r'[\u4e00-\u9fff]', sup))
chk('补充材料中文残留 0', sup_zh_res == 0, '%d' % sup_zh_res)

# ---------- F. 数字溯源 ----------
print('\n[F] 数字溯源（不得新造数字）')
nums = lambda s: set(re.findall(r'\d+(?:[.,]\d+)*', s))
en_flat = set(x.replace(',', '') for x in nums(en))
zh_flat = (set(x.replace(',', '') for x in nums(zh)) | set(x.replace(',', '') for x in nums(au))
           | set(x.replace(',', '') for x in nums(ar))
           | set(x.replace(',', '') for x in nums(e1n))
           | set(x.replace(',', '') for x in nums(e2n))
           | set(x.replace(',', '') for x in nums(rcn))
           | set(x.replace(',', '') for x in nums(v27n))
           | set(x.replace(',', '') for x in nums(a5n)))
WHITE = set(str(i) for i in range(0, 103))
ARXIV = set(x for x in nums(en) if re.fullmatch(r'\d{4}\.\d{4,5}', x))
# 结构性 token：章节号/附录号（从英文稿自身标题导出，不硬编码）
SECT = set()
for m in re.finditer(r'^#{2,4}\s+(\d+(?:\.\d+)*)(?=\s)', en, re.M):   # 数字标题，如 "### 3.9 "
    SECT.add(m.group(1))
for m in re.finditer(r'§\s*(\d+(?:\.\d+)*)', en):                      # 正文交叉引用，如 "(§3.1)"
    SECT.add(m.group(1))
# 附录二层小节号（M.18.8 → 18.8）：它们是**结构编号**而非"新造数字"，必须一并白名单，
# 否则正文引用附录小节会被 [F] 段误报为无法溯源的数字（2026-09-22 实测）。
for m in re.finditer(r'\b[A-M]\.(\d+\.\d+)\b', en):
    SECT.add(m.group(1))
# 书写等价的数字（附出处；每一条都写明为什么不是新造数字）
EQUIV = {
    # 中文定稿写「约 62 万条记录」（骨架 L13/L71/L80/L429），英文写 620k —— 同一量、同一出处
    '620': '中文「62 万」的英文写法（骨架 L13/L71/L80/L429）',
    # §7.3 的 0.07 是**推导值**：p≈0.008 是 9 个枚举分割点上的最小值 ⇒ 最小可校正值 ≈ 0.008×9。
    # 该句由 2026-09-20 的 v0487 轮[external-review]指出后补写，故不在中文定稿里。
    '0.07': '§7.3 多重校正后的最小可校正 p（= 0.008 × 9 个枚举分割点），2026-09-20 补写',
    # ★ 2026-09-29（v0605）：§7.3 新增**按旋钮聚类**的区间端点（簇级整块 bootstrap 2,000 次，
    #   种子 20260924）。它不是中文定稿里的数，因为该区间是本轮**新做的只读复算**；
    #   出处：`analysis/work/p3r2_plan_m37_cluster.py` →
    #   `analysis/work/p3r2_plan_m37_cluster_result.json`（判据件
    #   `p3r2_plan_m37cluster_criteria_frozen.json` 跑前冻结）；同一批读数印在补充材料 §F.7。
    '0.913': '§7.3 簇级（按旋钮整块）bootstrap 31 单元下沿，2026-09-29 v0605 只读复算',
    '0.994': '§7.3 簇级（按旋钮整块）bootstrap 31 单元上沿，2026-09-29 v0605 只读复算',
    # ★ 2026-09-30（v0607）：§7.3 的 per-unit isotonic 一组两个值（8 单元 0.571 / 36 单元 0.521）。
    #   更正前该处印的是 `0.571 / 0.548` —— 0.548 是**相邻那一行**（per-unit affine, refitted per
    #   level）的 36 单元值，属**串行**（[external-review][external-review] 蒸馏器发现，本轮一手核到）。
    #   0.571 与 0.521 都在**发布包内**的冻结件里：`code/analysis/perknob_rung_8unit_result.json`
    #   （md5 `63ceb33804756655956d873c13a8d62e`，见补充材料 §M.37 的 Reproduction 行），
    #   同一张表印在补充材料 §M.37 的 "per-unit isotonic" 行。0.521 不在中文定稿里（中文定稿没有该表），
    #   故按既有做法**登记于此并写明出处**，而不是放宽判据。
    '0.521': '§M.37 表 per-unit isotonic 行的 36 单元值（同一行 8 单元值 = 0.571）；'
             '冻结件 perknob_rung_8unit_result.json 在发布包内，2026-09-30 v0607 更正串行',
    # ★ 2026-10-01（v0619）：§7.3 补进 §M.37 的**抗重标度检验**那一组读数（主稿此前只写口径、
    #   不载这组数，[round][external-review]均指出）。三个值都**逐字印在补充材料 §M.37**：
    #   「…the Spearman against the ρ ordering falls to **0.629**, and under a per-item rank
    #   correlation … to **0.595** … Four subsets … all remain below 0.85 (**0.580–0.754**)」。
    #   故它们不是新造数字，只是首次被主稿引用。
    '0.595': '§M.37 的 per-item 秩相关 Spearman（抗任意单调重标度的最强形式）；同段印 0.629（log ratios）；'
             '2026-10-01 v0619 由主稿 §7.3 首次引用',
    '0.580': '§M.37 四子集 Spearman 区间下沿（补充材料逐字印作 0.580–0.754）；2026-10-01 v0619 首次进主稿',
    '0.754': '§M.37 四子集 Spearman 区间上沿（同上）；2026-10-01 v0619 首次进主稿',
    # §5.12 的 10/12 是主稿已印的计数；此处补的检验量即由它直接算出，故可复算：
    #   P(X≥10 | n=12, p=1/2) = (C(12,10)+C(12,11)+C(12,12))/2^12 = (66+12+1)/4096 = 0.019287
    '0.019': '主稿 §5.12 的 10/12 计数的精确二项检验 P(X≥10|n=12,p=1/2)=(66+12+1)/4096=0.0193；'
             '2026-10-01 v0619 由稿内已印计数直接算出（该节其他同类计数均带检验，此处原缺）',
    # §M.21.9 的单侧 Clopper–Pearson 批界（补充材料逐字印 3.92 pp）；主稿 §5.7 用它把 7 pp 带与批界区分开。
    '3.92': '§M.21.9 的单侧 Clopper–Pearson 批界（补充材料逐字印 3.92 pp）；'
            '2026-10-01 v0619 由主稿 §5.7 首次引用，用于把 7 pp 跨重复带与批界区分开',
    # 硬件规格常数：weight-and-activation 8-bit 需要 compute capability 8.9（公开规格）。
    # 印在 §M.46(c)（capability 8.9 / 本机 8.0 / W8A16 下限 7.5），主稿 §8.2 的保真度注记引用。
    '8.9': 'W8A8 推断所需的 compute capability（公开规格；本机为 8.0）；逐字印在 §M.46(c)；'
           '2026-10-01 起被主稿 §8.2 的保真度注记引用',
    # ★ 2026-10-04（v0645）：**新实验**（合成数值刺激上的 count × 可读性正交控制）第一次进主稿的四个读数。
    #   它们**不是新造数字**：逐字印在补充材料 §M.11.1（同轮新增），而 §M.11.1 的每个数都来自**随包放行**的
    #   判决书与逐项记录（`data/derived/a5_2_a800/a5_2_verdict.md`，md5
    #   `2f56d6609f9513c3d7e9e0b547a9a466`；`data/derived/a5_2_a800/` 下 18 个逐格 CSV 各 648 行，n = 11,664）。
    #   主稿 §5.6 只是**首次引用**这三个区间端点与一个池化率，故按既有做法**登记于此并写明出处**，
    #   而不是放宽 [F] 段判据（判据、白名单区间、权威档集合一字未改）。
    '4.3696': '§5.6 引用的新实验主效应 β_count_std（补充材料 §M.11.1 逐字印 −4.3696，Wald 95% CI '
              '[−4.8066, −3.9327]）；来源：随包判决书 data/derived/a5_2_a800/a5_2_verdict.md'
              '（md5 2f56d6609f9513c3d7e9e0b547a9a466）与 18 个逐格 CSV（n = 11,664）；2026-10-04 v0645 首次进主稿',
    '4.8066': '同上的 Wald 95% 区间下沿（补充材料 §M.11.1 逐字印 [−4.8066, −3.9327]）；'
              '来源同 4.3696；2026-10-04 v0645 首次进主稿',
    '3.9327': '同上的 Wald 95% 区间上沿（补充材料 §M.11.1 逐字印 [−4.8066, −3.9327]）；'
              '来源同 4.3696；2026-10-04 v0645 首次进主稿',
    '49.6': '§5.6 引用的新实验在 count = 8 档的池化答对率（补充材料 §M.11.1 逐字印 49.6% = 1930/3888；'
            '同段另有 32 档 2.1% 与 80 档 0.6% —— 那两个值已在权威档内）；来源同 4.3696；2026-10-04 v0645 首次进主稿',
}

# ★ 2026-10-04（v0644）：**随包摘要（md5）的数字片段**一并列为结构 token。
#   起因（实测）：主稿把随包件摘要逐字印在正文里（§5.14 的 `w1_prereg.json` 等）。摘要是
#   **标识符**，不是稿件声称的量；它的十进制片段能不能过 [F] 段，此前纯属**碰巧**
#   ——v0644 换发摘要后，新摘要 `0a42e6e5…1b075` 的三个片段 `89543` / `1522` / `075`
#   恰好不在任何权威档里，于是被 [F] 段报成"无法溯源"。正确处理与 `SECT` / `ARXIV` 同类：
#   **由文本自身导出**的结构白名单（只认 32 位十六进制字面量内部的片段），而不是放宽判据、
#   也不是把摘要片段逐条塞进 EQUIV。
MD5TOK = set()
for _m in re.finditer(r'\b[0-9a-f]{32}\b', en):
    MD5TOK |= set(re.findall(r'\d+(?:[.,]\d+)*', _m.group(0)))

missing = sorted((en_flat - zh_flat) - WHITE - ARXIV - SECT - set(EQUIV) - MD5TOK,
                 key=lambda s: -len(s))
chk('无法溯源的数字 token 0 个', not missing, str(missing[:12]))
print('      （白名单：0–102 结构数 %d；章节号 %d 个；书写等价 %d 条；随包摘要片段 %d 个）'
      % (len(WHITE), len(SECT), len(EQUIV), len(MD5TOK)))
# ★ 2026-09-24：把本门禁的**固有盲区显式报出来**。WHITE 是为"结构数"（臂数/格数/维数/格位等）设的，
#   但它对**恰好落在 0–102 的测量值**同样不设防：例如把 "2.6 pp" 误写成 "3.6 pp"、"36 pp" 误写成
#   "26 pp"，只要该 token 不出现在任何权威档里，本门禁**抓不到**。与其让它当隐含特权，不如印出来：
#   这些 token 本门禁不校验，必须由证据档/独立重算核对（M.40/M.41 一类的数字另有 anchor_m40m41.py）。
_only_white = sorted((en_flat - zh_flat - ARXIV - SECT - set(EQUIV)) & WHITE, key=lambda s: -len(s))
# ★★ 2026-09-24 自查（**一次自造永真断言的抓出与撤销**，留档以免重犯）：
#   我曾在此处加过一条硬检查「仅靠 0–102 白名单放行的 token 必须登记在册」，动机是担心
#   `WHITE` 对落在该区间的**测量值**静默放行（例如把 "2.6 pp" 写成 "3.6 pp" 抓不到）。
#   为证明它不是永真断言，写了阳性对照 `_posctrl_white_registry.py`：往英文稿里注入
#   0–102 中第一个不在权威档里的整数并按真实路径重跑 en_check。
#   **结果 3/3 不触发**；再加诊断打印才看清根因：`WHITE ⊆ zh_flat`——
#   0–102 每个整数都已在某份权威档里出现过 ⇒ `(… ) & WHITE` **恒为空集** ⇒ 那条检查
#   **永远为真**，它不会失败，也就什么都守护不了。⇒ 已删除该 chk（永真断言不是门禁，
#   留着只会让"全过"显得更可信而实际更虚）。
#   现在改为**把这条逻辑关系本身印出来并逐次校验**：若哪天 `WHITE ⊄ zh_flat`，
#   下面这行会变成 False，提示"白名单重新变成活的放行通道，需要重新评估"。
_white_dead = WHITE <= zh_flat
print('      ★ 白名单 0–102 在该门禁里是否**不起作用**：%s（判据：WHITE ⊆ 权威档数字集）' % _white_dead)
print('        ⇒ 意味着"仅靠白名单放行"的 token 不存在（实测 %d 个），'
      '且 [F] 的判别力**全部**来自权威档集合 zh_flat，不来自白名单。' % len(_only_white))
print('        ⇒ 本类检查**够不着**的唯一残余盲区：把测量值改错成"另一个在别处出现过的数"'
      '（集合成员判据对**数值正确性**无感）。数值级正确性靠**重算类**检查：表内算术自洽 /'
      ' 闭式 S 对账 / 82–94% 口径限定 / `_e1_indep_check.py`、`_e2_indep_check.py`'
      '（绕开生成器直接读原始 CSV）/ `anchor_m40m41.py`（288 值取值宇宙）。')
if not _white_dead:
    print('        ★★ 注意：白名单已不再是死代码 ⇒ "仅靠白名单放行"重新成为可能，'
          '当前有 %d 个 token 属此类，须逐个核对出处。' % len(_only_white))
    for _t in _only_white[:20]:
        _mm = re.search(r'.{0,46}\b' + re.escape(_t) + r'\b.{0,46}', en)
        print('          %-8s … %s' % (_t, (_mm.group(0) if _mm else '').replace('\n', ' ').strip()))
for k, v in EQUIV.items():
    print('      EQUIV %s ← %s' % (k, v))

# ---------- G. 篇幅（以**发布方的尺子**为合规判据；自订严尺子只作披露） ----------
# ★ 2026-09-22 修正：旧版把合规判据挂在 measurement.json（12 pt／双倍行距／2.54 cm）上，
#   那是**自订的严尺子**，期刊一项都不要求（PR L567/L569/L571：Word 用 1.5 倍、10 pt、边距 4.3/4.8）。
#   按自订尺子判会得到"36 页 ⇒ 超限"的假失败，并推动无意义地删内容。
#   现改为：合规看 ①真实交付件 .docx 的实测页数（measurement_pr_docx.json）
#   与 ②官方版式 RTF 代理（measurement_pr_layout.json）；自订严尺子照实印出并注明不代表期刊口径。
print('\n[G] 篇幅：实测优先，折算仅参考；**合规判据挂在发布方口径**')
# ★ 摘要长度门禁（2026-09-24 新增）：期刊要求 **≤250 词**。
#   为什么按**空白分词**判：期刊说 "250 words"，编辑/生产系统按 Word 的计数理解——**数字也算词**
#   （`82–94%` 记 1 个），而本文件其余地方的 `W()` 口径只数 `[A-Za-z][A-Za-z'-]*`（**不数数字**），
#   两套相差 36 词。取更严的那套当判据 ⇒ 两种解释都满足。
_ab_m = re.search(r'(?m)^##\s*Abstract\s*$', en)
_ab = en[_ab_m.end():en.find('\n## ', _ab_m.end())] if _ab_m else ''
_ab_ns = len(re.findall(r'\S+', _ab))
chk('摘要 ≤ 250 词（期刊口径=空白分词，数字也算词；同时打印本库口径）',
    bool(_ab_m) and _ab_ns <= 250,
    '空白分词 %d 词／本库口径 %d 词' % (_ab_ns, W(_ab)))
MEAS_DOCX = RP('measurement_pr_docx.json')
MEAS_PRL = NR('measurement_pr_layout.json')
MEAS = NR('measurement.json')          # 自订严尺子（仅披露）
w = W(en)
# 边界修正：正文 = `## References` 之前。原写法 W(en) − W(References…Appendix C) 会把
# 参考文献**之后**的 Appendix C 指针段算进正文（8,507 vs 正确 8,371，差 136 词）。
_i_ref = en.find('## References')
main_w = W(en[:_i_ref])
refs_w = W(en[_i_ref:en.find('## Appendix C')])
print('  折算参考：正文 %d 词 ≈ %.1f 页；含参考文献 %d 词 ≈ %.1f 页（折算不作合规判据）'
      % (main_w, main_w / 255.0, main_w + refs_w, (main_w + refs_w) / 255.0))
if not os.path.exists(MEAS_DOCX):
    chk('页数已实测（.docx 交付件）', False, 'measurement_pr_docx.json 缺失——页数必须实测，不接受折算')
else:
    dj = json.loads(io.open(MEAS_DOCX, encoding='utf-8', newline='').read())
    pages = dj['result']['pages']
    chk('实测页数 ≤ 35（PR 硬规则，**.docx 交付件 + 官方版式**）', pages <= dj['result']['limit_pages'],
        '%d 页（余量 %d 页；Word %s）' % (pages, dj['result']['margin_pages'], dj['layout']['body_pt']))
    _match = dj['inputs']['markdown_md5'] == hashlib.md5(en.encode('utf-8')).hexdigest()
    chk('实测输入与当前英文稿一致（.docx）', _match,
        ('一致（%s）' % dj['inputs']['markdown_md5'][:12]) if _match
        else '不一致 ⇒ 英文稿已改，须重跑 build_pr_docx.py + freeze_docx_measurement.py')
if os.path.exists(MEAS_PRL):
    pj = json.loads(io.open(MEAS_PRL, encoding='utf-8', newline='').read())
    pv = pj['variants'].get('titleA_fig7.5') or list(pj['variants'].values())[-1]
    ctl = pj.get('positive_control', {})
    chk('测量有效性（阳性对照：注入 %s 词，页数必须变化）' % ctl.get('injected_words'),
        bool(ctl.get('responded')),
        '%s → %s 页' % (ctl.get('pages_before'), ctl.get('pages_after')))
    print('  官方版式 RTF 代理：含图 %d 页 / 不含图 %d 页（判据同挂官方口径）'
          % (pv['pages'], pj['variants'].get('titleA_fignone', {}).get('pages', 0)))
if os.path.exists(MEAS):
    mdj = json.loads(io.open(MEAS, encoding='utf-8', newline='').read())
    pv2 = mdj['variants'].get('7.5cm') or mdj['variants'].get('none')
    print('  ⚠ 自订严尺子（12 pt／双倍行距／2.54 cm，**期刊一项都不要求**）：%d 页 —— 仅披露，不作判据'
          % pv2['pages'])
    rg = mdj.get('reference_growth', {})
    if rg:
        print('  参考文献增长实测：27 条=%s 页；35 条=%s 页；45 条=%s 页'
              % (rg.get('refs27'), rg.get('refs35'), rg.get('refs45')))

# ---------- G2. 区间一致性与术语（2026-09-20 由一轮[external-review]抓出的缺陷类别） ----------
print('\n[G2] 区间一致性与术语')
# (a) 区间一致性：正文任何"a–b%"的弃权份额声称，必须**明确限定其适用范围**，
#     且附录 J.1 的表不得出现超出该范围的互斥读数。
#     教训：正文写 82–94%，而附录 J.1 列了 95.7/98.4/99.4% —— [external-review][external-review] 一眼抓出。
_occ = [m for m in re.finditer(r'82–94%', en)]
# ★ 2026-09-22：判据放宽为"限定语出现 base arm **或** base contract arm"——两者都把该数字限定到
#   base 契约臂（正文 §5.5 用全称、摘要用简称），判据要看的是"有没有限定"，不是"用哪种写法"。
_scoped = [m for m in _occ
           if re.search(r'base (?:contract )?arm', en[max(0, m.start() - 400):m.end() + 400])]
chk('正文每处 82–94% 都标注了 base 臂限定', len(_occ) > 0 and len(_occ) == len(_scoped),
    '%d 处，其中带限定 %d 处' % (len(_occ), len(_scoped)))
chk('附录 J.1 声明 82–94% 的适用范围', 'Scope of the 82–94% headline' in sup)
chk('附录 J.1 仅列 canonical 主运行（派生重跑已排除）', 'canonical primary runs only' in sup)
chk('附录 J.1 给出全臂真实区间（含 42.5% 与 99.4%）', '42.5%' in sup and '99.4%' in sup)
# (b) 术语：`class` 不得同词两义（六个旋钮 vs 四个侧）
chk('已消除 "four classes"（应作 four sides）', 'four classes' not in en)
chk('已消除 "six knob classes"', 'six knob classes' not in (en + sup))
chk('附录 F.2 标题与表头用 knobs/side', 'The six knobs, their sides, and their spans' in sup
    and '| Family | Knob | Side |' in sup)

# ---------- G3. 负锚点：改掉的错话不得回来（2026-09-20 依 21 手册 §9.3） ----------
# 手册禁止把旧措辞列成负锚点，是因为**它的**审计语料含内部记录（记录按设计保留旧措辞）。
# 本项目校验语料只有送审件（en/sup），不含记录 ⇒ 负锚点安全，且正是防线。
print('\n[G3] 负锚点（已修正的错话不得回来）')
BANNED = [
    ('0.092 / 0.049 / 0.029', '无源的数字三元组（τ=0.5 的 pred/gt，实为别处的量）'),
    ('at $\\tau = 0.5$ the ratio of', '把"ladder 最高值"误标为"τ=0.5"的旧句'),
    ('four classes and ten units', '同词两义（应作 four knob sides）'),
    ('six knob classes', '同词两义（应作 six knobs）'),
    ('| Family | Knob | Class |', '与"四个侧"冲突的旧表头（应作 Side）'),
]
for _s, _why in BANNED:
    _hit = _s in en or _s in sup
    chk('已移除「%s」' % _why, not _hit, '命中位置：%s' % ('en' if _s in en else ('sup' if _s in sup else '无')))

# ---------- G4. 附录算术对账（2026-09-20 由 v0487 轮 3 份[external-review]的"三行除法"逼出） ----------
# 既有断言只查"字符串在不在"，**没有一条做算术对账**，于是 J.1 两张表口径不一致（分解表取派生重跑、
# S 表取主运行）在我们的守卫下全绿通过，却被三份[external-review]各自用三行除法当场证伪。
# ★ 本段循环变量一律加前缀 `_`：首发版本用 `w` 作循环变量，**遮蔽了全局词数 `w`**，
#   于是摘要行印出"英文稿 0 词"——同族（变量遮蔽）在本会话已出现三次。
print('\n[G4] 附录 J.1 算术对账（分解表 ⇄ 闭式 S ⇄ §5.11(a) 的 gap）')
try:
    _rowre = (r'(?m)^\|\s*([A-Za-z\-]+)\s*\|\s*(-?[\d.]+)%\s*\|\s*(-?[\d.]+)%\s*\|'
              r'\s*(-?[\d.]+)%\s*\|\s*(-?[\d.]+)%\s*\|\s*([\d.]+)\s*\|\s*(-?[\d.]+)%\s*\|')
    _rows = re.findall(_rowre, sup)
    chk('分解表可解析（含 w 与 ρ_ans 列）', len(_rows) >= 4, '%d 行' % len(_rows))
    _bad = []
    for _ds, _rt, _ab, _an, _tot, _wv, _rav in _rows:
        _rt, _ab, _an, _wv, _rav = (float(x) for x in (_rt, _ab, _an, _wv, _rav))
        if abs((_ab + _an) - _rt) > 0.02:
            _bad.append('%s 加法 %.2f+%.2f≠%.2f' % (_ds, _ab, _an, _rt))
        if abs(-(1 - _wv) * 100 - _ab) > 0.05 or abs(_wv * _rav - _an) > 0.05:
            _bad.append('%s w/ρ_ans 与分量不符' % _ds)
    chk('分解表逐行算术自洽（加法 + w/ρ_ans 反推）', not _bad, '；'.join(_bad[:3]) or '各行全对')
    _S = re.findall(r'(?m)^\|\s*Qwen3-VL-32B / ([A-Za-z\-]+)\s*\|\s*([\d.]+)%\s*\|', sup)
    _smap = {k.lower(): float(v) for k, v in _S}
    _mis = []
    for _ds, _rt, _ab, _an, _tot, _wv, _rav in _rows:
        _wv, _rav = float(_wv), float(_rav)
        if _rav >= 0:
            continue
        _sc = (1 - _wv) / (1 - _wv * (1 + _rav / 100)) * 100
        for _k, _v in _smap.items():
            if _ds[:4].lower() in _k or _k[:4] in _ds.lower():
                if abs(_sc - _v) > 0.6:
                    _mis.append('%s 闭式 %.1f vs 表 %.1f' % (_ds, _sc, _v))
    chk('闭式 S 与 S 表同值', not _mis, '；'.join(_mis[:3]) or '一致')
    _gaps = re.findall(r'\*\*(61\.3|57\.5|40\.6) pp\*\*', en)
    chk('§5.11(a) 的 gap 保留（61.3/57.5/40.6）', len(_gaps) >= 3, '%d 个' % len(_gaps))
    # J.4 行数**只在 J.4 段内**数（首发版本用全附录正则，把别处的 32B 行也数进来 ⇒ 6 数成 8）
    _i4 = sup.find('### J.4')
    _j4 = sup[_i4:sup.find('## Appendix K', _i4)] if _i4 > 0 else ''
    _j4rows = len(re.findall(r'(?m)^\|\s*32B\s*/', _j4))
    _wmap = {'six': 6, 'seven': 7, 'eight': 8}
    _div = re.findall(r'across the (\w+) such pairs', en)
    chk('§8.1 的 pairs 计数与 J.4 表行数一致',
        bool(_div) and _wmap.get(_div[0]) == _j4rows and _j4rows > 0,
        '§8.1=%s，J.4 %d 行' % (_div[0] if _div else '?', _j4rows))
except Exception as _e:
    chk('G4 算术对账可执行', False, '异常：%s' % _e)

# ---------- H. 补充材料 ----------
print('\n[H] 补充材料')
sw = W(sup)
print('  补充材料 %d 词；md5 %s' % (sw, hashlib.md5(sup.encode('utf-8')).hexdigest()[:12]))
print('  英文稿   %d 词；md5 %s' % (w, hashlib.md5(en.encode('utf-8')).hexdigest()[:12]))
# 上限从 4600 提到 5400：v0487 轮具名迁出把正文细节搬进补充材料（这是迁移的目的），
# 而 **PR 补充材料本身无页数上限** —— 这条只是可读性的软守卫，不是期刊规则。
# ★★ 2026-09-22（路线 A）：**从"绝对词数"改为"相对正文的比例"**。
#   原因：为满足**正文 35 页硬上限**，本轮把 §3.8 命题框架（约 1 250 词）逐字迁往附录 M.21，
#   绝对词数必然上升；再靠"上调阈值"放行会让守卫失去意义。
#   新口径：**补充材料 ≤ 1.35 × 正文词数**（正文词数取 .docx 实测），另加 15 000 词绝对兜底。
#   语义：补充材料是"附件"，不该长成第二篇论文；正文腾多少页，附件就最多长多少。
_mw = None
try:
    import json as _json
    _mj = _json.load(io.open(RP('measurement_pr_docx.json'), encoding='utf-8'))
    for _k in ('words', 'word_count', 'Words'):
        if isinstance(_mj.get(_k), int):
            _mw = _mj[_k]
            break
    if _mw is None:
        _s = _json.dumps(_mj)
        _m = re.search(r'"words"\s*:\s*(\d+)', _s)
        _mw = int(_m.group(1)) if _m else None
except Exception:
    _mw = None
if _mw:
    # ★ 口径演变（每次调整都留档，便于回溯；**不做静默放宽**）：
    #   11000 → 12000 → 12600 → 13000（绝对词数）→ 1.35× → 1.50× → 1.55× → **现在：绝对护栏为判据 + 比例仅作诊断**。
    #   为什么最终这样定（2026-09-23）：
    #     ① 期刊对补充材料**没有页数/词数上限**，真正的硬约束是正文 ≤35 页（由 [G] 对 .docx 的实测把守）；
    #     ② 正文已到 35 页**硬上限** ⇒ 正文词数被页限钉死，比例的分母不再可调；
    #     ③ 此时比例守卫不再度量"把正文论证挪进附录"（真正的注水），而只度量"页限装不下的证据量"——
    #        它会把**新实验的参考材料**（本轮 W1/W2：6 家族/6 血统 + 3 托管端点 + 示例臂）判为超标，
    #        而唯一的"合规"办法是删掉既有证据，这与"补充材料是证据的家"直接冲突；
    #     ④ 故以**绝对护栏 20,000 词**为通过判据（它本来就是设计里的"跑飞"护栏），比例照实打印供人判断。
    #   实测（2026-09-23）：补充材料 17,957 词、正文约 11,410 词（重建 .docx 后）、比例 1.57、护栏余量 2,043 词。
    ratio = sw / float(_mw)
    # ★ 2026-09-23：自订绝对护栏 20,000 → **20,500**。唯一理由是容纳 **M.37** 的**新测量**
    #   （逐 unit 留出重拟合的排序分布 + 校准尺度 s 的分布）；**不含任何复述、导语、总结段**。
    #   期刊对补充材料**无**页数/词数上限，此数纯属自订 ⇒ 上调一事同时在**补充材料开头**与
    #   `改稿记录_排序口径边界与校准族_记录_P3_20260923.md` 中披露（裁决 Q1 的三条件）。
    # ★ 2026-09-23（第二次上调）：20,500 → **21,000**。**与上一次同源、同条件**——首次上调写明的条件就是
    #   "**只收新测量**、禁复述"；E-A（真零识别对照）是一次**新的实测实验**（真零池 + 5 家族 × 3 臂），
    #   不是复述 ⇒ 满足该条件。三条件齐备：只收新测量、在**补充材料开头**写明理由与日期、在记录文件里披露。
    # ★ 2026-09-24：**取消自订上限**（用户口径："补充材料干脆不要设上限，但是每次加完要看一下词数"）。
    #   依据：期刊对补充材料**本来就没有**词数/页数上限（这一条自 20,000 起就是自订的）；
    #   历次加帽（20000→20500→21000→21500→21700→22100→22400→22600→22700→22800→23500→24500）
    #   每次都要改三处并重新论证，成本落在"改措辞"而不是"改证据"上。
    #   ⇒ 现在**只记录、不判据**：词数照实打印，主稿页限仍由 [G] 的 Word 实测把守（那才是硬约束）。
    #   保留一行历史说明，便于回溯"曾经有过护栏、为什么撤掉"。
    print('      [记录] 补充材料 %d 词（**自订上限已取消**：期刊对补充材料无词数上限，此数仅作记录，'
          '不作判据；历史护栏 20000→…→24500 于 2026-09-24 撤除）' % sw)
    print('      [诊断] 补充材料/正文 词数比 = %.2f（%.0f%%，仅作记录，不作判据）' % (ratio, 100 * ratio))
else:
    print('      [记录] 补充材料 %d 词（正文词数读不到；无自订上限，仅记录）' % sw)
# 历史（保留，便于回溯）：11000 → 12000 → 12600 → 13000 皆为"绝对词数"口径，已被上面替换。
#   官方对补充材料**没有页数/词数上限**，故这是自订软守卫；
#   真正的硬约束（正文 ≤35 页）由上面 [G] 的实测判据把守。

# ---------- I. 投稿包同步 ----------
print('\n[I] 投稿包同步')
for src, dst in [(EN, NR('review_pkg_20260919', '06_英文稿_EN.md')),
                 (SUP, NR('review_pkg_20260919', '08_英文补充材料_Supplementary.md'))]:
    if os.path.exists(dst):
        same = io.open(src, encoding='utf-8', newline='').read().replace('\r\n', '\n') == \
               io.open(dst, encoding='utf-8', newline='').read().replace('\r\n', '\n')
        chk('同步 %s' % os.path.basename(dst), same, '' if same else '内容不一致，需重建投稿包')
    else:
        chk('同步 %s' % os.path.basename(dst), False, '文件不存在')

print('\n' + '=' * 100)
print('失败 %d 项%s' % (len(fails), ('：' + '；'.join(fails)) if fails else ' ✓ 全过'))
print('=' * 100)
sys.exit(0 if not fails else 1)
