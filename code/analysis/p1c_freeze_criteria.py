# -*- coding: utf-8 -*-
"""p1c_freeze_criteria.py —— **P1c（生态版：真实图像 × {clean, blur4, down15}）判据，跑之前冻结**。

回答 v0547 盲审 glm53flash 的原话（"在 2–3 个 E3 家族补一组 blur/tiling 对照（每家族 300 张 × 2 臂）"）
的**真实图像**版本，同时给 dspro 那条补上"真实密集图上非 Qwen 血统会不会答 0"的一面。

设计：300 张真实图像（150 ShanghaiTech-A 密集 + 150 VisDrone 航拍，确定性抽样）× 3 处理
**clean / blur4（σ=4 高斯模糊）/ down15（缩到 15% 像素，线性 ×√0.15）** × 2 臂（base/permit）
× 3 家族（Phi-3.5-Vision、LLaVA-OneVision-7B、Qwen3-VL-8B）= **5,400 次调用**。
用法：python -u p1c_freeze_criteria.py [--check]
"""
import hashlib
import io
import json
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')
W = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(W, 'p1c_criteria_frozen.json')
MD5 = OUT + '.md5'

CRIT = {
    "title": "P1c frozen criteria — legibility manipulations on real corpus images, across families",
    "frozen_on": "2026-09-25",
    "answers_review_items": [
        "glm53flash 实验充分性 −3.5（2–3 个 E3 家族的真实图像 blur/legibility 对照）",
        "dspro 实验充分性 −4.5 的另一面（真实密集图上非 Qwen 血统会不会答 0）",
        "§5.7 的'模糊而不是分辨率'在**真实图像**上的跨家族复现",
    ],
    "design": {
        "images": "150 ShanghaiTech-A（密集）+ 150 VisDrone（航拍），确定性等步长抽样",
        "treatments": {"clean": "原图", "blur4": "高斯模糊 σ=4",
                       "down15": "缩放到 15% 的像素（线性 ×0.387，LANCZOS）"},
        "arms": ["base", "permit"],
        "families": ["Phi-3.5-Vision", "LLaVA-OneVision-7B", "Qwen3-VL-8B"],
        "calls": 5400,
        "instrument": "p1_probe.py（importlib 复用冻结 19e_probe_multi.py；提示词为冻结臂，对象=人）",
        "manifests": "p1c_prep.py 生成，每处理一份 manifest（clean 7789d98a9afb｜blur4 911f5970dbf7｜down15 8f9e5d373fa0）",
    },
    "criteria": {
        "H8_blur_gate_on_real_images": {
            "statement": "在**密集**子集（st_a）上，blur4 的 base 答零率高于 clean，"
                         "且该升高在 3 个家族中 ≥2 个成立；down15 对同一批图的移动应显著更小（对照）",
            "threshold": {"families_min": 2, "of": 3, "paired": True},
        },
        "H9_contract_gate": {
            "statement": "凡 base 在该单元格产生 ≥10 个零，`permit` 的残留零率 ≤5%",
            "threshold": {"min_base_zeros": 10, "residual": 0.05},
        },
        "H10_dense_zeros_beyond_one_lineage": {
            "statement": "报告每个（家族 × 域 × 处理）的 base 零数；若任一**非 Qwen** 家族在真实密集图上"
                         "产生 ≥10 个零 ⇒ '密集域答零'不再可由单血统解释（本条只报数量，不设通过阈值）",
            "threshold": {"zeros": 10},
        },
    },
    "reporting_rules": [
        "所有比例给 Wilson 95% 区间；三种处理在**同一批 item**上配对（逐 item 比较）",
        "解析失败逐格报出并排除在池化率之外",
        "跨家族只比'处理效应是否同向'，不比绝对率",
        "结果件必须携带本判据 md5",
    ],
}


def main():
    t = json.dumps(CRIT, ensure_ascii=False, indent=2)
    if '--check' in sys.argv:
        old = io.open(OUT, encoding='utf-8', newline='').read() if os.path.exists(OUT) else ''
        same = old.strip() == t.strip()
        print('P1c 判据与本次生成逐字一致：%s' % ('✓' if same else '✗'))
        return 0 if same else 1
    io.open(OUT, 'w', encoding='utf-8', newline='\n').write(t + '\n')
    h = hashlib.md5(io.open(OUT, 'rb').read()).hexdigest()
    io.open(MD5, 'w', encoding='utf-8', newline='\n').write('%s  %s\n' % (h, os.path.basename(OUT)))
    print('已冻结 P1c 判据（md5 %s）｜规模 %d 次调用' % (h[:12], CRIT['design']['calls']))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
