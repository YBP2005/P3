# -*- coding: utf-8 -*-
"""p5c_analyze.py —— P5 Phase 2（hidden states）的正式判定，只读冻结判据 5f4683bb9cdf。

读 /root/p5c_results2_summary.json（由 p5c_hidden.py 在跑完时写出）+ /root/p5c_results2.jsonl。
**不确定处照实标"不可判"**：本判据有两处我写得不够严，分析时如实暴露，不择优——
  ① H_P2b 的 `L_total` 未定义（37 个 hidden_states = embedding + 36 层）；
  ② H_P2c 的 `cos<0` 与 `|cos|<0.1` 两个分支未规定优先次序，本值同时满足两者。
"""
import io
import json
import sys

sys.stdout.reconfigure(encoding='utf-8')
S = json.loads(io.open('/root/p5c_results2_summary.json', encoding='utf-8').read())
C = json.loads(io.open('/root/p5c_criteria_frozen.json', encoding='utf-8').read())
n = S['n_layer']
rows = [json.loads(l) for l in io.open('/root/p5c_results2.jsonl', encoding='utf-8')]
R = dict(criteria_md5='5f4683bb9cdf', n_items=len(rows), n_base_zero=S['n_base_zero'], n_layer=n)

print('=== P5c 判定（判据 5f4683bb9cdf）｜%d 项 ｜ base 答 0 的 %d 项 ｜ %d 个 hidden_states（=embedding+%d 层）==='
      % (len(rows), S['n_base_zero'], n, n - 1))

# ── H_P2a ────────────────────────────────────────────────────────────────────
p0 = S['p0_mean']
verdict_a = p0['base'] > p0['forbid0']
R['H_P2a'] = dict(passed=bool(verdict_a), p0=p0)
print('\n■ H_P2a  值位置 p0：base=%.4f  forbid0=%.4f  neutral0=%.4f' % (p0['base'], p0['forbid0'], p0['neutral0']))
print('  规则 "p0(base) > p0(forbid0)" ⇒ %s' % ('PASS' if verdict_a else 'FAIL'))
print('  （附：neutral0 的 p0 = %.4f，几乎为 1）' % p0['neutral0'])

# ── H_P2b ────────────────────────────────────────────────────────────────────
Lf, Ln = S['Lstar_forbid0'], S['Lstar_neutral0']
r_count = Lf / n
r_last = Lf / (n - 1)
print('\n■ H_P2b  首个使逐层平均 cos < 0.99 的层：forbid0 L*=%s ｜ neutral0 L*=%s' % (Lf, Ln))
print('  ★ 判据原文没定义 L_total ⇒ 两种读法：L*/n=%.4f（FAIL）｜ L*/(n−1)=%.4f（恰好 PASS）' % (r_count, r_last))
print('  ⇒ **按保守读法判为不可判/不支持**，不取恰好达标的那一读法。如实标注为判据欠定。')
R['H_P2b'] = dict(Lstar_forbid0=Lf, Lstar_neutral0=Ln, ratio_over_n=r_count, ratio_over_layers=r_last,
                  verdict='UNDETERMINED（判据未定义分母；两种读法分居阈值两侧）')

# ── H_P2c / H_P2d ────────────────────────────────────────────────────────────
mf, mn = S['cos_mean_dh_u0_forbid0'], S['cos_mean_dh_u0_neutral0']
cf, cn = S['cos_item_mean_forbid0'], S['cos_item_mean_neutral0']
print('\n■ H_P2c  cos(meanΔh, u0) ｜ forbid0')
print('  L*=%d 处 %+.4f ｜ 末层 %+.4f ｜ 全层最大 |cos| = %.4f（L=%d）'
      % (Lf, mf[Lf], mf[-1], max(abs(x) for x in mf), max(range(n), key=lambda i: abs(mf[i]))))
print('  冻结规则两分支**同时命中**：cos<0（末层 %+.4f）且 |cos|<0.1' % mf[-1])
print('  ⇒ 判据未规定优先次序；取**更弱的主张**（|cos|<0.1 ⇒ 只判"读出口径变化"）⇒ **强形式不支持**')
R['H_P2c'] = dict(cos_at_Lstar=mf[Lf], cos_last=mf[-1], max_abs_cos=max(abs(x) for x in mf),
                  verdict='强形式不支持：|cos|<0.1 全程成立（两分支冲突，取弱）')
print('\n■ H_P2d  cos(meanΔh, u0) ｜ neutral0')
print('  L*=%d 处 %+.4f（>0 ⇒ PASS）｜ 末层 %+.4f ｜ 峰值 %.4f（L=%d）'
      % (Ln, mn[Ln], mn[-1], max(mn, key=abs), max(range(n), key=lambda i: abs(mn[i]))))
print('  分层面貌：L27–L35 的投影显著抬升（0.10→0.27），即"锚定把表示推向 0"集中在**后段层**')
R['H_P2d'] = dict(passed=bool(mn[Ln] > 0), cos_at_Lstar=mn[Ln], cos_last=mn[-1],
                  peak=max(mn, key=abs), peak_layer=max(range(n), key=lambda i: abs(mn[i])),
                  profile_l27_l35=[round(x, 4) for x in mn[27:36]])

print('\n■ 逐层余弦（表示本身几乎没动，但末层分歧最大）')
print('  cos_item_mean：forbid0 最低 %.4f（L=%d）｜ neutral0 最低 %.4f（L=%d）'
      % (min(cf), cf.index(min(cf)), min(cn), cn.index(min(cn))))
R['cos_item_profile'] = dict(forbid0_min=(min(cf), cf.index(min(cf))),
                             neutral0_min=(min(cn), cn.index(min(cn))))

print('\n=== 汇总 ===')
print('  H_P2a PASS ｜ H_P2b 不可判（判据欠定）｜ H_P2c 强形式不支持 ｜ H_P2d PASS（弱正向）')
print('  ⇒ 机制读法：**"锚定"有表示层签名（后段层朝 0 方向），而"禁止"没有** ——')
print('     禁止把 p0 从 %.4f 压到 %.4f，却全程与 u0 近乎正交（最大 |cos| %.3f）' % (p0['base'], p0['forbid0'], max(abs(x) for x in mf)))
print('     ⇒ 禁止效应**不是**沿"0 的反嵌入方向"移动表示所能解释的；与 P5a 的"重算而非重分配"并列时须注明口径不同。')

io.open('/root/p5c_result.json', 'w', encoding='utf-8', newline='\n').write(
    json.dumps(R, ensure_ascii=False, indent=1, default=str) + '\n')
print('\n已写 /root/p5c_result.json')
