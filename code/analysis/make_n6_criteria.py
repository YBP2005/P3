# -*- coding: utf-8 -*-
"""make_n6_criteria.py — #13「预算匹配跨度」的跑前冻结判据（[external-review] E-2）。

原话要点（`P3_任务清单…` §1.3 #13）：
  「**预算匹配跨度**：给每个旋钮**预注册同一 MAE 增幅与推理成本上限**，在**共同保留水平**上算跨度与秩」，
  并注明"零新跑的**近似版**可做（去相关 / 对数化重算）；完整版需新跑"。

★ 本件给出**方向无关**的可执行定义（不设"参考档"，以免按结果挑方向），只依赖两个预注册常数：
  误差预算 B 与成本上限 C。
"""
import io
import json
import os

W = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(W, 'n6_criteria_frozen.json')

J = {
    'round': 'n6(budget-matched span)',
    'frozen_at': '2026-09-27',
    'frozen_by': 'P3 owner (author side)',
    'requester': '[external-review] E-2（[external-review]）',
    'zero_new_data': '★ 只用已发布逐项记录（与 M.37 / n5 同一批单元构建）；零新跑。',

    'unit_set': '与 `n5_order_prereg.py` 完全相同：**逐字复制** `a39_unit_calib_heldout.py` 的构建，'
                '并同样先过**复现闸门**（36/36 单元的 span_full 与冻结件逐单元相等）。',

    'definition': {
        'level_error': 'MAE(l) = mean|pred − gt|，在该单元**公共 item 交集**上算。',
        'level_cost': 'cost(l) = 该档的推理成本代理（见 cost_proxy）；**没有成本维度的旋钮整类排除**。',
        'admissible_pair': '档对 (a,b)（a≠b）**可保留** ⇔ '
                           'max(MAE_a,MAE_b) / min(MAE_a,MAE_b) ≤ **1 + B** 且 '
                           'max(cost_a,cost_b) / min(cost_a,cost_b) ≤ **C**。',
        'budget_matched_span': 'span_BM = 该单元所有**可保留档对**上 |ρ(a) − ρ(b)| 的最大值；'
                               '若一个可保留档对都没有 ⇒ **该单元记为不可算**（不填数、不剔单元）。',
        'ordering': '按 span_BM 给单元排序，与**全档位 span**（= 已发表 M.37 口径）的排序比 Spearman。',
        'why_direction_free': '不设"参考档"、不按 ρ 的符号挑方向：只问"在**同等误差增幅与同等成本**内'
                              '允许走的两个档之间，跨度还有多大"。',
    },

    'cost_proxy_preregistered': {
        'VLM·pixel budget': 'cost = 该档的 budget（像素）；**native 档（budget = 0）按已发表处理器的'
                            '上限 1048576 记**（声明：这是上限而非该图真实像素，属已声明的近似）。',
        'VLM·tiling': "cost = 调用次数：'whole' ⇒ 1；'tileN' ⇒ N²。",
        'det·（含 tau@SZ 与全网格）': 'cost = imgsz²（同一 tau@SZ 单元内各档 imgsz 相同 ⇒ 成本恒定，'
                                      '此时只有误差预算在起作用）。',
        'density·': 'cost = 档位标签里的 value（若能解析为数）；解析不出则整类排除。',
        'VLM·output contract': '**无成本维度 ⇒ 整类排除**（它换的是指令措辞，不换算力）。',
        'VLM·prompt family': '**无成本维度 ⇒ 整类排除**（同上）。',
    },

    'constants_preregistered': {
        'primary': {'B_mae': 0.10, 'C_cost': 2.0},
        'secondary_sensitivity': {'B_mae': 0.25, 'C_cost': 4.0},
    },

    'criteria_fixed_in_advance': {
        'Q_primary': {
            'rule': '在 (B, C) = (0.10, 2.0) 下：**预算匹配后的排序与已发表排序完全一致**'
                    '（Spearman = 1.00）且**顶端旋钮不变**。',
            'fail_reads_as': '排序改变或顶端改变 ⇒ §7.3 的排序主张**在同等预算下不成立**，按实际读数改写法。',
        },
        'Q_secondary': '同一判据在 (0.25, 4.0) 下重报。',
        'Q_reported_not_gating': [
            '每个单元的 span_BM 与全档位 span 的比值（保留率）',
            '可保留档对数、不可算单元名单',
            '两个常数下的全部统计量',
        ],
    },

    'declared_in_advance': [
        '成本代理是**已声明的近似**，不是真实延迟测量（真实延迟需新跑，属"完整版"）。',
        '两个**无成本维度**的旋钮（输出契约、问法族）整类排除 ⇒ 本检的排序只在**有成本维度**的单元上比，'
        '不与 36 单元的完整排序混为一谈。',
    ],
}

io.open(OUT, 'w', encoding='utf-8', newline='\n').write(json.dumps(J, ensure_ascii=False, indent=1))
print('written %s' % OUT)
