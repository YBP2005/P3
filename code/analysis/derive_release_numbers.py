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
    python derive_release_numbers.py --apply    # 写回 README.md（须显式）
"""
import csv
import hashlib
import io
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
DERIVED_SIDECARS = ('code/analysis/m37_ci_power_result.json.md5',)
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
    ('''No other 32-hex digest printed in the manuscript or in the supplementary material matches any file this
package ships, before or after v0608.''',
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
     '   `MANIFEST.csv` registers 4701 files** (`wc -l MANIFEST.csv` minus the header) and `data/` holds **3785**\n'
     '   of them — both are re-derived by `code/analysis/derive_release_numbers.py`.',
     '   *Write-back policy*), which took the package **at that revision** from **3,659** to **3,651** manifested\n'
     '   files and left both the rewritten set and the substitution count untouched. **At this revision\n'
     '   `MANIFEST.csv` registers %d files** (`wc -l MANIFEST.csv` minus the header) and `data/` holds **%d**\n'
     '   of them — both are re-derived by `code/analysis/derive_release_numbers.py`.' % (N_MAN, N_DATA)),
    ("4. **31** files merely *contain* one of the placeholder strings: `grep -rlE '<REDACTED-|<WORKDIR>|<SHARED-DIR>' . | wc -l`\n"
     "   → **31**, i.e. the 30 rewritten files above plus this `README.md`, which names the placeholders on purpose.",
     "4. **%d** files merely *contain* one of the placeholder strings: `grep -rlE '<REDACTED-|<WORKDIR>|<SHARED-DIR>' . | wc -l`\n"
     "   → **%d** (the sanitiser's own rewritten set is count 3 above; the remainder only quote a placeholder\n"
     "   string — this `README.md` does so on purpose)." % (n_ph, n_ph)),
    # data/ 文件数（本轮投了 6 个 e8b_aerial CSV，旧值 2,767 已不成立）
    ('**Nothing under `data/` was altered.** Every one of the **3785** files under `data/` is byte-identical to',
     '**Nothing under `data/` was altered.** Every one of the **%d** files under `data/` is byte-identical to' % N_DATA),
    ('of the six placeholder patterns above in the file, and a scan of all 3785 released data files finds **zero**',
     'of the six placeholder patterns above in the file, and a scan of all %d released data files finds **zero**' % N_DATA),
]

readme = rd(README)
SUB = [x for x in SUB if x is not None]
# 依赖消毒台账的那一条：**只在台账在场时**参与（见上）。
if san is not None:
    SUB.append((
        '3. **30** files were rewritten by the sanitiser, in **58** substitutions (the table above). This set cannot be',
        '3. **%d** files were rewritten by the sanitiser, in **%d** substitutions (the table above). This set cannot be'
        % (len(san['files']), san['substitutions'])))
if san is None:
    print('  ⚠ 未找到消毒台账（作者侧）⇒ 跳过依赖它的替换；其余照常。')
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
