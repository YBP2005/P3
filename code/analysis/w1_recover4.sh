#!/bin/bash
# w1_recover4.sh — Molmo-7B-D 第三次尝试（前两次都是**环境缺件**，均已修复并记录）
#   ① 首轮：缺 `trust_remote_code`（仓库含自定义代码）→ 加参数；
#   ② 次轮：自定义 image processor 需要 `import tensorflow` → 装 tensorflow-cpu 2.21.0（并已验证 vLLM/torch 环境完好）；
#   ③ 本轮：应可起服。跑"普查 + FSC 示例臂"，完成后**重新打包**（覆盖上一版 bundle）。
# 纪律：同一仪器、同一 smoke 门、单卡串行、产物写同一目录。
set -u
export BAILIAN_API=http://127.0.0.1:8000/v1/chat/completions
export DASHSCOPE_API_KEY=dummy
export VLLM_USE_FLASHINFER_SAMPLER=0
export TF_CPP_MIN_LOG_LEVEL=3
export TF_ENABLE_ONEDNN_OPTS=0
PY=/usr/local/miniconda3/bin/python
VLLM=/usr/local/miniconda3/bin/vllm
L=/root/logs/w1_recover4.log
R=/root/w1_results
N=Molmo-7B-D-0924
MP=/root/w1_models/molmo-7b-d
mkdir -p "$R"/{zero,nonzero,smoke,fsc} /root/logs
say() { echo "[$(date +%H:%M:%S)] $*" | tee -a "$L"; }

gpu_clear() {
  pkill -9 -i -f vllm 2>/dev/null; pkill -9 -f resource_tracker 2>/dev/null; sleep 3
  for i in $(seq 1 40); do
    used=$(nvidia-smi --query-gpu=memory.used --format=csv,noheader | tr -d ' MiB')
    [ "$used" -lt 500 ] && return 0; sleep 3
  done
  say "  !! 显存未清空：${used} MiB"; return 1
}

say "===== Molmo 第三次尝试（缺件已修复：trust_remote_code + tensorflow）====="
gpu_clear || exit 1
setsid nohup $VLLM serve "$MP" --served-model-name "$N" --max-model-len 4096 \
  --limit-mm-per-prompt '{"image": 1}' --gpu-memory-utilization 0.85 --max-num-seqs 16 --port 8000 \
  --trust-remote-code </dev/null > "/root/logs/serve_w1r4_molmo.log" 2>&1 &
for i in $(seq 1 60); do
  sleep 15
  curl -sf -m 5 -o /dev/null http://127.0.0.1:8000/v1/models && { say "起服就绪 $((i*15))s"; break; }
  grep -qiE "Engine core initialization failed|ImportError|is not supported" /root/logs/serve_w1r4_molmo.log 2>/dev/null && \
    { say "!! 起服报错（早停）"; grep -E "ERROR|Error" /root/logs/serve_w1r4_molmo.log | tail -3 | sed 's/^/   /' | tee -a "$L"; exit 1; }
done
curl -sf -m 5 -o /dev/null http://127.0.0.1:8000/v1/models || { say "!! 起服超时"; exit 1; }

# smoke 门（同主面板）
rm -f "$R/smoke/e1_${N}_st_a_base_native.csv" "$R/smoke/e1_${N}_visdrone_base_native.csv"
$PY /root/19f_probe_ablation.py --model "$N" --arms base --ds st_a     --n 2 --outdir "$R/smoke" --workers 2 >> "$L" 2>&1
$PY /root/19f_probe_ablation.py --model "$N" --arms base --ds visdrone --n 2 --outdir "$R/smoke" --workers 2 >> "$L" 2>&1
ok=$($PY /root/w1_smoke_count.py "$R/smoke/e1_${N}_st_a_base_native.csv" "$R/smoke/e1_${N}_visdrone_base_native.csv" 2>/dev/null | tail -1)
say "smoke：可解析 ${ok:-0} / 4 条"
if [ "${ok:-0}" -lt 1 ]; then say "!! 未过 smoke 门 ⇒ 最终排除"; gpu_clear; exit 1; fi

for ds in st_a ucf visdrone aitod; do
  $PY /root/19f_probe_ablation.py --model "$N" --arms base,permit,channel --ds "$ds" --n 150 --pool zero --outdir "$R/zero" --workers 8 >> "$L" 2>&1
  $PY /root/19f_probe_ablation.py --model "$N" --arms base --ds "$ds" --n 150 --pool zero --imgsz 640 --outdir "$R/zero" --workers 8 >> "$L" 2>&1
  $PY /root/19f_probe_ablation.py --model "$N" --arms base,permit,channel --ds "$ds" --n 150 --pool nonzero --outdir "$R/nonzero" --workers 8 >> "$L" 2>&1
  say "  $ds 完成"
done
$PY /root/w1_fsc_probe.py --model "$N" --arms base,permit,exemplar3,exemplar3permit --n 300 --workers 8 >> "$L" 2>&1
say "Molmo 完成：零池 $(ls $R/zero/e1_${N}_* | wc -l)/16，非零池 $(ls $R/nonzero/e1_${N}_* | wc -l)/12，FSC $(ls $R/fsc/fsc_${N}_* 2>/dev/null | wc -l)/4"
gpu_clear

say "重新打包（覆盖上一版 bundle）"
cd /root
tar --exclude='*.part' -czf /root/w1_bundle.tar.gz \
  w1_results logs/w1_*.log w1_prereg.json w1_prereg.md5 \
  w1_run.sh w1_recover.sh w1_recover2.sh w1_recover3.sh w1_recover4.sh w1_fsc_run.sh w1_fsc_late.sh \
  w1_guard.sh w1_hosted.sh w1_hosted_probe.py w1_fsc_probe.py w1_smoke_count.py w1_dl.sh w1_dl2.sh \
  w1_pack.sh 2>/dev/null
say "打包完成：$(du -h /root/w1_bundle.tar.gz | cut -f1)  $(md5sum /root/w1_bundle.tar.gz | cut -d' ' -f1)"
say "最终产物计数：zero=$(ls $R/zero | wc -l) nonzero=$(ls $R/nonzero | wc -l) fsc=$(ls $R/fsc 2>/dev/null | wc -l) hosted=$(ls $R/hosted 2>/dev/null | wc -l)"
echo "W1_RECOVER4_DONE" >> "$L"
