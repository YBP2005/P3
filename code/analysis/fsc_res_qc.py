# -*- coding: utf-8 -*-
"""fsc_res_qc.py —— E1 产物质检（**防静默失败**）。

为什么必须有：`w1_fsc_probe.py` 在臂名无效时走 `E.P[arm]` → KeyError → 被 worker 的
`except Exception` 吞掉，写成 `ERR:...` 行 ⇒ 表面上"跑完了"，实际该臂 **100% unparsed**。
所以每臂都要核：行数 = 300、unparsed 占比 < 90%、raw 列不是 ERR、item 集合与冻结样本一致。

只读，输出 `/root/w1_results/e1_qc.json`（供拉回本地核对）。任一硬条件不满足即打印 FAIL 并以非零码退出。
"""
import collections
import csv
import glob
import io
import json
import os
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
MODELS = ('InternVL3_5-8B', 'Phi-3.5-vision-instruct', 'gemma3-12b')
ARMS = ('base', 'permit', 'channel', 'enumAbstain', 'exemplar3', 'exemplar3permit')
RES = ('384', '256', '768up')
SAMPLE = '/root/fsc147/sample_test_ids.txt'


def cls_of(raw, pred):
    r = (raw or '').lower()
    for k in ('abstain', 'cannot_judge', 'no_people'):
        if k in r:
            return k
    p = (pred or '').strip()
    if p == '':
        return 'unparsed'
    try:
        return 'zero' if float(p) == 0 else 'nonzero'
    except ValueError:
        return 'unparsed'


ids0 = {x.strip() for x in io.open(SAMPLE) if x.strip()}
out, bad, hard = {}, [], []
for R in RES:
    for m in MODELS:
        for a in ARMS:
            f = '/root/w1_results/fsc_sc%s/fsc_%s_%s.csv' % ({'384': '384', '256': '256', '768up': '768'}[R],
                                                             m, a)
            if not os.path.exists(f):
                bad.append('%s|%s|%s MISSING' % (R, m, a))
                continue
            rows = list(csv.DictReader(io.open(f, encoding='utf-8-sig', errors='replace')))
            items = {str(r.get('item')) for r in rows}
            c = collections.Counter(cls_of(r.get('raw'), r.get('pred')) for r in rows)
            n = max(1, len(rows))
            err = sum(1 for r in rows if str(r.get('raw') or '').startswith('ERR'))
            rec = dict(rows=len(rows), err_rows=err,
                       zero=round(100.0 * c.get('zero', 0) / n, 1),
                       abstain=round(100.0 * c.get('abstain', 0) / n, 1),
                       cannot_judge=round(100.0 * c.get('cannot_judge', 0) / n, 1),
                       no_people=round(100.0 * c.get('no_people', 0) / n, 1),
                       nonzero=round(100.0 * c.get('nonzero', 0) / n, 1),
                       unparsed=round(100.0 * c.get('unparsed', 0) / n, 1))
            out['%s|%s|%s' % (R, m, a)] = rec
            if len(rows) != 300:
                hard.append('%s|%s|%s rows=%d ≠ 300' % (R, m, a, len(rows)))
            if rec['unparsed'] >= 90.0:
                hard.append('%s|%s|%s unparsed=%.1f%%（疑臂名无效/解析失败）' % (R, m, a, rec['unparsed']))
            if err:
                bad.append('%s|%s|%s ERR 行 %d' % (R, m, a, err))
            miss = ids0 - items
            if miss:
                bad.append('%s|%s|%s 缺 %d 个样本 item' % (R, m, a, len(miss)))

print('■ E1 质检：%d 个 (分辨率, 模型, 臂) 单元' % len(out))
print('  表头：零率 / 弃权率 / cannot_judge / no_people / unparsed')
for R in RES:
    for m in MODELS:
        cells = ['%s:%.1f/%.1f/%.1f/%s' % (a, out['%s|%s|%s' % (R, m, a)]['zero'],
                                           out['%s|%s|%s' % (R, m, a)]['abstain'],
                                           out['%s|%s|%s' % (R, m, a)]['cannot_judge'],
                                           out['%s|%s|%s' % (R, m, a)]['unparsed'])
                 for a in ARMS if '%s|%s|%s' % (R, m, a) in out]
        if cells:
            print('  %-6s %-26s %s' % (R, m, ' | '.join(cells)))
print('  硬条件违规：%d；缺件/异常：%d' % (len(hard), len(bad)))
for x in hard:
    print('   FAIL %s' % x)
for x in bad:
    print('   warn %s' % x)
io.open('/root/w1_results/e1_qc.json', 'w', encoding='utf-8', newline='\n').write(
    json.dumps(dict(cells=out, hard_fail=hard, warnings=bad), ensure_ascii=False, indent=2))
print('  已写 /root/w1_results/e1_qc.json')
sys.exit(1 if hard else 0)
