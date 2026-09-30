# -*- coding: utf-8 -*-
"""B1 分析：**公开基准 FSC-147** 上的"契约门控 + 口径→榜单"。

输入：`analysis/fsc_a800/fsc_<model>_{base,permit}.csv`（由 `19g_probe_fsc.py` 产生，
提示词/解析器/传输格式**逐字复用 19e**）。

三件事：
  ① 契约门控（跨配置）：base 答 0 的 item，在 permit 下仍答 0 的比例 + Wilson 95% CI；
  ② 两口径指标：A「弃权当 0」与 B「只算已答」下的 signed ρ；
  ③ **口径→榜单**：按 |ρ| 给配置排名，比较两个排名（Spearman、序对反转、top-1 是否变化）。
判据（与 §5.12 同一口径，跑前写死）：
  · "口径改变结论" = top-1 变化 **或** Spearman < 0.9；
  · 契约门控"跨配置成立" = 每个配置 permit 残留零 ≤5%。
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
          'llava-onevision-qwen2-7b-ov', 'Qwen3-VL-32B-Instruct']


def wilson(k, n, z=1.959963985):
    if n == 0:
        return (None, None)
    p = k / float(n)
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def load(fn):
    p = os.path.join(RP('analysis', 'fsc_a800'), fn)
    if not os.path.exists(p):
        return None
    out = {}
    for r in csv.DictReader(io.open(p, encoding='utf-8-sig')):
        raw = str(r.get('raw') or '').lower()
        pv = str(r.get('pred') or '').strip()
        try:
            gt = float(r['gt'])
        except (KeyError, TypeError, ValueError):
            continue
        if any(k in raw for k in ABSTAIN):
            v = None
        else:
            try:
                v = float(pv)
            except ValueError:
                v = None
        out[r['item']] = (v, gt)
    return out


def spearman(a, b):
    def rk(x):
        idx = sorted(range(len(x)), key=lambda i: x[i])
        r = [0.0] * len(x)
        for pos, i in enumerate(idx):
            r[i] = pos + 1
        return r
    ra, rb = rk(a), rk(b)
    n = len(a)
    ma, mb = sum(ra) / n, sum(rb) / n
    num = sum((ra[i] - ma) * (rb[i] - mb) for i in range(n))
    da = sum((x - ma) ** 2 for x in ra) ** .5
    db = sum((x - mb) ** 2 for x in rb) ** .5
    return num / (da * db) if da and db else float('nan')


print('=' * 104)
print('① 契约门控（FSC-147，公开基准；同一批 300 张测试图）')
print('=' * 104)
print('%-28s %6s %8s %10s %14s' % ('配置', 'n', 'base 答0', 'permit 仍0', 'Wilson 95% CI'))
rows = {}
for m in MODELS:
    b, p = load('fsc_%s_base.csv' % m), load('fsc_%s_permit.csv' % m)
    if not b or not p:
        print('%-28s   缺数据' % m)
        continue
    keys = sorted(set(b) & set(p))
    z = [k for k in keys if b[k][0] == 0]
    still = sum(1 for k in z if p[k][0] == 0)
    lo, hi = wilson(still, len(z)) if z else (None, None)
    rows[m] = dict(n=len(keys), n_zero=len(z), still=still,
                   ratio=(still / len(z)) if z else None, ci=[lo, hi])
    print('%-28s %6d %8d %10s %14s'
          % (m, len(keys), len(z),
             ('%d (%.1f%%)' % (still, 100 * still / len(z))) if z else '—',
             ('[%.3f, %.3f]' % (lo, hi)) if z else '—'))

print()
print('=' * 104)
print('② 两口径指标 + ③ 口径→榜单')
print('=' * 104)
tab = []
for m, r in rows.items():
    b = load('fsc_%s_base.csv' % m)
    keys = sorted(b)
    sp = sum(b[k][0] for k in keys if b[k][0] is not None)
    sg = sum(b[k][1] for k in keys)
    rho_all = (sp - sg) / sg * 100 if sg else None
    ans = [k for k in keys if b[k][0] not in (None, 0)]
    sp2 = sum(b[k][0] for k in ans)
    sg2 = sum(b[k][1] for k in ans)
    rho_ans = (sp2 - sg2) / sg2 * 100 if sg2 else None
    mae_all = sum(abs(b[k][0] - b[k][1]) for k in keys if b[k][0] is not None) / len(keys)
    mae_ans = sum(abs(b[k][0] - b[k][1]) for k in ans) / len(ans) if ans else None
    tab.append(dict(model=m, n=len(keys), n_ans=len(ans),
                    w=100.0 * len(ans) / len(keys),
                    rho_all=rho_all, rho_ans=rho_ans,
                    mae_all=mae_all, mae_ans=mae_ans))
print('%-28s %5s %7s %10s %10s %10s %10s'
      % ('配置', 'n', '已答%', 'MAE(A)', 'MAE(B)', 'ρ_A', 'ρ_B'))
for t in sorted(tab, key=lambda x: abs(x['rho_all'])):
    f = lambda v: ('%.2f' % v) if isinstance(v, float) else '—'
    print('%-28s %5d %7.1f %10s %10s %10s %10s'
          % (t['model'], t['n'], t['w'], f(t['mae_all']), f(t['mae_ans']),
             f(t['rho_all']), f(t['rho_ans'])))

if len(tab) >= 3:
    ra = sorted(tab, key=lambda x: abs(x['rho_all']))
    rb = sorted(tab, key=lambda x: abs(x['rho_ans']))
    sp = spearman([abs(t['rho_all']) for t in tab], [abs(t['rho_ans']) for t in tab])
    pairs = list(itertools.combinations(tab, 2))
    inv = sum(1 for x, y in pairs
              if (x['rho_all'] - y['rho_all']) * (x['rho_ans'] - y['rho_ans']) < 0)
    dmax = max(tab, key=lambda t: abs(t['rho_all'] - t['rho_ans']))
    print()
    print('  排名：口径 A 首位 %s ｜口径 B 首位 %s ｜top-1 %s'
          % (ra[0]['model'], rb[0]['model'], '变化 ★' if ra[0]['model'] != rb[0]['model'] else '不变'))
    print('  Spearman(A,B) = %.3f；序对反转 %d/%d；单配置最大 |Δρ| = %.1f pp（%s）'
          % (sp, inv, len(pairs), abs(dmax['rho_all'] - dmax['rho_ans']), dmax['model']))
    verdict = (ra[0]['model'] != rb[0]['model']) or (sp < 0.9)
    print('  判定（跑前冻结）：%s' % ('口径改变结论 ★' if verdict else '公开基准上口径稳健'))
else:
    print('（配置数不足 3，不做排名比较）')

io.open(RP('analysis', 'work', 'b1_fsc_result.json'), 'w', encoding='utf-8').write(
    json.dumps(dict(gate=rows, table=tab), ensure_ascii=False, indent=1))
print('\nJSON -> b1_fsc_result.json')
