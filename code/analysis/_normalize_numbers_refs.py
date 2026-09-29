# -*- coding: utf-8 -*-
"""_normalize_numbers_refs.py —— 把正文里 `*(Numbers: X.Y.)*` 内部指针改写成论文体交叉引用。

## 为什么要改（v0539 八模型盲审，grok46 提为**阻塞项**）
正文有 21 处 `*(Numbers: M.11.)*` 这类斜体尾巴，出现在 §1／§2.9／§3.5／§5.x 等。它**确实是**
指向补充材料附录的交叉引用（M.8/M.9/M.11/M.14/M.16/M.17/L.1 都是 "Numeric detail moved from …" 节），
但**形式像工作日志**（"Numbers:" 是中文稿里那张数字跟踪表的说法）。grok46 的判断是：
"未达可直接外审体裁"，建议删掉；dsflash/dspro 也各自点到 §1 的同一样式。

## 为什么不删
删掉会**丢指针**（这 21 处正是"数字在附录哪一节"的入口）。改写成
`(Appendix X.Y)` 后：
- **词数不变**：`*(Numbers: M.11.)*` 与 `(Appendix M.11)` 在 `en_check` 的 W 尺下都是 **2 个词**
  （Numbers/M ↔ Appendix/M），故 35 页上限**零成本**；
- **门禁反而变强**：`en_check` 的 N1（附录交叉引用可解析）用
  `Appendix\\s+([A-M](?:\\.\\d+)*)` 抓引用，原来这种写法**匹配不上**（`M.11.` 后面是 `.` 不是 `)`），
  改写后这 21 处**全部进入** N1 的校验范围，任何一个指错都会当场失败。

用法：
    python -u _normalize_numbers_refs.py            # 干跑，只打印将改什么
    python -u _normalize_numbers_refs.py --apply    # 落盘

★ 2026-09-24 二次执行时扩到**补充材料**：同样的样式在附录里也有 7 处
（`*(Numbers: F.8.)*` 等）。虽然 grok46 只点了正文，但这是**同一类内部痕迹**，
两处不一致反而更刺眼；改写同样 0 词，故一并做掉。
"""
import io, os, re, sys

sys.stdout.reconfigure(encoding='utf-8')
EN = r'<WORKDIR>\PaperB\PaperB_英文稿_PR_20260919.md'
SUP = r'<WORKDIR>\PaperB\PaperB_英文补充材料_PR_20260919.md'
PAT = re.compile(r'\*\(Numbers:\s*([A-M]\.\d+)\.\)\*')
W = lambda s: len(re.findall(r"[A-Za-z][A-Za-z'\-]*", s))


def do_file(path, supheads, apply):
    print('=' * 90)
    print(path)
    t = io.open(path, encoding='utf-8', newline='').read()
    hits = PAT.findall(t)
    if not hits:
        print('  无命中（已规范化或样式不同）')
        return 0
    print('  命中 %d 处；按目标分节：%s' % (len(hits), ', '.join(
        '%s×%d' % (k, hits.count(k)) for k in sorted(set(hits)))))
    dead = sorted(set(hits) - supheads)
    print('  目标在补充材料中是否存在标题：%s' % ('全部存在 ✓' if not dead else '★ 缺失 %s' % dead))
    if dead:
        print('  !! 有死引用，拒绝改写（先修标题或改目标）。')
        return 1
    new = PAT.sub(lambda m: '(Appendix %s)' % m.group(1), t)
    print('  W 尺词数：%d → %d（%+d）   字符：%d → %d（%+d）'
          % (W(t), W(new), W(new) - W(t), len(t), len(new), len(new) - len(t)))
    if PAT.findall(new):
        print('  !! 改写后仍有残留，拒绝。')
        return 1
    if apply:
        io.open(path, 'w', encoding='utf-8', newline='').write(new)
        print('  已写盘 ✓')
    return 0


def main():
    apply = '--apply' in sys.argv
    sup = io.open(SUP, encoding='utf-8', newline='').read()
    supheads = set(re.findall(r'^#{2,4}\s+(?:Appendix\s+)?([A-M](?:\.\d+)*)[\.\s]', sup, re.M))
    rc = do_file(EN, supheads, apply)
    rc |= do_file(SUP, supheads, apply)
    if not apply:
        print('\n（干跑，未写盘。加 --apply 落盘。）')
    return rc


if __name__ == '__main__':
    raise SystemExit(main())

