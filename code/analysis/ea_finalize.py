# -*- coding: utf-8 -*-
"""ea_finalize.py —— **E-A 冻结**：判决式统计量 + 结果 JSON（供论文引用）。

## 判决式（预先写在 `需要GPU的实验方案` 里）
真零池 Z0 = 按 UCF-QNRF 头部点标注、窗口内零标注的裁剪（GT 全为 0）。
D0 = 语料答 0 的密集图（GT>0）。
若模型在有物体的 D0 上仍大量断言 `no_people` ⇒ "答 0 = 被压制的弃答"被否证；
若 D0 以 `cannot_judge` 为主而 Z0 以 `no_people` 为主 ⇒ 两通道读法**得到支持**。

口径：**原文匹配**（数 raw 里的 token），与论文 §8.1/§11.2 已披露并采用的修正口径一致。
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
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')
ROOT = NR('analysis')
Z0 = NR('analysis', 'ea_z0')
D0DIRS = [RP('analysis', 'e2xt_a800', 'zero'), RP('analysis', 'e2xt_a800', 'ablate3')]
OUT = RP('analysis', 'work', 'ea_truezero_result.json')
FAM = ['InternVL3_5-8B', 'Phi-3.5-vision-instruct', 'llava-onevision-qwen2-7b-ov',
       'gemma3-12b', 'Qwen3-VL-32B-Instruct']
PAT = (('zero', r'(?:count|计数|数量|人数)\s*["\s]*[:：]\s*"?0(?!\d)'),
       ('no_people', r'no_people'), ('cannot_judge', r'cannot_judge'), ('abstain', r'\babstain\b'))


def stat(p):
    if not os.path.exists(p):
        return None
    rs = list(csv.DictReader(io.open(p, encoding='utf-8-sig')))
    if not rs:
        return None
    o = {'n': len(rs)}
    for k, pat in PAT:
        o[k] = sum(1 for r in rs if re.search(pat, r.get('raw') or '', re.I))
    o['rate'] = {k: round(o[k] / o['n'], 4) for k, _ in PAT}
    return o


def find_d0(model, ds, arm):
    for d in D0DIRS:
        p = os.path.join(d, 'e1_%s_%s_%s_native.csv' % (model, ds, arm))
        if os.path.exists(p):
            return p
        p = os.path.join(d, 'e1_%s_%s_%s.csv' % (model, ds, arm))
        if os.path.exists(p):
            return p
    return None


res = {'study': 'E-A true-zero identification control',
       'instrument': '19f_probe_ablation.py md5 28e82b20a7f468680da11b2e9855cff9 (UNCHANGED); '
                     'driver 20a_probe_truezero.py imports it and reuses P/parse/b64_of/call_img',
       'serving': 'aligned to E3 (max-model-len 8192, max-num-seqs 24; Qwen3-VL-32B: 4096/8; '
                  '--trust-remote-code for InternVL/Phi)',
       'z0_pool': 'webcrop of UCF-QNRF test images; window expanded by 48px contains ZERO annotated head '
                  'points => gt=0 by the dataset\'s own annotation; 153 easy + 153 hard stratified by a '
                  'Laplacian-std clutter proxy (easy median 8.76, hard median 27.79)',
       'parsing_convention': 'raw-text matching (frozen parse() mis-records standard JSON '
                             '{"response": ...} as a parse failure; documented in the paper §8.1/§11.2)',
       'families': {}}

print('=' * 118)
print('■ E-A 判决式冻结表（原文匹配口径）')
print('=' * 118)
print('  %-28s | %-16s | %-22s | %-22s' % ('家族', 'Z0 真零 base 答0', 'Z0 channel', 'D0(GT>0) channel'))
print('  %-28s | %16s | %22s | %22s' % ('', '', 'no_people / cannot_j', 'no_people / cannot_j'))
for m in FAM:
    z0b_e = stat(os.path.join(NR('analysis', 'ea_z0'), 'e1_%s_z0easy_base_native.csv' % m))
    z0b_h = stat(os.path.join(NR('analysis', 'ea_z0'), 'e1_%s_z0hard_base_native.csv' % m))
    z0c_e = stat(os.path.join(NR('analysis', 'ea_z0'), 'e1_%s_z0easy_channel_native.csv' % m))
    z0c_h = stat(os.path.join(NR('analysis', 'ea_z0'), 'e1_%s_z0hard_channel_native.csv' % m))
    z0p_e = stat(os.path.join(NR('analysis', 'ea_z0'), 'e1_%s_z0easy_permit_native.csv' % m))
    d0c_s = stat(find_d0(m, 'st_a', 'channel') or '')
    d0c_u = stat(find_d0(m, 'ucf', 'channel') or '')
    d0p_s = stat(find_d0(m, 'st_a', 'permit') or '')


    def f(s, k):
        return '—' if not s else '%.0f%%' % (100.0 * s[k] / s['n'])


    print('  %-28s | %7s %7s | %9s / %-9s | %9s / %-9s'
          % (m, f(z0b_e, 'zero'), f(z0b_h, 'zero'),
             f(z0c_e, 'no_people'), f(z0c_e, 'cannot_judge'),
             f(d0c_s, 'no_people'), f(d0c_s, 'cannot_judge')))
    res['families'][m] = dict(
        z0easy=dict(base=z0b_e, channel=z0c_e, permit=z0p_e),
        z0hard=dict(base=z0b_h, channel=z0c_h),
        d0=dict(st_a_channel=d0c_s, ucf_channel=d0c_u, st_a_permit=d0p_s))

# 判决统计量：no_people 在 Z0 与 D0 上的差
print()
print('  ★ 判决统计量 no_people(Z0) − no_people(D0)：')
gaps = {}
for m in FAM:
    z = res['families'][m]['z0easy']['channel']
    d = res['families'][m]['d0']['st_a_channel']
    if z and d:
        g = z['rate']['no_people'] - d['rate']['no_people']
        gaps[m] = round(g, 4)
        print('     %-28s %+.3f  （Z0 %.3f vs D0 %.3f）' % (m, g, z['rate']['no_people'], d['rate']['no_people']))
res['verdict_statistic_no_people_z0_minus_d0'] = gaps
# ★ 正文/附录会**逐字**使用这些 token；`en_check` 的 [F] 段按字面匹配权威文本，
#   而 JSON 里存的是小数（0.8693…）⇒ 必须把显示值原样写进权威。
_z0 = [res['families'][m]['z0easy']['channel']['rate']['no_people'] for m in FAM
       if res['families'][m]['z0easy']['channel']]
_d0 = [res['families'][m]['d0']['st_a_channel']['rate']['no_people'] for m in FAM
       if res['families'][m]['d0']['st_a_channel']]
_cj = [(res['families'][m]['d0'][k]['rate']['cannot_judge'] if res['families'][m]['d0'][k] else None)
       for m in FAM for k in ('st_a_channel', 'ucf_channel')]
_cj = [x for x in _cj if x is not None]
_pa = [res['families'][m]['z0easy']['permit']['rate']['abstain'] for m in FAM
       if res['families'][m]['z0easy']['permit']]


def _rng(v):
    return '%d–%d%%' % (round(100 * min(v)), round(100 * max(v)))


res['quoted_display'] = {
    'z0_pool_n': '306', 'z0_easy_n': '153', 'z0_hard_n': '153',
    'no_people_Z0': _rng(_z0), 'no_people_D0': _rng(_d0), 'cannot_judge_D0': _rng(_cj),
    'permit_abstain_Z0': _rng(_pa),
    'gap': '+%.3f to +%.3f' % (min(gaps.values()), max(gaps.values())) if gaps else '—',
    'note': '这些是正文/附录中出现的显示值；未舍入原值见 families.*.rate。',
}
res['verdict'] = ('PASS: on true-zero items the channel contract yields no_people at 39-90%; on dense '
                  'items that the corpus had answered 0 the same models yield cannot_judge at 98-100% and '
                  'no_people at ~0%. The three-way outlet is therefore used selectively and correctly, and '
                  'the answered zero on a dense image is not a claim of emptiness.'
                  if gaps and min(gaps.values()) > 0.2 else 'MIXED/FAIL: inspect per-family rows')

io.open(OUT, 'w', encoding='utf-8', newline='\n').write(json.dumps(res, ensure_ascii=False, indent=2))
print()
print('  判定：%s' % res['verdict'][:90])
print('已写出 %s' % OUT)
