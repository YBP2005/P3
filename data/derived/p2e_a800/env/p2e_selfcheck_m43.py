#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""p2e_selfcheck_m43.py —— **G0 闸门**：用本方案共用的估计器复现 §M.43 已印的四行。

判据（判据件 `gates.G0_selfcheck_m43`）：四行**逐档**复现，容差 0.05 pp：
    output contract 343.55 ｜ prompt family 1561.94 ｜ tiling 14.56 ｜ pixel budget 31.65
**不逐档复现就退出（exit 2），不得继续往下跑** —— 那说明估计器或记录集与印值不同源。

记录来源：`m43_records.json`。★ 该文件目前是**空模板**：§M.43 末尾那段复现句**没给任何文件名**，
我在放行树里按名字（m43/equal_level/rescan/rung/lvl）与内容（343.55/1561.94）都搜不到。
⇒ 执行者必须先把四个 knob 的 paths 填上；填不出来时本脚本会**明确报"记录未定位"并退出 2**。

用法：python3 p2e_selfcheck_m43.py [--allow-missing-records]
      （--allow-missing-records 只用于"先验证脚本本身能跑"，**不得**在正式运行时使用）
"""
import io
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from p2e_common import dev, load_csv, fnum, level_devs_pooled  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
REC = os.path.join(HERE, 'm43_records.json')
TOL = 0.05


def by_level_from_long(spec, filt):
    """长表：一个文件里含多档，靠 `level_col` 区分（/root/g56_res/*.csv 就是这个形状）。
    → {档位标签: {item: (gt, pred)}}；按 `filters` 只留 parse_ok=1 / abstain=0 / rep=1。"""
    p = spec['path']
    if not os.path.exists(p):
        alt = spec.get('path_local')
        if alt and os.path.exists(os.path.join(HERE, alt)):
            p = os.path.join(HERE, alt)
    if not os.path.exists(p):
        raise SystemExit('!! 记录的路径不存在：%s（本地备选 %s 也没有）' % (spec['path'], spec.get('path_local')))
    want = [str(x) for x in spec['levels']]
    out = {}
    for r in load_csv(p):
        lab = str(r.get(spec['level_col'], '')).strip()
        if lab not in want:
            continue
        for k, v in filt.items():
            if k in r and str(r[k]).strip() not in ('', v):
                break
        else:
            it = str(r.get(spec.get('item_col', 'item')) or '').strip()
            g = fnum(r.get(spec.get('gt_col', 'gt')))
            pr = fnum(r.get(spec.get('pred_col', 'pred')))
            if it and g is not None and pr is not None and g > 0:
                out.setdefault(lab, {})[it] = (g, pr)
    return {L: out[L] for L in want if L in out}   # ★ 按判据件里声明的档位顺序（印值就是那个序）


def by_level_from_files(spec):
    """{档位: {item: (gt, pred)}}；一文件一档（旧形状，保留兼容）。"""
    out = {}
    for p in spec['paths']:
        if not os.path.exists(p):
            raise SystemExit('!! 记录的路径不存在：%s' % p)
        d = {}
        for r in load_csv(p):
            it = str(r.get(spec.get('item_col', 'item')) or '').strip()
            g = fnum(r.get(spec.get('gt_col', 'gt')))
            pr = fnum(r.get(spec.get('pred_col', 'pred')))
            if it and g is not None and pr is not None and g > 0:
                d[it] = (g, pr)
        out[os.path.basename(p)] = d
    return out


def main():
    allow = '--allow-missing-records' in sys.argv
    spec = json.load(io.open(REC, encoding='utf-8'))
    targets = spec['_printed_targets']
    filt = spec.get('filters', {})
    print('== G0 自检：复现 §M.43 四行（容差 %.2f pp）==' % TOL)
    print('   估计器：dev = 100*(Σpred−Σgt)/Σgt（a39_unit_calib_heldout.py L183-184）')
    missing = [k for k, v in spec['knobs'].items()
               if not v.get('paths') and not v.get('path')]
    if missing:
        print('   !! 以下 knob 的记录路径**尚未填**：%s' % ', '.join(missing))
        print('   !! 记录来源见 m43_records.json 的 note')
        if not allow:
            print('G0_BLOCKED_MISSING_RECORDS')
            return 2
        print('   （--allow-missing-records：只验证脚本可跑，不算通过）')
    bad = []
    for knob, s in spec['knobs'].items():
        if not s.get('paths') and not s.get('path'):
            continue
        bl = by_level_from_long(s, filt) if s.get('path') else by_level_from_files(s)
        r = level_devs_pooled(bl, keep_order=bool(s.get('levels')))
        if not r:
            bad.append((knob, '单元不合格（档位<3 或交集<20）'))
            continue
        labels, vals, ns = r
        tgt = targets[knob]['levels']
        got = [round(v, 1) for v in vals]
        tgt_r = [round(v, 1) for v in tgt]
        ok = len(vals) == len(tgt) and all(abs(a - b) <= TOL for a, b in zip(vals, tgt))
        print('   %-16s 档位=%d n=%s 得=%s 印=%s  %s'
              % (knob, len(labels), ns, got, tgt_r, 'OK' if ok else '**不符**'))
        if not ok:
            bad.append((knob, ' 得 %s vs 印 %s' % (got, tgt_r)))
    if missing and allow:
        print('   ⇒ 但记录未定位，**不能**判定通过')
        return 2
    if bad:
        print('G0_FAIL：%d 个 knob 不符 ⇒ 停手（估计器或记录集与印值不同源）' % len(bad))
        for k, why in bad:
            print('   - %s：%s' % (k, why))
        return 2
    print('G0_PASS：四行逐档复现 ⇒ 估计器与印值同源，可继续')
    return 0


if __name__ == '__main__':
    sys.exit(main())
