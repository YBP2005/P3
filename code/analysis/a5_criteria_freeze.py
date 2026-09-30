# -*- coding: utf-8 -*-
"""A5 判据冻结（**跑之前**写死，之后不得修改）。

协议纪律（本项目与 P1 侧共用）：判据先冻结、md5 留痕、跑完不改。本脚本只做两件事：
  ① 把三条判据（P1 契约效应跨家族、P2 两类答 0 跨家族、P3 否证条件）与其**判定规则**写成一个 JSON；
  ② 计算该 JSON 的 md5 并打印，供日后核对"判定用的是不是这一版判据"。
不含任何结果；结果由 `a5_judge.py`（待写）按此 JSON 判定。
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

sys.stdout.reconfigure(encoding='utf-8')
OUT = RP('analysis', 'work', 'a5_criteria_frozen.json')

SPEC = {
    'round': 'A5-cross-family',
    'frozen_at': '2026-09-22',
    'question': ('把"答 0 是弃权、且由输出契约开关"与"两类答 0（密集域=构建特异 / 航拍域=域特异）"'
                 '从 2 个血统扩到 ≥5 个独立家族，是否仍成立？'),
    'design': {
        'domains': ['st_a', 'ucf', 'visdrone', 'aitod'],
        'pools': ['zero', 'nonzero'],
        'arms_zero': ['base', 'permit', 'channel'],
        'arms_nonzero': ['base', 'permit', 'channel'],
        'n': 150,
        'sampling': '固定种子；跨家族**同一批 item**（与 E2 同抽样器）',
        'serving': 'vLLM 0.29.0；temperature 0；max-model-len 8192；--limit-mm-per-prompt {"image":1}；'
                   'workers 8；每条请求只发图像 + 与 E2 逐字相同的契约提示词',
        'judge_instrument': 'analysis/work/19e_probe_multi.py（与 E2 **逐字同一份**）',
    },
    'criteria': {
        'P1_contract_effect_cross_family': {
            'statement': '对每个**新家族**，permit 臂把零池中"仍答 0"的比例压到 ≤5%',
            'pass_rule': '≥5/6 家族满足（含已有 Qwen3-VL / Qwen2.5-VL / InternVL2.5 三个锚点家族）',
            'fail_rule': '某家族 permit 下"仍答 0" > 30% ⇒ 记为**反例**，正文写"家族依赖"',
            'undefined_band': '5% < 比例 ≤ 30% ⇒ 记为"部分成立"，不作通过',
        },
        'P2_two_kinds_cross_family': {
            'statement': '密集域(st_a+ucf)与航拍域(visdrone+aitod)的 base 答 0 率之差 ≥30 pp',
            'pass_rule': '≥5/6 家族满足',
        },
        'P3_direction_consistency': {
            'statement': 'families 之间 permit 减零效应的**方向**一致（都为正：都把答 0 换掉）',
            'pass_rule': '方向一致家族数 ≥ 6/6 或据实报例外',
        },
    },
    'reporting': {
        'intervals': '所有比例给二项 95% CI（Wilson）',
        'pairing': '跨家族比较只在**同一 item 集合**上做（配对）',
        'exclusions': '预测值 ≥1e5 视为异常并剔除；弃答（pred 空）不计入池化 ρ',
        'no_post_hoc_change': '本 JSON 的 md5 冻结后，判定脚本只读不改；任何修改须新开一轮',
    },
    'environment_note': ('A800-SXM4-80GB（sm_80）执行；模型来自本地可控 vLLM；'
                         '新家族若只能取到 4bit 量化版，须在报告里标注"家族×构建"不可分，'
                         '并与 BF16 可得的家族分组报告（E2 已证同一权重换构建可差 90 pp）。'),
}

io.open(OUT, 'w', encoding='utf-8', newline='\n').write(json.dumps(SPEC, ensure_ascii=False, indent=2))
raw = io.open(OUT, 'rb').read()
md5 = hashlib.md5(raw).hexdigest()
print('判据已冻结：%s' % OUT)
print('  %d 字节  md5 %s' % (len(raw), md5))
print('  家族数要求：≥5/6 通过 P1、≥5/6 通过 P2；反例规则：permit 仍答 0 > 30% ⇒ 记家族依赖')
# 冻结不可变：把 md5 也写进一个旁车文件，方便日后核对（不改 JSON 本体）
io.open(OUT + '.md5', 'w', encoding='utf-8', newline='\n').write(md5 + '\n')
print('  sidecar: %s.md5' % os.path.basename(OUT))
