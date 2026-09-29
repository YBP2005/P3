# -*- coding: utf-8 -*-
"""w0_frame3.py — W0 第四步（修正版）：本地候选的多模态判定 + 下载候选的文件构成。

修正：上一次用 os.path.join 在 Windows 上生成了反斜杠路径（`...\\config.json`），
      远端 grep 全部 No such file，导致"本地新家族 0 个"这个**错误结论**。
      远端路径一律手工拼 '/' —— 远端是 Linux，路径分隔符必须显式。
输出：w0_frame_final.json（local_new / downloads / file_lists）。
"""
import io
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from a800_conn import connect, sh  # noqa: E402

sys.stdout.reconfigure(encoding='utf-8')
HOST = ('<REDACTED-A800-HOST>', 23, 'root', '<REDACTED-A800-PASSWORD>')
HERE = os.path.dirname(os.path.abspath(__file__))
PY = '/usr/local/miniconda3/bin/python'

USED_PAT = (r'gemma-3-12b-it$|gemma3-12b|internvl3_5-8b|internvl3\.5-8b|phi-3\.5|llava-onevision|'
            r'llava-ov|qwen3-vl-32b|qwen3-vl-8b|qwen3-vl-4b|qwen3-vl-30b-a3b|qwen2\.5-vl-3b|'
            r'qwen2\.5-vl-7b')
# 无计数能力或非通用计数的候选（理由必须写明，写进 frame 表）
NOT_COUNTER = {'ATH-MaaS/OvisOCR2': '文档 OCR 专用模型，非通用场景计数（域外）',
               'LLM-Research/gemma-3-1b-pt': '预训练基座（pt），非 instruct，无法跟随计数指令',
               'openbmb/MiniCPM-2B-sft-bf16': '纯文本模型',
               'ZhipuAI/GLM-Image/vision_language_encoder': '仅是图像生成模型的视觉编码器组件'}

DOWNLOADS = [
    'HuggingFaceM4/Idefics3-8B-Llama3',
    'deepseek-ai/deepseek-vl2-tiny',
    'allenai/Molmo-7B-D-0924',
    'microsoft/Phi-4-multimodal-instruct',
    'OpenBMB/MiniCPM-V-4_5',
    'AIDC-AI/Ovis2-8B',
    'AIDC-AI/Ovis2-8B-Instruct',
]
SEARCH = ['Ovis2', 'MiniCPM-V-4', 'Step3-VL', 'Molmo', 'Idefics3']


def ms_files(c, mid):
    cmd = ('curl -sS -m 60 "https://www.modelscope.cn/api/v1/models/%s/repo/files?Revision=master'
           '&Recursive=true"' % mid)
    raw = sh(c, cmd, t=120)
    try:
        d = json.loads(raw)
    except Exception:
        return None, raw[:120]
    fs = [f for f in d.get('Data', {}).get('Files', []) if f.get('Type') != 'tree']
    return [(f.get('Path'), int(f.get('Size') or 0)) for f in fs], None


def main():
    c = connect(HOST)
    with io.open(os.path.join(HERE, 'w0_frame_candidates.json'), encoding='utf-8') as f:
        cands = json.load(f)

    print('=' * 104)
    print('① 本地候选：多模态判定（远端路径用 "/" 拼接）+ architectures + 是否已用过')
    print('=' * 104)
    rows = []
    for r in cands:
        d, mb = r['path'], r['size_mb']
        cfg = d + '/config.json'                    # ★ 必须 '/'，不能用 os.path.join
        mm = sh(c, 'grep -qiE "vision_config|image_token|visual|vision_tower|image_token_index|mm_tokens" '
                   '%s && echo MM || echo TEXT' % cfg, t=60).strip()
        arch = sh(c, '%s -c "import json,sys;print(str(json.load(open(sys.argv[1])).get(\'architectures\'))'
                     '[:70])" %s 2>/dev/null' % (PY, cfg), t=60).strip()
        used = bool(re.search(USED_PAT, d, re.I))
        rel = d.replace('/model/ModelScope/', '').replace('/root/models/', '')
        reason = NOT_COUNTER.get(rel, '')
        rows.append(dict(path=d, rel=rel, size_mb=mb, mm=mm, arch=arch, used=used, reason=reason))
        print('%s %-5s %8s MB  %-40s %s' % ('USED' if used else ('NEW ' if mm == 'MM' else 'skip'),
                                            mm, mb, arch, d))
    local_new = [r for r in rows if r['mm'] == 'MM' and not r['used'] and not r['reason']]
    print('\n★ 本地可用且**未用过**的家族：%d 个' % len(local_new))
    for r in local_new:
        print('    %8s MB  %-34s %s' % (r['size_mb'], r['arch'], r['rel']))
    print('\n（被排除的本地候选及理由）')
    for r in rows:
        if r['reason']:
            print('    %-52s %s' % (r['rel'], r['reason']))

    print('\n' + '=' * 104)
    print('② 下载候选：ModelScope 清单与实际构成（体积异常的要看清是什么文件）')
    print('=' * 104)
    dl = []
    for mid in DOWNLOADS:
        fs, err = ms_files(c, mid)
        if fs is None:
            print('  %-40s ✗ 取清单失败：%s' % (mid, err))
            continue
        if not fs:
            print('  %-40s ✗ 0 文件（该 id 在 ModelScope 上不存在或无公开文件）' % mid)
            continue
        total = sum(s for _, s in fs)
        big = sorted(fs, key=lambda x: -x[1])[:4]
        print('  %-40s %2d 文件 %6.2f GB' % (mid, len(fs), total / 1e9))
        for p, s in big:
            print('        %9.2f GB  %s' % (s / 1e9, p))
        dl.append(dict(model_id=mid, files=len(fs), gb=round(total / 1e9, 2),
                       biggest=[[p, s] for p, s in big]))

    print('\n' + '=' * 104)
    print('③ ModelScope 关键词搜索（找 Ovis2 等确切的 model id）')
    print('=' * 104)
    for kw in SEARCH:
        cmd = ('curl -sS -m 60 -X POST "https://www.modelscope.cn/api/v1/dolphin/models" '
               '-H "Content-Type: application/json" -d \'{"PageSize":12,"PageNumber":1,"Name":"%s"}\''
               % kw)
        raw = sh(c, cmd, t=120)
        try:
            d = json.loads(raw)
            ms = d.get('Data', {}).get('Model', {}).get('Models') or []
            ids = [m.get('Path', '') + '/' + m.get('Name', '') for m in ms][:12]
        except Exception:
            ids = ['<搜索接口不可用：%s>' % raw[:80]]
        print('  %-14s %s' % (kw, ' | '.join(ids)))
    c.close()

    with io.open(os.path.join(HERE, 'w0_frame_final.json'), 'w', encoding='utf-8', newline='\n') as f:
        json.dump(dict(local_all=rows, local_new=local_new, downloads=dl), f,
                  ensure_ascii=False, indent=2)
    print('\n写出 w0_frame_final.json')


if __name__ == '__main__':
    main()
