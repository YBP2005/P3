# -*- coding: utf-8 -*-
"""endgame_e2.py — E2 收尾一键流程：拉回 gemma12b / q32 的产物 → 三个分析器 → 重生成 M.40。

为什么写成一键：E2 跑完时正是"数据刚到、要赶紧落进论文"的节点，手敲 12 条拉取命令容易漏一个目录
（漏了就静默少一个构建，M.40 的"几个构建"就会少说）。本脚本按**目录清单**逐个拉，缺一个就报错停下。

用法：python -u endgame_e2.py
"""
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
W = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable
EA2 = r'<WORKDIR>\PaperB\analysis\ea2_z0'
# 远端目录后缀 tag：E2 的 run_build 用的是 ivl8b/phi35/llavaov/gemma12b/q32
TAGS = ('ivl8b', 'phi35', 'llavaov', 'gemma12b', 'q32')


def run(args, **kw):
    p = subprocess.run(args, cwd=W, capture_output=True, text=True, encoding='utf-8', errors='replace', **kw)
    return p.returncode, (p.stdout or '') + (p.stderr or '')


print('■ ① 拉回 5 个构建 × 3 次服务 × 双语言 = 30 个目录')
for tag in TAGS:
    for lang, pre in (('cn', 'z0_results_'), ('en', 'z0_results_en_')):
        for s in (1, 2, 3):
            rem = '/root/%s%s_s%d' % (pre, tag, s)
            loc = os.path.join(EA2, '%s_%s_s%d' % (lang, tag, s))
            rc, out = run([PY, '-u', 'rsh.py', '--get', rem, loc, '--t', '600'])
            ok = os.path.isdir(loc) and len([f for f in os.listdir(loc) if f.endswith('.csv')]) >= 6
            print('   %-28s → %-46s %s  %s' % (rem, loc, 'OK' if ok else '!! 不足 6 个 CSV',
                                               out.strip().splitlines()[-1] if out.strip() else ''))
            if not ok:
                sys.exit('!! %s 拉取不完整 ⇒ 停下（不要用缺件的结果生成正文）' % rem)

print('\n■ ② 四个结构对照（ea2_integrity.py）')
rc, out = run([PY, '-u', 'ea2_integrity.py'])
print('\n'.join(out.strip().splitlines()[-8:]))
if rc:
    sys.exit('!! 结构对照未全过 ⇒ 停下')

print('\n■ ③ 服务级噪声（ea2_analyze.py）')
rc, out = run([PY, '-u', 'ea2_analyze.py'])
print('\n'.join(out.strip().splitlines()[-3:]))
if rc:
    sys.exit('!! ea2_analyze 失败 ⇒ 停下')

print('\n■ ④ 真零 vs 非零对照（ea2_contrast.py）')
rc, out = run([PY, '-u', 'ea2_contrast.py'])
for line in out.strip().splitlines():
    if '真零' in line or '已写出' in line:
        print('   ' + line.strip())
if rc:
    sys.exit('!! ea2_contrast 失败 ⇒ 停下')

print('\n■ ⑤ 重生成补充材料 M.40（构建数 <4 时生成器会自行拒绝）')
rc, out = run([PY, '-u', 'gen_m40_e2.py'])
print(out.strip()[-900:])
sys.exit(rc)
