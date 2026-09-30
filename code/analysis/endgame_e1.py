# -*- coding: utf-8 -*-
"""endgame_e1.py — E1 收尾一键流程：拉回三档产物 → 质检 → 分析器 → 重生成 M.41。

远端目录（fscres_run.sh 的 OUTD）：
  /root/w1_results/fsc_sc384  ← 本批次 384（发布分辨率，同脚本重测）
  /root/w1_results/fsc_sc256  ← 短边 256（面积 0.444×）
  /root/w1_results/fsc_sc768  ← 短边 768（面积 4.000×，upsampled）
本地：analysis/fsc_res/{384,256,768up}（frozen384 = §5.6 冻结面板，作交叉核对，不覆盖）。

用法：python -u endgame_e1.py
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
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
W = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable
DEST = RP('analysis', 'fsc_res')
MAP = (('fsc_sc384', '384'), ('fsc_sc256', '256'), ('fsc_sc768', '768up'))
MODELS = ('InternVL3_5-8B', 'Phi-3.5-vision-instruct', 'gemma3-12b')
ARMS = ('base', 'permit', 'channel', 'enumAbstain', 'exemplar3', 'exemplar3permit')


def run(args):
    p = subprocess.run(args, cwd=W, capture_output=True, text=True, encoding='utf-8', errors='replace')
    return p.returncode, (p.stdout or '') + (p.stderr or '')


print('■ ① 拉回三档产物')
for rem_name, tag in MAP:
    rem = '/root/w1_results/%s' % rem_name
    loc = os.path.join(RP('analysis', 'fsc_res'), tag)
    rc, out = run([PY, '-u', 'rsh.py', '--get', rem, loc, '--t', '900'])
    have = sorted(f[:-4].split('_', 1)[1] for f in os.listdir(loc) if f.endswith('.csv')) \
        if os.path.isdir(loc) else []
    need = {'%s_%s' % (m, a) for m in MODELS for a in ARMS}
    missing = sorted(need - set(have))
    print('   %-34s → %-42s %d 个臂文件%s' % (rem, loc, len(have),
                                              '' if not missing else '  ｜缺 %d：%s' % (len(missing), missing[:4])))

print('\n■ ② 远端质检（fsc_res_qc.py：行数 = 300、解析率 < 90% 才算数）')
rc, out = run([PY, '-u', 'rsh.py', '--t', '600', '/usr/local/miniconda3/bin/python /root/fsc_res_qc.py'])
print('\n'.join(out.strip().splitlines()[-14:]))
rc2, out2 = run([PY, '-u', 'rsh.py', '--get', '/root/w1_results/e1_qc.json',
                 os.path.join(W, 'e1_qc.json'), '--t', '300'])
print('   ', out2.strip().splitlines()[-1] if out2.strip() else '(未取回 e1_qc.json)')

print('\n■ ③ 分析器（fsc_res_analyze.py）')
rc, out = run([PY, '-u', 'fsc_res_analyze.py'])
keep = [l for l in out.strip().splitlines()
        if l.startswith('■') or '最大' in l or '已写出' in l or '核对' in l or '（暂无' in l]
print('\n'.join('   ' + l.strip() for l in keep))
if rc:
    sys.exit('!! 分析器失败 ⇒ 停下')

print('\n■ ④ 重生成补充材料 M.41（gen_m41_e1.py）')
rc, out = run([PY, '-u', 'gen_m41_e1.py'])
print(out.strip()[-900:])
sys.exit(rc)
