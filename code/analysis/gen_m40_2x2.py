# -*- coding: utf-8 -*-
"""gen_m40_2x2.py —— 为 M.40 生成评审要求的**逐项 2×2 表**：出口（`no_people` / `cannot_judge`）
× 图像类型（真零池 / 非零密集池），并冻结成 `m40_2x2_result.json`。

## 为什么加这张表（v0539 八模型盲审，dsflash 的扣分项）
M.40 原文把"真零图上用 `no_people`、真有人图上改用 `cannot_judge`"写成**区间**
（真零 `no_people` 47.9–86.9%、非零密集 `cannot_judge` 92.1–100%、`no_people` 0.0–1.7%）。
dsflash 要的是**同一张 2×2 表里的计数**，理由是区间看不出"两个出口被有区别地使用"这一事实的
**规模**（多少观测落在哪个格）。数据早已冻结，纯 ANALYSIS。

## 口径（必须写清，否则又是"跨口径相减"）
* **观测级池化**：每个 (构建 × 语言 × 分层 × 服务启动 × item) 算**一个观测**；真零侧
  5 构建 × 2 语言 × 2 分层 × 3 启动 × 153 item = 9,180 观测/臂；非零侧为
  4 构建 × 密集域 × item（各构建的 item 集不同，故用**该池的实际观测数**为分母，不强行对齐）。
* **分类**：raw-match（同 `a5_judge.cls()`）：先扫 raw 文本的 `abstain`/`cannot_judge`/`no_people`，
  再退回 `pred`（0 → `zero`，非 0 → `nonzero`，空 → `unparsed`）。
* 两侧**同一支探针**；这里只做统计，不做任何新推理。
* 真零侧按 (model, lang, stratum, arm) 池化前**断言三次服务的 item 集完全一致**（同 `ea2_contrast.py`）。

用法：python -u gen_m40_2x2.py [--apply]
    不带 --apply 时只打印表与统计，不写盘。
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
Z0 = RP('analysis', 'ea2_z0')
NZ = RP('analysis', 'e1_results_nonzero')
OUT = RP('analysis', 'work', 'm40_2x2_result.json')
DENSE = ('st_a', 'ucf')
ARMS = ('base', 'permit', 'channel')
KEYS = ('zero', 'nonzero', 'no_people', 'cannot_judge', 'abstain', 'unparsed')


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


def read_csv(f):
    d = {}
    for r in csv.DictReader(io.open(f, encoding='utf-8-sig', errors='replace')):
        if '#' in str(r.get('item') or ''):
            continue
        d[r['item']] = cls_of(r.get('raw'), r.get('pred'))
    return d


def wilson(k, n, z=1.959964):
    """Wilson 95% 区间（双侧）。与 `anchor_m40m41.py` 的 `wilson_hi` **同源同一公式**——
    正文/附录已有的零格上界就是它算的，故这里给非零格区间时用的是**同一把尺子**。
    （v0539 盲审 glm53flash 指出：零格给了界、非零格没给，与本文自订规则不一致。）"""
    if not n:
        return (0.0, 0.0)
    p = k / float(n)
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    h = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5)
    # ★ 端点**统一保留 2 位小数**：若在这里就 round 到 1 位，0/9180 的上界 0.04% 会塌成 0.0，
    #   而那正好违反本稿"不许把 0 印成精确的 0"的规矩。冻结件里存什么，表里就印什么（口径一致）。
    return (round(100.0 * max(0.0, (c - h) / d), 2), round(100.0 * min(1.0, (c + h) / d), 2))


def tally(obs):
    c = collections.Counter(obs)
    n = len(obs)
    # ★ `other` 必须**存进冻结件**：门禁 `anchor_m40m41.py` 只认"冻结件里存在的值"，
    #   若表里印了 other 而 json 里没有，门禁会（正确地）判为"无出处"。
    #   第一次就是这么被抓的：2372 / 8903 / 484 三处被判未登记。⇒ 派生量也要落进冻结件。
    other = c.get('nonzero', 0) + c.get('abstain', 0) + c.get('unparsed', 0)
    cnt = dict({k: c.get(k, 0) for k in KEYS}, other=other)
    # ★ Wilson 区间也一并落盘（同"派生量必须进冻结件"的道理）
    ci = {k: wilson(cnt[k], n) for k in list(cnt)}
    return dict(n=n, count=cnt,
                pct=dict({k: round(100.0 * cnt[k] / n, 1) for k in cnt}),
                ci=ci)


def main():
    apply = '--apply' in sys.argv
    # ── 真零侧 ────────────────────────────────────────────────────────────
    z0 = collections.defaultdict(list)
    z0_items = collections.defaultdict(list)
    for f in glob.glob(RP('analysis', 'ea2_z0', '*', '*.csv')):
        m = re.match(r'^(cn|en)_(.+)_s(\d)$', os.path.basename(os.path.dirname(f)))
        mm = re.match(r'^e1_(.+?)_(z0easy|z0hard)_(base|permit|channel)_.*\.csv$', os.path.basename(f))
        if not (m and mm):
            continue
        k = (mm.group(1), m.group(1), mm.group(2), mm.group(3))
        z0[k].extend(read_csv(f).values())
        z0_items[k].append((int(m.group(3)), set(read_csv(f))))
    for k, lst in z0_items.items():
        sets = [s for _, s in sorted(lst)]
        assert len(sets) >= 1 and all(s == sets[0] for s in sets[1:]), 'item 集不一致，不能池化：%s' % (k,)

    # ── 非零（密集）侧 ─────────────────────────────────────────────────────
    nz = collections.defaultdict(list)
    for f in glob.glob(RP('analysis', 'e1_results_nonzero', '*.csv')):
        mm = re.match(r'^e1_(.+?)_([a-z_]+)_(base|permit|channel)\.csv$', os.path.basename(f))
        if not mm:
            continue
        model, dom, arm = mm.group(1), mm.group(2), mm.group(3)
        if dom not in DENSE:
            continue
        nz[(model, arm)].extend(read_csv(f).values())

    out = dict(purpose='M.40 的逐项 2×2：出口 × 图像类型（v0539 盲审 dsflash 要求）',
               rule='raw-match（同 a5_judge.cls()）；观测级池化：每个 (构建×语言×分层×启动×item) 一个观测',
               arms={})
    print('=' * 108)
    print('■ M.40 的逐项 2×2：出口（no_people / cannot_judge）× 图像类型（真零池 / 非零密集池）')
    print('=' * 108)
    for arm in ARMS:
        zobs = [v for k in z0 if k[3] == arm for v in z0[k]]
        nobs = [v for k in nz if k[1] == arm for v in nz[k]]
        zt, nt = tally(zobs), tally(nobs)
        out['arms'][arm] = dict(truezero=zt, nonzero_dense=nt)
        print('\n臂 `%s`：' % arm)
        print('  真零池  n=%5d ｜ no_people %5d (%5.1f%%) ｜ cannot_judge %5d (%4.1f%%) ｜ zero %5d (%4.1f%%) ｜ 其他 %d'
              % (zt['n'], zt['count']['no_people'], zt['pct']['no_people'],
                 zt['count']['cannot_judge'], zt['pct']['cannot_judge'],
                 zt['count']['zero'], zt['pct']['zero'],
                 zt['count']['nonzero'] + zt['count']['abstain'] + zt['count']['unparsed']))
        print('  非零密集 n=%5d ｜ no_people %5d (%5.1f%%) ｜ cannot_judge %5d (%4.1f%%) ｜ zero %5d (%4.1f%%) ｜ 其他 %d'
              % (nt['n'], nt['count']['no_people'], nt['pct']['no_people'],
                 nt['count']['cannot_judge'], nt['pct']['cannot_judge'],
                 nt['count']['zero'], nt['pct']['zero'],
                 nt['count']['nonzero'] + nt['count']['abstain'] + nt['count']['unparsed']))
        # 结构性断言：`channel` 臂的两个出口必须被**有区别地**使用（真零偏 no_people、非零偏 cannot_judge）
        if arm == 'channel':
            assert zt['pct']['no_people'] > zt['pct']['cannot_judge'], 'channel 臂真零侧未偏向 no_people'
            assert nt['pct']['cannot_judge'] > nt['pct']['no_people'], 'channel 臂非零侧未偏向 cannot_judge'

    # markdown 表（供 M.40 直接粘贴；数字全部来自上面的统计）
    # ★ 单元格带 Wilson 95% 区间：零格与非零格**同一把尺子**（回应 glm53flash 的 D1d）
    lines = ['| arm | pool | n | `no_people` | `cannot_judge` | `zero` | other |',
             '|---|---|---|---|---|---|---|']
    # ★ 区间格式：端点统一 2 位小数（与冻结件一致），避免 0.04% 印成 0.0
    for arm in ARMS:
        for lab, key in (('true-zero crops', 'truezero'), ('non-zero dense items', 'nonzero_dense')):
            t = out['arms'][arm][key]
            cell = lambda k: ('**%d** (%.1f%%, [%.2f, %.2f])'
                              % (t['count'][k], t['pct'][k], t['ci'][k][0], t['ci'][k][1]))
            lines.append('| `%s` | %s | %d | %s | %s | %s | %d |'
                         % (arm, lab, t['n'], cell('no_people'), cell('cannot_judge'),
                            cell('zero'), t['count']['other']))
    md = '\n'.join(lines)
    out['markdown'] = md
    print('\n' + md)

    if apply:
        io.open(OUT, 'w', encoding='utf-8', newline='\n').write(json.dumps(out, ensure_ascii=False, indent=2))
        h = hashlib.md5(io.open(OUT, 'rb').read()).hexdigest()
        io.open(OUT + '.md5', 'w', encoding='utf-8', newline='\n').write(
            '%s  %s  (gen_m40_2x2.py)\n' % (h, os.path.basename(OUT)))
        print('\n已冻结 %s（md5 %s）' % (os.path.basename(OUT), h[:12]))
    else:
        print('\n（未写盘；加 --apply 冻结）')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
