# -*- coding: utf-8 -*-
"""A5-1 离线重解析（★ 只读原始行、只写派生件；原始行一字不改、append-only）。

背景：A5-1 的 `channel` 臂契约要求输出 `{"response": N}`（N 为数量）或 `{"response":"cannot_judge"|"no_people"}`，
而首轮 runner 的解析器只认 `{"count": N}` ⇒ `channel` 臂的数值被记为 pred=None。
★ 原始 `raw` 已完整保留 ⇒ 可离线重解析，**无需重新调用模型**。

派生字段：
  pred2       : 重解析得到的数值（None=未取到数值）
  kind2       : numeric | abstain_schema | hard_abstain | other
     · numeric          = 取到数字（count 或 response 为数字）
     · abstain_schema   = {"count":"abstain"} 或 {"response":"cannot_judge"/"no_people"}（契约内弃答）
     · hard_abstain     = 其它明确的弃答表述（裸词 abstain / 无法判断 / 不能确证 …）
     · other            = 非数字、且不属上面两类（真实失败/退化生成）
用法: python reparse_a51.py <目录含 *.jsonl> [输出csv]
"""
import json, glob, os, re, csv, sys, collections

ABSTAIN_TOKENS = ('abstain', 'cannot_judge', 'no_people')
HARD_PAT = re.compile(r'(无法(判断|确定|确证)|不能(确定|确证)|无法提供|不能提供|抱歉|sorry|i cannot|i can\'t|unable to)')


def parse2(raw):
    """返回 (pred2, kind2)"""
    r = (raw or '').strip()
    if not r:
        return None, 'other'
    # ① {"count": N}
    m = re.search(r'\{\s*"count"\s*:\s*(\d+)', r)
    if m:
        return int(m.group(1)), 'numeric'
    # ② {"response": N}
    m = re.search(r'\{\s*"response"\s*:\s*(\d+)', r)
    if m:
        return int(m.group(1)), 'numeric'
    # ③ schema 弃答
    if re.search(r'"count"\s*:\s*"(abstain|none|无)"', r, re.I) or \
       re.search(r'"response"\s*:\s*"(cannot_judge|no_people|abstain)"', r, re.I):
        return None, 'abstain_schema'
    # ④ 裸词/短语弃答
    low = r.lower()
    if any(t in low for t in ABSTAIN_TOKENS) or HARD_PAT.search(r):
        return None, 'hard_abstain'
    return None, 'other'


def main():
    src = sys.argv[1]
    out = sys.argv[2] if len(sys.argv) > 2 else os.path.join(src, 'T_reparse_summary.csv')
    rows_out = []
    agg = collections.defaultdict(lambda: collections.Counter())
    for f in sorted(glob.glob(os.path.join(src, '*.jsonl'))):
        base = os.path.basename(f)[:-6]
        recs = []
        for l in open(f, encoding='utf-8', errors='replace'):
            try:
                recs.append(json.loads(l))
            except Exception:
                pass
        ok = {}
        for x in recs:
            if x.get('http') == 200:
                ok[x.get('key')] = x
        per = collections.defaultdict(collections.Counter)
        for k, x in ok.items():
            arm = x.get('arm') or '?'
            p2, kind = parse2(x.get('raw'))
            per[arm][kind] += 1
            per[arm]['n'] += 1
            if kind == 'numeric':
                per[arm]['zero'] += (1 if p2 == 0 else 0)
            agg[arm][kind] += 1
            agg[arm]['n'] += 1
            if kind == 'numeric':
                agg[arm]['zero'] += (1 if p2 == 0 else 0)
        for arm in sorted(per):
            c = per[arm]
            rows_out.append(dict(file=base, arm=arm, n=c['n'], numeric=c['numeric'],
                                 abstain_schema=c['abstain_schema'], hard_abstain=c['hard_abstain'],
                                 other=c['other'], zero=c['zero'],
                                 numeric_rate=round(c['numeric'] / c['n'], 4) if c['n'] else 0,
                                 abstain_rate=round((c['abstain_schema'] + c['hard_abstain']) / c['n'], 4) if c['n'] else 0))
    if rows_out:
        with open(out, 'w', encoding='utf-8', newline='') as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows_out[0].keys()))
            w.writeheader()
            for x in rows_out:
                w.writerow(x)
    print('== 全库合计（按臂）==')
    for arm in sorted(agg):
        c = agg[arm]
        n = c['n'] or 1
        print('  %-8s n=%-5d numeric=%-5d(%.1f%%) 弃答schema=%-5d 硬弃答=%-5d other=%-5d zero=%d'
              % (arm, c['n'], c['numeric'], 100.0 * c['numeric'] / n, c['abstain_schema'], c['hard_abstain'], c['other'], c['zero']))
    print('已写', out, '（%d 行）' % len(rows_out))


if __name__ == '__main__':
    main()
