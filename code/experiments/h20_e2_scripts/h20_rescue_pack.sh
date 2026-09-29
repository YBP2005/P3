#!/bin/bash
# H20 抢救打包：只打**不可再下载**的东西（结果、日志、脚本、池定义、GT/计数、语料）
# 明确排除：/root/models、/root/incoming（模型 tar）、/root/vllm312（venv）、
#           数据集图片目录、__pycache__、各类缓存
set -u
OUT=/root/rescue_h20_20260922.tar.gz
LST=/root/rescue_list.txt
cd /root

: > "$LST"
# ① 结果与日志
for d in e1_results e1_results_nonzero logs dense_results corpus_new probes; do
  [ -d "$d" ] && find "$d" -type f ! -path '*__pycache__*' >> "$LST"
done
# ② 脚本 / 探针 / 补丁 / 运行日志（顶层）
find . -maxdepth 1 -type f \( -name '*.sh' -o -name '*.py' -o -name '*.log' -o -name '*.txt' \) >> "$LST"
# ③ GT 与计数（不含图片）
find aerial -maxdepth 1 -type f -name '*.csv' >> "$LST"
find dense -maxdepth 1 -type f -name '*.csv' >> "$LST"
find ext -maxdepth 3 -type f -name '*.csv' >> "$LST"

sort -u "$LST" -o "$LST"
echo "清单文件数：$(wc -l < $LST)"
tar czf "$OUT" -T "$LST"
echo "打包完成：$(du -h $OUT | cut -f1)"
echo "tar 内条目：$(tar tzf $OUT | wc -l)"
echo "md5：$(md5sum $OUT | cut -d' ' -f1)"
echo "字节：$(stat -c %s $OUT)"
echo "== 清单前 12 项 =="
head -12 "$LST"
echo "== 按目录统计 =="
awk -F/ '{print $1"/"$2}' "$LST" | sort | uniq -c | sort -rn | head -12
echo "H20_RESCUE_TAR_OK"
