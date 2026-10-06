#!/bin/bash
exec env SRV=/root/a52_ext_serve_fp8.sh PORT=8015 SERVED=Qwen3-VL-32B-Instruct-FP8 TAG=b1 load_s=1 \
  bash /root/a52_ext_smoke_driver.sh
