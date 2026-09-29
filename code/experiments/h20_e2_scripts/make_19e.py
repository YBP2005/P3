# -*- coding: utf-8 -*-
"""生成 19e_probe_multi.py：以 19b 为母本，**只做四处扩展**，其余逐字不动。

扩展内容：
  ① 新增 3 个契约臂，用于把主稿 §3.6(d) 的两个因素分开（枚举要求 × 弃答是否可选）：
       enum        —— 要求逐个枚举，**不允许**弃答
       enumAbstain —— 要求逐个枚举，**允许**弃答
       locate      —— 主稿原话风格的 "locate every person"，不允许弃答
  ② 新增 3 个域：visdrone（航拍 400）、aitod（航拍微小目标 226）、countbench（自然图 491）
  ③ load_gt 增加新域的 GT 读取分支
  ④ 图像路径从写死的 '.jpg' 改为**多扩展名探测**（aitod 是 .png；countbench 的 item 自带扩展名）
  ⑤ 增加 --pool zero|nonzero，使同一支探针既能跑零池也能跑非零池
     （默认 zero，且 OUTD 与 19b 相同 ⇒ 对既有域的行为与 19b **完全一致**）

校验：把上述改动逐一还原后，必须与 19b **逐字一致**。
"""
import io
import os
import py_compile
import sys

sys.stdout.reconfigure(encoding='utf-8')

SRC = '/root/19b_e1_probe.py'
DST = '/root/19e_probe_multi.py'

# ---------- ① 新增臂 ----------
ARMS = """# ===== 为 §3.6(d) 补的臂：把「要求逐项枚举」与「允许弃答」两个因素分开 =====
P['enum'] = ('请把图片中的每一个人**逐个**找出来并数出总数（不要遗漏、不要重复）。'
             '以JSON格式输出：{"count": 数量}，只输出JSON。')
P['enumAbstain'] = ('请把图片中的每一个人**逐个**找出来并数出总数；'
                    '如果有任何一个人你无法确证，请回答 abstain，而不要猜测。'
                    '以JSON格式输出：{"count": 数量} 或 {"count": "abstain"}，只输出JSON。')
P['locate'] = ('请定位并数出图片中的每一个人（locate every person），'
               '对每个人都要给出位置与计数。以JSON格式输出：{"count": 数量}，只输出JSON。')

"""

# ---------- ② 新增域 ----------
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

# ---------- ③ load_gt 增加新域 ----------
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

# ---------- ④ 多扩展名图像解析 ----------
IMG_OLD = """                p = os.path.join(DS_DIRS[A.ds], base_it + '.jpg')"""
IMG_NEW = """                p = None
                for _ext in ('', '.jpg', '.png', '.jpeg', '.tif', '.TIF', '.bmp'):
                    _cand = os.path.join(DS_DIRS[A.ds], base_it + _ext)
                    if os.path.exists(_cand):
                        p = _cand
                        break
                if p is None:
                    p = os.path.join(DS_DIRS[A.ds], base_it + '.jpg')"""

# ---------- ⑤ --pool 开关 ----------
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
    ('arms', "DS_DIRS = {", ARMS + "DS_DIRS = {"),
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

# ---- 校验：还原全部改动后必须与 19b 逐字一致 ----
back = out
for name, a, b in reversed(PATCHES):
    back = back.replace(b, a, 1)
same = (back == src)
print('还原后与 19b 逐字一致 : %s' % same)
assert same, '还原不一致，说明改动超出了预期范围'

# ---- 校验：臂与域清单 ----
import re
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
print('19b 域 : %s' % domains(src))
print('19e 域 : %s' % domains(out))
print('新增域 : %s' % sorted(set(domains(out)) - set(domains(src))))
assert set(domains(out)) - set(domains(src)) == {'visdrone', 'aitod', 'countbench'}
print('提示词（原有部分）是否逐字未改 : %s'
      % (re.search(r"^P = \{(.*?)^\}", src, re.S | re.M).group(1)
         == re.search(r"^P = \{(.*?)^\}", out, re.S | re.M).group(1)))
assert (re.search(r"^P = \{(.*?)^\}", src, re.S | re.M).group(1)
        == re.search(r"^P = \{(.*?)^\}", out, re.S | re.M).group(1))
print('语法编译: 通过   大小 %d B' % os.path.getsize(DST))
print('MAKE_19E_OK')
