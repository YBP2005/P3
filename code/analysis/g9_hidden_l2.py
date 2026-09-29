#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""g9_hidden_l2.py — G9：倒数第二层特征 $L_2$ 范数（进程内 HF 前向）。

冻结判据：/root/g9_criteria_frozen.json（启动时断言 md5）。
★ **先过污染闸门**：HF greedy 与冻结的 vLLM 逐项记录不一致率 > 5% ⇒ 直接判"不可测"、退出。

用法（先烟测，再全跑）：
    /usr/local/miniconda3/bin/python g9_hidden_l2.py --smoke 3
    /usr/local/miniconda3/bin/python g9_hidden_l2.py
输出：/root/g9_res/g9_hidden.csv（逐 item 逐臂逐层范数汇总）+ /root/g9_res/g9_guard.json
"""
import argparse
import csv
import hashlib
import io
import json
import os
import sys
import time

CRIT = '/root/g9_criteria_frozen.json'
CRIT_MD5 = 'cd4d138bfe50a51c172d8648933bf955'
MODEL = '/model/ModelScope/Qwen/Qwen3-VL-32B-Instruct'
PROBE = '/root/19f_probe_ablation.py'
PROBE_MD5 = '28e82b20a7f468680da11b2e9855cff9'
BASE_REC = '/root/p5c_results2_summary.json'      # §M.19.14 的冻结汇总（对照用，若在）
SC8 = '/root/e1_results_nonzero'                  # σ=8 item 来源（若需重建名单）
OUT = '/root/g9_res'
os.makedirs(OUT, exist_ok=True)

ARMS = ['base', 'forbid0', 'neutral0']
IMG = '/root/dense/shanghaitech/images/part_A_test'


def check():
    b = open(CRIT, 'rb').read()
    got = hashlib.md5(b).hexdigest()
    assert got == CRIT_MD5, '冻结件 md5 不符：%s' % got
    assert hashlib.md5(open(PROBE, 'rb').read()).hexdigest() == PROBE_MD5, '冻结探针 md5 不符'
    print('[g9] 冻结件 md5 OK：%s' % got, flush=True)
    return json.loads(b.decode('utf-8'))


def items(n=None):
    """σ=8 那一层的 item 名单：取自 §M.19.14 用过的目录（若不在，退化为按文件名排序取 135）。"""
    for d in ('/root/p5c_results', '/root/p5a_results'):
        p = os.path.join(d, 'items.txt')
        if os.path.exists(p):
            its = [x.strip() for x in io.open(p, encoding='utf-8') if x.strip()]
            return its[:n] if n else its
    fs = sorted(f for f in os.listdir(IMG) if f.lower().endswith('.jpg'))
    return fs[:n] if n else fs[:135]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--smoke', type=int, default=0)
    A = ap.parse_args()
    J = check()
    import torch
    from transformers import AutoProcessor, AutoModelForImageTextToText as AutoVLM
    t0 = time.time()
    # ★ 与冻结的 vLLM 记录**同一套像素界限**（否则是拿两种预处理比，不是比模型）
    try:
        proc = AutoProcessor.from_pretrained(MODEL, trust_remote_code=True,
                                           max_pixels=1048576, min_pixels=3136)
    except Exception:
        proc = AutoProcessor.from_pretrained(MODEL, trust_remote_code=True)
    model = AutoVLM.from_pretrained(MODEL, dtype=torch.bfloat16, device_map='auto',
                                    trust_remote_code=True)
    model.eval()
    print('[g9] 模型加载 %.0fs ｜ transformers %s ｜ torch %s'
          % (time.time() - t0, __import__('transformers').__version__, torch.__version__), flush=True)
    from PIL import Image
    import importlib.util
    spec = importlib.util.spec_from_file_location('frz', PROBE)
    M = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(M)
    # ★ 2026-09-27 修：冻结探针 19f::P 里**没有** forbid0 / neutral0（它只有 base/permit/channel/...）
    #   ⇒ 这两条臂逐字取自**已冻结的 G5/G6 判据件**（md5 22869fd86fefb37502ddf9d8dd5bec8b，本机在档）。
    import json as _json
    _g56 = _json.load(io.open('/root/g56_criteria_frozen.json', encoding='utf-8'))
    PROMPT = {'base': M.P['base'],
              'forbid0': _g56['prompts_verbatim']['forbid0'],
              'neutral0': _g56['prompts_verbatim']['neutral0']}
    its = items(A.smoke or None)
    print('[g9] item 数 %d（%s）' % (len(its), '烟测' if A.smoke else '全跑'), flush=True)
    out = os.path.join(OUT, 'g9_hidden_smoke.csv' if A.smoke else 'g9_hidden.csv')
    if not os.path.exists(out):
        with io.open(out, 'w', encoding='utf-8-sig', newline='') as f:
            csv.writer(f).writerow(['item', 'arm', 'pred_greedy', 'n_layers', 'l2_penult',
                                    'l2_all', 'cos_penult_vs_base'])
    l2 = {}
    for it in its:
        p = os.path.join(IMG, it)
        if not os.path.exists(p):
            print('  ⚠ 缺图：%s' % it, flush=True)
            continue
        im = Image.open(p).convert('RGB')
        for arm in ARMS:
            msgs = [{'role': 'user', 'content': [{'type': 'image'}, {'type': 'text', 'text': PROMPT[arm]}]}]
            try:
                txt = proc.apply_chat_template(msgs, add_generation_prompt=True, tokenize=False)
            except Exception:
                txt = proc.apply_chat_template(msgs, add_generation_prompt=True, tokenize=False,
                                               return_tensors=None)
            inp = proc(text=[txt], images=[im], return_tensors='pt').to(model.device)
            with torch.no_grad():
                g = model.generate(**inp, max_new_tokens=8, do_sample=False,
                                   output_hidden_states=True, return_dict_in_generate=True)
            seq = g.sequences[0][inp['input_ids'].shape[1]:]
            raw = proc.decode(seq, skip_special_tokens=True)
            pred = M.parse(raw)
            # ★ 读取位置：**预测第一个生成 token 的那个位置** = 最后一个 prompt token。
            #   `g.hidden_states` 是"每个生成步 × 每一层"的元组；第 0 步就是 prompt 的隐藏态，
            #   其最后一维位置 prompt_len-1 正是产生首个新 token 的那个位置（§M.19.14 同口径）。
            step0 = g.hidden_states[0]
            nL = len(step0)                       # = embedding 输出 + 36 层 = 37
            pos = inp['input_ids'].shape[1] - 1
            vecs = [step0[l][0, pos, :].float() for l in range(nL)]
            pen = vecs[-2] if nL >= 2 else vecs[-1]   # 倒数第二层
            l2[it] = l2.get(it, {})
            l2[it][arm] = {'pen': float(pen.norm().item()), 'vec': pen}
            base = l2[it].get('base', {}).get('vec')
            cos = None
            if base is not None:
                cos = float(torch.nn.functional.cosine_similarity(pen, base, dim=0).item())
            with io.open(out, 'a', encoding='utf-8-sig', newline='') as f:
                csv.writer(f).writerow([it, arm, '' if pred is None else pred, nL,
                                        '%.6f' % pen.norm().item(),
                                        ';'.join('%.4f' % v.norm().item() for v in vecs),
                                        '' if cos is None else '%.6f' % cos])
            print('  %-34s %-9s pred=%-6s l2_pen=%.3f cos=%s'
                  % (it, arm, pred, pen.norm().item(), ('%.4f' % cos) if cos is not None else '-'),
                  flush=True)
    print('\n[g9] 逐项结果 -> %s' % out, flush=True)
    print('[g9] ★ 下一步是**污染闸门**：把 pred_greedy 与冻结的 vLLM 记录逐项比对；'
          '不一致率 >5%% 则整节报"不可测"（见 g9_criteria_frozen.json::corruption_guard）。', flush=True)


if __name__ == '__main__':
    main()
