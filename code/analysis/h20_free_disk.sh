#!/bin/bash
# H20 清盘（2026-09-22）：只删**可再下载 / 可重建**的大件；
# 抢救下来的结果、日志、脚本、池定义、GT、抢救包一律保留。
set -u
echo "== 清理前 =="
df -h / | tail -1

echo
echo "== 逐项删除（每项打印释放量）=="
free_one() {
  local p="$1" note="$2"
  if [ -e "$p" ]; then
    local before after
    before=$(df --output=avail -k / | tail -1)
    rm -rf "$p"
    after=$(df --output=avail -k / | tail -1)
    echo "  已删 $(printf '%-40s' "$p") ($note)  释放 $(( (after - before) / 1024 )) MB"
  else
    echo "  跳过 $(printf '%-40s' "$p") (不存在)"
  fi
}

# ① 模型权重（公开可再下载）
free_one /root/models                    "11 个公开检查点，约 252 G"
free_one /root/incoming                  "models_awq32.tar，20 G"
# ② 虚拟环境（可重建）
free_one /root/vllm312                   "vllm venv，8.3 G"
# ③ 数据集（A800 上已有逐字节副本；GT/计数/池定义已抢救到本地）
free_one /root/dense                     "ShanghaiTech+UCF 图（计数已抢救）"
free_one /root/aerial                    "VisDrone/AI-TOD 图（GT 已抢救）"
free_one /root/ext/countbench/images     "CountBench 图（counts.csv 已抢救）"
# ④ 缓存与编译产物
free_one /root/__pycache__               "python 缓存"
free_one /root/.triton                   "triton 缓存"
free_one /root/.tilelang                 "tilelang 缓存"
free_one /root/.cache                    "各类缓存"
free_one /root/.npm                      "npm 缓存"
free_one /root/.humming                  "humming 缓存"
free_one /root/.nv                       "nvidia 缓存"

echo
echo "== 清理后 =="
df -h / | tail -1

echo
echo "== 保留物核对（抢救内容必须都在）=="
for p in /root/e1_results /root/e1_results_nonzero /root/logs /root/dense_results \
         /root/corpus_new /root/probes /root/ext/countbench/counts.csv \
         /root/rescue_h20_20260922.tar.gz /root/19e_probe_multi.py; do
  if [ -e "$p" ]; then echo "  ✓ $p"; else echo "  ✗ 缺 $p"; fi
done
echo "  顶层脚本数：$(ls /root/*.sh /root/*.py 2>/dev/null | wc -l)"
echo "  结果 CSV：$(ls /root/e1_results/*.csv 2>/dev/null | wc -l) 零池 + $(ls /root/e1_results_nonzero/*.csv 2>/dev/null | wc -l) 非零池"
echo "  抢救包：$(stat -c %s /root/rescue_h20_20260922.tar.gz 2>/dev/null) 字节"
echo "H20_FREE_DISK_DONE"
