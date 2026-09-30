# -*- coding: utf-8 -*-
"""E2 配对校验：确认 AWQ 与 BF16 两次运行抽到的是同一批 item，
再做 base 臂逐项配对与 parse_ok/ERR 完整性核对。"""


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
import glob
import os
import statistics as st
import sys

sys.stdout.reconfigure(encoding='utf-8')

D_A = RP('analysis', 'e2_5090')
D_B = RP('analysis', 'e2_h20')


def load(path):
    with open(path, encoding='utf-8-sig') as f:
        return list(csv.DictReader(f))


def find(d, tag, ds, arm):
    g = [p for p in glob.glob(os.path.join(d, '*_%s_%s.csv' % (ds, arm))) if tag in os.path.basename(p)]
    return g[0] if g else None


def num(v):
    try:
        return float(str(v).strip())
    except Exception:
        return None


print('=== 1) 四臂 item 集合一致性（AWQ vs BF16，同数据集）===')
pair_ok = True
for ds in ('st_a', 'ucf'):
    for arm in ('base', 'permit', 'bestA', 'channel'):
        a, b = find(D_A, 'awq', ds, arm), find(D_B, 'bf16', ds, arm)
        ia = {r['item'] for r in load(a)}
        ib = {r['item'] for r in load(b)}
        same = ia == ib
        pair_ok &= same
        print('  %-5s %-8s |AWQ|=%d |BF16|=%d  %s'
              % (ds, arm, len(ia), len(ib), '同一批 item ✓' if same else '✗ 不同: 差 %s' % (ia ^ ib)))
print('  => 配对成立' if pair_ok else '  => 配对不成立，比较无效')

print()
print('=== 2) parse_ok / ERR 完整性 ===')
for tag, d in (('AWQ', D_A), ('BF16', D_B)):
    bad = []
    for p in sorted(glob.glob(os.path.join(d, '*.csv'))):
        for r in load(p):
            if str(r.get('parse_ok', '1')).strip() not in ('1', '1.0'):
                bad.append((os.path.basename(p), r['item'], r.get('raw', '')[:60]))
            if 'ERR' in (r.get('raw') or '').upper():
                bad.append((os.path.basename(p), r['item'], 'ERR'))
    print('  %-5s 解析失败/ERR 行：%d %s' % (tag, len(bad), bad[:3]))

print()
print('=== 3) base 臂逐项配对（同一批 40 项）===')
for ds in ('st_a', 'ucf'):
    A = {r['item']: r for r in load(find(D_A, 'awq', ds, 'base'))}
    B = {r['item']: r for r in load(find(D_B, 'bf16', ds, 'base'))}
    items = [i for i in A if i in B]
    both0 = a0b0 = aw0_bfnz = awnz_bf0 = 0
    nz_info = []
    for i in items:
        pa, pb = num(A[i]['pred']), num(B[i]['pred'])
        g = num(A[i]['gt'])
        if pa == 0 and pb == 0:
            both0 += 1
        elif pa == 0 and pb != 0:
            aw0_bfnz += 1
            nz_info.append((i, g, pb, pb / g if g else None))
        elif pa != 0 and pb == 0:
            awnz_bf0 += 1
    print('  %-5s n=%d  两者都=0: %d  AWQ=0 而 BF16≠0: %d  AWQ≠0 而 BF16=0: %d'
          % (ds, len(items), both0, aw0_bfnz, awnz_bf0))
    if nz_info:
        rs = [x[3] for x in nz_info if x[3] is not None]
        print('        BF16 给出非零的 %d 项：gt 中位 %.1f，pred/gt 中位 %.4f，范围 %s'
              % (len(nz_info), st.median([x[1] for x in nz_info]), st.median(rs),
                 '%.4f~%.4f' % (min(rs), max(rs))))
        for x in nz_info[:8]:
            print('          %-10s gt=%-6.0f BF16 pred=%-8.0f pred/gt=%.4f' % (x[0], x[1], x[2], x[3]))

print()
print('=== 4) permit/channel 的弃答形态（确认是显式弃答而非漏答）===')
for tag, d in (('AWQ', D_A), ('BF16', D_B)):
    for ds in ('st_a', 'ucf'):
        for arm in ('permit', 'channel'):
            p = find(d, tag, ds, arm)
            vals = {}
            for r in load(p):
                v = (r.get('raw') or '').strip()
                vals[v] = vals.get(v, 0) + 1
            top = sorted(vals.items(), key=lambda x: -x[1])[:3]
            print('  %-5s %-5s %-8s 原样输出分布: %s' % (tag, ds, arm, top))
