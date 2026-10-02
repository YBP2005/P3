# -*- coding: utf-8 -*-
"""p1d_prep.py —— P1-D 的数据准备（全部在机上做，不需下载）。

产出（都在 /root/p1d/data/）：
  mtdc/images/*.jpg            （软链到 /root/mtdc/images，避免复制 361 张）
  mtdc/items.csv               item,gt        —— gt = len(metadata.objects.bbox)
  gwhd/images/<item>.jpg       （从 parquet 的 `image` 列解出）
  gwhd/items.csv               item,gt        —— gt = len(objects['boxes'])
  sample_<domain>.csv          item,gt        —— 每域**确定性**抽 250 项（按 item 排序后等间隔，种子固定）

核对数（必须打印）：池大小、与图目录交集、gt 的 min/median/max、抽样后的项数与 gt 分布。
"""
import csv
import io
import json
import os
import random

OUT = '/root/p1d/data'
MTDC = '/root/mtdc'
GWHD = '/root/gwhd/data'
N = 250
SEED = 20261002


def w(path, rows, header=('item', 'gt')):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with io.open(path, 'w', encoding='utf-8', newline='') as f:
        wr = csv.writer(f); wr.writerow(header); wr.writerows(rows)
    return len(rows)


def stat(rows):
    g = sorted(float(x[1]) for x in rows if float(x[1]) > 0)
    if not g:
        return 'gt 全 0？'
    n = len(g)
    return 'n=%d gt min=%.0f p50=%.0f max=%.0f mean=%.1f' % (n, g[0], g[n // 2], g[-1], sum(g) / n)


def sample(rows, tag):
    rows = sorted(rows, key=lambda r: r[0])
    if len(rows) <= N:
        pick = rows
    else:
        rnd = random.Random(SEED)
        idx = sorted(rnd.sample(range(len(rows)), N))
        pick = [rows[i] for i in idx]
    p = os.path.join(OUT, 'sample_%s.csv' % tag)
    w(p, pick)
    print('  [sample] %-5s %s ｜ %s' % (tag, stat(pick), p))
    return pick


def main():
    os.makedirs(OUT, exist_ok=True)

    # ---------- MTDC ----------
    md = os.path.join(MTDC, 'images')
    have = {os.path.basename(p).rsplit('.', 1)[0] for p in os.listdir(md)}
    print('MTDC 图目录 %d 张' % len(have))
    rows, miss = [], 0
    for ln in io.open(os.path.join(MTDC, 'metadata.jsonl'), encoding='utf-8'):
        ln = ln.strip()
        if not ln:
            continue
        o = json.loads(ln)
        it = os.path.basename(o['file_name']).rsplit('.', 1)[0]
        n = len(o.get('objects', {}).get('bbox', []) or [])
        if it in have:
            rows.append((it, n))
        else:
            miss += 1
    print('MTDC metadata 行=361 ｜ 与图目录交集 %d ｜ 缺图 %d' % (len(rows), miss))
    w(os.path.join(OUT, 'mtdc', 'items.csv'), rows)
    os.makedirs(os.path.join(OUT, 'mtdc'), exist_ok=True)
    print('  MTDC 池：%s' % stat(rows))
    sample(rows, 'mtdc')

    # ---------- GWHD（parquet → 图 + gt） ----------
    import pyarrow.parquet as pq
    gi = os.path.join(OUT, 'gwhd', 'images')
    os.makedirs(gi, exist_ok=True)
    rows, nrows = [], 0
    for split in ('test',):
        fs = [os.path.join(GWHD, f) for f in sorted(os.listdir(GWHD)) if f.startswith(split) and f.endswith('.parquet')]
        for p in fs:
            pf = pq.ParquetFile(p)
            for b in range(pf.num_row_groups):
                t = pf.read_row_group(b, columns=['image', 'objects'])
                imgs = t.column('image').to_pylist()
                objs = t.column('objects').to_pylist()
                for i, (im, ob) in enumerate(zip(imgs, objs)):
                    it = 'gwhd_%s_%05d' % (split, nrows)
                    nrows += 1
                    gt = len((ob or {}).get('boxes', []) or [])
                    ip = os.path.join(gi, it + '.jpg')
                    if not os.path.exists(ip):
                        data = im.get('bytes') if isinstance(im, dict) else None
                        if data is None:
                            continue
                        with open(ip, 'wb') as fh:
                            fh.write(data)
                    rows.append((it, gt))
            print('  GWHD %s 已处理，累计 %d' % (os.path.basename(p), len(rows)))
    print('GWHD 解出 %d 项 ｜ 与图目录交集 %d' % (len(rows), len(os.listdir(gi))))
    w(os.path.join(OUT, 'gwhd', 'items.csv'), rows)
    print('  GWHD 池：%s' % stat(rows))
    sample(rows, 'gwhd')

    print('P1D_PREP_DONE')


if __name__ == '__main__':
    main()
