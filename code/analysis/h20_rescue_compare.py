# -*- coding: utf-8 -*-
"""H20 抢救包 vs 本地已有：找出**只存在于 H20** 的东西（这才是"有价值"的判据）。"""
import hashlib
import io
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')
R = r'<WORKDIR>\PaperB\analysis\h20_rescue_20260922\extract'
E2 = r'<WORKDIR>\PaperB\analysis\e2_newh20'
REPO = r'<WORKDIR>\PaperB\repro_github'


def md5(p):
    h = hashlib.md5()
    with io.open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def census(d, rec=False):
    out = {}
    for root, dirs, files in os.walk(d):
        dirs[:] = [x for x in dirs if x != '__pycache__']
        for f in files:
            p = os.path.join(root, f)
            out[os.path.relpath(p, d).replace('\\', '/')] = (os.path.getsize(p), md5(p))
    return out


print('=' * 92)
print('① 零池结果：H20 e1_results  vs  本地 e2_newh20')
print('=' * 92)
h_zero = census(os.path.join(R, 'e1_results'))
l_all = census(E2)
l_zero = {k: v for k, v in l_all.items() if not k.startswith('nz__') and k.endswith('.csv')}
only_h = sorted(set(h_zero) - set(l_zero))
diff = sorted(k for k in set(h_zero) & set(l_zero) if h_zero[k][1] != l_zero[k][1])
print('  H20 %d 个 / 本地同名 %d 个' % (len(h_zero), len(l_zero)))
print('  ★ 只在 H20：%d 个 %s' % (len(only_h), only_h[:6]))
print('  同名但内容不同：%d 个 %s' % (len(diff), diff[:6]))

print()
print('=' * 92)
print('② 非零池结果：H20 e1_results_nonzero  vs  本地 nz__* 前缀副本')
print('=' * 92)
h_nz = census(os.path.join(R, 'e1_results_nonzero'))
l_nz = {k[4:]: v for k, v in l_all.items() if k.startswith('nz__')}
only_nz = sorted(set(h_nz) - set(l_nz))
diff_nz = sorted(k for k in set(h_nz) & set(l_nz) if h_nz[k][1] != l_nz[k][1])
print('  H20 %d 个 / 本地 %d 个' % (len(h_nz), len(l_nz)))
print('  ★ 只在 H20：%d 个 %s' % (len(only_nz), only_nz[:6]))
print('  同名但内容不同：%d 个 %s' % (len(diff_nz), diff_nz[:6]))

print()
print('=' * 92)
print('③ 池定义 / 语料 / GT：本地是否有')
print('=' * 92)
for sub, local_hint in (('dense_results', os.path.join(E2, 'dense_results')),
                        ('corpus_new', os.path.join(E2, 'corpus_new')),
                        ('aerial', None), ('ext', None), ('probes', None)):
    src = os.path.join(R, sub)
    if not os.path.isdir(src):
        continue
    names = sorted(os.listdir(src))
    have = sum(1 for n in names if local_hint and os.path.exists(os.path.join(local_hint, n)))
    print('  %-14s H20 %2d 个；本地对应目录%s（已有 %d）'
          % (sub, len(names), ('有' if local_hint and os.path.isdir(local_hint) else '无'), have))

print()
print('=' * 92)
print('④ 运行脚本 / 日志：与复现包比对')
print('=' * 92)
script_names = [f for f in os.listdir(R) if f.endswith(('.py', '.sh'))]
pkg = census(os.path.join(REPO, 'code'))
pkg_names = set(os.path.basename(k) for k in pkg)
new_scripts = [f for f in sorted(script_names) if f not in pkg_names]
print('  H20 顶层脚本 %d 个；复现包里没有的 %d 个：' % (len(script_names), len(new_scripts)))
for f in new_scripts:
    print('     %s' % f)
logs = sorted(os.listdir(os.path.join(R, 'logs'))) if os.path.isdir(os.path.join(R, 'logs')) else []
print('  H20 logs/ 共 %d 个文件' % len(logs))
