# -*- coding: utf-8 -*-
"""pin_diff.py —— 两枚**锁定评审包**的分件差异清单。

用途：逐轮如实声明「被评审的那一件」与「当前件」到底差在哪。原则是**不靠回忆**：
把两枚 pin 按包内小节标记切成部件，逐件比 md5，并对差异件给出字符级 opcode 摘要。

用法：
    python pin_diff.py <旧pin.md> <新pin.md>
"""
import io, re, sys, hashlib, difflib

MARKS = [
    ('材料自述', re.compile(r'<!-- ===== 材料自述.*?-->(.*?)(?=<!-- =====)', re.S)),
    ('评审提示词', re.compile(r'<!-- ===== 以下为 02_评审提示词\.txt ===== -->(.*?)(?=<!-- =====)', re.S)),
    ('问句集', re.compile(r'<!-- ===== 以下为 02d_问句集_PR版\.txt ===== -->(.*?)(?=<!-- =====)', re.S)),
    ('主稿', re.compile(r'<!-- ===== 以下为 06_英文稿_EN\.md ===== -->(.*?)(?=<!-- =====)', re.S)),
    ('补充材料', re.compile(r'<!-- ===== 以下为 08_英文补充材料_Supplementary\.md ===== -->(.*)$', re.S)),
]
W = lambda s: len(re.findall(r"[A-Za-z][A-Za-z'\-]*", s))


def parts(path):
    t = io.open(path, encoding='utf-8').read()
    out = {'__whole__': t}
    for name, rx in MARKS:
        m = rx.search(t)
        out[name] = m.group(1).strip('\n') if m else None
    return out


def main():
    if len(sys.argv) < 3:
        print(__doc__); return 2
    a_p, b_p = sys.argv[1], sys.argv[2]
    A, B = parts(a_p), parts(b_p)
    print('旧 %s\n    整体 md5 %s  chars=%d' % (a_p, hashlib.md5(A['__whole__'].encode()).hexdigest(), len(A['__whole__'])))
    print('新 %s\n    整体 md5 %s  chars=%d' % (b_p, hashlib.md5(B['__whole__'].encode()).hexdigest(), len(B['__whole__'])))
    print('\n%-10s %-14s %-14s %s' % ('部件', '旧 md5', '新 md5', '判定'))
    bad = []
    for name, _ in [('材料自述', 0)] + [(n, 0) for n, _ in MARKS[1:]]:
        x, y = A.get(name), B.get(name)
        if x is None or y is None:
            print('%-10s %-14s %-14s %s' % (name, '—', '—', '缺失')) ; bad.append(name); continue
        hx, hy = hashlib.md5(x.encode()).hexdigest()[:12], hashlib.md5(y.encode()).hexdigest()[:12]
        same = x == y
        print('%-10s %-14s %-14s %s' % (name, hx, hy, '相同' if same else '**不同**'))
        if not same:
            bad.append(name)
            print('           W 尺：%d -> %d (%+d)   字符：%d -> %d (%+d)' % (
                W(x), W(y), W(y) - W(x), len(x), len(y), len(y) - len(x)))
            for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, x, y).get_opcodes():
                if tag == 'equal':
                    continue
                print('           %-8s W %+d | 旧: %s' % (
                    tag, W(y[j1:j2]) - W(x[i1:i2]), x[i1:i2].replace('\n', ' ⏎ ')[:110]))
                print('           %-8s       | 新: %s' % ('', y[j1:j2].replace('\n', ' ⏎ ')[:110]))
    print('\n差异部件：%s' % (('、'.join(bad) if bad else '无（两枚逐字相同）')))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
