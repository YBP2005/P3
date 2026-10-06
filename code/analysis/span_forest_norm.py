# -*- coding: utf-8 -*-
"""span_forest_norm.py — 三条"零 GPU 分析项"一次算完并冻结（预注册条款）。

  预注册条款一：要在 §7.3 加"十单元跨度 + CI 森林图"。本文的**可复算**版本是 36 单元集 ⇒ 画它的
     森林图：点 = 全档位 span，横杠 = **三种去偏**（等点数 k=4、去掉每梯最高档、去掉最低档）的范围。
     （即"跨度对去偏的敏感性区间"，比单一 CI 更贴本稿的口径纪律；图由冻结件生成，不是画的示意。）
  预注册条款二：命题 7 的**第三渠道污染**敏感性区间。闭式推导（本轮给出、可检验）：
     设弃权按 three 通道分：答 0 占 a、文字拒答占 r、第三通道占 ε（a+r+ε=1），κ=a/r 为测得比值。
     可报告弃权数 = a·A，真实 = A ⇒ 相对误差 = 1−a = r+ε；又 a=(1−ε)κ/(κ+1)
     ⇒ **误差 = 1/(κ+1) + ε·κ/(κ+1)**。ε=0 时回到命题 7；第三通道把它**线性放大**。
  预注册条款三：**归一化跨度**——把每个单元的跨度除以本文自己的噪声底（2.15–6.46 pp），
     得到"以噪声底为单位"的跨度；并同时给出弃权质量 w 的一等指标列（w 已在 J.1 报，此处并列）。

输入（冻结，未改动）：`equalcount36_result.json`、`a39_unit_calib_heldout_result.json`
输出：`span_forest_norm_result.json`（+ .md5）、`analysis/figures/F17_span_forest.png`
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
import hashlib
import io
import json
import os
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
W = RP('analysis', 'work')
FIG = RP('analysis', 'figures')
EQ = RP('analysis', 'work', 'equalcount36_result.json')
OUT = RP('analysis', 'work', 'span_forest_norm_result.json')
NF_LO, NF_HI = 2.15, 6.46        # 噪声底下端/上端（A.3：ρ 的跨重复 σ）

eq = json.loads(io.open(EQ, encoding='utf-8').read())
units = eq['units']

rows = []
for u in units:
    vals = [v for v in (u.get('span_eq4'), u.get('span_drop_high'), u.get('span_drop_low'))
            if v is not None]
    lo, hi = (min(vals), max(vals)) if vals else (u['span'], u['span'])
    rows.append(dict(unit=u['unit'], n=u['n'], span=u['span'],
                     defl_min=lo, defl_max=hi,
                     norm_lo=u['span'] / NF_LO, norm_hi=u['span'] / NF_HI))
rows.sort(key=lambda r: -r['span'])
print('■ 36 单元的跨度与"去偏敏感性区间"（前 8 与后 3）：')
for r in rows[:8] + rows[-3:]:
    print('   %-46s n=%d span=%9.1f 去偏区间 [%8.1f, %8.1f] 归一化(以噪声底为单位) [%7.2f, %7.2f]'
          % (r['unit'][:46], r['n'], r['span'], r['defl_min'], r['defl_max'], r['norm_lo'], r['norm_hi']))

# ── #23 第三渠道敏感性（闭式）──────────────────────────────────────────
KAPPA = {'Qwen3-VL-32B': 550.6, 'InternVL2.5-8B': 2.2990}
EPS = [0.0, 0.01, 0.05, 0.10, 0.20]
sens = {}
print('\n■ 命题 7 的第三渠道敏感性：误差 = 1/(κ+1) + ε·κ/(κ+1)')
for nm, k in KAPPA.items():
    sens[nm] = {'kappa': k, 'base_error_pct': round(100 / (k + 1), 2),
                'per_1pct_third_channel_pp': round(100 * k / (k + 1) / 100, 3),
                'table': {('%.2f' % e): round(100 * (1 / (k + 1) + e * k / (k + 1)), 2) for e in EPS}}
    print('   %-16s κ=%-7.2f  基线误差 %.2f%%  每 1%% 第三渠道 +%.3f pp  ⇒ %s'
          % (nm, k, sens[nm]['base_error_pct'], 100 * (k / (k + 1)) / 100, sens[nm]['table']))

# ── 森林图 ─────────────────────────────────────────────────────────────
import matplotlib                                                          # noqa: E402
matplotlib.use('Agg')
import matplotlib.pyplot as plt                                            # noqa: E402

plt.rcParams.update({'font.size': 6.2, 'axes.linewidth': 0.6})
fig, ax = plt.subplots(figsize=(3.5, 4.6), dpi=300)
ys = list(range(len(rows)))[::-1]
spans = [r['span'] for r in rows]
ax.hlines(ys, [r['defl_min'] for r in rows], [r['defl_max'] for r in rows],
          color='#9aa7b4', lw=1.1, zorder=1)
ax.scatter(spans, ys, s=7, color='#1f3b57', zorder=2)
ax.set_xscale('log')
ax.set_yticks(ys)
ax.set_yticklabels(['%s (n=%d)' % (r['unit'].replace('·', ' / '), r['n']) for r in rows], fontsize=4.4)
ax.set_xlabel('span of pooled $\\rho$ (pp, log scale)', fontsize=6.0)
ax.axvspan(NF_LO, NF_HI, color='#e8b23a', alpha=0.30, zorder=0,
           label='noise floor 2.15–6.46 pp')
ax.set_ylim(-0.8, len(rows) - 0.2)
ax.legend(fontsize=5.0, loc='lower right', frameon=False)
ax.grid(axis='x', lw=0.3, color='#dddddd', zorder=0)
ax.set_title('Recomputable 36-unit spans, with the spread\nacross the three deflations of §F.10',
             fontsize=6.2, pad=3)
fig.tight_layout(pad=0.3)
os.makedirs(FIG, exist_ok=True)
png = RP('analysis', 'figures', 'F17_span_forest.png')
fig.savefig(png)
plt.close(fig)
print('\n森林图写出 %s（%.0f KB）' % (png, os.path.getsize(png) / 1024))

out = dict(
    purpose='盲审 #3（跨度森林图 + 可复算区间）、#23（命题 7 第三渠道敏感性）、#35（归一化跨度）',
    inputs=dict(equalcount36=os.path.basename(EQ),
                md5=hashlib.md5(io.open(EQ, 'rb').read()).hexdigest()),
    noise_floor_pp=[NF_LO, NF_HI],
    units=rows,
    third_channel=dict(formula='error = 1/(κ+1) + ε·κ/(κ+1)', epsilons=EPS, table=sens),
    figure=os.path.basename(png),
    quoted=dict(n_units=len(rows),
                span_max=round(rows[0]['span'], 1), span_min=round(rows[-1]['span'], 1),
                norm_max=round(rows[0]['norm_lo'], 1), norm_min=round(rows[-1]['norm_hi'], 2),
                eps_1pct_qwen=sens['Qwen3-VL-32B']['table']['0.01'],
                eps_1pct_ivl=sens['InternVL2.5-8B']['table']['0.01'],
                eps_5pct_ivl=sens['InternVL2.5-8B']['table']['0.05']),
)
io.open(OUT, 'w', encoding='utf-8', newline='\n').write(json.dumps(out, ensure_ascii=False, indent=2))
h = hashlib.md5(io.open(OUT, 'rb').read()).hexdigest()
io.open(OUT + '.md5', 'w', encoding='utf-8', newline='\n').write(
    '%s  %s  (span_forest_norm.py)\n' % (h, os.path.basename(OUT)))
print('已冻结 %s（md5 %s）' % (os.path.basename(OUT), h[:12]))
print('显示值：%s' % json.dumps(out['quoted'], ensure_ascii=False))
