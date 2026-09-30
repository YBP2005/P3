# -*- coding: utf-8 -*-
"""ea_lang_manifest.py —— 生成 E-C 的**同 item 配对清单**（CN 已有结果 ↔ EN 待跑）。

为什么配对：语言等价性检验必须是**同一批图**上的对照，否则语言差异会和 item 差异混在一起。
CN 侧的 item 直接取自已有产物（`analysis/ea_z0/` 的 Z0 结果、`e2xt_a800/zero/` 的 D0 结果）。
输出 `analysis/work/_ea_lang/items.csv`（列：model,pool,item），由 `deploy.py --put` 上传。
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
import csv
import io
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')
ROOT = NR('analysis')
OUTDIR = RP('analysis', 'work', '_ea_lang')
os.makedirs(OUTDIR, exist_ok=True)
FAM = ['InternVL3_5-8B', 'Phi-3.5-vision-instruct', 'llava-onevision-qwen2-7b-ov',
       'gemma3-12b', 'Qwen3-VL-32B-Instruct']

rows = []
for m in FAM:
    # Z0 两池：item 列表各模型相同（同一批裁剪），但为稳妥仍按模型各自的产物取
    for pool, suf in (('z0easy', 'z0easy'), ('z0hard', 'z0hard')):
        p = os.path.join(NR('analysis', 'ea_z0'), 'e1_%s_%s_base_native.csv' % (m, suf))
        if not os.path.exists(p):
            print('  缺 %s' % os.path.basename(p)); continue
        for r in csv.DictReader(io.open(p, encoding='utf-8-sig')):
            rows.append((m, pool, r['item']))
    # D0：st_a / ucf 的语料答0池（与 E-A 判决式同池）
    for pool, ds in (('d0st_a', 'st_a'), ('d0ucf', 'ucf')):
        got = False
        for cand in (os.path.join(RP('analysis', 'e2xt_a800', 'zero'), 'e1_%s_%s_base.csv' % (m, ds)),
                     os.path.join(RP('analysis', 'e2xt_a800', 'ablate3'), 'e1_%s_%s_base_native.csv' % (m, ds))):
            if os.path.exists(cand):
                for r in csv.DictReader(io.open(cand, encoding='utf-8-sig')):
                    rows.append((m, pool, r['item']))
                got = True
                break
        if not got:
            print('  %s 的 %s 无 D0 对照件（跳过该池）' % (m, ds))

outp = RP('analysis', 'work', '_ea_lang', 'items.csv')
with io.open(outp, 'w', newline='', encoding='utf-8') as f:
    w = csv.writer(f)
    w.writerow(['model', 'pool', 'item'])
    for r in rows:
        w.writerow(r)
print('写出 %s：%d 行' % (outp, len(rows)))
from collections import Counter
c = Counter((m, p) for m, p, _ in rows)
for k in sorted(c):
    print('   %-28s %-8s %d' % (k[0], k[1], c[k]))
print('总调用（×2 臂）= %d' % (2 * len(rows)))
