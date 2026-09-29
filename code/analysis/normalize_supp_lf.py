# -*- coding: utf-8 -*-
"""normalize_supp_lf.py — 把补充材料的行尾从 CRLF 归一为 LF（**纯空白改动，零内容变化**）。

为什么做：补充材料 4,419 行全是 CRLF，而主稿与其余送审源都是 LF ⇒ 拼出的评审包**行尾混杂**。
`_pin_pack.py` 用 `io.open(...).read()`（universal newlines，把 CRLF 折成 LF）算 md5 与字数，
而 `md5sum` 对**原始字节**算 ⇒ 两个 md5 永远对不上。新盲审形态里评审与协调都要核 md5，这坑会踩上。

本脚本的**安全保证**：
  1. 先备份 `<file>.bak_crlf_20260928`；
  2. 断言原文**没有孤立 CR**（只有 `\r\n`），否则拒绝改写；
  3. 改写后再读回，断言 `原文.replace(b'\r\n', b'\n') == 新文` 且 `新文` 里 `\r` 计数为 **0**；
  4. 打印两侧的 md5 / 字节数 / 字符数，便于留档。

用法：python normalize_supp_lf.py [--check]
"""
import hashlib
import io
import os
import shutil
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
P = r'<WORKDIR>\PaperB\PaperB_英文补充材料_PR_20260919.md'
BAK = P + '.bak_crlf_20260928'

raw = io.open(P, 'rb').read()
crlf, lf, cr = raw.count(b'\r\n'), raw.count(b'\n'), raw.count(b'\r')
print('原文：%d 字节   CRLF=%d  LF=%d  孤立CR=%d' % (len(raw), crlf, lf, cr - crlf))
print('原文 md5(原始字节)   =', hashlib.md5(raw).hexdigest())
print('原文 md5(CRLF->LF 后) =', hashlib.md5(raw.replace(b'\r\n', b'\n')).hexdigest())

if '--check' in sys.argv:
    ok = (cr - crlf == 0) and crlf == 0
    print('CHECK: %s（CRLF 应为 0）' % ('PASS' if ok else 'FAIL'))
    raise SystemExit(0 if ok else 1)

assert cr - crlf == 0, '存在孤立 CR，拒绝改写'
if crlf == 0:
    print('已经是纯 LF，无需改动。')
    raise SystemExit(0)

if not os.path.exists(BAK):
    shutil.copy2(P, BAK)
    print('已备份 ->', BAK)
else:
    print('备份已存在，保留原样 ->', BAK)

new = raw.replace(b'\r\n', b'\n')
io.open(P, 'wb').write(new)

back = io.open(P, 'rb').read()
assert back.count(b'\r') == 0, '改写后仍有 CR'
assert back == raw.replace(b'\r\n', b'\n'), '改写后不等于"仅折行尾"'
assert back.decode('utf-8').replace('\r\n', '\n') == raw.decode('utf-8').replace('\r\n', '\n'), \
    '内容层面不一致（不该发生）'
print('新文：%d 字节   CRLF=0' % len(back))
print('新文 md5(原始字节)   =', hashlib.md5(back).hexdigest())
print('新文 md5(CRLF->LF 后) =', hashlib.md5(back.replace(b'\r\n', b'\n')).hexdigest())
print('★ 两种算法现在应当相同 => %s' % ('是' if hashlib.md5(back).hexdigest()
                                        == hashlib.md5(back.replace(b'\r\n', b'\n')).hexdigest() else '否'))
print('内容等价性：仅行尾变化，逐字内容不变 ✓')
