# -*- coding: utf-8 -*-
"""把 M.24.3 的发现**系统化**（零 GPU）：在所有已有 `channel` 臂的家族×域上，
比较 `permit` 与 `channel` 两个出口的**清除率**，检验"把出口**列为选项**是否严格优于**给予许可**"。

判据（先写死）：
  · 若存在 (家族×域) 单元满足 residual(permit) > 5% 而 residual(channel) ≤ 5% ⇒ 记"channel 救场"，并列出。
  · 若所有单元两者都 ≤5% 或都 >5% ⇒ 记"两者等效（在这些单元上）"。
数据：`analysis/e2xt_a800/merged/`（4 新家族 + 3 锚点）、`analysis/e2_newh20/`（E2 的 14 配置）。
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
DIRS = [RP('analysis', 'e2xt_a800', 'merged'), RP('analysis', 'e2_newh20')]
DS_ALL = ['st_a', 'st_b', 'ucf', 'visdrone', 'aitod']
ABSTAIN = ('abstain', 'cannot_judge', 'no_people')


def cls(p):
    raw = str(p.get('raw') or '').lower()
    v = str(p.get('pred') or '').strip()
    for k in ABSTAIN:
        if k in raw:
            return 'abstain'
    if v == '':
        return 'unparsed'
    try:
        return 'zero' if float(v) == 0 else 'nonzero'
    except ValueError:
        return 'unparsed'


def load(fn):
    for d in DIRS:
        p = os.path.join(d, fn)
        if os.path.exists(p):
            return {r['item']: cls(r) for r in csv.DictReader(io.open(p, encoding='utf-8-sig'))}
    return None


def cfg_of(fn):
    body = fn[3:-4]
    for ds in DS_ALL:
        i = body.find('_' + ds + '_')
        if i > 0:
            return body[:i], ds
    return None, None


units = {}
for d in DIRS:
    if not os.path.isdir(d):
        continue
    for f in sorted(os.listdir(d)):
        if not (f.startswith('e1_') and f.endswith('.csv')):
            continue
        c, ds = cfg_of(f)
        if not c or not ds:
            continue
        for arm in ('base', 'permit', 'channel'):
            if f.endswith('_%s.csv' % arm):
                units.setdefault((c, ds), {})[arm] = f

rows = []
for (c, ds), arms in sorted(units.items()):
    if not all(a in arms for a in ('base', 'permit', 'channel')):
        continue
    b, p, ch = load(arms['base']), load(arms['permit']), load(arms['channel'])
    keys = sorted(set(b) & set(p) & set(ch))
    z = [k for k in keys if b[k] == 'zero']
    if len(z) < 10:
        continue
    rp = sum(1 for k in z if p[k] == 'zero') / float(len(z))
    rc = sum(1 for k in z if ch[k] == 'zero') / float(len(z))
    rows.append((c, ds, len(z), rp, rc))

print('%-30s %-9s %6s %10s %10s %s' % ('配置', '域', '零池n', 'permit残留', 'channel残留', 'channel救场?'))
saves = []
for c, ds, n, rp, rc in rows:
    save = (rp > 0.05) and (rc <= 0.05)
    if save:
        saves.append((c, ds, rp, rc))
    print('%-30s %-9s %6d %10.3f %10.3f %s' % (c[:30], ds, n, rp, rc, '★' if save else ''))

print()
print('合计 %d 个 (家族×域) 单元；channel **严格救场**（permit>5%% 而 channel≤5%%）的：%d 个' % (len(rows), len(saves)))
for c, ds, rp, rc in saves:
    print('   %s | %s：permit %.3f → channel %.3f' % (c, ds, rp, rc))
if not saves:
    print('   ⇒ 在这些单元上两者等效（都 ≤5% 或都 >5%）')
import json
io.open(RP('analysis', 'work', 'permit_vs_channel_result.json'), 'w', encoding='utf-8').write(
    json.dumps(dict(n_units=len(rows), saves=saves,
                    rows=[dict(cfg=c, ds=ds, n=n, permit=rp, channel=rc) for c, ds, n, rp, rc in rows]),
               ensure_ascii=False, indent=1))
print('JSON -> permit_vs_channel_result.json')
