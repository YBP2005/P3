# -*- coding: utf-8 -*-
"""w0_frame.py — W0 第二步：从只读镜像与 /root/models 里**只挑 VLM 候选**并给出体积。

为什么单独一个脚本：/model/ModelScope 是 40 TB 公共镜像，逐层列举会产出几万条无关目录
（图像/视频/语音模型），既慢又会把真正要看的候选淹掉。这里按**模型名关键词**过滤，
再对候选逐个取体积。输出 w0_frame_candidates.json（供本地按冻结规则抽样）。
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

# VLM 候选关键词（模型目录名，小写匹配）
KW = (r'vl|vision|visual|llava|internvl|phi-3|phi-4|gemma-3|gemma-4|paligemma|ovis|minicpm|'
      r'molmo|idefics|smolvlm|glm-4.*v|deepseek-vl|qwen2-vl|qwen2\.5-vl|qwen3-vl|llama-3\.2|'
      r'pixtral|mplug|emu|vila|bunny|cogvlm|kosmos|florence|blip|chameleon|aria|fuyu|'
      r'granite.*vision|nemotron.*vl|hunyuan.*vl|ernie.*vl|step.*vl|moondream|mantis|'
      r'cambrian|pangea|spatialvlm|video-llava|longva|vlm')
SKIP = re.compile(r'(\._____temp|/unet|/vae|/text_encoder|/tokenizer$|/audio|/svd|gguf|fp8|'
                  r'embedding|reranker|asr|tts|whisper|diffusion|flux|image-gen|video-gen)', re.I)


def main():
    c = connect(HOST)
    print('枚举含 config.json 的模型目录（关键词过滤后取体积）…')
    cmd = (
        'for root in /model/ModelScope /root/models; do [ -d "$root" ] || continue; '
        '  find "$root" -maxdepth 4 -name config.json -printf "%h\\n" 2>/dev/null; done'
    )
    dirs = [x.strip() for x in sh(c, cmd, t=600).splitlines() if x.strip()]
    print('  全部含 config.json 的目录：%d 个' % len(dirs))
    cand = [d for d in dirs if re.search(KW, d, re.I) and not SKIP.search(d)]
    print('  关键词筛出 VLM 候选：%d 个' % len(cand))
    rows = []
    for d in cand:
        r = sh(c, 'du -sm %s 2>/dev/null | cut -f1' % json.dumps(d), t=90).strip()
        try:
            mb = int(r)
        except Exception:
            mb = None
        # 是否是"多模态"（config.json 里有 vision 相关字段）
        v = sh(c, '/usr/local/miniconda3/bin/python - <<\'EOF\'\n'
                 'import json,sys\ntry:\n'
                 '    j=json.load(open(%s))\n'
                 '    ks=" ".join(j.keys()).lower()\n'
                 '    arch=str(j.get("architectures",""))\n'
                 '    print("MM" if any(k in ks for k in ("vision","image","visual")) else "??", arch[:80])\n'
                 'except Exception as e:\n    print("ERR", e)\n'
                 'EOF' % json.dumps(os.path.join(d, 'config.json')), t=90).strip()
        rows.append(dict(path=d, size_mb=mb, probe=v))
        print('  %8s MB  %-22s %s' % (mb, v[:22], d))
    c.close()
    with io.open(os.path.join(HERE, 'w0_frame_candidates.json'), 'w', encoding='utf-8', newline='\n') as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)
    print('\n写出 w0_frame_candidates.json（%d 行）' % len(rows))


if __name__ == '__main__':
    main()
