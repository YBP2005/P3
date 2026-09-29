#!/bin/bash
# 准备多域实验的前置件：
#  ① 19b 本体确认存在（作为母本，逐字不改）
#  ② 生成 19e_probe_multi.py 并逐字校验
#  ③ 为新域准备语料 base CSV（探针按 /root/dense_results/vlm_<ds>_base_whole.csv 取名）
mkdir -p /root/dense_results
echo "=== ① 新域语料 base CSV 落地 ==="
cp -f /root/corpus_new/aer_visdrone_base.csv    /root/dense_results/vlm_visdrone_base_whole.csv
cp -f /root/corpus_new/aer_aitod_base.csv       /root/dense_results/vlm_aitod_base_whole.csv
cp -f /root/corpus_new/ext_countbench_base.csv  /root/dense_results/vlm_countbench_base_whole.csv
ls -la /root/dense_results/
echo
echo "=== ② 逐项核对（item 覆盖率）==="
/usr/local/miniconda3/bin/python3 - <<'PY'
import csv, os
base = {'visdrone': '/root/dense_results/vlm_visdrone_base_whole.csv',
        'aitod': '/root/dense_results/vlm_aitod_base_whole.csv',
        'countbench': '/root/dense_results/vlm_countbench_base_whole.csv'}
gtf = {'visdrone': '/root/aerial/gt_visdrone.csv',
       'aitod': '/root/aerial/gt_aitod.csv',
       'countbench': '/root/ext/countbench/counts.csv'}
for ds in base:
    with open(base[ds], encoding='utf-8-sig') as f:
        bs = list(csv.DictReader(f))
    if ds == 'countbench':
        with open(gtf[ds], encoding='utf-8-sig') as f:
            gt = {os.path.splitext(os.path.basename(r['file']))[0]: int(r['number'])
                  for r in csv.DictReader(f)}
    else:
        with open(gtf[ds], encoding='utf-8-sig') as f:
            gt = {r['item']: int(r['gt']) for r in csv.DictReader(f)}
    hit = sum(1 for r in bs if r['item'] in gt)
    z = sum(1 for r in bs if str(r.get('pred','')).strip() in ('0','0.0') and r['item'] in gt)
    nz = hit - z
    print('  %-11s base %d 行，与 GT 交集 %d，零池 %d，非零池 %d' % (ds, len(bs), hit, z, nz))
PY
echo
echo "=== ③ 生成 19e ==="
/usr/local/miniconda3/bin/python3 /root/make_19e.py
echo GEN_19E_DONE
