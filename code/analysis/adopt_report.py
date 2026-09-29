#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""adopt_report.py — 把 `adopt_contract_probe.py` 的逐图 CSV 变成**两个可报告的量**与一个判定。

它实现的就是论文 §M.22 的五步配方里第 3–5 步（前两步是"固定栈、跑三臂"，由探针完成）：
  ① **通道诊断**：base 答 0 的 item 里，permit 仍答 0 的比例（含 Wilson 95% CI）；
  ② **弃权质量** $w$：已给数字的比例（口径切换的规模就是 $-(1-w)(1+\rho_{\text{answered}})$）；
  ③ **双口径**：ρ（弃权当 0）与 ρ（仅已答）；
  ④ **判定**（判据来自 `adopt_criteria.json`，**跑前冻结**）：
     · 若 ①≤5% ⇒ "该零由契约决定"；若 >30% ⇒ 记反例（"契约依赖模型"）；介于其间 ⇒ 部分成立；
     · 若 |两口径之差| > 噪声地板 ⇒ "单一口径的报告不可比"。

用法：
  python adopt_report.py --dir ./out --criteria adopt_criteria.json [--model <name>]
"""
import argparse
import csv
import io
import json
import math
import os
import re
import sys

ABST = ('abstain', 'cannot_judge', 'no_people')


def wilson(k, n, z=1.959963985):
    if n == 0:
        return (None, None)
    p = k / float(n)
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def load(p):
    out = {}
    for r in csv.DictReader(io.open(p, encoding='utf-8-sig')):
        raw = str(r.get('raw') or '').lower()
        try:
            gt = float(r['gt'])
        except (KeyError, TypeError, ValueError):
            gt = None
        if any(k in raw for k in ABST):
            v = None
        else:
            try:
                v = float(str(r['pred']).strip())
            except ValueError:
                v = None
        out[r['item']] = (v, gt)
    return out


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
        keys = sorted(set(b) & set(p))
        z = [k for k in keys if b[k][0] == 0]
        still = sum(1 for k in z if p[k][0] == 0)
        lo, hi = wilson(still, len(z)) if z else (None, None)
        print('  ① 通道诊断：base 答 0 的 item %d 个；permit 仍答 0 %d 个（%.1f%%，Wilson 95%% CI [%.1f%%, %.1f%%]）'
              % (len(z), still, 100 * still / len(z) if z else 0,
                 100 * lo if lo is not None else 0, 100 * hi if hi is not None else 0))
        if z:
            r = still / float(len(z))
            if r <= p1_pass:
                print('     判定：**该零由输出契约决定**（残留 ≤ %.0f%%）' % (100 * p1_pass))
            elif r > p1_counter:
                print('     判定：**反例——契约依赖模型**（残留 > %.0f%%）；请对照论文 §M.24.3（换成 channel 三选一）'
                      % (100 * p1_counter))
            else:
                print('     判定：**部分成立**（残留介于 %.0f%% 与 %.0f%% 之间）' % (100 * p1_pass, 100 * p1_counter))
            if 'channel' in files:
                c = load(files['channel'])
                cs = sum(1 for k in z if k in c and c[k][0] == 0)
                print('     对照（channel 三选一）：仍答 0 %d 个（%.1f%%）'
                      % (cs, 100 * cs / len(z) if z else 0))
        ans = [k for k in keys if b[k][0] not in (None, 0)]
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


if __name__ == '__main__':
    sys.exit(main())
