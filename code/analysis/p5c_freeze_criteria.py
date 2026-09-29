# -*- coding: utf-8 -*-
"""p5c_freeze_criteria.py —— P5 Phase 2（hidden states）的判据冻结。**必须在跑之前执行。**

要回答的问题（承接 P5a 与 §7.7「重算方向，机制仍未闭合」）：
  P5a 用 vLLM 的 top-20 logprobs 看到：`forbid0` 在**值位置**把"0"的概率质量压掉（8B −67%、32B −99.9%），
  而它最终吐出的数**几乎不出现在 base 的 top-5**（0.0% / 2.7%）⇒ 判为"**重算**而非**重分配**"。
  但那是**输出分布**层面的证据。Phase 2 往上一层问：**在残差流里，这个变化发生在哪一层、朝哪个方向？**

方法（**不走 vLLM**，用 transformers 直读层激活）：
  物品：P1 确定性网格的 **σ=8 stratum（135 张）**——零率最高的那一档。
  臂：`base` / `forbid0` / `neutral0`（neutral0 作锚定对照）。
  两遍：
    ① 贪婪生成 ≤12 token（与 P5a 同 max_tokens）；
    ② **教师强制**再前向一遍（prompt + 生成的回答），取 `output_hidden_states=True`，
       在**第一个数字 token 的前一个位置**读：各层残差流 + 该位置的 logits。
       —— 这个位置正是"**决定值 token**"的状态，三臂可比（同一序列位置语义）。

事前写死的判据：
  H_P2a **逻辑层复现**：值位置上 token `0` 的概率 p0 满足 p0(base) > p0(forbid0)。
        （若连这一条都不成立，说明 transformers 与 vLLM 的口径不可比，后续判据全部作废——先报这条。）
  H_P2b **分歧发生在哪一层**：在 base 答 0 的物品上，逐层平均 `cos(h_base[L], h_forbid0[L])`；
        记 L* = 首个使平均 cos < **0.99** 的层。预测：**L*/L_total ≥ 0.5**（分歧出现在后半深度）。
  H_P2c **变化的方向**：Δh(L*) = mean(h_forbid0(L*) − h_base(L*))；
        u0 = `lm_head` 里 token `0` 的**反嵌入行**。预测 `cos(Δh, u0) < 0`
        ⇒ 表示**朝远离 0 的方向移动**（**表示层重算**，而非只动读出）。
        若 `|cos| < 0.1` ⇒ 只能判"读出口径变化"，须照实改措辞。
  H_P2d **锚定对照**：`neutral0` 对 `base` 的同一组量；预测 `cos(Δh_neutral, u0) > 0`
        （提 0 把表示**推向** 0 方向）⇒ 与 H_P2c 构成方向相反的一对。

边界与纪律：
  * 单族（Qwen3-VL-8B，bf16 可整卡放下）；32B 不做（transformers 放不下）。
  * 图像**不做任何缩放**（与语料/P5a 一致的原生分辨率口径）。
  * 生成与解析逐字复用冻结 `19e_probe_multi.py` 的 `parse()`；提示词经 `p1d_probe.to_circles` 适配并断言尾串不变。
  * 本块是**机制探索**，不改变 P5a 的任何结论；两条证据并列写。
"""
import hashlib
import io
import json
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')
W = os.path.dirname(os.path.abspath(__file__))


def md5_12(p):
    return hashlib.md5(io.open(p, 'rb').read()).hexdigest()[:12]


CRIT = {
    'version': 'p5c-v1',
    'frozen_note': '阈值在任何激活/概率被计算之前写死；p5c_hidden.py 只读本文件。',
    'design': dict(
        family='Qwen3-VL-8B-Instruct',
        weights='/model/ModelScope/Qwen/Qwen3-VL-8B-Instruct',
        strata='P1 网格 σ=8（135 项）',
        arms=['base', 'forbid0', 'neutral0'],
        max_new_tokens=12,
        value_position='第一个数字 token 的**前一个位置**（教师强制前向里读该位置的 hidden_states 与 logits）',
        pass1='贪婪生成（与 P5a 的 max_tokens=12 对齐）',
        pass2='prompt+回答 教师强制前向，output_hidden_states=True',
        image_policy='原生分辨率，不做任何缩放（与语料/P5a 一致）',
    ),
    'H_P2a': dict(metric='p0 at value position', rule='p0(base) > p0(forbid0)',
                  gate='若不成立 ⇒ 口径不可比，H_P2b/c/d 全部作废，先报这条'),
    'H_P2b': dict(metric='layer-wise mean cos(h_base, h_forbid0) on base-zero items',
                  cos_threshold=0.99, rule='L*/L_total ≥ 0.5（分歧出现在后半深度）'),
    'H_P2c': dict(metric='cos(Δh(L*), u0)', u0='lm_head 中 token "0" 的反嵌入行',
                  rule='cos < 0 ⇒ 表示层重算；|cos| < 0.1 ⇒ 只能判读出口径变化'),
    'H_P2d': dict(metric='cos(Δh_neutral(L*), u0)', rule='> 0（锚定把表示推向 0 方向）'),
    'retraction_rules': [
        'H_P2a 不成立 ⇒ 本块整体作废，不得与 P5a 并列引用',
        'H_P2b 不成立 ⇒ 不能说"分歧在深层"，须报实测 L*',
        'H_P2c 落在 |cos|<0.1 ⇒ "重算"这一说法必须撤回，改为"读出层面变化"',
        'H_P2d 不成立 ⇒ 锚定效应的表示层签名与禁止效应同向，必须重新解释',
    ],
    'honesty': [
        '单族单权重；不外推到 32B 或其它血统',
        'σ=8 stratum 是刻意选取的高零率档，不代表全网格',
        'transformers 与 vLLM 的数值口径不完全一致 ⇒ 只做**臂间**对比，不与 P5a 的绝对值比',
    ],
}


def main():
    outp = os.path.join(W, 'p5c_criteria_frozen.json')
    io.open(outp, 'w', encoding='utf-8', newline='\n').write(
        json.dumps(CRIT, ensure_ascii=False, indent=1) + '\n')
    m = md5_12(outp)
    io.open(outp + '.md5', 'w', encoding='utf-8', newline='\n').write(
        '%s  %s\n' % (hashlib.md5(io.open(outp, 'rb').read()).hexdigest(), os.path.basename(outp)))
    print('已冻结 %s' % outp)
    print('  判据 md5-12 = %s' % m)
    print('  网格 manifest md5-12 = %s'
          % md5_12(os.path.join(os.path.dirname(os.path.dirname(W)), 'analysis', 'p1_grid', 'manifest.csv')))
    print()
    for k in ('H_P2a', 'H_P2b', 'H_P2c', 'H_P2d'):
        print('  %-8s %s' % (k, CRIT[k].get('rule')))
    again = md5_12(outp)
    print('\n  重读 md5-12 = %s  %s' % (again, 'STABLE' if again == m else 'UNSTABLE(!!)'))
    return 0 if again == m else 1


if __name__ == '__main__':
    raise SystemExit(main())
