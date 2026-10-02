#!/bin/bash
# P3R4 §3B —— **B1（InternVL3.5-38B-BF16）TP=2 起服脚本**，端口 8021
# ★★ 本件是 **条件性未来项 1（两卡张量并行 TP=2）** 的落地件。
# ★ 只用指定的两张卡（由调用方用 CUDA_VISIBLE_DEVICES 控制）；**GPU0 上的外部任务任何情况下不碰**。
# ★ 纯起服；不跑推理；不碰别人的进程。
#
# ══════════════════════════════════════════════════════════════════════════════
# 【TP=2 显存几何（自算，不照抄单卡的 0.97）】
#   单卡实测锚点：权重 **71.77 GiB**（`Model loading took 71.77 GiB memory`），KV = **256 KiB/token**
#   TP=2 后逐卡分摊（张量并行按**层内**切分，权重与 KV 都约减半）：
#     · 权重/卡      ≈ 71.77 / 2            ≈ **35.9 GiB**
#     · KV/卡        = 每卡 4 个 KV 头 ⇒ 128 KiB/token
#                      ⇒ 4 路 × 8192 tokens = 4 × 8192 × 128 KiB ≈ **4.0 GiB/卡**
#     · 非 KV 开销/卡（激活峰值 + CUDAGraph + 编码器缓存 + 框架）
#                      ≈ 3.7 GiB（单卡实测反推值）**× 2**（TP 下两卡各留一份全量激活/图缓存）
#                      ≈ **7.4 GiB/卡**（取保守上界）
#     · NCCL all-reduce 缓冲/通信 ≈ 1–2 GiB/卡（保守取 2）
#     ⇒ 每卡需求 ≈ 35.9 + 4.0 + 7.4 + 2.0 ≈ **49.3 GiB**
#   80 GiB 卡 ⇒ 所需 utilization ≈ 49.3 / 80 ≈ **0.62**
#   ★ 取 **0.60**（留 ~2 GiB 余量；因 KV 只是"能放下 4 路"的最低要求，余量大些更稳）
#     80 × 0.60 = **48.0 GiB/卡** 预算。
#   ★ 与单卡的对照：单卡 0.97 ⇒ 77.6 GiB 预算仍只给 **1.16×** 并发；
#     TP=2 下 KV/卡 只需 4.0 GiB（而非 8.0）且权重减半 ⇒ **4 路 8192 变得宽裕**。
#   ★ 这是**显存切分参数**，不改变模型算什么 ⇒ 仍需以"Max concurrency ≥ 4"实测坐实。
# ══════════════════════════════════════════════════════════════════════════════
#
# 【前置清单（上级 2026-09-30 登记，逐条落实）】
#   ✅ 1. `VLLM_USE_FLASHINFER_SAMPLER=0` —— **可比性必需**：本机全局基线（50+ house 脚本，
#         `ea_lang_run.sh` 第 7 行全局 export），**既有 InternVL 面板件都在它下面产生**。
#   ✅ 2. `--tensor-parallel-size 2`
#   ✅ 3. **不传** `--mm-processor-kwargs` —— InternVL 架构不支持（实测 TypeError: max_pixels）
#   ✅ 4. `--max-model-len 8192` / `--limit-mm-per-prompt '{"image":1}'` / `--max-num-seqs 24` 保持冻结值
#   ✅ 5. `--trust-remote-code`
#   ✅ 6. `--gpu-memory-utilization` 按 TP=2 几何重算 = **0.60**（见上）
#
# 【验收闸门（上级要求，不得省）】起服后必须确认日志里
#   `Maximum concurrency for 8,192 tokens per request ≥ 4`；**<4 就停手回报**。
export PATH=/usr/local/miniconda3/bin:$PATH
export VLLM_USE_FLASHINFER_SAMPLER=0
echo "ninja -> $(which ninja) $(ninja --version 2>&1 | head -1)"
echo "g++   -> $(which g++ || echo MISSING)"
echo "cmake -> $(which cmake || echo MISSING)"
echo "CUDA_VISIBLE_DEVICES=$CUDA_VISIBLE_DEVICES  (TP=2)"
echo "VLLM_USE_FLASHINFER_SAMPLER=$VLLM_USE_FLASHINFER_SAMPLER"
PY=/usr/local/miniconda3/bin/python
exec $PY -m vllm.entrypoints.openai.api_server \
  --model /root/models/InternVL3_5-38B-BF16 \
  --served-model-name InternVL3_5-38B-BF16 \
  --port 8021 --trust-remote-code --max-model-len 8192 \
  --tensor-parallel-size 2 \
  --gpu-memory-utilization ${GMEM_UTIL:-0.60} \
  --limit-mm-per-prompt '{"image": 1}' \
  --max-num-seqs 24
