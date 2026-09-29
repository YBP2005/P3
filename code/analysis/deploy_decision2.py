# -*- coding: utf-8 -*-
"""方案 #2 第 1 步（**修正版**）：D1/D3 **扫阈值** + D2 **同数据集内**选择。

修正了什么（第一版的错）：
  ① D1/D3 只用了 θ=0.70 ⇒ 两种口径**都判 fail**，阈值落在分辨率之外，测不出任何东西。
     现在扫 θ ∈ {0.30,0.50,0.70} × 容差 {10%,20%,50%}，报**每个组合下的翻转数**。
  ② D2 第一版把**不同数据集**的单元混在一起比"交付误差"，那不是同类比较。
     现在**在每个数据集内部**比较配置，并给出"按口径 A / B 各选出的最优配置"及对称差。
口径：A「弃权当错」（分母=全部）；B「弃权待复核」（分母=已答，弃权图移出交付集）。
判据（跑前写死）：**存在任一 (θ,tol) 组合下翻转 ≥2 个同类单元**，或**任一数据集内最优配置不同** ⇒ 有后果。
"""
import csv
import io
import json
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')
FSC = r'<WORKDIR>\PaperB\analysis\fsc_a800'
MER = r'<WORKDIR>\PaperB\analysis\e2xt_a800\merged'
E2 = r'<WORKDIR>\PaperB\analysis\e2_newh20'
ABSTAIN = ('abstain', 'cannot_judge', 'no_people')
THETAS = (0.30, 0.50, 0.70)
TOLS = (0.10, 0.20, 0.50)


def load_csv(p):
    out = {}
    for r in csv.DictReader(io.open(p, encoding='utf-8-sig')):
        raw = str(r.get('raw') or '').lower()
        try:
            gt = float(r['gt'])
        except (KeyError, TypeError, ValueError):
            continue
        if any(k in raw for k in ABSTAIN):
            v = None
        else:
            try:
                v = float(str(r['pred']).strip())
            except ValueError:
                v = None
        out[r['item']] = (v, gt)
    return out


def rates(items, tol):
    n = len(items)
    ans = [(v, g) for v, g in items if v is not None]
    hit_all = sum(1 for v, g in items if v is not None and g > 0 and abs(v - g) / g <= tol)
    hit_ans = sum(1 for v, g in ans if g > 0 and abs(v - g) / g <= tol)
    errB = (sum(min(abs(v - g) / g, 1.0) for v, g in ans) / len(ans)) if ans else None
    # ★ 口径 A 的度量：**全部 item 计错**，弃权/答 0 记为满误差 1.0（这正是"弃权当错"的字面含义）
    errA = (sum(min(abs(v - g) / g, 1.0) for v, g in ans) + (n - len(ans))) / n if n else None
    return dict(n=n, n_ans=len(ans), hA=hit_all / n if n else None,
                hB=hit_ans / len(ans) if ans else None, errA=errA, errB=errB,
                covered=len(ans) / n if n else None)


# 收集：{数据集: {配置: items}}
def collect():
    data = {}
    for f in sorted(os.listdir(FSC)):
        if f.startswith('fsc_') and f.endswith('_base.csv'):
            data.setdefault('FSC-147', {})[f[4:-9]] = list(load_csv(os.path.join(FSC, f)).values())
    seen = set()
    for d in (MER, E2):
        for f in sorted(os.listdir(d)):
            if not (f.startswith('e1_') and f.endswith('_base.csv')):
                continue
            body = f[3:-9]
            if body in seen:
                continue
            seen.add(body)
            p = os.path.join(d, f)
            if not os.path.exists(p):
                continue
            u = load_csv(p)
            if len(u) < 40:
                continue
            for ds in ('st_a', 'ucf', 'visdrone', 'aitod'):
                if body.endswith('_' + ds):
                    data.setdefault(ds, {})[body[:-len(ds) - 1]] = list(u.values())
    return data


data = collect()
print('数据集：%s' % '、'.join('%s(%d 配置)' % (k, len(v)) for k, v in data.items()))

print()
print('=' * 104)
print('D1/D3：可交付性判定翻转数（口径 A=弃权当错；B=弃权待复核）')
print('=' * 104)
print('%-10s %-7s %8s %10s %12s %s' % ('数据集', '容差', 'θ', '单元数', '翻转数', '翻转单元'))
flip_total = {}
for ds, cfgs in data.items():
    for tol in TOLS:
        for th in THETAS:
            flips = []
            for c, items in cfgs.items():
                m = rates(items, tol)
                if not m['hA'] or not m['hB']:
                    continue
                if (m['hA'] >= th) != (m['hB'] >= th):
                    flips.append('%s(hA=%.2f→%s, hB=%.2f→%s)'
                                 % (c[:18], m['hA'], 'pass' if m['hA'] >= th else 'fail',
                                    m['hB'], 'pass' if m['hB'] >= th else 'fail'))
            flip_total['%s|tol%.0f|θ%.1f' % (ds, 100 * tol, th)] = len(flips)
            print('%-10s %-7s %8.2f %10d %12d %s' % (ds, '%.0f%%' % (100 * tol), th,
                                                     len(cfgs), len(flips),
                                                     '；'.join(flips[:2])))

print()
print('=' * 104)
print('D2：**同一数据集内**按口径选出的最优配置（交付误差最小，弃权图移出交付集）')
print('=' * 104)
sym_all = []
for ds, cfgs in data.items():
    best = {}
    scored_by = {}
    for conv in ('A', 'B'):
        scored = []
        for c, items in cfgs.items():
            m = rates(items, 0.20)
            key = 'errA' if conv == 'A' else 'errB'   # ★ 各口径用**各自**的度量
            if m[key] is None:
                continue
            scored.append((c, m[key], m['covered']))
        scored.sort(key=lambda x: x[1])
        scored_by[conv] = scored
        best[conv] = [s[0] for s in scored[:3]]
    sym = set(best['A']) ^ set(best['B'])
    sym_all.append(bool(sym))
    print('  %-10s A（全 item 计错）前三：%s' % (ds, '、'.join(best['A'])))
    print('  %-10s B（仅已答）   前三：%s  对称差 %s' % ('', '、'.join(best['B']),
                                                       '非空 ★' if sym else '空'))
    if sym:
        onlyA = [c for c in best['A'] if c not in best['B']]
        onlyB = [c for c in best['B'] if c not in best['A']]
        covA = {c: round(100 * rates(cfgs[c], 0.20)['covered'], 1) for c in onlyA}
        covB = {c: round(100 * rates(cfgs[c], 0.20)['covered'], 1) for c in onlyB}
        print('            只在 A 入选：%s（已答率 %s）' % (onlyA, covA))
        print('            只在 B 入选：%s（已答率 %s）' % (onlyB, covB))

any_flip_ge2 = any(v >= 2 for v in flip_total.values())
verdict = any_flip_ge2 or any(sym_all)
print()
print('=' * 104)
print('判定（跑前冻结）：翻转 ≥2（任一 θ×容差 组合） **或** 任一数据集内最优配置不同 ⇒ 有后果')
print('  最大翻转数（任一组合）：%d' % max(flip_total.values()))
print('  同数据集内最优配置不同的数据集数：%d/%d' % (sum(sym_all), len(sym_all)))
print('  结论：%s' % ('**有后果 ★**' if verdict else '**无后果**（如实报 + 给机制）'))
print('=' * 104)

io.open(r'<WORKDIR>\PaperB\analysis\work\deploy_decision2_result.json', 'w', encoding='utf-8').write(
    json.dumps(dict(flip_by_cell=flip_total, max_flip=max(flip_total.values()),
                    selection_diff_units=sum(sym_all), n_units=len(sym_all),
                    verdict=bool(verdict)), ensure_ascii=False, indent=1))
print('JSON -> deploy_decision2_result.json')
