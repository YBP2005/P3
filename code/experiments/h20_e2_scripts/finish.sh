#!/bin/bash
# 收尾：定向补齐缺的包 → 生成 19c/19d → 资产校验 → 通过就启动实验
set -u
PY=/usr/local/miniconda3/bin/python3
L=/root/finish.log
say() { echo "[$(date +%H:%M:%S)] $*" | tee -a "$L"; }

say "收尾开始"

# ① 停掉低效的整轮接收（它会重下已解包的包）与重复的推送器
pkill -9 -f 'newh20_fetch_packs' 2>/dev/null && say "  停掉整轮接收"
pkill -9 -f 'newh20_push' 2>/dev/null && say "  停掉全部推送器"
sleep 5

# ② 定向补齐：环境包最关键，其次探针，其次 InternVL
say "=== 定向补齐 vllm312 / probes / models_ivl ==="
$PY -u /root/h20_fetch_missing.py vllm312.tar.gz probes.tar.gz models_ivl.tar >> "$L" 2>&1
say "  补齐结束"

# ③ 生成 19c / 19d（M机 上没有这两个）
say "=== 生成 19c/19d ==="
$PY /root/h20_make_19c.py >> "$L" 2>&1; say "  19c rc=$?"
$PY /root/h20_make_19d.py >> "$L" 2>&1; say "  19d rc=$?"

# ④ 环境可用性
say "=== 环境可用性 ==="
if [ -x /root/vllm312/bin/python ]; then
  /root/vllm312/bin/python -c "import vllm,torch;print('vllm',vllm.__version__,'torch',torch.__version__)" >> "$L" 2>&1
  /root/vllm312/bin/python -c "import PIL;print('PIL',PIL.__version__)" >> "$L" 2>&1
  say "  vllm312 可用"
else
  say "  !! vllm312 不存在，无法继续"
  echo FINISH_BLOCKED_ENV >> "$L"; exit 1
fi

# ⑤ 资产逐项校验
say "=== 资产校验 ==="
MISS=0
for d in /root/models/Qwen3-VL-32B-Instruct-AWQ-4bit/config.json \
         /root/models/Qwen3-VL-8B-Instruct-AWQ-4bit/config.json \
         /root/models/Qwen2.5-VL-7B-Instruct-AWQ/config.json \
         /root/models/InternVL2_5-8B-AWQ/config.json \
         /root/dense/shanghaitech/counts.csv \
         /root/dense/ucf_qnrf/counts.csv \
         /root/dense_results/vlm_st_a_base_whole.csv \
         /root/dense_results/vlm_ucf_base_whole.csv \
         /root/19b_e1_probe.py /root/19c_probe_paraphrase.py /root/19d_probe_nonzero.py \
         /model/ModelScope/Qwen/Qwen3-VL-32B-Instruct/config.json \
         /model/ModelScope/Qwen/Qwen3-VL-8B-Instruct/config.json; do
  if [ -e "$d" ]; then say "  OK  $d"; else say "  缺  $d"; MISS=$((MISS+1)); fi
done
say "缺失项 = $MISS"

# ⑥ 重启单个推送器（结果双备份）
say "=== 重启推送器（单个）==="
cd /root
setsid nohup $PY -u /root/newh20_push.py < /dev/null > /root/push.log 2>&1 &
say "  推送器 pid=$!"

if [ "$MISS" -gt 0 ]; then
  say "!! 有缺失，先不启动实验"
  echo FINISH_BLOCKED_ASSETS >> "$L"; exit 1
fi

# ⑦ 启动实验（exp.sh 自带按模型分组 + 就绪重试）
say "=== 启动实验 ==="
cd /root
setsid nohup bash /root/exp.sh < /dev/null > /root/logs/exp.log 2>&1 &
say "  exp.sh pid=$!"
echo FINISH_DONE >> "$L"
