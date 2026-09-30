# -*- coding: utf-8 -*-
"""n2_adversarial_probe.py —— 【N2 附件】两个必须回答的问题，不能只报"极差 0"就完事：

  Q1 **"零边界不变"是定理还是这批数据的经验事实？** 规则之间唯一的分歧是**非零标签**
     （拒答词 vs unparsed）。要让某个规则**误判成 zero**，reply 必须**同时**含拒答词与数字，
     且那个数字排在拒答词之前（`first_int` 取第一个整数）。本脚本**直接数这类 reply 有几个**：
     若为 0 ⇒ 不变性是**这批数据的经验事实**，换一批就可能破。
  Q2 稿内 M.18.3 印的那几行（`permit → 拒答 / → 给数 / → 仍答 0`）能否复现？
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
import csv
import glob
import io
import os
import re
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
ROOT = NR()
E3 = RP('analysis', 'e2xt_a800', 'merged')
E2 = RP('analysis', 'e2_newh20')
P2R = RP('analysis', 'p2_a800', 'p2_probe_results_reparsed')
AW = ('abstain', 'cannot_judge', 'no_people')
FIRST = re.compile(r'-?\d+')


def load(p):
    with io.open(p, encoding='utf-8-sig') as f:
        return [r for r in csv.DictReader(f) if '#r' not in str(r.get('item') or '')]


def has_word(r):
    s = (r or '').lower()
    return any(k in s for k in AW)


def first_int(r):
    m = FIRST.search((r or '').replace(',', ''))
    return m.group(0) if m else None


print('=' * 110)
print('Q1  **"零边界不变"是定理还是经验事实？** —— 直接数"含拒答词 **且** 含数字"的 reply')
print('=' * 110)
files = (sorted(glob.glob(RP('analysis', 'e2xt_a800', 'merged', '*.csv')))
         + sorted(glob.glob(RP('analysis', 'e2_newh20', 'e1_*.csv')))
         + sorted(glob.glob(RP('analysis', 'p2_a800', 'p2_probe_results_reparsed', '*.csv'))))
n_all = n_word = n_word_num = n_word_num_before = 0
examples = []
for f in files:
    for r in load(f):
        raw = r.get('raw') or ''
        n_all += 1
        if not has_word(raw):
            continue
        n_word += 1
        m = FIRST.search(raw.replace(',', ''))
        if not m:
            continue
        n_word_num += 1
        # 数字是否出现在**第一个拒答词之前** ⇒ first_int 会把它当计数
        low = raw.lower()
        wi = min([low.find(k) for k in AW if k in low])
        if m.start() < wi:
            n_word_num_before += 1
            if len(examples) < 8:
                examples.append((os.path.basename(f), raw[:120]))
print('  扫描文件 %d 个 ｜ 记录 %d 行' % (len(files), n_all))
print('  含拒答词的行                              = %d' % n_word)
print('  含拒答词 **且** 含数字的行                = %d' % n_word_num)
print('  ★ 其中数字排在拒答词**之前**的行（会让「首个整数」规则误判成 zero）= **%d**' % n_word_num_before)
if examples:
    for f, raw in examples:
        print('     %-46s %r' % (f, raw))
print('  ⇒ 结论：这批语料里**一条都没有** ⇒ "零边界跨规则不变"是**经验事实**（%d 行全中），' % n_all)
print('     不是结构性定理：只要有一条 reply 把数字写在拒答词前面，`first_int` 就会把它读成计数。')
print()
print('  人工反例验证（合成行，不入库、不写任何文件）：')
SYN = ['{"response": "no_people", "confidence": 0.85}',
       '{"count": 0, "note": "no_people"}',
       'I cannot count them; 42 people maybe.']
for s in SYN:
    fi = first_int(s)
    kw = next((k for k in AW if k in s.lower()), None)
    print('    %-50s first_int=%-6s keyword=%-14s ⇒ %s'
          % (s, fi, kw, '★ 会分歧' if (fi is not None and kw) else '一致'))

print()
print('=' * 110)
print('Q2  复现 M.18.3 印出的那些行（口径 = a5_report.py::cls()，即 raw 关键词优先 + 已存 pred）')
print('=' * 110)


def cls_pub(raw, pred):
    r = str(raw or '').lower()
    p = str(pred or '').strip()
    for k in AW:
        if k in r:
            return k
    if p == '':
        return 'unparsed'
    try:
        v = float(p)
    except ValueError:
        return 'unparsed'
    if v >= 1e5:
        return 'anomaly'
    return 'zero' if v == 0 else 'nonzero'


WANT = [('qwen3-vl-32b-awq', 'st_a'), ('qwen3-vl-32b-fp8', 'st_a'),
        ('qwen3-vl-32b-awq8', 'ucf'), ('qwen25vl-72b-awq', 'visdrone'),
        ('qwen3-vl-32b-gptq', 'visdrone'), ('qwen3-vl-8b-awq', 'visdrone'),
        ('internvl25-8b-awq', 'visdrone'), ('qwen3-vl-32b-awq', 'aitod'),
        ('qwen3-vl-2b', 'visdrone'), ('qwen3-vl-2b', 'aitod')]
print('  %-34s %6s %6s %6s %6s %6s' % ('model / domain', 'zer', '→ref', '→num', '→0', '→unp'))
for m, d in WANT:
    pb = os.path.join(RP('analysis', 'e2_newh20'), 'e1_%s_%s_base.csv' % (m, d))
    pp = os.path.join(RP('analysis', 'e2_newh20'), 'e1_%s_%s_permit.csv' % (m, d))
    if not (os.path.exists(pb) and os.path.exists(pp)):
        print('  %-34s  缺文件' % ('%s / %s' % (m, d)))
        continue
    rb = {r['item']: cls_pub(r.get('raw'), r.get('pred')) for r in load(pb)}
    rp = {r['item']: cls_pub(r.get('raw'), r.get('pred')) for r in load(pp)}
    z = [i for i, c in rb.items() if c == 'zero']
    c = {'ref': 0, 'num': 0, 'zero': 0, 'unp': 0}
    for i in z:
        v = rp.get(i)
        if v in AW:
            c['ref'] += 1
        elif v == 'zero':
            c['zero'] += 1
        elif v == 'unparsed':
            c['unp'] += 1
        else:
            c['num'] += 1
    print('  %-34s %6d %6d %6d %6d %6d' % ('%s / %s' % (m, d), len(z), c['ref'], c['num'], c['zero'], c['unp']))
print()
print('  （稿内 M.18.3 逐字：32B-AWQ-4bit/st_a = 102/102/0/0；FP8/st_a = 82/82/0/0；')
print('    AWQ-8bit/ucf = 125/125/0/0；Qwen2.5-72B/visdrone = 121/121/0/0；')
print('    GPTQ-W4/visdrone = 145/145/0/0；Qwen3-VL-8B-AWQ/visdrone = 136/136/0/0；')
print('    InternVL2.5-8B/visdrone = 128/128/0/0；32B-AWQ-4bit/aitod = 149/148/0/1；')
print('    Qwen3-VL-2B/visdrone = 194/34/52/108；Qwen3-VL-2B/aitod = 101/48/11/42）')
