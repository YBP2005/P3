set -u
P=/usr/local/miniconda3/bin/python
for i in $(seq 1 90); do
  curl -sS -m 5 http://127.0.0.1:8013/v1/models 2>/dev/null | grep -q 'Qwen3-VL-32B-Instruct-AWQ' && break
  sleep 10
done
echo "READY after $((i*10))s"
T0=$(date +%s)
$P -u /root/p1d/p1d_probe.py --api http://127.0.0.1:8013/v1/chat/completions --model Qwen3-VL-32B-Instruct-AWQ \
   --items /root/p1d/data/sample_mtdc.csv --domain mtdc --budget 0 --start 0 \
   --imgdir /root/mtdc/images --out /root/p1d/res/SMOKE_mtdc_b0.csv --workers 4 --limit 20
T1=$(date +%s)
echo "SMOKE_SECONDS=$((T1-T0))"
awk -v d=$((T1-T0)) 'BEGIN{printf "items/min = %.1f\n", 20*60/d}'
grep -o 'Running: [0-9]* reqs, Waiting: [0-9]* reqs' /root/logs/p1d_serve_smoke.log | tail -3
echo SMOKE_DONE
