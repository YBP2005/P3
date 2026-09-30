# -*- coding: utf-8 -*-
"""生成合成评审产物，用于回归自测 collect_round.py 的**一位小数**解析。

★ 设计要点：故意让每个维度都带小数、且**小数位出现在旧的整数正则的匹配盲区**。
  旧正则 `新颖性[^\n]{0,80}?(\d+)\s*/\s*(\d+)` 遇到 `12.5/15`，会在 `5/15` 处匹配 ⇒ 把 12.5 读成 5；
  总分 `82.5` 会被读成 `82`。本文件用断言把这两种错读钉住。
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
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

D = RP('analysis', 'work', '_test_review_dir')
os.makedirs(D, exist_ok=True)

# 一位小数、且**全部**小数位非零（12.5/15 → 旧正则得 5/15，差异最大）
SC = [('新颖性与贡献', 12.5, 15), ('技术严谨性与理论正确性', 11.5, 15),
      ('实验充分性与消融', 13.5, 15), ('评估公平性与基准协议', 8.5, 10),
      ('可复现性', 9.5, 10), ('评估指标合理性', 14.5, 15),
      ('统计显著性', 7.5, 10), ('不确定度与误差分析', 6.5, 10)]
TOTAL = round(sum(s for _, s, _ in SC), 1)          # = 84.0
assert TOTAL == 84.0, TOTAL
SUB = round(sum(s for k, s, _ in SC if k in
                ('评估指标合理性', '统计显著性', '不确定度与误差分析')), 1)  # = 28.5
assert SUB == 28.5, SUB

body = ['# 合成评审产物（回归自测，非真实意见）', '',
        '这是一份用于校验采集脚本数值解析的**合成**产物，内容无学术含义。' * 6, '',
        '## 量化评分（8 维 / 100 分）', '',
        '| # | 维度 | 得分 | 依据（发现 + 稿内位置） |', '|---|---|---|---|']
for i, (k, s, f) in enumerate(SC, 1):
    body.append('| %d | %s | %.1f/%d | §0 合成依据 |' % (i, k, s, f))
body += ['', '- **总分**：%.1f/100' % TOTAL,
         '- **专项小计（6+7+8）**：%.1f/35' % SUB,
         '- **命中否决项**：无',
         '- **判定**：接受',
         '- **一句话理由**：合成样本。', '',
         '### 逐处扣分（每处四行；缺任一行的维度，其评分不予采信）', '']
for i, (k, s, f) in enumerate(SC, 1):
    body += ['维度 %d %s：得分 %.1f/%d   （扣 %.1f）' % (i, k, s, f, f - s),
             '  ② 原因：合成缺陷 + §0',
             '  ③ 改进：合成动作  | 类别：WRITING',
             '  ④ 改进后预期：%d.0/%d' % (f, f), '']
body += ['- **D1_RESIDUAL**：none']
txt = '\n'.join(body) + '\n'

p = RP('analysis', 'work', '_test_review_dir', 'm4prime_review_dsflash_20990101_000000.md')
io.open(p, 'w', encoding='utf-8').write(txt)
print('written %s  (%d B)' % (p, len(txt.encode('utf-8'))))
print('期望：总分 %.1f，专项 %.1f' % (TOTAL, SUB))
for k, s, f in SC:
    print('   期望 %-14s %.1f/%d' % (k[:12], s, f))
