#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""adopt_report.py — 把 `adopt_contract_probe.py` 的逐图 CSV 变成**两个可报告的量**与一个判定。

它实现的就是论文 §M.22 的五步配方里第 3–5 步（前两步是"固定栈、跑三臂"，由探针完成）：
  ① **通道诊断**：base 答 0 的 item 里，permit 仍答 0 的比例（含 Wilson 95% CI）；
  ② **弃权质量** $w$：已给数字的比例（口径切换的规模就是 $-(1-w)(1+\\rho_{\\text{answered}})$）；
  ③ **双口径**：ρ（弃权当 0）与 ρ（仅已答）；
  ④ **判定**（判据来自 `adopt_criteria.json`，**跑前冻结**）：
     · 若 ①≤5% ⇒ "该零由契约决定"；若 >30% ⇒ 记反例（"契约依赖模型"）；介于其间 ⇒ 部分成立；
     · 若 |两口径之差| > 噪声地板 ⇒ "单一口径的报告不可比"。

★ 失败语义（2026-10-04，`v0647` 轮改正）——**三类记录必须分开，失败不得当作"零已移除"**：

  探针的逐图 CSV 有三类非数值记录，此前被**一律折成 `None`** 并当作"permit 把这个零去掉了"：
    (i) **显式弃答**（raw 含 `abstain` / `cannot_judge` / `no_people`）—— 这是契约**按设计生效**，算成功；
    (ii) **失败/缺失**（超时、HTTP 错、空串、未解析出数字）—— **不是**成功，必须**单列**、**留在分母里**、
         并在判定里标为 **不可判定**（它们使残留率只成为一个**下界**，其保守上界是 (still+undecidable)/N）；
    (iii) **数值**（`pred` 可解析，含 0 与正数）。
  实测过的失效模式（上一版）：`raw=ERR:timeout, pred='', parse_ok=0` ⇒ `(None, gt)` ⇒ 不计入 `still`
  ⇒ 残留打印 **0.0%** ⇒ 判定打印"**该零由输出契约决定**"。即"把超时当成契约生效"。
  另两处同源缺陷一并改正：`z` 为空时印 `CI [0.0%, 0.0%]`（应为**不可判定**）；
  channel 对照把**缺 channel 记录**的项静默留在分母里（当作"已移除"）而不单列。

用法：
  python adopt_report.py --dir ./out --criteria adopt_criteria.json [--model <name>]
  python adopt_report.py --selftest        # 阴性对照：注入超时/空串，必须判"不可判定"而非"契约决定"
"""
import argparse
import csv
import io
import json
import math
import os
import re
import sys
import tempfile

ABST = ('abstain', 'cannot_judge', 'no_people')
# ★ 成败三分：num（可解析数值）/ abstain（显式弃答）/ fail（失败·缺失·未解析）
NUM, ABSTAIN, FAIL = 'num', 'abstain', 'fail'

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass


def wilson(k, n, z=1.959963985):
    """Wilson 双侧 95% 区间。n==0 时返回 (None, None) —— 调用方须印"不可判定"，**不得**印 [0.0%, 0.0%]。"""
    if n == 0:
        return (None, None)
    p = k / float(n)
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def load(p):
    """→ {item: (value|None, gt|None, kind, raw)}；**kind 区分三态**（见文件头 ★ 失败语义）。"""
    out = {}
    for r in csv.DictReader(io.open(p, encoding='utf-8-sig')):
        raw = str(r.get('raw') or '')
        rawl = raw.lower()
        pred = str(r.get('pred') or '').strip()
        try:
            gt = float(r['gt'])
        except (KeyError, TypeError, ValueError):
            gt = None
        if any(k in rawl for k in ABST):
            v, kind = None, ABSTAIN
        else:
            try:
                v, kind = float(pred), NUM
            except ValueError:
                v, kind = None, FAIL
        out[r['item']] = (v, gt, kind, raw)
    return out


def _fmt_ci(k, n):
    """(点估计%, CI 串)。n==0 或全不可判定 ⇒ "不可判定"。"""
    if n == 0:
        return None, '不可判定'
    lo, hi = wilson(k, n)
    if lo is None:
        return None, '不可判定'
    return 100.0 * k / n, '[%.1f%%, %.1f%%]' % (100 * lo, 100 * hi)


def diagnose(base, permit, channel=None, p1_pass=0.05, p1_counter=0.30):
    """通道诊断（纯函数，便于自测）。返回 (行列表, verdict 键)。"""
    keys = sorted(set(base) & set(permit))
    z = [k for k in keys if base[k][0] == 0]
    base_fail = [k for k in keys if base[k][2] == FAIL]
    still = sum(1 for k in z if permit[k][0] == 0)
    undec = sum(1 for k in z if permit[k][2] == FAIL)          # ★ 失败/缺失：单列，且**留在分母里**
    n = len(z)
    rate, ci = _fmt_ci(still, n)
    ub = 100.0 * (still + undec) / n if n else None
    lines = []
    lines.append('  ① 通道诊断：base 答 0 的 item %d 个；permit 仍答 0 %d 个%s'
                 % (n, still, ('' if rate is None else '（%.1f%%，Wilson 95%% CI %s）' % (rate, ci))))
    if base_fail:
        lines.append('     · base 侧**不可判定**（超时/空串/未解析）%d 个 —— 单列，**不计入**上面的分母'
                     '（它们没有产生可判定的"零"）' % len(base_fail))
    if n and undec:
        lines.append('     · ★ permit 侧**不可判定** %d/%d 个 —— 已**计入分母**并单列；'
                     '它们**不得当作"零已被移除"**。故残留率 **%.1f%%** 是**下界**，'
                     '保守上界 = (%d+%d)/%d = **%.1f%%**。'
                     % (undec, n, rate, still, undec, n, ub))
    # 判定
    decided = n - undec
    if n == 0:
        lines.append('     判定：**不可判定** —— base 侧没有任何可判定的答零项（分母 0）；'
                     '不印 CI、也不下"契约决定"的结论。')
        verdict = 'undecidable'
    elif decided == 0:
        lines.append('     判定：**不可判定** —— %d 个 base 答零项的 permit 记录**全部**是失败/缺失；'
                     '一个可判定的结果都没有。' % n)
        verdict = 'undecidable'
    else:
        r = still / float(n)
        if undec and r <= p1_pass:
            lines.append('     判定：**点估计在 ≤ %.0f%% 以内，但 %d/%d 不可判定 ⇒ 不可判为"契约决定"**；'
                         '按保守上界 %.1f%% 记，并把不可判定项单列。' % (100 * p1_pass, undec, n, ub))
            verdict = 'undecidable_partial'
        elif r <= p1_pass:
            lines.append('     判定：**该零由输出契约决定**（残留 ≤ %.0f%%；无不可判定项）' % (100 * p1_pass))
            verdict = 'contract'
        elif r > p1_counter:
            lines.append('     判定：**反例——契约依赖模型**（残留 > %.0f%%）；请对照论文 §M.24.3'
                         '（换成 channel 三选一）' % (100 * p1_counter))
            verdict = 'counterexample'
        else:
            lines.append('     判定：**部分成立**（残留介于 %.0f%% 与 %.0f%% 之间）'
                         % (100 * p1_pass, 100 * p1_counter))
            verdict = 'partial'
    if channel is not None and n:
        present = [k for k in z if k in channel]
        missing = n - len(present)
        cs = sum(1 for k in present if channel[k][0] == 0)
        cud = sum(1 for k in present if channel[k][2] == FAIL)
        cci = _fmt_ci(cs, len(present))[1]
        lines.append('     对照（channel 三选一）：分母 = 有 channel 记录的 **%d** 项%s；仍答 0 **%d** 个%s'
                     '%s'
                     % (len(present),
                        ('（**缺 %d 项单列**，不静默当"已移除"）' % missing) if missing else '',
                        cs, ('（Wilson 95%% CI %s）' % cci) if cci != '不可判定' else '',
                        ('；其中**不可判定** %d 个' % cud) if cud else ''))
    return lines, verdict


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dir', required=True)
    ap.add_argument('--criteria', default='adopt_criteria.json')
    ap.add_argument('--model', default='')
    A = ap.parse_args()
    crit = json.load(io.open(A.criteria, encoding='utf-8')) if os.path.exists(A.criteria) else {}
    p1_pass = crit.get('P1_pass_max_residual', 0.05)
    p1_counter = crit.get('P1_counterexample_above', 0.30)

    arms = {}
    for f in sorted(os.listdir(A.dir)):
        m = re.match(r'adopt_(.+)_(base|permit|channel|enumAbstain)\.csv$', f)
        if m and (not A.model or m.group(1) == A.model):
            arms.setdefault(m.group(1), {})[m.group(2)] = os.path.join(A.dir, f)
    if not arms:
        print('!! 目录里没有 adopt_<model>_<arm>.csv：%s' % A.dir)
        return 2

    for model, files in sorted(arms.items()):
        print('=' * 88)
        print('模型：%s' % model)
        print('=' * 88)
        if 'base' not in files or 'permit' not in files:
            print('  缺 base 或 permit 臂，无法做通道诊断（需要 base+permit）')
            continue
        b, p = load(files['base']), load(files['permit'])
        c = load(files['channel']) if 'channel' in files else None
        for line in diagnose(b, p, c, p1_pass, p1_counter)[0]:
            print(line)
        keys = sorted(set(b) & set(p))
        ans = [k for k in keys if b[k][2] == NUM and b[k][0] != 0]
        w = len(ans) / float(len(keys)) if keys else None
        has_gt = all(b[k][1] is not None for k in keys) and bool(keys)
        print('  ② 弃权质量：已给数字 %d/%d（w = %.3f）' % (len(ans), len(keys), w or 0))
        if has_gt and ans:
            sp = sum(b[k][0] for k in keys if b[k][0] is not None)
            sg = sum(b[k][1] for k in keys)
            sp2 = sum(b[k][0] for k in ans)
            sg2 = sum(b[k][1] for k in ans)
            rhoA = (sp - sg) / sg * 100 if sg else None
            rhoB = (sp2 - sg2) / sg2 * 100 if sg2 else None
            if rhoA is None or rhoB is None:
                print('  ③ 双口径：真值为 0 ⇒ ρ 未定义（不印数字）')
            else:
                print('  ③ 双口径：ρ(弃权当0) = %.1f%%  ｜  ρ(仅已答) = %.1f%%  ｜  差 %.1f pp'
                      % (rhoA, rhoB, abs(rhoA - rhoB)))
                floor = crit.get('noise_floor_pp', 7.0)
                print('     判定：%s' % ('**单一口径的报告不可比**（差 > 噪声地板 %.1f pp）' % floor
                                         if abs(rhoA - rhoB) > floor else
                                         '该单元上口径无关（差 ≤ 噪声地板 %.1f pp）' % floor))
        else:
            print('  ③ 双口径：缺 gt（--gt-csv），跳过')
        print()
    print('提示：本报告只依赖逐图 CSV 与冻结判据，不需要本仓库的其它模块。')
    return 0


def selftest():
    """★ 阴性对照：**失败调用必须判"不可判定"，绝不能被当成"契约生效"**。"""
    d = tempfile.mkdtemp(prefix='adopt_selftest_')
    hdr = 'item,gt,pred,parse_ok,raw,latency_s\n'
    # base：3 项答 0（另有 1 项失败，不产生"零"）
    io.open(os.path.join(d, 'adopt_m_base.csv'), 'w', encoding='utf-8', newline='\n').write(
        hdr + 'a,5,0,1,{"count": 0},1.0\n'
              'b,7,0,1,{"count": 0},1.0\n'
              'c,9,0,1,{"count": 0},1.0\n'
              'd,4,,0,ERR:timeout,180.0\n')
    # permit：a/b 显式弃答；c **超时/空串**（旧版把它当"零已移除" ⇒ 残留 0.0% ⇒ "契约决定"）
    io.open(os.path.join(d, 'adopt_m_permit.csv'), 'w', encoding='utf-8', newline='\n').write(
        hdr + 'a,5,,1,{"count": "abstain"},1.0\n'
              'b,7,,1,{"count": "abstain"},1.0\n'
              'c,9,,0,ERR:timeout,180.0\n'
              'd,4,,0,ERR:timeout,180.0\n')
    io.open(os.path.join(d, 'adopt_m_channel.csv'), 'w', encoding='utf-8', newline='\n').write(
        hdr + 'a,5,0,1,{"response": 0},1.0\n'
              'b,7,,1,{"response": "cannot_judge"},1.0\n'
              'c,9,0,1,{"response": 0},1.0\n')
    b, p = load(os.path.join(d, 'adopt_m_base.csv')), load(os.path.join(d, 'adopt_m_permit.csv'))
    c = load(os.path.join(d, 'adopt_m_channel.csv'))
    lines, verdict = diagnose(b, p, c)
    for l in lines:
        print(l)
    ctl = []
    ctl.append(('base 侧失败 1 项被单列（不计入分母）', any('base 侧**不可判定**' in l for l in lines)))
    ctl.append(('permit 侧失败 1 项被单列并计入分母', any('permit 侧**不可判定** 1/3' in l for l in lines)))
    ctl.append(('点估计 0.0% 且 1 项不可判定 ⇒ 判定**不是**"契约决定"', verdict == 'undecidable_partial'))
    ctl.append(('保守上界给出 (0+1)/3 = 33.3%', any('33.3%' in l for l in lines)))
    ctl.append(('channel 对照行给出', any('对照（channel 三选一）' in l for l in lines)))
    # 全失败：必须判不可判定、且 CI 不印 [0.0%, 0.0%]
    allfail = {k: (None, None, FAIL, 'ERR:timeout') for k in b}
    l2, v2 = diagnose(b, allfail, None)
    ctl.append(('全失败 ⇒ 判定"不可判定"', v2 == 'undecidable'))
    ctl.append(('全失败 ⇒ 印"不可判定"而非 CI [0.0%, 0.0%]',
                any('不可判定' in l for l in l2) and not any('[0.0%, 0.0%]' in l for l in l2)))
    # 空分母：必须判不可判定、不印 [0.0%, 0.0%]
    l3, v3 = diagnose({'x': (5, 5, NUM, '')}, {'x': (5, 5, NUM, '')}, None)
    ctl.append(('空分母 ⇒ 判定"不可判定"、不印 [0.0%, 0.0%]',
                v3 == 'undecidable' and not any('[0.0%, 0.0%]' in l for l in l3)))
    ok = True
    for name, passed in ctl:
        print('  [%s] %s' % ('PASS' if passed else 'FAIL', name))
        ok = ok and passed
    print('ADOPT_REPORT SELFTEST: %s' % ('PASS' if ok else 'FAIL'))
    return ok


if __name__ == '__main__':
    if '--selftest' in sys.argv:
        sys.exit(0 if selftest() else 1)
    sys.exit(main())
