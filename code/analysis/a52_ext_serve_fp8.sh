#!/bin/bash
# A5-2 ext b1 = official Qwen/Qwen3-VL-32B-Instruct-FP8, single card, port 8015.
# A800 = SM80 -> vLLM's CompressedTensorsW8A8Fp8 needs >=8.9, so this falls back to
# CompressedTensorsW8A16Fp8 (weights FP8, activations BF16). --quantization fp8
# is required explicitly (awq_marlin/gptq report "does not match").
export PATH=/usr/local/miniconda3/bin:$PATH
export VLLM_USE_FLASHINFER_SAMPLER=0
exec /usr/local/miniconda3/bin/python -m vllm.entrypoints.openai.api_server \
  --model /root/models/Qwen3-VL-32B-Instruct-FP8 \
  --served-model-name Qwen3-VL-32B-Instruct-FP8 \
  --port 8015 --trust-remote-code --max-model-len 8192 \
  --quantization fp8 \
  --gpu-memory-utilization ${GMEM_UTIL:-0.90} \
  --limit-mm-per-prompt '{"image": 1}' \
  --mm-processor-kwargs '{"max_pixels":1048576,"min_pixels":3136}' \
  --max-num-seqs 24
