# -*- coding: utf-8 -*-
"""p5c_hidden.py —— **P5 Phase 2**：在残差流里定位"禁止 0"改变表示的位置与方向。

不走 vLLM（vLLM 不吐层激活），用 transformers 直跑两遍：
  ① 贪婪生成 ≤12 token（与 P5a 的 max_tokens 对齐）；
  ② 教师强制再前向一遍（prompt + 生成的回答），`output_hidden_states=True`，
     在**第一个数字 token 的前一个位置**读各层残差流与该位置的 logits。

不做任何图像缩放（与语料/P5a 的原生分辨率口径一致）。
判据来自 `p5c_criteria_frozen.json`（跑前冻结，md5 5f4683bb9cdf）；本件只产原始量，不判读。

用法：
  python -u p5c_hidden.py [--sigma 8] [--limit N] [--out /root/p5c_results.jsonl] [--device 0]
"""
import argparse
import csv
import io
import json
import os
import re
import sys
import time

sys.stdout.reconfigure(encoding='utf-8')
FROZEN = os.environ.get('P1_FROZEN', '/root/19e_probe_multi.py')
P1D = os.environ.get('P1D_PROBE', '/root/p1d_probe.py')
GRID = os.environ.get('P1_GRID', '/root/p1_grid')
MP_DEFAULT = '/model/ModelScope/Qwen/Qwen3-VL-8B-Instruct'
DIGIT = re.compile(r'\d')


def load_p1d():
    import hashlib
    import importlib.util
    got = hashlib.md5(io.open(FROZEN, 'rb').read()).hexdigest()
    if got != '03edb14c98ffa3aea9ffa20f59b00bc8':
        raise SystemExit('!! 冻结探针 md5 不符：%s' % got[:12])
    spec = importlib.util.spec_from_file_location('p1dmod', P1D)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    F, E = m.load_frozen()
    ppl = dict(F.P)
    ppl.update(E['arms'])
    out = {a: m.to_circles(ppl[a], a) for a in ('base', 'forbid0', 'neutral0')}
    print('  提示词（圆点版）就绪；尾串比对：%s'
          % all(out[a].partition('。')[2] == ppl[a].partition('。')[2] for a in out))
    return F, out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--model-path', default=MP_DEFAULT)
    ap.add_argument('--served-name', default='Qwen3-VL-8B-Instruct')
    ap.add_argument('--sigma', type=float, default=8.0)
    ap.add_argument('--limit', type=int, default=0)
    ap.add_argument('--max-new', type=int, default=12)
    ap.add_argument('--out', default='/root/p5c_results.jsonl')
    ap.add_argument('--device', default='0')
    A = ap.parse_args()

    import torch
    from PIL import Image
    from transformers import AutoProcessor, AutoModelForImageTextToText

    os.environ['CUDA_VISIBLE_DEVICES'] = A.device
    F, PROMPTS = load_p1d()

    print('  载入模型 %s（bf16，device %s）' % (A.model_path, A.device))
    t0 = time.time()
    proc = AutoProcessor.from_pretrained(A.model_path)
    model = AutoModelForImageTextToText.from_pretrained(
        A.model_path, dtype=torch.bfloat16, device_map={'': 0})
    model.eval()
    print('  载入完成 %.1f s' % (time.time() - t0))
    tok = proc.tokenizer
    tid0 = tok.encode('0', add_special_tokens=False)
    tid0 = tid0[-1] if tid0 else None
    u0 = model.get_output_embeddings().weight[tid0].detach().float().cpu()
    print('  token "0" id=%s ｜ u0 范数 %.3f' % (tid0, float(u0.norm())))

    rows = [r for r in csv.DictReader(io.open(os.path.join(GRID, 'manifest.csv'), encoding='utf-8'))
            if abs(float(r['sigma']) - A.sigma) < 1e-9]
    if A.limit:
        rows = rows[:A.limit]
    print('  σ=%g 层：%d 项 ｜ 臂 %s' % (A.sigma, len(rows), list(PROMPTS)))

    fh = io.open(A.out, 'a', encoding='utf-8', newline='\n')
    done = set()
    if os.path.exists(A.out):
        for line in io.open(A.out, encoding='utf-8'):
            try:
                done.add(json.loads(line)['item'])
            except Exception:
                pass
    todo = [r for r in rows if r['item'] not in done]
    print('  已完成 %d / 本次 %d' % (len(done), len(todo)))

    n = 0
    t1 = time.time()
    # ★ 冻结判据 H_P2b/c/d 要的是 **均值向量** 的余弦（`cos(mean Δh, u0)`），
    #   而逐项余弦的均值 ≠ 均值向量的余弦。所以必须在这里累加 Δh 向量本身。
    #   只在 base 答 0 的物品上累加（判据原文：on base-zero items）。
    acc = {'n0': 0, 'f': None, 'neu': None, 'p0': {'base': [], 'forbid0': [], 'neutral0': []},
           'cos_f': None, 'cos_neu': None, 'cnt_cos': 0}
    for r in todo:
        im = Image.open(os.path.join(GRID, r['path'])).convert('RGB')
        per_arm = {}
        for arm, prompt in PROMPTS.items():
            msgs = [{'role': 'user', 'content': [{'type': 'image'}, {'type': 'text', 'text': prompt}]}]
            text = proc.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True)
            inp = proc(text=[text], images=[im], return_tensors='pt').to('cuda')
            with torch.no_grad():
                gen = model.generate(**inp, max_new_tokens=A.max_new, do_sample=False,
                                     output_hidden_states=True, output_scores=True,
                                     return_dict_in_generate=True)
            plen = int(inp['input_ids'].shape[1])
            gids = gen.sequences[0][plen:]
            resp = tok.decode(gids, skip_special_tokens=True)
            ans = F.parse(resp)
            # 找第一个含数字的生成 token
            j = None
            for k, gid in enumerate(gids.tolist()):
                if DIGIT.search(tok.decode([gid], skip_special_tokens=True) or ''):
                    j = k
                    break
            if j is None:
                per_arm[arm] = dict(answer=ans, resp=resp, p0=None, has_digit=False)
                continue
            # ★ 一遍搞定：`generate` 在 `output_hidden_states=True` 下按**生成步**返回各层激活，
            #   `scores` 返回每一步的 logits。**不要**自己拼接再前向一遍 —— 那样 `mm_token_type_ids`
            #   仍是提示词长度，会在 `get_rope_index` 里炸（实测：mask [1079] vs tensor [1070]）。
            if j is None:
                per_arm[arm] = dict(answer=ans, resp=resp, p0=None, has_digit=False)
                continue
            step_hs = gen.hidden_states[j]                 # tuple(层) of [1, seq_j, H]
            hs = [h[0, -1, :].detach().float().cpu() for h in step_hs]
            lg = gen.scores[j][0].detach().float()         # [V]
            p0 = float(torch.softmax(lg, dim=-1)[tid0])
            per_arm[arm] = dict(answer=ans, resp=resp, p0=p0, has_digit=True,
                                n_layer=len(hs), _h=hs,
                                _digit=tok.decode([gids[j]], skip_special_tokens=True))
        # 计算与 base 的逐层余弦 / Δh 在 u0 上的投影
        rec = dict(item=r['item'], n=int(r['n']), r=int(r['r']), sigma=float(r['sigma']),
                   gt=int(r['gt']), arms={})
        hb = per_arm.get('base', {}).get('_h')
        for arm, d in per_arm.items():
            e = dict(answer=d.get('answer'), resp=d.get('resp'), p0=d.get('p0'),
                     has_digit=d.get('has_digit'), digit=d.get('_digit'),
                     n_layer=(len(d['_h']) if d.get('_h') is not None else 0))
            if hb is not None and d.get('_h') is not None and len(d['_h']) == len(hb):
                cos, cosdh = [], []
                for L in range(len(hb)):
                    a, b = hb[L], d['_h'][L]
                    cos.append(float(torch.nn.functional.cosine_similarity(a, b, dim=0)))
                    dh = (b - a).float()
                    nd = float(dh.norm())
                    cosdh.append(float(torch.dot(dh, u0) / nd) if nd > 1e-9 else 0.0)
                e['cos_vs_base'] = cos
                e['cos_dh_u0'] = cosdh
            rec['arms'][arm] = e
        for arm, d in per_arm.items():
            if d.get('p0') is not None:
                acc['p0'][arm].append(d['p0'])
        # 累加 Δh（仅 base 答 0 的物品）与其逐层余弦
        hb2 = per_arm.get('base', {}).get('_h')
        hf = per_arm.get('forbid0', {}).get('_h')
        hn = per_arm.get('neutral0', {}).get('_h')
        if (hb2 and hf and hn and len(hb2) == len(hf) == len(hn)
                and per_arm['base'].get('answer') == 0):
            if acc['f'] is None:
                acc['f'] = [torch.zeros_like(hb2[L]) for L in range(len(hb2))]
                acc['neu'] = [torch.zeros_like(hb2[L]) for L in range(len(hb2))]
                acc['cos_f'] = [0.0] * len(hb2)
                acc['cos_neu'] = [0.0] * len(hb2)
            for L in range(len(hb2)):
                acc['f'][L] += (hf[L] - hb2[L])
                acc['neu'][L] += (hn[L] - hb2[L])
                acc['cos_f'][L] += float(torch.nn.functional.cosine_similarity(hb2[L], hf[L], dim=0))
                acc['cos_neu'][L] += float(torch.nn.functional.cosine_similarity(hb2[L], hn[L], dim=0))
            acc['n0'] += 1
        fh.write(json.dumps(rec, ensure_ascii=False) + '\n')
        fh.flush()
        n += 1
        if n % 10 == 0:
            print('    %d/%d  %.2f it/s' % (n, len(todo), n / max(time.time() - t1, 1e-9)), flush=True)
    fh.close()
    # ── 汇总（判据真正需要的量）───────────────────────────────────────────────
    if acc['n0'] > 0 and acc['f'] is not None:
        k = acc['n0']
        mean_dh_f = [acc['f'][L] / k for L in range(len(acc['f']))]
        mean_dh_n = [acc['neu'][L] / k for L in range(len(acc['neu']))]
        cos_mean_f = [float(torch.dot(v, u0) / v.norm()) if float(v.norm()) > 1e-9 else 0.0
                      for v in mean_dh_f]
        cos_mean_n = [float(torch.dot(v, u0) / v.norm()) if float(v.norm()) > 1e-9 else 0.0
                      for v in mean_dh_n]
        cos_item_f = [c / k for c in acc['cos_f']]
        cos_item_n = [c / k for c in acc['cos_neu']]

        def first_below(v, thr):
            for i, x in enumerate(v):
                if x < thr:
                    return i
            return None
        summary = dict(_summary=True, n_base_zero=k, n_layer=len(mean_dh_f),
                       p0_mean={a: (sum(v) / len(v) if v else None) for a, v in acc['p0'].items()},
                       p0_n={a: len(v) for a, v in acc['p0'].items()},
                       cos_item_mean_forbid0=cos_item_f, cos_item_mean_neutral0=cos_item_n,
                       cos_mean_dh_u0_forbid0=cos_mean_f, cos_mean_dh_u0_neutral0=cos_mean_n,
                       Lstar_forbid0=first_below(cos_item_f, 0.99),
                       Lstar_neutral0=first_below(cos_item_n, 0.99),
                       sd_u0=float(u0.norm()))
        with io.open(A.out.replace('.jsonl', '_summary.json'), 'w', encoding='utf-8', newline='\n') as sf:
            sf.write(json.dumps(summary, ensure_ascii=False, indent=1) + '\n')
        print('  汇总：n_base_zero=%d ｜ L*(forbid0)=%s ｜ L*(neutral0)=%s ｜ '
              'cos(meanΔh,u0) 末层 f=%+.4f n=%+.4f'
              % (k, summary['Lstar_forbid0'], summary['Lstar_neutral0'],
                 cos_mean_f[-1], cos_mean_n[-1]))
    else:
        print('  ！没有可用的 base-zero 物品，未写汇总')
    print('  DONE：%d 项 → %s' % (n, A.out))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
