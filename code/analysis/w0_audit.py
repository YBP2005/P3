# -*- coding: utf-8 -*-
"""w0_audit.py — 独立家族前瞻验证（W0）：**零 GPU 资产审计 + 采样框枚举**。

只做只读盘点，不启动任何服务、不写任何数据：
  1. 机器与 GPU 状态（确认显存干净、磁盘余量）；
  2. 既有资产核对（数据目录文件数/字节、探针 md5、冻结判据 md5）——与交接单对齐；
  3. ★ **枚举可用的开源 VLM 采样框**：遍历只读镜像 /model/ModelScope 与 /root/models，
     打印候选与体积；并标出**已被 E2/E3/FSC 面板用过**的家族（必须排除，否则不是独立样本）；
  4. 输出机器可读的 w1_frame_raw.json 供本地据"冻结抽样规则"生成 w1_frame.json。

用法：python w0_audit.py
"""
import io
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from a800_conn import connect, sh  # noqa: E402

sys.stdout.reconfigure(encoding='utf-8')
HOST = ('<REDACTED-A800-HOST>', 23, 'root', '<REDACTED-A800-PASSWORD>')

# 已用过（**不可**作为独立样本）：E2/E3 主格 + FSC-147 面板 + 消融/B2 试跑
USED = [
    'gemma-3-12b', 'gemma3-12b', 'internvl3_5-8b', 'internvl3.5-8b', 'phi-3.5-vision',
    'llava-onevision', 'llava-ov', 'qwen3-vl-32b', 'qwen3-vl-8b', 'qwen3-vl-4b',
    'qwen3-vl-30b-a3b', 'qwen2.5-vl-3b', 'qwen2.5-vl-7b',
]


def main():
    c = connect(HOST)
    out = {}
    print('=' * 78)
    print('W0 资产审计（只读）')
    print('=' * 78)
    for label, cmd in [
        ('kernel/host', 'hostname; uname -r; nproc; free -g | head -2'),
        ('gpu', 'nvidia-smi --query-gpu=name,memory.total,memory.used,driver_version --format=csv,noheader'),
        ('compute procs', 'nvidia-smi --query-compute-apps=pid,used_memory --format=csv,noheader || true'),
        ('disk', 'df -h / /root 2>/dev/null | sed -n "1,4p"'),
        ('python/vllm', '/usr/local/miniconda3/bin/python -c "import torch,vllm;print(\'torch\',torch.__version__,\'vllm\',vllm.__version__,\'cuda\',torch.cuda.is_available())"'),
        ('data dirs', 'for d in /root/aerial /root/dense /root/corpus_new /root/dense_results; do '
                      'n=$(find $d -type f 2>/dev/null | wc -l); b=$(du -sb $d 2>/dev/null | cut -f1); '
                      'echo "$d files=$n bytes=$b"; done'),
        ('probes', 'md5sum /root/19e_probe_multi.py /root/19b_e1_probe.py /root/19f_probe_ablation.py '
                   '/root/19g_probe_fsc.py 2>/dev/null'),
        ('frozen criteria', 'md5sum /root/a5_criteria_frozen.json 2>/dev/null; ls -la /root/*.json 2>/dev/null | head -20'),
        ('result dirs', 'for d in /root/e1_results /root/e1_results_nonzero /root/e1_results_ablate '
                        '/root/e1_results_ablate3 /root/e1_results_build /root/e1_results_reps '
                        '/root/fsc_results; do echo "$d $(ls $d 2>/dev/null | wc -l)"; done'),
        ('fsc assets', 'ls -d /root/fsc* /root/FSC* 2>/dev/null; du -sh /root/fsc* 2>/dev/null | head'),
        ('logs', 'ls -la /root/logs 2>/dev/null | tail -8'),
    ]:
        r = sh(c, cmd, t=180)
        out[label] = r
        print('\n--- %s ---\n%s' % (label, r))

    # 采样框枚举
    print('\n' + '=' * 78)
    print('采样框枚举：只读镜像 /model/ModelScope（可能很大，逐层列到模型目录）')
    print('=' * 78)
    enum_cmd = (
        'for root in /model/ModelScope /model /root/models; do '
        '  [ -d "$root" ] || continue; echo "### $root"; '
        '  find "$root" -maxdepth 3 -mindepth 2 -type d 2>/dev/null | head -300; '
        'done'
    )
    listing = sh(c, enum_cmd, t=300)
    print(listing)

    # 只读卷通常按 组织/模型 分层，尽量识别"含 config.json 的模型目录"
    print('\n' + '=' * 78)
    print('含 config.json 的模型目录（更可靠的候选判据，最多 400 条）')
    print('=' * 78)
    models_cmd = (
        'for root in /model/ModelScope /root/models; do [ -d "$root" ] || continue; '
        '  find "$root" -maxdepth 4 -name config.json -printf "%h\\n" 2>/dev/null | head -400; done'
    )
    model_dirs = [x.strip() for x in sh(c, models_cmd, t=400).splitlines() if x.strip()]
    for m in model_dirs:
        print('  ' + m)

    print('\n' + '=' * 78)
    print('各候选目录体积（只读卷 du 可能慢，超时则单独补）')
    print('=' * 78)
    size_map = {}
    for m in model_dirs[:120]:
        r = sh(c, 'du -sm %s 2>/dev/null | cut -f1' % json.dumps(m), t=60)
        try:
            size_map[m] = int(r.strip())
        except Exception:
            size_map[m] = None
    for m in model_dirs:
        if m in size_map:
            print('  %6s MB  %s' % (size_map[m], m))

    c.close()
    out['model_dirs'] = model_dirs
    out['size_mb'] = size_map
    out['used_markers'] = USED
    with io.open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              'w0_frame_raw.json'), 'w', encoding='utf-8', newline='\n') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print('\n写出 w0_frame_raw.json（模型目录 %d 个）' % len(model_dirs))


if __name__ == '__main__':
    main()
