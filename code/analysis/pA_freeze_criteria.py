# -*- coding: utf-8 -*-
"""pA_freeze_criteria.py —— 方案 A 的**判据冻结**（必须在跑分析之前执行一次）。

纪律：判据先于结果。本脚本只做两件事：
  ① 把三条证据块的数据源逐个 md5-12 钉死（防止"换一批数据再报数"）；
  ② 把判据的**机器可读阈值**写进 pA_criteria_frozen.json，
     `pA_analyze.py` 只从该文件读阈值，不得在代码里另写一套。
产物 md5 会由 pA_analyze.py 抄进结果文件，供 anchor 复核。

三条证据块（全部零 API 成本，均已测过）：
  Block A 真实语料 E1 普查：e2xt_a800/merged 与 e2_newh20，臂 base/permit/channel/
          enum/enumAbstain/locate/bestA/bestB/bestC/permitB/permitC/channelB
  Block B 受控模糊网格（675 item，同 item 配对）：data/pod_mirror/*_blurct，臂 base/forbid0/choice/range
  Block C 受控遮挡网格（160 item，同 item 配对）：data/pod_mirror/*_occlct，臂 base/forbid0
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

BLOCK_A_DIRS = [
    os.path.join(PAPER, 'analysis', 'e2xt_a800', 'merged'),
    os.path.join(PAPER, 'analysis', 'e2_newh20'),
]
BLOCK_B_DIRS = [
    os.path.join(PAPER, 'analysis', 'data', 'pod_mirror', 'b2__out_32b_blurct'),
    os.path.join(PAPER, 'analysis', 'data', 'pod_mirror', 'b2__out_8b_blurct'),
    os.path.join(PAPER, 'analysis', 'data', 'pod_mirror', 'ivl_blurct'),
]
BLOCK_C_DIRS = [
    os.path.join(PAPER, 'analysis', 'data', 'pod_mirror', 'b2__out_32b_occlct'),
    os.path.join(PAPER, 'analysis', 'data', 'pod_mirror', 'b2__out_8b_occlct'),
]

RUN_ORDER = ['b2__out_32b_blurct', 'b2__out_8b_blurct', 'ivl_blurct',
             'b2__out_32b_occlct', 'b2__out_8b_occlct']


def md5_12(p):
    return hashlib.md5(io.open(p, 'rb').read()).hexdigest()[:12]


def pin():
    out = {'block_A': {}, 'block_B': {}, 'block_C': {}}
    for tag, dirs in (('block_A', BLOCK_A_DIRS), ('block_B', BLOCK_B_DIRS), ('block_C', BLOCK_C_DIRS)):
        for d in dirs:
            fs = sorted(glob.glob(os.path.join(d, '*.csv')))
            if not fs:
                continue
            out[tag][os.path.basename(d)] = {os.path.basename(f): md5_12(f) for f in fs}
    return out


CRIT = {
    'version': 'pA-v1',
    'frozen_note': '阈值在**任何**零率/弃答率被计算之前写死；分析脚本只读本文件。',

    # ── 主判据（因果形态：最小对）────────────────────────────────────────────
    'H_A1_abstain_permit_clause': dict(
        block='A', contrast='enumAbstain - enum',
        why='两臂类型集唯一差别 = 增加 ABSTAIN_PERMIT 条款（TASK/ENUM/FORMAT 不变）',
        metric_zero='zero_rate', metric_abst='abstain_rate',
        zero_delta_max_pp=-10.0, abst_delta_min_pp=10.0, min_families=3, n_families=4,
        min_cell_n=20,
        rule='Δzero ≤ -10.0pp 在 ≥3/4 家族成立 且 Δabst ≥ +10.0pp 在 ≥3/4 家族成立'),

    'H_A2_zero_forbid_clause': dict(
        block='B', contrast='forbid0 - base',
        why='两臂唯一差别 = 增加 ZERO_FORBID 条款；同一 item 配对',
        metric='zero_rate', delta_max_pp=-10.0,
        runs_required=3, rule='Δzero ≤ -10.0pp 在 3/3 run 成立'),

    'H_A2b_zero_forbid_replication': dict(
        block='C', contrast='forbid0 - base', metric='zero_rate', delta_max_pp=-10.0,
        runs_required=2, rule='Δzero ≤ -10.0pp 在 2/2 run 成立（遮挡网格复现）'),

    'H_A3_type_beats_wording': dict(
        block='A',
        wording_pairs=[['permitB', 'permit'], ['permitC', 'permit'], ['channelB', 'channel']],
        type_pairs=[['permit', 'base'], ['enumAbstain', 'enum']],
        metric='zero_rate', wording_abs_max_pp=15.0,
        rule='max|Δzero|(措辞对) ≤ 15.0pp 且 < max|Δzero|(类型对)'),

    'H_A4_format_axis': dict(
        block='B', contrast='range - base', metric='zero_rate', abs_delta_max_pp=10.0,
        runs_required=2,
        descriptive_only=['choice - base'],
        rule='|Δzero| ≤ 10.0pp 在 ≥2/3 run 成立（range 只换输出口径，不该大幅改零率）；'
             'choice 显式含 0 选项，只作描述不作判据'),

    # ── 观测性关联（明确声明非因果）──────────────────────────────────────────
    'H_A5_association': dict(
        blocks=['A', 'B'], causal=False,
        features_expected_significant=['has_ABSTAIN_PERMIT', 'has_ZERO_FORBID'],
        features_expected_null=['has_FORMAT'],
        alpha=0.05, n_perm=10000, seed=20260925,
        loocv_models=dict(M0='intercept', M1='contract', M2='contract+enum+format', M3='all'),
        rule='契约类特征置换 p<0.05 且 M1 的 LOOCV MAE < M0 的；'
             'has_FORMAT 置换 p≥0.05；否则按 §8 诚实边界改写，不换分'),

    # ── 声明式边界（预写，不允许事后放宽）────────────────────────────────────
    'retraction_rules': [
        'H_A1 不成立 ⇒ §5.7 中"契约条款负责效应"必须撤回，改为"效应由条款组合产生，无法归因到单一条款"',
        'H_A2 不成立 ⇒ 同一撤回适用于"零值禁止"',
        'H_A3 不成立（措辞效应 ≥ 类型效应）⇒ 必须承认效应是字面敏感的，写入限制章节',
        'H_A5 中 has_FORMAT 显著 ⇒ 必须承认格式约束本身也推动弃答（与 Let Me Speak Freely 一致）',
    ],
    'honesty': [
        'H_A5 是观测性联结（臂数少、特征共线），只用于筛选，不作因果结论',
        'Block B/C 是合成网格，块内结论不得直接外推到真实语料',
        '所有 Δ 一律报 pp 与配对样本量；不做多重比较校正之外的择优',
    ],
}


def main():
    pins = pin()
    doc = dict(criteria=CRIT, sources=pins, run_order=RUN_ORDER)
    outp = os.path.join(W, 'pA_criteria_frozen.json')
    io.open(outp, 'w', encoding='utf-8', newline='\n').write(
        json.dumps(doc, ensure_ascii=False, indent=1) + '\n')
    m = md5_12(outp)
    print('已冻结 %s' % outp)
    print('  判据 md5-12 = %s' % m)
    for tag in ('block_A', 'block_B', 'block_C'):
        tot = sum(len(v) for v in pins[tag].values())
        print('  %-8s 目录 %d 个 / 文件 %d 个' % (tag, len(pins[tag]), tot))
    print('\n判据：')
    for k, v in CRIT.items():
        if k.startswith('H_'):
            print('  %-32s %s' % (k, v.get('rule', '')))
    # 冻结文件自校验：写入后立刻重读，确认 md5 稳定
    again = md5_12(outp)
    print('\n重读 md5-12 = %s  %s' % (again, 'STABLE' if again == m else 'UNSTABLE(!!)'))
    return 0 if again == m else 1


if __name__ == '__main__':
    raise SystemExit(main())
