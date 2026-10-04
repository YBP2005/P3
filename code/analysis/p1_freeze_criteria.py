# -*- coding: utf-8 -*-
"""p1_freeze_criteria.py —— **在开机之前**把 P1 的判据与报告口径写死并冻结（md5 旁车）。

对应 [external-review]的三条需实验意见：
  * [external-review]（实验充分性）："在 2–3 个 E3 家族补一组 blur/tiling 对照（每家族 300 张 × 2 臂）"；
  * [external-review]："一族内 template × contract 交互"；
  * [external-review]："至少补 2–3 个新 family 于 dense zero pool"（用户已决定**不做**其文字替代）。

## 为什么必须先冻结
本项目已有先例：判据事后改一次，整轮结论就不可复核（见 `PaperB_[external-review]修回证据_20260924.md`
§6(s) 的"永真断言"与 §6(w) 的过度更正）。本脚本把 H1–H4、层定义、排除规则写进 JSON 并记 md5；
`p1_analyze.py` 会把该 md5 一并写进结果件，于是"这份结果是用哪套判据读的"**由产物本身携带**。

用法：
    python -u p1_freeze_criteria.py            # 写 p1_criteria_frozen.json + .md5
    python -u p1_freeze_criteria.py --check    # 只校验现有冻结件与本次生成是否逐字一致
"""
import hashlib
import io
import json
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')
W = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(W, 'p1_criteria_frozen.json')
MD5 = OUT + '.md5'

CRIT = {
    "title": "P1 frozen criteria — does legibility (blur) induce the answered zero in other lineages?",
    "frozen_on": "2026-09-25",
    "answers_review_items": [
        "预注册补充：blur/tiling 对照",
        "预注册补充：一族内 template × contract 交互",
        "预注册补充：1–2 个新 family 落进 dense zero pool；★ 用户 2026-09-25 决定不做其纯文字替代",
    ],
    "design": {
        "grid": {"n": [100, 400, 800], "r": [2, 4, 8], "sigma": [0.0, 1.0, 2.0, 4.0, 8.0],
                 "per_cell": 15, "items": 675, "canvas": 1024,
                 "images": "一次性落盘（显式固定种子，逐位可复现），各臂/各起服读同一批文件 ⇒ 真正配对",
                 "generator": "p1_prep_grid.py（绘制算法与 12_abstain_causal.py 逐字同源；种子改为显式）"},
        "families_new": ["gemma-3-12b", "Phi-3.5-Vision", "LLaVA-OneVision-7B"],
        "families_anchor": ["Qwen3-VL-8B", "Qwen3-VL-32B", "InternVL2.5-8B"],
        "arms": ["base", "permit"],
        "template_axis": {"levels": ["native", "plus_system"],
                          "note": "仅在三族 × σ=8 × 300 张生态样本上跑，报绝对率位移与契约效应是否随之变化（G3）"},
        "temperature": 0.0, "max_tokens": 64, "one_image_per_prompt": True,
    },
    "criteria": {
        "H1_mechanism_cross_lineage": {
            "statement": "在 σ=8（池化全部 n 与 r）上，3 个新家族中 ≥2 个的 base 答零率 ≥ 20%",
            "threshold": {"rate": 0.20, "families_min": 2, "of": 3, "at_sigma": 8.0},
            "verdict_if_pass": "mechanism replicates in the new lineages",
        },
        "H1b_dose_response": {
            "statement": "在每个家族内，base 答零率随 σ ∈ {0,1,2,4,8} 单调上升（Spearman ≥ 0.8）",
            "threshold": {"spearman_min": 0.8},
            "role": "次要（机制方向），不单独决定结论",
        },
        "H2_contract_gate_cross_lineage": {
            "statement": "对每题：base 答 0 的那些 item 里，permit 仍答 0 的比例 ≤ 5%（家族级）",
            "threshold": {"residual": 0.05, "counterexample_above": 0.30, "families_min": 2, "of": 3},
            "verdict_if_pass": "the contract gate extinguishes the zero in the new lineages too",
        },
        "H3_falsification": {
            "statement": "若 σ=8 上达到 ≥20% 的新家族 <2 ⇒ 记为**血统特异**，并据此收窄 §5.7 的跨家族读法",
            "role": "否证条件；成立与否都要写进论文，且不得事后改判据",
        },
        "H4_anchor_comparability": {
            "statement": "在新生成的确定性网格上，锚 `Qwen3-VL-32B` 在 **σ=8 ∧ n=800** 这一格的 base 答零率与已发表值之差 ≤ 10 pp",
            "published_reference": {"family": "Qwen3-VL-32B", "sigma": 8.0, "n": 800,
                                    "base_zero_rate": 1.00,
                                    "provenance": "补充材料 G.2 原文：'At σ = 8, n = 800 the 32B base abstention rate is 100% — every item answered zero.'（该格是已发表的唯一 σ=8 单格读数；原文其余列报的是 Δ(forbid0)，不发散为基率）"},
            "threshold": {"abs_diff_pp_max": 10.0},
            "role": "可比性闸门：若不过，说明'确定性重生成'换了刺激 ⇒ 新家族的网格数只能同批内比，不与 G.2 并表",
        },
    },
    "reporting_rules": [
        "所有比例给 Wilson 95% 区间；跨家族只比**预先写死的阈值判定**，不比绝对率的排序",
        "配对比较只在**同一 item 交集**上做（本设计里各臂读同一批 PNG ⇒ 交集即全集）",
        "解析失败：逐格计数并报出，**排除在池化率之外**；任一格解析失败 >2% 则该格加旗标",
        "pred ≥ 1e5 视为异常值（沿用普查口径），报出但不进池化",
        "逐 item CSV 必须存**完整** raw（**不截断**）：旧脚本把 raw 截到 80 字符，独立重算就无法复现解析",
        "'答零'= 解析出的计数恰为 0；'弃答'= 文本含弃答标记（两列分开报，不混为一件）",
        "结果件必须携带本判据文件的 md5；判据一旦冻结，**任何改动都写新文件新 md5**",
    ],
    "cost_estimate": {
        "controlled_grid_calls": "6 家族 × 675 × 2 臂 = 8,100",
        "template_axis_calls": "3 家族 × 300 × 2 模板 × 2 臂 = 3,600",
        "ecological_blur_tile_calls": "3 家族 × 300 × {blur σ=4, tile-2×2} × 2 臂 = 3,600",
        "total_calls": 15300,
        "wall_clock": "按 S1 实测标尺（21,600 次 / 66 分 45 秒）≈ 55–75 分钟推理 + 3–6 次起服",
    },
    "notes": [
        "生态版（300 张真实图）与受控版（675 张合成网格）**分开报**，不合并成一张表",
        "若 H3 成立：论文那句从'跨家族'改成'家族特异'（更保守、不加词）",
        "所有新数字先写进权威档（`PaperB_盲审v0527修回证据_20260924.md` §6）再引用，否则 en_check [F] 会拦",
    ],
}


def main():
    t = json.dumps(CRIT, ensure_ascii=False, indent=2)
    if '--check' in sys.argv:
        old = io.open(OUT, encoding='utf-8', newline='').read() if os.path.exists(OUT) else ''
        same = old.strip() == t.strip()
        print('判据文件与本次生成逐字一致：%s' % ('✓' if same else '✗（冻结件已被改动 ⇒ 必须写新文件新 md5）'))
        return 0 if same else 1
    io.open(OUT, 'w', encoding='utf-8', newline='\n').write(t + '\n')
    h = hashlib.md5(io.open(OUT, 'rb').read()).hexdigest()
    io.open(MD5, 'w', encoding='utf-8', newline='\n').write('%s  %s\n' % (h, os.path.basename(OUT)))
    print('已冻结判据 %s（md5 %s）' % (OUT, h[:12]))
    print('  H1 %s' % CRIT['criteria']['H1_mechanism_cross_lineage']['statement'])
    print('  H2 %s' % CRIT['criteria']['H2_contract_gate_cross_lineage']['statement'])
    print('  H3 %s' % CRIT['criteria']['H3_falsification']['statement'])
    print('  规模 %s 次调用' % CRIT['cost_estimate']['total_calls'])
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
