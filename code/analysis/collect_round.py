# -*- coding: utf-8 -*-
"""按 21 号文收结果：① 文件级完整性（先于内容）② 选每模型最新 ③ 抽取 8 维评分与判定。
判据先行：完整性不过的档位不参与内容判读，单列出来。
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
import glob
import io
import os
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')
# 目录可用环境变量覆盖，便于用合成评分表做**回归自测**（不污染真实产物目录）。
D = os.environ.get('REVIEW_DIR') or NR('@up1', 'analysis', 'model_review')
MODELS = ['dsflash', 'dspro', 'glm53flash', 'gemini38flash', 'grok46', 'gpt56sol', 'qwen38max', 'hy4']
if os.environ.get('REVIEW_MODELS'):
    MODELS = [x.strip() for x in os.environ['REVIEW_MODELS'].split(',') if x.strip()]
# ★ 2026-09-22：权重按**修订版** 21 号文（25 号文）：新颖 15 / 技术严谨 15 / 实验 15 /
#   公平 10 / 可复现 10 / 指标 15 / 统计 10 / 不确定度 10 = 100。档位无缝。
#   键用**短名**（是全名的子串），以兼容模型把维度名写全或写短：
#   新颖性(与贡献) / 技术严谨(性与理论正确性) / 实验充分(性与消融) /
#   评估公平(性与基准协议) / 可复现(性) / 评估指标合理(性) / 统计显著(性) / 不确定度(与误差分析)
DIMS = [('新颖性', 15), ('技术严谨', 15), ('实验充分', 15), ('评估公平', 10),
        ('可复现', 10), ('指标合理', 15), ('统计显著', 10), ('不确定度', 10)]
q = chr(0x3002)  # 。
END_OK = set('.!?' + q + '）)]}"\'*`|')

print('=' * 104)
print('① 文件级完整性（先于内容）')
print('=' * 104)
sel = {}
for m in MODELS:
    cands = [p for p in glob.glob(os.path.join(D, 'm4prime_review_%s_*.md' % m))
             if not p.endswith('.part') and '.part.' not in p]
    if not cands:
        print('%-14s **无产物**' % m); continue
    p = max(cands, key=os.path.getmtime)
    t = io.open(p, encoding='utf-8', errors='replace').read()
    body = re.sub(r'(?s)```.*?```', lambda x: x.group(0), t)   # 保留代码块，仅用于长度
    flags = []
    if len(t) < 500:
        flags.append('过短')
    zh = len(re.findall(r'[\u4e00-\u9fff]', t))
    if zh < 200:
        flags.append('正文中文过少(%d)' % zh)
    tail = t.rstrip()
    last = tail[-1] if tail else ''
    # 软收尾：`D1_RESIDUAL：none` 这类合法结尾不以标点结束，不算截断
    if last not in END_OK and not re.search(r'D1_RESIDUAL[^\n]{0,48}$', tail):
        flags.append('可能截断(末字符=%r)' % last)
    if '量化评分' not in t and '8 维' not in t and '八维' not in t:
        flags.append('**缺评分表**')
    if not re.search(r'(?m)^\|.*新颖', t):
        flags.append('评分表非表格形式')
    sel[m] = p
    print('%-14s %7d B  %5d 中文字  %s' % (m, len(t), zh, ' ok' if not flags else ' ⚠ ' + '; '.join(flags)))
print()
print('② 选中文件（每模型最新时间戳）')
for m, p in sel.items():
    print('   %-14s %s' % (m, os.path.basename(p)))

print()
print('=' * 104)
print('③ 8 维评分抽取（每维取首次出现的 x/满分）')
print('=' * 104)
rows = {}
# ★ 2026-09-22：评分表规格改为**一位小数**（权重 15/15/15/10/10/15/10/10，档位无缝）。
#   旧正则 `(\d+)\s*/\s*(\d+)` 只吃整数：遇到 `12.5/15` 会在 **`5/15`** 处匹配 ⇒ **静默错读成 5/15**；
#   `总分` 同样只取整数（`82.5` → `82`）。故全部改为接受可选小数位。
NUM = r'(\d+(?:\.\d+)?)'
for m, p in sel.items():
    t = io.open(p, encoding='utf-8', errors='replace').read()
    sc = {}
    for key, full in DIMS:
        pat = re.escape(key) + r'[^\n]{0,80}?' + NUM + r'\s*/\s*' + NUM
        mm = re.search(pat, t)
        if mm:
            sc[key] = (float(mm.group(1)), float(mm.group(2)))
    total = re.search(r'总分[^\d]{0,12}' + NUM, t)
    # ★ 专项小计：标签本身含数字（`专项小计（6+7+8）**：28.5/35`），故**不能**用 `[^\d]{0,12}` 跨过它
    #   （旧写法在真实产物上恒为 None —— 一直静默漏读）。改为在含“专项”且含 `/35` 的行里取 `/35` 前的数。
    sub = None
    for _line in t.splitlines():
        if '专项' in _line and re.search(r'/\s*35', _line):
            _c = re.findall(NUM + r'\s*/\s*35', _line)
            if _c:
                sub = float(_c[-1])
                break
    veto = re.search(r'否决项[^\n]{0,80}', t)
    dec = re.search(r'判定[^\n]{0,60}', t)

    def clean(s):
        """去掉 markdown 强调符与行首标点，便于打印判读。"""
        if not s:
            return ''
        s = re.sub(r'^\s*(?:否决项|判定)\s*[*_`]*\s*[:：]?\s*', '', s)
        return s.replace('**', '').replace('`', '').strip()

    rows[m] = dict(sc=sc, total=float(total.group(1)) if total else None,
                   sub=sub,
                   veto=clean(veto.group(0) if veto else ''),
                   dec=clean(dec.group(0) if dec else ''))
    got = sum(1 for k, _ in DIMS if k in sc)
    # 越界核对：可打分值不得超过满分（评分表规则第 1 条）
    _over = [k for k, full in DIMS if k in sc and sc[k][0] > full + 1e-9]
    # 自洽核对：8 维之和应等于总分（评分表规则第 4 条）
    _sum = round(sum(v[0] for v in sc.values()), 1) if sc else None
    _ok = ('✓' if (rows[m]['total'] is not None and _sum is not None
                   and abs(_sum - rows[m]['total']) <= 0.05) else '⚠')
    print('%-14s 抽出 %d/8 维%s | 总分 %s | 维度之和 %s %s | 专项 %s'
          % (m, got, '' if got == 8 else '  ⚠', rows[m]['total'], _sum, _ok, rows[m]['sub']))
    if _over:
        print('     ⚠ 超出满分: %s' % {k: sc[k] for k in _over})
    if got < 8:
        print('     已抽到: %s' % {k: v for k, v in sc.items()})

print()
print('=' * 104)
print('④ 对照表（未抽到的留 —；**统一一位小数**）')
print('=' * 104)


def fm(v):
    """统一按一位小数显示；None 显示 —。★ 不可用 %d：'%d' % 12.5 会静默截成 12。"""
    return '—' if v is None else '%.1f' % v


hdr = '%-14s' % 'model' + ''.join('%-11s' % k[:4] for k, _ in DIMS) + '%7s %7s' % ('总', '专项')
print(hdr)
for m in MODELS:
    if m not in rows:
        continue
    sc = rows[m]['sc']
    line = '%-14s' % m + ''.join(
        '%-11s' % ('%s/%s' % (fm(sc[k][0]), fm(sc[k][1])) if k in sc else '—') for k, _ in DIMS)
    line += '%7s %7s' % (fm(rows[m]['total']), fm(rows[m]['sub']))
    print(line)
print()
for m in MODELS:
    if m in rows:
        print('%-14s 否决: %s' % (m, rows[m]['veto'][:80] or '（未抽到）'))
        print('%-14s 判定: %s' % ('', rows[m]['dec'][:80] or '（未抽到）'))
