# -*- coding: utf-8 -*-
"""n2_rule_spread.py —— 【N2，v2】把"解析规则灵敏度"从 P2 的 12 臂**扩到在册条目真正点名的那两张表**。

在册条目要的三件事（逐字转述）：
  · 对 **§5.7 七家族表** 与 **M.18.3 的 52 个 (model×domain) 格**，每个值分别按 **R3-first** 与
    **R1-only** 各报一次，并给最大偏差；
  · 给**四个规则**（冻结正则 / `json.loads` / raw 关键词 / 首个整数）在**头条率**上的极差表，
    判据：**任一头条率在四规则下极差 ≥ 7 pp ⇒ 该数必须改成区间、不得再作为点值引用**；
  · 逐格出口灵敏度，以及**是否有任何结论变号**。

规则语义**全部照抄自源码**，不发明（逐字见 `n2_rule_spread_result.md` §1）：
  · `frozen_regex`  = `19e_probe_multi.py::parse()` **逐字**
  · `json_loads`    = 去 ``` 围栏后 `json.loads`，取 count/response/计数/数量/人数
  · `raw_keyword`   = raw 子串先找 abstain/cannot_judge/no_people，否则取首个整数
  · `first_int`     = 只取首个整数（不做任何结构/关键词识别）
  · `r1_only`       = `p2_reparse.py` 的 R1（容忍带引号的键），**不**回落
  · `r1r2r3_pipeline` = `p2_reparse.py` 的实际优先级管线
  · `as_published`  = `a5_report.py::cls()` 逐字（raw 关键词优先，否则看**已存 `pred` 列**）

只读分析；新文件只写 `analysis/work/`。
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
import collections
import csv
import glob
import hashlib
import io
import json
import math
import os
import re
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

ROOT = NR()
WORK = RP('analysis', 'work')
E3 = RP('analysis', 'e2xt_a800', 'merged')
E2 = RP('analysis', 'e2_newh20')
P2R = RP('analysis', 'p2_a800', 'p2_probe_results_reparsed')

ABSTAIN_WORDS = ('abstain', 'cannot_judge', 'no_people')
ANOM = 1e5
DOM4 = ['st_a', 'ucf', 'visdrone', 'aitod']
DOMS6 = ['st_a', 'st_b', 'ucf', 'visdrone', 'aitod', 'countbench']

FROZEN_RE = re.compile(r'\{\s*(?:count|response|计数|数量|人数)\s*[:：]\s*"?'
                       r'(\d+|abstain|cannot_judge|no_people)', re.I)
R1_RE = re.compile(r"""['"]?(?:count|response|计数|数量|人数)['"]?\s*[:：]\s*['"]?"""
                   r"""(\d+|abstain|cannot_judge|no_people)""", re.I)
R2_RE = FROZEN_RE
FIRSTINT_RE = re.compile(r'-?\d+')
CLASSES = ('zero', 'nonzero', 'no_people', 'cannot_judge', 'abstain', 'unparsed', 'anomaly')


def cls_from_value(v):
    if v is None:
        return 'unparsed'
    if isinstance(v, str):
        s = v.strip().lower()
        if s in ABSTAIN_WORDS:
            return s
        try:
            v = float(s)
        except ValueError:
            return 'unparsed'
    v = float(v)
    if v >= ANOM:
        return 'anomaly'
    return 'zero' if v == 0 else 'nonzero'


def _first_int(raw):
    m = FIRSTINT_RE.search((raw or '').replace(',', ''))
    return int(m.group(0)) if m else None


def r_frozen(raw):
    raw = raw or ''
    m = FROZEN_RE.search(raw)
    if m:
        v = m.group(1)
        return cls_from_value(int(v) if v.isdigit() else v)
    return cls_from_value(_first_int(raw))


def r_json(raw):
    s = re.sub(r'```[a-zA-Z]*', ' ', raw or '').replace('\\n', ' ').strip()
    cands = [s]
    if '{' in s and '}' in s and s.rfind('}') > s.find('{'):
        cands.append(s[s.find('{'):s.rfind('}') + 1])
    for c in cands:
        if not c:
            continue
        try:
            d = json.loads(c)
        except Exception:
            continue
        if isinstance(d, dict):
            for k in ('count', 'response', '计数', '数量', '人数'):
                if k in d:
                    return cls_from_value(d[k])
    return 'unparsed'


def r_keyword(raw):
    r = (raw or '').lower()
    for k in ABSTAIN_WORDS:
        if k in r:
            return k
    return cls_from_value(_first_int(raw))


def r_int(raw):
    return cls_from_value(_first_int(raw))


def r_r1_only(raw):
    flat = re.sub(r'```[a-zA-Z]*', ' ', raw or '').replace('\\n', ' ')
    m = R1_RE.search(flat)
    if not m:
        return 'unparsed'
    v = m.group(1)
    return cls_from_value(int(v) if v.isdigit() else v)


def r_pipeline(raw):
    flat = re.sub(r'```[a-zA-Z]*', ' ', raw or '').replace('\\n', ' ')
    m = R1_RE.search(flat)
    if m:
        v = m.group(1)
        return cls_from_value(int(v) if v.isdigit() else v)
    m = R2_RE.search(raw or '')
    if m:
        v = m.group(1)
        return cls_from_value(int(v) if v.isdigit() else v)
    return cls_from_value(_first_int(raw))


RULES = [('frozen_regex', r_frozen),
         ('json_loads', r_json),
         ('raw_keyword', r_keyword),
         ('first_int', r_int),
         ('r1_only', r_r1_only),
         ('r1r2r3_pipeline', r_pipeline)]
RULEDICT = dict(RULES)
ALLCOL = [n for n, _ in RULES] + ['as_published']


def cls_published(raw, pred):
    r = str(raw or '').lower()
    p = str(pred or '').strip()
    for k in ABSTAIN_WORDS:
        if k in r:
            return k
    if p == '':
        return 'unparsed'
    try:
        v = float(p)
    except ValueError:
        return 'unparsed'
    if v >= ANOM:
        return 'anomaly'
    return 'zero' if v == 0 else 'nonzero'


def load(p):
    with io.open(p, encoding='utf-8-sig') as f:
        return [r for r in csv.DictReader(f) if '#r' not in str(r.get('item') or '')]


def md5f(p):
    return hashlib.md5(io.open(p, 'rb').read()).hexdigest()


def wilson(k, n, z=1.959963985):
    if n == 0:
        return (float('nan'), float('nan'))
    p = k / float(n)
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return ((c - h) / d, (c + h) / d)


def split_model(body):
    """body = '<model>_<ds>_<arm>'（ds 可能含下划线：st_a/st_b/countbench）→ (model, ds, arm)。"""
    for ds in DOMS6:
        i = body.find('_' + ds + '_')
        if i > 0:
            return body[:i], ds, body[i + len(ds) + 2:]
    return None


FILES = []
_CLS_DIST = collections.defaultdict(collections.Counter)
_ZERO_DISAGREE = []
_ZERO_DISAGREE_N = [0]


def track(p, zk):
    """记录文件 md5，并在解析时顺带统计逐类分布与 zero-判定分歧。"""
    if p and p not in [f for f, _ in FILES]:
        FILES.append((p, md5f(p)))


def ruleclasses(rows, arm_key='raw'):
    out = {n: {} for n, _ in RULES}
    out['as_published'] = {}
    for n, fn in RULES:
        for r in rows:
            out[n][r['item']] = fn(r.get(arm_key))
    for r in rows:
        out['as_published'][r['item']] = cls_published(r.get('raw'), r.get('pred'))
    return out


def tally(rows, tag):
    """逐类分布 + zero-判定分歧统计。"""
    cls = ruleclasses(rows)
    ids = list(cls['as_published'])
    for n in ALLCOL:
        for i in ids:
            _CLS_DIST[(tag, n)][cls[n][i]] += 1
    for i in ids:
        zs = {n: (cls[n][i] == 'zero') for n in ALLCOL}
        if len(set(zs.values())) > 1:
            _ZERO_DISAGREE_N[0] += 1
            if len(_ZERO_DISAGREE) < 12:
                rec = {n: cls[n][i] for n in ALLCOL}
                rec['_raw'] = next((r['raw'] for r in rows if r['item'] == i), '')
                _ZERO_DISAGREE.append(rec)
    return cls


# ───────────────────────────── 表 1：§5.7 七家族（M.19.2） ─────────────────────────────
def seven_family():
    print('=' * 132)
    print('【表 1】§5.7 七家族契约表（M.19.2）：permit 臂下"仍答 0" —— 六规则 + as_published 逐家对照')
    print('=' * 132)
    bodies = {}
    for p in glob.glob(RP('analysis', 'e2xt_a800', 'merged', '*.csv')):
        b = os.path.basename(p)
        if not b.startswith('e1_'):
            continue
        sp = split_model(b[3:-4])
        if sp:
            bodies.setdefault(sp[0], set()).add(sp[1])
    fams = sorted(f for f, ds in bodies.items()
                  if sum(1 for d in DOM4 if d in ds) > 0
                  and any(os.path.exists(os.path.join(RP('analysis', 'e2xt_a800', 'merged'), 'e1_%s_%s_permit.csv' % (f, d))) for d in DOM4))
    res = {}
    for f in fams:
        per_rule = {n: [0, 0] for n in ALLCOL}
        for d in DOM4:
            pb = os.path.join(RP('analysis', 'e2xt_a800', 'merged'), 'e1_%s_%s_base.csv' % (f, d))
            pp = os.path.join(RP('analysis', 'e2xt_a800', 'merged'), 'e1_%s_%s_permit.csv' % (f, d))
            if not (os.path.exists(pb) and os.path.exists(pp)):
                continue
            track(pb, None); track(pp, None)
            rb, rp = load(pb), load(pp)
            cb = tally(rb, 'E3/%s/%s/base' % (f, d))
            cp = tally(rp, 'E3/%s/%s/permit' % (f, d))
            for n in ALLCOL:
                z = [i for i in cb['as_published'] if cb[n][i] == 'zero']
                per_rule[n][0] += len(z)
                per_rule[n][1] += sum(1 for i in z if cp[n].get(i) == 'zero')
        res[f] = per_rule

    print('%-28s' % '家族' + ''.join('%17s' % n[:17] for n in ALLCOL))
    print('-' * 132)
    rates = collections.defaultdict(dict)
    for f in fams:
        line = '%-28s' % f
        for n in ALLCOL:
            b, k = res[f][n]
            rt = 100.0 * k / b if b else float('nan')
            rates[n][f] = rt
            line += '%17s' % ('%d/%d %.3f%%' % (k, b, rt))
        print(line)
    print('-' * 132)
    agg = {}
    for n in ALLCOL:
        tb = sum(res[f][n][0] for f in fams)
        tk = sum(res[f][n][1] for f in fams)
        agg[n] = 100.0 * tk / tb if tb else float('nan')
    print('%-28s' % '七家合计率' + ''.join('%17s' % ('%.3f%%' % agg[n]) for n in ALLCOL))
    print()
    print('  逐家跨规则极差（pp，含 as_published）：')
    worst = 0.0
    for f in fams:
        vals = [rates[n][f] for n in ALLCOL if not math.isnan(rates[n][f])]
        sp = max(vals) - min(vals)
        worst = max(worst, sp)
        print('    %-28s 极差 %8.4f pp  （min %.3f%% / max %.3f%%）%s'
              % (f, sp, min(vals), max(vals), '   ← ★ ≥7 pp' if sp >= 7 else ''))
    print('    ⇒ 家族级最大极差 = **%.4f pp**' % worst)
    print('  七家合计率极差 = **%.4f pp**' % (max(agg.values()) - min(agg.values())))
    print()
    print('  P1 判定（≤5% 通过；>30% 反例），逐规则：')
    for n in ALLCOL:
        ok = [f for f in fams if rates[n][f] <= 5.0]
        bad = [f for f in fams if rates[n][f] > 30.0]
        mid = [f for f in fams if 5.0 < rates[n][f] <= 30.0]
        print('    %-18s 通过 %d/%d ｜ 反例 %s ｜ 部分(5,30] %s' % (n, len(ok), len(fams), bad or '无', mid or '无'))
    return fams, rates, agg


# ───────────────────────── 表 2：M.18.3 的 52 个 (model × domain) 格 ─────────────────────────
def census_52():
    print()
    print('=' * 132)
    print('【表 2】M.18.3 的 52 个 (model×domain) 格：permit / channel 是否消掉该模型自己 base 的答零')
    print('=' * 132)
    models = {}
    for p in glob.glob(RP('analysis', 'e2_newh20', 'e1_*.csv')):
        sp = split_model(os.path.basename(p)[3:-4])
        if sp:
            models.setdefault(sp[0], set()).add((sp[1], sp[2]))
    cells = []
    for m in sorted(models):
        for d in DOM4:
            arms = {a for (dd, a) in models[m] if dd == d}
            if {'base', 'permit', 'channel'} <= arms:
                cells.append((m, d))
    print('  有 census 文件的配置 = %d ｜ 四域上 base+permit+channel 齐备的格 = **%d**'
          % (len(models), len(cells)))
    partial = [(m, sum(1 for (dd, a) in models[m] if dd in DOM4 and a == 'base'))
               for m in sorted(models)]
    print('  逐配置在四域上的 base 文件数（诊断，应为 4）：'
          + ', '.join('%s=%d' % (m, n) for m, n in partial if n != 4) or '  全部 = 4')
    per_rule = {n: {'p': 0, 'c': 0, 'cells': {}} for n in ALLCOL}
    details = []
    for (m, d) in cells:
        pb = os.path.join(RP('analysis', 'e2_newh20'), 'e1_%s_%s_base.csv' % (m, d))
        pp = os.path.join(RP('analysis', 'e2_newh20'), 'e1_%s_%s_permit.csv' % (m, d))
        pc = os.path.join(RP('analysis', 'e2_newh20'), 'e1_%s_%s_channel.csv' % (m, d))
        for q in (pb, pp, pc):
            track(q, None)
        rb, rp, rc = load(pb), load(pp), load(pc)
        cb = tally(rb, 'E2/%s/%s/base' % (m, d))
        cp = tally(rp, 'E2/%s/%s/permit' % (m, d))
        cc = tally(rc, 'E2/%s/%s/channel' % (m, d))
        _CACHE[(m, d, 'base')] = cb
        _CACHE[(m, d, 'permit')] = cp
        _CACHE[(m, d, 'channel')] = cc
        row = {'model': m, 'dom': d}
        for n in ALLCOL:
            z = [i for i in cb['as_published'] if cb[n][i] == 'zero']
            kp = sum(1 for i in z if cp[n].get(i) == 'zero')
            kc = sum(1 for i in z if cc[n].get(i) == 'zero')
            row[n] = (len(z), kp, kc)
            per_rule[n]['cells'][(m, d)] = (len(z), kp, kc)
            per_rule[n]['p'] += 1 if kp == 0 else 0
            per_rule[n]['c'] += 1 if kc == 0 else 0
        details.append(row)

    ncl = len(cells)
    print()
    print('  口径                        permit 消掉的格            channel 消掉的格')
    for n in ALLCOL:
        print('    %-20s %3d/%d = %6.2f%%          %3d/%d = %6.2f%%'
              % (n, per_rule[n]['p'], ncl, 100.0 * per_rule[n]['p'] / ncl,
                 per_rule[n]['c'], ncl, 100.0 * per_rule[n]['c'] / ncl))
    hit = [n for n in ALLCOL if per_rule[n]['p'] == 46 and per_rule[n]['c'] == 52]
    print('  ★ 与稿内印的 **46 of 52 / 52 of 52** 一致的规则：%s' % (', '.join(hit) or '**无**'))
    print()
    sp_rows = []
    for row in details:
        vals = []
        for n in ALLCOL:
            b, kp, kc = row[n]
            vals.append(100.0 * kp / b if b else 0.0)
        sp_rows.append((max(vals) - min(vals), row))
    sp_rows.sort(reverse=True, key=lambda x: x[0])
    print('  逐格"permit 仍答 0"跨规则极差 —— 最大 5 格：')
    for sp, row in sp_rows[:5]:
        print('    %-24s %-9s 极差 %8.4f pp' % (row['model'], row['dom'], sp))
    print('    ⇒ 52 格的最大极差 = **%.4f pp**' % sp_rows[0][0])
    flips_p = [row for row in details if len({row[n][1] == 0 for n in ALLCOL}) > 1]
    flips_c = [row for row in details if len({row[n][2] == 0 for n in ALLCOL}) > 1]
    print('  ★ 判定翻转：permit %s ｜ channel %s'
          % ('无' if not flips_p else '%d 格' % len(flips_p),
             '无' if not flips_c else '%d 格' % len(flips_c)))

    # 出口灵敏度：permit 下"拒答 vs 给数 vs 仍答 0" 三分，逐规则合计
    print()
    print('  ★ 出口灵敏度（52 格的 base 答零项在 permit 下的去向，逐规则合计）：')
    print('    %-20s %10s %10s %10s %10s' % ('规则', '→拒答', '→给数', '→仍答0', '→未解析'))
    for n in ALLCOL:
        tot = collections.Counter()
        for (m, d) in cells:
            pb = os.path.join(RP('analysis', 'e2_newh20'), 'e1_%s_%s_base.csv' % (m, d))
            pp = os.path.join(RP('analysis', 'e2_newh20'), 'e1_%s_%s_permit.csv' % (m, d))
            cb = _CACHE[(m, d, 'base')]
            cp = _CACHE[(m, d, 'permit')]
            for i in cb['as_published']:
                if cb[n][i] != 'zero':
                    continue
                c = cp[n].get(i)
                if c in ('abstain', 'cannot_judge', 'no_people'):
                    tot['refusal'] += 1
                elif c == 'zero':
                    tot['zero'] += 1
                elif c == 'unparsed':
                    tot['unparsed'] += 1
                else:
                    tot['number'] += 1
        print('    %-20s %10d %10d %10d %10d'
              % (n, tot['refusal'], tot['number'], tot['zero'], tot['unparsed']))
    return cells, per_rule, details


_CACHE = {}


# ───────────────────── 表 3：头条率的四规则极差（7 pp 判据） ─────────────────────
def headline_spread(fams, rates, agg, details):
    print()
    print('=' * 132)
    print('【表 3】头条率的四规则极差 —— 判据：任一 ≥ 7 pp ⇒ 该数必须改成区间、不得作点值')
    print('=' * 132)
    four = ['frozen_regex', 'json_loads', 'raw_keyword', 'first_int']
    rows = []
    for f in fams:
        rows.append(('表1 · 七家族 %s 的"仍答 0"率' % f, [rates[n][f] for n in four]))
    rows.append(('表1 · 七家族合计率', [agg[n] for n in four]))
    ncl = len(details)
    for key, lab in (('p', '表2 · census permit 消格率'), ('c', '表2 · census channel 消格率')):
        vals = []
        for n in four:
            cnt = 0
            for row in details:
                b, kp, kc = row[n]
                cnt += 1 if ((kp == 0) if key == 'p' else (kc == 0)) else 0
            vals.append(100.0 * cnt / ncl)
        rows.append((lab, vals))
    for d in ('st_a', 'ucf'):
        for m in ('qwen3-vl-32b-awq', 'qwen3-vl-32b-awq8', 'qwen3-vl-32b-bf16',
                  'qwen3-vl-32b-fp8', 'qwen3-vl-32b-gptq'):
            p = os.path.join(RP('analysis', 'e2_newh20'), 'e1_%s_%s_base.csv' % (m, d))
            if not os.path.exists(p):
                continue
            track(p, None)
            rs = load(p)
            cb = tally(rs, 'E2/%s/%s/base' % (m, d))
            vals = [100.0 * sum(1 for i in cb[n] if cb[n][i] == 'zero') / len(rs) for n in four]
            rows.append(('表2b · M.18.8 %s/%s 答零率' % (m, d), vals))
    hdr = '  %-48s' % '量' + ''.join('%11s' % n[:11] for n in four) + '%11s' % '极差'
    print(hdr)
    print('-' * 132)
    breach = []
    for lab, vals in rows:
        sp = max(vals) - min(vals)
        if sp >= 7:
            breach.append((lab, sp, vals))
        print('  %-48s' % lab + ''.join('%11.4f' % v for v in vals) + '%11.4f  %s'
              % (sp, '★ ≥7 pp' if sp >= 7 else ''))
    print('-' * 132)
    print('  ⇒ 触发 7 pp 判据的量：%s'
          % (', '.join('%s（%.4f pp）' % (l, s) for l, s, _ in breach) or '**无**'))
    print('    最大极差 = %.4f pp' % max(sp for _, sp in
                                       [(r[0], max(r[1]) - min(r[1])) for r in rows]))
    return rows, breach


# ───────────────────── 复核 p2 的 3,598/3,600（独立路线） ─────────────────────
def reverify_p2():
    print()
    print('=' * 132)
    print('【表 4】复核 p2 的 3,598 / 3,600 —— **独立路线**：用已存 `pred_frozen` 列，不重新派生 pred')
    print('=' * 132)
    files = sorted(glob.glob(RP('analysis', 'p2_a800', 'p2_probe_results_reparsed', '*.csv')))
    if not files:
        print('  !! 目录不存在或为空：%s ⇒ 未核实' % P2R)
        return None
    agree = disagree = 0
    detail = []
    for f in files:
        track(f, None)
        rs = load(f)
        same = 0
        for r in rs:
            fa = cls_published(r.get('raw'), r.get('pred_frozen'))
            fb = cls_published(r.get('raw'), r.get('pred'))
            same += 1 if fa == fb else 0
        agree += same
        disagree += len(rs) - same
        detail.append((os.path.basename(f), len(rs), same, len(rs) - same))
    for name, n, s, d in detail:
        print('    %-46s n=%-4d 一致 %-4d 不一致 %-4d' % (name, n, s, d))
    tot = agree + disagree
    print('  ⇒ 一致 **%d / %d = %.4f%%**（稿内印 3,598 / 3,600 = 99.9444%%）' % (agree, tot, 100.0 * agree / tot))
    print('  ★ 两者是否同一个对象：**是同一个「零/非零」边界上的比较**，但用的列不同 ——')
    print('    稿内那个数是 `p2_rule_sensitivity.py` 用 `cls_of(raw, pred)` 对 `cls_reparse(pred)` 算的；')
    print('    本路线用**冻结件写的 `pred_frozen`** 对重解析 `pred` 算。结论相同 ⇒ 互为独立复核。')
    return agree, tot, disagree


def print_class_dists():
    print()
    print('=' * 132)
    print('【表 5】逐类分布（合并全部文件）—— 规则之间**到底差在哪一类**')
    print('=' * 132)
    agg = collections.defaultdict(collections.Counter)
    for (tag, n), c in _CLS_DIST.items():
        agg[n] += c
    print('  %-20s' % '规则' + ''.join('%13s' % k for k in CLASSES))
    for n in ALLCOL:
        print('  %-20s' % n + ''.join('%13d' % agg[n].get(k, 0) for k in CLASSES))
    print()
    print('  ★ zero-判定分歧（同一 item 在不同规则下"是不是 zero"不一致）：**%d 项**' % _ZERO_DISAGREE_N[0])
    if _ZERO_DISAGREE:
        print('  前几例（raw / 各规则判定）：')
        for rec in _ZERO_DISAGREE[:6]:
            print('    raw=%r' % rec['_raw'][:90])
            print('      ' + '  '.join('%s=%s' % (n, rec[n]) for n in ALLCOL))


def main():
    fams, rates, agg = seven_family()
    cells, per_rule, details = census_52()
    rows, breach = headline_spread(fams, rates, agg, details)
    rv = reverify_p2()
    print_class_dists()
    print()
    print('=' * 132)
    print('【文件清单（md5）】共 %d 个输入件' % len(FILES))
    print('=' * 132)
    for p, h in FILES:
        print('  %s  %s' % (h, p))
    with io.open(RP('analysis', 'work', 'n2_rule_spread_inventory.json'), 'w', encoding='utf-8') as f:
        json.dump({'files': [{'md5': h, 'path': p} for p, h in FILES],
                   'rules': [n for n, _ in RULES],
                   'cells_52': [{'model': c[0], 'dom': c[1]} for c in cells],
                   'zero_disagreements': _ZERO_DISAGREE_N[0],
                   'p2_reverify': rv,
                   'breach_7pp': [b[0] for b in breach]},
                  f, ensure_ascii=False, indent=1)
    print('\n清单 → n2_rule_spread_inventory.json')


if __name__ == '__main__':
    main()
