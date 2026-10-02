#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""p1d_integrity.py —— P1-D 的**重启后前置件核对**（纯 CPU，不动 GPU、不起服务）。

机器关过再起（或换成新容器）后**第一件事**就跑它：
  python3 p1d_integrity.py --baseline    # 现在就跑一次：把当前所有前置件的 md5 落成基线
  python3 p1d_integrity.py               # 重启后再跑：逐件比对，缺件/变号 ⇒ 退 2 并列出
基线文件：/root/p1d/p1d_integrity.json（若换容器则需重传本 JSON，否则报"无基线"）
"""
import csv
import glob
import hashlib
import io
import json
import os
import sys

D = '/root/p1d'
BASE = os.path.join(D, 'p1d_integrity.json')


def md5f(p):
    h = hashlib.md5()
    with io.open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def nrows(p):
    try:
        return len(list(csv.DictReader(io.open(p, encoding='utf-8-sig', newline=''))))
    except Exception:
        return -1


def items():
    """(路径, 期望校验方式)。'md5' 逐字节；'csv:N' 期望行数 + 存在性。"""
    out = [(os.path.join(D, '_p1d_criteria_frozen.json'), 'md5'),
           (os.path.join(D, 'p1d_probe.py'), 'md5'),
           (os.path.join(D, 'p1d_run.sh'), 'md5'),
           (os.path.join(D, 'p1d_prep.py'), 'md5'),
           (os.path.join(D, 'p1d_analyze.py'), 'md5'),
           (os.path.join(D, 'p1d_check.py'), 'md5'),
           ('/root/pf_p0_probe.py', 'md5'),
           ('/root/pf_serve_awq4bit_8013.sh', 'md5'),
           (os.path.join(D, 'data', 'sample_mtdc.csv'), 'csv'),
           (os.path.join(D, 'data', 'sample_gwhd.csv'), 'csv'),
           (os.path.join(D, 'data', 'mtdc', 'items.csv'), 'csv'),
           (os.path.join(D, 'data', 'gwhd', 'items.csv'), 'csv'),
           (os.path.join(D, 'ref', 'res_ctrl_st_a.csv'), 'csv'),
           (os.path.join(D, 'ref', 'res_ctrl_ucf.csv'), 'csv'),
           (os.path.join(D, 'ref', 'res_ctrl_visdrone.csv'), 'csv'),
           ('/root/aerial/gt_visdrone.csv', 'csv'),
           ('/root/aerial/gt_aitod.csv', 'csv'),
           ]
    for p in ('/root/models/Qwen3-VL-32B-Instruct-AWQ-4bit/config.json',
              '/root/models/Qwen3-VL-32B-Instruct-AWQ-4bit/model.safetensors.index.json'):
        out.append((p, 'ex'))
    return out


def dirs():
    return [('/root/mtdc/images', 361), ('/root/dense/shanghaitech/images/part_A_test', 182),
            (os.path.join(D, 'data', 'gwhd', 'images'), 1381),
            ('/root/aerial/visdrone/images', 400), ('/root/aerial/aitod/images', 226)]


def snap():
    s = {'files': {}, 'dirs': {}}
    for p, kind in items():
        if not os.path.exists(p):
            s['files'][p] = 'MISSING'
            continue
        if kind == 'md5':
            s['files'][p] = md5f(p)
        elif kind == 'csv':
            s['files'][p] = 'csv:%d' % nrows(p)
        else:
            s['files'][p] = 'exists'
    for d, n in dirs():
        s['dirs'][d] = len(glob.glob(os.path.join(d, '*'))) if os.path.isdir(d) else 'MISSING'
    return s


def main():
    base_mode = '--baseline' in sys.argv
    s = snap()
    if base_mode:
        with io.open(BASE, 'w', encoding='utf-8') as f:
            json.dump(s, f, ensure_ascii=False, indent=1)
        print('== 基线已落 %s ==' % BASE)
    bad = []
    ref = None
    if not base_mode:
        if os.path.exists(BASE):
            ref = json.load(io.open(BASE, encoding='utf-8'))
        else:
            print('!! 找不到基线 %s（换容器后需重传）⇒ 只做存在性检查' % BASE)
    for p, kind in items():
        cur = s['files'][p]
        flag = ''
        if ref and p in ref['files']:
            if ref['files'][p] != cur:
                flag = ' **变了**（基线 %s）' % ref['files'][p]
                bad.append(p)
        elif cur == 'MISSING':
            flag = ' **缺件**'
            bad.append(p)
        print('  %-58s %s%s' % (p.replace('/root/', ''), cur, flag))
    for d, n in dirs():
        cur = s['dirs'][d]
        exp = n if not ref else ref['dirs'].get(d, n)
        flag = '' if cur == exp else ' **数目不符**（期望 %s）' % exp
        if flag:
            bad.append(d)
        print('  %-58s %s 张%s' % (d.replace('/root/', '') + '/', cur, flag))
    print('== 结论：%s ==' % ('全部在且一致 ✓' if not bad else '有 %d 件异常 ⇒ 报上级' % len(bad)))
    print('P1D_INTEGRITY_DONE')
    return 0 if not bad else 2


if __name__ == '__main__':
    sys.exit(main())
