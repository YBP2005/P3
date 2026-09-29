#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""M 机 vLLM 冒烟：加载 Qwen3-VL-8B-AWQ，用与 API 实验**逐字相同**的提示词，
原生分辨率 + JPEG q92 编码，跑 3 张 VisDrone 图。确认本地栈可用且输出可比。
"""
import io, os, sys, time, re, base64
from PIL import Image

MODEL = os.environ.get('MODEL_DIR', '/root/models/Qwen3-VL-8B-Instruct-AWQ-4bit')
IMGDIR = os.environ.get('IMG_DIR', '/root/vdtest')
PR = ('请数出图片中的人数（人群中的每个人头或人体），不要遗漏，不要重复，'
      '以JSON格式输出：{"count": 数量}，只输出JSON。')
PAT = re.compile(r'\{\s*"?\s*(?:count|计数|数量|人数)\s*"?\s*[:：]\s*"?\s*(\d+)', re.I)

print('importing vllm ...', flush=True)
t0 = time.time()
from vllm import LLM, SamplingParams
print('imported %.1fs' % (time.time() - t0), flush=True)

t0 = time.time()
llm = LLM(model=MODEL, dtype='bfloat16', max_model_len=32768,
          gpu_memory_utilization=0.85, limit_mm_per_prompt={'image': 1},
          trust_remote_code=True, disable_log_stats=True)
print('模型加载完成 %.1fs' % (time.time() - t0), flush=True)

sp = SamplingParams(temperature=0.0, max_tokens=2048, top_p=1.0, top_k=-1,
                    repetition_penalty=1.0, seed=0)

files = sorted(f for f in os.listdir(IMGDIR) if f.lower().endswith('.jpg'))[:3]
print('测试图: %s' % files, flush=True)

for f in files:
    with Image.open(os.path.join(IMGDIR, f)) as im:
        img = im.convert('RGB')
        b = io.BytesIO(); img.save(b, 'JPEG', quality=92)
    # 用 image_url + base64 data URL：与 API 实验逐字节相同的 q92 JPEG
    data_url = 'data:image/jpeg;base64,' + base64.b64encode(b.getvalue()).decode()
    msgs = [{'role': 'user', 'content': [
        {'type': 'image_url', 'image_url': {'url': data_url}},
        {'type': 'text', 'text': PR}]}]
    t1 = time.time()
    try:
        out = llm.chat(msgs, sp, use_tqdm=False)
        o = out[0].outputs[0]
        m = PAT.search(o.text.replace(',', ''))
        print('  %-34s %.1fs finish=%s tok=%d pred=%s  content=%r'
              % (f, time.time() - t1, o.finish_reason, len(o.token_ids),
                 int(m.group(1)) if m else None, o.text[:70]), flush=True)
    except Exception as ex:
        print('  %-34s 失败 %s: %s' % (f, type(ex).__name__, str(ex)[:300]), flush=True)

print('冒烟结束：%.0fs' % (time.time() - t0), flush=True)
