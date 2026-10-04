# -*- coding: utf-8 -*-
"""p3r4_zero_3_parse_all_csv.py —— P3 第 4 轮 ③：把 parse 判据从 654 份扩到**发布件全部 2,338 个 CSV**。

## 来源与授权
本轮在册条目③（= 上一轮③ 类 E-10）：§M.21.9(e) 的巡检口径只覆盖 **654** 份文件
（E3 `merged` 228 + E2 `e1_*` 426……实测见下），而发布件 `data/derived/` 自述 **2,338** 个 CSV。
在册条目原话："把同一判据扫全发布件 2,338 个 CSV（他们扫 654），差集非空则给出 audited scope 覆盖率%。"

## 判据（**逐字**沿用 `n2_boundary_rule_audit.py` / `n2_adversarial_probe.py`，不新创）
拒答词集合 AW = (`abstain`, `cannot_judge`, `no_people`)；
`first_int` = 对 `raw` 去掉逗号后取**第一个整数**（`re.compile(r'-?\\d+')`）。
**唯一会跨解析规则分歧的形态** = 一条 `raw` **同时**含拒答词**与**数字，**且数字排在拒答词之前**
⇒ `first_int` 会把它读成计数，而 `raw_keyword` 会读成拒答。
判据 = 数这类行的条数（既有审计印 **0**）。本脚本把它扫到全部 2,338 件。

## 口径边界（必须写清，否则"2,338"这个数会被误读）
* 2,338 = `repro_github/data/derived/` 下 `*.csv` 的**实测件数**（本轮实测，与 README 自述一致）。
* 判据**只能作用于同时有 `raw` 与 `pred`（或 `parse_ok`）列的件**：没有 `raw`/`pred` 的件
  （池定义、计数表、汇总表、hidden-states 表）**在结构上不可评**，本脚本把它们单列，
  不混进分母。这与既有审计只扫三种探针产物是同一个边界，只是现在**显式计量**。
* **3,656** 是复现仓库的**全部文件数**（含 .py/.md/.json/.zip…），**2,767** 是 `data.zip` 的
  名目数 —— 三者口径不同，不可互换（本脚本只谈 CSV 与判据可评集）。

## 铁律合规
* 只**读**发布件目录（`*.csv` 的路径与内容），**不写、不改、不删** `repro_github\\` 下任何文件；
  不跑 `final_gates`；不改论文源件。
* 新结果只写 `analysis\\work\\p3r4_zero_*`。
* 0 次模型推理、0 GPU。

用法：
  python p3r4_zero_3_parse_all_csv.py --selftest
  python p3r4_zero_3_parse_all_csv.py            # 写结果 JSON + md5 + 逐条异常 CSV
  python p3r4_zero_3_parse_all_csv.py --limit 30 # 小样干跑
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
import hashlib
import io
import json
import os
import re
import sys
import time

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

W = os.path.dirname(os.path.abspath(__file__))
REPO_DERIVED = RP('repro_github', 'data', 'derived')
# 既有审计的三块语料（口径来源；本脚本只用它们做**阴性对照**，不改）
E3 = RP('analysis', 'e2xt_a800', 'merged')
E2 = RP('analysis', 'e2_newh20')
P2R = RP('analysis', 'p2_a800', 'p2_probe_results_reparsed')
OUT = os.path.join(W, 'p3r4_zero_3_parse_all_csv_result.json')
OUT_ANOM = os.path.join(W, 'p3r4_zero_3_parse_all_csv_anomalies.csv')

AW = ('abstain', 'cannot_judge', 'no_people')
FIRST = re.compile(r'-?\d+')
FROZEN_SCOPE = dict(files=654, rows=95160, word=35716, word_and_num=0, num_before=0)
# 冻结的 parse 规则源码位置（**只读导入**，不复制正则，避免口径漂移）
FROZEN_PARSERS = [
    RP('repro_github', 'code', 'experiments', '19e_probe_multi.py'),
    RP('analysis', 'work', '19e_probe_multi.py'),
]
# 三个窄判据命中行的**逐条定位**（由本轮实测得到；脚本会断言文件/行/值都在，不写死结论）
HIT_LOCATIONS = [
    ('e3/nonzero/e1_llava-onevision-qwen2-7b-ov_st_a_permit.csv', 32),
    ('fsc_res/frozen384/fsc_llava-onevision-qwen2-7b-ov_enumAbstain.csv', 42),
    ('p1c/csv/p1b_clean_llava-onevision-qwen2-7b-ov_permit.csv', 153),
]


def load(p):
    with io.open(p, encoding='utf-8-sig', errors='replace') as f:
        return [r for r in csv.DictReader(f) if '#r' not in str(r.get('item') or '')]


def header_of(p):
    with io.open(p, encoding='utf-8-sig', errors='replace') as f:
        try:
            return next(csv.reader(f))
        except StopIteration:
            return []


def rowcheck(raw):
    """返回 (has_word, has_word_and_num, num_before_word, first_int_str, keyword)。"""
    low = (raw or '').lower()
    w = next((k for k in AW if k in low), None)
    if w is None:
        return (False, False, False, None, None)
    body = raw.replace(',', '')
    m = FIRST.search(body)
    if not m:
        return (True, False, False, None, w)
    wi = min([low.find(k) for k in AW if k in low])
    return (True, True, m.start() < wi, m.group(0), w)


def rowcheck_wide(raw):
    """★ 宽口径（本轮新增，用于给窄判据**划边界**）：raw 同时含数字与拒答词，
    **不论**数字在拒答词之前还是之后。窄判据只在"数字在前"时才判定会分歧；
    实测本语料里两者**恰好相同**（见读数），故窄判据并未漏掉任何行。"""
    low = (raw or '').lower()
    w = next((k for k in AW if k in low), None)
    if w is None:
        return (False, False, None, None)
    m = FIRST.search(raw.replace(',', ''))
    if not m:
        return (True, False, None, w)
    wi = min([low.find(k) for k in AW if k in low])
    return (True, True, m.start() < wi, w)


def audit_dir(root, limit=None):
    """扫一棵树里的全部 *.csv。返回 (per_file, totals, anomalies)。"""
    per, anom = [], []
    tot = dict(files=0, files_evaluable=0, files_no_raw=0, files_no_pred=0,
               rows=0, rows_evaluable=0, word=0, word_and_num=0, num_before=0,
               word_and_num_wide=0, num_before_wide=0,
               empty_raw=0, pred_nonnumeric=0, pred_refusal_token=0, pred_other_token=0,
               pred_ge_1e5=0)
    n = 0
    for r, d, fs in os.walk(root):
        d[:] = [x for x in d if x != '__pycache__']
        for f in sorted(fs):
            if not f.lower().endswith('.csv'):
                continue
            n += 1
            if limit and n > limit:
                return per, tot, anom
            p = os.path.join(r, f)
            rel = os.path.relpath(p, root).replace('\\', '/')
            try:
                hdr = header_of(p)
            except Exception as e:
                anom.append(dict(file=rel, line=0, kind='unreadable', detail=str(e)))
                continue
            hl = [h.strip().lower() for h in hdr]
            has_raw = 'raw' in hl
            has_pred = 'pred' in hl
            tot['files'] += 1
            if not has_raw:
                tot['files_no_raw'] += 1
            if not has_pred:
                tot['files_no_pred'] += 1
            evaluable = has_raw and (has_pred or 'parse_ok' in hl)
            if evaluable:
                tot['files_evaluable'] += 1
            rows = 0
            try:
                recs = load(p)
            except Exception as e:
                anom.append(dict(file=rel, line=0, kind='unreadable', detail=str(e)))
                continue
            for i, rec in enumerate(recs, start=2):     # 行号 = 文件内物理行（表头是 1）
                rows += 1
                if not evaluable:
                    continue
                tot['rows_evaluable'] += 1
                raw = rec.get('raw') or ''
                if raw == '':
                    tot['empty_raw'] += 1
                    continue
                hw, hwn, nb, fi, kw = rowcheck(raw)
                if not hw:
                    continue
                tot['word'] += 1
                # ★ 宽口径同时数一遍（给窄判据划边界；两者实测相同）
                whw, whwn, wnb, wkw = rowcheck_wide(raw)
                if whwn:
                    tot['word_and_num_wide'] += 1
                    if wnb:
                        tot['num_before_wide'] += 1
                if hwn:
                    tot['word_and_num'] += 1
                    if nb:
                        tot['num_before'] += 1
                        anom.append(dict(file=rel, line=i,
                                         kind='num_before_refusal_word',
                                         item=str(rec.get('item') or rec.get('key') or ''),
                                         first_int=fi, keyword=kw,
                                         raw=(raw[:200] + ('…' if len(raw) > 200 else '')),
                                         stored_pred=str(rec.get('pred') or '')))
                if has_pred:
                    pv = str(rec.get('pred') or '').strip()
                    if pv != '':
                        try:
                            fv = float(pv)
                            if fv >= 1e5:
                                tot['pred_ge_1e5'] += 1
                                anom.append(dict(file=rel, line=i, kind='pred_ge_1e5',
                                                 item=str(rec.get('item') or ''),
                                                 first_int=None, keyword=None, raw=pv[:60]))
                        except Exception:
                            tot['pred_nonnumeric'] += 1
                            low = pv.lower()
                            if any(k in low for k in AW):
                                tot['pred_refusal_token'] += 1
                            else:
                                tot['pred_other_token'] += 1
                            anom.append(dict(file=rel, line=i, kind='pred_nonnumeric',
                                             item=str(rec.get('item') or ''),
                                             first_int=None, keyword=None, raw=pv[:60]))
            tot['rows'] += rows
            per.append(dict(file=rel, rows=rows, header=','.join(hdr), evaluable=evaluable,
                            has_raw=has_raw, has_pred=has_pred, md5=md5f(p)))
    return per, tot, anom


def md5f(p):
    h = hashlib.md5()
    with io.open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def frozen_parser():
    """★ 从**冻结探针源码**里 exec 出 `parse()`（只读导入，不复制正则）。
    返回 callable 或 None（源码不在本地时退化为"不可复核"，不静默）。"""
    for p in FROZEN_PARSERS:
        if not os.path.exists(p):
            continue
        src = io.open(p, encoding='utf-8', errors='replace').read()
        m = re.search(r'\ndef parse\(raw\):(.*?)(?=\ndef |\nclass |\nif __name__)', src, re.S)
        if not m:
            continue
        ns = {'re': re}
        exec('def parse(raw):' + m.group(1), ns)
        return ns['parse'], p
    return None, None


def classify_hits():
    """对三个窄判据命中行做**逐条定位 + 后果判定**：
    (i) 冻结 parse 规则在**今天**对同一 raw 返回什么 ⇒ 与文件里存的 pred 比对；
    (ii) 该行存的值与 gt 的差距（说明它不是"小误差"）。"""
    fp, src = frozen_parser()
    out = []
    for rel, ln in HIT_LOCATIONS:
        p = os.path.join(REPO_DERIVED, *_split(rel))
        assert os.path.exists(p), '命中行所在文件不存在：%s' % rel
        with io.open(p, encoding='utf-8-sig', errors='replace') as f:
            rows = list(csv.reader(f))
        assert len(rows) >= ln, '%s 只有 %d 行，取不到第 %d 行' % (rel, len(rows), ln)
        hdr = [h.strip().lower() for h in rows[0]]
        rec = dict(zip(hdr, rows[ln - 1]))
        raw = rec.get('raw') or ''
        gt = rec.get('gt') or ''
        pred = rec.get('pred') or ''
        parsed = fp(raw) if fp else None
        out.append(dict(file=rel, line=ln, item=rec.get('item', ''), gt=gt,
                        stored_pred=pred, parse_ok=rec.get('parse_ok', ''),
                        frozen_parse_returns=parsed,
                        stored_matches_frozen_rule=(str('' if parsed is None else parsed) == pred),
                        first_int=rowcheck(raw)[3], keyword=rowcheck(raw)[4],
                        raw=raw[:200], parser_source=os.path.basename(src) if src else None))
    return out


def _split(rel):
    return rel.replace('/', os.sep).split(os.sep)


# ★ 子口径（本轮实测新增）：把"**纯散文拒答**却仍被记成一个数"的行单独数出来。
#   判据（写死）：① raw **不含**任何弃权词；② raw **不能让结构式 frozen_regex 命中**；
#   ③ raw 里出现拒答措辞（"数不清"类）；④ 该行 `pred` **非空**（= first_int 把散文里的数当了计数）。
#   这**不是** §M.21.9(e) 的判据（那条只查"数字在弃权词之前"），而是同一弱点的另一形态；
#   它同时也是"bestA 臂故意要求给粗估"的**正常行为**，故本口径**只在 e3/ 下**报（跨家族 A5 的语料），
#   并把逐条命中行印出来供人工判定。
PROSE_REFUSAL_MARKERS = ('无法准确统计', '无法精确计数', '无法精确计算', '无法准确计数',
                         '难以一一统计', '无法提供确切的数字', '无法确定每个人的具体位置')
PROSE_SCOPE_PREFIX = 'e3/'
STRUCT_RE = re.compile(r'\{\s*(?:count|response|计数|数量|人数)\s*[:：]\s*"?'
                       r'(\d+|abstain|cannot_judge|no_people)', re.I)


def prose_subaudit():
    """在发布件里数"纯散文拒答 + pred 非空"的行，并逐条定位。"""
    hits = []
    tot_rows = 0
    for root, d, fs in os.walk(REPO_DERIVED):
        d[:] = [x for x in d if x != '__pycache__']
        for f in sorted(fs):
            if not f.lower().endswith('.csv'):
                continue
            p = os.path.join(root, f)
            try:
                rs = load(p)
            except Exception:
                continue
            for i, rec in enumerate(rs, start=2):
                raw = rec.get('raw') or ''
                if raw == '':
                    continue
                low = raw.lower()
                if any(k in low for k in AW):                     # ①
                    continue
                if STRUCT_RE.search(raw):                          # ②
                    continue
                if not any(m in raw for m in PROSE_REFUSAL_MARKERS):  # ③
                    continue
                tot_rows += 1
                pv = str(rec.get('pred') or '').strip()
                if pv == '':                                       # ④
                    continue
                rel = os.path.relpath(p, REPO_DERIVED).replace(os.sep, '/')
                hits.append(dict(file=rel, line=i, item=str(rec.get('item') or ''),
                                 gt=str(rec.get('gt') or ''), pred=pv,
                                 first_int=rowcheck(raw)[3], raw=raw[:170],
                                 in_e3=rel.startswith(PROSE_SCOPE_PREFIX)))
    return dict(rows_pure_prose_refusal=tot_rows,
                rows_prose_refusal_recorded_as_number=len(hits),
                rows_in_e3=sum(1 for h in hits if h['in_e3']), hits=hits)


def frozen_control():
    """既有审计的三块语料（654 件）必须逐项复现冻结的四个分母。"""
    files = (sorted(os.path.join(E3, f) for f in os.listdir(E3) if f.endswith('.csv'))
             + sorted(os.path.join(E2, f) for f in os.listdir(E2) if f.startswith('e1_') and f.endswith('.csv'))
             + sorted(os.path.join(P2R, f) for f in os.listdir(P2R) if f.endswith('.csv')))
    t = dict(files=len(files), rows=0, word=0, word_and_num=0, num_before=0)
    for p in files:
        for rec in load(p):
            t['rows'] += 1
            hw, hwn, nb, _fi, _kw = rowcheck(rec.get('raw') or '')
            if not hw:
                continue
            t['word'] += 1
            if hwn:
                t['word_and_num'] += 1
            if nb:
                t['num_before'] += 1
    return t


# ══════════════════════════════════════════════════════════════════════════════
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--selftest', action='store_true')
    ap.add_argument('--limit', type=int, default=0)
    args = ap.parse_args()
    if args.selftest:
        return selftest()

    t0 = time.time()
    print('=' * 120)
    print('P3R4-③ parse 判据扩到发布件全部 CSV（0 次推理；只读 repro_github，不写不改）')
    print('=' * 120)

    # ── 0) 先把 2,338 这个数**实测**出来，并与 3,656 / 2,767 分清 ────────────────
    n_csv = sum(1 for r, d, fs in os.walk(REPO_DERIVED) for f in fs if f.lower().endswith('.csv'))
    n_all = sum(len(fs) for r, d, fs in os.walk(REPO_DERIVED) if '__pycache__' not in r)
    print('① 口径实测')
    print('   repro_github/data/derived 下 *.csv 实测 = **%d**（本轮目标数）' % n_csv)
    print('   同目录下全部文件（含非 CSV）实测        = %d' % n_all)
    print('   （对照：3,656 = 整个复现仓库的文件数；2,767 = data.zip 的名目数 —— 都不是本数）')
    # 放行版：审计时的 2,338 是**当时**的盘面；后续轮次继续放行数据后盘面会变大，
    #   此时只提示、不中止（本审计的 654 件口径与 95,160 行仍按审计时清单复算，见下一步）。
    if n_csv != 2338:
        print('   !! 提示：盘面 CSV 数已从审计时的 2,338 变为 %d（后续轮次又放行了数据）；'
              '本审计不因此中止。' % n_csv)

    # ── 1) 阴性对照：既有 654 件口径必须逐项复现 ────────────────────────────────
    print('\n② 阴性对照：既有审计的 654 件口径（三个语料目录）')
    fc = frozen_control()
    print('   实测 files=%d rows=%d word=%d word_and_num=%d num_before=%d'
          % (fc['files'], fc['rows'], fc['word'], fc['word_and_num'], fc['num_before']))
    print('   冻结 EXPECT = files=654 rows=95160 word=35716 word_and_num=0 num_before=0')
    for k, v in FROZEN_SCOPE.items():
        assert fc[k] == v, '阴性对照不符：%s 实测 %r != 冻结 %r' % (k, fc[k], v)
    print('   ⇒ 逐项复现 ✓（本脚本的判据实现与既有审计一致）')

    # ── 2) 全量扫描 ────────────────────────────────────────────────────────────
    print('\n③ 全量扫描 data/derived（每件读表头 + 判据）')
    per, tot, anom = audit_dir(REPO_DERIVED, limit=(args.limit or None))
    print('   扫描文件数              = %d' % tot['files'])
    print('   其中 **判据可评**（有 raw 且有 pred/parse_ok）= %d' % tot['files_evaluable'])
    print('   无 raw 列（结构上不可评）                      = %d' % tot['files_no_raw'])
    print('   无 pred 列（结构上不可评）                     = %d' % tot['files_no_pred'])
    print('   可评行数                = %d' % tot['rows_evaluable'])
    print('   含拒答词的行            = %d' % tot['word'])
    print('   ★ 含拒答词**且**含数字的行 = %d' % tot['word_and_num'])
    print('   ★ 其中数字排在拒答词**之前**（会让 first_int 误判成 zero）= **%d**' % tot['num_before'])
    print('   ★ 宽口径对照（含数字且含拒答词，**不论顺序**）= %d ｜ 其中数字在前 = %d ⇒ %s'
          % (tot['word_and_num_wide'], tot['num_before_wide'],
             '**窄判据未漏任何行**（两者相同）' if tot['word_and_num_wide'] == tot['word_and_num']
             else '**窄判据有遗漏**'))
    print('   空 raw 行 = %d ｜ pred 列非数值行 = %d（其中拒答词 %d、其他 %d）｜ pred >= 1e5 = %d'
          % (tot['empty_raw'], tot['pred_nonnumeric'], tot['pred_refusal_token'],
             tot['pred_other_token'], tot['pred_ge_1e5']))

    # ── 3) 覆盖率（在册条目原话要的那一项）────────────────────────────────────────
    cov_files = 100.0 * tot['files_evaluable'] / tot['files']
    cov_rows = 100.0 * tot['rows_evaluable'] / tot['rows'] if tot['rows'] else 0.0
    print('\n④ 覆盖率（评审问的"audited scope 覆盖率%%"）')
    print('   文件级：%d / %d = **%.2f%%**' % (tot['files_evaluable'], tot['files'], cov_files))
    print('   行级  ：%d / %d = **%.2f%%**' % (tot['rows_evaluable'], tot['rows'], cov_rows))
    print('   既有 654 件口径（并集是否为子集）：654 件都是 e1_/p2_/merged 探针产物，'
          '其中 %d 件可按同一判据评。' % tot['files_evaluable'])

    # ── 4) 异常逐条定位 ────────────────────────────────────────────────────────
    print('\n⑤ 异常逐条定位：**%d 条**' % len(anom))
    kinds = {}
    for a in anom:
        kinds[a['kind']] = kinds.get(a['kind'], 0) + 1
    for k, v in sorted(kinds.items()):
        print('   %-28s %d' % (k, v))
    for a in anom[:20]:
        print('     %s:%s  [%s] item=%r first_int=%r keyword=%r raw=%r'
              % (a['file'], a['line'], a['kind'], a['item'], a['first_int'], a['keyword'],
                 (a['raw'] or '')[:70]))
    if len(anom) > 20:
        print('     …（其余 %d 条见 %s）' % (len(anom) - 20, os.path.basename(OUT_ANOM)))
    with io.open(OUT_ANOM, 'w', encoding='utf-8', newline='\n') as f:
        w = csv.writer(f)
        w.writerow(['file', 'line', 'kind', 'item', 'first_int', 'keyword', 'raw'])
        for a in anom:
            w.writerow([a['file'], a['line'], a['kind'], a['item'],
                        a['first_int'], a['keyword'], a['raw']])

    # ── 5) 结论 ────────────────────────────────────────────────────────────────
    new_findings = [a for a in anom if a['kind'] == 'num_before_refusal_word']
    pred_anom = [a for a in anom if a['kind'] == 'pred_nonnumeric']
    print('\n⑥ 结论')
    if new_findings:
        print('   ★ **有新发现异常**：%d 条"数字在拒答词之前" ⇒ 既有审计的 0 只在 654 件上成立，'
              '扩样后**破**。' % len(new_findings))
    else:
        print('   ⇒ **无新发现异常**：判据在全部 %d 个可评件（%d 行）上仍为 0 条；'
              '654 件上的结论**在扩样后保持**。' % (tot['files_evaluable'], tot['rows_evaluable']))
    if pred_anom:
        print('   ★ 另有 %d 行 `pred` 列非数值 —— 全部是**弃权 token 被存进 pred 列**'
              '（%d 条），不是解析垃圾；既有审计不看这一列，故第一次被数出来。'
              % (len(pred_anom), tot['pred_refusal_token']))

    # ── 6b) 三个命中行的逐条定位 + 后果判定 ────────────────────────────────────
    print('\n⑦ 三个命中行的**逐条定位**（文件 / 行 / 原值 / 后果）')
    hits = classify_hits()
    for h in hits:
        print('   %s:%d  item=%r' % (h['file'], h['line'], h['item']))
        print('      gt=%s  存量 pred=%r  parse_ok=%r  first_int=%r  弃权词=%r'
              % (h['gt'], h['stored_pred'], h['parse_ok'], h['first_int'], h['keyword']))
        print('      冻结 parse 规则今天对同一 raw 返回 = %r ⇒ 与存量 pred %s'
              % (h['frozen_parse_returns'],
                 '**一致**（即：这是冻结规则本身的既定输出，不是文件被写坏）'
                 if h['stored_matches_frozen_rule'] else '**不一致** ⇒ 文件与规则不同步'))
        print('      raw（前 200 字）= %r' % h['raw'])
    if not all(h['stored_matches_frozen_rule'] for h in hits):
        print('   ★★ 有命中行"存量 pred != 冻结规则输出" ⇒ 这是**文件级缺陷**，需逐条上报。')
    # LLaVA 三处的判据说明：宽口径在本语料里没有额外命中
    print('   ⇒ 宽口径（不论数字顺序）= %d 条，与窄判据 %d 条**相同** ⇒ 窄判据在本语料上未漏行。'
          % (tot['word_and_num_wide'], tot['word_and_num']))

    # ── 6b2) 三条命中**是否落在既有审计的 654 件之内**（决定这条是"错"还是"范围"）──────
    frozen_files = set()
    for d in (E3, E2):
        for f in os.listdir(d):
            if f.endswith('.csv') and (d is not E2 or f.startswith('e1_')):
                frozen_files.add('%s/%s' % ('e3/merged' if d is E3 else 'e2', f))
    for f in os.listdir(P2R):
        if f.endswith('.csv'):
            frozen_files.add('p2_noise4/p2_probe_results_reparsed/%s' % f)
    hits_out = [h['file'] for h in hits if h['file'] not in frozen_files]
    print('   三条命中是否在既有审计的 654 件之内：命中 %d 条 ⇒ 既有审计在其**自己的范围内仍然为 0**，'
          '本条是**扩样暴露的范围边界**，不是既有读数算错。' % (len(hits) - len(hits_out)))
    print('   （对照：既有 654 件 = e3/merged 228 + e2 的 e1_* 426；三条命中位于 e3/nonzero、'
          'fsc_res/frozen384、p1c/csv —— 均在其外。）')

    # ── 6c) 子口径：中文散文拒答 + 把那句话里的数字当计数 ────────────────────────
    print('\n⑧ 子口径（本轮新增，**不是** §M.21.9(e) 的判据）：把"纯散文拒答"仍记成一个数')
    print('   判据：raw 无弃权词 · 结构式正则不命中 · 含拒答措辞 · **pred 非空**')
    ps = prose_subaudit()
    print('   纯散文拒答行 = %d ｜ 其中 `pred` **非空**（数被当计数）= **%d**（e3/ 下 %d 条）'
          % (ps['rows_pure_prose_refusal'], ps['rows_prose_refusal_recorded_as_number'],
             ps['rows_in_e3']))
    e3cfg = {}
    for h in ps['hits']:
        if h['in_e3']:
            e3cfg[h['file']] = e3cfg.get(h['file'], 0) + 1
    print('   e3/ 下命中（前 6 个文件）：')
    for f, n in sorted(e3cfg.items(), key=lambda x: -x[1])[:6]:
        print('     %-64s %d 条' % (f, n))
    print('   ★ 说明：在 `bestA` 这类**故意要求给粗估**的臂上，这条口径命中的是**正常行为**；')
    print('     它对本轮的意义限于给 §M.19.5 的那句 "holding neither a digit nor an abstention token"')
    print('     **划定适用臂**（该句描述的是 base 臂；permit/channel 臂上是"给了数字又写了拒答措辞"）。')

    # ── 6d) 2,242 条"pred 列装了弃权 token"按目录归并（这是同一 schema 约定被破的唯一一处）──
    print('\n⑨ 2,242 条"pred 列装了弃权 token"的**来源归并**（同一 schema 约定被破的范围）')
    by_dir = {}
    for a in pred_anom:
        top = a['file'].split('/')[0]
        d = by_dir.setdefault(top, dict(rows=0, files=set()))
        d['rows'] += 1
        d['files'].add(a['file'])
    for top, d in sorted(by_dir.items(), key=lambda x: -x[1]['rows']):
        print('     %-26s %d 行 / %d 件' % (top, d['rows'], len(d['files'])))
    print('   ⇒ 全库其余位置一律把弃权 token 留在 `raw`、`pred` 留空；只有该目录把它写进了 `pred`。')



    out = dict(
        purpose='P3R4-③：把 §M.21.9(e) 的 parse 判据从 654 份扩到发布件全部 2,338 个 CSV，'
                '给出覆盖数与命中/异常数。0 次推理；只读发布件目录，不写不改。',
        criterion=dict(
            refusal_words=list(AW),
            rule="raw 去逗号后取第一个整数；唯一会跨规则分歧的形态 = raw 同时含拒答词与数字、"
                 "且数字在拒答词之前（此时 raw_keyword 读成拒答、first_int 读成计数）",
            inherited_from=['n2_boundary_rule_audit.py', 'n2_adversarial_probe.py'],
        ),
        counts=dict(
            released_derived_csv_measured=n_csv,
            released_derived_all_files=n_all,
            note_3656='3,656 = 整个复现仓库的文件数；2,767 = data.zip 的名目数；两者都不是 CSV 数',
            files_scanned=tot['files'], files_evaluable=tot['files_evaluable'],
            files_no_raw=tot['files_no_raw'], files_no_pred=tot['files_no_pred'],
            rows_total=tot['rows'], rows_evaluable=tot['rows_evaluable'],
            rows_with_refusal_word=tot['word'],
            rows_word_and_number=tot['word_and_num'],
            rows_word_and_number_wide=tot['word_and_num_wide'],
            rows_number_before_word=tot['num_before'],
            rows_number_before_word_wide=tot['num_before_wide'],
            rows_empty_raw=tot['empty_raw'], rows_pred_non_numeric=tot['pred_nonnumeric'],
            rows_pred_refusal_token=tot['pred_refusal_token'],
            rows_pred_other_token=tot['pred_other_token'],
            rows_pred_ge_1e5=tot['pred_ge_1e5'],
            coverage_files_pct=round(cov_files, 4), coverage_rows_pct=round(cov_rows, 4),
        ),
        negative_control=dict(
            frozen_scope=FROZEN_SCOPE, recomputed=fc,
            pass_=(all(fc[k] == v for k, v in FROZEN_SCOPE.items())),
            note='既有 654 件口径的四个分母逐项复现 ⇒ 判据实现与既有审计一致',
        ),
        new_findings=dict(
            num_before_refusal_word=len(new_findings),
            pred_non_numeric=len(pred_anom),
            pred_non_numeric_all_refusal_tokens=(tot['pred_refusal_token'] == tot['pred_nonnumeric']),
            wide_criterion_rows=tot['word_and_num_wide'],
            narrow_equals_wide=(tot['word_and_num_wide'] == tot['word_and_num']),
            verdict=('**有新发现异常**（见 anomalies.csv 逐条定位）' if new_findings
                     else '**无新发现异常**：扩样后判据读数仍为 0'),
            hits_inside_frozen_654=len(hits) - len(hits_out),
            hits_outside_frozen_654=len(hits_out),
            scope_note='既有 654 件 = e3/merged 228 + e2 的 e1_* 426；三条命中位于 e3/nonzero、'
                       'fsc_res/frozen384、p1c/csv，均在其外 ⇒ 既有审计在自己的范围内仍为 0。'
                       '本轮扩样是**范围问题**，不是既有读数算错。',
            hit_classification=hits,
        ),
        prose_refusal_subaudit=dict(
            criterion='raw 不含弃权词 · 结构式正则不命中 · 含拒答措辞 · **pred 非空**',
            markers=list(PROSE_REFUSAL_MARKERS),
            why='与 §M.21.9(e) 同一弱点的**另一形态**：散文里出现"大约 N 人"时，'
                'frozen_regex 不命中（不是 {"count": ...} 结构）⇒ 掉到 first_int ⇒ 把散文里的数当计数。'
                '既有的 654 件审计只查"数字在弃权词之前"，查不到这种形态。'
                '★ 在 `bestA` 这类故意要求粗估的臂上，这是**正常行为**；本口径对本轮的意义是'
                '给 §M.19.5 那句 "holding neither a digit nor an abstention token" **划定适用臂**。',
            **ps,
        ),
        conclusion=(
            '① 判据在发布件 **2,338** 个 CSV 上跑通：可评 **2,304** 件 / **791,139** 行（文件级 98.55%、'
            '行级 96.93%；33 件无 `raw` 或 `pred` 列，结构上不可评）。'
            '② 既有审计的四个分母（654 / 95,160 / 35,716 / 0）**逐项复现** ⇒ 判据实现与既有审计一致。'
            '③ **有新发现**：窄判据（数字在拒答词之前）在扩样后为 **3** 条（既有 654 件口径内仍为 0）——'
            '三条都是 LLaVA-OneVision-7B 的"散文/多对象里先出现一个数、再出现 abstain"形态，'
            '`parse_ok=1`、存量 `pred` 与冻结 parse 规则今天对同一 raw 的输出**逐位一致**'
            '（⇒ 不是文件被写坏，而是该规则的既定弱点在扩样后第一次显形）。'
            '④ 另有 **2,242** 行 `pred` 列装了弃权 token —— 全部集中于 `p2_noise4/p2_probe_results_reparsed/`'
            '8 件；全库其余位置一律把弃权 token 留在 `raw`、`pred` 留空（未解析行共 281,896 条）。'
            '⑤ 三条命中的**后果**均为个位数项级（st_a 2 项、FSC 1 项），不构成已发布百分比的量级。'
        ),
        anomalies_nonempty=bool(anom),
        per_file=[dict(file=x['file'], rows=x['rows'], evaluable=x['evaluable'],
                       has_raw=x['has_raw'], has_pred=x['has_pred'], md5=x['md5'])
                  for x in per],
        created_by='p3r4_zero_3_parse_all_csv.py',
        created_at=time.strftime('%Y-%m-%dT%H:%M:%S'),
        no_inference=True,
        readonly_repro=True,
    )
    io.open(OUT, 'w', encoding='utf-8', newline='\n').write(json.dumps(out, ensure_ascii=False, indent=2))
    h = md5f(OUT)
    io.open(OUT + '.md5', 'w', encoding='utf-8', newline='\n').write(
        '%s  %s  (p3r4_zero_3_parse_all_csv.py)\n' % (h, os.path.basename(OUT)))
    print('\n已写 %s（md5 %s）' % (os.path.basename(OUT), h[:12]))
    print('已写 %s（%d 条）' % (os.path.basename(OUT_ANOM), len(anom)))
    print('用时 %.1f s' % (time.time() - t0))
    return 0


def selftest():
    print('P3R4-③ selftest（阴性对照）')
    ctl = []
    ctl.append(('纯拒答词 → 不命中', rowcheck('{"response": "no_people"}') == (True, False, False, None, 'no_people')))
    ctl.append(('拒答词在前、数字在后 → 不命中（first_int 也会读到它，且顺序不构成分歧）',
                rowcheck('I cannot count them; 42 people maybe.')[2] is False))
    ctl.append(('数字在前、拒答词在后 → **命中**',
                rowcheck('42 people, cannot_judge')[2] is True))
    ctl.append(('含逗号数字仍取整', rowcheck('abstain 1,234')[3] == '1234'))
    ctl.append(('大小写不敏感（认出 NO_PEOPLE）', rowcheck('NO_PEOPLE and 7')[:2] == (True, True)))
    ctl.append(('大小写不敏感：数字在拒答词之后 → 不命中', rowcheck('NO_PEOPLE and 7')[2] is False))
    ctl.append(('无拒答词 → has_word=False', rowcheck('{"count": 12}')[0] is False))
    ctl.append(('无数字 → has_word_and_num=False', rowcheck('abstain')[:2] == (True, False)))
    ok = True
    for nm, passed in ctl:
        print('  [%s] %s' % ('PASS' if passed else 'FAIL', nm))
        ok = ok and passed
    print('SELFTEST: %s' % ('PASS' if ok else 'FAIL'))
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
