# -*- coding: utf-8 -*-
"""机械检查：正文里**点名的**方法/数据集/架构，其**首次出现**是否带引用编号。
对应 P1 文件 §2.1 的建议，并按其 §2.1⑤ 做白名单（自造名、仅出现在参考条目标题里的名字不算）。
只读，不改任何文件。
"""
import os
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')
D = r'<WORKDIR>\PaperB'
MS = os.path.join(D, 'PaperB_英文稿_PR_20260919.md')
t = open(MS, encoding='utf-8').read()

# 正文 = References 之前
body = t.split('## References')[0]
refs = t.split('## References')[-1]

# 句子切分（保留标点）
sents = re.split(r'(?<=[.!?])\s+', body)

PATTERNS = [
    r'\b[A-Z]{2,}[a-z]*[0-9]{0,3}\b',                 # CSRNet / BL / COCO / SAHI / BBBC005
    r'\b[A-Za-z]+-?[A-Z][a-z]+-?[A-Za-z0-9]*\b',      # DM-Count / UCF-QNRF / AI-TOD / P2PNet
    r'\b[A-Z][a-z]+[0-9]+(?:\.[0-9]+)?\b',            # YOLOv12 / Qwen3 / InternVL2.5
    r'\bYOLO[a-z0-9]*n?\b',
    r'\b(?:[A-Z][a-z]+){2,}[0-9]*(?:\.[0-9]+)?\b',    # CamelCase 多段
]
# 结构性/常见词白名单（不是"被点名的方法"）
STOP = set('''Abstract Introduction Related Work Method Results Discussion Limitations References
Appendix Table Figure Fig Section Proposition Corollary QED The This These Those There Then They Their
Two Three Four Five Six Seven Eight Nine Ten One Both Each Every When Where Which While With Without
However Because Since Although Moreover Furthermore Finally First Second Third Fourth Fifth
Model Models Dataset Datasets Journal Paper Papers Author Authors Note Notes Item Items Cell Cells
Row Rows Column Columns Level Levels Arm Arms Domain Domains Unit Units Side Sides Knob Knobs
Span Spans Ratio Ratios Rate Rates Share Shares Count Counts Prediction Predictions Image Images
Item Ground Truth Answer Answers Question Questions Response Responses Prompt Prompts Contract Contracts
Base Over Under Permit Channel Tiling Blur Resolution Overlap Legibility Density Regression Detection
Classification Localization Segmentation Tracking Benchmark Baselines So Far Beyond Neural Network
English Chinese Supplementary Repository GitHub Code Data Source Sources Full Detail Details
Text Box Boxes Panel Panels Curve Curves Point Points Value Values Mean Median Mode Slope Intercept
Trace Error Errors Bias Deviation Deviations Percent Percentages Points Statistics Bootstrap Permutation
Seed Seeds Repetition Repetitions Run Runs Instance Instances Object Objects Person People
True False Total Aggregate Pooled Weighted Unweighted Canonical Primary Secondary Tertiary
Open Close Known Unknown Higher Lower Larger Smaller Greater Less Same Different Other Others
Might Must Should Would Could Can Cannot May Not No Yes All Any Some None Only Just Even Also
Given Let Put Take Make Made Set See Show Shows Shown Report Reports Reported State States Stated
Holds Holding Keeps Kept Remains Remain Applies Apply Use Used Using Uses'''.split())
STOP |= {'A', 'I', 'An', 'In', 'On', 'Of', 'To', 'Is', 'It', 'As', 'At', 'By', 'For', 'We', 'The'}

cands = {}
for si, s in enumerate(sents):
    for pat in PATTERNS:
        for m in re.finditer(pat, s):
            w = m.group(0).strip('.,;:()[]')
            if len(w) < 2 or w in STOP:
                continue
            if w.lower() in ('json', 'api', 'http', 'https', 'vlm', 'vlms', 'llm', 'llms'):
                continue
            # 必须含大写或数字，且不是纯大写常见缩写
            if not re.search(r'[A-Z]', w):
                continue
            if w not in cands:
                cands[w] = (si, s.strip())

print('候选专名 %d 个（按首次出现顺序）' % len(cands))
print()
buckets = {'cited': [], 'uncited': []}
for w, (si, s) in sorted(cands.items(), key=lambda kv: kv[1][0]):
    has_num = re.search(r'\[\d+(?:,\s*\d+)*\]', s) is not None
    (buckets['cited'] if has_num else buckets['uncited']).append((w, si, s))

print('=== 首次出现即带引用编号（含 [n]）===')
for w, si, s in buckets['cited']:
    print('   %-24s %s' % (w, s[:96]))
print()
print('=== 首次出现**不带**引用编号（%d 个）===' % len(buckets['uncited']))
for w, si, s in buckets['uncited']:
    print('   %-24s %s' % (w, s[:110]))
print()
print('=== 参考表里出现过的候选（用于区分"正文点名"与"仅参考条目")===')
for w in sorted(cands):
    if re.search(r'\b' + re.escape(w) + r'\b', refs):
        print('   %-24s 参考表命中' % w)
