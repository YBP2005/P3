# -*- coding: utf-8 -*-
"""fsc_res_analyze.py — E1（FSC-147 分辨率敏感性）分析器：384（发布）/ 256（短边 256）/ 768（短边 768，上采样）。

## 前提事实（直接读官方包 `/root/fsc147_orig.zip` 的 6146 个图像条目核过）
FSC-147 官方发布件 `images_384_VarV2` 把**短边固定在 384**（6146/6146 = 100%），**长边随长宽比变化
（384–1918）**；本批 300 张样本：短边恒 384、长边 384–1229（中位 514）、长宽比 1.00–3.20。
⇒ "384"是**短边约束（定线性尺度）**，不是统一画布；原始分辨率**无**官方下载点。
故"另一分辨率"只能在可用方向上做，且必须用**统一直线缩放**（长宽比逐像素不变）：
  · 短边 **256**（`fsc_build_sc.py`，scale 0.6667，面积 0.444×）= 干净的低分辨率点；
  · 短边 **768**（scale 2.0000，面积 4.000×）= **同一信息、更大画布**，结论里必须标注 upsampled。
★ 早期版本按**最长边**归一（384×1229 → 240×768，面积比 0.391）：那会让"上采样"对高长宽比图为假，
  已废弃并删除旧目录（见 `fsc_build_sc.py` 顶部说明）。

## 两个 384
`<root>/384` 是 E1 本批次的 384 列（探针副本 `w1_fsc_probe_384.py`，与 256/768 只差图像/输出目录常量）；
`<root>/frozen384` 是 §5.6 的**冻结面板** `/root/fsc_results`（由 `19g_probe_fsc.py` 产出，同样 import
冻结的 `19e_probe_multi.py` 提示词与解析器 ⇒ base/permit/channel/enumAbstain 四臂与 E1 **逐字同题**）。
⇒ 两者在共享臂上的差 = **同题同图、不同脚本批次与服务启动**的可复现性核对，一并写进产物。

## 口径
分类沿用论文自身的 raw-match 顺序（abstain → 数字 → unparsed），与 `a5_judge.cls()` 同源。
产物：`analysis/work/fsc_res_result.json`（+ .md5）
用法：python -u fsc_res_analyze.py [--root <default: data/derived/fsc_res/ in this package>]
目录约定：<root>/384/fsc_<model>_<arm>.csv、<root>/256/…、<root>/768up/…、<root>/frozen384/…
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
import argparse
import collections
import csv
import glob
import hashlib
import io
import json
import os
import re
import statistics as st
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
OUT = RP('analysis', 'work', 'fsc_res_result.json')
SWEEP = ('384', '256', '768up')
ARMS_RE = r'(base|permit|channel|enumAbstain|exemplar3|exemplar3permit)'



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


def read(f):
    d, preds = {}, []
    for r in csv.DictReader(io.open(f, encoding='utf-8-sig', errors='replace')):
        it = str(r.get('item') or '')
        if '#' in it:
            continue
        c = cls_of(r.get('raw'), r.get('pred'))
        d[it] = c
        try:
            preds.append(float(r.get('pred')))
        except (TypeError, ValueError):
            pass
    return d, preds


ap = argparse.ArgumentParser()
ap.add_argument('--root', default=RP('analysis', 'fsc_res'))
A = ap.parse_args()

res = collections.defaultdict(dict)
for tag in SWEEP + ('frozen384',):
    for f in glob.glob(os.path.join(A.root, tag, '*.csv')):
        m = re.match(r'^fsc_(.+?)_%s\.csv$' % ARMS_RE, os.path.basename(f))
        if not m:
            continue
        model, arm = m.group(1), m.group(2)
        d, preds = read(f)
        if not d:
            continue
        c = collections.Counter(d.values())
        n = len(d)
        res[model][('%s|%s' % (tag, arm))] = dict(
            n=n, zero=round(100.0 * c.get('zero', 0) / n, 1),
            abstain=round(100.0 * c.get('abstain', 0) / n, 1),
            cannot_judge=round(100.0 * c.get('cannot_judge', 0) / n, 1),
            no_people=round(100.0 * c.get('no_people', 0) / n, 1),
            nonzero=round(100.0 * c.get('nonzero', 0) / n, 1),
            unparsed=round(100.0 * c.get('unparsed', 0) / n, 1),
            median_pred=(round(st.median(preds), 1) if preds else None))

# 本批次实际测了哪些 (分辨率, 臂) —— 表只列**真有数据**的格子；顺序固定（表行序不得随文件系统变化）
ARMS_ORDER = ('base', 'permit', 'channel', 'enumAbstain', 'exemplar3', 'exemplar3permit')
arms_seen = {k.split('|')[1] for t in res.values() for k in t}
SW_ARMS = [a for a in ARMS_ORDER if a in arms_seen]

print('=' * 112)
print('■ E1：FSC-147 的分辨率敏感性（384 = 数据集发布分辨率；256 = 降采样；768up = 上采样）')
print('  臂：%s' % ', '.join(SW_ARMS))
print('=' * 112)
for model in sorted(res):
    print('\n%s' % model)
    for tag in SWEEP:
        row = []
        for arm in SW_ARMS:
            v = res[model].get('%s|%s' % (tag, arm))
            if v:
                row.append('%s: zero %4.1f abstain %4.1f unparsed %3.1f med %6.1f'
                           % (arm[:6], v['zero'], v['abstain'], v['unparsed'], v['median_pred'] or -1))
        if row:
            print('  %-6s %s' % (tag, ' | '.join(row)))

# 与 384 的差（关键量：率是否随分辨率移动）
# ★ 基线回退：本批次的 384（同脚本重测）是**附加核对**，排在最后；若它还没跑到（提前收工）或某构建缺，
#   就用 **§5.6 的冻结 384 面板**作基线——两者提示词/解析器/300 张样本**逐字同一**（都 import 冻结的
#   19e_probe_multi.py），故这是**设计内的**比较；但**必须把基线来源写进产物**，不能混着不标。
print('\n■ 相对 384 的变化（pp；基线 = 本批次 384，缺则回退冻结面板，逐条标注）')
delta = {}
for model in sorted(res):
    for arm in SW_ARMS:
        b, src = res[model].get('384|%s' % arm), 'sweep384'
        if not b:
            b, src = res[model].get('frozen384|%s' % arm), 'frozen384'
        if not b:
            continue
        for tag in ('256', '768up'):
            v = res[model].get('%s|%s' % (tag, arm))
            if not v:
                continue
            k = '%s|%s|%s' % (model, tag, arm)
            delta[k] = dict(zero=round(v['zero'] - b['zero'], 1),
                            baseline_from=src,
                            abstain=round(v['abstain'] - b['abstain'], 1))
            print('  %-28s %-6s %-16s Δzero %+5.1f pp | Δabstain %+5.1f pp  [基线 %s]'
                  % (model, tag, arm, delta[k]['zero'], delta[k]['abstain'], src))

# ── 交叉核对：E1 的 384 列 vs 冻结面板 /root/fsc_results（同题同图、不同脚本批次）──
print('\n■ 384 列与冻结面板的核对（同提示词、同 300 图；差 = 批次可复现性）')
repl = {}
for model in sorted(res):
    for arm in SW_ARMS:
        a, b = res[model].get('384|%s' % arm), res[model].get('frozen384|%s' % arm)
        if not (a and b):
            continue
        k = '%s|%s' % (model, arm)
        repl[k] = dict(sweep_zero=a['zero'], frozen_zero=b['zero'], d_zero=round(a['zero'] - b['zero'], 1),
                       sweep_abstain=a['abstain'], frozen_abstain=b['abstain'],
                       d_abstain=round(a['abstain'] - b['abstain'], 1))
        print('  %-28s %-16s Δzero %+5.1f pp（本批 %.1f vs 冻结 %.1f）| Δabstain %+5.1f pp'
              % (model, arm, repl[k]['d_zero'], a['zero'], b['zero'], repl[k]['d_abstain']))
if not repl:
    print('  （暂无两侧数据：需先跑完本批次 384 列）')

# 网格内最大位移（供正文/M.41 直接引用，避免手算）
mx = {'zero': None, 'abstain': None}
for field in ('zero', 'abstain'):
    cand = [(abs(v[field]), k) for k, v in delta.items() if v.get(field) is not None]
    cand += [(abs(v['d_' + field]), k) for k, v in repl.items() if v.get('d_' + field) is not None]
    if cand:
        mx[field] = dict(max_abs_pp=round(max(c[0] for c in cand), 1),
                         where=max(cand)[1], n=len(cand))
print('\n■ 最大位移：Δzero %s ；Δabstain %s' % (mx['zero'], mx['abstain']))

out = dict(
    purpose='E1：FSC-147 的分辨率敏感性；并记录"384 是发布件的短边约束"这一事实',
    fact_official_release='FSC-147 官方发布件 images_384_VarV2：6146 张图**短边恒为 384**（100%），'
                          '长边随长宽比在 384–1918 之间（本批样本长边 384–1229，长宽比 1.00–3.20）；'
                          '原始分辨率无官方下载点 ⇒ 384 由数据集决定，不是本文管道的选择',
    design='同一族探针（副本只差图像/输出目录常量，提示词与解析器 import 自冻结的 19e_probe_multi.py）；'
           '同一 300 张冻结样本；三档 = 短边 384（发布）/ 256（scale 0.6667，面积 0.444×）/'
           '768（scale 2.0，面积 4.0×，upsampled）× 六臂',
    rule='raw-match（abstain → 数字 → unparsed），与 a5_judge.cls() 同源',
    arms=SW_ARMS,
    by_model=res, delta_vs_384=delta, replication_384_vs_frozen=repl, max_shift=mx, root=A.root,
)
io.open(OUT, 'w', encoding='utf-8', newline='\n').write(json.dumps(out, ensure_ascii=False, indent=2))
h = hashlib.md5(io.open(OUT, 'rb').read()).hexdigest()
io.open(OUT + '.md5', 'w', encoding='utf-8', newline='\n').write('%s  %s  (fsc_res_analyze.py)\n'
                                                               % (h, os.path.basename(OUT)))
print('\n已写出 %s（md5 %s）' % (os.path.basename(OUT), h[:12]))
