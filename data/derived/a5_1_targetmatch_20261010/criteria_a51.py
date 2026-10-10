# -*- coding: utf-8 -*-
"""A5-1 判据表：按图聚类 + 单侧 95% 上界 + 承重格门控（评审 A5 指定输出）。
★ 只读本地 raw/*.jsonl（24 件）；★ 判据全部预先写在 A5-1 设计里，不事后调参。
输出：A5-1_判据表.csv / A5-1_判据表.md
"""
import json, glob, os, re, csv, collections, random, statistics as st

RAW = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'raw')
OUT = os.path.dirname(os.path.abspath(__file__))
random.seed(20261010)


def parse2(raw):
    r = (raw or '').strip()
    m = re.search(r'\{\s*"count"\s*:\s*(\d+)', r) or re.search(r'\{\s*"response"\s*:\s*(\d+)', r)
    if m:
        return int(m.group(1)), 'num'
    if re.search(r'"count"\s*:\s*"(abstain|none|无)"', r, re.I) or \
       re.search(r'"response"\s*:\s*"(cannot_judge|no_people|abstain)"', r, re.I):
        return None, 'abs'
    low = r.lower()
    if any(t in low for t in ('abstain', 'cannot_judge', 'no_people')) or \
       re.search(r'(无法|不能|抱歉|sorry|unable|i can\'t|i cannot)', r):
        return None, 'abs'
    return None, 'other'


def wilson_ub(k, n, z=1.645):
    """单侧 95% 上界（Wilson，z=1.645）"""
    if n == 0:
        return 1.0
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    h = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5)
    return min(1.0, (c + h) / d)


rows = []
for f in sorted(glob.glob(os.path.join(RAW, '*.jsonl'))):
    b = os.path.basename(f)[:-6]
    cond = 'people' if '_people_' in b else ('class' if '_class_' in b else 'other')
    alias = b.split('_')[0]
    rep = b.split('_')[-1]
    ok = {}
    for l in open(f, encoding='utf-8', errors='replace'):
        try:
            r = json.loads(l)
        except Exception:
            continue
        if r.get('http') == 200:
            ok[r.get('key')] = r
    for k, r in ok.items():
        v, kind = parse2(r.get('raw'))
        gt = r.get('gt')
        try:
            gt = int(gt)
        except Exception:
            gt = None
        rows.append(dict(alias=alias, cond=cond, rep=rep, arm=r.get('arm'), image=k.split('|')[-1],
                         kind=kind, pred=v, gt=gt,
                         dev=(abs(v - gt) if (kind == 'num' and gt is not None) else None)))

# ① 逐 条件×臂 汇总 + 按图聚类
summary = []
for cond in ('people', 'class'):
    for arm in ('base', 'permit', 'channel'):
        sel = [x for x in rows if x['cond'] == cond and x['arm'] == arm]
        if not sel:
            continue
        n = len(sel)
        num = [x for x in sel if x['kind'] == 'num']
        zero = [x for x in num if x['pred'] == 0]
        devs = [x['dev'] for x in num if x['dev'] is not None]
        # 按图聚类：每图取"该图是否出现答零"（三 rep 合并 ⇒ 图级指示）
        byimg = collections.defaultdict(list)
        for x in sel:
            byimg[x['image']].append(x)
        img_zero = {i: any((y['kind'] == 'num' and y['pred'] == 0) for y in v) for i, v in byimg.items()}
        k_img = sum(1 for v in img_zero.values() if v)
        n_img = len(img_zero)
        # 图级 bootstrap（单侧 95% UB），2000 次
        keys = list(img_zero)
        ub = None
        if keys:
            boots = []
            for _ in range(2000):
                s = [img_zero[random.choice(keys)] for _ in keys]
                boots.append(sum(s) / len(s))
            boots.sort()
            ub = boots[int(0.95 * len(boots)) - 1] if len(boots) > 20 else None
        summary.append(dict(cond=cond, arm=arm, cells=n, numeric=len(num), zero=len(zero),
                            zero_rate_num=round(len(zero) / len(num), 4) if num else None,
                            mae_median=st.median(devs) if devs else None,
                            mae_mean=round(st.mean(devs), 2) if devs else None,
                            imgs=n_img, imgs_with_zero=k_img,
                            img_zero_rate=round(k_img / n_img, 4) if n_img else None,
                            img_boot_ub95=round(ub, 4) if ub is not None else None,
                            wilson_ub95_cell=round(wilson_ub(len(zero), len(num)), 4) if num else None))

with open(os.path.join(OUT, 'A5-1_判据表.csv'), 'w', encoding='utf-8', newline='') as fh:
    w = csv.DictWriter(fh, fieldnames=list(summary[0].keys()))
    w.writeheader()
    for r in summary:
        w.writerow(r)

# ② 按图配对（base 臂 people vs class）
P = {x['image']: x for x in rows if x['cond'] == 'people' and x['arm'] == 'base' and x['kind'] == 'num'}
C = {x['image']: x for x in rows if x['cond'] == 'class' and x['arm'] == 'base' and x['kind'] == 'num'}
common = sorted(set(P) & set(C))
pz = [1 if P[i]['pred'] == 0 else 0 for i in common]
cz = [1 if C[i]['pred'] == 0 else 0 for i in common]
d = [P[i]['pred'] - C[i]['pred'] for i in common]

# ③ 门控
gate = []
cls_base = [x for x in rows if x['cond'] == 'class' and x['arm'] == 'base' and x['kind'] == 'num']
zero_imgs = {x['image'] for x in cls_base if x['pred'] == 0}
gate.append(('承重格（class×base）出现答零的不同图像数', len(zero_imgs), '≥60', 'PASS' if len(zero_imgs) >= 60 else 'INDETERMINATE'))
r_cls = [x for x in summary if x['cond'] == 'class' and x['arm'] == 'base'][0]
gate.append(('class×base 答零率', r_cls['zero_rate_num'], '—', '—'))
gate.append(('其图级 bootstrap 单侧 95% 上界', r_cls['img_boot_ub95'], '≤0.05 才能宣称残留≤5%',
             'PASS' if (r_cls['img_boot_ub95'] is not None and r_cls['img_boot_ub95'] <= 0.05) else 'INDETERMINATE'))

L = ['# A5-1 判据表（目标词配对；FSC-147 300 图 × 4 构建 × 2 条件 × 3 臂 × 3 起服 = 21,600 格）', '',
     '## 一 逐 条件×臂（★ 按图聚类；`img_boot_ub95` = 图级 bootstrap 单侧 95% 上界）', '',
     '| 条件 | 臂 | 格数 | numeric | zero | 答零率(数) | MAE中位 | MAE均值 | 图数 | 含零图数 | 图级零率 | 图级UB95 | Wilson UB(格级) |',
     '|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|']
for r in summary:
    L.append('| {cond} | {arm} | {cells} | {numeric} | {zero} | {zero_rate_num} | {mae_median} | {mae_mean} | {imgs} | {imgs_with_zero} | {img_zero_rate} | {img_boot_ub95} | {wilson_ub95_cell} |'.format(**r))
L += ['', '## 二 按图配对（base 臂，people vs class，共同图 %d）' % len(common), '',
      '- 仅 people 答零：**%d** 张｜仅 class 答零：**%d** 张｜两者都零：**%d** 张'
      % (sum(1 for i in range(len(common)) if pz[i] and not cz[i]),
         sum(1 for i in range(len(common)) if cz[i] and not pz[i]),
         sum(1 for i in range(len(common)) if pz[i] and cz[i])),
      '- 逐图差值（people − class）：中位 **%s**｜均值 **%.2f**' % (st.median(d), st.mean(d)), '',
      '## 三 门控判定（评审指定）', '', '| 判据 | 实测 | 门槛 | 判定 |', '|---|---:|---|---|']
for a, b_, c_, e_ in gate:
    L.append('| %s | %s | %s | **%s** |' % (a, b_, c_, e_))
L += ['', '★ 说明：本表**只读**原始行（24 件）；★ 判据与门槛**沿用 A5-1 设计原文**，未事后调整；★ 唯一丢失数据点 = `lov7b/people/rep2` 的 `5588.jpg`（退化重复、`finish=length`）⇒ **保留缺失、不填不猜**。']
open(os.path.join(OUT, 'A5-1_判据表.md'), 'w', encoding='utf-8').write('\n'.join(L) + '\n')

print('\n'.join(L[:6]))
print('...')
for r in summary:
    print('  %-7s %-8s 格=%-5d 答零率=%-7s MAE中位=%-5s 图级UB95=%s' % (r['cond'], r['arm'], r['cells'], r['zero_rate_num'], r['mae_median'], r['img_boot_ub95']))
print()
for a, b_, c_, e_ in gate:
    print('  门控: %-34s 实测=%-8s 门槛=%-24s %s' % (a, b_, c_, e_))
print('已写 A5-1_判据表.md / .csv')
