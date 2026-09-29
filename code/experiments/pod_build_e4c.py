#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""pod_build_e4c.py — BBBC005 契约臂清单（细胞专属提示词，不动 probe_gen.py）
   设计：同一批 1,200 个 F=1 item × 4 个契约臂（base/forbid0/range/choice）
   细胞专属提示词逐字镜像 probe_gen.py 里的人数版本，只把"人数(人群中的每个人头或人体)"换成"细胞个数"。
   通过清单的 prompt 列覆盖 PROMPTS[arm]，同时保留 arm 名以复用 parse() 的分支逻辑。
"""
import csv, io, os, sys

IDX = '/root/bbbc/index.csv'
OUT = '/root/b2/man_E4C.csv'
FOCUS = os.environ.get('E4C_FOCUS', '1')
LIMIT = int(os.environ.get('E4C_LIMIT', '1200') or 1200)

CELL = '图片中的细胞个数'
PROMPTS = {
    'base': '请数出%s，不要遗漏，不要重复，以JSON格式输出：{"count": 数量}，只输出JSON。' % CELL,
    'forbid0': '请数出%s，不要遗漏，不要重复。注意：**不要回答 0**；'
               '如果你认为可能是 0，请给出你最接近的估计值。'
               '以JSON格式输出：{"count": 数量}，只输出JSON。' % CELL,
    'range': '请估计%s的范围。以JSON格式输出：{"low": 下界, "high": 上界}，只输出JSON。' % CELL,
    'choice': '请从以下选项中选择最接近%s的选项：0, 10, 50, 100, 500, 1000。'
              '以JSON格式输出：{"choice": 选项}，只输出JSON。' % CELL,
}
ARMS = ['base', 'forbid0', 'range', 'choice']

seen, items = set(), []
with io.open(IDX, encoding='utf-8-sig', newline='') as f:
    for r in csv.DictReader(f):
        if str(r.get('focus', '')).strip() != FOCUS:
            continue
        it = r['item'].strip()
        if it in seen:
            continue
        seen.add(it)
        items.append((it, r['path'].strip(), int(r['count'])))
items.sort()
if LIMIT:
    items = items[:LIMIT]
print('F=%s 唯一 item %d 个，臂 %s ⇒ 共 %d 个任务'
      % (FOCUS, len(items), ARMS, len(items) * len(ARMS)))

with io.open(OUT, 'w', encoding='utf-8-sig', newline='') as f:
    w = csv.writer(f)
    w.writerow(['exp', 'item', 'domain', 'path', 'gt', 'arm', 'budget', 'nsample', 'temp', 'prompt'])
    for it, p, c in items:
        for arm in ARMS:
            w.writerow(['E4C', it, 'bbbc', p, c, arm, 0, 1, 0.0, PROMPTS[arm]])
print('已写 %s' % OUT)
cs = [c for _, _, c in items]
print('GT 范围 %d-%d，均值 %.1f' % (min(cs), max(cs), sum(cs) / len(cs)))
# 校验：4 臂 × 每 item
assert os.path.getsize(OUT) > 0
print('臂分布校验：')
import collections
cnt = collections.Counter()
with io.open(OUT, encoding='utf-8-sig', newline='') as f:
    for r in csv.DictReader(f):
        cnt[r['arm']] += 1
print('  ', dict(cnt))
print('提示词长度校验：')
for a, t in PROMPTS.items():
    print(f'  {a:<8} {len(t):>3} 字')
