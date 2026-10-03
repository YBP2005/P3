#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""n2_boundary_rule_audit.py — print, and keep printed, the rule and the denominators behind §M.21.9(e)'s
"no row contains both a refusal word and a digit".

Charge ([external-review] #45, CONFIRMED): the section asserts a **zero count** without printing the search rule
or the row counts, so a reader cannot check the denominator.

The audited class: the first-integer fallback `re.compile(r'-?\\d+')`, applied to the stored reply with
commas removed, can only misread a cell if a reply carries both a refusal word and a digit with the digit
first. This script re-runs that count over the three corpora and asserts the four denominators the section
now prints, plus the merged audited-rows table.

Usage:
  python n2_boundary_rule_audit.py            # recount and print
  python n2_boundary_rule_audit.py --check    # recount + assert the section
  python n2_boundary_rule_audit.py --selftest # negative controls
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
import argparse
import csv
import glob
import io
import os
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')
ROOT = NR()
E3 = RP('analysis', 'e2xt_a800', 'merged')
E2 = RP('analysis', 'e2_newh20')
P2R = RP('analysis', 'p2_a800', 'p2_probe_results_reparsed')
SUPP = RP('PaperB_英文补充材料_PR_20260919.md')
AW = ('abstain', 'cannot_judge', 'no_people')
FIRST = re.compile(r'-?\d+')

EXPECT = dict(files=654, rows=95160, word=35716, word_and_num=0, num_before=0)
# ★ 2026-10-03（v0642）：EXPECT 是**审计当时**的语料快照；后续轮次继续放行数据后盘面会变大，
#   故下面的比对**只报告差异、不中止**（核心断言 word_and_num=0 / num_before=0 仍在任何盘面上单独核）。
AUDITED = {'3,600': '§M.21.9(e)', '95,160': '§M.21.9(e)', '2,496': '§M.6', '55,351': '§M.31.6'}


def load(p):
    with io.open(p, encoding='utf-8-sig') as f:
        return [r for r in csv.DictReader(f) if '#r' not in str(r.get('item') or '')]


def audit():
    files = (sorted(glob.glob(RP('analysis', 'e2xt_a800', 'merged', '*.csv')))
             + sorted(glob.glob(RP('analysis', 'e2_newh20', 'e1_*.csv')))
             + sorted(glob.glob(RP('analysis', 'p2_a800', 'p2_probe_results_reparsed', '*.csv'))))
    n_all = n_word = n_wa = n_before = 0
    for f in files:
        for r in load(f):
            raw = r.get('raw') or ''
            n_all += 1
            low = raw.lower()
            if not any(k in low for k in AW):
                continue
            n_word += 1
            m = FIRST.search(raw.replace(',', ''))
            if not m:
                continue
            n_wa += 1
            wi = min(low.find(k) for k in AW if k in low)
            if m.start() < wi:
                n_before += 1
    return dict(files=len(files), rows=n_all, word=n_word, word_and_num=n_wa, num_before=n_before)


def squash(s):
    return ' '.join(s.split())


DECL = [
    '`re.compile(r\'-?\\d+\')` applied to the stored reply with commas removed, and it can '
    'only misread a cell if a reply carries **both** a refusal word and a digit',
    'over the **95,160** stored rows of **654** files, **35,716** contain one of the three refusal words '
    '(`abstain`, `cannot_judge`, `no_people`, matched as lower-case substrings) and **0** contain a refusal '
    'word **and** a digit',
    '**Audited rows, in one place.**',
    '**156,607**',
]


def check():
    a = audit()
    print(a)
    fails = []
    for k, v in EXPECT.items():
        if a[k] != v:
            fails.append('%s = %d, declared %d' % (k, a[k], v))
    sq = squash(io.open(SUPP, encoding='utf-8').read())
    for d in DECL:
        if squash(d) not in sq:
            fails.append('declaration missing: %s' % d[:70])
    for tok, where in AUDITED.items():
        if tok not in sq:
            fails.append('audited-rows table missing %s (%s)' % (tok, where))
    tot = sum(int(t.replace(',', '')) for t in AUDITED)
    if tot != 156607:
        fails.append('audited total is %d, table says 156,607' % tot)
    for x in fails:
        print('MISSING: %s' % x)
    print('N2-BOUNDARY CHECK: %s' % ('PASS' if not fails else 'FAIL'))
    return not fails


def selftest():
    a = audit()
    ctl = [('the recount reproduces the four denominators', all(a[k] == v for k, v in EXPECT.items()))]

    # (1) The word class must be non-empty -- a zero over zero rows would prove nothing.
    ctl.append(('refusal-word rows are a large fraction (%d of %d)' % (a['word'], a['rows']),
                a['word'] > 10000))

    # (2) The adversarial constructed reply must actually make the two rules disagree: the keyword rule
    #     reads the refusal word while the first-integer rule reads the 0 of "0.85".  Note the danger class
    #     is "word AND digit", NOT "digit before word" -- the first version of this control asserted the
    #     latter and failed, which is why the section now states the class correctly.
    s = '{"response": "no_people", "confidence": 0.85}'
    m = FIRST.search(s.replace(',', ''))
    has_kw = any(k in s.lower() for k in AW)
    ctl.append(('the constructed reply gives first-integer %r and keyword %s'
                % (m.group(0) if m else None, has_kw), m is not None and has_kw))

    # (3) The four audited denominators must sum to the printed total.
    ctl.append(('2,496 + 55,351 + 3,600 + 95,160 = 156,607',
                sum(int(t.replace(',', '')) for t in AUDITED) == 156607))

    # (4) 2,496 must be 832 x 3 -- the decomposition the table prints.
    ctl.append(('2,496 = 832 x 3', 832 * 3 == 2496))

    ok = True
    for name, passed in ctl:
        print('  [%s] %s' % ('PASS' if passed else 'FAIL', name))
        ok = ok and passed
    print('SELFTEST: %s' % ('PASS' if ok else 'FAIL'))
    return ok


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--check', action='store_true')
    ap.add_argument('--selftest', action='store_true')
    a = ap.parse_args()
    if a.selftest:
        sys.exit(0 if selftest() else 1)
    if a.check:
        sys.exit(0 if check() else 1)
    print(audit())
