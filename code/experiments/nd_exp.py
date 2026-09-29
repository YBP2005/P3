#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""M 机本地 vLLM 的「非确定性来源分解」实验。

条件矩阵（每个条件都跑完全部 item，得到一个完整的预测集）：
  A. batch_size ∈ {1,2,4,8,16,32,64,120}  —— 批处理打包是否改变输出？
  B. temperature ∈ {0.0, 0.7}（后者固定 seed=0）—— 种子能否恢复可复现？
  C. enforce_eager ∈ {False, True}（由外部参数决定，脚本内记录）

输出：/root/nd_exp.jsonl 逐条落盘（item, cond, trial, pred, finish, ntok, secs）
      → 支持断点续跑
用法: python nd_exp.py <trials> [temp]
"""
import io, os, sys, re, json, time, base64
from PIL import Image

MODEL = os.environ.get('MODEL_DIR', '/root/models/Qwen3-VL-8B-Instruct-AWQ-4bit')
IMGDIR = os.environ.get('IMG_DIR', '/root/vdtest')
OUT = os.environ.get('ND_OUT', '/root/nd_exp.jsonl')
TRIALS = int(sys.argv[1]) if len(sys.argv) > 1 else 3
TEMPS = [float(x) for x in (sys.argv[2].split(',') if len(sys.argv) > 2 else ['0.0'])]
BS_LIST = [int(x) for x in os.environ.get('BS_LIST', '1,2,4,8,16,32,64,120').split(',')]
EAGER = os.environ.get('EAGER', '0') == '1'
MAXLEN = int(os.environ.get('MAXLEN', '32768') or 32768)
GPUTIL = float(os.environ.get('GPUTIL', '0.85') or 0.85)
TAG = os.environ.get('TAG', 'graph' if not EAGER else 'eager')

PR = ('请数出图片中的人数（人群中的每个人头或人体），不要遗漏，不要重复，'
      '以JSON格式输出：{"count": 数量}，只输出JSON。')
PAT = re.compile(r'\{\s*"?\s*(?:count|计数|数量|人数)\s*"?\s*[:：]\s*"?\s*(\d+)', re.I)

items = sorted(f[:-4] for f in os.listdir(IMGDIR) if f.lower().endswith('.jpg'))
print('item %d 项；trials=%d temps=%s bs=%s eager=%s tag=%s'
      % (len(items), TRIALS, TEMPS, BS_LIST, EAGER, TAG), flush=True)

# 预编码，保证所有条件输入逐字节一致
CACHE = {}
for it in items:
    with Image.open(os.path.join(IMGDIR, it + '.jpg')) as im:
        img = im.convert('RGB')
        b = io.BytesIO(); img.save(b, 'JPEG', quality=92)
        CACHE[it] = 'data:image/jpeg;base64,' + base64.b64encode(b.getvalue()).decode()
print('预编码完成（与托管 API 实验逐字节一致的 q92 JPEG）', flush=True)

# 续跑
done = set()
if os.path.exists(OUT):
    for line in io.open(OUT, encoding='utf-8'):
        line = line.strip()
        if line:
            try:
                o = json.loads(line)
                done.add((o['item'], o['cond'], o['trial']))
            except Exception:
                pass
    print('续跑：已有 %d 条' % len(done), flush=True)
fh = io.open(OUT, 'a', encoding='utf-8')

t_imp = time.time()
from vllm import LLM, SamplingParams
print('import vllm %.1fs' % (time.time() - t_imp), flush=True)

t0 = time.time()
llm = LLM(model=MODEL, dtype='bfloat16', max_model_len=MAXLEN,
          gpu_memory_utilization=GPUTIL, limit_mm_per_prompt={'image': 1},
          trust_remote_code=True, disable_log_stats=True, enforce_eager=EAGER)
print('模型加载完成 %.1fs' % (time.time() - t0), flush=True)


def msgs_for(it):
    return [{'role': 'user', 'content': [
        {'type': 'image_url', 'image_url': {'url': CACHE[it]}},
        {'type': 'text', 'text': PR}]}]


def run_batch(batch_items, temp):
    sp = SamplingParams(temperature=temp, max_tokens=256, top_p=1.0, top_k=-1,
                        repetition_penalty=1.0, seed=0)
    convs = [msgs_for(it) for it in batch_items]
    t1 = time.time()
    outs = llm.chat(convs, sp, use_tqdm=False)
    dt = time.time() - t1
    res = []
    for it, o in zip(batch_items, outs):
        o0 = o.outputs[0]
        m = PAT.search(o0.text.replace(',', ''))
        res.append(dict(item=it, pred=int(m.group(1)) if m else None,
                        finish=o0.finish_reason, ntok=len(o0.token_ids),
                        text=o0.text[:60]))
    return res, dt


total = 0
for temp in TEMPS:
    for bs in BS_LIST:
        for trial in range(TRIALS):
            cond = '%s_t%s_bs%d' % (TAG, temp, bs)
            need = [it for it in items if (it, cond, trial) not in done]
            if not need:
                continue
            for i in range(0, len(need), bs):
                chunk = need[i:i + bs]
                res, dt = run_batch(chunk, temp)
                for r in res:
                    r.update(cond='%s_t%s_bs%d' % (TAG, temp, bs), trial=trial, maxlen=MAXLEN, gputil=GPUTIL,
                             tag=TAG, bs=len(chunk), secs=round(dt / len(chunk), 4))
                    fh.write(json.dumps(r, ensure_ascii=False) + '\n')
                    total += 1
                fh.flush()
            print('  [%s trial%d] 完成 %d 项' % (cond, trial, len(need)), flush=True)

fh.close()
print('\n完成，本次写入 %d 条 → %s' % (total, OUT), flush=True)
print('总输出 token 分布将在分析脚本里统计', flush=True)
