# -*- coding: utf-8 -*-
"""pA_freeze_criteria_v2.py —— 方案 A 判据冻结 v2（**仪器修正**版）。

为什么要 v2（诚实记录）
----------------------
v1（`pA_criteria_frozen.json`，md5 37e1fd4a25f5）跑完后发现**测量仪器本身是坏的**：

  `analysis/e2xt_a800/merged/e1_*_{permit,channel,enumAbstain,permitB,permitC,channelB}.csv`
  里 **94–100% 的行 `pred` 列是空的**，而同一行的 `raw` 列逐字写着 `{"count": "abstain"}`。
  也就是说旧解析器（19b/19e 的 `parse()`）根本不接受弃答 token，把它当解析失败丢掉了。

  逐臂审计（12595/12595/3357 行量级）：
    arm          n     pred空            raw含abstain      zero(pred列)
    base      12595    491 ( 3.9%)          0 ( 0.0%)         6253
    permit    12595  11917 (94.6%)      11826 (93.9%)          176
    channel   12595  12503 (99.3%)      12499 (99.2%)            0
    enum       3357     69 ( 2.1%)          0 ( 0.0%)         2184
    enumAbstain 3357  3204 (95.4%)       3204 (95.4%)           79
    channelB   1981   1981 (100.0%)      1981 (100.0%)            0
    permitB    1981   1981 (100.0%)      1981 (100.0%)            0
    permitC    1981   1981 (100.0%)      1981 (100.0%)            0

  后果：v1 里"零率"对出口臂其实测的是**解析失败率**，于是
    H_A1 出现 `Δzero = -25…-88 pp 但 Δabst = 0.0 pp` 这种自相矛盾的结果。
  v1 的 `pA_result.json` 因此**整体作废**（保留存档，不删除）。

v2 只改**仪器**，不改**阈值**：
  · `abstain` 从 `raw` 用 `abstain|cannot_judge|no_people` 恢复（不依赖 `pred` 列）；
  · `err` = `pred` 为空 **且** raw 不含弃答 token（真解析失败）；
  · `zero` 定义不变：`pred` 解析为数值 0；
  · H_A1/H_A2/H_A2b/H_A3/H_A4/H_A5 的阈值与判据**逐字沿用 v1**；
  · 另加（明确标注为**事后补充的描述量**，不参与判定）：
      - H_A3 的措辞对同时报 Δabst；
      - Block D：`nz__*`（非零池）作为**反向对照**单独成块，v1 误把它并进了 Block A。
  · `ivl_*` 的身份确认为 **InternVL2.5-8B-AWQ**（见 `monitor_status.md`）。
"""
import glob
import hashlib
import io
import json
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')
W = os.path.dirname(os.path.abspath(__file__))
PAPER = os.path.dirname(os.path.dirname(W))


def md5_12(p):
    return hashlib.md5(io.open(p, 'rb').read()).hexdigest()[:12]


def pin():
    groups = {
        'block_A': [os.path.join(PAPER, 'analysis', 'e2xt_a800', 'merged'),
                    os.path.join(PAPER, 'analysis', 'e2_newh20')],
        'block_D_reverse_control': [os.path.join(PAPER, 'analysis', 'e2_newh20')],
        'block_B': [os.path.join(PAPER, 'analysis', 'data', 'pod_mirror', d) for d in
                    ('b2__out_32b_blurct', 'b2__out_8b_blurct', 'ivl_blurct')],
        'block_C': [os.path.join(PAPER, 'analysis', 'data', 'pod_mirror', d) for d in
                    ('b2__out_32b_occlct', 'b2__out_8b_occlct')],
    }
    out = {}
    for tag, dirs in groups.items():
        acc = {}
        for d in dirs:
            if not os.path.isdir(d):
                continue
            fs = sorted(glob.glob(os.path.join(d, '*.csv')))
            if fs:
                acc[os.path.basename(d)] = {os.path.basename(f): md5_12(f) for f in fs}
        out[tag] = acc
    return out


INSTRUMENT = {
    'zero_rate': "pred 列解析为数值且 == 0 的行 / n",
    'abstain_rate': "raw 列匹配 r'abstain|cannot_judge|no_people'（忽略大小写）的行 / n",
    'err_rate': "pred 列为空 **且** raw 不匹配弃答 token 的行 / n",
    'why': 'e2xt_a800/merged 的出口臂 pred 列 94–100% 为空而 raw 含弃答 token；'
           '必须从 raw 恢复，否则"零率"实为"解析失败率"',
    'verified_by': 'pA_analyze.py --audit（逐臂 pred空/raw含abstain/zero 三联审计）',
}

CRIT = {
    'version': 'pA-v2',
    'supersedes': 'pA-v1',
    'supersede_reason': 'v1 的仪器把弃答解析失败计成零率，结果自相矛盾（Δzero≠−Δabst）；'
                        'v2 只修仪器，阈值逐字沿用 v1',
    'instrument': INSTRUMENT,
    'amendments': [
        'abstain 改由 raw 恢复；err = pred 空且 raw 无弃答 token',
        'nz__*（非零池）从 Block A 移出，单列 Block D 反向对照',
        'ivl_blurct/ivl_occlct 身份确认为 InternVL2.5-8B-AWQ',
        'H_A3 增设 Δabst 描述量（不参与判定）',
    ],
    'unchanged_from_v1': ['全部阈值', '全部判据文字', '证据块 B/C 的配对定义'],

    'H_A1_abstain_permit_clause': dict(
        block='A', contrast='enumAbstain - enum',
        why='两臂类型集唯一差别 = 增加 ABSTAIN_PERMIT 条款（TASK/ENUM/FORMAT 不变）',
        metric_zero='zero_rate', metric_abst='abstain_rate',
        zero_delta_max_pp=-10.0, abst_delta_min_pp=10.0, min_families=3, n_families=4,
        min_cell_n=20,
        rule='Δzero ≤ -10.0pp 在 ≥3/4 血统成立 且 Δabst ≥ +10.0pp 在 ≥3/4 血统成立'),

    'H_A2_zero_forbid_clause': dict(
        block='B', contrast='forbid0 - base', metric='zero_rate', delta_max_pp=-10.0,
        runs_required=3, rule='Δzero ≤ -10.0pp 在 3/3 run 成立'),

    'H_A2b_zero_forbid_replication': dict(
        block='C', contrast='forbid0 - base', metric='zero_rate', delta_max_pp=-10.0,
        runs_required=2, rule='Δzero ≤ -10.0pp 在 2/2 run 成立（遮挡网格复现）'),

    'H_A3_type_beats_wording': dict(
        block='A',
        wording_pairs=[['permitB', 'permit'], ['permitC', 'permit'], ['channelB', 'channel']],
        type_pairs=[['permit', 'base'], ['enumAbstain', 'enum']],
        metric='zero_rate', wording_abs_max_pp=15.0,
        rule='max|Δzero|(措辞对) ≤ 15.0pp 且 < max|Δzero|(类型对)',
        descriptive_only=['Δabst of wording pairs']),

    'H_A4_format_axis': dict(
        block='B', contrast='range - base', metric='zero_rate', abs_delta_max_pp=10.0,
        runs_required=2, descriptive_only=['choice - base'],
        rule='|Δzero| ≤ 10.0pp 在 ≥2/3 run 成立；choice 显式含 0 选项，只作描述'),

    'H_A5_association': dict(
        blocks=['A', 'B'], causal=False,
        features_expected_significant=['has_ABSTAIN_PERMIT', 'has_ZERO_FORBID'],
        features_expected_null=['has_FORMAT'],
        alpha=0.05, n_perm=10000, seed=20260925,
        loocv_models=dict(M0='intercept', M1='contract', M2='contract+enum+format', M3='all'),
        rule='契约类特征置换 p<0.05 且 M1 的 LOOCV MAE < M0 的；has_FORMAT 置换 p≥0.05'),

    'Block_D_reverse_control': dict(
        block='D', arms=['base', 'permit'], descriptive_only=True,
        expectation='非零池上 base 本就极少答 0 ⇒ Δzero 应≈0；这是零率口径的反向对照，不参与判定'),
}

RUN_ORDER = ['b2__out_32b_blurct', 'b2__out_8b_blurct', 'ivl_blurct',
             'b2__out_32b_occlct', 'b2__out_8b_occlct']
RUN_MODEL = {'b2__out_32b_blurct': 'Qwen3-VL-32B', 'b2__out_8b_blurct': 'Qwen3-VL-8B',
             'ivl_blurct': 'InternVL2.5-8B-AWQ',
             'b2__out_32b_occlct': 'Qwen3-VL-32B', 'b2__out_8b_occlct': 'Qwen3-VL-8B'}


def main():
    doc = dict(criteria=CRIT, sources=pin(), run_order=RUN_ORDER, run_model=RUN_MODEL,
               v1_md5=md5_12(os.path.join(W, 'pA_criteria_frozen.json')))
    outp = os.path.join(W, 'pA_criteria_frozen_v2.json')
    io.open(outp, 'w', encoding='utf-8', newline='\n').write(
        json.dumps(doc, ensure_ascii=False, indent=1) + '\n')
    m = md5_12(outp)
    print('已冻结 %s' % outp)
    print('  v2 判据 md5-12 = %s' % m)
    print('  所取代的 v1 md5-12 = %s' % doc['v1_md5'])
    for tag, v in doc['sources'].items():
        print('  %-24s 目录 %d 个 / 文件 %d 个' % (tag, len(v), sum(len(x) for x in v.values())))
    again = md5_12(outp)
    print('  重读 md5-12 = %s  %s' % (again, 'STABLE' if again == m else 'UNSTABLE(!!)'))
    return 0 if again == m else 1


if __name__ == '__main__':
    raise SystemExit(main())
