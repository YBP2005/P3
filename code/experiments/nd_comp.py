#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""batch **组成** 实验：固定目标 item，只改变同批里的同伴与位置。
目的：把「批多大」与「同批里还有谁/在第几位」这两个因素分开 —— 上一个实验把两者混在了一起。

对每个目标 item，构造若干种同伴集（companion sets），每种重复 TRIALS 次，
看目标的预测是否随同伴变化；同时做「目标单独成批」作对照。
输出 /root/nd_comp.jsonl（逐条落盘，支持续跑）
"""
import io, os, sys, re, json, time, base64, random
from PIL import Image

MODEL = os.environ.get('MODEL_DIR', '/root/models/Qwen3-VL-8B-Instruct-AWQ-4bit')
IMGDIR = os.environ.get('IMG_DIR', '/root/vdtest')
OUT = '/root/nd_comp.jsonl'
TRIALS = int(sys.argv[1]) if len(sys.argv) > 1 else 10
N_TARGET = int(sys.argv[2]) if len(sys.argv) > 2 else 20
BS = int(sys.argv[3]) if len(sys.argv) > 3 else 8
EAGER = os.environ.get('EAGER', '0') == '1'

PR = ('请数出图片中的人数（人群中的每个人头或人体），不要遗漏，不要重复，'
      '以JSON格式输出：{"count": 数量}，只输出JSON。')
PAT = re.compile(r'\{\s*"?\s*(?:count|计数|数量|人数)\s*"?\s*[:：]\s*"?\s*(\d+)', re.I)

items = sorted(f[:-4] for f in os.listdir(IMGDIR) if f.lower().endswith('.jpg'))
random.seed(12345)
targets = random.sample(items, min(N_TARGET, len(items)))
print('总 item %d；目标 %d 个；每批 %d 张；trials=%d；eager=%s'
      % (len(items), len(targets), BS, TRIALS, EAGER), flush=True)

CACHE = {}
for it in items:
    with Image.open(os.path.join(IMGDIR, it + '.jpg')) as im:
        img = im.convert('RGB')
        b = io.BytesIO(); img.save(b, 'JPEG', quality=92)
        CACHE[it] = 'data:image/jpeg;base64,' + base64.b64encode(b.getvalue()).decode()
print('预编码完成', flush=True)

done = set()
if os.path.exists(OUT):
    for line in io.open(OUT, encoding='utf-8'):
        line = line.strip()
        if line:
            try:
                o = json.loads(line)
                done.add((o['target'], o['cond'], o['trial']))
            except Exception:
                pass
    print('续跑：已有 %d 条' % len(done), flush=True)
fh = io.open(OUT, 'a', encoding='utf-8')

from vllm import LLM, SamplingParams
t0 = time.time()
llm = LLM(model=MODEL, dtype='bfloat16', max_model_len=32768,
          gpu_memory_utilization=0.85, limit_mm_per_prompt={'image': 1},
          trust_remote_code=True, disable_log_stats=True, enforce_eager=EAGER)
print('模型加载完成 %.1fs' % (time.time() - t0), flush=True)


def msg(it):
    return [{'role': 'user', 'content': [
        {'type': 'image_url', 'image_url': {'url': CACHE[it]}},
        {'type': 'text', 'text': PR}]}]


sp = SamplingParams(temperature=0.0, max_tokens=256, top_p=1.0, top_k=-1,
                    repetition_penalty=1.0, seed=0)
total = 0
for tgt in targets:
    for trial in range(TRIALS):
        # 条件 cond 决定同伴集与目标位置；用 trial 派生，保证每种条件被多次重复
        others = [x for x in items if x != tgt]
        comp = random.sample(others, BS - 1)
        pos = trial % BS                       # 目标在批中的位置轮转
        batch = list(comp)
        batch.insert(pos, tgt)
        cond = 'bs%d_pos%d' % (BS, pos)
        if (tgt, cond, trial) in done:
            continue
        t1 = time.time()
        outs = llm.chat([msg(x) for x in batch], sp, use_tqdm=False)
        dt = time.time() - t1
        o = outs[batch.index(tgt)].outputs[0]
        m = PAT.search(o.text.replace(',', ''))
        fh.write(json.dumps(dict(target=tgt, cond=cond, trial=trial, pred=int(m.group(1)) if m else None,
                                 finish=o.finish_reason, companions=comp[:3], pos=pos, bs=BS,
                                 secs=round(dt, 3)), ensure_ascii=False) + '\n')
        fh.flush()
        total += 1
    print('  目标 %s 完成' % tgt, flush=True)

fh.close()
print('\n完成，本次写入 %d 条 → %s' % (total, OUT), flush=True)
