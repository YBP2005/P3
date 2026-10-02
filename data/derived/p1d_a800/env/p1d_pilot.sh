set -u
P=/usr/local/miniconda3/bin/python
cd /root/p1d
for w in 4 12; do
  O=/root/p1d/res/PILOT_w${w}.csv
  rm -f "$O"
  S=$(date +%s)
  $P -u p1d_probe.py --api http://127.0.0.1:8013/v1/chat/completions --model Qwen3-VL-32B-Instruct-AWQ \
     --items /root/p1d/data/sample_mtdc.csv --domain mtdc --budget 0 --start 0 \
     --imgdir /root/mtdc/images --out "$O" --workers $w --limit 200 >/dev/null 2>&1
  E=$(date +%s)
  N=$(($(wc -l < "$O") - 1))
  awk -v w=$w -v d=$((E-S)) -v n=$N 'BEGIN{printf "workers=%d 行=%d 秒=%d items/min=%.1f\n", w, n, d, n*60/d}'
  grep -o 'Running: [0-9]* reqs, Waiting: [0-9]* reqs' /root/logs/p1d_serve_smoke.log | tail -2
done
echo PILOT_DONE
