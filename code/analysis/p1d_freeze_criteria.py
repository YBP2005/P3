# -*- coding: utf-8 -*-
"""p1d_freeze_criteria.py —— P1d（`forbid0` / `neutral0` 两臂）的判据 + 运行配置冻结。

**必须在任何结果产生之前执行一次。** 冻结两样东西：
  ① 判据阈值（分析脚本只从本文件读，不得另写一套）；
  ② 运行配置（每族显存比例 / maxlen / 端口 / 臂 / workers / 网格 manifest md5），
     使"这次是在什么条件下采的"本身可核。

背景（为什么要做 P1d）：
  * 语料侧 H_A2（`forbid0 − base`）**不成立**：5 个 run 里 4 个不达 −10 pp，且 InternVL2.5-8B-AWQ **反号 +42.8 pp**；
  * 但那个反号是**单一血统、单次运行**，且原网格（`13b_blur_contract.py`）的图**不可逐位复现**
    （种子用 `abs(hash(item))`，Python 字符串 hash 逐进程随机化）；
  * `internvl25-8b-awq` 权重**不在机器上** ⇒ 不可能"复现那个权重"。
  ⇒ P1d 换一个**可逐位复现**的网格（P1 的 675 张，逐图记 md5），并加一条**诊断臂**把
    "禁止"与"提示词里出现 0 这个 token"分开。结论若成立，只能表述为**血统类**现象，不是同权重复现。
"""
import hashlib
import io
import json
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')
W = os.path.dirname(os.path.abspath(__file__))
PAPER = os.path.dirname(os.path.dirname(W))
GRID_MANIFEST = os.path.join(PAPER, 'analysis', 'p1_grid', 'manifest.csv')


def md5_12(p):
    return hashlib.md5(io.open(p, 'rb').read()).hexdigest()[:12]


CRIT = {
    'version': 'p1d-v1',
    'frozen_note': '阈值在任何零率/弃答率被计算之前写死；p1d_analyze.py 只读本文件。',

    'design': dict(
        grid='P1 确定性网格（675 张 PNG，显式固定种子一次落盘，逐图记 md5）',
        grid_manifest_md5_12=md5_12(GRID_MANIFEST) if os.path.exists(GRID_MANIFEST) else None,
        items=675,
        arms=['base', 'forbid0', 'neutral0'],
        arms_note='base 为**同会话重跑**（与已发表 base 比可量跨会话噪声）；三臂同会话并发采集',
        families=6,
        objects='circles（合成圆点；只改对象名词，句号之后逐字节相同）',
        why_deterministic='语料侧反号所在的网格不可逐位复现，故换确定性网格；结论只能是血统类，非同权重复现',
    ),

    'H_A2p_zero_forbid_works': dict(
        contrast='forbid0 - base', metric='zero_rate', delta_max_pp=-10.0, min_families=3,
        n_families=6,
        rule='Δzero ≤ -10.0pp 在 ≥3/6 族成立 ⇒ 该条款在确定性网格上也有效',
        rationale='与语料侧 H_A2 用同一门槛，便于两个证据块直接对比',
    ),

    'H_A2rev_reversal': dict(
        contrast='forbid0 - base', metric='zero_rate', delta_min_pp=10.0,
        rule='∃ 族使 Δzero ≥ +10.0pp ⇒ 记录为"确定性网格上出现反号"',
        scope_warning='原反号权重 internvl25-8b-awq **不在机器上**；本项若成立只能表述为血统类现象，'
                      '**不得**写成"复现了语料侧那个 +42.8 pp"',
        candidate='InternVL3_5-8B（本网格上 base 零率 0%，"把零造出来"的效应最容易被看见）',
    ),

    'H_A2n_prohibition_vs_mention': dict(
        diagnostic='在 |Δzero(forbid0-base)| ≥ 10pp 的族上，比较 neutral0 - base',
        prohibition_driver_if='|Δzero(neutral0-base)| ≤ 0.5 × |Δzero(forbid0-base)|',
        mention_driver_if='|Δzero(neutral0-base)| ≥ 0.8 × |Δzero(forbid0-base)|',
        else_='混合/不可判定，按实报',
        design_note='base 不提 0；neutral0 提 0 且允许；forbid0 提 0 且禁止 ⇒ '
                    'neutral0-base 与 forbid0-neutral0 分别隔离两个因子',
    ),

    'H_N0_my_noise_floor': dict(
        contrast='fresh base - stored base（同网格、同族，跨会话）',
        metric='zero_rate', descriptive=True,
        rule='逐族报 |Δ|，并把最大值记为本栈的**跨会话**经验噪声带',
        why='CVPR 侧测的"本地为 0"是同进程/同起服；本项量的是跨会话，两者口径不同（见回件 §2）',
        same_session_note='forbid0/neutral0/base 三臂**同会话**采集 ⇒ 三者之间的对比是同会话对比',
    ),

    'H_Abst_forbid_suppresses_abstention': dict(
        contrast='forbid0 - base', metric='abstain_rate', delta_max_pp=0.0, min_families=4,
        n_families=6,
        rule='Δabst ≤ 0 在 ≥4/6 族成立（该条款要求给数，理应同时压弃答）',
    ),

    'retraction_rules': [
        'H_A2p 不成立 ⇒ 与语料侧 H_A2 一致，"禁止 0 条款有效"这一读法在两个证据块上都不成立',
        'H_A2rev 成立 ⇒ 必须写明是**血统类**现象、且与语料侧不是同一权重，禁止暗示"复现"',
        'H_A2n 落在 mention_driver_if ⇒ "禁止"不是驱动因素，正文相关措辞须改为"提及 0 本身"',
        'H_N0 若很大（>10 pp）⇒ 说明语料侧那些 ≤10 pp 的臂间差不可解释，需回查既有结论',
    ],

    'honesty': [
        '本块是合成圆点网格，结论不外推到真实语料；语料侧结论也不因本块而改变方向',
        '三臂同会话并发采集：臂与臂共享同一个服务进程，批组成可能带来末位比特差异（贪婪解码下近乎并列的 token 可翻转）；'
        'base 重跑与已发表 base 的差正是这一项的观测量',
        'families 只覆盖 P1 六族中权重在盘上的部分；若某族起服失败，按实际族数报告，不补齐、不替换',
    ],
}


def main():
    outp = os.path.join(W, 'p1d_criteria_frozen.json')
    io.open(outp, 'w', encoding='utf-8', newline='\n').write(
        json.dumps(CRIT, ensure_ascii=False, indent=1) + '\n')
    m = md5_12(outp)
    io.open(outp + '.md5', 'w', encoding='utf-8', newline='\n').write(
        '%s  %s\n' % (hashlib.md5(io.open(outp, 'rb').read()).hexdigest(), os.path.basename(outp)))
    print('已冻结 %s' % outp)
    print('  判据 md5-12 = %s' % m)
    print('  网格 manifest md5-12 = %s（675 项）' % CRIT['design']['grid_manifest_md5_12'])
    print('  提示词件 p1d_prompts.json md5-12 = %s'
          % md5_12(os.path.join(W, 'p1d_prompts.json')))
    print()
    for k, v in CRIT.items():
        if k.startswith('H_'):
            print('  %-38s %s' % (k, v.get('rule', '')))
    again = md5_12(outp)
    print('\n  重读 md5-12 = %s  %s' % (again, 'STABLE' if again == m else 'UNSTABLE(!!)'))
    return 0 if again == m else 1


if __name__ == '__main__':
    raise SystemExit(main())
