# -*- coding: utf-8 -*-
"""采用示例（路线 A 的第②件）：**口径一换，名次就变** —— 用 E2 普查记录直接算，无需任何新实验。

原理：E2 的零池（语料答 0 的 item）与非零池（语料给出数字的 item）在**域内互补**，
合起来就是该域的（语料答过的）测试集 ⇒ 可以在**同一 item 集合**上同时算两种口径：
  口径 A「把弃权当 0」：ρ_all = (Σpred − Σgt) / Σgt，pred 取模型原样（含 0）
  口径 B「只算已答」  ：ρ_ans = 同一式，但只保留 pred≠0 的 item
两种口径都是领域内**标准做法**（MAE/RMSE 用 A，报告"误差方向"时常偷偷用 B）。

判据（先写死）：
  · 在每个域内按 |ρ| 给配置排名，比较 A 与 B 两个排名：
    **出现 top-1 更替**或**排名相关（Spearman）< 0.9** ⇒ 记"口径切换改变结论"；
  · 统计有多少个 (域) 单元出现改变，并给出具体翻转对（哪个配置超过了哪个）。
"""


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
import io
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')
D = RP('analysis', 'e2_newh20')
DS = ['st_a', 'st_b', 'ucf', 'visdrone', 'aitod']


def load(fn):
    p = os.path.join(RP('analysis', 'e2_newh20'), fn)
    if not os.path.exists(p):
        return None
    out = {}
    for r in csv.DictReader(io.open(p, encoding='utf-8-sig')):
        try:
            pred = float(str(r['pred']).strip())
        except (KeyError, TypeError, ValueError):
            continue
        try:
            gt = float(r['gt'])
        except (KeyError, TypeError, ValueError):
            continue
        out[r['item']] = (pred, gt)
    return out or None


DS_ALL = ['st_a', 'st_b', 'ucf', 'visdrone', 'aitod', 'countbench']


def cfg_of(fn):
    """e1_<config>_<ds>_<arm>.csv → (<config>, <ds>)；配置名本身可能含 '-'、不含 '_'。"""
    body = fn[3:-4]
    for ds in DS_ALL:
        i = body.find('_' + ds + '_')
        if i > 0:
            return body[:i], ds
    return None, None


cfgs = set()
for f in os.listdir(D):
    if f.startswith('e1_') and f.endswith('.csv'):
        c, _ = cfg_of(f)
        if c:
            cfgs.add(c)
cfgs = sorted(cfgs)
print('配置数 %d：%s' % (len(cfgs), ', '.join(cfgs[:8]) + (' …' if len(cfgs) > 8 else '')))

def spearman(a, b):
    def rk(x):
        o = sorted(range(len(x)), key=lambda i: x[i])
        r = [0.0] * len(x)
        for pos, i in enumerate(o):
            r[i] = pos + 1
        return r
    ra, rb = rk(a), rk(b)
    n = len(a)
    ma, mb = sum(ra) / n, sum(rb) / n
    num = sum((ra[i] - ma) * (rb[i] - mb) for i in range(n))
    da = sum((x - ma) ** 2 for x in ra) ** .5
    db = sum((x - mb) ** 2 for x in rb) ** .5
    return num / (da * db) if da and db else float('nan')


flip_units = []
detail = {}
for ds in DS:
    per = {}
    for c in cfgs:
        z = load('e1_%s_%s_base.csv' % (c, ds))
        nz = load('nz__e1_%s_%s_base.csv' % (c, ds))
        if not z or not nz:
            continue
        merged = dict(nz)
        merged.update(z)          # 零池优先（两池在域内互补）
        if len(merged) < 40:
            continue
        per[c] = merged
    if len(per) < 3:
        continue
    # ★ 只在**所有配置共有的 item 交集**上比（否则 n 不同会把排名差异读成口径差异）
    common = None
    for m in per.values():
        common = set(m) if common is None else (common & set(m))
    common = sorted(common)
    rows = []
    for c, m in per.items():
        if len(common) < 40:
            continue
        sp = sum(m[k][0] for k in common)
        sg = sum(m[k][1] for k in common)
        ann = [k for k in common if m[k][0] != 0]
        rho_all = (sp - sg) / sg * 100 if sg else None
        if len(ann) < 10:
            continue
        sp2 = sum(m[k][0] for k in ann)
        sg2 = sum(m[k][1] for k in ann)
        rho_ans = (sp2 - sg2) / sg2 * 100 if sg2 else None
        rows.append(dict(cfg=c, n=len(common), n_ans=len(ann),
                         w=100.0 * len(ann) / len(common), rho_all=rho_all, rho_ans=rho_ans))
    if len(rows) < 3:
        continue
    # 按 |ρ| 排名（越小越"准"）
    ra = sorted(rows, key=lambda r: abs(r['rho_all']))
    rb = sorted(rows, key=lambda r: abs(r['rho_ans']))
    sp = spearman([abs(r['rho_all']) for r in rows], [abs(r['rho_ans']) for r in rows])
    flip = ra[0]['cfg'] != rb[0]['cfg']
    detail[ds] = dict(n_cfg=len(rows), spearman=round(sp, 3),
                      top1_all=ra[0]['cfg'], top1_ans=rb[0]['cfg'], top1_flip=flip,
                      rows=[{k: (round(v, 2) if isinstance(v, float) else v) for k, v in r.items()} for r in rows])
    if flip or sp < 0.9:
        flip_units.append(ds)
    print('\n== %s ==（%d 个配置；Spearman(A,B)=%.3f；top1: A=%s  B=%s  %s）'
          % (ds, len(rows), sp, ra[0]['cfg'], rb[0]['cfg'], '★翻转' if flip else ''))
    print('   %-24s %5s %6s %9s %9s' % ('配置', 'n', '已答%', 'ρ_all', 'ρ_ans'))
    for r in ra:
        print('   %-24s %5d %6.1f %9.2f %9.2f' % (r['cfg'], r['n'], r['w'], r['rho_all'], r['rho_ans']))

print()
print('=' * 92)
print('结论：%d/%d 个域出现"口径切换改变结论"' % (len(flip_units), len(detail)))
print('  ' + ('、'.join(flip_units) if flip_units else '无'))
print('=' * 92)
import json
io.open(RP('analysis', 'work', 'convention_rank_result.json'), 'w', encoding='utf-8').write(
    json.dumps(dict(units=detail, flip_units=flip_units, n_units=len(detail)), ensure_ascii=False, indent=1))
print('JSON -> convention_rank_result.json')
