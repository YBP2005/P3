#!/bin/bash
# A5 追加实验（第三批）：把**尺度/模板中性**放到"有零可换"的家族与域上。
# 为什么需要：第二批把模板变体放在 Gemma 的密集域，而 Gemma 密集域**没有零可换**（base 0.000），
#   该域检验不了契约效应的中性。故第三批改在：
#     · InternVL3.5-8B / Phi-3.5-Vision @ **visdrone**（零池 95 / 92 个），做 s640 / s1536 / sys 三变体；
#     · 拉伸项：Qwen3-VL-32B-Instruct（只读缓存 63 GB BF16）@ st_a，做 native / s640 / sys，
#       因为密集域的"语料零"只在这个家族上大量存在（E2 锚点）。
# 先等第二批写完标记再开始（单卡串行）。
set -u
export BAILIAN_API=http://127.0.0.1:8000/v1/chat/completions
export DASHSCOPE_API_KEY=dummy
export VLLM_USE_FLASHINFER_SAMPLER=0
PY=/usr/local/miniconda3/bin/python
VLLM=/usr/local/miniconda3/bin/vllm
L=/root/logs/a5_extra3.log
mkdir -p /root/logs /root/e1_results_ablate3
say() { echo "[$(date +%H:%M:%S)] $*" >> "$L"; }

say "########## A5 追加实验（第三批）开始（先等第二批）##########"
for i in $(seq 1 120); do
  if grep -q A5_EXTRA2_DONE /root/logs/a5_extra2.log 2>/dev/null; then say "  第二批已完成，开始"; break; fi
  sleep 30
done
grep -q A5_EXTRA2_DONE /root/logs/a5_extra2.log 2>/dev/null || { say "  !! 等第二批超时，仍继续"; }

gpu_clear() {
  pkill -9 -i -f vllm 2>/dev/null; pkill -9 -f resource_tracker 2>/dev/null; sleep 3
  for i in $(seq 1 40); do
    used=$(nvidia-smi --query-gpu=memory.used --format=csv,noheader | tr -d ' MiB')
    [ "$used" -lt 500 ] && return 0; sleep 3
  done
  say "  !! 显存未清空：${used} MiB"; return 1
}

serve_up() {  # serve_up <name> <path> <tag> [extra...]
  local N=$1 MP=$2 TAG=$3; shift 3
  gpu_clear || return 1
  setsid nohup $VLLM serve "$MP" --served-model-name "$N" --max-model-len 8192 \
    --limit-mm-per-prompt '{"image": 1}' --gpu-memory-utilization 0.85 --max-num-seqs 24 --port 8000 \
    "$@" </dev/null > "/root/logs/serve_${TAG}.log" 2>&1 &
  for i in $(seq 1 40); do
    sleep 15
    curl -sf -m 5 -o /dev/null http://127.0.0.1:8000/v1/models && { say "  [$TAG] 起服就绪（$((i*15))s）"; return 0; }
  done
  say "  [$TAG] !! 起服失败"; tail -6 "/root/logs/serve_${TAG}.log" | sed 's/^/      /' >> "$L"; return 1
}

abl3() {  # abl3 <name> <tag> <ds>
  local N=$1 TAG=$2 DS=$3
  $PY /root/19f_probe_ablation.py --model "$N" --arms base,permit,channel \
      --ds "$DS" --n 150 --workers 8 --pool zero --imgsz 640 \
      --outdir /root/e1_results_ablate3 >> "$L" 2>&1
  say "  [$TAG/$DS] s640 rc=$?"
  $PY /root/19f_probe_ablation.py --model "$N" --arms base,permit,channel \
      --ds "$DS" --n 150 --workers 8 --pool zero --imgsz 1536 \
      --outdir /root/e1_results_ablate3 >> "$L" 2>&1
  say "  [$TAG/$DS] s1536 rc=$?"
  $PY /root/19f_probe_ablation.py --model "$N" --arms base,permit,channel \
      --ds "$DS" --n 150 --workers 8 --pool zero \
      --system 'You are a careful visual counting assistant. Follow the requested output format exactly.' \
      --outdir /root/e1_results_ablate3 >> "$L" 2>&1
  say "  [$TAG/$DS] sys rc=$?"
}

# ---------- 阶段 E：InternVL3.5-8B @ visdrone ----------
say "---- 阶段 E：InternVL3.5-8B @ visdrone ----"
if serve_up InternVL3_5-8B /root/models/InternVL3_5-8B extra3_ivl --trust-remote-code; then
  abl3 InternVL3_5-8B extra3_ivl visdrone
fi

# ---------- 阶段 F：Phi-3.5-Vision @ visdrone ----------
say "---- 阶段 F：Phi-3.5-Vision @ visdrone ----"
if serve_up Phi-3.5-vision-instruct /root/models/Phi-3.5-vision-instruct extra3_phi --trust-remote-code; then
  abl3 Phi-3.5-vision-instruct extra3_phi visdrone
fi

# ---------- 阶段 G（拉伸）：Qwen3-VL-32B-Instruct BF16 @ st_a（密集域有零） ----------
say "---- 阶段 G：Qwen3-VL-32B-Instruct BF16 @ st_a ----"
GMP=/model/ModelScope/Qwen/Qwen3-VL-32B-Instruct
if serve_up Qwen3-VL-32B-Instruct "$GMP" extra3_q32 --max-model-len 4096 --max-num-seqs 8; then
  for v in "" "--imgsz 640"; do
    say "  [q32/st_a] 变体 ${v:-native}"
    $PY /root/19f_probe_ablation.py --model Qwen3-VL-32B-Instruct --arms base,permit,channel \
        --ds st_a --n 150 --workers 8 --pool zero $v \
        --outdir /root/e1_results_ablate3 >> "$L" 2>&1
    say "     rc=$?"
  done
  say "  [q32/st_a] 变体 sys"
  $PY /root/19f_probe_ablation.py --model Qwen3-VL-32B-Instruct --arms base,permit,channel \
      --ds st_a --n 150 --workers 8 --pool zero \
      --system 'You are a careful visual counting assistant. Follow the requested output format exactly.' \
      --outdir /root/e1_results_ablate3 >> "$L" 2>&1
  say "     rc=$?"
fi
for f in /root/e1_results_ablate3/*_native.csv; do [ -e "$f" ] || continue; done

say "文件清点：ablate3 $(ls /root/e1_results_ablate3 | wc -l) 个"
say "########## A5 追加实验（第三批）结束 ##########"
echo "A5_EXTRA3_DONE" >> "$L"
