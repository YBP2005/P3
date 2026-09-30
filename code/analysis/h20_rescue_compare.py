# -*- coding: utf-8 -*-
"""H20 抢救包 vs 本地已有：找出**只存在于 H20** 的东西（这才是"有价值"的判据）。"""


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
import hashlib
import io
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')
R = RP('analysis', 'h20_rescue_20260922', 'extract')
E2 = RP('analysis', 'e2_newh20')
REPO = RP('repro_github')


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
h_zero = census(RP('analysis', 'h20_rescue_20260922', 'extract', 'e1_results'))
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
h_nz = census(RP('analysis', 'h20_rescue_20260922', 'extract', 'e1_results_nonzero'))
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
for sub, local_hint in (('dense_results', RP('analysis', 'e2_newh20', 'dense_results')),
                        ('corpus_new', RP('analysis', 'e2_newh20', 'corpus_new')),
                        ('aerial', None), ('ext', None), ('probes', None)):
    src = os.path.join(RP('analysis', 'h20_rescue_20260922', 'extract'), sub)
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
pkg = census(RP('repro_github', 'code'))
pkg_names = set(os.path.basename(k) for k in pkg)
new_scripts = [f for f in sorted(script_names) if f not in pkg_names]
print('  H20 顶层脚本 %d 个；复现包里没有的 %d 个：' % (len(script_names), len(new_scripts)))
for f in new_scripts:
    print('     %s' % f)
logs = sorted(os.listdir(RP('analysis', 'h20_rescue_20260922', 'extract', 'logs'))) if os.path.isdir(RP('analysis', 'h20_rescue_20260922', 'extract', 'logs')) else []
print('  H20 logs/ 共 %d 个文件' % len(logs))
