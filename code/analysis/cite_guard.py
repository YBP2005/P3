# -*- coding: utf-8 -*-
"""守卫：**凡正文点名的「方法 / 数据集 / 基线架构 / 被测模型」，首次出现处必须带引用编号。**
（对应 P1 文件 §2.1 的机械检查；白名单按 §2.1⑤：自造名与"仅出现在参考条目标题里"的名字不算。）
另修一处遗留：line 238 的 "PseCo 2311.12386" 张冠李戴（2311.12386 是 [19]）。
只读检查 + 一处定点修正；一次事务写一次盘、幂等。
"""
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')
MS = r'<WORKDIR>\PaperB\PaperB_英文稿_PR_20260919.md'
t = open(MS, encoding='utf-8').read()

# ---------- 定点修：(2605.10887; PseCo 2311.12386) → ([18]; [19]) ----------
if 'PseCo 2311.12386' in t:
    t = t.replace('(2605.10887; PseCo 2311.12386)', '([18]; [19])')
    open(MS, 'w', encoding='utf-8', newline='\n').write(t)
    print('已修：PseCo 张冠李戴 → ([18]; [19])')
else:
    print('PseCo 遗留：无（已修）')

body = t.split('## References')[0]

# ---------- 必须带编号的实体（正文点名者）----------
MUST = ['DM-Count', 'P2PNet', 'CSRNet', 'ShanghaiTech', 'UCF-QNRF', 'VisDrone', 'AI-TOD',
        'SFCHD', 'CountBench', 'TallyQA', 'FSC-147', 'YOLOv12n', "Faster R-CNN", 'RetinaNet',
        'BBBC005', 'Qwen3-VL', 'Qwen2.5-VL', 'InternVL2.5', 'AWQ', 'COCO',
        'SAHI', 'CountQA', 'PushupBench', 'CAPTURe', 'PairTally', 'NumerosityVLM', 'VLMCountBench']
# 说明：'BL' 太短（易与其它词碰撞）→ 用 'BL,' / 'BL ' 形式单列检查
EXTRA = [re.compile(r'\bBL\b')]

sents = re.split(r'(?<=[.!?])\s+', body)
fails = []
print()
print('%-16s %-5s %s' % ('entity', 'ok', 'first-mention sentence'))
for e in MUST:
    idx = body.find(e)
    if idx < 0:
        print('%-16s %-5s %s' % (e, '—', '正文未出现（不需引用）'))
        continue
    si = next(i for i, s in enumerate(sents) if e in s)
    s = sents[si]
    ok = re.search(r'\[\d+(?:\s*,\s*\d+)*\]', s) is not None
    print('%-16s %-5s %s' % (e, 'ok' if ok else '**缺**', ' '.join(s.split())[:88]))
    if not ok:
        fails.append(e)
for pat in EXTRA:
    m = pat.search(body)
    if not m:
        continue
    si = next(i for i, s in enumerate(sents) if pat.search(s))
    s = sents[si]
    ok = re.search(r'\[\d+(?:\s*,\s*\d+)*\]', s) is not None
    print('%-16s %-5s %s' % (pat.pattern, 'ok' if ok else '**缺**', ' '.join(s.split())[:88]))
    if not ok:
        fails.append(pat.pattern)

print()
if fails:
    print('未在首次出现处给出引用编号：%s' % fails)
    sys.exit(1)
print('全部点名实体在首次出现处均带引用编号。')
