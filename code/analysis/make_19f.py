# -*- coding: utf-8 -*-
"""从 19e_probe_multi.py **派生**出消融探针 19f_probe_ablation.py。

为什么派生而不是改：19e 是全流程（E2 与 A5 主实验）的**同一把尺子**，md5 已冻结在案，
任何修改都会让"同一仪器"这句失效。消融必须用**另一个**仪器，且该仪器要能追溯到 19e。

19f 相对 19e 只加三件事（其余逐字相同）：
  1. `--imgsz S`：把图像按比例缩放到最长边 = S（输入尺度消融；0 = 原生）
  2. `--system TEXT`：在对话最前面插一条 system 消息（模板消融；'' = 不加）
  3. `--outdir D`：输出目录（默认 /root/e1_results_ablate），文件名带变体后缀

每次替换都断言**恰好命中一次**；派生后对公共部分做逐行一致性校验。
"""
import hashlib
import io
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')
SRC = r'<WORKDIR>\PaperB\repro_github\code\experiments\19e_probe_multi.py'
DST = r'<WORKDIR>\PaperB\analysis\work\19f_probe_ablation.py'
EXPECT_MD5 = '03edb14c98ff'  # 19e 前 12 位（冻结值）

REPL = [
    # 1) 头部说明
    ('''"""19b_e1_probe.py — E1 强制非零探针（阿里云百炼兼容模式）。''',
     '''"""19f_probe_ablation.py — **消融探针**，由 19e_probe_multi.py 派生（见 make_19f.py）。

与 19e 的差别只有三处：--imgsz（输入尺度）、--system（模板）、--outdir（输出隔离）。
主实验（E2 / A5）一律使用 19e；本文件只用于 M.19 的消融小节。'''),
    # 2) 输出根目录
    ("OUTD = '/root/e1_results'\n",
     "OUTD = '/root/e1_results_ablate'\n"),
    # 3) call_img 支持 system 消息
    ("""def call_img(b64, prompt, model, timeout=180, retries=5):
    payload = {'model': model, 'messages': [{'role': 'user', 'content': [
        {'type': 'image_url', 'image_url': {'url': 'data:image/jpeg;base64,' + b64}},
        {'type': 'text', 'text': prompt}]}], 'temperature': 0.0, 'max_tokens': 128}""",
     """def call_img(b64, prompt, model, timeout=180, retries=5, system=''):
    msgs = []
    if system:
        msgs.append({'role': 'system', 'content': system})
    msgs.append({'role': 'user', 'content': [
        {'type': 'image_url', 'image_url': {'url': 'data:image/jpeg;base64,' + b64}},
        {'type': 'text', 'text': prompt}]})
    payload = {'model': model, 'messages': msgs, 'temperature': 0.0, 'max_tokens': 128}"""),
    # 4) 新增命令行参数
    ("""    ap.add_argument('--pool', default='zero', choices=('zero', 'nonzero'))
    A = ap.parse_args()""",
     """    ap.add_argument('--pool', default='zero', choices=('zero', 'nonzero'))
    ap.add_argument('--imgsz', type=int, default=0, help='最长边缩放到该值；0=原生')
    ap.add_argument('--system', default='', help='插入的 system 消息；空=不加')
    ap.add_argument('--outdir', default='/root/e1_results_ablate')
    A = ap.parse_args()"""),
    # 5) OUTD 覆盖（放在 pool 判断之后，消融结果一律进 outdir）
    ("""    if A.pool == 'nonzero':
        OUTD = '/root/e1_results_nonzero'
    os.makedirs(OUTD, exist_ok=True)""",
     """    if A.pool == 'nonzero':
        OUTD = '/root/e1_results_nonzero'
    OUTD = A.outdir
    os.makedirs(OUTD, exist_ok=True)
    variant = ('s%d' % A.imgsz) if A.imgsz else 'native'
    if A.system:
        variant += '_sys'"""),
    # 6) 输出文件名带变体后缀
    ("""        outp = os.path.join(OUTD, 'e1_%s_%s_%s.csv' % (tag, A.ds, arm))""",
     """        outp = os.path.join(OUTD, 'e1_%s_%s_%s_%s.csv' % (tag, A.ds, arm, variant))"""),
    # 7) 缩放 + system 传入
    ("""                try:
                    im = Image.open(p).convert('RGB')
                    raw = call_img(b64_of(im), P[arm], A.model)""",
     """                try:
                    im = Image.open(p).convert('RGB')
                    if A.imgsz:
                        im.thumbnail((A.imgsz, A.imgsz), Image.LANCZOS)
                    raw = call_img(b64_of(im), P[arm], A.model, system=A.system)"""),
]


def main():
    src = io.open(SRC, encoding='utf-8').read()
    md5 = hashlib.md5(src.encode('utf-8')).hexdigest()
    print('19e md5 = %s（冻结前缀 %s）%s' % (md5, EXPECT_MD5,
                                          'OK' if md5.startswith(EXPECT_MD5) else '★不一致'))
    if not md5.startswith(EXPECT_MD5):
        print('19e 已被改动 ⇒ 拒绝派生（同一仪器原则）')
        return 2
    out = src
    for i, (a, b) in enumerate(REPL, 1):
        n = out.count(a)
        if n != 1:
            print('替换 #%d 命中 %d 次（应为 1）⇒ 中止' % (i, n))
            return 3
        out = out.replace(a, b, 1)
        print('替换 #%d ok' % i)
    io.open(DST, 'w', encoding='utf-8', newline='\n').write(out)
    print('已写 %s（%d 字节，md5=%s）'
          % (DST, len(out.encode('utf-8')), hashlib.md5(out.encode('utf-8')).hexdigest()))
    # 公共部分校验：19f 去掉新增行后应与 19e 行集一致
    s19 = set(l for l in src.splitlines() if l.strip())
    s19f = set(l for l in out.splitlines() if l.strip())
    only19 = sorted(s19 - s19f)
    print('19e 有而 19f 没有的行：%d 条' % len(only19))
    for l in only19:
        print('   - %s' % l[:110])
    return 0


if __name__ == '__main__':
    sys.exit(main())
