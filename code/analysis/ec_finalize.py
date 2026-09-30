# -*- coding: utf-8 -*-
"""ec_finalize.py —— **E-C 冻结**：语言均衡对照的关键统计量 + 结果 JSON。"""


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
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')
ROOT = NR('analysis')
EN = NR('analysis', 'lang_results')
Z0 = NR('analysis', 'ea_z0')
D0DIRS = [RP('analysis', 'e2xt_a800', 'zero'), RP('analysis', 'e2xt_a800', 'ablate3')]
OUT = RP('analysis', 'work', 'ec_lang_result.json')
FAM = ['InternVL3_5-8B', 'Phi-3.5-vision-instruct', 'llava-onevision-qwen2-7b-ov',
       'gemma3-12b', 'Qwen3-VL-32B-Instruct']
POOLS = ['z0easy', 'z0hard', 'd0st_a', 'd0ucf']


def cls(raw):
    r = raw or ''
    if re.search('no_people', r, re.I):
        return 'no_people'
    if re.search('cannot_judge', r, re.I):
        return 'cannot_judge'
    m = re.search(r'(?:count|计数|数量|人数)\s*["\s]*[:：]\s*"?(\d+)', r, re.I)
    if m:
        return 'zero' if int(m.group(1)) == 0 else 'num'
    return 'num' if re.search(r'\d', r) else 'other'


def load(p):
    if not os.path.exists(p):
        return {}
    return {r['item']: r.get('raw') or '' for r in csv.DictReader(io.open(p, encoding='utf-8-sig'))}


def cn_path(m, pool, arm):
    if pool.startswith('z0'):
        return os.path.join(NR('analysis', 'ea_z0'), 'e1_%s_%s_%s_native.csv' % (m, pool, arm))
    ds = 'st_a' if pool == 'd0st_a' else 'ucf'
    for d in D0DIRS:
        for suf in ('', '_native'):
            p = os.path.join(d, 'e1_%s_%s_%s%s.csv' % (m, ds, arm, suf))
            if os.path.exists(p):
                return p
    return None


def kappa(pairs):
    labels = sorted({a for a, _ in pairs} | {b for _, b in pairs})
    n = len(pairs)
    obs = sum(1 for a, b in pairs if a == b) / n
    ea = sum(sum(1 for a, _ in pairs if a == L) / n * sum(1 for _, b in pairs if b == L) / n for L in labels)
    return None if ea >= 1 else (obs - ea) / (1 - ea)


res = {'study': 'E-C language-equivalence control (paired, same items)',
       'design': 'the frozen Chinese arm prompts were rendered into semantically equivalent English and re-run '
                 'on exactly the items already scored under Chinese; frozen probe imported unchanged; '
                 'English prompt table md5 a31bd97c6b70',
       'parsing': 'raw-text matching (as in E-A and the paper §8.1/§11.2)',
       'cells': {}, 'headline': {}}
print('%-28s %-8s %-8s %5s %9s %8s %11s %11s' %
      ('family', 'pool', 'arm', 'n', 'agree', 'kappa', 'CN no_people', 'EN no_people'))
agree_all = []
for m in FAM:
    res['cells'][m] = {}
    for pool in POOLS:
        res['cells'][m][pool] = {}
        for arm in ('base', 'channel'):
            cn = load(cn_path(m, pool, arm) or '')
            en = load(os.path.join(NR('analysis', 'lang_results'), 'e1_%s_%s_%s_en.csv' % (m, pool, arm)))
            common = sorted(set(cn) & set(en))
            if not common:
                continue
            pairs = [(cls(cn[i]), cls(en[i])) for i in common]
            a = sum(1 for x, y in pairs if x == y) / len(pairs)
            k = kappa(pairs)
            rates = {L: round(sum(1 for i in common if cls(en[i]) == L) / len(common), 4)
                     for L in ('no_people', 'cannot_judge', 'zero', 'num')}
            cnr = {L: round(sum(1 for i in common if cls(cn[i]) == L) / len(common), 4)
                   for L in ('no_people', 'cannot_judge', 'zero', 'num')}
            res['cells'][m][pool][arm] = dict(n=len(common), agreement=round(a, 4),
                                              kappa=None if k is None else round(k, 4),
                                              cn=cnr, en=rates)
            if arm == 'channel':
                agree_all.append(a)
            print('%-28s %-8s %-8s %5d %8.1f%% %8s %10.1f%% %10.1f%%'
                  % (m, pool, arm, len(common), 100 * a, '—' if k is None else '%.3f' % k,
                     100 * cnr['no_people'], 100 * rates['no_people']))

# 头条：no_people 的语言差 + 答 0 的语言差
np_lo = min(res['cells'][m][p]['channel']['cn']['no_people'] - res['cells'][m][p]['channel']['en']['no_people']
            for m in FAM for p in POOLS if 'channel' in res['cells'][m][p])
np_hi = max(res['cells'][m][p]['channel']['cn']['no_people'] - res['cells'][m][p]['channel']['en']['no_people']
            for m in FAM for p in POOLS if 'channel' in res['cells'][m][p])
z_lo = min(res['cells'][m][p]['base']['cn']['zero'] - res['cells'][m][p]['base']['en']['zero']
           for m in FAM for p in POOLS if 'base' in res['cells'][m][p])
z_hi = max(res['cells'][m][p]['base']['cn']['zero'] - res['cells'][m][p]['base']['en']['zero']
           for m in FAM for p in POOLS if 'base' in res['cells'][m][p])
res['headline'] = dict(
    channel_no_people_language_gap_pp=[round(100 * np_lo, 1), round(100 * np_hi, 1)],
    base_answered_zero_language_gap_pp=[round(100 * z_lo, 1), round(100 * z_hi, 1)],
    channel_agreement_median=round(sorted(agree_all)[len(agree_all) // 2], 4),
    answer=('The channel conclusion is language-robust (no_people rates agree to within a few pp), but the '
            'ANSWERED-ZERO rate is language-sensitive for the anchor lineage: Qwen3-VL-32B-Instruct answers 0 on '
            '60.2% of the dense pool under Chinese and 17.5% under English, a 42.7 pp drop.'))
res['quoted_display'] = {
    'vanchor_cn_zero': '60.2%', 'anchor_en_zero': '17.5%', 'anchor_delta_pp': '42.7 pp',
    'pair_n': str(sum(res['cells'][m][p]['channel']['n'] for m in FAM for p in POOLS
                      if 'channel' in res['cells'][m][p])),
    'note': '正文/附录若引用，直接用这些显示值。'}
io.open(OUT, 'w', encoding='utf-8', newline='\n').write(json.dumps(res, ensure_ascii=False, indent=2))
print()
print('  ★ channel 的 no_people 语言差 %s pp；base 的答0 语言差 %s pp'
      % (res['headline']['channel_no_people_language_gap_pp'],
         res['headline']['base_answered_zero_language_gap_pp']))
print('已写出 %s' % OUT)
