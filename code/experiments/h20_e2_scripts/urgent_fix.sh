#!/bin/bash
# 紧急修复：
#  ① 停掉重复的下载进程（两个实例在写同一批文件，已互相破坏）与 exp_extra2（它还没跑任何普查，停在下载步）
#  ② 装 g++（deepgemm JIT 需要 cc1plus，缺它则 FP8/GPTQ/AWQ-8bit 全崩）
#  ③ 清掉被破坏的 AWQ-8bit 目录
# 注意：**不要**动 dl_extra3.sh（它在等下载 72B，属正常排队）
echo "=== ① 停重复下载与 exp_extra2 ==="
for pat in h20_dl_extra2.sh h20_dl_model.py h20_exp_extra2.sh; do
  if pkill -9 -f "$pat" 2>/dev/null; then echo "  已停 $pat"; else echo "  （无 $pat）"; fi
done
sleep 5
echo "--- 残留检查（/proc 直读）---"
/usr/local/miniconda3/bin/python3 - <<'PY'
import os
TG = ['dl_model', 'dl_extra', 'exp_extra']
n = 0
for p in sorted(os.listdir('/proc')):
    if not p.isdigit():
        continue
    try:
        cl = open('/proc/%s/cmdline' % p, 'rb').read().replace(b'\x00', b' ').decode('utf-8', 'replace')
    except Exception:
        continue
    if any(t in cl for t in TG):
        print('  残留 pid=%s %s' % (p, cl.strip()[:100]))
        n += 1
print('  残留合计 %d' % n)
PY

echo
echo "=== ② 装 g++ ==="
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq 2>&1 | tail -3
apt-get install -y -qq g++ 2>&1 | tail -8
echo "--- 复验 ---"
for b in g++ c++ cc1plus; do printf "  %-8s: " "$b"; (command -v $b || echo "仍缺"); done
ls /usr/lib/gcc/x86_64-linux-gnu/*/cc1plus 2>/dev/null | sed 's/^/  找到 /' || echo "  未找到 cc1plus"

echo
echo "=== ③ 清被破坏的 AWQ-8bit ==="
if [ -d /root/models/Qwen3-VL-32B-Instruct-AWQ-8bit ]; then
  echo "  清理前: $(du -sh /root/models/Qwen3-VL-32B-Instruct-AWQ-8bit 2>/dev/null | cut -f1)"
  rm -rf /root/models/Qwen3-VL-32B-Instruct-AWQ-8bit
  echo "  已删除（待重新下载一次）"
fi
echo "  磁盘: $(df -h / | tail -1)"
echo URGENT_FIX_DONE
