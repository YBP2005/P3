# -*- coding: utf-8 -*-
"""derive_release_numbers.py — 放行树 README 的**摘要类数字一律从实物派生**（不手写）。

为什么要有这一支（准则 §7「派生守卫」）：README 里同时出现过**同一件文件的三套 md5**
（论文印一套、MANIFEST 记一套、README 又写一套），还有一句**为假的全称句**
（"No other 32-hex digest … matches any file this package ships"）。手抄的数字必然漂移；
本轮把这几类数字改成**当场算出来、并硬断言**。

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
#   起因（本轮核到的**既存假全称句**）：README 写「Nothing under `data/` was altered … a scan of all
#   <N> released data files finds **zero** placeholder patterns」。实测 `data/` 下**早已有** 1 件
#   带占位符（`data/derived/a5_2_a800/env/_a52_运行单.md` 的 `<WORKDIR>`）＋1 件带中性内部名占位符
#   （判据件的 `<INTERNAL-ITEM-NOTE>` / `<INTERNAL-PLAN-DIR>`），共 **2** 件被消毒改写。该句在 v0655
#   之前就是**假**的，本轮又新增 2 件（扩构建两份报告），故改为**当场派生**三个计数：
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
    # ★ v0656 修（**本轮核出的既存缺陷**，不是本轮引入）：作者侧消毒台账**按设计不随包**，于是
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
#   起因（本轮盲审，三家独立报同一处，且**上面那三条断言全是绿的**）：
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

# ── ⑤ README 的替换（每条都必须**恰好命中 1 次**，否则不写盘）──────────────────
SUB = []
if san is not None:
    for f in san['files']:
        if f['path'] == 'manuscript/review_control_evidence.md' and f['src_md5']:
            SUB.append(('| `manuscript/review_control_evidence.md` | 2 | `7052DE8CCB7FC67C57150619A570F742` | `C648AA81B75985825523170E44B8945F` |',
                        '| `manuscript/review_control_evidence.md` | 2 | `%s` | `%s` |'
                        % (f['src_md5'].upper(), f['shipped_md5'].upper())))
SUB += [
    # worked example ①：A_analyze.py 的**发布形态** md5
    ('`F795CD0233C4EA03C7E4C9D70CAC8BD2` both as the authors\' source file and as the copy shipped here (the sanitiser no longer',
     '`%s` both as the authors\' source file and as the copy shipped here (the sanitiser no longer'
     % by_md5.get(md5f(os.path.join(ROOT, 'code', 'analysis', 'A_analyze.py')).lower(), '?')),
    # worked example ②：n4 的历史摘要 + 发布摘要
    ('''* Supplementary §M.19.15 prints md5 `9c74db226c1b785361807ebc7e069771` for
  `n4_cross_family_dense_panel.py`; that script now hashes to `3A9F8BB2FEED81D58E15E480419DF5F9`. The printed value is neither the
  current source digest nor the shipped digest. It is stated here rather than silently corrected because
  the submitted supplementary material is frozen; **the script's behaviour did not change**, only the
  literals that located its inputs.''',
     '''* Supplementary §M.19.15 prints, for `n4_cross_family_dense_panel.py`, a **historical** digest
  `9c74db226c1b785361807ebc7e069771` and the digest of the copy shipped here,
  `%s` — the latter is the `MANIFEST.csv` row for that path. **The script's behaviour did not
  change**, only the literals that located its inputs, so both numbers are stated rather than one of them
  being silently corrected.'''
     % by_md5.get(md5f(os.path.join(ROOT, 'code', 'analysis', 'n4_cross_family_dense_panel.py')).lower(), '?')),
    # 那句为假的全称句 → 派生式陈述
    # ★ v0655：OLD 同步到 README **现印**的那一份（31/26/5）—— 本轮补充材料新增了一个
    #   "印在 provenance 行、但随包发的是**更正后**那一版"的摘要（机上实跑用的分析器副本），
    #   故派生结果为 32/26/6；新串由 `printed`/`hits`/`miss` 当场算出。
    # ★ v0656：老串再次同步到 README **现印**的那一份（32/26/6 —— 因为本轮把`bf873c5e…`
    #   （被取代的机上分析器）作为存档件放进 `archives/`，它**从"未随包摘要"变成"随包摘要"**，
    #   故派生结果为 32/27/5；被换下的那一条已进 ⑥ 的持久注册表，不删。）
    ('''Of the **32** distinct 32-hex digests printed in the manuscript and the supplementary material, **26**
equal the `MANIFEST.csv` md5 of a file this package ships, before or after v0608. The remaining **6** are
not shipped-file digests: `0a42e6e5bbfa89543ba9fc1522f1b075`, `758962a2643e1035698682abefec5748`, `9c74db226c1b785361807ebc7e069771`, `aca4444c7f681b0596db4e4a84578b62`, `bf873c5e7da083dae42cb379efe9af9d`, `d95d7466b482f575dc781d152e5ddf23`.''',
     '''Of the **%d** distinct 32-hex digests printed in the manuscript and the supplementary material, **%d**
equal the `MANIFEST.csv` md5 of a file this package ships, before or after v0608. The remaining **%d** are
not shipped-file digests: %s.'''
     % (len(printed), len(hits), len(miss), ', '.join('`%s`' % d for d in miss))),
    # 四类计数（当场重算）
    # ★ OLD = README **现印**的那一份（"上次印出的值"）；NEW = 当场派生。数目一变，本支就报红并要求
    #   把 OLD 同步到新印值 —— 这正是"不许手抄、必须派生"的落地方式。
    ('1. **154** scripts resolve their inputs through the shared root: the **146** converted in v0608 plus the\n'
     '   scripts added to the released set since. Each imports `code/analysis/_repro_root.py`:\n'
     '   `grep -rl "from _repro_root import" code | wc -l` → **154**.',
     '1. **%d** scripts resolve their inputs through the shared root: the **146** converted in v0608 plus the\n'
     '   scripts added to the released set since. Each imports `code/analysis/_repro_root.py`:\n'
     '   `grep -rl "from _repro_root import" code | wc -l` → **%d**.' % (n_shared, n_shared)),
    ('   Widening the same scan to **every** text file in the package gives **15** files, still none of them a\n'
     '   script\'s data path. The other 13 are: **9** frozen artefacts whose recorded strings hold the authors\'\n'
     '   prefix in backslash-escaped form (`A_result.json`, `ea2_z0_result.json`, `fsc_res_result.json`,',
     '   Widening the same scan to **every** text file in the package gives **%d** files, still none of them a\n'
     '   script\'s data path. They are frozen artefacts and run logs whose recorded strings hold the authors\'\n'
     '   prefix in backslash-escaped form (e.g. `A_result.json`, `ea2_z0_result.json`, `fsc_res_result.json`,' % n_abspath_all),
    ('   `n1_span_artefact_result.json`, `n2_rule_spread_inventory.json`, two copies of the first two under\n'
     '   `data/derived/fsc_res/`, and `manuscript/pagination_measurement.json` plus its RTF-proxy companion);\n'
     '   **3** prose mentions in the `env/a800_logs_20260927/` handover notes; and this `README.md`, which quotes\n'
     '   the `e:\\n` fragment above. The frozen artefacts are **deliberately not modified** — they are reported',
     '   `n1_span_artefact_result.json`, `n2_rule_spread_inventory.json`, the per-image records under\n'
     '   `data/derived/`, the `env/` handover notes, and this `README.md`, which quotes\n'
     '   the `e:\\n` fragment above). The frozen artefacts are **deliberately not modified** — they are reported'),
    # ★ v0655：计数 2 的前半句此前是**手写**的（后随的 `Widening…` 已派生，本句没有）。
    #   本轮 `derive_release_numbers.py` 自己的替换串引用了同一段 `e:\n` 片段 ⇒ 该计数
    #   2 → 3（第三件就是本支自身）⇒ 老串从 README 现场读出、新串改用 `n_abspath_code`。
    (
     '2. **0** of those scripts carries an author-machine path, and no script\'s *data* path is absolute:\n'
     '   `grep -rEl "(^|[^A-Za-z0-9])[A-Za-z]:[\\\\\\\\/]" code --include=\'*.py\' --include=\'*.sh\'` → **2** files, and\n'
     '   neither is a data path: `_repro_root.py` itself (its single env-overridable `PAPERB_SHARED` default) and\n'
     '   `w0_frame.py`, where the match is the fragment `e:\\n` inside a quoted Python-code template\n'
     '   (`\'except Exception as e:\\n\'`), not a path.',
     '2. **0** of those scripts carries an author-machine path, and no script\'s *data* path is absolute:\n'
     '   `grep -rEl "(^|[^A-Za-z0-9])[A-Za-z]:[\\\\\\\\/]" code --include=\'*.py\' --include=\'*.sh\'` → **%d** files, and\n'
     '   neither is a data path: `_repro_root.py` itself (its single env-overridable `PAPERB_SHARED` default) and\n'
     '   `w0_frame.py`, where the match is the fragment `e:\\n` inside a quoted Python-code template\n'
     '   (`\'except Exception as e:\\n\'`), and `derive_release_numbers.py`, which quotes that same fragment\n'
     '   in its substitution strings below — none of the three is a path.' % n_abspath_code),
    # ★ v0654：这一条**依赖作者侧消毒台账**（取件数/替换数）。此前它在 `san is None` 时
    #   仍按写死的退路值 30/58 去替换 ⇒ 在**放行树里**跑本支时必然"命中 0 次"而**报红**，
    #   而真因只是"放行树没有台账"。现在它只在有台账时参与（值一律由台账派生）。
    # ★ v0654：README 里"共享根脚本数"**出现两次**（"How to run" 段一次、计数 1 一次），
    #   旧支只改后者 ⇒ 两处会长期互不一致（实测本轮接手时：一处 **149**、一处 **154**，真值 154）。
    #   这两条把 "How to run" 那一处也纳入派生（值同 `n_shared`）。
    ('data path at all — **149** of them — imports `code/analysis/_repro_root.py` and resolves its inputs through',
     'data path at all — **%d** of them — imports `code/analysis/_repro_root.py` and resolves its inputs through'
     % n_shared),
    ('   *Write-back policy*), which took the package **at that revision** from **3,659** to **3,651** manifested\n'
     '   files and left both the rewritten set and the substitution count untouched. **At this revision\n'
     '   `MANIFEST.csv` registers 4757 files** (`wc -l MANIFEST.csv` minus the header) and `data/` holds **3829**\n'
     '   of them — both are re-derived by `code/analysis/derive_release_numbers.py`.',
     '   *Write-back policy*), which took the package **at that revision** from **3,659** to **3,651** manifested\n'
     '   files and left both the rewritten set and the substitution count untouched. **At this revision\n'
     '   `MANIFEST.csv` registers %d files** (`wc -l MANIFEST.csv` minus the header) and `data/` holds **%d**\n'
     '   of them — both are re-derived by `code/analysis/derive_release_numbers.py`.' % (N_MAN, N_DATA)),
    ("4. **37** files merely *contain* one of the placeholder strings: `grep -rlE '<REDACTED-|<WORKDIR>|<SHARED-DIR>' . | wc -l`\n"
     "   → **37** (the sanitiser's own rewritten set is count 3 above; the remainder only quote a placeholder\n"
     "   string — this `README.md` does so on purpose).",
     "4. **%d** files merely *contain* one of the placeholder strings: `grep -rlE '<REDACTED-|<WORKDIR>|<SHARED-DIR>' . | wc -l`\n"
     "   → **%d** (the sanitiser's own rewritten set is count 3 above; the remainder only quote a placeholder\n"
     "   string — this `README.md` does so on purpose)." % (n_ph, n_ph)),
    # ★ v0655：`data/` 的"改没改"必须**派生**（见文件上方 N_PH_DATA / N_DATA_SAN 的计算与说明）。
    #   下面三条的老串 = **本轮落笔时 README 里的原文**；新串由实物算出。三条合起来把那句
    #   既存的**假全称句**（"Nothing under data/ was altered … finds zero placeholder patterns"）
    #   换成一个**可复核**的陈述：改了几件、其余逐字节相同、manifest 只在被改写的行上变化。
    # ★ v0656：老串同步到 README **现印**的那一份（3829/4/3825）；被换下的"假全称句"那条
    #   （`**Nothing under data/ was altered.** Every one of the **3787** …`）已进 ⑥ 的持久注册表。
    ('**Almost nothing under `data/` was altered.** Of the **3829** files under `data/`, **4** are text files\n'
     'the sanitiser rewrote (they are the `data/` rows of the table above); every one of the remaining **3825** is\n'
     'byte-identical to the corresponding source file.',
     '**Almost nothing under `data/` was altered.** Of the **%d** files under `data/`, **%d** are text files\n'
     'the sanitiser rewrote (they are the `data/` rows of the table above); every one of the remaining **%d** is\n'
     'byte-identical to the corresponding source file.' % (N_DATA, N_DATA_SAN, N_DATA - N_DATA_SAN)),
    # ★ v0656：老串同步到 README **现印**的那一份（3829 / **3**）；被换下的"finds **zero**"那条已进 ⑥。
    ('of the six placeholder patterns above in the file, and a scan of all 3829 released data files finds **3**\n'
     'carrying one of them — the remaining rewritten data file carries a neutral internal-name placeholder\n'
     'instead of a host/path placeholder; (ii)',
     'of the six placeholder patterns above in the file, and a scan of all %d released data files finds **%d**\n'
     'carrying one of them — the remaining rewritten data file carries a neutral internal-name placeholder\n'
     'instead of a host/path placeholder; (ii)' % (N_DATA, N_PH_DATA)),
    ('manifest of `data/` taken before and after the release script ran is **unchanged**. In particular the 138',
     'manifest of `data/` taken before and after the release script ran differs **only in the rows the sanitiser\n'
     'rewrote** (the table above). In particular the 138'),
]

readme = rd(README)
SUB = [x for x in SUB if x is not None]
# 依赖消毒台账的那一条：台账在场时用台账；**台账缺席（放行树）时改用 README 消毒表**的同名算量。
# ★ v0656：此处先前在台账缺席时**整段跳过**，于是放行树里的读数与 README 现印的 34/68 无人核对；
#   而一旦有人把它写成"两边都不命中"，本支在放行树里就必然报红（包外复核会照 README 跑本支）。
#   现在两条路径**都参与**，来源在上一段已显式打印（台账 vs README 表），判据一字未改。
if san is not None:
    _N_SAN_FILES, _N_SAN_SUBS = len(san['files']), san['substitutions']
else:
    _rm = re.findall(r'(?m)^\|\s*`([^`|]+)`\s*\|\s*(\d+)\s*\|\s*`([0-9A-Fa-f]{32})`\s*\|\s*`([0-9A-Fa-f]{32})`\s*\|',
                     readme)
    _N_SAN_FILES, _N_SAN_SUBS = len(_rm), sum(int(r[1]) for r in _rm)
    print('  ⚠ 未找到消毒台账（作者侧）⇒ 该两条派生量改用 README 消毒表：%d 个文件 / %d 处替换。'
          % (_N_SAN_FILES, _N_SAN_SUBS))
SUB.append((
    '3. **32** files were rewritten by the sanitiser, in **64** substitutions (the table above). This set cannot be',
    '3. **%d** files were rewritten by the sanitiser, in **%d** substitutions (the table above). This set cannot be'
    % (_N_SAN_FILES, _N_SAN_SUBS)))
plan = []
for old, new in SUB:
    c = readme.count(old)
    if c == 0 and new in readme:
        # ★ 幂等：本支已经跑过一次（旧串已被换成新串）⇒ 记为已应用，不算失败
        plan.append('(已应用) ' + old[:48])
        continue
    if c != 1:
        FAILS.append('README 替换串命中 %d 次（期望 1）：%r…' % (c, old[:70]))
        print('  ★ README 替换串命中 %d 次：%r…' % (c, old[:70]))
        continue
    readme = readme.replace(old, new)
    plan.append(old[:60])

# ── ⑥ ★ v0656：**持久陈旧串断言**（把"上一代老串"升级为常设判据）────────────────────────────
#   机制弱点（v0655 §7 登记、本轮修）：⑤ 的替换表是**逐代手抄的老串**。它只在"老串仍印在 README
#   里"的那一轮起一次作用；计数一变，老串与新串两边都不命中 ⇒ 要么报红、要么落进"已应用"分支
#   **静默跳过**。更要紧的是：**更早几代**的陈旧值（更旧的清单行数、更旧的目录计数、更旧的
#   "发布形态"摘要）**此后没有任何一条判据再看一眼** —— 旧模板一旦被重新生成，陈旧数字会原地
#   复活而闸门照样全绿。
#   处置：把所有**已知陈旧串**收进一个 **append-only 注册表**（只增不减），并断言它们在
#   **替换后的 README** 里命中 **0 次**。⑤ 的"每条恰好命中 1 次 / 或已应用"两条判据**一字未改**
#   —— 本段是**只加断言，不放宽任何现有判据**。
#   ★ 范围（为什么只查 README）：本支的守卫对象就是 README 的派生数字。放行树里另有三处**冻结
#     编排件**按纪律保留 `19 文件` 的历史叙述（登记不改；见本轮检查单 §25.2），故不做树级断言。
#   ★ 注册表维护：每轮更新 ⑤ 的老串时，把**被换下的那一条**移入下表（而不是删掉）。
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
    ('占位符扫描的假零（v0655 已改为派生式陈述）',
     'scan of all 3787 released data files finds **zero**'),
    # —— 旧"发布形态"md5 摘要（README 已不再印它们；复活即说明 README 被从旧模板重生成）——
    ('A_analyze.py 旧发布摘要', 'F795CD0233C4EA03C7E4C9D70CAC8BD2'),
    ('review_control_evidence.md 旧摘要', '7052DE8CCB7FC67C57150619A570F742'),
    ('n4 脚本旧发布摘要', '3A9F8BB2FEED81D58E15E480419DF5F9'),
    ('w1_prereg 旧摘要', '75eeca6fa68c9be65c2b569d4237d8df'),
    ('被取代的机上分析器（本轮已随 archives/ 放行 ⇒ 不再是"未随包"摘要）',
     'bf873c5e7da083dae42cb379efe9af9d'),
] + [('（⑤ 上一代替换串）%s' % old[:44], old) for old, _n in SUB]


def stale_hits(txt):
    """注册表里每一条陈旧串在 txt 里的命中（只列非 0 的）。"""
    return [(lab, nd, txt.count(nd)) for lab, nd in STALE_STRINGS if txt.count(nd)]


print('\n⑥ 持久陈旧串断言（对象 = 替换后的 README；注册表 %d 条，append-only）'
      % len(STALE_STRINGS))
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
    if _POS and len(_NEG) == len(_PROBES):
        print('  ⇒ STALE_SELFTEST_PASS')
    else:
        FAILS.append('持久陈旧串断言的自测未通过（正例=%s / 负例 %d/%d）'
                     % (_POS, len(_NEG), len(_PROBES)))

print('\n%s' % ('=' * 96))
if FAILS:
    print('!! 有 %d 条断言/替换未通过 ⇒ 不写盘：' % len(FAILS))
    for f in FAILS:
        print('   - %s' % f)
    sys.exit(1)
print('全部断言通过；README 替换 %d 处' % len(plan))
if not APPLY:
    print('（DRY-RUN：未写盘；加 --apply 才写）')
    sys.exit(0)
io.open(README, 'w', encoding='utf-8', newline='').write(readme)
print('已写 %s（%d 字节，md5 %s）' % (README, os.path.getsize(README), md5f(README)))
print('★ 注意：README.md 自身也在 MANIFEST 里 ⇒ 写回后须再跑一次 sync_repro 刷新那一行。')
