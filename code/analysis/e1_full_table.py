# -*- coding: utf-8 -*-
"""E1 全表：行taxonomy + 跨模型对齐 + 主表 + flash 污染检查。
样本帧是确定性的（zero.sort(gt) 后等间隔取），因此各模型应共享同一 40 个 item。
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
import os
import re
import statistics
import sys
import collections
import json

sys.stdout.reconfigure(encoding='utf-8')
D = RP('analysis', 'e1_5090')
ABSTAIN_TOKENS = ('abstain', 'cannot_judge', 'no_people')


def is_num(v):
    try:
        float(v)
        return True
    except Exception:
        return False


def load(p):
    out = []
    for r in csv.DictReader(open(p, encoding='utf-8-sig')):
        it = r['item']
        base_it, _, rep = it.partition('#r')
        out.append(dict(base=base_it, rep=(int(rep) if rep else None),
                        gt=float(r['gt']),
                        pred=(r['pred'] or '').strip(),
                        ok=(r.get('parse_ok') or '').strip(),
                        raw=(r.get('raw') or '')))
    return out


def main():
    files = {}
    pat = re.compile(r'^(?P<model>.+)_(?P<ds>st_a|st_b|ucf)_(?P<arm>[A-Za-z]+)$')
    for p in sorted(glob.glob(RP('analysis', 'e1_5090', 'e1_*.csv'))):
        b = os.path.basename(p)[3:-4]
        mm = pat.match(b)
        if not mm:
            print('!! 无法解析', b)
            continue
        files[(mm.group('model'), mm.group('ds'), mm.group('arm'))] = load(p)

    # ---- 1. 确定性样本帧：从带 rep 的文件里取 base item 集 ----
    canon = {}
    for ds in ('st_a', 'ucf'):
        for (m, d, a), rows in files.items():
            if d == ds and any(r['rep'] is not None for r in rows):
                s = sorted({r['base'] for r in rows if r['rep'] is not None})
                if len(s) >= 40:
                    canon[ds] = s
                    print('canon[%s] = %d 个 item（取自 %s/%s）' % (ds, len(s), m, a))
                    break
    print()
    print('=== 2. 行 taxonomy 与帧外行 ===')
    print('%-46s %5s %5s %5s %6s %s' % ('file', 'rows', 'rep#', 'bare', 'frame', 'extra_items'))
    for k in sorted(files):
        rows = files[k]
        nrep = sum(1 for r in rows if r['rep'] is not None)
        nbare = len(rows) - nrep
        base_items = {r['base'] for r in rows}
        extra = sorted(base_items - set(canon[k[1]]))
        print('%-46s %5d %5d %5d %6d %s' % ('%s_%s_%s' % k, len(rows), nrep, nbare,
                                            len(base_items & set(canon[k[1]])),
                                            (','.join(extra[:6]) + ('...' if len(extra) > 6 else '')) if extra else '-'))

    # ---- 3. 主表：只用帧内行 ----
    print()
    print('=== 3. 主表（仅帧内 %d/%d 个 item）===' % (len(canon['st_a']), len(canon['ucf'])))
    hdr = '%-28s %-5s %-8s %4s %5s %7s %8s %8s %7s %6s %6s' % (
        'model', 'ds', 'arm', 'n', 'zero', 'medP/G', 'dev%', '|dev|', 'abst', 'chan', 'ok')
    print(hdr)
    table = {}
    for (m, d, a) in sorted(files, key=lambda x: (x[1], x[0], x[2])):
        rows = [r for r in files[(m, d, a)] if r['base'] in set(canon[d])]
        if not rows:
            continue
        nums = [float(r['pred']) for r in rows if is_num(r['pred'])]
        gts = [r['gt'] for r in rows if is_num(r['pred'])]
        zeros = sum(1 for v in nums if v == 0)
        abst = sum(1 for r in rows if (not is_num(r['pred'])) or any(t in r['raw'].lower() for t in ABSTAIN_TOKENS))
        chan = sum(1 for r in rows if any(t in (r['raw'] + ' ' + r['pred']).lower() for t in ABSTAIN_TOKENS))
        ok = sum(1 for r in rows if r['ok'] == '1')
        ratios = [v / r['gt'] for v, r in zip(nums, [x for x in rows if is_num(x['pred'])]) if r['gt'] > 0]
        med = statistics.median(ratios) if ratios else float('nan')
        dev = (sum(nums) - sum(gts)) / sum(gts) * 100 if nums else float('nan')
        print('%-28s %-5s %-8s %4d %5d %7.3f %7.1f%% %7.1f%% %7d %6d %6d' % (
            m, d, a, len(rows), zeros, med, dev, abs(dev), abst, chan, ok))
        table['%s|%s|%s' % (m, d, a)] = dict(
            n=len(rows), zeros=zeros, zero_rate=zeros / len(rows),
            med=med, dev=dev, abst=abst, chan=chan, ok=ok,
            n_num=len(nums), mean_pred=sum(nums) / len(nums) if nums else None,
            mean_gt=sum(gts) / len(gts) if gts else None)

    # ---- 4. 摘要：各模型 base 臂零率 + 通道臂行为 ----
    print()
    print('=== 4. base 臂零率（帧内）===')
    for m in sorted({k[0] for k in files}):
        line = []
        for d in ('st_a', 'ucf'):
            t = table.get('%s|%s|base' % (m, d))
            line.append('%s %2d/%-3d=%4.1f%%' % (d, t['zeros'], t['n'], t['zero_rate'] * 100) if t else '%s -' % d)
        print('  %-28s %s' % (m, '   '.join(line)))
    print()
    print('=== 5. permit / channel 臂的显式弃权率 ===')
    for m in sorted({k[0] for k in files}):
        for a in ('permit', 'channel'):
            pts = []
            for d in ('st_a', 'ucf'):
                t = table.get('%s|%s|%s' % (m, d, a))
                if t:
                    pts.append('%s %3d/%-3d=%5.1f%%' % (d, t['chan'], t['n'], t['chan'] / t['n'] * 100))
            if pts:
                print('  %-28s %-8s %s' % (m, a, '   '.join(pts)))
    print()
    print('=== 6. 禁止弃权臂的过估倍数（帧内，pred/gt 中位）===')
    for m in sorted({k[0] for k in files}):
        for a in ('bestA', 'bestB', 'bestC'):
            pts = []
            for d in ('st_a', 'ucf'):
                t = table.get('%s|%s|%s' % (m, d, a))
                if t:
                    pts.append('%s %6.3f' % (d, t['med']))
            if pts:
                print('  %-28s %-6s %s' % (m, a, '   '.join(pts)))

    with open(RP('analysis', 'e1_5090', 'e1_table.json'), 'w', encoding='utf-8') as f:
        json.dump(table, f, ensure_ascii=False, indent=1)
    print()
    print('-> e1_table.json 已写出，%d 个格' % len(table))


if __name__ == '__main__':
    main()
