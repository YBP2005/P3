# -*- coding: utf-8 -*-
"""B1 完整分析（9 配置 + 机制臂）：公开基准 FSC-147 上的契约门控、口径→榜单、以及反例诊断。

比 `b1_fsc_analysis.py` 多做两件事：
  ① 把机制臂（channel / enumAbstain）并入，用于解释"某配置在 permit 下仍大量答 0"是**出口措辞**问题
     还是**模型拒绝**问题；
  ② 对反例配置直接抽样看 `raw`（是否把 0 写在散文里、是否被 max_tokens 截断）。
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
import itertools
import json
import math
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')
D = RP('analysis', 'fsc_a800')
ABSTAIN = ('abstain', 'cannot_judge', 'no_people')
MODELS = ['gemma3-12b', 'InternVL3_5-8B', 'Phi-3.5-vision-instruct',
          'llava-onevision-qwen2-7b-ov', 'Qwen3-VL-32B-Instruct',
          'Qwen3-VL-8B-Instruct', 'Qwen3-VL-4B-Instruct',
          'Qwen3-VL-30B-A3B-Instruct', 'Qwen2.5-VL-3B-Instruct']
ARMS = ['base', 'permit', 'channel', 'enumAbstain']


def wilson(k, n, z=1.959963985):
    if n == 0:
        return (None, None)
    p = k / float(n)
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def load(fn, keep_raw=False):
    p = os.path.join(RP('analysis', 'fsc_a800'), fn)
    if not os.path.exists(p):
        return None
    out = {}
    for r in csv.DictReader(io.open(p, encoding='utf-8-sig')):
        raw = str(r.get('raw') or '')
        rl = raw.lower()
        try:
            gt = float(r['gt'])
        except (KeyError, TypeError, ValueError):
            continue
        if any(k in rl for k in ABSTAIN):
            v = None
        else:
            try:
                v = float(str(r['pred']).strip())
            except ValueError:
                v = None
        out[r['item']] = (v, gt, rl, raw[:160]) if keep_raw else (v, gt, rl)
    return out


print('=' * 108)
print('① FSC-147 契约门控（9 配置；同一批 300 张分层抽样测试图）')
print('=' * 108)
print('%-28s %6s %8s %11s %14s %10s' % ('配置', 'n', 'base 答0', 'permit 仍0', 'Wilson 95% CI', 'channel 仍0'))
gate = {}
for m in MODELS:
    b, p = load('fsc_%s_base.csv' % m), load('fsc_%s_permit.csv' % m)
    if not b or not p:
        continue
    keys = sorted(set(b) & set(p))
    z = [k for k in keys if b[k][0] == 0]
    still = sum(1 for k in z if p[k][0] == 0)
    lo, hi = wilson(still, len(z)) if z else (None, None)
    ch = load('fsc_%s_channel.csv' % m)
    ch_still = None
    if ch:
        kk = [k for k in z if k in ch]
        ch_still = sum(1 for k in kk if ch[k][0] == 0)
    gate[m] = dict(n=len(keys), n_zero=len(z), still=still,
                   ratio=still / float(len(z)) if z else None,
                   ci=[lo, hi], channel_still=ch_still)
    print('%-28s %6d %8d %5d (%5.1f%%) %14s %10s'
          % (m, len(keys), len(z), still, 100 * still / len(z) if z else 0,
             ('[%.1f%%, %.1f%%]' % (100 * lo, 100 * hi)) if z else '—',
             ('%d' % ch_still) if ch_still is not None else '—'))

print()
print('=' * 108)
print('② 两口径 + 口径→榜单（9 配置）')
print('=' * 108)
tab = []
for m in MODELS:
    b = load('fsc_%s_base.csv' % m)
    if not b:
        continue
    keys = sorted(b)
    sp = sum(b[k][0] for k in keys if b[k][0] is not None)
    sg = sum(b[k][1] for k in keys)
    ans = [k for k in keys if b[k][0] not in (None, 0)]
    sp2 = sum(b[k][0] for k in ans); sg2 = sum(b[k][1] for k in ans)
    tab.append(dict(model=m, n=len(keys), w=100.0 * len(ans) / len(keys),
                    rho_all=(sp - sg) / sg * 100 if sg else None,
                    rho_ans=(sp2 - sg2) / sg2 * 100 if sg2 else None))
print('%-28s %5s %7s %10s %10s' % ('配置', 'n', '已答%', 'ρ_A(全部)', 'ρ_B(已答)'))
for t in sorted(tab, key=lambda x: abs(x['rho_all'] or 0)):
    print('%-28s %5d %7.1f %10.2f %10.2f' % (t['model'], t['n'], t['w'], t['rho_all'], t['rho_ans']))


def spearman(a, b):
    def rk(x):
        idx = sorted(range(len(x)), key=lambda i: x[i])
        r = [0.0] * len(x)
        for pos, i in enumerate(idx):
            r[i] = pos + 1
        return r
    ra, rb = rk(a), rk(b)
    n = len(a); ma = sum(ra) / n; mb = sum(rb) / n
    num = sum((ra[i] - ma) * (rb[i] - mb) for i in range(n))
    da = sum((x - ma) ** 2 for x in ra) ** .5; db = sum((x - mb) ** 2 for x in rb) ** .5
    return num / (da * db) if da and db else float('nan')


if len(tab) >= 3:
    sp = spearman([abs(t['rho_all']) for t in tab], [abs(t['rho_ans']) for t in tab])
    pairs = list(itertools.combinations(tab, 2))
    inv = sum(1 for x, y in pairs
              if (x['rho_all'] - y['rho_all']) * (x['rho_ans'] - y['rho_ans']) < 0)
    ra = sorted(tab, key=lambda x: abs(x['rho_all']))[0]
    rb = sorted(tab, key=lambda x: abs(x['rho_ans']))[0]
    dmax = max(tab, key=lambda t: abs(t['rho_all'] - t['rho_ans']))
    print()
    print('  top-1：A=%s ｜ B=%s ｜ %s' % (ra['model'], rb['model'],
                                          '变化 ★' if ra['model'] != rb['model'] else '不变'))
    print('  Spearman(A,B) = %.3f；序对反转 %d/%d；单配置最大 |Δρ| = %.1f pp（%s）'
          % (sp, inv, len(pairs), abs(dmax['rho_all'] - dmax['rho_ans']), dmax['model']))
    print('  判定（跑前冻结：top-1 变化 或 Spearman<0.9 ⇒ 口径改变结论）：%s'
          % ('口径改变结论 ★' if (ra['model'] != rb['model'] or sp < 0.9) else '公开基准上口径稳健'))

print()
print('=' * 108)
print('③ 反例诊断：permit 残留最高的配置，看它到底在说什么')
print('=' * 108)
worst = max(gate.items(), key=lambda kv: kv[1]['still'])
m = worst[0]
p = load('fsc_%s_permit.csv' % m, keep_raw=True)
b = load('fsc_%s_base.csv' % m, keep_raw=True)
zs = [k for k in sorted(p) if b.get(k) and b[k][0] == 0 and p[k][0] == 0]
print('%s：base 答 0 且 permit 仍答 0 的 item 共 %d 个；抽 5 个看原文：' % (m, len(zs)))
for k in zs[:5]:
    print('   [%s] permit_raw=%s' % (k, p[k][3][:120].replace('\n', ' ')))
ab = [k for k in sorted(p) if b.get(k) and b[k][0] == 0 and p[k][0] is None]
print('   （对照）同一配置里改为**显式弃答**的 item 数：%d' % len(ab))
for k in ab[:3]:
    print('   [%s] permit_raw=%s' % (k, p[k][3][:120].replace('\n', ' ')))

io.open(RP('analysis', 'work', 'b1_fsc_full.json'), 'w', encoding='utf-8').write(
    json.dumps(dict(gate=gate, table=tab), ensure_ascii=False, indent=1))
print('\nJSON -> b1_fsc_full.json')
