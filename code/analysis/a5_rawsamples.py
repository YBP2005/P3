# -*- coding: utf-8 -*-
"""看原始输出：确认"契约生效"是真的（permit 后 base 答 0 的 item 被换成 abstain/数字），
以及 unparsed 到底是什么文本（LLaVA 密集域解析率低的原因）。"""


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
D = RP('analysis', 'e2xt_a800', 'merged')
ABSTAIN = ('abstain', 'cannot_judge', 'no_people')
CASES = [
    ('InternVL3_5-8B', 'visdrone'),
    ('Phi-3.5-vision-instruct', 'visdrone'),
    ('llava-onevision-qwen2-7b-ov', 'visdrone'),
    ('gemma3-12b', 'visdrone'),
]


def load(f, ds, arm):
    p = os.path.join(RP('analysis', 'e2xt_a800', 'merged'), 'e1_%s_%s_%s.csv' % (f, ds, arm))
    if not os.path.exists(p):
        return None
    return {r['item']: r for r in csv.DictReader(io.open(p, encoding='utf-8-sig'))}


def is_abstain(r):
    raw = str(r.get('raw') or '').lower()
    return any(k in raw for k in ABSTAIN)


for f, ds in CASES:
    b = load(f, ds, 'base')
    p = load(f, ds, 'permit')
    c = load(f, ds, 'channel')
    print('=== %s / %s ===' % (f, ds))
    zs = [k for k, r in b.items() if str(r.get('pred', '')).strip() in ('0', '0.0')]
    print('base 答 0 的 item：%d 个' % len(zs))
    for k in zs[:2]:
        print('  item=%s base_raw=%s' % (k, str(b[k]['raw'])[:120].replace('\n', ' ')))
        if p and k in p:
            print('            permit_pred=%-8s permit_raw=%s'
                  % (p[k]['pred'], str(p[k]['raw'])[:120].replace('\n', ' ')))
        if c and k in c:
            print('            channel_pred=%-8s channel_raw=%s'
                  % (c[k]['pred'], str(c[k]['raw'])[:120].replace('\n', ' ')))
    if not zs:
        # 该家族在该域不出零：看 base 的非零输出与解析失败的样本
        ups = [k for k, r in b.items() if not str(r.get('pred') or '').strip()]
        print('base 未解析样本 %d 个，示例：' % len(ups))
        for k in ups[:3]:
            print('  item=%s raw=%s' % (k, str(b[k]['raw'])[:150].replace('\n', ' ')))
        nz = [k for k, r in b.items() if str(r.get('pred') or '').strip() not in ('', '0', '0.0')]
        for k in nz[:2]:
            print('  item=%s pred=%s gt=%s raw=%s'
                  % (k, b[k]['pred'], b[k]['gt'], str(b[k]['raw'])[:110].replace('\n', ' ')))
    print()
