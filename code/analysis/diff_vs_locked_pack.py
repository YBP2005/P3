# -*- coding: utf-8 -*-
"""diff_vs_locked_pack.py —— 「锁定件 vs 工作稿」精确改动清单（不靠回忆）。

用法：
    python diff_vs_locked_pack.py <锁定包.md> <当前主稿.md>
    python diff_vs_locked_pack.py <锁定包.md> <当前主稿.md> --para "锚点短语"

为什么要有它：本项目多条纪律都要求「被在册条目/被引用的那一件」与「工作稿」的关系必须可核。
把权威副本从**锁定包里取出来**（而不是去翻备份或凭记忆列改动），再做字符级 diff，
可以得到该改动的**逐项 W 尺省/费**，从而核对"净变化"这类声明。

W 尺 = en_check.py 口径：re.findall(r"[A-Za-z][A-Za-z'\\-]*", s)
"""
import io, re, sys, difflib, hashlib

PKG = re.compile(r'以下为 06_英文稿_EN\.md ===== -->(.*?)<!-- ===== ', re.S)
W = lambda s: len(re.findall(r"[A-Za-z][A-Za-z'\-]*", s))


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    pack_p, cur_p = sys.argv[1], sys.argv[2]
    para_key = None
    if '--para' in sys.argv:
        para_key = sys.argv[sys.argv.index('--para') + 1]

    pack = io.open(pack_p, encoding='utf-8').read()
    cur = io.open(cur_p, encoding='utf-8').read()
    m = PKG.search(pack)
    assert m, '未在包内定位到 06_英文稿_EN.md 段：' + pack_p
    old = m.group(1).strip('\n')

    print('锁定包 %s' % pack_p)
    print('  包内主稿副本 md5 %s  chars=%d' % (
        hashlib.md5(old.encode('utf-8')).hexdigest(), len(old)))
    print('当前主稿     %s' % cur_p)
    print('  当前主稿       md5 %s  chars=%d' % (
        hashlib.md5(cur.encode('utf-8')).hexdigest(), len(cur)))

    if old == cur:
        print('\n两者**逐字相同**：自该锁定件起主稿无任何改动。')
        return 0

    print('\n=== 字符级改动（W 尺为该项的省(−)/费(+)）===')
    net = 0
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, old, cur).get_opcodes():
        if tag == 'equal':
            continue
        a, b = old[i1:i2], cur[j1:j2]
        net += W(b) - W(a)
        print('%-8s W %+d' % (tag, W(b) - W(a)))
        print('   旧: %s' % a.replace('\n', ' ⏎ ')[:400])
        print('   新: %s' % b.replace('\n', ' ⏎ ')[:400])
    print('\n全文 W 尺：%d -> %d  (%+d)' % (W(old), W(cur), W(cur) - W(old)))
    print('    字符数：%d -> %d  (%+d)' % (len(old), len(cur), len(cur) - len(old)))

    if para_key:
        def para(text):
            i = text.index(para_key)
            a = text.rindex('\n\n', 0, i) + 2
            b = text.index('\n\n', i)
            return text[a:b]
        po, pc = para(old), para(cur)
        print('\n段落「%s…」W 尺：%d -> %d  (%+d)' % (
            para_key[:24], W(po), W(pc), W(pc) - W(po)))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
