#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""make_19e.py — 由 `19b_e1_probe.py` **确定性**生成 E2 用的探针 `19e_probe_multi.py`。

为什么要有这个脚本而不是直接放一个 19e 文件：
  E2 的全部结果都由 19e 产出，而 19e 与 19b 的**唯一区别**必须可枚举、可复核：
    · 新增三支臂 enum / enumAbstain / locate（把"要求逐项枚举"与"允许弃答"分开）；
    · 新增三个域 visdrone / aitod / countbench（含各自的 GT 读取方式）；
    · 图像扩展名多候选；新增 `--pool {zero,nonzero}` 开关与对应的取样分支。
  生成后本脚本会**逐字还原**并断言与 19b 完全一致 —— 即"改动没有越界"。
  故仓库里同时留 19b（原版）与本脚本，19e 是可复算的派生物，而不是一份无从核对的拷贝。

运行： python make_19e.py            # 在 code/experiments/ 目录下
"""
import io
import os
import py_compile
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, '19b_e1_probe.py')
DST = os.path.join(HERE, '19e_probe_multi.py')

ARMS = """# ===== 为 §3.6(d) 补的臂：把「要求逐项枚举」与「允许弃答」两个因素分开 =====
P['enum'] = ('请把图片中的每一个人**逐个**找出来并数出总数（不要遗漏、不要重复）。'
             '以JSON格式输出：{"count": 数量}，只输出JSON。')
P['enumAbstain'] = ('请把图片中的每一个人**逐个**找出来并数出总数；'
                    '如果有任何一个人你无法确证，请回答 abstain，而不要猜测。'
                    '以JSON格式输出：{"count": 数量} 或 {"count": "abstain"}，只输出JSON。')
P['locate'] = ('请定位并数出图片中的每一个人（locate every person），'
               '对每个人都要给出位置与计数。以JSON格式输出：{"count": 数量}，只输出JSON。')

"""

DS_OLD = """DS_DIRS = {
    'st_a': '/root/dense/shanghaitech/images/part_A_test',
    'st_b': '/root/dense/shanghaitech/images/part_B_test',
    'ucf':  '/root/dense/ucf_qnrf/UCF-QNRF_ECCV18/Test',
}"""

DS_NEW = """DS_DIRS = {
    'st_a': '/root/dense/shanghaitech/images/part_A_test',
    'st_b': '/root/dense/shanghaitech/images/part_B_test',
    'ucf':  '/root/dense/ucf_qnrf/UCF-QNRF_ECCV18/Test',
    'visdrone':   '/root/aerial/visdrone/images',
    'aitod':      '/root/aerial/aitod/images',
    'countbench': '/root/ext/countbench/images',
}"""

GT_OLD = """def load_gt(ds):
    gt = {}
    if ds in ('st_a', 'st_b'):"""

GT_NEW = """def load_gt(ds):
    gt = {}
    # —— 新增域（GT 格式各不相同，故按域分派）——
    if ds in ('visdrone', 'aitod'):
        with open('/root/aerial/gt_%s.csv' % ds, encoding='utf-8-sig') as f:
            for r in csv.DictReader(f):
                gt[r['item']] = int(r['gt'])
        return gt
    if ds == 'countbench':
        with open('/root/ext/countbench/counts.csv', encoding='utf-8-sig') as f:
            for r in csv.DictReader(f):
                _fn = os.path.basename(r['file'])
                # ⚠ countbench 的 item 名**自带扩展名**（base CSV 里是 img_00006.jpg），
                #   而 counts.csv 的 file 也是带扩展名的 ⇒ 两种键都存，避免取交集为空。
                gt[_fn] = int(r['number'])
                gt[os.path.splitext(_fn)[0]] = int(r['number'])
        return gt
    if ds in ('st_a', 'st_b'):"""

IMG_OLD = """                p = os.path.join(DS_DIRS[A.ds], base_it + '.jpg')"""
IMG_NEW = """                p = None
                for _ext in ('', '.jpg', '.png', '.jpeg', '.tif', '.TIF', '.bmp'):
                    _cand = os.path.join(DS_DIRS[A.ds], base_it + _ext)
                    if os.path.exists(_cand):
                        p = _cand
                        break
                if p is None:
                    p = os.path.join(DS_DIRS[A.ds], base_it + '.jpg')"""

ARG_OLD = """    ap.add_argument('--reps', type=int, default=1)
    A = ap.parse_args()
    os.makedirs(OUTD, exist_ok=True)"""
ARG_NEW = """    ap.add_argument('--reps', type=int, default=1)
    ap.add_argument('--pool', default='zero', choices=('zero', 'nonzero'))
    A = ap.parse_args()
    global OUTD
    if A.pool == 'nonzero':
        OUTD = '/root/e1_results_nonzero'
    os.makedirs(OUTD, exist_ok=True)"""

SEL_OLD = """            if str(r.get('pred', '')).strip() in ('0', '0.0') and r.get('item') in gt:"""
SEL_NEW = """            _p = str(r.get('pred', '')).strip()
            _want = (_p in ('0', '0.0')) if A.pool == 'zero' else (_p not in ('0', '0.0'))
            if _want and r.get('item') in gt:"""

PATCHES = [
    ('arms', 'DS_DIRS = {', ARMS + 'DS_DIRS = {'),
    ('domains', DS_OLD, DS_NEW),
    ('load_gt', GT_OLD, GT_NEW),
    ('imgpath', IMG_OLD, IMG_NEW),
    ('pool_arg', ARG_OLD, ARG_NEW),
    ('pool_sel', SEL_OLD, SEL_NEW),
]

src = io.open(SRC, encoding='utf-8', newline='').read()
out = src
for name, a, b in PATCHES:
    assert out.count(a) == 1, '锚点 %s 出现 %d 次，不唯一' % (name, out.count(a))
    out = out.replace(a, b, 1)

io.open(DST, 'w', encoding='utf-8', newline='\n').write(out)
py_compile.compile(DST, doraise=True)

back = out
for name, a, b in reversed(PATCHES):
    back = back.replace(b, a, 1)
same = (back == src)
print('还原后与 19b 逐字一致 : %s' % same)
assert same, '还原不一致，说明改动超出了预期范围'


def arms(t):
    m = re.search(r"^P = \{(.*?)^\}", t, re.S | re.M)
    a = set(re.findall(r"'([A-Za-z0-9_]+)':\s*\(", m.group(1)))
    b = set(re.findall(r"^P\['([A-Za-z0-9_]+)'\]\s*=", t, re.M))
    return sorted(a | b)


def domains(t):
    m = re.search(r"^DS_DIRS = \{(.*?)^\}", t, re.S | re.M)
    return sorted(re.findall(r"'([a-z_]+)':", m.group(1)))


print('19b 臂 : %s' % arms(src))
print('19e 臂 : %s' % arms(out))
print('新增臂 : %s' % sorted(set(arms(out)) - set(arms(src))))
assert set(arms(out)) - set(arms(src)) == {'enum', 'enumAbstain', 'locate'}
assert not (set(arms(src)) - set(arms(out))), '丢失了原有臂'
print('19e 域 : %s' % domains(out))
assert set(domains(out)) - set(domains(src)) == {'visdrone', 'aitod', 'countbench'}
print('提示词（原有部分）是否逐字未改 : %s'
      % (re.search(r"^P = \{(.*?)^\}", src, re.S | re.M).group(1)
         == re.search(r"^P = \{(.*?)^\}", out, re.S | re.M).group(1)))
assert (re.search(r"^P = \{(.*?)^\}", src, re.S | re.M).group(1)
        == re.search(r"^P = \{(.*?)^\}", out, re.S | re.M).group(1))
print('语法编译: 通过   大小 %d B' % os.path.getsize(DST))
print('MAKE_19E_OK')
