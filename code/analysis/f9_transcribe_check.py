# -*- coding: utf-8 -*-
"""f9_transcribe_check.py —— **Q3 路径 B**：把 F.9 从"手打表"升级为**可核验转录**。

## 背景
`fix_ten_units.py` L46–74 把 F.9 的表**逐字写死**，注释说来源是"中文骨架 §8.10 ③ 表"。
本仓库的纪律是"数字一律脚本现算并写进 `*_quoted.json`，再登记为权威；绝不手打"，
而 F.9 是唯一例外，且它正是 §7.3 引用的冻结对象。裁决 Q3 允许两条路；本脚本实现**路径 B**：
  · 把 F.9 表内的**每一个字符级数值**与**上游骨架的主表**逐一比对，输出 10 行 × 4 列全命中的日志；
  · 把"转录记录 + 核验日志 + 上游文件 md5 + 口径与可部署性声明"写成 `f9_quoted.json` 并登记为权威；
  · **同时如实记录本脚本能证明什么、不能证明什么**（见 §不可证部分）。

## 不可证部分（必须与 F.9 一起披露，不许省）
`f9_repro.py` 证明：在 F.9 自己声明的 **pooled** 口径下、**样本内**，
  · 保序（oracle 方向 `p_cal=f(g)`）**恒等于 C0**（PAVA 保和 ⇒ Σp_cal=Σp）；
  · 保序（可部署方向 `g=f(p)`）与分位数映射**恒等于 0**（Σp_cal=Σg）。
且用仓库内可指认的来源**无法**复现 F.9 的 ISO 列（任何"族 × 口径"组合都对不上，差 1.4–3×）。
⇒ 因此 `f9_quoted.json` 里必须写：**该列的"可部署性"未经独立复算确认**，
  稿内引用它时必须同时写**口径名**与**"转录"字样**。
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
import hashlib
import io
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')
ROOT = NR()
SUP = RP('PaperB_英文补充材料_PR_20260919.md')
ZH = NR('PaperB_章节骨架_v3_可确证性_20260911.md')
FIX = RP('analysis', 'work', 'fix_ten_units.py')
OUT = RP('analysis', 'work', 'f9_quoted.json')

# F.9 表内 10 行的四个数值列（与 fix_ten_units.py L56–65 一致）
COLS = ['shared_affine', 'isotonic', 'quantile_map', 'isotonic_CI']


def md5(p):
    return hashlib.md5(open(p, 'rb').read()).hexdigest()


def read(p):
    raw = open(p, 'rb').read()
    for enc, bom in (('utf-16', b'\xff\xfe'), ('utf-8-sig', b'\xef\xbb\xbf')):
        if raw.startswith(bom):
            return raw.decode(enc)
    return raw.decode('utf-8', 'replace')


sup = read(SUP)
zh = read(ZH)

# ---- 1) 从补充材料里抓 F.9 的表格行 ----
i = sup.find('### F.9 The ten (knob × domain) units, isotonic-calibrated')
assert i > 0, 'F.9 节未找到'
f9blk = sup[i:sup.find('### F.10', i)]
rows_f9 = []
for ln in f9blk.splitlines():
    if not ln.strip().startswith('|') or '---' in ln or 'Unit (knob' in ln:
        continue
    c = [x.strip() for x in ln.strip().strip('|').split('|')]
    if len(c) < 5:
        continue
    nums = re.findall(r'-?\d+\.\d+', ln)
    if len(nums) < 5:
        continue
    rows_f9.append(dict(unit=c[0].strip('*').strip(), nums=[float(x) for x in nums]))
print('F.9 抓到 %d 行' % len(rows_f9))

# ---- 2) 从中文骨架 §8.10 ③ 的表抓上游值 ----
j = zh.find('③ 更强校准族')
assert j > 0, '骨架 §8.10 ③ 未找到'
zhblk = zh[j:j + 3000]
up = {}
for ln in zhblk.splitlines():
    ln = ln.lstrip()
    while ln.startswith('>'):            # ★ 骨架 §8.10 的表在 blockquote 里（行首 > |），要先剥掉
        ln = ln[1:].lstrip()
    if not ln.startswith('|'):
        continue
    c = [x.strip() for x in ln.strip().strip('|').split('|')]
    if len(c) < 5 or '单元' in c[0] or '---' in ln:
        continue
    nums = re.findall(r'-?\d+\.\d+', ln)
    if len(nums) >= 5:
        up[c[0].replace('**', '').strip()] = [float(x) for x in nums]
print('骨架 §8.10 ③ 抓到 %d 行' % len(up))

# ---- 3) 键映射（骨架用「·」「/」，F.9 用英文）----
KEY = [('Detection, in-domain / VisDrone', '检测·域内 VisDrone'),
       ('VLM, output contract / InternVL', 'VLM·输出契约 / ivl'),
       ('VLM, output contract / Qwen3-VL-32B', 'VLM·输出契约 / q32'),
       ('Detection, zero-shot COCO', '检测·零样本 COCO'),
       ('Detection, in-domain / BBBC005', '检测·域内 BBBC005'),
       ('Density regression, official DM-Count / UCF-QNRF', '密度·官方 DM / ucf'),
       ('Density regression, official DM-Count / ShanghaiTech-A', '密度·官方 DM / st_a'),
       ('VLM, pixel budget / UCF-QNRF', 'VLM·像素预算 / ucf'),
       ('VLM, pixel budget / VisDrone', 'VLM·像素预算 / visdrone'),
       ('VLM, pixel budget / ShanghaiTech-A', 'VLM·像素预算 / st_a')]

print()
print('=' * 120)
print('■ 转录核验：F.9（补充材料）× 骨架 §8.10 ③（上游）逐值比对')
print('=' * 120)
print('  %-46s %-22s %s' % ('F.9 单元', '骨架单元', '比对结果'))
ok_all, detail = True, []
for en, zhk in KEY:
    r = next((x for x in rows_f9 if x['unit'] == en), None)
    u = up.get(zhk)
    if r is None or u is None:
        print('  %-46s %-22s !! 缺（F.9=%s 骨架=%s）' % (en, zhk, r is not None, u is not None))
        ok_all = False
        detail.append(dict(unit=en, src=zhk, ok=False, why='missing'))
        continue
    # F.9 行内数值顺序：shared_affine, isotonic, quantile_map, CI_lo, CI_hi
    mine = [r['nums'][0], r['nums'][1], r['nums'][2], r['nums'][3], r['nums'][4]]
    same = mine == u[:5]
    ok_all &= same
    print('  %-46s %-22s %s   F.9=%s  骨架=%s'
          % (en, zhk, '✓' if same else '✗', mine, u[:5]))
    detail.append(dict(unit=en, src_line_key=zhk, f9=mine, upstream=u[:5], ok=bool(same)))

print()
print('  ⇒ 10 行 × 4 列（含 CI 两端）**全部逐值一致**：%s' % ('是 ✓' if ok_all else '否 ✗'))
assert ok_all, '转录核验失败：不得把 F.9 登记为"可核验转录"'

out = dict(
    title='F.9 ten (knob x domain) units — verifiable transcription record',
    kind='transcription (Q3 path B)',
    transcribed_into=os.path.basename(SUP),
    transcribed_from=os.path.basename(ZH),
    transcribed_from_md5=md5(ZH),
    transcribed_from_location='§8.10 ③ 「更强校准族（保序回归 / 分位数映射）…」主表',
    literal_script_fix_ten_units=os.path.basename(FIX),
    literal_script_note='fix_ten_units.py L46–74 以字面量写入 F.9；本记录的作用是把"手打"升级为"可核验转录"。',
    columns=COLS,
    rows=detail,
    verification='所有 10 行 × 4 数值列（含 ISO 95% CI 两端）与上游骨架表逐值一致（脚本 f9_transcribe_check.py，assert 通过）。',
    # ★ 必须与 F.9 同披露的部分
    deployability_disclosure=(
        'NOT independently reproduced. The upstream computation of the ISO column is not recoverable from the '
        'released records: f9_repro.py shows that under the pooled caliber declared in F.9 the in-sample isotonic '
        'calibration is identically equal to C0 in the oracle direction (PAVA preserves the sum) and identically '
        'zero in the deployable direction, and no family x caliber combination available in this repository '
        'reproduces the printed ISO values (mismatches of 1.4-3x). Citations of this table must therefore state '
        'the calibration caliber and mark the table as transcribed.'),
    reproduction='python -u analysis/work/f9_transcribe_check.py   (exit 0 = all 10 rows match; asserts)',
)
io.open(OUT, 'w', encoding='utf-8', newline='\n').write(json.dumps(out, ensure_ascii=False, indent=2))
print()
print('已写出 %s' % OUT)
