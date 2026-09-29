# -*- coding: utf-8 -*-
"""_p5c_env.py —— P5 Phase 2（hidden states，非 vLLM 路线）的**环境可行性**检查。"""
import importlib
import sys

sys.stdout.reconfigure(encoding='utf-8')
print('=== Python / CUDA ===')
print('  python', sys.version.split()[0])
try:
    import torch
    print('  torch', torch.__version__, '| cuda', torch.version.cuda,
          '| device_count', torch.cuda.device_count())
    for i in range(torch.cuda.device_count()):
        cap = torch.cuda.get_device_capability(i)
        free, total = torch.cuda.mem_get_info(i)
        print('    GPU%d %s cc=%s free=%.1f GB / %.1f GB'
              % (i, torch.cuda.get_device_name(i), cap, free / 2**30, total / 2**30))
except Exception as e:
    print('  torch 不可用：%s' % str(e)[:120])

print('=== 关键库 ===')
for name in ('transformers', 'accelerate', 'qwen_vl_utils', 'PIL', 'numpy'):
    try:
        m = importlib.import_module(name)
        print('  %-16s %s' % (name, getattr(m, '__version__', '(no __version__)')))
    except Exception as e:
        print('  %-16s !! %s' % (name, str(e)[:80]))

print('=== Qwen3-VL 是否被本机 transformers 认识 ===')
try:
    from transformers import AutoConfig
    for p in ('/model/ModelScope/Qwen/Qwen3-VL-8B-Instruct',
              '/model/ModelScope/Qwen/Qwen3-VL-32B-Instruct'):
        try:
            c = AutoConfig.from_pretrained(p, trust_remote_code=True)
            print('  %-46s arch=%s' % (p.split('/')[-1], getattr(c, 'architectures', '?')))
        except Exception as e:
            print('  %-46s !! %s' % (p.split('/')[-1], str(e)[:110]))
except Exception as e:
    print('  AutoConfig 不可用：%s' % str(e)[:120])
print('ENV_DONE')
