# -*- coding: utf-8 -*-
"""n6_budget_matched.py — #13：**预算匹配跨度**（[external-review] E-2），零新跑。

冻结判据：`n6_criteria_frozen.json`（断言 md5）。
单元与工具：**直接复用** `n5_order_prereg.py`（它自己逐字复制了 `a39_unit_calib_heldout.py` 的构建，
并带复现闸门）⇒ 两份分析建在**同一批单元**上，可比。

用法：python -u n6_budget_matched.py
"""
import hashlib
import io
import itertools
import json
import os
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import n5_order_prereg as N5  # noqa: E402

CRIT = os.path.join(HERE, 'n6_criteria_frozen.json')
OUT = os.path.join(HERE, 'n6_result.json')
EXCLUDED_PREFIX = ('VLM·output contract', 'VLM·prompt family')


def cost_of(name, label):
    """成本代理：**预注册**，见 n6_criteria_frozen.json::cost_proxy_preregistered。"""
    lab = label
    if name.startswith('VLM·pixel budget'):
        try:
            b = float(lab)
        except Exception:
            return None
        return b if b > 0 else 1048576.0
    if name.startswith('VLM·tiling'):
        return 1.0 if lab == 'whole' else float(str(lab)[4:]) ** 2
    if name.startswith('det·'):
        if isinstance(lab, tuple) and len(lab) > 1:
            return float(lab[1]) ** 2
        return 1.0
    if name.startswith('density·'):
        v = lab[-1] if isinstance(lab, tuple) else lab
        try:
            return float(v)
        except Exception:
            return None
    return None


def mae_of(unit, i):
    _s, d = unit['levels'][i]
    ks = unit['keys']
    return sum(abs(d[k][1] - d[k][0]) for k in ks) / len(ks)


def main():
    b = open(CRIT, 'rb').read()
    print('冻结判据 md5 %s（%d B）' % (hashlib.md5(b).hexdigest(), len(b)))
    crit = json.loads(b.decode('utf-8'))
    P = crit['constants_preregistered']['primary']
    S = crit['constants_preregistered']['secondary_sensitivity']
    assert P == {'B_mae': 0.10, 'C_cost': 2.0}, P

    N5.build_units()
    names = sorted(N5.UNITS)
    import numpy as np
    ref, full_rho = {}, {}
    for u in names:
        s, rs = N5.span_of(N5.UNITS[u])
        ref[u] = s
        full_rho[u] = rs
    j37 = json.load(io.open(N5.FROZEN36, encoding='utf-8'))
    for u in names:
        assert abs(ref[u] - j37['per_unit'][u]['span_full']) < 1e-9 * max(1.0, abs(ref[u]))
    print('★ 复现闸门通过（与 n5 同一批单元）')

    keep = [u for u in names if not u.startswith(EXCLUDED_PREFIX)]
    print('参与本检的单元 %d/%d（排除无成本维度的两类：输出契约 / 问法族）'
          % (len(keep), len(names)))

    out = {'units_used': keep, 'excluded': [u for u in names if u not in keep],
           'span_full': {u: ref[u] for u in keep}}
    order_ref = sorted(keep, key=lambda u: ref[u])

    for tag, (B, C) in (('primary_B10_C2', (P['B_mae'], P['C_cost'])),
                        ('secondary_B25_C4', (S['B_mae'], S['C_cost'])),
                        # ★ 两个**单边**变体：**事后（post-hoc）诊断**，用来分辨"是哪一条约束在卡"，
                        #   不是预注册判据（冻结件里没有它们），报告时明确标注。
                        ('exploratory_cost_only_C2', (float('inf'), 2.0)),
                        ('exploratory_mae_only_B10', (0.10, float('inf')))):
        bm, npair, undef = {}, {}, []
        for u in keep:
            unit = N5.UNITS[u]
            n = len(unit['levels'])
            mae = [mae_of(unit, i) for i in range(n)]
            cost = [cost_of(u, unit['levels'][i][0]) for i in range(n)]
            rs = full_rho[u]
            best = None
            cnt = 0
            for i, j in itertools.combinations(range(n), 2):
                if cost[i] is None or cost[j] is None:
                    continue
                me, ce = max(mae[i], mae[j]), max(cost[i], cost[j])
                mi, ci = min(mae[i], mae[j]), min(cost[i], cost[j])
                if mi <= 0 or ci <= 0:
                    continue
                if me / mi <= 1 + B and ce / ci <= C:
                    cnt += 1
                    d = abs(rs[i] - rs[j])
                    best = d if best is None else max(best, d)
            if best is None:
                undef.append(u)
            else:
                bm[u] = best
                npair[u] = cnt
        usable = [u for u in keep if u in bm]
        if usable:
            rho_s = N5.spearman([ref[u] for u in usable], [bm[u] for u in usable])
            o_new = sorted(usable, key=lambda u: bm[u])
            top_ref = max(keep, key=lambda u: ref[u])
            top_new = max(usable, key=lambda u: bm[u])
        else:
            rho_s, o_new, top_ref, top_new = float('nan'), [], None, None
        out[tag] = {'B': B, 'C': C, 'span_bm': bm, 'n_pairs': npair, 'undefined': undef,
                    'spearman': rho_s, 'order_ref': order_ref, 'order_new': o_new,
                    'top_ref': top_ref, 'top_new': top_new,
                    'retention_median': (sorted(bm[u] / ref[u] for u in usable)[len(usable) // 2]
                                         if usable else None)}
        print('\n[%s] B = %.2f ｜ C = %.2f ｜ 可用单元 %d ｜ 不可算 %d'
              % (tag, B, C, len(usable), len(undef)))
        if undef:
            print('   不可算单元：%s' % undef[:6])
        print('   Spearman(全档位排序, 预算匹配排序) = %.4f ｜ 顶端：全档位 %s ／ 预算匹配 %s'
              % (rho_s, (top_ref or '').split(' / ')[0], (top_new or '').split(' / ')[0]))
        print('   保留率（span_BM / span_full）中位 %.3f ｜ 可保留档对数中位 %d'
              % (out[tag]['retention_median'] or float('nan'),
                 sorted(npair.values())[len(npair) // 2] if npair else -1))
        if o_new:
            print('   预算匹配后升序：%s' % ' < '.join(u.split(' / ')[-1] or u for u in o_new[:6]))
        ok = (rho_s == rho_s) and abs(rho_s - 1.0) < 1e-12 and top_ref == top_new
        out[tag]['pass'] = bool(ok)
        print('   ⇒ 判据（排序完全一致且顶端不变）：**%s**' % ('PASS' if ok else 'FAIL'))

    io.open(OUT, 'w', encoding='utf-8').write(json.dumps(out, ensure_ascii=False, indent=1))
    print('\nJSON -> %s' % OUT)


if __name__ == '__main__':
    main()
