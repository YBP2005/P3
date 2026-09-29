#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""w1_smoke_count.py — 数产物 CSV 里 `parse_ok==1` 的行数（供 w1_run.sh 的 smoke 门用）。

为什么不用 awk：产物 CSV 的 `raw` 列里含逗号、换行与引号（模型原始回复），
按逗号拆列的 awk 会数错；必须用 csv 模块。上一版驱动就是踩了这个（写成 `$5==1`，
而正确列是第 4 列的 parse_ok，且列会被 raw 的内容挤歪）。
用法：python3 w1_smoke_count.py <csv> [csv...]   # 末行输出总可解析数
"""
import csv
import io
import sys


def main():
    total = 0
    for p in sys.argv[1:]:
        try:
            with io.open(p, encoding='utf-8-sig', newline='') as f:
                rows = list(csv.DictReader(f))
        except Exception:
            continue
        n = sum(1 for r in rows if str(r.get('parse_ok', '')).strip() == '1')
        total += n
        print('  %s: %d/%d 可解析' % (p.split('/')[-1], n, len(rows)))
    print(total)
    return 0


if __name__ == '__main__':
    sys.exit(main())
