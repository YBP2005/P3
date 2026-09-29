
import json, sys, urllib.request
sys.stdout.reconfigure(encoding='utf-8')
def get(u):
    req = urllib.request.Request(u, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=40) as r:
        return json.loads(r.read().decode())
j = get('https://pypi.org/pypi/vllm/json')
ver = j['info']['version']
print('vLLM 最新版本:', ver)
reqs = j['info'].get('requires_dist') or []
pins = [r for r in reqs if r.lower().startswith(('torch', 'torchaudio', 'torchvision', 'xformers', 'transformers'))]
for p in pins:
    print('   ', p)
# 同时列出 0.11.x / 0.10.x 的 torch 依赖
print()
print('=== 各版本 torch 依赖 ===')
for v in ['0.11.0', '0.10.2', '0.10.0', '0.9.2']:
    try:
        k = get('https://pypi.org/pypi/vllm/%s/json' % v)
        rs = [r for r in (k['info'].get('requires_dist') or []) if r.lower().startswith('torch')]
        print('  vllm %-8s -> %s' % (v, rs[:2]))
    except Exception as ex:
        print('  vllm %-8s 查询失败 %s' % (v, str(ex)[:40]))
print()
print('=== 当前安装进度 ===')
import os
print(os.popen('tail -c 220 /root/logs/install.log | tr "\\r" "\\n" | tail -3').read())
print(os.popen('/root/vllm_env/bin/python -c "import torch;print(torch.__version__)" 2>&1 | tail -1').read())
