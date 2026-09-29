# -*- coding: utf-8 -*-
"""ea2_contrast.py — **真零池（E2 新测）vs 非零池（已冻结）** 的通道对照。

为什么这是盲审 #1 要的那块拼图：gpt6sol 要"**混合真零／非零**图像"上的检验。
论文自己的非零池结果已冻结在 `/root/e1_results_nonzero`（4 构建 × 4 域 × 3 臂，同一支探针）；
E2 新测的是**真零池**（306 张核实图）。两者并列，就能回答："模型是否**有区别地**使用两个出口"——
真零图上用 `no_people`（"确实没有人"），非零图上用 `cannot_judge`（"数不清"）。

命名约定（两侧都用 raw-match 分类，同 `a5_judge.cls()`）：
  真零侧：analysis/ea2_z0/<cn|en>_<build>_s<N>/e1_<model>_<stratum>_<arm>_native.csv
  非零侧：analysis/e1_results_nonzero/e1_<model>_<domain>_<arm>.csv
产物：analysis/work/ea2_contrast_result.json（+ .md5）
"""
import collections
import csv
import glob
import hashlib
import io
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
Z0 = r'<WORKDIR>\PaperB\analysis\ea2_z0'
NZ = r'<WORKDIR>\PaperB\analysis\e1_results_nonzero'
OUT = r'<WORKDIR>\PaperB\analysis\work\ea2_contrast_result.json'
DENSE, AERIAL = ('st_a', 'ucf'), ('visdrone', 'aitod')
ARMS = ('base', 'permit', 'channel')


def cls_of(raw, pred):
    r = (raw or '').lower()
    for k in ('abstain', 'cannot_judge', 'no_people'):
        if k in r:
            return k
    p = (pred or '').strip()
    if p == '':
        return 'unparsed'
    try:
        return 'zero' if float(p) == 0 else 'nonzero'
    except ValueError:
        return 'unparsed'


def pct(d):
    """接受 {item: class} 或 [class, ...]（后者用于**跨服务池化**的观测列表）。"""
    vals = list(d.values()) if isinstance(d, dict) else list(d)
    c = collections.Counter(vals)
    n = len(vals) or 1
    return {k: round(100.0 * c.get(k, 0) / n, 1) for k in
            ('zero', 'nonzero', 'no_people', 'cannot_judge', 'abstain', 'unparsed')}


def read_csv(f):
    d = {}
    for r in csv.DictReader(io.open(f, encoding='utf-8-sig', errors='replace')):
        if '#' in str(r.get('item') or ''):
            continue
        d[r['item']] = cls_of(r.get('raw'), r.get('pred'))
    return d


# ── 真零侧（E2）────────────────────────────────────────────────────────
# ★ 2026-09-24 **修掉一个会静默改口径的 bug**：原来写的是
#     `z0[(model, lang, stratum, arm)].update(read_csv(f))`  —— 键是 item，而**三次服务跑的是同一批 item**，
#   于是 update 让**后一次服务覆盖前一次**：合并结果只剩 153 个观测，等于"**只报了一次服务**"，
#   却被正文说成"三次服务启动"。实测被抓到：gemma-3-12b 三次服务分别为 47.7/48.4/47.7%，
#   池化应为 47.9%，而旧代码报 47.7%（= 最后一次服务）。
#   ⇒ 现在按 (serving, item) **累计**（同一 item 在三次服务里各算一个观测），并在累计前断言
#      三次服务的 item 集**完全一致**（不一致就直接报错，不允许把不同 item 集混在一起算率）。
z0 = collections.defaultdict(list)          # (model, lang, stratum, arm) -> [class, ...]（跨服务的池化观测）
z0_items = collections.defaultdict(list)    # 同上键 -> [itemset_s1, itemset_s2, ...]，用于一致性断言
for f in glob.glob(os.path.join(Z0, '*', '*.csv')):
    dirn = os.path.basename(os.path.dirname(f))
    m = re.match(r'^(cn|en)_(.+)_s(\d)$', dirn)
    if not m:
        continue
    lang, build, srv = m.group(1), m.group(2), int(m.group(3))
    mm = re.match(r'^e1_(.+?)_(z0easy|z0hard)_(base|permit|channel)_.*\.csv$', os.path.basename(f))
    if not mm:
        continue
    model, stratum, arm = mm.group(1), mm.group(2), mm.group(3)
    # 同 (model, lang, 层, 臂) 的多次服务**池化**统计（服务级噪声由 ea2_analyze.py 单独报）
    one = read_csv(f)
    k = (model, lang, stratum, arm)
    z0[k].extend(one.values())
    z0_items[k].append((srv, set(one)))

# 一致性硬校验：同一 (model, lang, 层, 臂) 的各次服务必须跑**同一批 item**，
# 否则"池化"就是把不同总体混在一起算率（这正是评审最容易质疑的一类口径问题）。
for k, lst in z0_items.items():
    sets = [s for _, s in sorted(lst)]
    assert len(sets) >= 1
    if len(sets) > 1:
        assert all(s == sets[0] for s in sets[1:]), 'item 集不一致，不能池化：%s' % (k,)

# ── 非零侧（已冻结）─────────────────────────────────────────────────────
nz = collections.defaultdict(dict)
for f in glob.glob(os.path.join(NZ, '*.csv')):
    mm = re.match(r'^e1_(.+?)_([a-z_]+)_(base|permit|channel)\.csv$', os.path.basename(f))
    if not mm:
        continue
    model, dom, arm = mm.group(1), mm.group(2), mm.group(3)
    zone = 'dense' if dom in DENSE else ('aerial' if dom in AERIAL else dom)
    nz[(model, zone, arm)].update(read_csv(f))

print('=' * 118)
print('■ 真零池（E2 新测，306 张核实图）vs 非零池（已冻结）—— 同一支探针、同一分类口径')
print('=' * 118)
out = dict(purpose='E2 的真零/非零对照（盲审 #1 的"混合真零/非零"要求）',
           rule='raw-match，同 a5_judge.cls()', z0=dict(), nonzero=dict())

print('\n【非零池（gt>0 为主）】')
for (model, zone, arm) in sorted(nz):
    if arm not in ARMS:
        continue
    p = pct(nz[(model, zone, arm)])
    out['nonzero']['%s|%s|%s' % (model, zone, arm)] = dict(n=len(nz[(model, zone, arm)]), pct=p)
    print('  %-28s %-7s %-8s n=%4d  zero %5.1f | no_people %5.1f | cannot_judge %5.1f'
          % (model, zone, arm, len(nz[(model, zone, arm)]), p['zero'], p['no_people'], p['cannot_judge']))

print('\n【真零池（Z0，gt=0）】')
for (model, lang, stratum, arm) in sorted(z0):
    p = pct(z0[(model, lang, stratum, arm)])
    out['z0']['%s|%s|%s|%s' % (model, lang, stratum, arm)] = \
        dict(n=len(z0[(model, lang, stratum, arm)]), pct=p)
    print('  %-28s %-3s %-8s %-8s n=%3d  zero %5.1f | no_people %5.1f | cannot_judge %5.1f | abstain %5.1f'
          % (model, lang, stratum, arm, len(z0[(model, lang, stratum, arm)]), p['zero'],
             p['no_people'], p['cannot_judge'], p['abstain']))

# 关键对照：channel 臂在两个池上" emptiness 出口 vs 分辨率出口"的用法差异
print('\n■ 关键对照（`channel` 臂）：真零 → `no_people`，非零密集 → `cannot_judge`')
for model in sorted({k[0] for k in z0}):
    zp = [pct(z0[k]) for k in z0 if k[0] == model and k[3] == 'channel' and k[1] == 'cn']
    npd = pct(nz[(model, 'dense', 'channel')]) if (model, 'dense', 'channel') in nz else None
    if zp and npd:
        zpz = sum(v['no_people'] for v in zp) / len(zp)
        print('  %-28s 真零 no_people %5.1f%%  vs  非零密集 cannot_judge %5.1f%%（no_people %4.1f%%）'
              % (model, zpz, npd['cannot_judge'], npd['no_people']))

h = None
io.open(OUT, 'w', encoding='utf-8', newline='\n').write(json.dumps(out, ensure_ascii=False, indent=2))
h = hashlib.md5(io.open(OUT, 'rb').read()).hexdigest()
io.open(OUT + '.md5', 'w', encoding='utf-8', newline='\n').write('%s  %s  (ea2_contrast.py)\n'
                                                               % (h, os.path.basename(OUT)))
print('\n已写出 %s（md5 %s）' % (os.path.basename(OUT), h[:12]))
