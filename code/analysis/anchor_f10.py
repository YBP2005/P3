# -*- coding: utf-8 -*-
"""anchor_f10.py —— **F.10 的常设锚点门禁**（补上一条此前完全空白的覆盖）。

## 为什么需要它
2026-09-24 夜查出 F.10 的表值来自**跨口径相减**（`span_equalcount.py` 建检测 τ 阶梯时没过滤
`match` 列，把 person 与 allclass 两种口径交错放进同一条阶梯，于是"跨度"＝allclass 最大 − person 最小，
"档数"被算成两倍）。**这个错误活了很久，因为没有任何门禁覆盖附录 F 的表格数值**：
`en_check` [F] 只查**主稿**的数字溯源；`anchor_m40m41.py` 只覆盖 M.40/M.41。

本门禁把 F.10 表与正文里的每个数，逐格对回冻结件 `span_equalcount2_result.json`（由
`span_equalcount2.py` 按口径分开重算并冻结）。**不登记即失败**，与 `anchor_m40m41.py` 同一机制。

## 它必须能失败（阳性对照见 `--selftest`）
`--selftest` 会故意把冻结件里的一个值改掉（在内存里），并要求本门禁**报出失败**；
若它仍然全过，说明这是永真断言，必须重写。

用法：python -u anchor_f10.py [--selftest]
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

sys.stdout.reconfigure(encoding='utf-8')
W = RP('analysis', 'work')
SUP = RP('PaperB_英文补充材料_PR_20260919.md')
EN = RP('PaperB_英文稿_PR_20260919.md')
FROZEN = RP('analysis', 'work', 'span_equalcount2_result.json')

ok = fail = 0
FAILD = []


def chk(name, cond, detail=''):
    global ok, fail
    if cond:
        ok += 1
        print('  [OK  ] %s' % name)
    else:
        fail += 1
        FAILD.append(name)
        print('  [FAIL] %s   %s' % (name, detail))


def run(frozen, verbose=True):
    global ok, fail, FAILD
    ok = fail = 0
    FAILD = []
    sup = io.open(SUP, encoding='utf-8', newline='').read()
    en = io.open(EN, encoding='utf-8', newline='').read()
    seg = sup[sup.index('### F.10 '):sup.index('### F.11 ')] if '### F.11 ' in sup else \
        sup[sup.index('### F.10 '):]
    P = frozen['person']['units']
    A = frozen['allclass']['units']

    def u(lst, key):
        for x in lst:
            if key in x['unit']:
                return x
        return None

    # ① 表内 6 个检测行：档数、两种口径的全长与等点数跨度、保留率
    rows = [('Detector $\\tau$, in-domain / VisDrone (imgsz 1536)', '域内', 'tau@1536'),
            ('Detector $\\tau$, in-domain / VisDrone (imgsz 1024)', '域内', 'tau@1024'),
            ('Detector $\\tau$, in-domain / VisDrone (imgsz 640)', '域内', 'tau@640'),
            ('Detector $\\tau$, zero-shot COCO (imgsz 1536)', 'COCO', 'tau@1536'),
            ('Detector $\\tau$, zero-shot COCO (imgsz 1024)', 'COCO', 'tau@1024'),
            ('Detector $\\tau$, zero-shot COCO (imgsz 640)', 'COCO', 'tau@640')]
    for label, para, knob in rows:
        line = [l for l in seg.splitlines() if l.startswith('| ' + label)]
        chk('F.10 表行存在：%s' % label, bool(line), '未找到该行')
        if not line:
            continue
        cells = [c.strip().strip('*') for c in line[0].strip('|').split('|')]
        p = u(P, '%s / VisDrone / %s' % (para, knob))
        a = u(A, '%s / VisDrone / %s' % (para, knob))
        chk('  档数 = person 口径档数（%s，应为 %d 而非双倍）' % (label.split('/')[0].strip(), p['n']),
            cells[1] == str(p['n']), '表内 %s vs 冻结 %d' % (cells[1], p['n']))
        full = [x for x in cells[2].split('/')]
        chk('  全长跨度 = %s / %s' % (fmt(p['span']), fmt(a['span'])),
            len(full) == 2 and near(full[0], p['span']) and near(full[1], a['span']), '表内 %s' % cells[2])
        eq = cells[3].replace('*', '').split('/')
        chk('  等点数跨度 = %s / %s' % (fmt(p['span_eq']), fmt(a['span_eq'])),
            len(eq) == 2 and near(eq[0], p['span_eq']) and near(eq[1], a['span_eq']), '表内 %s' % cells[3])
        ret = cells[4].split('/')
        chk('  保留率 = %.2f / %.2f' % (p['span_eq'] / p['span'], a['span_eq'] / a['span']),
            len(ret) == 2 and near(ret[0], p['span_eq'] / p['span'])
            and near(ret[1], a['span_eq'] / a['span']), '表内 %s' % cells[4])

    # ② 非检测行不受口径影响（两种口径下必须同值）
    for label, key in (('Density regression, input multiplier / st_a', 'density / st_a / mult'),
                       ('Tiling / st_a', 'tiling / st_a / base'),
                       ('Pixel budget (res_ctrl) / q32 / visdrone', 'pxbudget(res_ctrl) / q32 / visdrone')):
        p, a = u(P, key), u(A, key)
        chk('非检测行两口径同值：%s' % label, p and a and p['span'] == a['span'],
            '%s vs %s' % (p['span'] if p else None, a['span'] if a else None))
        line = [l for l in seg.splitlines() if l.startswith('| ' + label)]
        chk('  表内跨度 = %s / —' % fmt(p['span']),
            bool(line) and near(line[0].strip('|').split('|')[2].strip().split('/')[0], p['span']),
            line[0].strip('|').split('|')[2].strip() if line else '未找到行')

    # ③ 正文里的秩相关三元组、倍率、保留率
    sseg = squash(seg)
    trio_p = '**%.3f** (equal-count), **%.3f** (highest level dropped) and **%.3f** (lowest level dropped) person-matched' \
             % (frozen['person']['spearman_span_eq'], frozen['person']['spearman_span_drop_high'],
                frozen['person']['spearman_span_drop_low'])
    chk('F.10 正文秩相关三元组（person）', trio_p in sseg, '未找到：%s' % trio_p)
    trio_a = '**%.3f / %.3f / %.3f** all-detections' % (
        frozen['allclass']['spearman_span_eq'], frozen['allclass']['spearman_span_drop_high'],
        frozen['allclass']['spearman_span_drop_low'])
    chk('F.10 正文秩相关三元组（all-det）', trio_a in sseg, '未找到：%s' % trio_a)
    chk('F.10 正文口径倍率 3.5–5.3×', '**3.5–5.3×**' in sseg, '未找到 3.5–5.3×')
    chk('F.10 正文量化等点数保留率（1.00 / 最差 0.74）',
        'median retention **1.00**, worst case **0.74**' in sseg, '未找到量化等点数保留率措辞')
    chk('F.10 正文已声明口径不可相减', 'not the same quantity' in sseg and 'within one caliber at a time' in sseg,
        '未找到口径声明')

    # ③b 随机删档那一句：数值必须与两个冻结件**逐项复算**一致（2026-09-24 夜新增）。
    #     ★ 加这一段的直接原因：写它的时候就查出一处不一致——正文写的 all-detections 六条阶梯中位
    #       区间是 0.52–0.57，而冻结件复算出来是 0.52–0.66（漏了域内三条）。数字靠复算，不靠记忆。
    dr = json.loads(io.open(RP('analysis', 'work', 'f10_random_drop_result.json'), encoding='utf-8').read())
    do = json.loads(io.open(RP('analysis', 'work', 'f10_random_drop_order_result.json'), encoding='utf-8').read())
    drng = {}
    for cal in ('person', 'allclass'):
        ms = [x['median'] for x in dr['per_caliber'][cal].values()]
        drng[cal] = (min(ms), max(ms))
    chk('F.10 随机删档 person 六条中位区间 = %.2f–%.2f'
        % drng['person'], '**%.2f–%.2f**' % drng['person'] in sseg,
        '冻结件 %.2f–%.2f ｜ 正文 %s' % (drng['person'][0], drng['person'][1],
                                      [t for t in re.findall(r'\*\*0\.\d+–0\.\d+\*\*', sseg)][:6]))
    chk('F.10 随机删档 all-det 六条中位区间 = %.2f–%.2f'
        % drng['allclass'], '**%.2f–%.2f**' % drng['allclass'] in sseg,
        '冻结件 %.2f–%.2f' % drng['allclass'])
    ur = do['per_caliber']['person']['unit_retention']
    for lab, val in (('24 单元保留率中位 %.2f' % ur['median'], '**%.2f**' % ur['median']),
                     ('24 单元 5 分位 %.2f' % ur['p05'], '**%.2f**' % ur['p05']),
                     ('24 单元最小值 %.2f' % ur['minimum'], '**%.2f**' % ur['minimum']),
                     ('24 单元 ≥90%% 的抽样占比 %.0f%%' % (100 * ur['frac_ge_090']),
                      '**%.0f%%**' % (100 * ur['frac_ge_090']))):
        chk('F.10 随机删档 %s 在文中' % lab, val in sseg, '未找到 %s' % val)
    os_ = do['per_caliber']
    chk('F.10 随机删档排序中位三元组（%.3f / %.3f）'
        % (os_['person']['ordering_spearman']['median'], os_['allclass']['ordering_spearman']['median']),
        ('**%.3f** (person) / **%.3f** (all-detections)'
         % (os_['person']['ordering_spearman']['median'],
            os_['allclass']['ordering_spearman']['median'])) in sseg, '未找到排序中位措辞')
    chk('F.10 随机删档排序 5–95% 区间',
        ('**[%.3f, %.3f]** / **[%.3f, %.3f]**'
         % (os_['person']['ordering_spearman']['p05'], os_['person']['ordering_spearman']['p95'],
            os_['allclass']['ordering_spearman']['p05'], os_['allclass']['ordering_spearman']['p95'])) in sseg,
        '未找到区间措辞')
    chk('F.10 随机删档排序最小 %.3f / %.3f'
        % (os_['person']['ordering_spearman']['minimum'], os_['allclass']['ordering_spearman']['minimum']),
        ('**%.3f** / **%.3f**' % (os_['person']['ordering_spearman']['minimum'],
                                  os_['allclass']['ordering_spearman']['minimum'])) in sseg,
        '未找到最小值措辞')

    # ④ 旧错值只能出现在"已撤回"的句子里
    for toks, why in ((['593.7', '258.2', '515.4', '231.9', '407.5', '182.1'], '跨口径相减的假跨度'),
                      (['2.2–2.3', '5–10×', '2.2–5.0×'], '被撤的缩小倍率'),
                      (['0.964', '0.993'], '旧秩相关（24 单元，口径混用）')):
        bad = retracted_ok(sup, toks)
        chk('旧错值仅在撤回句中：%s' % why, not bad, '出现在非撤回句：%s' % (' ｜ '.join(bad))[:200])
        bad_en = retracted_ok(en, toks)
        chk('  主稿内不得出现（%s）' % why, not bad_en, '主稿内出现：%s' % (' ｜ '.join(bad_en))[:160])
    # 0.977 从"旧错值"变成了**新量**：随机删档下的排序保全中位（all-detections）。同数不同义，
    # 因此判据改成**上下文判据**：每一句含 0.977 的句子必须落在 random 删除语境或撤回句里。
    bad977 = [s.strip()[:90] for s in re.split(r'(?<=[.;])\s+', sup.replace('\n', ' '))
              if '0.977' in s and not re.search(r'random|withdrawn|artefact|earlier version', s)]
    chk('0.977 只出现在随机删档/撤回语境', not bad977, '越界：%s' % (' ｜ '.join(bad977))[:200])

    # ⑤ 主稿同步：§7.3 的幅度句与秩相关
    chk('主稿 §7.3 口径句（caliber-portable + 96–196 / 353–508）',
        'caliber-portable' in en and '96–196 pp' in en and '353–508 pp' in en, '未找到')
    chk('主稿秩相关已同步为 0.981–0.999 / 0.999 / 0.981 / 0.991',
        '0.981–0.999' in en and '0.999 / 0.981 / 0.991' in en, '未找到')
    chk('主稿已无 portable/surviving 之外的旧措辞', '2.2–2.3' not in en and '5–10×' not in en, '仍有旧倍率')

    # ⑥ 冻结件本身自洽：等点数必取首尾 ⇒ 极值在端点的阶梯保留率应为 1.00
    for x in P:
        if 'tau' in x['unit'] and '域内' in x['unit']:
            chk('  %s 等点数=全长（首尾保留的结构性后果）' % x['unit'], abs(x['span_eq'] - x['span']) < 1e-9,
                '%s vs %s' % (x['span_eq'], x['span']))
    return fail


def fmt(v):
    """F.10 表内一律 1 位小数（与冻结件比对时也按 1 位小数四舍五入，避免 195.68 vs 195.7 的假失败）。"""
    return '%.1f' % v


def near(cell, v):
    try:
        return abs(float(cell) - v) < 0.051
    except (TypeError, ValueError):
        return False


def squash(s):
    return re.sub(r'\s+', ' ', s)


def retracted_ok(text, tokens, why_word=('withdrawn', 'artefact', 'earlier version')):
    """被撤的旧值**只能**出现在"已撤回"的句子里。

    这是本门禁里最容易写成空断言的一条：单纯断言"稿内不得出现 2.2–2.3"会失败——因为
    **撤回声明本身必须引用旧值**（"the apparent shrinkage that produced 2.2–2.3× … is withdrawn"）。
    ⇒ 正确判据是**上下文判据**：每一个含该 token 的句子，都必须同时含 withdrawn/artefact/earlier version。
    """
    bad = []
    for sent in re.split(r'(?<=[.;])\s+', text.replace('\n', ' ')):
        if any(t in sent for t in tokens) and not any(w in sent for w in why_word):
            bad.append(sent.strip()[:90])
    return bad


def main():
    frozen = json.loads(io.open(FROZEN, encoding='utf-8').read())
    print('=' * 100)
    print('■ F.10 锚点门禁（对照冻结件 span_equalcount2_result.json）')
    print('=' * 100)
    if '--selftest' in sys.argv:
        print('\n★ 阳性对照：把冻结件里 person/tau@1536 的长跨度改掉，门禁**必须**报失败。')
        n0 = run(frozen, verbose=False)
        bad = json.loads(json.dumps(frozen))
        for x in bad['person']['units']:
            if '域内' in x['unit'] and 'tau@1536' in x['unit']:
                x['span'] += 7.0
        n1 = run(bad, verbose=False)
        print('  未篡改 → 失败 %d 项；篡改后 → 失败 %d 项' % (n0, n1))
        print('  结论：%s' % ('★ 门禁**能失败**，阳性对照通过 ✓' if n1 > n0 else '★ 不能失败 ⇒ 是空断言，必须重写'))
        return 0 if n1 > n0 else 1
    f = run(frozen)
    print('\nF.10 锚点校验：%d 通过 ｜ %d 失败' % (ok, fail))
    if f:
        print('失败项：%s' % '；'.join(FAILD))
    return 1 if f else 0


if __name__ == '__main__':
    raise SystemExit(main())
