# -*- coding: utf-8 -*-
"""看原始输出：确认"契约生效"是真的（permit 后 base 答 0 的 item 被换成 abstain/数字），
以及 unparsed 到底是什么文本（LLaVA 密集域解析率低的原因）。"""
import csv
import io
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')
D = r'<WORKDIR>\PaperB\analysis\e2xt_a800\merged'
ABSTAIN = ('abstain', 'cannot_judge', 'no_people')
CASES = [
    ('InternVL3_5-8B', 'visdrone'),
    ('Phi-3.5-vision-instruct', 'visdrone'),
    ('llava-onevision-qwen2-7b-ov', 'visdrone'),
    ('gemma3-12b', 'visdrone'),
]


def load(f, ds, arm):
    p = os.path.join(D, 'e1_%s_%s_%s.csv' % (f, ds, arm))
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
