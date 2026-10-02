# -*- coding: utf-8 -*-
"""_p0a_cls.py —— P0-A 共用的行级判读（**类型优先 + 宽词表兜底**）。

★ 判读规则（**三级，逐级下判**；与 `classify()` 实现逐条对应，不要只按第一级理解）：
  (1) `raw` 里的 JSON 对象有 `count` 字段：
        值是数字 / 数字字符串            → **数值答案**
        值是数字以外的字符串             → **弃答**（不论措辞、不论语种）
        值不是标量（bool / 列表 / 空对象）→ **真·格式失败**
  (2) 否则，仪器已写盘的 `pred` 能解析成数 → **数值答案**（与仪器读法对齐）
  (3) 否则，`raw` 里出现 `MARK` 里的**任一词** → **弃答**
  (4) 其余                                → **真·格式失败**

★★ 命名更正（2026-10-02 主代理复核）：本件**不是"措辞无关"**判读 —— 只有第 (1) 级是
   纯类型判读；第 (3) 级是**词表匹配**（`MARK` 共 11 条，含中英与 `unable to count`/`cannot count`）。
   正确说法是：**类型优先、词表兜底，且兜底词表比放行件的三 token 表宽得多**。
   这一点在判决书 §4.1 与本附录 §4.1 已同步更正；旧措辞"与措辞/语种无关"属**过度声称**。

★ 因此凡引用"弃答率"的地方必须**并列两个口径**：
    (i) **放行件词表口径**（`abstain` / `cannot_judge` / `no_people`）——本次 EN 臂的散文弃答
        在它下面会落进 `unparsed`；
    (ii) **本件宽口径**（第 (1)–(3) 级）。
    两者之差纯粹是**词表覆盖差**，与"类型 vs 措辞"无关。
    但有一件事**两个口径都成立**：本仪器 `parse_ok=0` 等价于"**全文没有任何数字**"
    （`parse()` 在 count 键不中时会回退搜 `-?\\d+`）⇒ 这类行**在任何词表下都不是数值答案**。

★ 依据（本机实测，非推断）：本仪器 `parse_ok=0` **同时**编码了两类弃答：
    - 英/放行臂：`{"count": "abstain"}`
    - 中文 base 臂：`{"count": "无法准确数出"}`
  放行件 `e1_internvl35-38b-bf16_densezero_s1.csv` 里 `parse_ok=0` 的恰好 2 行是
  `IMG_115` 与 `img_0325`，raw 皆为「无法准确数出」⇒ 只用英文标记词会把**中文弃答误记为格式失败**。

配套（同一逻辑的必然延伸）：弃答**不算答零**；「有效」分母 = 数值答案 ∪ 明确弃答；C5 分两口径
（(a) 字面 parse_ok 率，(b) 真·格式失败率，5% 阈值用于 (b)）。见 `_p0a_criteria_addendum2_20261002.md`。
"""
import json
import math

MARK = ('abstain', 'cannot_judge', 'cannot judge', 'no_people', 'no people',
        '无法准确数出', '无法数出', '无法确定', '不能准确', 'unable to count', 'cannot count')


def fnum(x):
    x = (x or '').strip()
    if x == '':
        return None
    try:
        return float(x)
    except Exception:
        return None


def classify(r):
    """→ ('num', 值, None) ／ ('abst', None, 措辞) ／ ('bad', None, 原文片段)"""
    raw = (r.get('raw') or '').strip()
    s = raw
    if s.startswith('`'):
        s = s.strip('`')
        if s[:4].lower() == 'json':
            s = s[4:]
    i, j = s.find('{'), s.rfind('}')
    if i >= 0 and j > i:
        try:
            obj = json.loads(s[i:j + 1])
        except Exception:
            obj = None
        if isinstance(obj, dict) and 'count' in obj:
            c = obj['count']
            if isinstance(c, bool):
                return ('bad', None, raw[:60])
            if isinstance(c, (int, float)):
                return ('num', float(c), None)
            if isinstance(c, str):
                t = c.strip()
                v = fnum(t)
                if v is not None:
                    return ('num', v, None)
                return ('abst', None, t[:40])
            return ('bad', None, raw[:60])
    v = fnum(r.get('pred'))
    if v is not None:
        return ('num', v, None)
    low = raw.lower()
    for m in MARK:
        if m in low:
            return ('abst', None, m)
    return ('bad', None, raw[:60])


def cls(rows):
    st = dict(n=len(rows), num=0, zero=0, abst=0, unparsed=0, mismatch=0, words={}, bads=[])
    for r in rows:
        kind, v, w = classify(r)
        if kind == 'num':
            st['num'] += 1
            if v == 0:
                st['zero'] += 1
            p = fnum(r.get('pred'))
            if p is not None and p != v:
                st['mismatch'] += 1
        elif kind == 'abst':
            st['abst'] += 1
            st['words'][w] = st['words'].get(w, 0) + 1
        else:
            st['unparsed'] += 1
            st['bads'].append((r.get('item'), w))
    st['valid'] = st['num'] + st['abst']
    st['rate_valid'] = 100.0 * st['zero'] / st['valid'] if st['valid'] else float('nan')
    st['rate_num'] = 100.0 * st['zero'] / st['num'] if st['num'] else float('nan')
    st['abst_rate'] = 100.0 * st['abst'] / st['valid'] if st['valid'] else float('nan')
    st['c5a'] = 100.0 * sum(1 for r in rows if str(r.get('parse_ok', '')).strip() in ('1', '1.0')) / st['n'] if st['n'] else float('nan')
    st['c5b'] = 100.0 * st['unparsed'] / st['n'] if st['n'] else float('nan')
    return st


def wilson(k, n):
    if not n:
        return (float('nan'), float('nan'))
    z = 1.959963985
    ph = k / n
    d = 1 + z * z / n
    c = (ph + z * z / (2 * n)) / d
    h = z * math.sqrt(ph * (1 - ph) / n + z * z / (4 * n * n)) / d
    return (100 * (c - h), 100 * (c + h))
