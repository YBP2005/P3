# -*- coding: utf-8 -*-
"""p1d_check.py —— P1-D 的**纯 CPU 核对**（不起服务、不跑任何调用）。

做四件事并逐条打印：
  ① GWHD 转换的小样本验证：抽 8 张解出的 jpg，用 PIL 打开确认可读、尺寸合理，并与 parquet 里同一 index 的
     len(objects['boxes']) **逐项对照**（确认 gt 是"数出来"的，不是抄的）；
  ② MTDC 抽样：与图目录交集、gt 分布、gt=0 的项数；
  ③ 两个"未用域"（VisDrone / AI-TOD）：(item,gt) 与图目录交集、gt 分布；
  ④ 判据件/探针/编排/两个 sample 的 md5。
"""
import csv
import glob
import hashlib
import io
import os

D = '/root/p1d'


def md5f(p):
    h = hashlib.md5()
    with io.open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def rows(p):
    return list(csv.DictReader(io.open(p, encoding='utf-8-sig', newline='')))


def dist(rs, col='gt'):
    g = [float(r[col]) for r in rs if r.get(col) not in (None, '')]
    z = sum(1 for x in g if x == 0)
    pos = sorted(x for x in g if x > 0)
    if not pos:
        return 'n=%d gt>0=0 零值=%d' % (len(g), z)
    return ('n=%d ｜ gt>0=%d ｜ 零值=%d ｜ min=%.0f p50=%.0f max=%.0f mean=%.1f'
            % (len(g), len(pos), z, pos[0], pos[len(pos) // 2], pos[-1], sum(pos) / len(pos)))


def names(d):
    return {os.path.basename(p).rsplit('.', 1)[0] for p in glob.glob(os.path.join(d, '*'))}


print('===== ① GWHD 小样本验证 =====')
gi = os.path.join(D, 'data', 'gwhd', 'images')
items = rows(os.path.join(D, 'data', 'gwhd', 'items.csv'))
print('  items.csv 行数 = %d ｜ 图目录 = %d ｜ 交集 = %d'
      % (len(items), len(names(gi)), len({r['item'] for r in items} & names(gi))))
import pyarrow.parquet as pq  # noqa: E402
from PIL import Image        # noqa: E402
pf = pq.ParquetFile('/root/gwhd/data/test-00000-of-00001.parquet')
objs = []
for b in range(pf.num_row_groups):          # ★ 必须遍历**全部** row group：单个 row group 远小于 1381 行
    objs += pf.read_row_group(b, columns=['objects']).column('objects').to_pylist()
print('  parquet 全表 objects 行数 = %d（应 1381）' % len(objs))
pick = [0, 5, 40, 200, 500, 900, 1200, 1380]
byitem = {r['item']: r['gt'] for r in items}
for i in pick:
    it = 'gwhd_test_%05d' % i
    p = os.path.join(gi, it + '.jpg')
    with Image.open(p) as im:
        wh = im.size
    gt_parquet = len((objs[i] or {}).get('boxes', []) or [])
    gt_csv = byitem.get(it)
    print('  %-18s jpg=%s ｜ parquet boxes=%d ｜ items.csv gt=%s ｜ %s'
          % (it, wh, gt_parquet, gt_csv, 'OK' if str(gt_parquet) == str(gt_csv) else '**不符**'))

print('===== ② MTDC =====')
mt = rows(os.path.join(D, 'data', 'mtdc', 'items.csv'))
smt = rows(os.path.join(D, 'data', 'sample_mtdc.csv'))
print('  池：%s' % dist(mt))
print('  抽样 250 项：%s ｜ 与图目录交集 %d'
      % (dist(smt), len({r['item'] for r in smt} & names('/root/mtdc/images'))))

print('===== ③ 未用域（VisDrone / AI-TOD）=====')
for tag, gt, img in (('visdrone', '/root/aerial/gt_visdrone.csv', '/root/aerial/visdrone/images'),
                     ('aitod', '/root/aerial/gt_aitod.csv', '/root/aerial/aitod')):
    rs = rows(gt)
    im = names(img)
    print('  %-9s (item,gt) 行=%d ｜ 图目录=%d ｜ 交集=%d ｜ %s'
          % (tag, len(rs), len(im), len({r['item'] for r in rs} & im), dist(rs)))

print('===== ④ md5 =====')
for p in (os.path.join(D, '_p1d_criteria_frozen.json'), os.path.join(D, 'p1d_probe.py'),
          os.path.join(D, 'p1d_run.sh'), os.path.join(D, 'p1d_prep.py'),
          os.path.join(D, 'data', 'sample_mtdc.csv'), os.path.join(D, 'data', 'sample_gwhd.csv')):
    print('  %s  %s' % (md5f(p), p))
print('P1D_CHECK_DONE')
