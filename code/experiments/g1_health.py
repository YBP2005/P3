#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""g1_health.py — 产物健康检查 + 即时读出（弃权率 vs 绝对像素预算）
用法: python g1_health.py /root/res_ctrl/ivl [more dirs...]
污染行（HTTP 错误页/HTML）会被报告；污染率高的文件打标 QUARANTINE。
"""
import csv, glob, os, sys, collections
for d in sys.argv[1:]:
    print('=== %s' % d)
    tot = 0
    for f in sorted(glob.glob(os.path.join(d, '*.csv'))):
        rows = list(csv.DictReader(open(f, encoding='utf-8-sig')))
        if not rows:
            print('  %-28s 空' % os.path.basename(f)); continue
        bad = sum(1 for r in rows if r.get('http_err') == '1')
        ok = [r for r in rows if r.get('parse_ok') == '1' and r.get('http_err') == '0']
        tot += len(ok)
        flag = 'QUARANTINE' if bad > max(5, 0.02 * len(rows)) else 'ok'
        print('  %-28s 行=%5d 有效=%5d 污染=%3d  %s' % (os.path.basename(f), len(rows), len(ok), bad, flag))
        # 弃权率 vs 预算
        by = collections.defaultdict(lambda: [0, 0, 0.0, 0])
        for r in ok:
            b = r['budget']
            by[b][0] += 1
            by[b][1] += int(r['abstain'])
            try:
                by[b][2] += float(r['pred']) / max(1.0, float(r['gt']))
                by[b][3] += 1
            except Exception:
                pass
        for b in sorted(by, key=lambda x: int(x)):
            n, ab, s, c = by[b]
            print('      budget=%-8s n=%-5d 弃权=%5.1f%%  平均 pred/gt=%5.2f' % (
                b, n, 100.0 * ab / max(1, n), s / max(1, c)))
    print('  合计有效行=%d' % tot)
