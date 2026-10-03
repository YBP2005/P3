# -*- coding: utf-8 -*-
"""p1b_freeze_criteria.py —— **P1b（模板轴）的判据，跑之前冻结**（[external-review][external-review]。

要回答的那条原话："一族内 **template × contract** 交互"。

设计：只在 P1 网格的 **σ=8 那一层**（135 项 = n∈{100,400,800} × r∈{2,4,8} × 15）做 2×2：
  * **模板**：`native`（冻结传输，无 system 消息）｜`sys`（在最前面插一条 system 消息，
    文本**逐字沿用**本项目此前那次消融用过的同一条：`You are a careful visual counting assistant.
    Follow the requested output format exactly.` ⇒ 与 M.19.8 的 `+system` 列可比）；
  * **契约**：`base` ｜ `permit`。
家族：Phi-3.5-Vision、LLaVA-OneVision-7B（两者在 native 下有零）+ Qwen3-VL-8B（锚）。
规模：3 × 2 × 2 × 135 = **1,620 次调用**（按 P1 实测吞吐，卡上约 5–10 分钟）。

用法：python -u p1b_freeze_criteria.py [--check]
"""
import hashlib
import io
import json
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')
W = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(W, 'p1b_criteria_frozen.json')
MD5 = OUT + '.md5'

CRIT = {
    "title": "P1b frozen criteria — within-family template x contract interaction at sigma=8",
    "frozen_on": "2026-09-25",
    "answers_review_items": ["grok46 实验充分性 −3.0（一族内 template × contract 交互）",
                             "同时补齐 P1 生态版的前一半（模板轴）"],
    "design": {
        "grid": "P1 的 675 张 n×r×σ 网格，**只取 σ=8 那一层**（135 项）",
        "items": 135,
        "families": ["Phi-3.5-Vision", "LLaVA-OneVision-7B", "Qwen3-VL-8B"],
        "templates": {"native": "无 system 消息（冻结传输 19e.call_img）",
                      "sys": "在最前插一条 system：'You are a careful visual counting assistant. "
                             "Follow the requested output format exactly.'（与此前消融同一句，与 M.19.8 可比）"},
        "arms": ["base", "permit"],
        "calls": 1620,
        "instrument": "p1_probe.py（importlib 复用冻结 19e_probe_multi.py，启动断言 md5）",
        "prompt_object": "circles（提示词句号之后与冻结臂逐字相同，运行时断言）",
    },
    "criteria": {
        "H5_gate_survives_template_change": {
            "statement": "对每个家族，在**两种模板下** `permit` 的残留零率都 ≤5%；满足的家族 ≥2/3 ⇒ 契约闸门不依赖模板",
            "threshold": {"residual": 0.05, "families_min": 2, "of": 3},
        },
        "H6_template_effect_quantified": {
            "statement": "逐家族报 base 答零率在两种模板下的差 Δ = rate(sys) − rate(native)，并给 Wilson 区间",
            "threshold": {"first_order_pp": 20.0,
                          "note": "|Δ| ≥20 pp ⇒ 模板是**答零率的一阶调节量**（绝对率不可跨模板比较）"},
        },
        "H7_interaction_measurable": {
            "statement": "若某家族在 sys 下 base 答零率 <20% ⇒ 该家族**没有零可供门控**，"
                         "交互在该家族**不可测**（报 NOT MEASURABLE），不得记作'无交互'",
            "threshold": {"base_zero_rate_min": 0.20},
        },
    },
    "reporting_rules": [
        "所有比例给 Wilson 95% 区间；四个格子（2 模板 × 2 臂）在同一批 item 上配对",
        "解析失败逐格报出并排除在池化率之外（`permit` 臂的散文式拒答属预期）",
        "结论只写'闸门是否仍在'与'模板把绝对率移动了多少'两件事，不做跨家族的绝对率比较",
        "结果件必须携带本判据 md5；判据一旦冻结，改动写新文件新 md5",
    ],
}


def main():
    t = json.dumps(CRIT, ensure_ascii=False, indent=2)
    if '--check' in sys.argv:
        old = io.open(OUT, encoding='utf-8', newline='').read() if os.path.exists(OUT) else ''
        same = old.strip() == t.strip()
        print('P1b 判据与本次生成逐字一致：%s' % ('✓' if same else '✗（冻结件已被改动）'))
        return 0 if same else 1
    io.open(OUT, 'w', encoding='utf-8', newline='\n').write(t + '\n')
    h = hashlib.md5(io.open(OUT, 'rb').read()).hexdigest()
    io.open(MD5, 'w', encoding='utf-8', newline='\n').write('%s  %s\n' % (h, os.path.basename(OUT)))
    print('已冻结 P1b 判据 %s（md5 %s）｜规模 %d 次调用'
          % (OUT, h[:12], CRIT['design']['calls']))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
