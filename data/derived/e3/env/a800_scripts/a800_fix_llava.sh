#!/bin/bash
# A5：修复 vLLM 0.29 + transformers 5.x 下 llava_onevision 无法导入的问题。
# 根因：vLLM 的 pixtral.py 从 transformers 导入两个符号
#   - PixtralRotaryEmbedding   （transformers 5 改名为 PixtralVisionRotaryEmbedding，签名一致）
#   - position_ids_in_meshgrid （transformers 5 已移除）
# 这两个符号只被 vLLM 的 **Pixtral** 模型路径使用；LLaVA-OneVision 只是经由
#   llava_onevision -> llava -> pixtral 的**模块级 import** 被牵连。
# 做法：从 transformers 4.x 官方 wheel 里取出**原始实现**做兼容模块，再把 vLLM 的
#   import 改成 try/except 回退。备份为 .orig，可完整回滚。
set -u
S=/usr/local/miniconda3/lib/python3.13/site-packages
V=$S/vllm/model_executor/models/pixtral.py
LOG=/root/llava_fix.log
exec >> $LOG 2>&1
echo "=== $(date +%H:%M:%S) 修复开始 ==="

# 0) 备份（只做一次）
if [ ! -f $V.orig ]; then
  cp -p $V $V.orig
  echo "备份 -> $V.orig  md5=$(md5sum $V.orig | cut -d' ' -f1)"
fi

# 1) 取 transformers 4.x 官方 wheel，抽出原始实现
mkdir -p /root/tf4src
TF_VER=""
for v in 4.57.1 4.56.2 4.55.4 4.53.3; do
  if /usr/local/miniconda3/bin/pip download --no-deps -q -d /root/tf4src "transformers==$v" >/dev/null 2>&1; then
    TF_VER=$v; break
  fi
done
echo "transformers 源版本：${TF_VER:-未取到}"
if [ -z "$TF_VER" ]; then echo "TF4_FIX_FAIL 无法下载 4.x wheel"; exit 3; fi

cd /root/tf4src
W=$(ls transformers-$TF_VER*.whl 2>/dev/null | head -1)
[ -z "$W" ] && { echo "TF4_FIX_FAIL 没有 wheel"; exit 3; }
/usr/local/miniconda3/bin/python - <<PY
import zipfile, re, io
w = "$W"
z = zipfile.ZipFile(w)
name = [n for n in z.namelist() if n.endswith('models/pixtral/modeling_pixtral.py')][0]
src = z.read(name).decode('utf-8')
def grab(fn):
    m = re.search(r'^def %s\(.*?(?=^\S)' % fn, src, re.S | re.M)
    assert m, fn
    return m.group(0).rstrip() + '\n'
parts = [grab('position_ids_in_meshgrid')]
hdr = ('# -*- coding: utf-8 -*-\n'
       '# A5 兼容垫片：从 transformers %s 的 models/pixtral/modeling_pixtral.py\n'
       '# 取出的**原始实现**，仅用于补上 transformers 5.x 移除的符号。\n'
       'import torch\n\n') % "$TF_VER"
open('/root/a5_pixtral_compat.py', 'w').write(hdr + '\n'.join(parts))
print('垫片已写：/root/a5_pixtral_compat.py')
PY
md5sum /root/a5_pixtral_compat.py

# 2) 给 vLLM 的 import 加回退
/usr/local/miniconda3/bin/python - <<'PY'
p = "/usr/local/miniconda3/lib/python3.13/site-packages/vllm/model_executor/models/pixtral.py"
s = open(p, encoding='utf-8').read()
old = """from transformers.models.pixtral.modeling_pixtral import (
    PixtralRotaryEmbedding,
    apply_rotary_pos_emb,
    position_ids_in_meshgrid,
)"""
new = """try:  # A5 兼容：transformers 4.x 符号名
    from transformers.models.pixtral.modeling_pixtral import (
        PixtralRotaryEmbedding,
        apply_rotary_pos_emb,
        position_ids_in_meshgrid,
    )
except ImportError:  # transformers>=5：前者改名、后者移除
    from transformers.models.pixtral.modeling_pixtral import (
        PixtralVisionRotaryEmbedding as PixtralRotaryEmbedding,
        apply_rotary_pos_emb,
    )
    import sys as _sys
    _sys.path.insert(0, '/root')  # 垫片位置
    from a5_pixtral_compat import position_ids_in_meshgrid"""
if new in s:
    print('补丁已在位，跳过')
elif old in s:
    open(p, 'w', encoding='utf-8').write(s.replace(old, new, 1))
    print('补丁已应用')
else:
    raise SystemExit('PATCH_FAIL 未找到原始 import 块')
PY

# 3) 验证
/usr/local/miniconda3/bin/python -c "import vllm.model_executor.models.llava_onevision as m; print('LLAVA_IMPORT_OK', m.LlavaOnevisionForConditionalGeneration.__name__)" \
  && echo "LLAVA_FIX_OK" || echo "LLAVA_FIX_FAIL"
echo "=== $(date +%H:%M:%S) 修复结束 ==="
