# -*- coding: utf-8 -*-
"""_parse_bug.py — 确认 19e.parse() 的正则缺陷，并量化它对**既有普查产物**的影响。

要做两件事，缺一不可：
  ① 打印 parse() 源码里那条正则的**逐字符码点**，确定是哪个符号让 `"?` 退化成"可空"，
     导致值组必须直接以 `abstain` 开头（即只认 `{"count": abstain}`，不认提示词自己要求的
     `{"count": "abstain"}`）；
  ② 用**修正解析器**（语义不变，只是允许引号包住取值）重解析既有产物，统计有多少行的分类会变——
     因为这直接关系到论文里"显式弃答 N/N"这类数字是否被低估。这是投稿前必须做的完整性检查。
"""
import csv
import glob
import importlib.util
import inspect
import io
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')
spec = importlib.util.spec_from_file_location('p19e', '/root/19e_probe_multi.py')
E = importlib.util.module_from_spec(spec)
spec.loader.exec_module(E)

src = inspect.getsource(E.parse)
print('=== parse() 源码 ===')
print(src)
line = [l for l in src.splitlines() if 're.search' in l][0]
seg = line[line.find('r\''):] if "r'" in line else line[line.find('r"'):]
print('=== 正则片段逐字符码点（前 40 个）===')
print(' '.join('%s=%s' % (c, hex(ord(c))) for c in seg[:40]))

PAT_FIXED = re.compile(r'\{\s*(?:count|response|计数|数量|人数)\s*[:：]\s*"?\s*'
                       r'(\d+|abstain|cannot_judge|no_people|no_objects|unknown)', re.I)


def parse_fixed(raw):
    m = PAT_FIXED.search(raw or '')
    if m:
        v = m.group(1)
        return int(v) if v.isdigit() else v.lower()
    m = re.search(r'-?\d+', (raw or '').replace(',', ''))
    return int(m.group(0)) if m else None


print('=== 对照测试 ===')
for s in ['{"count": "abstain"}', '{"count":"abstain"}', '{"count": abstain}',
          '```json\n{\n  "count": "abstain"\n}\n```', '{"count": 42}', '{"count":"cannot_judge"}']:
    print('  %-42r 旧=%-8r 新=%r' % (s, E.parse(s), parse_fixed(s)))

print('\n=== 既有产物重解析影响（抽样：zero 池全部 + 非零池全部）===')
CH_OLD, CH_NEW, CH_SAME = {}, {}, 0
tot = 0
changed = []
for p in sorted(glob.glob('/root/w1_results/zero/*.csv') + glob.glob('/root/w1_results/nonzero/*.csv')
                + glob.glob('/root/e1_results/*.csv') + glob.glob('/root/e1_results_nonzero/*.csv')
                + glob.glob('/root/fsc_results/*.csv')):
    rows = list(csv.DictReader(io.open(p, encoding='utf-8-sig')))
    d = 0
    for r in rows:
        tot += 1
        old, new = r.get('pred', ''), parse_fixed(r.get('raw', ''))
        new = '' if new is None else str(new)
        if old.strip() != new.strip():
            d += 1
            if len(changed) < 12:
                changed.append((p.split('/')[-1], r['item'], old, new, (r.get('raw') or '')[:70]))
    if d:
        CH_OLD[p] = d
print('合计 %d 行；分类发生变化的行 %d 行（%.3f%%），涉及 %d 个文件'
      % (tot, sum(CH_OLD.values()), 100.0 * sum(CH_OLD.values()) / max(1, tot), len(CH_OLD)))
for f, d in sorted(CH_OLD.items(), key=lambda x: -x[1])[:10]:
    print('  %-56s %d 行' % (f.split('/')[-1], d))
print('样例：')
for f, it, o, n, raw in changed:
    print('  %-46s %-16s 旧=%-8r 新=%-14r raw=%s' % (f, it, o, n, raw))
