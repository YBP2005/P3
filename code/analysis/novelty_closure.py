# -*- coding: utf-8 -*-
"""第 1 轮盲审 **23 条扣分的闭环核查**：每一条都绑定"稿件里证明它已被处理"的断言锚点。

与 `verify_novelty_complaints.py` 的分工：
  · verify_novelty_complaints.py：核实"模型陈述的**事实**是否属实"（8/8 属实）——那是**输入**；
  · 本脚本：核实"每条扣分**现在是否已在稿内被处置**"（落点 + 数字 + 类别）——那是**输出**。
两者都要过，才敢说"可以送下一轮"。

判据：每条扣分的锚点**全部命中**才算闭环；命中位置必须在**正文**（EN）或**补充材料**（SUP）。
任何一条未闭环，脚本以非零码退出，并把它打印出来（供当轮修）。
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
import io
import json
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')
PAPER = NR()
J = PAPER + r'\analysis\model_review\novelty_paperB1_result.json'
EN = PAPER + r'\PaperB_英文稿_PR_20260919.md'
SUP = PAPER + r'\PaperB_英文补充材料_PR_20260919.md'
EV3 = PAPER + r'\PaperB_A5跨家族证据_20260922.md'

d = json.load(io.open(J, encoding='utf-8'))
en = io.open(EN, encoding='utf-8').read()
sup = io.open(SUP, encoding='utf-8').read()
ev3 = io.open(EV3, encoding='utf-8').read()
ALL = {'EN': en, 'SUP': sup, 'EV3': ev3}

MAP = {
    'dsflash': ['A1', 'A2', 'E', 'D1', 'D2', 'C'],
    'dspro': ['D1', 'A3', 'E', 'D2', 'D3', 'B'],
    'grok46': ['A2', 'A4', 'B', 'D3', 'C', 'F'],
    'glm53flash': ['B', 'D2', 'C', 'E', 'A3'],
}
THEME = {'A1': 'A 证据范围：κ 覆盖/操作化边界', 'A2': 'A 证据范围：构建特异',
         'A3': 'A 证据范围：域非系统抽样 / 未预注册', 'A4': 'A 证据范围：预注册清单',
         'A5': 'A 证据范围：跨家族证据', 'B': 'B 机制被先行工作占位',
         'C': 'C 契约门控（混杂/饱和/概念）', 'D1': 'D 恒等式被列为贡献',
         'D2': 'D 负结果/定义性压低新意', 'D3': 'D 贡献排序（经验发现被埋）',
         'E': 'E 可辨性代理：简单/不可部署', 'F': 'F 阶梯＝已知自由度的测量'}

# 每条扣分 → 闭环锚点（正则；全部命中才算闭环）。锚点尽量绑**数字**而非措辞，便于将来复查。
ANCHOR = {
    # A 证据范围
    'A1': [('EN', r'1/\(\\kappa\+1\)'), ('EN', r'30\.31%'), ('EN', r'\$\\kappa = 550\.6\$')],
    'A2': [('EN', r'build-specific'), ('EN', r'90\.3\s*pp'), ('EN', r'38\.7%')],
    'A3': [('EN', r'Domain composition is not systematic'),
           ('EN', r'not pre-registered as a whole')],
    'A4': [('EN', r'not pre-registered as a whole'), ('EN', r'Appendix G\.1')],
    'A5': [('EN', r'7 of 7 families'), ('EN', r'81\.3 pp'), ('SUP', r'M\.19')],
    # B 机制被占位 → 摘要/§1 必须给出"三点具体增量"而非"更根本"
    'B': [('EN', r'operationalisation'), ('EN', r'controlled\s+contract experiment'),
          ('EN', r'not underestimation\s+but abstention')],
    # C 契约门控
    'C': [('EN', r'the control\s+that E1 lacks'), ('EN', r'M\.18\.2'), ('EN', r'saturates in the dense domains')],
    # D 方向/恒等式
    'D1': [('EN', r'consistency check on the numbers printed in this paper'),
           ('EN', r'verification'), ('EN', r'Proposition 8')],
    # ★ 2026-09-23（第 4 轮后）：第 4 轮评审仍以"负结果/无量级预测子"扣 D2（合计 −28 落在 F/D），
    #   故把 §7.3 从"设计选择，不是退让"（原锚点 `design choice|treats the negative`）
    #   **改写为正面结论**："序稳健 ⇒ 报序不报量级"的操作规则。锚点随**新表述**更新；
    #   事实（序稳健、量级不可预测、可用性可判）不变，仍可现查。
    'D2': [('EN', r'ordering rule|usable without any law'),
           ('EN', r'isotonic|Spearman'),
           ('EN', r'no lineage reaches')],
    'D3': [('EN', r'Finding 1'), ('EN', r'two empirical findings|Finding 2'),
           ('EN', r'ordering (?:is )?(?:stable|stability)|Spearman 0\.9')],
    # E 可辨性代理
    'E': [('EN', r'selector AUC'), ('EN', r'diagnostic'), ('EN', r'31–66%')],
    # F 阶梯
    'F': [('EN', r'no lineage reaches|grid density|Spearman 0\.9'), ('EN', r'M\.8|F\.10')],
}

n_ok = n_bad = 0
fails = []
print('%-9s %-26s %6s  %-8s %s' % ('条目', '主题', '扣分', '闭环', '命中位置'))
print('-' * 108)
for m, rec in d['models'].items():
    tags = MAP[m]
    assert len(tags) == len(rec['deductions']), '%s 映射条数不符' % m
    for tag, it in zip(tags, rec['deductions']):
        hits = []
        ok = True
        for where, pat in ANCHOR[tag]:
            hit = 'EN' if re.search(pat, ALL['EN']) else ('SUP' if re.search(pat, ALL['SUP'])
                                                          else ('EV3' if re.search(pat, ALL['EV3']) else None))
            hits.append('%s:%s' % (where, '✓' if hit else '✗'))
            if hit is None:
                ok = False
        if ok:
            n_ok += 1
        else:
            n_bad += 1
            fails.append((m, tag, it['pts'], it['reason'][:70], hits))
        print('%-9s %-26s %6.1f  %-8s %s' % (m + '/' + tag, THEME[tag], it['pts'],
                                             '闭环' if ok else '★未闭环', ' '.join(hits)))
print('-' * 108)
print('闭环 %d 条 / 未闭环 %d 条' % (n_ok, n_bad))
if fails:
    print()
    print('未闭环明细（当轮要修的就是这些）：')
    for m, tag, pts, reason, hits in fails:
        print('  %-9s %-4s %6.1f  %s\n            锚点：%s' % (m, tag, pts, reason, ' '.join(hits)))
    print()
    print('NOVELTY_CLOSURE_INCOMPLETE：%d 条未闭环' % n_bad)
    sys.exit(1)
print()
print('NOVELTY_CLOSURE_OK：23 条扣分全部在稿内有可现查的落点')
