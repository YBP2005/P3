#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""pod 端：依次起 4 个 VLM，各问同样两个问题（整幅 + 左端放大），汇总到 /root/vlm_answers.txt"""
import os, sys, json, time, subprocess, urllib.request, base64, signal

PY = '/root/vllm312/bin/python'
LOG = '/root/vlm_answers.txt'
MODELS = [
    ('internvl25-8b-awq', '/root/models/InternVL2_5-8B-AWQ', 0.60, None),
    ('qwen25vl-7b-awq', '/root/models/Qwen2.5-VL-7B-Instruct-AWQ', 0.60, 3136),
    ('qwen3-vl-8b-awq', '/root/models/Qwen3-VL-8B-Instruct-AWQ-4bit', 0.55, 200704),
    ('qwen3-vl-32b-awq', '/root/models/Qwen3-VL-32B-Instruct-AWQ-4bit', 0.92, 3136),
]
QS = [('整幅 panel(a)', '/root/p_f13_full.txt', ['/root/figs/F13a_panel.png']),
      ('左端放大', '/root/p_f13_zoomleft.txt', ['/root/figs/F13a_zoomleft.png'])]


def sh(c):
    return subprocess.run(c, shell=True, capture_output=True, text=True).stdout


def kill_vllm():
    sh("for p in $(ps -eo pid,cmd | grep '[v]llm serve' | awk '{print $1}'); do kill $p 2>/dev/null; done")
    time.sleep(7)


def serve(name, path, gm, minpx, timeout=1200):
    kill_vllm()
    vlog = f'/root/logs/vllm_{name}.log'
    mm = f" --mm-processor-kwargs '{{\"max_pixels\": 1048576, \"min_pixels\": {minpx}}}'" if minpx else ''
    cmd = (f"export PATH=/root/vllm312/bin:$PATH; nohup /root/vllm312/bin/vllm serve {path} "
           f"--served-model-name {name} --trust-remote-code --max-model-len 8192 "
           f"--limit-mm-per-prompt '{{\"image\": 1}}'{mm} "
           f"--gpu-memory-utilization {gm} --max-num-seqs 32 --port 8000 >> {vlog} 2>&1 &")
    subprocess.Popen(cmd, shell=True, preexec_fn=os.setsid,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            r = urllib.request.urlopen('http://127.0.0.1:8000/v1/models', timeout=6)
            if r.status == 200:
                j = json.load(r)
                return j['data'][0]['id'], time.time() - t0
        except Exception:
            pass
        time.sleep(10)
    return None, time.time() - t0


def ask(model, pf, imgs):
    prompt = open(pf, encoding='utf-8').read()
    content = [{"type": "text", "text": prompt}]
    for p in imgs:
        b = base64.b64encode(open(p, 'rb').read()).decode()
        content.append({"type": "image_url", "image_url": {"url": "data:image/png;base64," + b}})
    body = json.dumps({"model": model, "messages": [{"role": "user", "content": content}],
                       "max_tokens": 1200, "temperature": 0.0}).encode()
    req = urllib.request.Request('http://127.0.0.1:8000/v1/chat/completions', data=body,
                                 headers={'Content-Type': 'application/json'})
    try:
        r = json.load(urllib.request.urlopen(req, timeout=900))
        return r['choices'][0]['message']['content']
    except Exception as e:
        try:
            return 'ERROR ' + e.read().decode()[:500]
        except Exception:
            return f'ERROR {type(e).__name__} {e}'


with open(LOG, 'w', encoding='utf-8') as fh:
    fh.write('')
for name, path, gm, minpx in MODELS:
    with open(LOG, 'a', encoding='utf-8') as fh:
        fh.write('\n' + '=' * 100 + f'\n### MODEL {name}\n' + '=' * 100 + '\n')
    got, dt = serve(name, path, gm, minpx)
    with open(LOG, 'a', encoding='utf-8') as fh:
        fh.write(f'[serve] ready={got} in {dt:.0f}s\n')
    if not got:
        with open(LOG, 'a', encoding='utf-8') as fh:
            fh.write('  !! 启动失败\n' + sh(f'tail -20 /root/logs/vllm_{name}.log'))
        continue
    for lab, pf, imgs in QS:
        ans = ask(name, pf, imgs)
        with open(LOG, 'a', encoding='utf-8') as fh:
            fh.write(f'\n--- Q: {lab} ---\n{ans}\n')
    kill_vllm()
with open(LOG, 'a', encoding='utf-8') as fh:
    fh.write('\n\nALL DONE\n')
print('ALL DONE')
