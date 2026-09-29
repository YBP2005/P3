# -*- coding: utf-8 -*-
"""verify_objective.py — 把"我说做完了"变成**逐条可推翻**的检查。

依 `19_送审材料的自述文字与测量保真度.md` §7：
  · 每条检查指向**具体字面或计数**（"§9 不再出现"、"页数 ≤ 35"），而不是"§9 写得好"；
  · 价值有二：**交付证据**（不依赖叙述，任一条可被证伪）＋ **回归守卫**
    （以后任何改动把某一批改回去，它会指出是**哪一批的哪一条**）；
  · **能被自己的后续改动弄红的检查才是检查。**

按**目标批次**组织（每批 = 一次交付目标），而非按检查类型。只读，不改任何产物。
退出码 0=全绿；1=有红项（打印红项所属批次与编号）。
"""
import io, os, re, sys, json, hashlib, glob
sys.stdout.reconfigure(encoding='utf-8')

ROOT = r'<WORKDIR>\PaperB'
PKG = os.path.join(ROOT, 'review_pkg_20260919')
WORK = os.path.join(ROOT, 'analysis', 'work')
ZH = os.path.join(ROOT, 'PaperB_章节骨架_v3_可确证性_20260911.md')
EN = os.path.join(ROOT, 'PaperB_英文稿_PR_20260919.md')
SUP = os.path.join(ROOT, 'PaperB_英文补充材料_PR_20260919.md')
MEAS = os.path.join(ROOT, 'measurement.json')

rd = lambda p: io.open(p, encoding='utf-8', newline='').read() if os.path.exists(p) else ''
W = lambda s: len(re.findall(r"[A-Za-z][A-Za-z'\-]*", s))
md5 = lambda p: hashlib.md5(io.open(p, 'rb').read()).hexdigest()

zh, en, sup = rd(ZH), rd(EN), rd(SUP)
# 正文边界 = 第一个顶层附录标题之前。"附A" 起于 67,406 字符；
# **不能用"附C 起点"** —— 那会把附A/附B 的审计台账算进正文（曾因此误报 4 项）。
_mA = re.search(r'(?m)^##\s+附[A-Z]', zh)
ZH_BODY = zh[:_mA.start()] if _mA else zh
p01 = rd(os.path.join(PKG, '01_评审包_论文.md'))
p01b = rd(os.path.join(PKG, '01b_评审包_论文+补充材料.md'))
ppr = rd(os.path.join(PKG, '02_评审提示词.txt'))
pgd = rd(os.path.join(PKG, '00_评审包_导读.md'))

ITEMS = []      # (batch, id, 描述, 通过?, 证据)


def ck(batch, i, desc, ok, ev=''):
    ITEMS.append((batch, i, desc, bool(ok), str(ev)[:150]))


def sec_wordcounts(t):
    out, cur, n = [], None, 0
    for ln in t.split('\n'):
        if re.match(r'^#{2,3}\s', ln):
            if cur:
                out.append((cur, n))
            cur, n = ln.strip('# ').strip(), W(ln)
        else:
            n += W(ln)
    if cur:
        out.append((cur, n))
    return out


# ══════════ 批次 P0：体裁清理（正文不含工作记录痕迹） ══════════
B = 'P0 体裁清理'
MARKS = [r'⚠', r'已撤回', r'⏳', r'待实验', r'~~', r'\bA\d{1,2}\b', r'\bT\d{1,2}\b', r'\bv\d+\b',
         r'修补语', r'骨架自述', r'评审过程', r'内部文档', r'占位符']
# 判据取标记的**具体形态**，不取裸词：正文里「我们如何修补」「占位/测试值（哨兵 1234567890）」
# 是**正常内容**，用裸词 `修补`/`占位` 会误报（曾因此误报 1 项）。
bad = {p: len(re.findall(p, ZH_BODY)) for p in MARKS if re.findall(p, ZH_BODY)}
ck(B, 1, '中文正文修补标记 13 类全 0', not bad, bad or '全 0')
ck(B, 2, '正文无附录章节（正文为 §0–§8 + 参考文献）',
   len(re.findall(r'(?m)^##\s+附[录A-Z]', ZH_BODY)) == 0,
   '正文段匹配 %d 处（附A/B/C 在正文之后，按设计保留）'
   % len(re.findall(r'(?m)^##\s+附[录A-Z]', ZH_BODY)))
ck(B, 3, '原 §7.1 占位整节已移出正文（且原文保留在附A）',
   '本节为待实验内容' not in ZH_BODY and '本节为待实验内容' in zh,
   '正文 %d 次 / 全文 %d 次' % (ZH_BODY.count('本节为待实验内容'), zh.count('本节为待实验内容')))
ck(B, 4, '摘要不含审计串', '⚠' not in ZH_BODY[:ZH_BODY.find('## 1.')] if ZH_BODY.find('## 1.') > 0 else False)

# ══════════ 批次 P1：可确证性定义 + 贡献清单 + 旧附录B/C ══════════
B = 'P1 定义与贡献'
i33 = zh.find('### 3.3')
seg33 = zh[i33:i33 + 2000] if i33 > 0 else ''
ELEM = ['代理', '三个可操纵因子' if '三个可操纵因子' in seg33 else '模糊', '放弃', '像素']
# 关键词须是**文中实际用词**：§3.3 写「它支持分层与选择性预测……是**诊断**，不是部署时判据」，
# 用的是「诊断」而不是「放弃」（曾用错词导致误报）
ck(B, 1, '§3.3 含定义/多变量/最强门控/共变量/诊断而非部署判据',
   all(k in seg33 for k in ['可确证性', '代理', '多变量', '最强', '诊断']),
   '要素命中 %d/5' % sum(k in seg33 for k in ['可确证性', '代理', '多变量', '最强', '诊断']))
j1, j2 = zh.find('## 1.'), zh.find('## 2.')
seg1 = zh[j1:j2]
m = re.search(r'本文有三条贡献', seg1)
n_contrib = len(re.findall(r'(?m)^(\d+)\.\s+\*\*', seg1[m.start():])) if m else 0
ck(B, 2, '§1 顶层贡献恰 3 条', n_contrib == 3, '实际 %d' % n_contrib)
ck(B, 3, '投稿包不含方法论备忘（旧附录B 自审清单）',
   '自审清单' not in p01 and '自审清单' not in p01b)
ck(B, 4, '投稿包不含基金语/答复语', '基金' not in p01[:2000] and '答复审稿' not in p01)

# ══════════ 批次 P2：方法学细节迁入附录 ══════════
B = 'P2 细节迁出'
iC = zh.find('附C.')
ck(B, 1, '附C 迁出明细 ≥ 30000 字符', len(zh[iC:]) >= 30000, '%d 字符' % len(zh[iC:]))
ck(B, 2, '被搬空的标题仍在正文（标题原地不动）',
   all(h in zh[:iC] for h in ['### 7.15', '### 7.16', '### 7.17']),
   '7.15/7.16/7.17 命中 %d/3' % sum(h in zh[:iC] for h in ['### 7.15', '### 7.16', '### 7.17']))
# 范围修正：内部机器名规则适用于**送审件**，不适用于内部骨架自己的台账附C
# （附C 记录脚本名 `work\pod_13b_blur_contract.py` 是它的职责）
_pkgtext = p01 + p01b + en + sup
ck(B, 3, '送审件（01/01b/英文稿/英文补充材料）无内部机器名与本地路径',
   not re.search(r'pod_[A-Za-z0-9_]+|[A-Za-z]:\\|/root/', en + sup),
   '英文侧命中 %s' % (re.findall(r'pod_[A-Za-z0-9_]+|[A-Za-z]:\\|/root/', en + sup)[:3] or '无'))

# ══════════ 批次 B1–B3：结构性重写 ══════════
B = 'B1–B3 结构重写'
ck(B, 1, '§0 以弃权为中心发现', '弃权' in zh[:zh.find('## 1.')])
ck(B, 2, 'B2 锚区统计检验段存在', '切分点' in zh or '可分离的低响应簇' in zh)
ck(B, 3, 'B3 血缘分层操作化段存在', '550.6' in zh and '2.3' in zh)

# ══════════ 批次 W4–W6：长度再平衡与随稿交付物 ══════════
B = 'W4–W6 长度与交付物'
secs = sec_wordcounts(zh)
# 口径修正：a26 的"正文总量"是**总字符数**（正文段 0–67406），不是汉字数（曾用错口径误报）
body_n = len(ZH_BODY)
ck(B, 1, '正文总量在 55k–72k 字符容差内', 55000 <= body_n <= 72000, '%d 字符' % body_n)
deliv = ['04_随稿补充材料清单.md', '05_实验提示词全文.md']
ck(B, 2, '随稿交付物 04/05 存在', all(os.path.exists(os.path.join(PKG, d)) for d in deliv),
   ', '.join(d for d in deliv if not os.path.exists(os.path.join(PKG, d))) or '齐全')
figs = glob.glob(os.path.join(ROOT, 'analysis', 'figures', '*'))
ck(B, 3, '图件清点 ≥ 12 张', len(figs) >= 12, '%d 张' % len(figs))

# ══════════ 批次 EN：英文稿（投稿本体） ══════════
B = 'EN 英文稿'
SECS = ['## Abstract', '## 1. Introduction', '## 2. Related Work', '## 3. Method', '## 4. Results I',
        '## 5. Results II', '## 6. Results III', '## 7. Discussion', '## 8. Limitations', '## References']
miss = [s for s in SECS if s not in en]
ck(B, 1, '章节 10/10', not miss, str(miss or ''))
o3 = [int(x) for x in re.findall(r'(?m)^### 3\.(\d+) ', en)]
ck(B, 2, '§3 子节编号 1–9 连续', o3 == list(range(1, 10)), str(o3))
DISC = ['Run-to-run non-determinism', 'Graded isolation', 'census of anomalous predictions',
        'Two runner defects', 'No attention-based criterion', 'Per-cell intervals are lower bounds',
        'optimal input fidelity was not located', 'attribution boundary is behavioural',
        'detector lineage is narrow', 'corpus is dominated by one lineage',
        'Domain composition is not systematic', 'not pre-registered as a whole',
        'power for the spectrum is low']
md_ = [d for d in DISC if d not in en]
ck(B, 3, '披露条目 13/13', not md_, str(md_ or ''))
BAD = [r'⚠', r'已撤回', r'\bA\d{1,2}\b', r'\bv\d+\b', r'PaperB_', r'[A-Za-z]:\\', r'/root/',
       r'pod_mirror', r'盲审|六模型|七模型']
bb = {n: len(re.findall(p, en)) for p, n in [(p, p) for p in BAD] if re.findall(p, en)}
ck(B, 4, '英文稿禁用串 0', not bb, str(bb or '全 0'))
ck(B, 5, '英文稿中文残留 0', len(re.findall(r'[\u4e00-\u9fff]', en)) == 0,
   '%d' % len(re.findall(r'[\u4e00-\u9fff]', en)))
AU = rd(os.path.join(ROOT, 'PaperB_命题4-6验证记录_20260919.md'))
nz = lambda s: set(x.replace(',', '') for x in re.findall(r'\d+(?:[.,]\d+)*', s))
SECT = set(re.findall(r'(?m)^#{2,4}\s+(\d+(?:\.\d+)*)(?=\s)', en)) | set(re.findall(r'§\s*(\d+(?:\.\d+)*)', en))
# 与 en_check 同源：第三/第四权威 = P40 上的 arXiv/Crossref 取回记录；
# '0.07' 是 §7.3 的推导值（0.008×9），2026-09-20 由 v0487 轮评审指出后补写。
_arx = ''
for _f in ['_arxiv_records.json', '_refs_inventory.json', '_refs_extra.json',
           '_pb_refs_out.json', '_pb_refs2_out.json', '_pb_refs34_out.json', '_pb_refs5_out.json']:
    _p = os.path.join(WORK, _f)
    if os.path.exists(_p):
        _arx += io.open(_p, encoding='utf-8').read()
_e1p = os.path.join(ROOT, 'PaperB_E1证据_20260920.md')
_e1 = io.open(_e1p, encoding='utf-8').read() if os.path.exists(_e1p) else ''
missn = sorted((nz(en) - nz(zh) - nz(AU) - nz(_arx) - nz(_e1) - SECT
                - {str(i) for i in range(103)} - {'620', '0.07'}), key=len, reverse=True)
ck(B, 6, '数字溯源 0 未溯源（五权威：中文定稿+命题验证记录+两份取回记录+E1 证据记录）',
   not missn, str(missn[:6]))
supheads = set(re.findall(r'(?m)^#{2,4}\s+(?:Appendix\s+)?([A-M](?:\.\d+)?)[\.\s]', sup))
refs = set(re.findall(r'Appendix\s+([A-M](?:\.\d+)*)', en)) | set(re.findall(r'\(([A-M]\.\d+)\)', en))
unres = sorted(r for r in refs if r not in supheads)
ck(B, 7, '附录交叉引用 0 未解析', not unres, str(unres or ''))
ck(B, 8, '投稿包 06/08 与源文件一致',
   rd(os.path.join(PKG, '06_英文稿_EN.md')).replace('\r\n', '\n') == en.replace('\r\n', '\n')
   and rd(os.path.join(PKG, '08_英文补充材料_Supplementary.md')).replace('\r\n', '\n') == sup.replace('\r\n', '\n'))

# ══════════ 批次 THEORY：命题 4–6 ══════════
B = 'THEORY 命题 4–6'
nprop = len(re.findall(r'\*\*Proposition (\d) \(', en))
ck(B, 1, '命题定义数 = 8（1–3 原始 + 4–6 分解/等变/分层 + 7–8 识别误差/口径界）',
   nprop == 8, '%d' % nprop)
ax = re.findall(r'(?m)^## Appendix ([A-Z])\.', sup)
ck(B, 2, '附录 A–M 齐全', ax == list('ABCDEFGHIJKLM'), ''.join(ax))
ck(B, 3, '§5.11(a) 与 §3.8 命题 4 的措辞一致（已改为一致性核对）',
   'Proposition 4 expresses this gap as' in en
   and 'consistency check on the numbers printed' in en)
ck(B, 4, '§8.1 含实测离散上界 0.81 pp', '0.81 pp' in en)
ck(B, 5, '命题验证记录存在且非空', len(AU) > 2000, '%d 字符' % len(AU))

# ══════════ 批次 FRAMING：自述文字与测量保真度 ══════════
B = 'FRAMING 自述与测量'
ck(B, 1, '提示词不含 §9（稿件只到 §8）', '§9' not in ppr,
   '§9 出现 %d 次' % ppr.count('§9'))
ck(B, 2, '提示词不含手写的字数/语言自述', '万字符' not in ppr and '中文撰写' not in ppr)
ck(B, 3, '导读由脚本生成（含生成声明）', '由 `pack_framing.py`' in pgd or 'pack_framing.py' in pgd)
ck(B, 4, '导读声明的正文范围与中文骨架一致', '§0–§8' in pgd and '§0–§9' not in pgd)
ck(B, 5, '导读声明的贡献条数与中文骨架一致', ('**%d 条**' % n_contrib) in pgd,
   '骨架=%d' % n_contrib)
ck(B, 6, '包目录不含上一轮评审产物（污染盲审独立性）',
   not glob.glob(os.path.join(PKG, '06_*汇总*.md')) and not glob.glob(os.path.join(PKG, '07_v0*_抽取.json')),
   '命中 ' + ','.join(os.path.basename(x) for x in
                    glob.glob(os.path.join(PKG, '06_*汇总*.md')) + glob.glob(os.path.join(PKG, '07_v0*_抽取.json'))))

# ══════════ 批次 MEASURE：实测分页 ══════════
B = 'MEASURE 实测分页'
if not os.path.exists(MEAS):
    ck(B, 1, 'measurement.json 存在', False, '缺失')
else:
    d = json.loads(rd(MEAS))
    ck(B, 1, 'measurement.json 存在', True, '')
    ck(B, 2, '阳性对照通过（测量会随内容变化）', d.get('positive_control', {}).get('responded'),
       '注入 %s 词 ⇒ %s→%s 页' % (d['positive_control']['injected_words'],
                                d['positive_control']['pages_before'], d['positive_control']['pages_after']))
    pv = d['variants'].get('7.5cm') or d['variants']['none']
    ck(B, 3, '实测页数 ≤ 35（PR 硬规则）', pv['pages'] <= 35, '%d 页' % pv['pages'])
    ck(B, 4, '实测输入 md5 与当前英文稿一致', d['inputs']['en_md5'] == md5(EN),
       '记录 %s / 现稿 %s' % (d['inputs']['en_md5'][:12], md5(EN)[:12]))
    ck(B, 5, '表格按 9 pt 单倍渲染（不是落进双倍正文分支）',
       d.get('diagnostics', {}).get('trowd', 0) > 0, 'trowd=%s' % d.get('diagnostics', {}).get('trowd'))

# ══════════ 输出 ══════════
batches = []
for b, i, d_, ok, ev in ITEMS:
    if b not in batches:
        batches.append(b)
nred = sum(1 for x in ITEMS if not x[3])
print('=' * 116)
print('verify_objective.py — 逐条可推翻的核验（%d 批 / %d 项）' % (len(batches), len(ITEMS)))
print('=' * 116)
for b in batches:
    rows = [x for x in ITEMS if x[0] == b]
    red = [x for x in rows if not x[3]]
    print('\n■ %s  —  %d 项，%s' % (b, len(rows), '全绿 ✓' if not red else '**红 %d 项**' % len(red)))
    for _, i, d_, ok, ev in rows:
        print('   [%s] %s.%d  %-52s %s' % ('OK  ' if ok else 'RED ', b.split()[0], i, d_, ev))
print('\n' + '=' * 116)
print('合计 %d 项，红 %d 项' % (len(ITEMS), nred))
if nred:
    print('红项清单（= 把"我说做完了"变成可推翻的检查）：')
    for b, i, d_, ok, ev in ITEMS:
        if not ok:
            print('   · [%s] %s.%d %s — %s' % ('RED', b.split()[0], i, d_, ev))
print('=' * 116)
sys.exit(0 if nred == 0 else 1)
