#!/bin/bash
export PATH=/usr/local/miniconda3/bin:$PATH
export VLLM_USE_FLASHINFER_SAMPLER=0
exec /usr/local/miniconda3/bin/python -m vllm.entrypoints.openai.api_server \
  --model /root/models/_dryrun_rtn_4b \
  --served-model-name Qwen3-VL-4B-RTN-Int4 \
  --port 8014 --trust-remote-code --max-model-len 8192 \
  --quantization compressed-tensors \
  --gpu-memory-utilization 0.85 \
  --limit-mm-per-prompt '{"image": 1}' \
  --mm-processor-kwargs '{"max_pixels":1048576,"min_pixels":3136}' \
  --max-num-seqs 24
