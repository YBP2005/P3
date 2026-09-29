#!/bin/bash
# FSC-147 下载（只取测试集抽样 300 张 + 标注 + 划分），来源：HF 数据集仓 isentropic/FSC147
# 目的：为 B1「公开基准上的口径→榜单」实验准备数据。
# 注意：本机 HF API 可用（模型仓 401，但 datasets 仓 200）。
set -u
L=/root/logs/fsc_dl.log
mkdir -p /root/logs /root/fsc147
say() { echo "[$(date +%H:%M:%S)] $*" >> "$L"; }
say "########## FSC-147 下载开始 ##########"

BASE=https://huggingface.co/datasets/isentropic/FSC147/resolve/main
cd /root/fsc147
for f in Train_Test_Val_FSC_147.json annotation_FSC147_384.json; do
  if [ ! -s "$f" ]; then
    say "下载 $f"
    curl -sL -m 900 -o "$f" "$BASE/$f" || { say "  !! $f 失败"; exit 1; }
  else
    say "$f 已存在（$(stat -c %s "$f") 字节）"
  fi
done
say "标注 $(stat -c %s annotation_FSC147_384.json) 字节；划分 $(stat -c %s Train_Test_Val_FSC_147.json) 字节"

# 抽样并逐图下载
/usr/local/miniconda3/bin/python - <<'PY'
import io, json, os, random, subprocess, sys, time
sys.stdout.reconfigure(encoding='utf-8')
D = '/root/fsc147'
ann = json.load(io.open(os.path.join(D, 'annotation_FSC147_384.json')))
sp = json.load(io.open(os.path.join(D, 'Train_Test_Val_FSC_147.json')))
test = sp['test'] if isinstance(sp, dict) else sp
print('测试集图片数：%d' % len(test))
# 计数（FSC 的标注里 boxes 每个含 count 字段）
cnt = {}
for k, v in ann.items():
    try:
        cnt[k] = float(v.get('box_examples_coordinates') and sum(
            b.get('count', 0) for b in v.get('boxes', [])) or 0)
    except Exception:
        cnt[k] = 0
test = [t for t in test if t in ann]
test.sort(key=lambda k: cnt.get(k, 0))
# 按 GT 分位分层抽 300（层内均匀取）
N = 300
step = max(1, len(test) // N)
pick = test[::step][:N]
print('抽样 %d 张（GT 从 %.0f 到 %.0f，分层）' % (len(pick), cnt.get(pick[0], 0), cnt.get(pick[-1], 0)))
io.open(os.path.join(D, 'sample_test_ids.txt'), 'w', encoding='utf-8').write('\n'.join(pick))
os.makedirs(os.path.join(D, 'images'), exist_ok=True)
BASE = 'https://huggingface.co/datasets/isentropic/FSC147/resolve/main/images_384_VarV2'
ok = fail = 0
for i, k in enumerate(pick):
    p = os.path.join(D, 'images', k)
    if os.path.exists(p) and os.path.getsize(p) > 1000:
        ok += 1
        continue
    r = subprocess.run(['curl', '-sL', '-m', '120', '-o', p, '%s/%s' % (BASE, k)])
    if r.returncode == 0 and os.path.exists(p) and os.path.getsize(p) > 1000:
        ok += 1
    else:
        fail += 1
    if (i + 1) % 50 == 0:
        print('  进度 %d/%d（成功 %d 失败 %d）' % (i + 1, len(pick), ok, fail), flush=True)
print('图片下载完成：成功 %d 失败 %d' % (ok, fail))
PY
rc=$?
say "python 抽样下载 rc=$rc"
ls /root/fsc147/images | wc -l >> "$L"
say "images 目录文件数见上"
echo "FSC_DL_DONE" >> "$L"
say "########## FSC-147 下载结束 ##########"
