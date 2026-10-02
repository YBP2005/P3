#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""p2e_analyze.py —— 出 §M.43 缺的**两行**，并与 §F.2 / §M.43 的印值对照。

输入（都在 out/ 或既有作者树）：
  out/p2e_detector_ladder.csv      detector 半（列同既有 VisDrone ladder）
  out/p2e_density_ladder.csv       density 半 · 官方 DM-Count（列同既有 CSRNet ladder）
  analysis/data/pod_mirror/A/csrsta_ladder_st_a.csv   density 半 · CSRNet（零调用交叉核对支）
输出：
  out/p2e_rows.json   两行的 span 与逐档 dev，加上 §M.43 四行印值，以及六 knob 排序的 Spearman
  out/p2e_verdict.md  人读版

判据见 `p2e_criteria_frozen.json` 的 `criteria`：同向、同量级、两支口径方向一致；不过就如实报"未过"。
"""
import io
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from p2e_common import OUT, criteria, dev, fnum, level_devs_pooled, load_csv, spearman, span_of  # noqa: E402

CSRSTA = os.environ.get('P2E_CSRSTA') or '/root/p3r8_p2e/ref/csrsta_ladder_st_a.csv'
M43_PRINTED = {'output_contract': 343.55, 'prompt_family': 1561.94, 'tiling': 14.56, 'pixel_budget': 31.65}
F2_PRINTED = {'detector': (30.0, 90.0), 'density': (20.1, 34.3)}


def from_ladder(path, level_cols, pred_col, gt_col='gt', item_col='item'):
    """level_cols = [列名...]（多列联合成一个档位标签）→ {label: {item:(gt,pred)}}"""
    out = {}
    for r in load_csv(path):
        g, p = fnum(r.get(gt_col)), fnum(r.get(pred_col))
        if g is None or p is None or g <= 0:
            continue
        lab = '|'.join(str(r.get(c)).strip() for c in level_cols)
        out.setdefault(lab, {})[str(r.get(item_col)).strip()] = (g, p)
    return out


def row_of(by_level, name):
    r = level_devs_pooled(by_level)
    if not r:
        return None
    labels, vals, ns = r
    return {'knob': name, 'levels': labels, 'devs': [round(v, 2) for v in vals],
            'span': round(span_of(vals), 2), 'n_per_level': ns}


def main():
    C = criteria()
    os.makedirs(OUT, exist_ok=True)
    rows = {}
    det = os.path.join(OUT, 'p2e_detector_ladder.csv')
    den = os.path.join(OUT, 'p2e_density_ladder.csv')

    if os.path.exists(det):
        # ★ 不要把不同 τ 的行按 imgsz 混在一起池化（那会把 n_det_person 在各 τ 上相加，得到 dev≈−100% 的伪行）。
        #   主档 = τ 固定 0.25、按 imgsz 分档；τ 网格另作极值报告。
        d25 = {}
        for r in load_csv(det):
            if abs(fnum(r['tau']) - 0.25) < 1e-9:
                d25.setdefault(str(r['imgsz']), {})[str(r['item'])] = (fnum(r['gt']), fnum(r['n_det_person']))
        if d25:
            rows['detector_primary_tau0.25'] = row_of(d25, 'detector·tau=0.25/whole')
    if os.path.exists(den):
        bm = from_ladder(den, ['protocol', 'value'], 'pred')
        m = {k: v for k, v in bm.items() if k.startswith('mult|') and float(k.split('|')[1]) <= 1.5}
        rows['density_official_dmcount'] = row_of(m, 'density·official DM-Count/st_a')
    if os.path.exists(CSRSTA):
        cs = from_ladder(CSRSTA, ['protocol', 'value'], 'pred')
        cm = {k: v for k, v in cs.items() if k.startswith('mult|') and float(k.split('|')[1]) <= 1.5}
        rows['density_csrnet_crosscheck'] = row_of(cm, 'density·CSRNet/st_a（零调用交叉核对）')

    print('== 两行（五档，span = max−min）==')
    for k, v in rows.items():
        print('   %-34s span=%-10s levels=%s' % (k, v['span'] if v else None, v['devs'] if v else None))

    # 判据
    verdict = {}
    d = rows.get('detector_primary_tau0.25') or rows.get('detector')
    if d:
        lo, hi = F2_PRINTED['detector']
        verdict['C2-span-detector'] = bool(lo <= abs(d['span']) <= hi * 1.5)
    dd = rows.get('density_official_dmcount')
    if dd:
        # ★ 口径提醒：F.2 的 20.1–34.3 pp 是**isotonic 校准后**的 per-(knob×domain) 单元跨度（F.9），
        #   而本行是**未校准的池化**跨度（与 §M.43 其余四行同口径）⇒ 两者不可直接比。
        #   故这里**不**对 F.2 那条带做 pass/fail，只登记"待同口径校准后再比"。
        verdict['C3-span-density'] = {'uncalibrated_span': dd['span'],
                                      'caliber_note': '与 F.2 的 20.1–34.3 pp（isotonic 校准）不可直接比；'
                                                      '本行的主用途是进入六 knob 排序（与 §M.43 四行同口径）'}
    cc = rows.get('density_csrnet_crosscheck')
    if dd and cc:
        # ★ C4 不能用 span 的符号比（span = max−min 恒为正，那样比必然"同向"）。
        #   要比的是**两支在各档上的逐档 dev 走向**：用 Spearman 与"同号档数"两个量。
        n = min(len(dd['devs']), len(cc['devs']))
        sp = spearman(dd['devs'][:n], cc['devs'][:n])
        same_sign = sum(1 for i in range(n) if dd['devs'][i] * cc['devs'][i] > 0)
        verdict['C4-caliber-same-direction'] = {
            'spearman_across_levels': round(sp, 3) if sp is not None else None,
            'same_sign_levels': '%d/%d' % (same_sign, n),
            'pass': bool(sp is not None and sp > 0 and same_sign == n),
            'note': '两支同向要求逐档 dev 的 Spearman>0 且每档同号；只用 span 符号比是错的（恒正）'}

    # 六 knob 排序（M.43 四行印值 + 本两行）
    names = ['output_contract', 'prompt_family', 'tiling', 'pixel_budget']
    spans = [M43_PRINTED[n] for n in names]
    if d:
        names.append('detector'); spans.append(abs(d['span']))
    if dd:
        names.append('density'); spans.append(abs(dd['span']))
    order = sorted(range(len(names)), key=lambda i: spans[i])
    print('\n== 六 knob 升序（本两行为实测，其余为 §M.43 印值）==')
    for i in order:
        print('   %-16s %10.2f pp' % (names[i], spans[i]))
    # ★ C5 基准必须**显式给出**：先前写成 spearman(spans, sorted(spans)) 等于拿"自身排序"当基准，
    #   与"已发表序"无关（三种算法给出 −0.83 / −0.66 / +0.2 三个数，就是因为基准没定死）。
    #   已发表序取 §F.2 各 knob 池化跨度的**中点**升序：
    #     budget 4.0–14.6 (9.3) < tiling 1.9–28.6 (15.3) < density 20.1–34.3 (27.2)
    #     < contract 26.8–53.7 (40.3) < detector 30.0–90.0 (60.0) < family 25–2008 (1016)
    PUBLISHED = ['pixel_budget', 'tiling', 'density', 'output_contract', 'detector', 'prompt_family']
    obs_rank = {names[i]: r + 1 for r, i in enumerate(order)}
    pub_rank = {n: r + 1 for r, n in enumerate(PUBLISHED)}
    common = [n for n in names if n in pub_rank]
    xs = [obs_rank[n] for n in common]
    ys = [pub_rank[n] for n in common]
    rho = spearman(xs, ys)
    swapped = [n for n in common if obs_rank[n] != pub_rank[n]]
    verdict['C5-ordering'] = {
        'observed_ascending': [names[i] for i in order],
        'published_ascending': PUBLISHED,
        'spearman_vs_published': round(rho, 3) if rho is not None else None,
        'knobs_off_their_published_rank': swapped,
        'pass': bool(rho is not None and rho >= 0.9),
        'note': '基准 = §F.2 中点的升序（显式写死）；不是"自身排序"'}
    print('   对已发表序 Spearman = %s ｜ 位置不同的 knob = %s'
          % (verdict['C5-ordering']['spearman_vs_published'], swapped))

    out = {'criteria_md5': None, 'rows': rows, 'verdict': verdict,
           'm43_printed': M43_PRINTED, 'f2_printed': F2_PRINTED,
           'caliber_red_lines': C['caliber_red_lines']}
    with io.open(os.path.join(OUT, 'p2e_rows.json'), 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    with io.open(os.path.join(OUT, 'p2e_verdict.md'), 'w', encoding='utf-8') as f:
        f.write('# P2-E 判定（detector + density 两行）\n\n')
        for k, v in rows.items():
            f.write('* **%s**：span **%s pp** ｜ levels %s ｜ 每档 n %s\n'
                    % (k, v['span'] if v else 'n/a', v['devs'] if v else '-',
                       v.get('n_per_level') if v else '-'))
        f.write('\n## 判据\n\n')
        for k, v in verdict.items():
            f.write('* %s：`%s`\n' % (k, v))
        f.write('\n## 口径红线（必须随结果一起报）\n\n')
        for x in C['caliber_red_lines']:
            f.write('* %s\n' % x)
    print('\n已写 out/p2e_rows.json 与 out/p2e_verdict.md')
    print('P2E_ANALYZE_DONE')
    return 0


if __name__ == '__main__':
    sys.exit(main())
