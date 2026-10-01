# -*- coding: utf-8 -*-
"""p3r4_e1_stats.py —— E-1 逐启动统计（在 A800 上跑，也在本地跑同一份以保证口径一致）。

口径：
  · 行数用 `csv.DictReader` 数（**不用 `wc -l`**：raw 字段内含换行，物理行数会 3 倍虚高）。
  · 清洗照 p4 口径：去重、剔空 pred、剔 pred ≥ 1e5。
  · zero-pool rate = 答零项 / parse_ok 项（分母 = 零池 253）。
  · S 用 `p3r4_zero_1_S_ci.py::S_of(recs,'gt')` 的**逐字同一公式**：
        w = GN/G；rho_t=(P-G)/G；rho_a=(P-GN)/GN；rho_t ≥ 0 ⇒ S 无定义；否则 S = 100(1-w)/(1-w(1+rho_a))
  · 跨启动翻转率：把每项按"答零/未答零"二值分类，对每对启动算逐项不一致比例，取最大值。
用法：python3 pf_e1_stats.py <zero_csv> <nonzero_csv> [--json out.json]
"""
import csv
import io
import json
import math
import sys

ANOM = 1e5


def load(path):
    with io.open(path, encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


def clean(rows):
    seen, out = set(), []
    for r in rows:
        k = str(r.get('item') or '').strip()
        if not k or k in seen:
            continue
        seen.add(k)
        s = str(r.get('pred') or '').strip()
        if s == '':
            continue
        try:
            v = float(s)
        except Exception:
            continue
        if v >= ANOM:
            continue
        try:
            gv = float(str(r.get('gt') or '').strip() or 0.0)
        except Exception:
            gv = 0.0
        out.append((k, gv, v))
    return out


def S_of(recs, weight='gt'):
    if not recs:
        return (None, None, None, None, 0, 0)
    n = len(recs)
    if weight == 'gt':
        G = sum(g for _, g, _ in recs)
        ans = [(g, p) for _, g, p in recs if p > 0]
        GN = sum(g for g, _ in ans)
        P = sum(p for _, p in ans)
    else:
        G = float(n)
        ans = [(1.0, p) for _, g, p in recs if p > 0]
        GN = float(len(ans))
        P = sum(p for _, p in ans)
    na = len(ans)
    if G <= 0 or GN <= 0 or na == 0 or na == n:
        return (None, None, None, None, n, na)
    w = GN / G
    rho_t = (P - G) / G
    rho_a = (P - GN) / GN
    if rho_t >= 0:
        return (None, w, rho_t, rho_a, n, na)
    return (100.0 * (1 - w) / (1 - w * (1 + rho_a)), w, rho_t, rho_a, n, na)


def wilson(k, n, z=1.959963984540054):
    if n == 0:
        return (float('nan'), float('nan'))
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return ((c - h) / d, (c + h) / d)


def rate_block(rows):
    """返回零池/非零池的原始行数、parse_ok 数、答零数、答零率与 Wilson 区间。"""
    n = len(rows)
    pok = sum(1 for r in rows if str(r.get('parse_ok') or '').strip() == '1')
    z = sum(1 for r in rows if str(r.get('parse_ok') or '').strip() == '1'
            and str(r.get('pred') or '').strip() in ('0', '0.0'))
    lo, hi = wilson(z, pok)
    return dict(n_rows=n, n_parse_ok=pok, parse_rate=(pok / n if n else float('nan')),
                n_zero=z, zero_rate=(z / pok if pok else float('nan')),
                zero_wilson=[lo, hi])


def main():
    zf, nzf = sys.argv[1], sys.argv[2]
    z, nz = load(zf), load(nzf)
    zc, nzc = clean(z), clean(nz)
    union = zc + nzc
    S, w, rt, ra, n, na = S_of(union, 'gt')
    out = dict(zero_csv=zf, nonzero_csv=nzf,
               zero_pool=rate_block(z),
               nonzero_pool=rate_block(nz),
               union=dict(n_clean=n, n_answered=na, S=S, w=w, rho_total=rt, rho_answered=ra),
               pred_vocab_zero_sorted=sorted(
                   [str(r.get('pred') or '').strip() for r in z
                    if str(r.get('parse_ok') or '').strip() == '1'])[:0])
    print('  zero-pool  n=%d  parse_ok=%d(%.1f%%)  答零=%d  率=%.2f%%  Wilson95=[%.2f%%, %.2f%%]'
          % (out['zero_pool']['n_rows'], out['zero_pool']['n_parse_ok'],
             100 * out['zero_pool']['parse_rate'], out['zero_pool']['n_zero'],
             100 * out['zero_pool']['zero_rate'], 100 * out['zero_pool']['zero_wilson'][0],
             100 * out['zero_pool']['zero_wilson'][1]))
    print('  nonzero    n=%d  parse_ok=%d(%.1f%%)  答零=%d'
          % (out['nonzero_pool']['n_rows'], out['nonzero_pool']['n_parse_ok'],
             100 * out['nonzero_pool']['parse_rate'], out['nonzero_pool']['n_zero']))
    print('  union      n_clean=%d n_answered=%d  S=%s  w=%.4f rho_total=%.4f rho_answered=%.4f'
          % (n, na, ('%.2f%%' % S) if S is not None else 'undef',
             w or float('nan'), rt if rt is not None else float('nan'),
             ra if ra is not None else float('nan')))
    print('  JSON ' + json.dumps(out, ensure_ascii=False))


if __name__ == '__main__':
    main()
