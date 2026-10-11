# -*- coding: utf-8 -*-
"""derive_release_numbers.py — 放行树 README 的**摘要类数字一律从实物派生**（不手写）。

为什么要有这一支（准则 §7「派生守卫」）：README 里同时出现过**同一件文件的三套 md5**
（论文印一套、MANIFEST 记一套、README 又写一套），还有一句**为假的全称句**
（"No other 32-hex digest … matches any file this package ships"）。手抄的数字必然漂移；
本次把这几类数字改成**当场算出来、并硬断言**。

派生源（都在包内，第三方可复跑）：
  · `MANIFEST.csv`      —— 全树 path/bytes/md5 清单；
  · 磁盘实物            —— 逐行核对 bytes 与 md5；
  · 论文与补充材料      —— 印在里面的 32 位十六进制摘要；
  · `_sanitize_log_sync_repro.json`（★ 作者侧，不随包发布）—— 消毒台账：每个被改写文件的
                          消毒前 md5 / 进包后 md5 / 替换处数。

用法：
    python derive_release_numbers.py            # 只核对 + 打印（不写盘）
    python derive_release_numbers.py --check    # 同上（显式）
    python derive_release_numbers.py --selftest # 只核对 + ⑥ 的正反例自测（不写盘）
    python derive_release_numbers.py --apply    # 写回 README.md（须显式）

★ v0656 起本支另含 **⑥ 持久陈旧串断言**：一个 append-only 注册表（旧叙述 / 旧计数 / 旧"发布形态"
  摘要）必须在**替换后的 README** 里 **0 命中**；`--selftest` 跑正例（当前 README 绿）与负例
  （注入陈旧串必须红）。该断言已挂进 `final_gates.py` 的调用链（⑦）。判据**只加不放宽**。
"""
import csv
import hashlib
import io
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')
try:
    from _repro_root import resolve as RP, not_released as NR
except ImportError:                      # 只拷走单个脚本时
    import os as _o
    _r = _o.environ.get('PAPERB_ROOT') or _o.path.dirname(_o.path.dirname(_o.path.abspath(__file__)))
    RP = lambda *p: _o.path.join(_r, *p)
    NR = lambda *p: _o.path.join(_r, '_NOT_RELEASED', *p)

APPLY = '--apply' in sys.argv
ROOT = os.path.normpath(RP('repro_github'))
README = os.path.join(ROOT, 'README.md')
MANIFEST = os.path.join(ROOT, 'MANIFEST.csv')
MANUS = RP('PaperB_英文稿_PR_20260919.md')
SUPP = RP('PaperB_英文补充材料_PR_20260919.md')
SANLOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), '_sanitize_log_sync_repro.json')
FAILS = []
if not os.path.exists(README):
    sys.exit('!! 找不到放行树 README：%s（本支应在作者树或放行树根上运行）' % README)


def md5f(p):
    h = hashlib.md5()
    with io.open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest().upper()


def rd(p):
    return io.open(p, encoding='utf-8').read()


def check(desc, got, want):
    ok = got == want
    print('  %-58s %s' % (desc, 'OK' if ok else '★不符（实测 %s / 期望 %s）' % (got, want)))
    if not ok:
        FAILS.append(desc)
    return ok


# ── ① MANIFEST 与磁盘逐行核对 ───────────────────────────────────────────────
rows = []
for r in csv.reader(io.open(MANIFEST, encoding='utf-8')):
    if len(r) >= 3 and r[0] != 'path':
        rows.append((r[0], int(r[1]), r[2].upper()))
print('MANIFEST.csv：%d 行' % len(rows))
print('  论文 = %s | 补充材料 = %s' % (MANUS, SUPP))
by_path = dict((p, m) for p, _b, m in rows)
by_md5 = {}
for p, _b, m in rows:
    by_md5.setdefault(m.lower(), p)
bad_bytes = bad_md5 = missing = 0
for p, b, m in rows:
    fp = os.path.join(ROOT, p.replace('/', os.sep))
    if not os.path.exists(fp):
        missing += 1
        continue
    if os.path.getsize(fp) != b:
        bad_bytes += 1
    if md5f(fp) != m:
        bad_md5 += 1
check('MANIFEST 行：磁盘缺失', missing, 0)
check('MANIFEST 行：字节数不符', bad_bytes, 0)
check('MANIFEST 行：md5 不符', bad_md5, 0)

disk = []
for dp, dn, fn in os.walk(ROOT):
    dn[:] = [d for d in dn if d != '.git']
    for f in fn:
        disk.append(os.path.relpath(os.path.join(dp, f), ROOT).replace(os.sep, '/'))
check('目录文件数 − MANIFEST 行数（应恰为 MANIFEST.csv 与 data.zip）',
      len(disk) - len(rows), 2)
N_MAN = len(rows)
N_DATA = sum(1 for p, _b, _m in rows if p.startswith('data/'))

# ── ★ 2026-10-06（v0655）：`data/` 的"消毒器改了没有"必须**算**，不能写死 ──────────────────
#   起因（本次核到的**既存假全称句**）：README 写「Nothing under `data/` was altered … a scan of all
#   <N> released data files finds **zero** placeholder patterns」。实测 `data/` 下**早已有** 1 件
#   带占位符（`data/derived/a5_2_a800/env/_a52_运行单.md` 的 `<WORKDIR>`）＋1 件带中性内部名占位符
#   （判据件的 `<INTERNAL-ITEM-NOTE>` / `<INTERNAL-PLAN-DIR>`），共 **2** 件被消毒改写。该句在 v0655
#   之前就是**假**的，本次又新增 2 件（扩构建两份报告），故改为**当场派生**三个计数：
#     N_DATA_SAN   = 消毒台账里 `data/` 下的路径数（"被改写"）
#     N_PH_DATA    = `data/` 下内容命中六种占位符图案的件数（"看得见占位"）
#     其余         = N_DATA − N_DATA_SAN（逐字节相同的那些）
_RX_PH = re.compile(r'<REDACTED-|<WORKDIR>|<SHARED-DIR>')
N_PH_DATA = 0
for _p, _b, _m in rows:
    if not _p.startswith('data/'):
        continue
    _fp = os.path.join(ROOT, _p.replace('/', os.sep))
    try:
        _s = io.open(_fp, encoding='utf-8').read()
    except (UnicodeDecodeError, OSError):
        continue
    if _RX_PH.search(_s):
        N_PH_DATA += 1
N_DATA_SAN = 0
N_DATA_SAN_SRC = '（无）'
if os.path.exists(SANLOG):
    try:
        _sl = json.loads(io.open(SANLOG, encoding='utf-8').read())
        N_DATA_SAN = len([f for f in _sl['files'] if f['path'].startswith('data/')])
        N_DATA_SAN_SRC = '作者侧消毒台账'
    except Exception:
        N_DATA_SAN = 0
else:
    # ★ v0656 修（**本次核出的既存缺陷**，不是本次引入）：作者侧消毒台账**按设计不随包**，于是
    #   在**放行树里**直接跑本支（包外复核时会这么做）时，上面这条断言必然 `3 ≤ 0` 报红、
    #   而 §5 里依赖同一算量的那条替换也会"两边都不命中"而报红 —— 真因只是"放行树没有台账"，
    #   与 v0654 已修过的那一类缺陷**同源**（见下 §5 那条注释）。
    #   处置：退回到 **README 自己的消毒表**（它是台账的**派生形态**，且本支要重写的那句话说的
    #   正是 "the `data/` rows of the table above"）。这不是循环论证：作者树里仍以台账为准，
    #   两条路径在作者树里已实测**同值**（放行树：34 行 / 68 处替换 / `data/` 4 行）。
    try:
        _rows_san = re.findall(
            r'(?m)^\|\s*`([^`|]+)`\s*\|\s*(\d+)\s*\|\s*`([0-9A-Fa-f]{32})`\s*\|'
            r'\s*`([0-9A-Fa-f]{32})`\s*\|', rd(README))
        N_DATA_SAN = len([r for r in _rows_san if r[0].startswith('data/')])
        N_DATA_SAN_SRC = 'README 消毒表（台账缺席时的派生形态）'
    except Exception:
        N_DATA_SAN = 0
print('  「data/ 被改写」来源：%s ⇒ %d 件' % (N_DATA_SAN_SRC, N_DATA_SAN))
check('data/ 下含占位符的件数 ≤ 台账里 data/ 被改写的件数', N_PH_DATA <= N_DATA_SAN, True)
print('data/：%d 件；台账登记被改写 %d 件；内容命中占位符 %d 件（其余 %d 件应与源逐字节相同）'
      % (N_DATA, N_DATA_SAN, N_PH_DATA, N_DATA - N_DATA_SAN))

# ── ①b 冻结件旁车（`*.md5`）：登记值必须等于**产物实物 md5**（★ v0654 新增）──────────
#   起因（一次全树复核实测到**旁车登记值与产物实物不一致**，而**上面那三条断言全是绿的**）：
#     `code/analysis/m37_ci_power_result.json.md5` 的**内容**登记 `44D5AE2E…`，而它所指的
#     `m37_ci_power_result.json` 实物是 `DFBDDF0B…`。MANIFEST 那一行本身**没错**（第 224 行登记的
#     是**旁车文件自身**的 md5 `50CA1A41…`）⇒ "按 MANIFEST 逐行核 bytes+md5"这一类检查**结构上
#     看不见它**，只有"把旁车打开、跟产物对一遍"才看得见。
#   根因：一次**全树清理**重写了产物 json 的字节，而 `.md5` 是**冻结记录**、没有任何环节重新派生它。
#   ⇒ 把"旁车登记值 == 产物实物 md5"变成**可复跑的派生断言**（下面 `DERIVED_SIDECARS` 是显式名单：
#     只覆盖"登记值就是产物摘要"的记录；`w1_prereg.md5` 一类**带冻结时间戳的 append-only 记录**
#     不在名单里，它们的语义是"冻结那一刻的值"，不由本支重写）。
DERIVED_SIDECARS = ('code/analysis/m37_ci_power_result.json.md5',
                    # ★ v0655：A5-2 扩构建的运行记录旁车 —— 由 `code/analysis/a52_ext_run_record.py`
                    #   当场从放行件派生（同一条 `hashlib.md5(产物)` 路径），故登记值必须等于实物。
                    'data/derived/a52_ext/a52_ext_run_record_20261006.json.md5')
print('\n①b 派生旁车（登记值 vs 产物实物）')
for _rel in DERIVED_SIDECARS:
    _fp = os.path.join(ROOT, _rel.replace('/', os.sep))
    if not os.path.exists(_fp):
        check('派生旁车在位：%s' % _rel, False, True)
        continue
    _m = re.match(r'\s*([0-9a-fA-F]{32})\s+(\S+)', rd(_fp))
    _tgt = os.path.join(os.path.dirname(_fp), _m.group(2)) if _m else ''
    check('派生旁车登记值 == 产物实物 md5：%s' % _rel,
          _m.group(1).upper() if _m else '解析失败',
          md5f(_tgt) if (_m and os.path.exists(_tgt)) else '缺产物')

# ── ② 论文明细里的 32 位摘要 vs MANIFEST ───────────────────────────────────
hx = re.compile(r'\b[0-9a-fA-F]{32}\b')
printed = set()
for p in (MANUS, SUPP):
    if os.path.exists(p):
        printed |= set(m.lower() for m in hx.findall(rd(p)))
hits = sorted(d for d in printed if d in by_md5)
miss = sorted(set(printed) - set(hits))
print('论文 + 补充材料里印出的 32 位摘要：%d 个去重；等于某个「本包发布件」的 MANIFEST md5：%d；不等于：%d'
      % (len(printed), len(hits), len(miss)))
for d in miss:
    print('    非发布件摘要  %s' % d)

# ── ③ 消毒台账（作者侧）────────────────────────────────────────────────────
san = None
if os.path.exists(SANLOG):
    import json
    san = json.loads(io.open(SANLOG, encoding='utf-8').read())
    for f in san['files']:
        m = by_path.get(f['path'])
        if m is not None:
            check('消毒台账 shipped_md5 == MANIFEST：%s' % f['path'], f['shipped_md5'], m)
        check('消毒台账 shipped_md5 == 实物 md5：%s' % f['path'],
              f['shipped_md5'], md5f(os.path.join(ROOT, f['path'].replace('/', os.sep)))
              if os.path.exists(os.path.join(ROOT, f['path'].replace('/', os.sep))) else f['shipped_md5'])

# ── ④ README 里的「四类计数」当场重算 ─────────────────────────────────────
n_shared = 0
n_abspath_code = 0
n_abspath_all = 0
n_ph = 0
rx_abs = re.compile(r'(^|[^A-Za-z0-9])[A-Za-z]:[\\/]')
rx_ph = re.compile(r'<REDACTED-|<WORKDIR>|<SHARED-DIR>')
for dp, dn, fn in os.walk(ROOT):
    dn[:] = [d for d in dn if d != '.git']
    for f in fn:
        fp = os.path.join(dp, f)
        rel = os.path.relpath(fp, ROOT).replace(os.sep, '/')
        if rel in ('MANIFEST.csv', 'data.zip'):
            continue
        try:
            s = io.open(fp, encoding='utf-8').read()
        except (UnicodeDecodeError, OSError):
            continue
        if 'from _repro_root import' in s and rel.startswith('code/'):
            n_shared += 1
        if rel.startswith('code/') and (f.endswith('.py') or f.endswith('.sh')) and rx_abs.search(s):
            n_abspath_code += 1
        if rx_abs.search(s):
            n_abspath_all += 1
        if rx_ph.search(s):
            n_ph += 1
print('README 四类计数：共享根 %d ｜ code 里作者机路径 %d ｜ 全树 %d ｜ 含占位符 %d'
      % (n_shared, n_abspath_code, n_abspath_all, n_ph))
if san is not None:
    print('消毒台账：%d 个文件 / %d 处替换' % (len(san['files']), san['substitutions']))

# ══ ⑤ README 的槽位替换（★ v0673：OLD 侧**结构槽位化** —— 会漂移的数字/摘要位不再逐代手抄）══════
# 【为什么改】2026-10-11 之前，每条替换的 OLD 侧是**手抄的 README 现印字面**，字面里含当轮会变的数字与
#   md5。数字一变 OLD 就落后一代，只能在下一轮**手工重指**（v0667 / v0668 / v0672 各一次；留痕见检查单
#   §37.4(乙) / §38.4(乙) / §41.10）—— **逐代复发**，而"重指"这一步本身又是手抄。
# 【改法】按上级 2026-10-11 任务书允许的做法 **2 ＋ 3 的组合**（结构/正则匹配 ＋ 形状断言）：
#   · 每条槽位给出**两类**模板，编译成正则后**仍要求"恰好命中 1 次"**（结构被改写 / 该行缺失 /
#     重复出现一律报红）：
#       `tmpl` = **预印形态**（README 现印文本：稳定散文逐字保留，**会漂移的数字位**写 `«n»`／
#                带宽度 `«n:k-m»`，**会漂移的 32 位摘要位**写 `«h»`，变长摘要清单写 `«hlist»`）；
#       `alt`  = **已应用形态**（`--apply` 之后的文本形态；没有则 None）。
#   · 数字位另有**形状断言**：`«n:k-m»` ⇒ 必须恰为 k–m 位十进制整数；不满足时打印
#     "严格 0 命中 / 宽松 1 命中"的诊断行，直接指出坏在宽度上。
#   · 命中后一律做 `命中文本 == 本轮实物派生文本` 判定（旧支的"已应用"分支**静默不核对**，
#     现支对**两种形态**都当场核对）：不等 ⇒ 记**待同步**并逐条打印；`--check` 不写盘。
#   · 同一实物派生量出现在多条槽位时，追加**跨槽位一致性断言**（README 自相矛盾 ⇒ 报红）
#     —— 这把旧字面匹配隐含的"同一量处处同值"显式化，强度不降。
#   · **NEW 侧仍由实物当场派生**；派生拿不到实物由 `_need_path()` **直接报红**，不再静默回退成 `?`。
#   · ⑥ 的 append-only 陈旧串注册表**固定条目一条未删**、可追溯退役表 3 条未删；动态条目仍按 ⑤ 的
#     槽位构造。★ "本轮命中文本 == 派生文本（无漂移）"的槽位字面不是"被换下的字面"：⑥ 中**显式标注
#     并打印**、不参与"复活"判定（不是静默跳过，注册表条目本身一条未删）。
#   ★ 强度账（逐条对账见检查单 §42）：**新增** 形状断言 / 派生失败报红 / 已应用形态也当场核对 /
#     跨槽位一致性 / 无漂移显式标注；**保留** 恰好命中 1 次、NEW 当场派生、⑥ append-only 不删条目；
#     **唯一变化**："数字换成另一个合法宽度的整数"不再报红，而是当场**自动同步**为实物派生值并逐条打印。
_MARK = re.compile(r'«(n|h|hlist|g)(?::(\d+)-(\d+))?»')


def _slot_rx(tmpl, strict=True):
    '''模板 → 正则：`«n»`/`«n:k-m»` → 数字组；`«h»` → 32 位十六进制；
    `«g»` → 通用值位（**遗留误印形态**识别用）；`«hlist»` → 摘要清单。'''
    out, i = [], 0
    for m in _MARK.finditer(tmpl):
        out.append(re.escape(tmpl[i:m.start()]))
        kind, lo, hi = m.group(1), m.group(2), m.group(3)
        if kind == 'n':
            out.append((r'(\d{%s,%s})' % (lo, hi)) if (strict and lo)
                       else (r'(\d{1,7})' if strict else r'(\d+)'))
        elif kind == 'h':
            out.append(r'([0-9A-Fa-f]{32})' if strict else r'([0-9A-Za-z]{2,64})')
        elif kind == 'g':
            out.append(r'([^\n`]{1,80})' if strict else r'([^\n]{1,80})')
        else:
            out.append(r'((?:`[0-9A-Fa-f]{32}`(?:, )?)+)' if strict else r'([^\n]*)')
        i = m.end()
    out.append(re.escape(tmpl[i:]))
    return re.compile(''.join(out))


def _need_path(rel, fails=None):
    '''NEW 侧派生守卫：取 `<ROOT>/<rel>` 的**随包摘要**（= `MANIFEST.csv` 该行的 md5）。

    ★ v0673 **缺陷修复**：此前这里是 `by_md5.get(md5f(path), '?')`，而 `by_md5` 是 **md5→路径**
      的映射 ⇒ ⑤ 把**路径**印进了 README 里"摘要/digest"的位置（实测 2 处，见检查单 §42）。
      改用 `by_path`（路径→md5；① 已断言它 == 实物 md5），拿不到实物时**报红**而不是静默给 `?`。
    '''
    p = os.path.join(ROOT, rel)
    _f = FAILS if fails is None else fails
    if not os.path.exists(p):
        _f.append('NEW 侧实物派生失败：%s 不在磁盘（实物被删或改名？）' % rel)
        return '?'
    v = by_path.get(rel) or md5f(p)
    if not v:
        _f.append('NEW 侧实物派生失败：%s 不在 MANIFEST.csv' % rel)
    return v or '?'


SLOTS = []


def slot(idtag, tmpl, new, alt=None, qty=None, note=''):
    '''登记一条槽位。

    `tmpl` = **预印形态**模板；`alt` = **已应用形态**模板（可 None）；`new` = 本轮实物派生文本；
    `qty` = 每个标记位对应的实物派生量名（跨槽位一致性断言用）。
    '''
    SLOTS.append(dict(id=idtag, tmpl=tmpl, new=new, alt=alt, qty=qty or [], note=note))




readme = rd(README)
if san is not None:
    _N_SAN_FILES, _N_SAN_SUBS = len(san['files']), san['substitutions']
else:
    _rm = re.findall(r'(?m)^\|\s*`([^`|]+)`\s*\|\s*(\d+)\s*\|\s*`([0-9A-Fa-f]{32})`\s*\|\s*`([0-9A-Fa-f]{32})`\s*\|',
                     readme)
    _N_SAN_FILES, _N_SAN_SUBS = len(_rm), sum(int(r[1]) for r in _rm)
    print('  ⚠ 未找到消毒台账（作者侧）⇒ 该两条派生量改用 README 消毒表：%d 个文件 / %d 处替换。'
          % (_N_SAN_FILES, _N_SAN_SUBS))
if san is not None:
    for f in san['files']:
        if f['path'] == 'manuscript/review_control_evidence.md' and f['src_md5']:
            slot("san-row:review_control_evidence",
                 "| `manuscript/review_control_evidence.md` | «n» | `«h»` | `«h»` |",
                 '| `manuscript/review_control_evidence.md` | 2 | `%s` | `%s` |' % (f['src_md5'].upper(), f['shipped_md5'].upper()),
                 alt=None,
                 qty=['n_san_row_subs', None, None])
slot("worked-example-1:A_analyze publish-form",
     "`«h»` both as the authors' source file and as the copy shipped here (the sanitiser no longer",
     "`%s` both as the authors' source file and as the copy shipped here (the sanitiser no longer" % _need_path('code/analysis/A_analyze.py'),
     alt="`«g»` both as the authors' source file and as the copy shipped here (the sanitiser no longer",
     qty=[None])
slot("worked-example-2:n4 historical+shipped digest",
     "* Supplementary §M.19.15 prints md5 `9c74db226c1b785361807ebc7e069771` for\n  `n4_cross_family_dense_panel.py`; that script now hashes to `«h»`. The printed value is neither the\n  current source digest nor the shipped digest. It is stated here rather than silently corrected because\n  the submitted supplementary material is frozen; **the script's behaviour did not change**, only the\n  literals that located its inputs.",
     "* Supplementary §M.19.15 prints, for `n4_cross_family_dense_panel.py`, a **historical** digest\n  `9c74db226c1b785361807ebc7e069771` and the digest of the copy shipped here,\n  `%s` — the latter is the `MANIFEST.csv` row for that path. **The script's behaviour did not\n  change**, only the literals that located its inputs, so both numbers are stated rather than one of them\n  being silently corrected." % _need_path('code/analysis/n4_cross_family_dense_panel.py'),
     alt="* Supplementary §M.19.15 prints, for `n4_cross_family_dense_panel.py`, a **historical** digest\n  `9c74db226c1b785361807ebc7e069771` and the digest of the copy shipped here,\n  `«g»` — the latter is the `MANIFEST.csv` row for that path. **The script's behaviour did not\n  change**, only the literals that located its inputs, so both numbers are stated rather than one of them\n  being silently corrected.",
     qty=[None])
slot("digest-counts:printed/equal/remaining",
     "Of the **«n»** distinct 32-hex digests printed in the manuscript and the supplementary material, **«n»**\nequal the `MANIFEST.csv` md5 of a file this package ships, before or after v0608. The remaining **«n»** are\nnot shipped-file digests: «hlist».",
     'Of the **%d** distinct 32-hex digests printed in the manuscript and the supplementary material, **%d**\nequal the `MANIFEST.csv` md5 of a file this package ships, before or after v0608. The remaining **%d** are\nnot shipped-file digests: %s.' % (len(printed), len(hits), len(miss), ', '.join(('`%s`' % d for d in miss))),
     alt=None,
     qty=['n_printed', 'n_hits', 'n_miss', None])
slot("shared-root-script-count",
     "1. **«n»** scripts resolve their inputs through the shared root: the **146** converted in v0608 plus the\n   scripts added to the released set since. Each imports `code/analysis/_repro_root.py`:\n   `grep -rl \"from _repro_root import\" code | wc -l` → **«n»**.",
     '1. **%d** scripts resolve their inputs through the shared root: the **146** converted in v0608 plus the\n   scripts added to the released set since. Each imports `code/analysis/_repro_root.py`:\n   `grep -rl "from _repro_root import" code | wc -l` → **%d**.' % (n_shared, n_shared),
     alt=None,
     qty=['n_shared', 'n_shared'])
slot("widen-scan:all-text-files",
     "   Widening the same scan to **every** text file in the package gives **«n»** files, still none of them a\n   script's data path. They are frozen artefacts and run logs whose recorded strings hold the authors'\n   prefix in backslash-escaped form (e.g. `A_result.json`, `ea2_z0_result.json`, `fsc_res_result.json`,",
     "   Widening the same scan to **every** text file in the package gives **%d** files, still none of them a\n   script's data path. They are frozen artefacts and run logs whose recorded strings hold the authors'\n   prefix in backslash-escaped form (e.g. `A_result.json`, `ea2_z0_result.json`, `fsc_res_result.json`," % n_abspath_all,
     alt=None,
     qty=['n_abspath_all'])
slot("frozen-artefacts-note(no-slot)",
     "   `n1_span_artefact_result.json`, `n2_rule_spread_inventory.json`, the per-image records under\n   `data/derived/`, the `env/` handover notes, and this `README.md`, which quotes\n   the `e:\\n` fragment above). The frozen artefacts are **deliberately not modified** — they are reported",
     '   `n1_span_artefact_result.json`, `n2_rule_spread_inventory.json`, the per-image records under\n   `data/derived/`, the `env/` handover notes, and this `README.md`, which quotes\n   the `e:\\n` fragment above). The frozen artefacts are **deliberately not modified** — they are reported',
     alt=None,
     qty=[])
slot("item-2:author-machine-path-files",
     "2. **0** of those scripts carries an author-machine path, and no script's *data* path is absolute:\n   `grep -rEl \"(^|[^A-Za-z0-9])[A-Za-z]:[\\\\\\\\/]\" code --include='*.py' --include='*.sh'` → **«n»** files, and\n   neither is a data path: `_repro_root.py` itself (its single env-overridable `PAPERB_SHARED` default) and\n   `w0_frame.py`, where the match is the fragment `e:\\n` inside a quoted Python-code template\n   (`'except Exception as e:\\n'`), not a path.",
     '2. **0** of those scripts carries an author-machine path, and no script\'s *data* path is absolute:\n   `grep -rEl "(^|[^A-Za-z0-9])[A-Za-z]:[\\\\\\\\/]" code --include=\'*.py\' --include=\'*.sh\'` → **%d** files, and\n   neither is a data path: `_repro_root.py` itself (its single env-overridable `PAPERB_SHARED` default) and\n   `w0_frame.py`, where the match is the fragment `e:\\n` inside a quoted Python-code template\n   (`\'except Exception as e:\\n\'`), and `derive_release_numbers.py`, which quotes that same fragment\n   in its substitution strings below — none of the three is a path.' % n_abspath_code,
     alt="2. **0** of those scripts carries an author-machine path, and no script's *data* path is absolute:\n   `grep -rEl \"(^|[^A-Za-z0-9])[A-Za-z]:[\\\\\\\\/]\" code --include='*.py' --include='*.sh'` → **«n»** files, and\n   neither is a data path: `_repro_root.py` itself (its single env-overridable `PAPERB_SHARED` default) and\n   `w0_frame.py`, where the match is the fragment `e:\\n` inside a quoted Python-code template\n   (`'except Exception as e:\\n'`), and `derive_release_numbers.py`, which quotes that same fragment\n   in its substitution strings below — none of the three is a path.",
     qty=['n_abspath_code'])
slot("shared-root-count:second-occurrence",
     "data path at all — **«n»** of them — imports `code/analysis/_repro_root.py` and resolves its inputs through",
     'data path at all — **%d** of them — imports `code/analysis/_repro_root.py` and resolves its inputs through' % n_shared,
     alt=None,
     qty=['n_shared'])
slot("manifest-and-data-counts",
     "   *Write-back policy*), which took the package **at that revision** from **3,659** to **3,651** manifested\n   files and left both the rewritten set and the substitution count untouched. **At this revision\n   `MANIFEST.csv` registers «n» files** (`wc -l MANIFEST.csv` minus the header) and `data/` holds **«n»**\n   of them — both are re-derived by `code/analysis/derive_release_numbers.py`.",
     '   *Write-back policy*), which took the package **at that revision** from **3,659** to **3,651** manifested\n   files and left both the rewritten set and the substitution count untouched. **At this revision\n   `MANIFEST.csv` registers %d files** (`wc -l MANIFEST.csv` minus the header) and `data/` holds **%d**\n   of them — both are re-derived by `code/analysis/derive_release_numbers.py`.' % (N_MAN, N_DATA),
     alt=None,
     qty=['n_man', 'n_data'])
slot("placeholder-containing-files",
     "4. **«n»** files merely *contain* one of the placeholder strings: `grep -rlE '<REDACTED-|<WORKDIR>|<SHARED-DIR>' . | wc -l`\n   → **«n»** (the sanitiser's own rewritten set is count 3 above; the remainder only quote a placeholder\n   string — this `README.md` does so on purpose).",
     "4. **%d** files merely *contain* one of the placeholder strings: `grep -rlE '<REDACTED-|<WORKDIR>|<SHARED-DIR>' . | wc -l`\n   → **%d** (the sanitiser's own rewritten set is count 3 above; the remainder only quote a placeholder\n   string — this `README.md` does so on purpose)." % (n_ph, n_ph),
     alt=None,
     qty=['n_ph', 'n_ph'])
slot("almost-nothing-under-data",
     "**Almost nothing under `data/` was altered.** Of the **«n»** files under `data/`, **«n»** are text files\nthe sanitiser rewrote (they are the `data/` rows of the table above); every one of the remaining **«n»** is\nbyte-identical to the corresponding source file.",
     '**Almost nothing under `data/` was altered.** Of the **%d** files under `data/`, **%d** are text files\nthe sanitiser rewrote (they are the `data/` rows of the table above); every one of the remaining **%d** is\nbyte-identical to the corresponding source file.' % (N_DATA, N_DATA_SAN, N_DATA - N_DATA_SAN),
     alt=None,
     qty=['n_data', 'n_data_san', 'n_data_rest'])
slot("scan-all-released-data-finds",
     "of the six placeholder patterns above in the file, and a scan of all «n» released data files finds **«n»**\ncarrying one of them — the remaining rewritten data file carries a neutral internal-name placeholder\ninstead of a host/path placeholder; (ii)",
     'of the six placeholder patterns above in the file, and a scan of all %d released data files finds **%d**\ncarrying one of them — the remaining rewritten data file carries a neutral internal-name placeholder\ninstead of a host/path placeholder; (ii)' % (N_DATA, N_PH_DATA),
     alt=None,
     qty=['n_data', 'n_ph_data'])
slot("manifest-before-after-prose(no-slot)",
     "manifest of `data/` taken before and after the release script ran is **unchanged**. In particular the 138",
     'manifest of `data/` taken before and after the release script ran differs **only in the rows the sanitiser\nrewrote** (the table above). In particular the 138',
     alt="manifest of `data/` taken before and after the release script ran differs **only in the rows the sanitiser\nrewrote** (the table above). In particular the 138",
     qty=[])
if san is not None:
    # 这一条**依赖作者侧消毒台账**（取件数/替换数）。旧写法在台账缺席（放行树）时按写死的退路值去替换
    # ⇒ 在放行树里跑本支必然"命中 0 次"而报红。现由 `_N_SAN_FILES` / `_N_SAN_SUBS` 两条路径派生
    # （台账在场用台账，缺席改用 README 消毒表），**判据一字未改**。
    slot("sanitiser-files-and-substitutions",
         "3. **«n»** files were rewritten by the sanitiser, in **«n»** substitutions (the table above). This set cannot be",
         '3. **%d** files were rewritten by the sanitiser, in **%d** substitutions (the table above). This set cannot be' % (_N_SAN_FILES, _N_SAN_SUBS),
         alt=None,
         qty=['n_san_files', 'n_san_subs'])

# ★ v0673：消毒表**锚行**改为**结构定位**（原先是手抄的两个 md5 字面，会随现印值漂移）。
#   锚行 = 表里 `manuscript/review_control_evidence.md` 那一行；**本应存在却找不到 ⇒ 报红**
#   （原写法找不到就静默跳过 ⇒ 台账新行不会被追加而闸门照绿，属"静默跳过"缺陷）。
_TBL_ANCHOR = None
_TBL_ROW_RX = re.compile(r'\| `manuscript/review_control_evidence\.md` \| \d+ \| '
                         r'`[0-9A-Fa-f]{32}` \| `[0-9A-Fa-f]{32}` \|')
if san is not None and any(f['path'] == 'manuscript/review_control_evidence.md' for f in san['files']):
    _m = _TBL_ROW_RX.search(readme)
    if _m:
        _TBL_ANCHOR = _m.group(0)
    else:
        FAILS.append('消毒表锚行（manuscript/review_control_evidence.md）未找到 ⇒ 台账新行无法追加')
        print('  ★ %s' % FAILS[-1])
if san is not None and _TBL_ANCHOR and _TBL_ANCHOR in readme:
    _add_rows = []
    for _f in san['files']:
        if ('| `%s` |' % _f['path']) in readme:
            continue
        _add_rows.append('| `%s` | %d | `%s` | `%s` |'
                         % (_f['path'], _f['subs'], (_f['src_md5'] or '').upper(),
                            (_f['shipped_md5'] or '').upper()))
    if _add_rows:
        readme = readme.replace(_TBL_ANCHOR, _TBL_ANCHOR + '\n' + '\n'.join(_add_rows), 1)
        print('  ★ 消毒表按台账补 %d 行：%s'
              % (len(_add_rows), [r.split('`')[1] for r in _add_rows]))


def _run_slots(txt, slots):
    '''按槽位替换 txt。返回 (新文本, 失败行, plan, 被换下的字面, 无漂移字面, 同步明细, 跨槽位量值)。

    ★ 与旧判据对账：旧支"每条 OLD 恰好命中 1 次 / 或已应用" ⇒ 现支"每条模板（预印或已应用）
      **恰好命中 1 次**"，且命中后一律与实物派生文本核对（旧支的"已应用"分支**不核对**）。
    '''
    fails, plan, dyn, nodrift, syncs, qty = [], [], [], [], [], {}
    for s in slots:
        forms = [('预印形态', s['rx'], s['rxl'])]
        if s['arx'] is not None:
            forms.append(('已应用形态', s['arx'], s['arxl']))
        m, msg = None, None
        for _kind, _rx, _rxl in forms:
            h = list(_rx.finditer(txt))
            if len(h) == 1:
                m = h[0]
                break
            if len(h) > 1:
                msg = 'README 结构槽位 %s（%s）：**命中 %d 次（期望 1）**' % (s['id'], _kind, len(h))
                break
        if m is None:
            if msg is None:
                _diag = []
                for _kind, _rx, _rxl in forms:
                    lo = list(_rxl.finditer(txt))
                    _diag.append('%s 严格 0 / 宽松 %d' % (_kind, len(lo)))
                    if len(lo) == 1:
                        msg = ('README 结构槽位 %s（%s）：数字/摘要位**形状不符**'
                               '（严格 0 命中 / 宽松 1 命中）⇒ %r'
                               % (s['id'], _kind, lo[0].group(0)[:90]))
                if msg is None:
                    msg = ('README 结构槽位 %s：锚文本**命中 0 次（期望 1）**（%s）⇒ 该行已被改写或缺失'
                           % (s['id'], '；'.join(_diag)))
            fails.append(msg)
            continue
        for _q, _g in zip(s['qty'], m.groups()):
            if _q:
                qty.setdefault(_q, {}).setdefault(_g, []).append(s['id'])
        old = m.group(0)
        if s['new'] == old:
            plan.append('(一致) ' + s['id'])
            nodrift.append(old)
            continue
        txt = txt[:m.start()] + s['new'] + txt[m.end():]
        plan.append('(自动同步) ' + s['id'])
        dyn.append(old)
        syncs.append((s['id'], old, s['new']))
    return txt, fails, plan, dyn, nodrift, syncs, qty


for _s in SLOTS:
    _s['rx'] = _slot_rx(_s['tmpl'], strict=True)
    _s['rxl'] = _slot_rx(_s['tmpl'], strict=False)
    _s['arx'] = _slot_rx(_s['alt'], strict=True) if _s['alt'] else None
    _s['arxl'] = _slot_rx(_s['alt'], strict=False) if _s['alt'] else None
_tpls = {}
for _s in SLOTS:
    _tpls.setdefault(_s['tmpl'], []).append(_s['id'])
_DUP = [(t, ids) for t, ids in _tpls.items() if len(ids) > 1]
if _DUP:
    FAILS.append('槽位模板重复（%d 组）⇒ 同一段文本被登记两次：%s'
                 % (len(_DUP), [ids for _t, ids in _DUP]))
    print('  ★ %s' % FAILS[-1])
readme, _f5, _plan, _DYN_OLD, _NODRIFT, _SYNCS, _QTY = _run_slots(readme, SLOTS)
FAILS += _f5
plan = _plan
print('  ⑤ README 槽位：%d 条（本轮待同步 %d 处 / 已一致 %d 处；**--apply 才写盘**）'
      % (len(SLOTS), len(_SYNCS), len(_NODRIFT)))
for _lab, _vals in sorted(_QTY.items()):
    if len(_vals) > 1:
        FAILS.append('README 同一派生量「%s」在不同槽位印值不一致：%s ⇒ README 自相矛盾'
                     % (_lab, sorted(_vals)))
        print('  ★ %s' % FAILS[-1])
for _sid, _o, _n in _SYNCS:
    print('     SYNC %-46s %r… → %r…' % (_sid, _o[:56], _n[:56]))
for _fm in _f5:
    print('  ★ %s' % _fm)

# ── ⑥ ★ v0656：**持久陈旧串断言**（把"上一代老串"升级为常设判据）────────────────────────────
#   机制弱点（v0655 §7 登记、本次修）：⑤ 的替换表是**逐代手抄的老串**。它只在"老串仍印在 README
#   里"的那一轮起一次作用；计数一变，老串与新串两边都不命中 ⇒ 要么报红、要么落进"已应用"分支
#   **静默跳过**。更要紧的是：**更早几代**的陈旧值（更旧的清单行数、更旧的目录计数、更旧的
#   "发布形态"摘要）**此后没有任何一条判据再看一眼** —— 旧模板一旦被重新生成，陈旧数字会原地
#   复活而闸门照样全绿。
#   处置：把所有**已知陈旧串**收进一个 **append-only 注册表**（只增不减），并断言它们在
#   **替换后的 README** 里命中 **0 次**。⑤ 的"每条恰好命中 1 次 / 或已应用"两条判据**一字未改**
#   —— 本段是**只加断言，不放宽任何现有判据**。
#   ★ 范围（为什么只查 README）：本支的守卫对象就是 README 的派生数字。放行树里另有三处**冻结
#     编排件**按纪律保留 `19 文件` 的历史叙述（登记不改；见本次检查单 §25.2），故不做树级断言。
#   ★ 注册表维护：每轮更新 ⑤ 的老串时，把**被换下的那一条**移入下表（而不是删掉）。
# ── ★ 2026-10-10（v0666）：**可追溯退役表**（append-only 的第三条通道）────────────────────
#   裁定（上级 2026-10-10）：当新派生值与某条"陈旧串"字面重合时，该条旧串的断言是**假阳性**
#   （数值巧合，不是残留）。处置＝**退役**（不删条目）：
#     · 下表逐条登记：字面（或前缀）、理由、实测依据、退役人/时间、依据件 md5；
#     · `stale_hits()` 跳过**已退役**的字面；其余陈旧串的检测**一字未改**；
#     · 自测里另加一条"已退役字面不再报红"的正例，与一条"未退役字面仍必须报红"的负例。
#   ★ 本表 **append-only**：退役条目不删，新退役只能追加。
RETIRED_STALE = [
    dict(literal_prefix='4. **39** files merely *contain*',
         label='（⑤ 上一代替换串）4. **39** files merely *contain* one of the',
         reason='本次实物派生的"含占位符件数"复现为 39，与上一代老串**字面重合**'
                '（旧串=新串）⇒ 替换后命中是**数值巧合**，不是陈旧残留',
         evidence='`python derive_release_numbers.py --check`（2026-10-10）：'
                  'README 四类计数 = 共享根 157 ｜ code 里作者机路径 3 ｜ 全树 21 ｜ 含占位符 39',
         retired_on='2026-10-10',
         retired_by='v0666 轮（上级裁定 2026-10-10 可追溯退役）',
         basis_md5='746dd9fd7761818f7b65e2224af03166（本次补材）/'
                   '35810a6d3fba7b9c2335ff6a90827d9c（本次主稿）'),
    # ★ 同一类假阳性（同一裁定、同一手续）：消毒件数/替换处数的实物派生值
    #   本次为 36 / 77，与上一代老串**字面重合** ⇒ 同样是数值巧合。
    dict(literal_prefix='3. **36** files were rewritten by the sanitiser',
         label='（⑤ 上一代替换串）3. **36** files were rewritten by the sanitiser',
         reason='本次实物派生的消毒件数/替换处数复现为 36 / 77，与上一代老串**字面重合**'
                '（旧串=新串）⇒ 替换后命中是**数值巧合**，不是陈旧残留',
         evidence='`python derive_release_numbers.py --check`（2026-10-10）：消毒台账 36 个文件 / 77 处替换；'
                  'README 四类计数 = 共享根 157 ｜ code 里作者机路径 3 ｜ 全树 21 ｜ 含占位符 39',
         retired_on='2026-10-10',
         retired_by='v0666 轮（上级裁定 2026-10-10 可追溯退役）',
         basis_md5='746dd9fd7761818f7b65e2224af03166（本次补材）/'
                   '35810a6d3fba7b9c2335ff6a90827d9c（本次主稿）'),
    # ★ 2026-10-11：同一类假阳性，同一裁定、同一手续。⑤ 的 `n1_span_artefact_result.json`
    #   那一条 OLD 按 R5 纪律同步到 README **现印**文本后，该 OLD 字面与 ⑥ 注册表里"上一代替换串"
    #   （上一轮那条 "two copies of the first two under …" 的被换下字面）**逐字重合** ⇒ 替换后命中
    #   是**字面重合**，不是陈旧残留。判据未放宽：注册表 append-only，此条只跳过对比、不删条目。
    dict(literal_prefix='   `n1_span_artefact_result.json`, `n2_rule_spread_inventory.json`, the per-image records under',
         label='（⑤ 上一代替换串）   `n1_span_artefact_result.json`, `n2_rule_…',
         reason='⑤ 的 OLD 按 R5 同步到 README **现印**文本后，与上一代被换下的字面**逐字重合**'
                '（旧串=新串）⇒ 替换后命中是**字面重合**，不是陈旧残留',
         evidence='`python derive_release_numbers.py --check`（2026-10-11）：消毒台账 37 个文件 / 81 处替换；'
                  'README 四类计数 = 共享根 159 ｜ code 里作者机路径 3 ｜ 全树 25 ｜ 含占位符 40',
         retired_on='2026-10-11',
         retired_by='沿用 v0666 可追溯退役裁定（本次无新裁定）',
         basis_md5='9fdd442397196fbe26f3f8c6a6b72c9e（本次补材）/'
                   '0aa4506850bdebd701079207020f814b（本次主稿）'),
]


def _retired(nd):
    """该陈旧串字面是否已被**可追溯退役**（仅前缀匹配，其余判据不变）。"""
    return any(nd.startswith(r['literal_prefix']) for r in RETIRED_STALE)


STALE_STRINGS = [
    # —— 跨代陈旧叙述（官方 FP8 件的件数，原写多算 1）——
    ('FP8 官方件数（旧叙述，中文）', '19 文件'),
    ('FP8 官方件数（旧叙述，英文）', '19 files'),
    # —— 跨代陈旧计数 ——
    ('清单登记行数（上一代）', 'registers 4703 files'),
    ('清单登记行数（更早一代）', 'registers 4701 files'),
    ('data/ 件数（上一代）', 'holds **3787**'),
    ('data/ 件数（更早一代）', 'holds **3785**'),
    ('共享根脚本数（上一代）', '**154** scripts resolve their inputs'),
    ('共享根脚本数（更早一代）', '**149** of them'),
    ('全树作者机路径件数（上一代）', 'gives **15** files'),
    ('含占位符件数（上一代）', '**37** files merely *contain*'),
    ('印出摘要数（上一代）', '**31** distinct 32-hex digests'),
    ('消毒替换处数（上一代）', '**64** substitutions'),
    ('假全称句（v0655 已改为派生式陈述）', 'Nothing under `data/` was altered.'),
    # ★ 2026-10-08（v0663）：把上一代（v0661/v0662）的四组计数老串补进来。
    ('清单登记行数（v0661/v0662 那一代）', 'registers 4764 files'),
    ('data/ 件数（v0661/v0662 那一代）', 'holds **3836**'),
    ('data/ 件数（只含占位符句）', 'Of the **3836** files under `data/`'),
    ('data/ 扩展扫描件数（v0661/v0662 那一代）', 'scan of all 3836 released'),
    ('占位符扫描的假零（v0655 已改为派生式陈述）',
     'scan of all 3787 released data files finds **zero**'),
    # —— 旧"发布形态"md5 摘要（README 已不再印它们；复活即说明 README 被从旧模板重生成）——
    ('A_analyze.py 旧发布摘要', 'F795CD0233C4EA03C7E4C9D70CAC8BD2'),
    ('review_control_evidence.md 旧摘要', '7052DE8CCB7FC67C57150619A570F742'),
    ('n4 脚本旧发布摘要', '3A9F8BB2FEED81D58E15E480419DF5F9'),
    ('w1_prereg 旧摘要', '75eeca6fa68c9be65c2b569d4237d8df'),
    ('被取代的机上分析器（本次已随 archives/ 放行 ⇒ 不再是"未随包"摘要）',
     'bf873c5e7da083dae42cb379efe9af9d'),
] + [('（⑤ 上一代替换串）%s' % old[:44], old) for old in (_DYN_OLD + _NODRIFT)]


def stale_hits(txt):
    """注册表里每一条陈旧串在 txt 里的命中（只列非 0 的）。

    ★ v0666：**已可追溯退役**的字面跳过对比（见 RETIRED_STALE）；其余一律照旧。
    """
    # ★ v0673：**无漂移槽位**的字面（本轮 ⑤ 命中的文本 == 实物派生文本）不是"被换下的字面"，
    #   跳过对比 —— 这是**显式**规则（⑥ 段里逐条打印说明），不是静默跳过；注册表条目一条未删。
    return [(lab, nd, txt.count(nd)) for lab, nd in STALE_STRINGS
            if txt.count(nd) and not _retired(nd) and nd not in _NODRIFT]


print('\n⑥ 持久陈旧串断言（对象 = 替换后的 README；注册表 %d 条，append-only）'
      % len(STALE_STRINGS))
print('  ★ 可追溯退役表：%d 条（append-only，不删条目）' % len(RETIRED_STALE))
for _r in RETIRED_STALE:
    print('     RETIRE %s' % _r['label'])
    print('       理由：%s' % _r['reason'])
    print('       依据：%s' % _r['evidence'])
    print('       退役人/时间：%s / %s；依据件 md5：%s'
          % (_r['retired_by'], _r['retired_on'], _r['basis_md5']))
if _NODRIFT:
    print('  ★ 无漂移槽位（本轮命中文本 == 实物派生文本）%d 条：其字面不是"被换下的字面"，'
          '不参与"复活"判定' % len(_NODRIFT))
_hits = stale_hits(readme)
if _hits:
    for lab, nd, c in _hits:
        print('  ★ 陈旧串复活 %d 次：%s → %r' % (c, lab, nd[:72]))
        FAILS.append('陈旧串在 README 里复活 %d 次：%s' % (c, lab))
else:
    print('  0 命中 ✓（%d 条已知陈旧串逐条核过：旧叙述 / 旧计数 / 旧摘要）'
          % len(STALE_STRINGS))

# —— 自测（正例 + 负例；`--selftest` 时才跑，仍不写盘）——
if '--selftest' in sys.argv:
    _POS = (len(stale_hits(readme)) == 0)
    _PROBES = ['19 文件', 'registers 4703 files', 'F795CD0233C4EA03C7E4C9D70CAC8BD2']
    for _p in _PROBES:
        assert any(_p == _nd for _l, _nd in STALE_STRINGS), \
            '负例探针不在注册表里：%r（自测本身无意义）' % _p
    _NEG = [p for p in _PROBES if stale_hits(readme + '\n' + p + '\n')]
    print('  [自测] 正例（当前 README 必须绿）：%s' % ('PASS' if _POS else 'FAIL'))
    print('  [自测] 负例（注入 %d 条陈旧串必须逐条抓住）：%s（抓住 %d/%d）'
          % (len(_PROBES), 'PASS' if len(_NEG) == len(_PROBES) else 'FAIL',
             len(_NEG), len(_PROBES)))
    for _p in _PROBES:
        if _p not in _NEG:
            print('     ★ 漏抓：%r' % _p)
    _RET_PROBES = [r['literal_prefix'] for r in RETIRED_STALE]
    _RETHIT = [p for p in _RET_PROBES if stale_hits(readme + '\n' + p + '\n')]
    print('  [自测] 已退役字面不再报红（退役生效）：%s（%d 条）'
          % ('PASS' if not _RETHIT else 'FAIL', len(_RET_PROBES)))
    # ★ v0673：⑤ 的**负例自测**（内存里做，不写盘）——
    #   ① OLD 侧锚文本改错 ⇒ 该槽位必须 0 命中并报红；
    #   ② OLD 侧数字位形状改错（8 位）⇒ 严格 0 / 宽松 1 ⇒ 必须报红（并指出坏在宽度上）；
    #   ③ NEW 侧实物改掉（文件被删/改名）⇒ `_need_path()` 必须报红。
    _n1 = readme.replace('scripts resolve their inputs through the shared root',
                         'scripts resolve their inputs via the shared root', 1)
    _n1f = _run_slots(_n1, SLOTS)[1]
    print('  [自测] NEG-1（OLD 侧锚文本改错必须报红）：%s' % ('PASS' if _n1f else 'FAIL'))
    for _m in _n1f[:1]:
        print('     %s' % _m)
    _n2 = re.sub(r'(?<=1\. \*\*)\d+(?=\*\* scripts resolve)', '12345678', readme, count=1)
    _n2f = _run_slots(_n2, SLOTS)[1]
    print('  [自测] NEG-2（OLD 侧数字位形状改错必须报红）：%s' % ('PASS' if _n2f else 'FAIL'))
    for _m in _n2f[:1]:
        print('     %s' % _m)
    _f3 = []
    _need_path('code/analysis/__negtest_missing__.py', fails=_f3)
    print('  [自测] NEG-3（NEW 侧实物改掉必须报红）：%s' % ('PASS' if _f3 else 'FAIL'))
    for _m in _f3[:1]:
        print('     %s' % _m)
    if _POS and len(_NEG) == len(_PROBES) and not _RETHIT and _n1f and _n2f and _f3:
        print('  ⇒ STALE_SELFTEST_PASS')
    else:
        FAILS.append('持久陈旧串/槽位断言的自测未通过（正例=%s / 负例 %d/%d / 退役正例=%s / '
                     'NEG-1=%s / NEG-2=%s / NEG-3=%s）'
                     % (_POS, len(_NEG), len(_PROBES), 'PASS' if not _RETHIT else 'FAIL',
                        bool(_n1f), bool(_n2f), bool(_f3)))

print('\n%s' % ('=' * 96))
if FAILS:
    print('!! 有 %d 条断言/替换未通过 ⇒ 不写盘：' % len(FAILS))
    for f in FAILS:
        print('   - %s' % f)
    sys.exit(1)
print('全部断言通过；README 槽位 %d 条（本轮待同步 %d 处 / 已一致 %d 处）'
      % (len(plan), len(_SYNCS), len(_NODRIFT)))
if not APPLY:
    print('（DRY-RUN：未写盘；加 --apply 才写）')
    sys.exit(0)
io.open(README, 'w', encoding='utf-8', newline='').write(readme)
print('已写 %s（%d 字节，md5 %s）' % (README, os.path.getsize(README), md5f(README)))
print('★ 注意：README.md 自身也在 MANIFEST 里 ⇒ 写回后须再跑一次 sync_repro 刷新那一行。')
