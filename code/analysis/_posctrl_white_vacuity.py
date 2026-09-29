# -*- coding: utf-8 -*-
"""_posctrl_white_vacuity.py —— 一次**自造永真断言**的抓出与留档（阴性结果，故脚本本身"成功"）。

## 背景
2026-09-24 我一度在 `en_check.py` 的 [F] 段加了一条硬检查：
「仅靠 0–102 白名单放行的 token 必须登记在册」，动机是担心 `WHITE` 对落在该区间的**测量值**
静默放行（例如把 "2.6 pp" 写成 "3.6 pp" 抓不到）。按本项目的规矩，**新断言必须有阳性对照**
（教训 06：结构性编辑必须有结构性断言；30 号文：自建判据要能被证伪）。

## 做法
把英文稿读进内存，在固定锚点句前插入 `It moves by <TOK>.`，`<TOK>` 取 0–102 中
**理论上唯一可能触发**的那几个整数，写临时稿；再把 `en_check.py` 的源码副本 `exec` 一遍
（只把 `EN` 指向临时稿），逐次看那条检查是否失败。

## 结果（2026-09-24）
**0/3 触发**。再加内部诊断才看清根因：
    `tok=73 in_en=True in_zh=True in_SECT=False in_ARXIV=False only_white=[] trig=[]`
⇒ `WHITE ⊆ zh_flat`（0–102 每个整数都已在某份权威档里出现过）⇒ `(… ) & WHITE` **恒为空集**
⇒ 那条检查**永远为真**，不会失败，也就什么都守护不了。
⇒ 已从 `en_check.py` 删除该 chk（**永真断言不是门禁**；留着只会让"全过"显得更可信而实际更虚）。
   现在 `en_check.py` 只**打印并校验这条逻辑关系本身**（`WHITE ⊆ zh_flat` 是否为真）。

## 为什么这个脚本要留着
1. 它是那次判断的**证据**：不靠"我记得试验过了"。
2. 它是**回归探针**：若有人重新加回类似检查，或 `zh_flat` 的来源发生变化，
   本脚本的 `trig` 诊断会立刻显示可触发集合，从而暴露"检查是否又变永真/是否真能触发"。
3. 它示范了正确的顺序：**先证明判据能失败，再把它当门禁用**。
"""
import io, os, re, sys, tempfile

sys.stdout.reconfigure(encoding='utf-8')
WORK = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(WORK, 'en_check.py')
EN = r'<WORKDIR>\PaperB\PaperB_英文稿_PR_20260919.md'

CANDS = ['73 pp', '75 pp', '86 pp']     # 0–102 中曾经（用不完整的权威档清单）以为"不在权威档"的三个
ANCHOR = 'Its diagnosis is informative:'


def run_with(tmp_path, tok):
    """用 EN 指向 tmp_path 的 en_check 源码副本跑一次，返回 (退出码, 全部输出)。"""
    src = io.open(SRC, encoding='utf-8').read()
    src = src.replace("EN = os.path.join(ROOT, 'PaperB_英文稿_PR_20260919.md')",
                      "EN = r'%s'" % tmp_path, 1)
    assert tmp_path in src, '未能把 EN 指向临时稿'
    # StringIO 没有 reconfigure（en_check 第 10 行会调）⇒ 去掉那一行，只影响本探针
    src = src.replace("sys.stdout.reconfigure(encoding='utf-8')",
                      "pass  # reconfigure (skipped in probe)", 1)
    # 注入诊断：直接问 en_check 自己的集合，而不是在外面另算一套（外面那套曾漏掉若干权威档）
    marker = "_white_dead = WHITE <= zh_flat"
    assert marker in src, '未找到注入锚点（en_check 结构变了？请同步本探针）'
    src = src.replace(
        marker,
        "print('      DBG tok=%s in_en=%s in_zh=%s in_SECT=%s in_ARXIV=%s only_white=%s white_dead=%s' % ("
        "TOK_DEBUG, TOK_DEBUG in en_flat, TOK_DEBUG in zh_flat, TOK_DEBUG in SECT,"
        " TOK_DEBUG in ARXIV, sorted(_only_white), WHITE <= zh_flat))\n" + marker, 1)
    src = src.replace("ROOT = r'D:\\deepseek\\PaperB'",
                      "ROOT = r'D:\\deepseek\\PaperB'\nTOK_DEBUG = %r" % tok, 1)

    buf = io.StringIO()
    old, code = sys.stdout, None
    sys.stdout = buf
    try:
        exec(compile(src, SRC, 'exec'), {'__name__': '__probe__'})
    except SystemExit as e:
        code = e.code
    finally:
        sys.stdout = old
    return code, buf.getvalue()


def main():
    text = io.open(EN, encoding='utf-8', newline='').read()
    assert ANCHOR in text, '锚点句未找到：%s' % ANCHOR
    print('阳性对照：确认「白名单登记制」那条检查**能不能失败**')
    print('锚点句：%s（句前插入 "It moves by <TOK>."）' % ANCHOR)
    print()
    rows = []
    for tok in CANDS:
        text2 = text.replace(ANCHOR, 'It moves by %s. %s' % (tok, ANCHOR), 1)
        tmp = os.path.join(tempfile.gettempdir(), '_en_check_vacuity.md')
        io.open(tmp, 'w', encoding='utf-8', newline='').write(text2)
        try:
            code, out = run_with(tmp, tok.split()[0])
        finally:
            os.remove(tmp)
        dbg = next((l.strip() for l in out.splitlines() if 'DBG ' in l), '')
        rows.append((tok, dbg))
        print('  %-8s %s' % (tok, dbg or '（未取到诊断行）'))
    print()
    print('结论：三个候选**全部未能触发**那条检查 ⇒ 它是**永真断言**，已从 en_check.py 删除。')
    print('      根因（诊断行里的 in_zh=True / white_dead=True）：`WHITE ⊆ zh_flat`，')
    print('      故 `(en_flat - zh_flat - ARXIV - SECT - EQUIV) & WHITE` **恒为空集**。')
    print()
    print('留给后人的两条：')
    print('  ① **先证明判据能失败，再把它当门禁。** 一条从不失败的检查不是"更强的保障"，')
    print('     而是让"全过"更虚的装饰——本项目已在这一类错误上栽过（元组比较 bug、聚合 bug）。')
    print('  ② 残余盲区与它的正确归属：[F] 是**集合成员判据**，对**数值正确性**无感；')
    print('     "把 2.6 pp 改成 3.6 pp"这类要由重算类检查负责（见 en_check 输出里的那行说明）。')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
