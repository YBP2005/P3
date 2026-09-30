# -*- coding: utf-8 -*-
"""anchor_aux.py —— **补上 F.9 / 附录 E 的数值门禁，并把"口径上下文白名单"做成常设检查**。

## 为什么（v0547 盲审两条明确要求）
* **qwen38max −2.0**："对附录中仍无门禁覆盖的数值表（特别是 **F.9 的 isotonic 列**、**E.1–E.5 的检测
  阶梯表**）补建门禁脚本，**至少覆盖主稿引用的每个数字**。"
* **hy4 −2.5**："将 `anchor_f10.py` 扩展为**全文正则扫描 + 上下文白名单**，并对 F.9 增加
  **口径字段转录校验**。"

## 三道检查（v0549 重写版）
  **A1｜F.9 十行 × 五列，转录校验**：
       (a) 每行按**显示名**（`f9_quoted.json` 的 `unit` 与 F.9 表首列逐字相同）匹配，不再用中文键前缀猜；
       (b) 五列数值（shared affine / isotonic / quantile map / CI 两端）逐格在册；
       (c) `transcribed_from_md5` 必须等于**中文骨架当前 md5**——转录来源被冻结，改骨架即报错；
       (d) 10 行全 `ok=True`，且 `columns` 四列口径齐全；
       (e) **跨产物独立复核**：F.9 的 (isotonic, CI_lo, CI_hi) 三元组多重集必须与
           `a44_split16_result.json` 的 `units_10` 逐一相同（a44_split16 的阶段 1 回归自检证明它
           逐位复算了这张表）；
       (f) `group` 列必须是 k=3 的 3/7 切分，且低组恰为三个像素预算单元；
       (g) F.9 段落必须**标注为转录**并给出"引用须带校准口径"的要求（口径字段披露）。
  **A2｜附录 E 的数值 ⇄ 冻结阶梯记录（从表里取值，不手抄）**：
       E.1 的每一行（min|ME| / τ* / 95% CI / 不可达）与 E.2 的 IoU 列、输入尺度列，都回到
       `PaperB_检测tau阶梯_20260911.md` 的**实际单元格**去核对；E.3 的 RetinaNet/UCF-QNRF/tile-512
       回到 `PaperB_检测端切块阶梯_20260912.md`；另加"主稿引用 Appendix E.n 的句子里的每个数字都必须
       出现在补充材料 Appendix E 段"的通用规则（qwen38max 的"最低要求"的机器化）。
  **A3｜口径上下文白名单（全文正则扫描）**：主稿里每一处 `N pp` 声称，**同一句内**必须出现口径词，
      或命中 `caliber_context_whitelist.json` 登记的"差值/受控比较"语境（那类数值两端同口径，口径在
      差值里抵消）。未命中即 FAIL。并打印每条规则的覆盖句数，单条覆盖 > 60% 判 FAIL（防白名单被稀释）。

## 阳性对照（教训 06b：先证明判据能失败）
`--selftest` 往一份内存稿里注入两句：(a) 一个**孤立量级** `12.3 pp`（必须判 FAIL）；
(b) 一个**带口径**的同类句子（必须**不**增加失败数）。两者都要满足才算门禁有效。
用法：python -u anchor_aux.py [--selftest]
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
import io
import json
import os
import re
import sys
import hashlib

sys.stdout.reconfigure(encoding='utf-8')
W = os.path.dirname(os.path.abspath(__file__))
EN = RP('PaperB_英文稿_PR_20260919.md')
SUP = RP('PaperB_英文补充材料_PR_20260919.md')
F9 = os.path.join(W, 'f9_quoted.json')
A44 = os.path.join(W, 'a44_split16_result.json')
WL = os.path.join(W, 'caliber_context_whitelist.json')
SKEL = NR('PaperB_章节骨架_v3_可确证性_20260911.md')
REC_LADDER = NR('PaperB_检测tau阶梯_20260911.md')
REC_TILE = NR('PaperB_检测端切块阶梯_20260912.md')

# 口径词：出现在同一句里即视为"已标注口径"
CALIBER = ('person-matched', 'all-detections', 'all-class', 'pooled', 'per-item', 'per image',
           'per-unit', 'base arm', 'base contract', 'equal-count', 'random', 'caliber',
           'sensitivity', 'specificity', 'GT-weighted', 'unweighted', 'shared', 'median',
           'channel', 'contract')

ok = fail = 0
FAILD = []


def chk(label, cond, detail=''):
    global ok, fail
    if cond:
        ok += 1
        print('  [OK  ] %s' % label)
    else:
        fail += 1
        FAILD.append(label)
        print('  [FAIL] %s   %s' % (label, detail))


def cells(line):
    return [c.strip().strip('*') for c in line.strip('|').split('|')]


def table(seg, start, end):
    """取 seg 中 start 标记到 end 标记之间的表行（跳过表头行与分隔行）。"""
    s = seg.index(start)
    e = seg.index(end, s + 1) if end else len(seg)
    out = []
    for l in seg[s:e].splitlines():
        if not l.strip().startswith('|'):
            continue
        if re.fullmatch(r'[\|\-: ]+', l.strip()):
            continue
        if start in l:          # 表头行本身
            continue
        out.append(cells(l))
    return out


def fnum(s):
    m = re.match(r'^\s*(-?\d+(?:\.\d+)?)', s)
    return float(m.group(1)) if m else None


def ladder_records(path=REC_LADDER):
    """冻结阶梯记录的实际单元格：npz 名 / 匹配的 CSV / min|ME| / τ* / 95% CI / 是否不可达。"""
    rows = []
    for l in io.open(path, encoding='utf-8', newline='', errors='replace').read().splitlines():
        if not l.strip().startswith('|') or '---' in l:
            continue
        c = cells(l)
        if len(c) < 8 or not c[0].endswith('.npz'):
            continue
        rows.append(dict(npz=c[0], csv=c[1], minme=fnum(c[4]), tau=fnum(c[5]),
                         ci=re.sub(r'\s+', ' ', c[6]).strip(),
                         unreach=('不可达' in l)))
    return rows


def rec_hits(rec, key):
    """同一配置在记录里可能有多行（npz 名或匹配的 CSV 含该键），两列都算。"""
    return [x for x in rec if key in x['npz'] or key in x['csv']]


def run(en_text=None, sup_text=None, quiet=False):
    global ok, fail, FAILD
    ok = fail = 0
    FAILD = []
    en = en_text if en_text is not None else io.open(EN, encoding='utf-8', newline='').read()
    sup = sup_text if sup_text is not None else io.open(SUP, encoding='utf-8', newline='').read()
    f9 = json.loads(io.open(F9, encoding='utf-8').read())
    a44 = json.loads(io.open(A44, encoding='utf-8').read())
    wl = json.loads(io.open(WL, encoding='utf-8').read())
    f9seg = sup[sup.index('### F.9'):]
    f9seg = f9seg[:f9seg.index('\n### ', 10)] if '\n### ' in f9seg[10:] else f9seg
    eseg = sup[sup.index('## Appendix E.'):]

    # ── A1 F.9 十行 × 五列（转录校验 + 跨产物复核） ────────────────────────
    print('\n[A1] F.9 十行 × 五列 vs 转录记录 f9_quoted.json / a44_split16_result.json')
    chk('A1 f9_quoted.json 记录四列口径', f9.get('columns') == ['shared_affine', 'isotonic',
                                                             'quantile_map', 'isotonic_CI'],
        str(f9.get('columns')))
    chk('A1 f9_quoted.json 十行转录自检全过', all(r.get('ok') for r in f9['rows']),
        str([r['unit'] for r in f9['rows'] if not r.get('ok')]))
    md5 = hashlib.md5(io.open(SKEL, 'rb').read()).hexdigest()
    chk('A1 转录来源（中文骨架）md5 与记录一致', md5 == f9.get('transcribed_from_md5'),
        '现在 %s / 记录 %s' % (md5[:12], str(f9.get('transcribed_from_md5'))[:12]))
    rows9 = table(f9seg, '| Unit (knob / domain)', None)
    rows9 = [r for r in rows9 if len(r) >= 5]
    chk('A1 F.9 表内恰 10 行', len(rows9) == 10, '实得 %d' % len(rows9))
    for row in f9['rows']:
        cand = [r for r in rows9 if r[0] == row['unit']]
        chk('A1 F.9 行按显示名匹配：%s' % row['unit'], bool(cand), '未找到同名行')
        if not cand:
            continue
        cs = cand[0]
        nums = [float(x) for c in cs for x in re.findall(r'-?\d+\.\d+', c)]
        for i, v in enumerate(row['f9']):
            chk('A1 F.9 [%s] 第 %d 列 = %.1f' % (row['unit'], i + 1, v), v in nums,
                '表内数值 %s' % nums)
    # group 列 = k=3 的 3/7 切分，低组恰为三个像素预算单元
    low = [r[0] for r in rows9 if len(r) > 5 and r[5].startswith('low')]
    chk('A1 F.9 group 列低组恰 3 个', len(low) == 3, str(low))
    chk('A1 F.9 低组都是像素预算单元', all('pixel budget' in x for x in low), str(low))
    # 跨产物独立复核：F.9 的 (iso, lo, hi) 与 a44_split16 的 units_10 逐一相同
    t_f9 = sorted((round(r['f9'][1], 1), round(r['f9'][3], 1), round(r['f9'][4], 1)) for r in f9['rows'])
    t_a44 = sorted((round(r['iso'], 1), round(r['iso_lo'], 1), round(r['iso_hi'], 1)) for r in a44['units_10'])
    chk('A1 F.9 三元组与 a44_split16_result.json(units_10) 逐一相同',
        len(t_a44) == 10 and t_f9 == t_a44,
        'F9 独有 %s ｜ a44 独有 %s' % ([x for x in t_f9 if x not in t_a44],
                                       [x for x in t_a44 if x not in t_f9]))
    # 口径字段披露：F.9 必须自称转录，并要求引用带校准口径
    chk('A1 F.9 自称转录（transcription）', 'transcription' in f9seg, '段落内无 transcription')
    chk('A1 F.9 要求引用带校准口径', re.search(r'calibration caliber|caliber', f9seg) is not None, '')

    # ── A2 附录 E ⇄ 冻结阶梯记录（从表里取值） ─────────────────────────────
    print('\n[A2] 附录 E 的单元格 vs 冻结阶梯记录（E.1/E.2 逐行回源；E.3 回切块记录）')
    rec = ladder_records()
    chk('A2 阶梯记录解析出行（含 npz/τ*/CI）', len(rec) >= 20, '实得 %d' % len(rec))
    e1 = [r for r in table(eseg, '| Input regime', '### E.2') if len(r) >= 5]
    chk('A2 E.1 表行数 = 6', len(e1) == 6, '实得 %d' % len(e1))
    for r in e1:
        mn, tau, ci, reach = fnum(r[2]), fnum(r[3]), re.sub(r'\s+', ' ', r[4]).strip(), r[5]
        cand = [x for x in rec if x['minme'] is not None and mn is not None
                and abs(x['minme'] - mn) < 1e-9]
        if not cand:
            chk('A2 E.1 行回源：%s %s' % (r[0], r[1]), False, '记录里没有 min|ME| = %s 的行' % r[2])
            continue
        if tau is None or 'no' in reach.lower() or '不可达' in reach:
            chk('A2 E.1 行回源（不可达）：%s %s' % (r[0], r[1]),
                any(x['unreach'] for x in cand), '记录里该 min|ME| 行并非不可达')
        else:
            hit = [x for x in cand if x['tau'] is not None and abs(x['tau'] - tau) < 1e-9
                   and x['ci'] == ci]
            chk('A2 E.1 行回源（τ*/CI）：%s %s' % (r[0], r[1]), bool(hit),
                '记录候选 %s' % [(x['tau'], x['ci']) for x in cand])
    e2 = [r for r in table(eseg, '| NMS IoU', '### E.3') if len(r) >= 3]
    io_ = [r for r in e2 if re.fullmatch(r'0\.\d', r[0])]
    sc = [r for r in e2 if re.fullmatch(r'\d{3,4}', r[0])]
    chk('A2 E.2 IoU 行 3 条 / 输入尺度行 3 条', len(io_) == 3 and len(sc) == 3,
        'IoU %d 行、尺度 %d 行' % (len(io_), len(sc)))
    for r in io_:
        key = 'ms1024_iou%s' % r[0]
        cand = rec_hits(rec, key)
        hit = [x for x in cand if x['tau'] is not None and abs(x['tau'] - fnum(r[1])) < 1e-9
               and x['ci'] == re.sub(r'\s+', ' ', r[2]).strip()]
        chk('A2 E.2 IoU %s 行回源（τ*/CI）' % r[0], bool(hit),
            '记录候选 %s' % [(x['tau'], x['ci']) for x in cand])
    for r in sc:
        key = 'ms%s_iou0.7' % r[0]
        cand = rec_hits(rec, key)
        hit = [x for x in cand if x['tau'] is not None and abs(x['tau'] - fnum(r[2])) < 1e-9
               and x['ci'] == re.sub(r'\s+', ' ', r[3]).strip()]
        chk('A2 E.2 输入尺度 %s 行回源（τ*/CI）' % r[0], bool(hit),
            '记录候选 %s' % [(x['tau'], x['ci']) for x in cand])
    # E.3 的 RetinaNet/UCF-QNRF/tile-512 回源到切块记录
    e3 = [r for r in table(eseg, '| Family', '### E.4') if len(r) >= 6]
    hit3 = [r for r in e3 if r[0] == 'RetinaNet' and 'UCF-QNRF' in r[1]]
    chk('A2 E.3 存在 RetinaNet/UCF-QNRF 行', bool(hit3), '未找到')
    if hit3:
        chk('A2 E.3 该行 tile-512 = 0.225', hit3[0][4] == '0.225', '表内 %s' % hit3[0][4])
        t = io.open(REC_TILE, encoding='utf-8', newline='', errors='replace').read()
        trec = [cells(l) for l in t.splitlines()
                if l.strip().startswith('|') and 'RetinaNet' in l and 'UCF-QNRF' in l and 'tile512' in l]
        chk('A2 切块记录里 RetinaNet/UCF-QNRF/tile512 = 0.225',
            any(len(c) > 6 and c[6] == '0.225' for c in trec), str(trec[:1]))
    # 主稿 §4.4 引用的 0.117/0.121/0.131 现在被 E.2 覆盖
    for v in ('0.117', '0.121', '0.131'):
        chk('A2 E.2 覆盖主稿 §4.4 的 %s' % v, v in eseg, 'E 段内未出现')
    # 协议行：177 点 + 4,000× 必须在两边一致，且三种 bootstrap 次数都写清
    chk('A2 E.1 协议行写明 177 点细网格', '177 points' in eseg, '')
    chk('A2 E.1 协议行写明细网格 4,000× bootstrap', '4,000×' in eseg, '')
    chk('A2 E.1 协议行写明切块阶梯 3,000× bootstrap', '3,000×' in eseg, '')
    chk('A2 E.1 协议行写明密度分箱 10,000× bootstrap', '10,000×' in eseg, '')
    chk('A2 主稿 §4.3 的 177 点与 4,000× 与附录一致',
        '177 points' in en and '4,000× bootstrap image resampling' in en, '')
    chk('A2 主稿不再残留 3,000× 细网格说法', '3,000× bootstrap image resampling' not in en, '')
    # 通用规则：引用 Appendix E.n 的主稿句里每个数字都要在 E 段里
    flat = re.sub(r'\s+', ' ', en)
    miss_all = []
    ncited = 0
    for s in re.split(r'(?<=[.!?])\s+', flat):
        if not re.search(r'Appendix E', s):
            continue
        ncited += 1
        s2 = re.sub(r'###\s*\d+(\.\d+)?', ' ', s)
        s2 = re.sub(r'§\d+(\.\d+)?', ' ', s2)
        s2 = re.sub(r'Appendix E\.?\d*', ' ', s2)
        seg_flat = re.sub(r'\s+', ' ', eseg)
        for t in re.findall(r'\d[\d,]*\.?\d*', s2):
            if t.replace(',', '') not in seg_flat.replace(',', ''):
                miss_all.append(t)
    chk('A2 引用 Appendix E 的 %d 句里全部数字都在 E 段' % ncited, not miss_all,
        '缺 %s' % sorted(set(miss_all)))

    # ── A3 口径上下文白名单（全文正则扫描） ───────────────────────────────
    print('\n[A3] 主稿每处 "N pp" 声称的同句口径检查（全文扫描 + 上下文白名单）')
    chk('A3 白名单登记表带 reviewed_on 与政策', bool(wl.get('reviewed_on')) and bool(wl.get('policy')), '')
    rules = wl['rules']
    sents = re.split(r'(?<=[.!?])\s+', re.sub(r'\s+', ' ', en))
    n_pp = 0
    bad = []
    cover = {r['id']: 0 for r in rules}
    for s in sents:
        if not re.search(r'\d[\d.,]*\s*pp\b', s):
            continue
        n_pp += 1
        if any(c.lower() in s.lower() for c in CALIBER):
            continue
        hit = [r['id'] for r in rules if re.search(r['pattern'], s, re.I)]
        if hit:
            for h in hit:
                cover[h] += 1
            continue
        bad.append(s.strip()[:160])
    chk('A3 含 "pp" 的 %d 句全部有口径词或命中登记语境' % n_pp, not bad,
        '；'.join(bad[:3]))
    print('       规则覆盖：%s' % ' ｜ '.join('%s=%d' % (k, v) for k, v in cover.items() if v))
    if n_pp:
        top = max(cover.values()) if cover else 0
        chk('A3 单条规则覆盖 %d/%d 未超 60%%（防空断言/橡皮图章）' % (top, n_pp),
            top <= 0.6 * n_pp, '最大覆盖率 %.0f%%' % (100.0 * top / n_pp))
    return fail


def main():
    if '--selftest' in sys.argv:
        print('=' * 100)
        print('■ 阳性对照：注入 (a) 孤立量级（必须 FAIL）与 (b) 带口径同句（必须不新增 FAIL）')
        print('=' * 100)
        en = io.open(EN, encoding='utf-8', newline='').read()
        baseline = run(None, None)
        inj_a = en + '\n\nThe detector ladder spans 12.3 pp here.\n'
        na = run(inj_a, None)
        inj_b = inj_a + '\nUnder the all-detections caliber the detector ladder spans 12.3 pp here.\n'
        nb = run(inj_b, None)
        print('\n  未注入 → 失败 %d 项；注入孤立量级 → %d 项；再注入带口径句 → %d 项'
              % (baseline, na, nb))
        oka, okb = na > baseline, nb == na
        print('  (a) 孤立量级被拦：%s' % ('✓' if oka else '✗ 空断言'))
        print('  (b) 带口径句不误报：%s' % ('✓' if okb else '✗ 误报'))
        print('  结论：%s' % ('★ 门禁能失败且不误报，阳性对照通过 ✓' if (oka and okb)
                            else '★ 阳性对照未通过，必须重写'))
        return 0 if (oka and okb) else 1
    print('=' * 100)
    print('■ anchor_aux.py：F.9 转录校验 + 附录 E 回源 + 口径上下文白名单')
    print('=' * 100)
    f = run(None, None)
    print('\nA1–A3 锚点校验：%d 通过 ｜ %d 失败' % (ok, fail))
    if f:
        print('失败项：%s' % '；'.join(FAILD))
    return 1 if f else 0


if __name__ == '__main__':
    raise SystemExit(main())
