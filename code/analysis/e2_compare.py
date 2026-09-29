# -*- coding: utf-8 -*-
"""E2 汇总：AWQ(M机5090) vs BF16(H20) 的单变量契约实验对照。
只做定量汇总，不做判断；输出用于写 E2 证据记录。"""
import csv
import glob
import os
import statistics as st
import sys

sys.stdout.reconfigure(encoding='utf-8')

D_A = r'<WORKDIR>\PaperB\analysis\e2_5090'   # AWQ
D_B = r'<WORKDIR>\PaperB\analysis\e2_h20'    # BF16
DATASETS = ['st_a', 'ucf']
ARMS = ['base', 'permit', 'bestA', 'channel']

print('=== 列名 ===')
f0 = sorted(glob.glob(os.path.join(D_B, '*.csv')))[0]
with open(f0, encoding='utf-8-sig') as f:
    rd = csv.DictReader(f)
    print(os.path.basename(f0), '->', rd.fieldnames)
    r0 = next(rd)
    for k, v in r0.items():
        print('   %-12s %r' % (k, (v or '')[:120]))


def rows(path):
    with open(path, encoding='utf-8-sig') as f:
        return list(csv.DictReader(f))


def num(v):
    try:
        return float(str(v).strip())
    except Exception:
        return None


def ratio(row):
    p, g = num(row.get('pred')), num(row.get('gt'))
    if p is None or g is None or g == 0:
        return None
    return p / g


def find(d, tag, ds, arm):
    g = glob.glob(os.path.join(d, '*_%s_%s.csv' % (ds, arm)))
    g = [p for p in g if tag in os.path.basename(p)]
    return g[0] if g else None


def summarize(path):
    rs = rows(path)
    preds = [num(r.get('pred')) for r in rs]
    vals = [p for p in preds if p is not None]
    rz = [num(r.get('gt')) for r in rs if num(r.get('pred')) == 0]
    abst, zero, err = 0, 0, 0
    for r in rs:
        p, g = num(r.get('pred')), num(r.get('gt'))
        blob = ' '.join((r.get(k) or '') for k in r if k not in ('pred', 'gt')).lower()
        is_ab = ('abstain' in blob) or ('cannot_judge' in blob)
        if is_ab:
            abst += 1
        if p == 0:
            zero += 1
        if p is None and 'ERR' in (r.get('raw') or '').upper():
            err += 1
    rats = [x for x in (ratio(r) for r in rs) if x is not None]
    return dict(n=len(rs), zero=zero, abst=abst, err=err,
                med=st.median(vals) if vals else None,
                medr=st.median(rats) if rats else None,
                gtr=st.median(rz) if rz else None,
                nz=sum(1 for v in vals if v > 0))


print()
print('=== E2 总表（每格 40 行）===')
hdr = ('精度', '数据集', '臂', 'n', '零数', '显式弃答', 'ERR', 'pred中位', 'pred/gt中位', '零项gt中位')
print('%-6s %-6s %-8s %4s %5s %8s %4s %9s %11s %10s' % hdr)
store = {}
for prec, d, tag in (('AWQ', D_A, 'awq'), ('BF16', D_B, 'bf16')):
    for ds in DATASETS:
        for arm in ARMS:
            p = find(d, tag, ds, arm)
            if not p:
                print('%-6s %-6s %-8s  (缺)' % (prec, ds, arm))
                continue
            s = summarize(p)
            store[(prec, ds, arm)] = s
            print('%-6s %-6s %-8s %4d %5d %8d %4d %9s %11s %10s'
                  % (prec, ds, arm, s['n'], s['zero'], s['abst'], s['err'],
                     ('%.3f' % s['med']) if s['med'] is not None else '-',
                     ('%.3f' % s['medr']) if s['medr'] is not None else '-',
                     ('%.1f' % s['gtr']) if s['gtr'] is not None else '-'))

print()
print('=== E2-C：AWQ vs BF16 的零率/弃答率差（判据 ≤7 pp）===')
for ds in DATASETS:
    for arm in ARMS:
        a, b = store.get(('AWQ', ds, arm)), store.get(('BF16', ds, arm))
        if not a or not b:
            continue
        dz = 100.0 * (b['zero'] - a['zero']) / a['n']
        da = 100.0 * (b['abst'] - a['abst']) / a['n']
        flag = 'OK' if abs(dz) <= 7.0 else '**超**'
        print('  %-6s %-8s 零率 %3d/40 -> %3d/40 (%+6.1f pp) %-6s 弃答 %3d -> %3d (%+6.1f pp)'
              % (ds, arm, a['zero'], b['zero'], dz, flag, a['abst'], b['abst'], da))
