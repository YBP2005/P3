#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""p3_A_prep.py —— 实验 A 的准备工作（**不调用模型**）：两个新域各建一份统一接口的数据。

统一接口（两域一致，便于同一支探针跑）：
    /root/A_data/<domain>/images/<item>.jpg   （mtdc 用符号链接，gwhd 落实体）
    /root/A_data/<domain>/gt.csv              # item,gt
    /root/A_data/<domain>/items.json          # 固定种子、按 GT 分层的 200 项（含 gt）

来源与 GT 口径（与 A_criteria_frozen.json 一致）：
  · mtdc : /root/mtdc/images/*  + /root/mtdc/annotations.json（COCO，逐图框数；**零框图也保留**，计 0）
  · gwhd : /root/gwhd/data/*.parquet 的 image 列 + objects.boxes 条数（HF 作者镜像）
"""
import argparse
import csv
import glob
import io
import json
import os
import random
import sys

from PIL import Image

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
BASE = '/root/A_data'
N_ITEMS = 200
SEED = 20260928


def prep_mtdc():
    d = os.path.join(BASE, 'mtdc')
    imd = os.path.join(d, 'images')
    os.makedirs(imd, exist_ok=True)
    ann = json.load(io.open('/root/mtdc/annotations.json', encoding='utf-8'))
    byid = {im['id']: im['file_name'] for im in ann['images']}
    cnt = {v: 0 for v in byid.values()}                    # ★ 零框图保留为 0
    for a in ann['annotations']:
        fn = byid.get(a['image_id'])
        if fn:
            cnt[fn] = cnt.get(fn, 0) + 1
    src = '/root/mtdc/images'
    pairs, nzero = [], 0
    for fn, g in sorted(cnt.items()):
        p = os.path.join(src, fn)
        if not os.path.exists(p):
            cand = glob.glob(os.path.join(src, os.path.splitext(fn)[0] + '.*'))
            if not cand:
                continue
            p = cand[0]
        item = os.path.splitext(os.path.basename(p))[0]
        link = os.path.join(imd, item + '.jpg')
        if not os.path.exists(link):
            os.symlink(p, link)
        pairs.append((item, g, p))
        nzero += (g == 0)
    print('  mtdc：图 %d 张，其中零实例 %d 张' % (len(pairs), nzero))
    return d, pairs


def prep_gwhd():
    """两遍：① 只读 objects 数框（不碰图像）② 只把**抽样到的** 200 张落盘。

    ★ 不整解 6,512 张 —— 既省时省盘，也避免把 1.5 GB 白写一遍。
    """
    import pyarrow.parquet as pq
    d = os.path.join(BASE, 'gwhd')
    imd = os.path.join(d, 'images')
    os.makedirs(imd, exist_ok=True)
    files = sorted(glob.glob('/root/gwhd/data/*.parquet'))
    counts = []                                            # (item, gt, (file, row))
    for f in files:
        t = pq.read_table(f, columns=['objects'])
        tag = os.path.basename(f).split('-')[0]
        for i in range(t.num_rows):
            objs = t.column('objects')[i].as_py() or {}
            counts.append(('%s_%05d' % (tag, i), len(objs.get('boxes') or []), (f, i)))
    print('  gwhd：图 %d 张（GT 已数，图像未解）' % len(counts))
    return d, counts


def extract_gwhd(d, pick):
    """只把抽样到的图落盘。pick 的元素是 (item, gt, (file, row))。"""
    import pyarrow.parquet as pq
    imd = os.path.join(d, 'images')
    by_file = {}
    for it, _g, ref in pick:
        f, i = ref
        by_file.setdefault(f, []).append((it, i))
    for f, rows in by_file.items():
        t = pq.read_table(f, columns=['image'])
        for it, i in rows:
            p = os.path.join(imd, it + '.jpg')
            if os.path.exists(p):
                continue
            cell = t.column('image')[i].as_py() or {}
            b = cell.get('bytes') if isinstance(cell, dict) else cell
            if b is None:
                continue
            if isinstance(b, bytes):
                io.open(p, 'wb').write(b)
            else:
                Image.open(io.BytesIO(b)).convert('RGB').save(p, 'JPEG', quality=95)


def stratified(pairs, n, seed):
    """按 GT 排序后等间隔抽 n 个（固定种子 + GT 分层，与 §5.13 的 sample_test_ids 同法）。"""
    pairs = sorted(pairs, key=lambda x: (x[1], x[0]))
    if len(pairs) <= n:
        return pairs
    rnd = random.Random(seed)
    step = len(pairs) / float(n)
    out, seen = [], set()
    for i in range(n):
        j = min(len(pairs) - 1, int((i + rnd.random()) * step))
        if pairs[j][0] not in seen:
            seen.add(pairs[j][0])
            out.append(pairs[j])
    k = 0
    while len(out) < n and k < len(pairs):                 # 去重后补足
        if pairs[k][0] not in seen:
            seen.add(pairs[k][0])
            out.append(pairs[k])
        k += 1
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--domain', required=True, choices=('mtdc', 'gwhd'))
    ap.add_argument('--n', type=int, default=N_ITEMS)
    A = ap.parse_args()
    d, pairs = prep_mtdc() if A.domain == 'mtdc' else prep_gwhd()
    if not pairs:
        print('!! 没有候选')
        return
    gts = sorted(g for _, g, _ in pairs)
    print('  候选 %d；GT 范围 %d .. %d，中位 %d' % (len(pairs), gts[0], gts[-1], gts[len(gts) // 2]))
    pick = stratified(pairs, A.n, SEED)
    if A.domain == 'gwhd':
        extract_gwhd(d, pick)
        pairs = [(it, g, (ref[0], ref[1])) for it, g, ref in pairs]
    with io.open(os.path.join(d, 'gt.csv'), 'w', encoding='utf-8', newline='') as f:
        w = csv.writer(f)
        w.writerow(['item', 'gt'])
        for it, g, _ in sorted(pairs):
            w.writerow([it, g])
    json.dump([{'item': it, 'gt': g} for it, g, _ in pick],
              io.open(os.path.join(d, 'items.json'), 'w', encoding='utf-8'), ensure_ascii=False)
    pg = [g for _, g, _ in pick]
    print('  抽样 %d 项（GT %d .. %d，中位 %d；零实例 %d 张）'
          % (len(pick), min(pg), max(pg), sorted(pg)[len(pg) // 2], sum(1 for g in pg if g == 0)))
    print('  接口目录 %s 下 %d 张' % (os.path.join(d, 'images'), len(os.listdir(os.path.join(d, 'images')))))
    print('A_PREP_%s_DONE' % A.domain.upper())


if __name__ == '__main__':
    main()
