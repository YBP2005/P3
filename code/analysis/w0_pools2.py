# -*- coding: utf-8 -*-
"""w0_pools2.py — 按**列名**（不是列序号）重算各域零池/非零池规模。

上一版用 awk 的 $4 取 pred，但 schema 是 `item,gt,pred,parse_ok,raw,latency_s` ⇒ pred 是第 3 列，
于是四个域都印出"零池 0"（实际是 parse_ok 列全非 0）。这类"列序号拍脑袋"的错误必须当场改正，
因为它会直接决定 W1 的每格样本量。
"""
import io
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from a800_conn import connect, sh  # noqa: E402

sys.stdout.reconfigure(encoding='utf-8')
HOST = ('<REDACTED-A800-HOST>', 23, 'root', '<REDACTED-A800-PASSWORD>')
PY = '/usr/local/miniconda3/bin/python'

REMOTE = r'''
import csv, io, glob, os
for ds in ('st_a','st_b','ucf','visdrone','aitod'):
    p = '/root/dense_results/vlm_%s_base_whole.csv' % ds
    if not os.path.exists(p):
        print(ds, 'MISSING'); continue
    with io.open(p, encoding='utf-8-sig') as f:
        rows = list(csv.DictReader(f))
    cols = list(rows[0].keys()) if rows else []
    z = sum(1 for r in rows if str(r.get('pred','')).strip() in ('0','0.0'))
    nz = sum(1 for r in rows if str(r.get('pred','')).strip() not in ('0','0.0'))
    bad = sum(1 for r in rows if str(r.get('pred','')).strip() in ('','None','nan'))
    print('%-9s 列=%s  总=%d  零池=%d  非零=%d  未解析=%d' % (ds, ','.join(cols), len(rows), z, nz, bad))
# GT 覆盖：零池 item 是否都在图像目录里
for ds, d in (('st_a','/root/dense/shanghaitech/images/part_A_test'),
              ('ucf','/root/dense/ucf_qnrf/UCF-QNRF_ECCV18/Test'),
              ('visdrone','/root/aerial/visdrone/images'),
              ('aitod','/root/aerial/aitod/images')):
    have = set()
    for f in os.listdir(d):
        have.add(os.path.splitext(f)[0])
    p = '/root/dense_results/vlm_%s_base_whole.csv' % ds
    with io.open(p, encoding='utf-8-sig') as f:
        rows = list(csv.DictReader(f))
    z = [r['item'] for r in rows if str(r.get('pred','')).strip() in ('0','0.0')]
    nz = [r['item'] for r in rows if str(r.get('pred','')).strip() not in ('0','0.0')]
    print('  %-9s 零池有图 %d/%d   非零有图 %d/%d' % (ds,
          sum(1 for i in z if i in have), len(z), sum(1 for i in nz if i in have), len(nz)))
'''


def main():
    c = connect(HOST)
    sf = c.open_sftp()
    with sf.open('/root/_w0pools2.py', 'w') as f:
        f.write(REMOTE.encode('utf-8'))
    sf.close()
    print(sh(c, '%s /root/_w0pools2.py' % PY, t=300))
    c.close()


if __name__ == '__main__':
    main()
