#!/bin/bash
# 重新生成 19e（修正 countbench 的 item 键），并复验三个新域的池子大小
echo "=== 重新生成 19e ==="
/usr/local/miniconda3/bin/python3 /root/make_19e.py
echo
echo "=== 复验三域池子（按 19e 的 load_gt 逻辑走一遍）==="
/usr/local/miniconda3/bin/python3 - <<'PY'
import csv, os, sys
sys.path.insert(0, '/root')
import importlib.util
spec = importlib.util.spec_from_file_location('p19e', '/root/19e_probe_multi.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
for ds in ('visdrone', 'aitod', 'countbench'):
    gt = m.load_gt(ds)
    base = '/root/dense_results/vlm_%s_base_whole.csv' % ds
    with open(base, encoding='utf-8-sig') as f:
        rows = list(csv.DictReader(f))
    z = [r['item'] for r in rows
         if str(r.get('pred', '')).strip() in ('0', '0.0') and r.get('item') in gt]
    nz = [r['item'] for r in rows
          if str(r.get('pred', '')).strip() not in ('0', '0.0') and r.get('item') in gt]
    print('  %-11s GT %-4d  base %-4d  零池 %-4d  非零池 %-4d' % (ds, len(gt), len(rows), len(z), len(nz)))
    # 抽查图像路径能否解析
    for it in (z[:1] + nz[:1]):
        d = m.DS_DIRS[ds]
        hit = None
        for e in ('', '.jpg', '.png', '.jpeg', '.tif', '.TIF', '.bmp'):
            if os.path.exists(os.path.join(d, it + e)):
                hit = it + e
                break
        print('      图像解析 %-42s -> %s' % (it, hit or '**失败**'))
PY
echo PREP2_DONE
