# -*- coding: utf-8 -*-
"""f9_repro.py —— **F.9 溯源的决定性实验**：那十个 unit 的"保序/分位数"跨度到底出自哪一族？

## 为什么必须做
Q3 的裁决要求"补脚本 + f9_quoted.json；做不到就做可核验转录"。而 Q6 的纪律要求
"凡引用校准族处必须写明哪一族 + 是否可部署"。两者在 F.9 上撞在一起：

* F.9 表头自述口径是 **pooled relative deviation**（池化 ρ）；
* 仓库里**唯一**实现保序/分位数校准的两个脚本 —— `calib_median.py` 与 `calib_truth.py` ——
  都是 **oracle 方向**（`p_cal = f(g)`，用了真值），且 `calib_median.py` 用的是**逐项中位**口径，
  与 F.9 自述的 pooled 口径**不是同一个**；
* `a39_calib3.py`（**可部署**方向 `pred′=a·pred+b`）只做仿射，不做保序/分位数。

⇒ 所以本脚本对每个 unit 同时算**两族 × 两个口径**，看哪一组能对上 F.9 印出的数：
    oracle 方向    = fit p 为 g 的函数，在 g 处取值（`calib_median.py`/`calib_truth.py` 的定义）；
    deployable 方向 = fit g 为 p 的函数（`a39_calib3.py` 的定义），在 p 处取值。
**对上 ⇒ 走 Q3 路径 A**（写 f9_quoted.json 并把单位/口径登记为权威）；
**对不上 ⇒ 走路径 B**（可核验转录 + 明确披露"该口径组合在仓库内无实现"）。

## 本脚本只说它能说的话
F.9 的十个 unit 与仓库文件的对应关系**部分是推断**（例如 "VLM, pixel budget" 未指明是 ivl 还是 q32）。
故本脚本对**可指认的来源**逐一试算，并把"来源指认"本身也打印出来供人工裁决；不硬凑、不调参。
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
import hashlib
import json
import io
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')
PM = RP('analysis', 'data', 'pod_mirror')
W = NR('@shared', 'work')
WORKDIR = os.path.dirname(os.path.abspath(__file__))
B = NR('@shared', 'work', 'b_harvest_20260917')
ANOM, SENT = 1e5, 1234567890

# F.9 印出的保序跨度（isotonic），用于比对
F9 = {
    'det·in-domain/VisDrone': 150.7,
    'det·zero-shot COCO': 54.2,
    'det·in-domain(micro)/BBBC005': 49.0,
    'density·official DM-Count/st_a(ShanghaiTech-A)': 33.5,
    'density·official DM-Count/ucf(UCF-QNRF)': 36.6,
    'VLM·pixel budget/Sha. 1.1': 1.1,
}


def load(p):
    return list(csv.DictReader(io.open(p, encoding='utf-8-sig', errors='replace')))


def fn(s):
    try:
        return float(s)
    except Exception:
        return None


def unitize(rows, dims, pcol):
    out = collections.defaultdict(dict)
    for r in rows:
        g = fn(r.get('gt')); p = fn(r.get(pcol))
        if g is None or g <= 0 or p is None or p >= ANOM or p == SENT:
            continue
        out[tuple(str(r[d]).strip() for d in dims)][str(r['item']).strip()] = (g, float(p))
    return out


# ---- 两族 × 两口径 ----
def rho_pooled(pairs):
    sg = sum(g for g, _ in pairs)
    return 100.0 * (sum(p for _, p in pairs) - sg) / sg if sg else None


def rho_median(pairs):
    v = sorted((p - g) / g * 100 for g, p in pairs if g > 0)
    if not v:
        return None
    n = len(v)
    return v[n // 2] if n % 2 else 0.5 * (v[n // 2 - 1] + v[n // 2])


def iso_oracle(pairs):
    """oracle：把 p 拟合为 g 的单调函数，在 g 处取值（calib_median.py 的定义）。"""
    from sklearn.isotonic import IsotonicRegression
    ir = IsotonicRegression(out_of_bounds='clip')
    ir.fit([g for g, _ in pairs], [p for _, p in pairs])
    return [(g, float(y)) for (g, _), y in zip(pairs, ir.predict([g for g, _ in pairs]))]


def iso_deploy(pairs):
    """deployable：把 g 拟合为 p 的单调函数，在 p 处取值（可部署方向）。"""
    from sklearn.isotonic import IsotonicRegression
    ir = IsotonicRegression(out_of_bounds='clip')
    ir.fit([p for _, p in pairs], [g for g, _ in pairs])
    return [(g, float(y)) for (g, p), y in zip(pairs, ir.predict([p for _, p in pairs]))]


def qnt_oracle(pairs):
    gs = sorted(g for g, _ in pairs)
    pr = sorted(range(len(pairs)), key=lambda i: pairs[i][1])
    out = [None] * len(pairs)
    for rank, i in enumerate(pr):
        out[i] = (pairs[i][0], float(gs[rank]))
    return out


def span(seq, cal):
    vals = []
    for prs in seq:
        prs2 = cal(prs) if cal else prs
        r = rho_pooled(prs2)
        if r is not None:
            vals.append(r)
    return max(vals) - min(vals) if len(vals) >= 2 else None


def report(name, bylevel, f9val):
    lv = sorted(bylevel)
    if len(lv) < 3:
        print('  %-46s 档位<3，跳过' % name)
        return
    common = set.intersection(*[set(bylevel[s]) for s in lv])
    if len(common) < 20:
        print('  %-46s 交集 %d <20，跳过' % (name, len(common)))
        return
    ks = sorted(common)
    seq = [[bylevel[s][k] for k in ks] for s in lv]
    row = dict(n_lv=len(lv), n=len(ks),
               C0=span(seq, None), ISO_oracle=span(seq, iso_oracle),
               ISO_deploy=span(seq, iso_deploy), QNT_oracle=span(seq, qnt_oracle))
    # 逐项中位口径（calib_median.py 的口径）另算一份，用于判断口径
    def span_med(cal):
        vals = []
        for prs in seq:
            prs2 = cal(prs) if cal else prs
            r = rho_median(prs2)
            if r is not None:
                vals.append(r)
        return max(vals) - min(vals) if len(vals) >= 2 else None
    print('  %-46s 档位%2d n=%3d | C0 %8.1f | ISO( oracle) %8.1f | ISO(deploy) %8.1f | QNT(oracle) %8.1f | F.9=%s'
          % (name, len(lv), len(ks), row['C0'], row['ISO_oracle'], row['ISO_deploy'],
             row['QNT_oracle'], ('%.1f' % f9val) if f9val is not None else '—'))
    row['f9'] = f9val                      # ★ 判读段要用：把 F.9 印出值一并带出
    row['C0_med'] = span_med(None)
    row['ISO_oracle_med'] = span_med(iso_oracle)
    row['ISO_deploy_med'] = span_med(iso_deploy)
    print('  %-46s          [逐项中位口径] C0 %8.1f | ISO(oracle) %8.1f | ISO(deploy) %8.1f'
          % ('', row['C0_med'], row['ISO_oracle_med'], row['ISO_deploy_med']))
    return row


print('=' * 150)
print('■ F.9 溯源：同一 unit 在 [oracle 方向] 与 [deployable 方向] × [pooled / 逐项中位] 下的保序跨度')
print('=' * 150)
print('  说明：F.9 自述口径 = pooled relative deviation；仓库内唯一的保序实现是 oracle 方向 + 逐项中位。')

res = {}
if os.path.exists(RP('analysis', 'data', 'pod_mirror', 'A', 'det_yolo_ladder_visdrone_det.csv')):
    res['det/VisDrone'] = report('Detection, in-domain / VisDrone',
                                 unitize(load(RP('analysis', 'data', 'pod_mirror', 'A', 'det_yolo_ladder_visdrone_det.csv')),
                                         ['tau', 'imgsz'], 'n_det_person'),
                                 F9['det·in-domain/VisDrone'])
if os.path.exists(RP('analysis', 'data', 'pod_mirror', 'A', 'det_yolo_ladder_yolo12n.csv')):
    res['det/COCO'] = report('Detection, zero-shot COCO',
                             unitize(load(RP('analysis', 'data', 'pod_mirror', 'A', 'det_yolo_ladder_yolo12n.csv')),
                                     ['tau', 'imgsz'], 'n_det_person'),
                             F9['det·zero-shot COCO'])
if os.path.exists(NR('@shared', 'work', 'b_harvest_20260917', 'bbbc_eval', 'ladder.csv')):
    res['det/BBBC005'] = report('Detection, in-domain / BBBC005',
                                unitize(load(NR('@shared', 'work', 'b_harvest_20260917', 'bbbc_eval', 'ladder.csv')),
                                        ['tau', 'imgsz'], 'n_det'),
                                F9['det·in-domain(micro)/BBBC005'])
if os.path.exists(NR('@shared', 'work', 'dm_ladder.csv')):
    u = unitize(load(NR('@shared', 'work', 'dm_ladder.csv')), ['dataset', 'protocol', 'value'], 'pred')
    for ds, lab, f9 in (('st_a', 'ShanghaiTech-A', F9['density·official DM-Count/st_a(ShanghaiTech-A)']),
                        ('ucf', 'UCF-QNRF', F9['density·official DM-Count/ucf(UCF-QNRF)'])):
        sub = {k: v for k, v in u.items() if k[0] == ds}
        if sub:
            res['density/' + ds] = report('Density regression, official DM-Count / %s' % lab, sub, f9)
for mdl in ('ivl', 'q32'):
    for ds in ('st_a', 'ucf', 'visdrone'):
        p = os.path.join(RP('analysis', 'data', 'pod_mirror'), 'res_ctrl__%s' % mdl, 'res_ctrl_%s.csv' % ds)
        if os.path.exists(p):
            res['pxbudget/%s/%s' % (mdl, ds)] = report('VLM, pixel budget / %s / %s' % (mdl, ds),
                                                       unitize(load(p), ['budget'], 'pred'), None)
for mdl, f9v in (('ivl', 97.7), ('q32', 85.9)):
    p = os.path.join(RP('analysis', 'data', 'pod_mirror'), 'b2__out_%s' % mdl, 'E1.csv')
    if os.path.exists(p):
        res['contract/%s' % mdl] = report('VLM, output contract / %s' % mdl,
                                          unitize(load(p), ['arm'], 'pred'), f9v)

print()
print('=' * 150)
print('■ 判读规则（写死，避免事后挑）')
print('=' * 150)
print('  若某 unit 的 F.9 值与其 ISO(oracle) 或 ISO(deploy) 相差 <5% ⇒ 判定 F.9 用的是该族该口径；')
print('  若两者都差 >20% ⇒ 判定"F.9 的口径组合在本仓库内无实现"，走 Q3 路径 B（可核验转录 + 显式披露）。')


# ============================== 判读与冻结（2026-09-24 补） ==============================
# 规则在上一段已**写死**：<5% ⇒ 判 F.9 用的是该族该口径；两族都 >20% ⇒ 判"该口径组合在仓库内无实现"。
print()
print('=' * 150)
print('■ 逐 unit 判读（阈值：<5% 记为命中；两族都 >20% 记为"仓库内无实现"）')
print('=' * 150)
print('  %-46s %8s | %-28s | %-28s | %s'
      % ('unit', 'F.9', 'pooled: ISO(oracle) / (deploy)', '逐项中位: ISO(oracle) / (deploy)', '判读'))
verdicts = {}
for key, row in res.items():
    if not row:
        continue
    f9v = row.get('f9')
    if f9v is None:
        continue
    cand = {'ISO_oracle': row['ISO_oracle'], 'ISO_deploy': row['ISO_deploy'],
            'ISO_oracle_med': row['ISO_oracle_med'], 'ISO_deploy_med': row['ISO_deploy_med']}
    rel = {k: (abs(v - f9v) / f9v if (v is not None and f9v) else None) for k, v in cand.items()}
    hits = [k for k, v in rel.items() if v is not None and v < 0.05]
    both_far = all(v is None or v > 0.20 for v in rel.values())
    verdicts[key] = dict(f9=f9v, computed={k: (round(v, 2) if v is not None else None)
                                          for k, v in cand.items()},
                         rel={k: (round(v, 3) if v is not None else None) for k, v in rel.items()},
                         hits=hits, no_impl=bool(both_far))
    v = ('命中 ' + '、'.join(hits)) if hits else ('**仓库内无实现**' if both_far else '无一 <5%')
    print('  %-46s %8.1f | %8.1f / %8.1f            | %8.1f / %8.1f            | %s'
          % (key, f9v, row['ISO_oracle'], row['ISO_deploy'],
             row['ISO_oracle_med'], row['ISO_deploy_med'], v))

uniq = {h for d in verdicts.values() for h in d['hits']}
# ★ 总体判读的正确条件：**每个** unit 都有命中，且**所有** unit 命中同一个"族 × 口径"。
#   （原先只判 len(uniq)==1，会把"只有 2/7 命中 ISO_oracle、另外 4 个无实现"误报成"全部命中"。）
all_hit = bool(verdicts) and all(d['hits'] for d in verdicts.values())
same = all_hit and len(uniq) == 1
n_noimpl = sum(1 for d in verdicts.values() if d['no_impl'])
print()
print('■ 总体判读：命中组合并集 = %s；逐单位命中数 = %d/%d；判为"仓库内无实现"的 unit = %d/%d'
      % (sorted(uniq) if uniq else '（空）', sum(1 for d in verdicts.values() if d['hits']),
         len(verdicts), n_noimpl, len(verdicts)))
print('  ⇒ %s' % ('**全部 unit 命中同一组合 %s** ⇒ 可把该族该口径登记为权威。' % sorted(uniq)[0] if same else
                 '**没有任何"族 × 口径"能同时对上全部 unit**（%d/%d 个 unit 两族都差 >20%%）⇒ F.9 的十行属'
                 '**可核验转录**，其口径组合在本仓库内无实现。' % (n_noimpl, len(verdicts))))

out = {
    'purpose': 'F.9 十行跨度能否由已发布记录重算（盲审 #10/#25/#28 的决定性实验）',
    'rule': '<5% 记为命中该族该口径；两族都 >20% 记为"该口径组合在仓库内无实现"',
    'inputs': {
        'det_ladder_visdrone': 'analysis/data/pod_mirror/A/det_yolo_ladder_visdrone_det.csv',
        'det_ladder_coco': 'analysis/data/pod_mirror/A/det_yolo_ladder_yolo12n.csv',
        'note': '像素预算与契约单元走 pod_mirror 下 res_ctrl__*/ 与 b2__out_*/E1.csv',
    },
    'units': verdicts,
    'verdict': ('all_units_match:%s' % sorted(uniq)[0] if same
                else 'no_single_family_and_caliber_reproduces_all_units'),
    'hit_counts': {'units_total': len(verdicts),
                   'units_with_any_hit': sum(1 for d in verdicts.values() if d['hits']),
                   'units_no_implementation': n_noimpl},
    'conclusion': ('F.9 的十行是**可核验转录**（逐行对过中文骨架 §8.10，见 f9_transcribe_check.py），'
                   '不是 pooled 口径可复算表；正文的承重排序证据已改为 M.37 的 36 单元可复算集。'),
}
OUTP = os.path.join(WORKDIR, 'f9_repro_result.json')
io.open(OUTP, 'w', encoding='utf-8', newline='\n').write(json.dumps(out, ensure_ascii=False, indent=2))
_h = hashlib.md5(io.open(OUTP, 'rb').read()).hexdigest()
io.open(OUTP + '.md5', 'w', encoding='utf-8', newline='\n').write(
    '%s  %s  (f9_repro.py)\n' % (_h, os.path.basename(OUTP)))
print()
print('已冻结 %s（md5 %s）' % (os.path.basename(OUTP), _h[:12]))
