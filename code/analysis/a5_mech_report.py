# -*- coding: utf-8 -*-
"""A5 机制臂对照：在**共同 item 集合**上比**比率**（不是计数），检验 E2 的核心机制结论
——"门是 abstain 词位，不是'要求逐项枚举'"——是否在新家族上复现。

为什么要改成比率：E2 的 `base` 文件是**多轮追加**的（同一家族同域可能跑过全池 + 150 抽样，
如 Qwen3-VL-32B/st_a 有 412 行），而 `enum/locate/enumAbstain` 臂各只有一轮（103 行）。
拿计数对比会把"分母不同"误读成"机制变了"（2026-09-22 实测踩到）。

判据（**本脚本自订、非预注册**；冻结判据 a5_criteria_frozen.json 不含这三个臂，故在此写明）：
  在 base 有零、且四臂共同 item ≥ 30 的单元格上：
    腿1 `enumAbstain` 的答 0 率 ≤ 5%（加了出口就归零）
    腿2 `enum` 的答 0 率 ≥ 5%（只要求枚举、不给出口，零仍在）
    腿3 `enum` 率 / `base` 率 ≥ 0.25（枚举并未把零清掉一个数量级）
  三条同时成立 = 机制复现；否则该单元格记为**例外**并如实报告。
用法：python a5_mech_report.py [merged_dir]
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
D = sys.argv[1] if len(sys.argv) > 1 else RP('analysis', 'e2xt_a800', 'merged')
E2D = RP('analysis', 'e2_newh20')
ABSTAIN = ('abstain', 'cannot_judge', 'no_people')
ARMS = ['base', 'enum', 'locate', 'enumAbstain', 'permit']
FAMS = ['gemma3-12b', 'InternVL3_5-8B', 'Phi-3.5-vision-instruct',
        'llava-onevision-qwen2-7b-ov', 'qwen3-vl-32b-awq']


def load(fam, ds, arm):
    for d, pre in ((D, ''), (E2D, ''), (E2D, 'nz__')):
        p = os.path.join(d, '%se1_%s_%s_%s.csv' % (pre, fam, ds, arm))
        if os.path.exists(p):
            out = {}
            for r in csv.DictReader(io.open(p, encoding='utf-8-sig')):
                pv = str(r.get('pred') or '').strip()
                raw = str(r.get('raw') or '').lower()
                out[r['item']] = (pv in ('0', '0.0'),
                                  any(k in raw for k in ABSTAIN))
            return out
    return None


def rate(d, keys):
    if not keys:
        return None, None
    z = sum(1 for k in keys if d[k][0])
    a = sum(1 for k in keys if d[k][1])
    return z / float(len(keys)), a


print('%-28s %-9s %6s | %-16s %-16s %-16s %-16s' %
      ('家族', '域', '共同n', 'base 零率(弃答)', 'enum 零率(弃答)', 'locate 零率(弃答)', 'enumAbstain 零率(弃答)'))
exc = []
for fam in FAMS:
    for ds in ('st_a', 'ucf', 'visdrone', 'aitod'):
        tabs = {a: load(fam, ds, a) for a in ARMS}
        if tabs['base'] is None or tabs['enum'] is None or tabs['enumAbstain'] is None:
            continue
        keys = set(tabs['base'])
        for a in ARMS:
            if tabs[a]:
                keys &= set(tabs[a])
        keys = sorted(keys)
        if not keys:
            continue
        cells = []
        for a in ARMS:
            if tabs[a] is None:
                cells.append('—')
            else:
                z, ab = rate(tabs[a], keys)
                cells.append('%.3f(%.3f)' % (z, ab))
        print('%-28s %-9s %6d | %-16s %-16s %-16s %-16s'
              % (fam, ds, len(keys), cells[0], cells[1], cells[2], cells[3]))
        rb = rate(tabs['base'], keys)[0]
        re_, ra = rate(tabs['enum'], keys)[0], rate(tabs['enumAbstain'], keys)[0]
        if rb >= 0.10 and len(keys) >= 30:
            ok = (ra <= 0.05) and (re_ >= 0.05) and (rb > 0 and re_ / rb >= 0.25)
            if not ok:
                exc.append((fam, ds, rb, re_, ra))
print()
if exc:
    print('例外（未满足三条腿的单元格）：')
    for fam, ds, rb, re_, ra in exc:
        print('  %-28s %-9s base=%.3f enum=%.3f enumAbstain=%.3f' % (fam, ds, rb, re_, ra))
else:
    print('所有 base 零率 ≥10% 的单元格都满足三条腿：机制跨家族复现。')
