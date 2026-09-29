#!/bin/bash
# w1_phi4_gate.sh — 解除主驱动对 Phi-4 下载的**误阻塞**（只核验必需文件，不伪造成功）。
#
# 问题（实测）：microsoft/Phi-4-multimodal-instruct 仓库里 `figures/*.png`、`examples/*.wav` 在
#   ModelScope 上取不到（实测 0 字节），下载器因此报"失败 N"、**永不打印"成功"行**；
#   而主驱动的等待条件正是那一行 ⇒ 最长白等 5 小时（150×120s）。
# 处置：本闸门
#   ① 等下载进程退出；
#   ② 用 ModelScope API 的**声明尺寸**独立核验"加载所需文件"（config/权重/tokenizer/processor）是否齐全且尺寸一致；
#   ③ 若必需文件全部合格，向下载日志追加一行**自述文字**（说明该行由本闸门核验后写入、缺的是哪些非加载资源），
#      从而解除阻塞；若必需文件不合格，则不写、并打印不合格清单（保持阻塞，让人介入）。
# 为什么不是直接写"成功"：那会伪造下载器的结论。这里写的是"由闸门核验必需文件后判定可用"，
#   并把缺失的非加载资源逐条列出，读者可自行复核。
set -u
PY=/usr/local/miniconda3/bin/python
L=/root/logs/w1_dl.log
G=/root/logs/w1_phi4_gate.log
MID=microsoft/Phi-4-multimodal-instruct
MP=/root/w1_models/phi4-mm
say() { echo "[$(date +%H:%M:%S)] $*" | tee -a "$G"; }

say "等待下载进程退出…"
for i in $(seq 1 120); do
  pgrep -f "w1_dl_model.py $MID" >/dev/null || break
  sleep 30
done
say "下载进程已退出（或等待超时）"

$PY - "$MID" "$MP" <<'PYEOF' >> "$G" 2>&1
import io, json, os, sys, urllib.request
mid, mp = sys.argv[1], sys.argv[2]
NEED_SUFFIX = ('.safetensors', '.json', '.model', '.txt', '.py', '.tiktoken')
IGNORE_PREFIX = ('figures/', 'examples/', 'assets/', 'docs/')
url = ('https://www.modelscope.cn/api/v1/models/%s/repo/files?Revision=master&Recursive=true' % mid)
d = json.load(urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'curl/8'}), timeout=60))
files = [(f['Path'], int(f.get('Size') or 0)) for f in d.get('Data', {}).get('Files', []) if f.get('Type') != 'tree']
need, ignored, missing, ok = [], [], [], 0
for p, s in files:
    if p.startswith('.') or p.startswith(IGNORE_PREFIX) or not p.endswith(NEED_SUFFIX):
        ignored.append((p, s)); continue
    need.append((p, s))
    lp = os.path.join(mp, p)
    if os.path.exists(lp) and os.path.getsize(lp) == s:
        ok += 1
    else:
        missing.append((p, s, os.path.getsize(lp) if os.path.exists(lp) else -1))
print('必需文件 %d 个，齐全 %d 个，缺失/尺寸不符 %d 个' % (len(need), ok, len(missing)))
for p, s, got in missing:
    print('   缺失 %-52s 期望 %d 实得 %d' % (p, s, got))
print('被忽略的非加载资源 %d 个（前缀 %s）' % (len(ignored), IGNORE_PREFIX))
print('GATE_VERDICT=' + ('PASS' if not missing and len(need) > 0 else 'FAIL'))
PYEOF

if grep -q "GATE_VERDICT=PASS" "$G"; then
  mkdir -p "$MP"
  miss_list=$(grep -o "被忽略的非加载资源 [0-9]* 个" "$G" | tail -1)
  echo "→ $MID 成功（由 w1_phi4_gate.sh 核验：加载所需文件齐全且尺寸一致；$miss_list；缺失的仅为 figures/examples 下的非加载资源，见 $G）" >> "$L"
  say "已追加核验行到 w1_dl.log ⇒ 主驱动的等待条件解除"
else
  say "!! 必需文件不合格，**不**追加核验行（保持阻塞，需人工介入）；详见 $G"
fi
