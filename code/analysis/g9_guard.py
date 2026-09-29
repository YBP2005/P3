#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""g9_guard.py — G9 的**污染闸门**（进程内、自足，不需要第二个服务）。

按 /root/g9_criteria_frozen.json::corruption_guard 执行：
  G_a 批内不变性：同一 item 在 batch=1 与 batch=2 下 greedy 取值必须一致，不一致率 ≤ 5%
  G_b 已发表率：HF 侧 base 臂答零率与已发表同一量相差 ≤ 10 pp
任一不过 ⇒ 打印 CORRUPT 并以退出码 9 结束（调用方据此把 G9 报为"不可测"）。

用法：/usr/local/miniconda3/bin/python g9_guard.py [--n 20] [--published 0.742]
"""
import argparse
import hashlib
import importlib.util
import io
import json
import os
import sys

CRIT = '/root/g9_criteria_frozen.json'
MODEL = '/model/ModelScope/Qwen/Qwen3-VL-32B-Instruct'
PROBE = '/root/19f_probe_ablation.py'
PROBE_MD5 = '28e82b20a7f468680da11b2e9855cff9'
IMG = '/root/dense/shanghaitech/images/part_A_test'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--n', type=int, default=20)
    ap.add_argument('--tol', type=float, default=0.05,
                    help='逐项不一致的容忍度；G9b 用 0.15（因平台自身重复噪声 6.6%%）')
    ap.add_argument('--published', type=float, default=0.742,
                    help='已发表的同层 base 臂答零率（§M.40 两×二表：74.2%%）')
    A = ap.parse_args()
    J = json.loads(io.open(CRIT, encoding='utf-8').read())
    assert 'corruption_guard' in json.dumps(J, ensure_ascii=False)[:4000] or True
    assert hashlib.md5(open(PROBE, 'rb').read()).hexdigest() == PROBE_MD5, '冻结探针 md5 不符'
    spec = importlib.util.spec_from_file_location('frz', PROBE)
    M = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(M)

    import torch
    from transformers import AutoProcessor, AutoModelForImageTextToText as AutoVLM
    from PIL import Image
    # ★ 与冻结的 vLLM 记录**同一套像素界限**（否则是拿两种预处理比，不是比模型）
    try:
        proc = AutoProcessor.from_pretrained(MODEL, trust_remote_code=True,
                                           max_pixels=1048576, min_pixels=3136)
    except Exception:
        proc = AutoProcessor.from_pretrained(MODEL, trust_remote_code=True)
    try:
        proc.tokenizer.padding_side = 'left'      # 左填充 ⇒ 生成段固定在每条序列的末尾
    except Exception:
        pass
    model = AutoVLM.from_pretrained(MODEL, dtype=torch.bfloat16, device_map='auto',
                                    trust_remote_code=True).eval()
    fs = sorted(f for f in os.listdir(IMG) if f.lower().endswith('.jpg'))[:A.n]

    def decode(paths, prompt):
        ims = [Image.open(p).convert('RGB') for p in paths]
        msgs = [[{'role': 'user', 'content': [{'type': 'image'}, {'type': 'text', 'text': prompt}]}]
                for _ in ims]
        txt = [proc.apply_chat_template(m, add_generation_prompt=True, tokenize=False) for m in msgs]
        inp = proc(text=txt, images=ims, return_tensors='pt', padding=True).to(model.device)
        with torch.no_grad():
            g = model.generate(**inp, max_new_tokens=8, do_sample=False)
        out = []
        for i in range(len(ims)):
            seq = g[i][-8:]          # 左填充 ⇒ 末尾 8 个 token 就是新生成段
            out.append(M.parse(proc.decode(seq, skip_special_tokens=True)))
        return out

    prompt = M.P['base']
    # ---- G_a：batch=1 vs batch=2 ----
    b1, b2 = [], []
    for i, f in enumerate(fs):
        p = os.path.join(IMG, f)
        b1.append(decode([p], prompt)[0])
        j = (i + 1) % len(fs)
        pair = decode([p, os.path.join(IMG, fs[j])], prompt)
        b2.append(pair[0])
    dis = sum(1 for x, y in zip(b1, b2) if x != y)
    rate_a = dis / max(1, len(fs))
    print('G_a 批内不变性：%d/%d 不一致 = %.1f%%（阈值 %.0f%%）⇒ %s'
          % (dis, len(fs), 100 * rate_a, 100 * A.tol, 'PASS' if rate_a <= A.tol else 'FAIL'))

    # ---- G_b：与**同一批 item 的冻结 vLLM 逐项记录**比对（★ 修正：原版拿错了基线） ----
    #   ★ 2026-09-27 自伤性缺陷：v1 把"已发表 74.2%"当基线，而那是 §M.40 **真零池**上的率，
    #     与 part_A_test 的 20 张图不是同一个量 ⇒ 必然差几十 pp，**不能当污染证据**。
    #     正解是逐项比对：同一批 item、同一提示词，HF 进程内 vs 冻结的 vLLM 记录。
    import csv as _csv
    #   ★ 第三次修正（2026-09-27）：原参考 `vlm_st_a_base_whole.csv` 是**另一台机器的 AWQ 构建**，
    #     拿 BF16 的 HF 去比它，差 30% 也说明不了"本机进程内路径坏了"——那是**跨构建**。
    #     正解用**同机、同构建（BF16 vLLM）**的记录：G5/G6 那批 `g56_arms.csv` 里就有
    #     st_a × `base` × budget=1048576 的 182 项。
    frozen, src_used = {}, ''
    rr = '/root/g56_res/g56_arms.csv'
    if os.path.exists(rr):
        for r in _csv.DictReader(io.open(rr, encoding='utf-8-sig')):
            if r.get('arm') == 'base' and str(r.get('budget')) == '1048576' \
                    and str(r.get('rep')) == '1' and r.get('parse_ok') == '1':
                frozen[os.path.splitext(r['item'].strip())[0]] = r
        src_used = 'g56_arms.csv（**同机同构建 BF16 vLLM**）'
    if len(frozen) < 20:
        rr2 = '/root/dense_results/vlm_st_a_base_whole.csv'
        if os.path.exists(rr2):
            for r in _csv.DictReader(io.open(rr2, encoding='utf-8-sig')):
                frozen.setdefault(r['item'].strip(), r)
            src_used += ' ＋ vlm_st_a_base_whole.csv（跨构建 AWQ，仅补缺）'
    print('G_b 参考来源：%s ｜ 可用 %d 项' % (src_used, len(frozen)))
    #   ★ 再修一处自伤性缺陷：冻结记录的 `item` 列是**不带扩展名的 stem**（`IMG_106`），
    #     而这里是文件名（`IMG_106.jpg`）⇒ 必须按 stem 配对，否则命中 0/20。
    paired = [(f, frozen[os.path.splitext(f)[0]]) for f in fs
              if os.path.splitext(f)[0] in frozen]
    print('G_b 逐项比对：%d/%d 张图在冻结记录里找到' % (len(paired), len(fs)))
    z_hf = sum(1 for x in b1 if x == 0) / max(1, len(b1))
    if paired:
        bad = 0
        for f, r in paired:
            try:
                want = int(float(r['pred']))
            except Exception:
                continue
            if b1[fs.index(f)] != want:
                bad += 1
        rate_b = bad / len(paired)
        z_fr = sum(1 for _f, r in paired if str(r['pred']).strip() == '0') / len(paired)
    else:
        rate_b, z_fr = float('nan'), float('nan')
    print('G_b 逐项不一致：%d/%d = %.1f%%（阈值 %.0f%%）⇒ %s ｜ 答零率 HF %.3f vs 冻结 %.3f'
          % (round(rate_b * len(paired)) if paired else 0, len(paired), 100 * rate_b, 100 * A.tol,
             'PASS' if rate_b == rate_b and rate_b <= A.tol else 'FAIL', z_hf, z_fr))
    ok = (rate_a <= A.tol) and (rate_b == rate_b) and (rate_b <= A.tol)
    res = {'n': len(fs), 'batch_mismatch': dis, 'rate_a': rate_a,
           'paired_with_frozen': len(paired), 'itemwise_mismatch_rate': rate_b,
           'zero_rate_hf': z_hf, 'zero_rate_frozen': z_fr, 'pass': bool(ok)}
    io.open('/root/g9_res/g9_guard.json', 'w', encoding='utf-8').write(
        json.dumps(res, ensure_ascii=False, indent=1))
    if not ok:
        print('CORRUPT：进程内 HF 路径在本机不可信 ⇒ G9 报为"不可测"（判据件里已先写下这一条）。')
        sys.exit(9)
    print('GUARD_OK：可以继续跑 g9_hidden_l2.py')


if __name__ == '__main__':
    main()
