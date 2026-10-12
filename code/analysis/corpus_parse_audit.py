#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""语料解析器审计：dense-VLM 驱动脚本的 parse 是否真的用到了 JSON 里的 count？
对每个 dense_results CSV：
  - 结构分支是否命中（按该驱动的 pattern 原样，从源码 AST 取出）
  - 第一个整数（fallback）与 JSON count 字段是否一致
  - 出货的 pred 与谁一致
  - pred==0 的行：JSON count 是否就是 0

★ 2026-10-12：**去掉作者机绝对路径**。此前本脚本把驱动脚本与结果目录都写成作者机上的
  绝对路径（服务器侧根目录下），第三方拿到放行包后**无从复算**本件承诺的审计。
  现在两处都经 `_repro_root.resolve()` 解析（放行包内为 `code/experiments/06_dense_vlm.py` 与
  `data/derived/dense_results/`），并可用环境变量 `PAPERB_DENSE_VLM_SRC` /
  `PAPERB_DENSE_RESULTS` 覆盖。行为与取数口径**一字未改**：仍是同一个驱动的 `parse` 结构分支、
  同一批 CSV、同一套逐行判定。
"""
import ast
import csv
import glob
import json
import os
import re
import sys
from collections import Counter

try:
    from _repro_root import resolve as RP
except ImportError:                      # 只拷走单个脚本时：就地反推仓库根
    _r = os.environ.get('PAPERB_ROOT') or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    RP = lambda *p: os.path.join(_r, *p)

BS = chr(92)


def _first_file(cands, what):
    for p in cands:
        if os.path.isfile(p):
            return p
    raise SystemExit('找不到 %s；已试：%s' % (what, list(cands)))


def _first_dir(cands, what):
    for p in cands:
        if os.path.isdir(p):
            return p
    raise SystemExit('找不到 %s 目录；已试：%s' % (what, list(cands)))


SRC = os.environ.get('PAPERB_DENSE_VLM_SRC') or _first_file((
    # 作者树 / 放行树两条等价落点（同一文件，md5 实测相同）
    RP('analysis', 'e1_5090', '06_dense_vlm.py'),
    RP('repro_github', 'code', 'experiments', '06_dense_vlm.py'),
), 'dense-VLM 驱动脚本')

RESULTS_DIR = os.environ.get('PAPERB_DENSE_RESULTS') or _first_dir((
    RP('analysis', 'data', 'pod_mirror', 'dense_results'),
    RP('repro_github', 'data', 'derived', 'dense_results'),
), 'dense_results')


def load_pattern():
    src = open(SRC, encoding='utf-8').read()
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.FunctionDef) and node.name == 'parse':
            for sub in ast.walk(node):
                if isinstance(sub, ast.Constant) and isinstance(sub.value, str) and 'count' in sub.value:
                    return sub.value
    raise SystemExit('未找到 06 的 parse pattern')


PAT = load_pattern()
print('06 parse pattern =', repr(PAT))
print('语料实际输出形态 {"count": 120} 是否命中结构分支：',
      '命中' if re.search(PAT, '{"count": 120}', re.I) else '不命中（只能走 fallback）')
print()


def json_count(raw):
    """尽力取 JSON 对象里的 count/数量 字段；取不到返回 None。"""
    s = raw.strip()
    s = re.sub(r'^```(?:json)?', '', s).strip()
    s = re.sub(r'```$', '', s).strip()
    m = re.search('"' + 'count' + '"' + BS + 's*:' + BS + 's*"?(-?' + BS + 'd+)', s)
    if m:
        return int(m.group(1))
    m = re.search('数量' + BS + 's*[:' + chr(0xff1a) + ']' + BS + 's*"?(-?' + BS + 'd+)', s)
    if m:
        return int(m.group(1))
    try:
        o = json.loads(s)
        if isinstance(o, dict):
            for k in ('count', '数量', '人数'):
                if k in o and str(o[k]).lstrip('-').isdigit():
                    return int(o[k])
    except Exception:
        pass
    return None


def first_int(raw):
    m = re.search('-?' + BS + 'd+', raw.replace(',', ''))
    return int(m.group(0)) if m else None


files = sorted(glob.glob(os.path.join(RESULTS_DIR, '*.csv')))
print('语料结果文件 %d 个' % len(files))
print()
hdr = '%-44s %5s %5s %6s %7s %7s %7s' % ('file', 'rows', 'nodig', 'j≠1st', 'pred≠1st', 'jNone', 'z_json0')
print(hdr)
tot = Counter()
zrows = []
for p in files:
    rows = list(csv.DictReader(open(p, encoding='utf-8-sig')))
    if not rows:
        continue
    n = len(rows)
    nodig = jne = pne = jnone = zj0 = ztot = 0
    for r in rows:
        raw = r.get('raw') or ''
        pred = (r.get('pred') or '').strip()
        fi = first_int(raw)
        jc = json_count(raw)
        if fi is None and jc is None:
            nodig += 1
        if jc is not None and fi is not None and jc != fi:
            jne += 1
        if fi is not None and pred not in ('',) and str(fi) != pred:
            pne += 1
        if jc is None:
            jnone += 1
        if pred in ('0', '0.0'):
            ztot += 1
            if jc == 0:
                zj0 += 1
            if len(zrows) < 12:
                zrows.append((os.path.basename(p), r.get('item'), raw[:150]))
    print('%-44s %5d %5d %6d %7d %7d %6d/%d' % (os.path.basename(p), n, nodig, jne, pne, jnone, zj0, ztot))
    tot['rows'] += n
    tot['nodig'] += nodig
    tot['jne'] += jne
    tot['pne'] += pne
    tot['jnone'] += jnone
    tot['zj0'] += zj0
    tot['ztot'] += ztot
print()
print('合计 rows=%d 无数字行=%d  JSON≠首个整数=%d  pred≠首个整数=%d  JSON不可取=%d  pred为0且JSON也是0=%d/%d'
      % (tot['rows'], tot['nodig'], tot['jne'], tot['pne'], tot['jnone'], tot['zj0'], tot['ztot']))
print()
print('=== pred==0 的样本 raw ===')
for b, it, raw in zrows:
    print('  %-40s %-10s %s' % (b[:40], it, repr(raw)))
