# -*- coding: utf-8 -*-
"""关机前核对：远端成果是否已全部落到本地 + 把日志/补丁/脚本留档。

判据（三条全过才说"可以关"）：
 ① 远端每个结果目录的 CSV 数（按文件名集合）与本地一致；
 ② 关键日志、补丁垫片、远端脚本已拉到本地并校验 md5；
 ③ 远端无残留计算进程、显存回落。
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
import hashlib
import io
import os
import posixpath
import sys

sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, RP('analysis', 'work'))
from a800_conn import connect, sh

A = ('<REDACTED-A800-HOST>', 23, 'root', '<REDACTED-A800-PASSWORD>')
L = RP('analysis', 'e2xt_a800')
ENV = RP('analysis', 'e2xt_a800', 'env')
os.makedirs(ENV, exist_ok=True)
os.makedirs(RP('analysis', 'e2xt_a800', 'env', 'a800_logs'), exist_ok=True)

PAIRS = [
    ('/root/e1_results', 'zero'),
    ('/root/e1_results_nonzero', 'nonzero'),
    ('/root/e1_results_ablate', 'ablate'),
    ('/root/e1_results_ablate3', 'ablate3'),
    ('/root/e1_results_build', 'build'),
    ('/root/e1_results_reps', 'reps'),
]
LOGS = ['/root/logs/a5_gemma3-12b.log', '/root/logs/a5_internvl3.5-8b.log',
        '/root/logs/a5_phi-3.5-vision.log', '/root/logs/a5_llava-ov-7b.log',
        '/root/logs/a5_ablation.log', '/root/logs/a5_extra.log', '/root/logs/a5_extra2.log',
        '/root/logs/a5_extra3.log', '/root/logs/a5_extra4.log', '/root/dl_a5.log',
        '/root/llava_fix.log']
SCRIPTS = ['/root/a5_grid.sh', '/root/a800_ablate.sh', '/root/a800_extra.sh',
           '/root/a800_extra2.sh', '/root/a800_extra3.sh', '/root/a800_extra4.sh',
           '/root/a800_fix_llava.sh', '/root/19e_probe_multi.py', '/root/19f_probe_ablation.py',
           '/root/a5_qc.py', '/root/a5_precision.py', '/root/a5_pixtral_compat.py',
           '/root/19b_e1_probe.py']

c = connect(A, tries=8, wait=8)
sftp = c.open_sftp()

print('=' * 92)
print('① 结果文件：远端 vs 本地')
print('=' * 92)
ok_all = True
for rdir, sub in PAIRS:
    try:
        rfiles = set(f for f in sftp.listdir(rdir) if f.endswith('.csv'))
    except IOError:
        print('  %-28s 远端不存在' % rdir)
        continue
    ldir = os.path.join(RP('analysis', 'e2xt_a800'), sub)
    lfiles = set(f for f in os.listdir(ldir) if f.endswith('.csv')) if os.path.isdir(ldir) else set()
    miss = rfiles - lfiles
    same = sum(1 for f in rfiles & lfiles
               if sftp.stat(posixpath.join(rdir, f)).st_size == os.path.getsize(os.path.join(ldir, f)))
    flag = 'OK' if not miss and same == len(rfiles) else '★不一致'
    if flag != 'OK':
        ok_all = False
    print('  %-28s 远端 %3d / 本地 %3d / 同名且字节一致 %3d  %s%s'
          % (rdir, len(rfiles), len(lfiles), same, flag,
             ('  缺：%s' % sorted(miss)[:3] if miss else '')))

print()
print('=' * 92)
print('② 日志与补丁留档')
print('=' * 92)
for rp in LOGS + SCRIPTS:
    name = posixpath.basename(rp)
    try:
        st = sftp.stat(rp)
    except IOError:
        print('  %-34s 远端无' % name)
        continue
    dst = os.path.join(RP('analysis', 'e2xt_a800', 'env', 'a800_logs'), name) if rp in LOGS else os.path.join(RP('analysis', 'e2xt_a800', 'env', 'a800_scripts'), name)
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    if not (os.path.exists(dst) and os.path.getsize(dst) == st.st_size):
        sftp.get(rp, dst)
    h = hashlib.md5(io.open(dst, 'rb').read()).hexdigest()
    rmd5 = sh(c, 'md5sum %s | cut -d" " -f1' % rp).strip()
    print('  %-34s %9d B  md5 %s  %s' % (name, st.st_size, h[:12],
                                         'OK' if h == rmd5 else '★不一致(远端 %s)' % rmd5[:12]))
    if h != rmd5:
        ok_all = False

sftp.close()
print()
print('=' * 92)
print('③ 远端运行状态')
print('=' * 92)
print('  计算进程:', sh(c, 'nvidia-smi --query-compute-apps=pid,used_memory --format=csv,noheader') or '（无）')
print('  显存占用:', sh(c, 'nvidia-smi --query-gpu=memory.used --format=csv,noheader').strip())
print('  vllm 进程数:', sh(c, "ps -eo cmd | grep -i 'vllm' | grep -vc grep").strip())
print('  后台脚本:', sh(c, "ps -eo cmd | grep -E '[a]800_extra|[a]5_grid|[a]800_ablate' | wc -l").strip())
print('  磁盘:', sh(c, 'df -h / | tail -1').strip())
c.close()
print()
print('结论：%s' % ('**可以安全关机**（成果、日志、补丁均已留档，卡上无残留）' if ok_all
                  else '**暂缓关机**：上面有 ★ 标记的项未落档'))
