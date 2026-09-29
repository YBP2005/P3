#!/bin/bash
# 新 H20 实验主脚本（扩满版）——机器随时可能被回收，故一次排完。
#
# 组织方式：**按模型分组**，每个模型只起一次服务，连着跑完它的所有子任务。
#   ⇒ 服务启动从 18 次降到 6 次；且先跑完的整块就是最有价值的证据。
#
# 关键配置（上一台 H20 用血换来的）：
#   · AWQ 模型**不能**加 --attention-backend FLASH_ATTN —— 会在加载阶段被 SIGKILL；
#     故默认不带，失败才回退带（BF16 在 Hopper 上可能需要它绕 flashinfer JIT）。
#   · VLLM_USE_FLASHINFER_SAMPLER=0 必须保留（env 为 sm_120 编译，H20 是 sm_90）。
#   · 就绪判断用 curl -f，否则 HTTP 错误会被当成 READY。
#   · 探针输出落盘到单独日志，失败时能看到真实报错。
set -u
export VLLM_USE_FLASHINFER_SAMPLER=0
export BAILIAN_API=http://127.0.0.1:8000/v1/chat/completions
export DASHSCOPE_API_KEY=dummy
PY=/root/vllm312/bin/python
VLLM=/root/vllm312/bin/vllm
mkdir -p /root/e1_results /root/e1_results_nonzero /root/logs

gpu_clear() {
  for p in $(nvidia-smi --query-compute-apps=pid --format=csv,noheader 2>/dev/null | tr -d ' '); do
    [ -n "$p" ] && kill -9 "$p" 2>/dev/null
  done
}
ready() { curl -s -f -m 5 -o /dev/null http://127.0.0.1:8000/v1/models; }
serving() { curl -s -m 5 http://127.0.0.1:8000/v1/models 2>/dev/null | grep -q "\"$1\""; }

start_only() {  # $1 model $2 name $3 log $4 util  $5.. extra
  local M=$1 N=$2 L=$3 U=$4; shift 4
  nohup $VLLM serve "$M" --served-model-name "$N" --max-model-len 8192 \
    --limit-mm-per-prompt '{"image": 1}' \
    --mm-processor-kwargs '{"max_pixels": 1048576, "min_pixels": 200704}' \
    --gpu-memory-utilization "$U" --max-num-seqs 24 --port 8000 "$@" > "$L" 2>&1 &
  local P=$! i
  for i in $(seq 1 48); do
    sleep 15
    kill -0 $P 2>/dev/null || { echo "      进程第 $((i*15))s 消失"; return 1; }
    ready && return 0
  done
  return 1
}

serve() {  # $1 model $2 name $3 log $4 util $5.. extra
  local M=$1 N=$2 L=$3 U=$4; shift 4
  [ -d "$M" ] || { echo "[$(date +%H:%M:%S)]   !! 模型目录不存在: $M"; return 1; }
  if serving "$N"; then echo "[$(date +%H:%M:%S)]   复用已就绪服务 $N"; return 0; fi
  pkill -9 -f 'vllm serve' 2>/dev/null; sleep 5; gpu_clear; sleep 5
  echo "[$(date +%H:%M:%S)]   起服务 $N（不带 attention-backend）"
  if start_only "$M" "$N" "$L" "$U" "$@"; then
    echo "[$(date +%H:%M:%S)]     READY 显存 $(nvidia-smi --query-gpu=memory.used --format=csv,noheader)"
    return 0
  fi
  echo "[$(date +%H:%M:%S)]     失败 → 回退带 --attention-backend FLASH_ATTN"
  pkill -9 -f 'vllm serve' 2>/dev/null; sleep 5; gpu_clear; sleep 5
  if start_only "$M" "$N" "$L" "$U" --attention-backend FLASH_ATTN "$@"; then
    echo "[$(date +%H:%M:%S)]     READY(回退)"
    return 0
  fi
  echo "[$(date +%H:%M:%S)]   !! $N 两种配置都起不来；日志尾："
  tail -6 "$L" | sed 's/^/        /'
  return 1
}

run() {  # $1 探针 $2 模型名 $3 数据集 $4 臂 $5 标记 $6 reps
  local P=$1 N=$2 DS=$3 A=$4 TAG=$5 R=${6:-1}
  local d before after rc
  for d in $DS; do
    case "$P" in
      19d*) before=$(ls /root/e1_results_nonzero/ 2>/dev/null | wc -l);;
      *)    before=$(ls /root/e1_results/ 2>/dev/null | wc -l);;
    esac
    echo "[$(date +%H:%M:%S)]     跑 $P / $N / $d / $A (reps=$R)"
    if [ "$R" -gt 1 ]; then
      $PY /root/$P --model "$N" --arms "$A" --ds "$d" --n 1000 --workers 8 --reps "$R" \
        > "/root/logs/probe_${TAG}_${d}.log" 2>&1
    else
      $PY /root/$P --model "$N" --arms "$A" --ds "$d" --n 1000 --workers 8 \
        > "/root/logs/probe_${TAG}_${d}.log" 2>&1
    fi
    rc=$?
    case "$P" in
      19d*) after=$(ls /root/e1_results_nonzero/ 2>/dev/null | wc -l);;
      *)    after=$(ls /root/e1_results/ 2>/dev/null | wc -l);;
    esac
    echo "[$(date +%H:%M:%S)]       rc=$rc 文件 $before→$after"
    if [ "$after" -le "$before" ]; then
      echo "[$(date +%H:%M:%S)]       !! 未产出新文件（池可能为空），探针日志尾："
      tail -5 "/root/logs/probe_${TAG}_${d}.log" | sed 's/^/          /'
    fi
  done
}

AWQ32=/root/models/Qwen3-VL-32B-Instruct-AWQ-4bit
AWQ8=/root/models/Qwen3-VL-8B-Instruct-AWQ-4bit
Q25=/root/models/Qwen2.5-VL-7B-Instruct-AWQ
IVL=/root/models/InternVL2_5-8B-AWQ
BF32=/model/ModelScope/Qwen/Qwen3-VL-32B-Instruct
BF8=/model/ModelScope/Qwen/Qwen3-VL-8B-Instruct
ALL=base,permit,bestA,bestB,bestC,channel
NZ=base,permit,channel

echo "########## 全部任务开始 $(date +%H:%M:%S) ##########"

# ========== ① AWQ 32B（与语料同为 4bit：最核心）==========
if serve $AWQ32 qwen3-vl-32b-awq /root/logs/v_awq32.log 0.75; then
  run 19b_e1_probe.py qwen3-vl-32b-awq "st_a ucf" $ALL awq32_census
  run 19d_probe_nonzero.py qwen3-vl-32b-awq "st_a ucf" $NZ awq32_nz
  run 19c_probe_paraphrase.py qwen3-vl-32b-awq "st_a ucf" permitB,permitC,channelB awq32_para
  run 19b_e1_probe.py qwen3-vl-32b-awq "st_a ucf" $NZ awq32_reps3 3
fi

# ========== ② BF16 32B（精度轴）==========
if serve $BF32 qwen3-vl-32b-bf16 /root/logs/v_bf32.log 0.90; then
  run 19b_e1_probe.py qwen3-vl-32b-bf16 "st_a ucf" $ALL bf32_census
  run 19d_probe_nonzero.py qwen3-vl-32b-bf16 "st_a ucf st_b" $NZ bf32_nz
  run 19c_probe_paraphrase.py qwen3-vl-32b-bf16 "st_a ucf" permitB,permitC,channelB bf32_para
  run 19b_e1_probe.py qwen3-vl-32b-bf16 "st_a" $NZ bf32_reps3 3
fi

# ========== ③ 8B AWQ（规模×精度交叉）==========
if serve $AWQ8 qwen3-vl-8b-awq /root/logs/v_awq8.log 0.75; then
  run 19b_e1_probe.py qwen3-vl-8b-awq "st_a ucf" $ALL awq8_census
  run 19d_probe_nonzero.py qwen3-vl-8b-awq "st_a ucf" $NZ awq8_nz
  run 19c_probe_paraphrase.py qwen3-vl-8b-awq "st_a ucf" permitB,permitC,channelB awq8_para
  run 19b_e1_probe.py qwen3-vl-8b-awq "st_a" $NZ awq8_reps3 3
fi

# ========== ④ 8B BF16（规模轴）==========
if serve $BF8 qwen3-vl-8b-bf16 /root/logs/v_bf8.log 0.75; then
  run 19b_e1_probe.py qwen3-vl-8b-bf16 "st_a ucf" $ALL bf8_census
  run 19d_probe_nonzero.py qwen3-vl-8b-bf16 "st_a ucf" $NZ bf8_nz
fi

# ========== ⑤ Qwen2.5-VL-7B-AWQ（跨族）==========
if serve $Q25 qwen25vl-7b-awq /root/logs/v_q25.log 0.75; then
  run 19b_e1_probe.py qwen25vl-7b-awq "st_a ucf" $ALL q25_census
  run 19d_probe_nonzero.py qwen25vl-7b-awq "st_a ucf" $NZ q25_nz
fi

# ========== ⑥ InternVL2.5-8B-AWQ（跨族）==========
if serve $IVL internvl25-8b-awq /root/logs/v_ivl.log 0.75 --trust-remote-code; then
  run 19b_e1_probe.py internvl25-8b-awq "st_a ucf" $ALL ivl_census
  run 19d_probe_nonzero.py internvl25-8b-awq "st_a ucf st_b" $NZ ivl_nz
fi

echo "########## 全部任务结束 $(date +%H:%M:%S) ##########"
echo "--- 零池结果 ---"; ls -la /root/e1_results/ 2>/dev/null | tail -30
echo "--- 非零池结果 ---"; ls -la /root/e1_results_nonzero/ 2>/dev/null | tail -30
echo "--- 各文件行数 ---"
for f in /root/e1_results/*.csv /root/e1_results_nonzero/*.csv; do
  [ -e "$f" ] && echo "  $(basename $f): $(( $(wc -l < "$f") - 1 )) 行"
done
echo EXP_ALL_DONE
