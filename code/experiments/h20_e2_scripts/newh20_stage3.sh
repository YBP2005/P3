#!/bin/bash
# 第三阶段：等接续器完成 → 校验资产 → 小样本验证探针通路 → 通过才启动全部实验
# 目的：既不让 GPU 空转，又避免在"通路未验证"的情况下白跑 10 个任务（上一台的教训）。
set -u
export VLLM_USE_FLASHINFER_SAMPLER=0
export BAILIAN_API=http://127.0.0.1:8000/v1/chat/completions
export DASHSCOPE_API_KEY=dummy
PY=/root/vllm312/bin/python
L=/root/stage3.log
say() { echo "[$(date +%H:%M:%S)] $*" | tee -a "$L"; }

say "第三阶段启动，等接续器完成"
while ! grep -q CHAIN_ALL_DONE /root/chain.log 2>/dev/null; do sleep 30; done
say "接续器已完成"

say "=== 资产校验 ==="
MISS=0
for d in /root/vllm312/bin/python \
         /root/models/Qwen3-VL-32B-Instruct-AWQ-4bit/config.json \
         /root/models/Qwen3-VL-32B-Instruct-AWQ-4bit/model.safetensors.index.json \
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
say "缺失项数 = $MISS"
ls -d /root/dense/shanghaitech/images/part_A_test 2>/dev/null && say "  OK  图像目录" || say "  缺  图像目录"

say "=== env 可用性 ==="
$PY -c "import vllm,torch;print('vllm',vllm.__version__,'torch',torch.__version__)" >> "$L" 2>&1
$PY -c "import PIL;print('PIL',PIL.__version__)" >> "$L" 2>&1
tail -3 "$L"

if [ "$MISS" -gt 0 ]; then
  say "!! 有缺失，不启动实验（等我处理）"
  echo STAGE3_BLOCKED >> "$L"
  exit 1
fi

say "=== 小样本验证：起 AWQ 服务 ==="
pkill -9 -f 'vllm serve' 2>/dev/null; sleep 5
for p in $(nvidia-smi --query-compute-apps=pid --format=csv,noheader 2>/dev/null | tr -d ' '); do
  [ -n "$p" ] && kill -9 "$p" 2>/dev/null
done
sleep 5
nohup /root/vllm312/bin/vllm serve /root/models/Qwen3-VL-32B-Instruct-AWQ-4bit \
  --served-model-name qwen3-vl-32b-awq --max-model-len 8192 \
  --limit-mm-per-prompt '{"image": 1}' \
  --mm-processor-kwargs '{"max_pixels": 1048576, "min_pixels": 200704}' \
  --gpu-memory-utilization 0.75 --max-num-seqs 24 --port 8000 \
  > /root/logs/sanity_awq.log 2>&1 &
SP=$!
OK=0
for i in $(seq 1 48); do
  sleep 15
  kill -0 $SP 2>/dev/null || { say "  服务第 $((i*15))s 消失"; break; }
  if curl -s -f -m 4 -o /dev/null http://127.0.0.1:8000/v1/models; then
    say "  服务 READY after $((i*15))s"; OK=1; break
  fi
done

if [ "$OK" != "1" ]; then
  say "!! 服务起不来，日志尾："; tail -15 /root/logs/sanity_awq.log | sed 's/^/    /' | tee -a "$L"
  echo STAGE3_SERVE_FAILED >> "$L"; exit 1
fi

say "=== 小样本探针（n=8, st_a, base+permit）==="
rm -f /root/e1_results/*.csv 2>/dev/null
$PY /root/19b_e1_probe.py --model qwen3-vl-32b-awq --arms base,permit --ds st_a --n 8 --workers 2 \
  > /root/logs/sanity_probe.log 2>&1
say "  探针 rc=$?"
cat /root/logs/sanity_probe.log | sed 's/^/    /' | tee -a "$L"
NF=$(ls /root/e1_results/ 2>/dev/null | wc -l)
say "  产出文件数 = $NF"

if [ "$NF" -lt 1 ]; then
  say "!! 探针未产出，不启动实验"
  echo STAGE3_PROBE_FAILED >> "$L"; exit 1
fi

say "=== 通路验证通过，清理并启动全部实验 ==="
rm -f /root/e1_results/*.csv
pkill -9 -f 'vllm serve' 2>/dev/null; sleep 5
for p in $(nvidia-smi --query-compute-apps=pid --format=csv,noheader 2>/dev/null | tr -d ' '); do
  [ -n "$p" ] && kill -9 "$p" 2>/dev/null
done
sleep 5
if ps -eo cmd | grep -q '[n]ewh20_exp'; then
  say "实验脚本已在运行"
else
  cd /root
  setsid nohup bash /root/exp.sh < /dev/null > /root/logs/exp.log 2>&1 &
  say "  已启动 exp.sh pid=$!"
fi
echo STAGE3_DONE >> "$L"
