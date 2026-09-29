# -*- coding: utf-8 -*-
"""参考文献**按正文首次出现顺序**重编号（PR 官方 L693）。
做法：① 解析列表；② 按正文首现建 old→new 映射；③ 改写正文所有 [n]（含 [a,b]）；
④ 按 new 顺序重排列表并重编号。
**写盘前硬校验**：重排后正文首现序列必须为 1..N 严格递增、1..N 全覆盖、[n] token 总数不变。
"""
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')
MS = r'<WORKDIR>\PaperB\PaperB_英文稿_PR_20260919.md'
t = open(MS, encoding='utf-8').read()
head, sep, refs = t.partition('## References')
entries = re.findall(r'(?m)^(\d+)\. (.+)$', refs)
N = len(entries)
if N < 35:
    raise SystemExit('列表解析异常：只解析到 %d 条' % N)
by_old = {int(n): txt for n, txt in entries}

# 首现顺序
first, order = {}, []
for m in re.finditer(r'\[(\d+(?:\s*,\s*\d+)*)\]', head):
    for n in re.findall(r'\d+', m.group(1)):
        n = int(n)
        if n not in first:
            first[n] = m.start()
            order.append(n)
print('正文引用到的编号 %d 个；列表 %d 条' % (len(order), N))
if len(order) != N:
    missing = sorted(set(by_old) - set(order))
    raise SystemExit('有未被引用的条目，先修引用：%s' % missing)

mapping = {old: i + 1 for i, old in enumerate(order)}
print('映射前 10：%s' % {k: mapping[k] for k in order[:10]})

# 改写正文
n_tok_before = len(re.findall(r'\[(\d+(?:\s*,\s*\d+)*)\]', head))
def repl(m):
    nums = [str(mapping[int(x)]) for x in re.findall(r'\d+', m.group(1))]
    return '[' + ', '.join(nums) + ']'
new_head = re.sub(r'\[(\d+(?:\s*,\s*\d+)*)\]', repl, head)
n_tok_after = len(re.findall(r'\[(\d+(?:\s*,\s*\d+)*)\]', new_head))

# 重排列表
new_refs = ['## References'] + ['%d. %s' % (i + 1, by_old[order[i]]) for i in range(N)]
# ★ 保留参考文献表之后的尾部（附录指针等）——上次正因丢了它整节
_last = list(re.finditer(r'(?m)^\d+\. .*$', refs))[-1]
KEEP_TAIL = refs[_last.end():].strip()
new_refs_txt = '\n\n'.join([new_refs[0]] + new_refs[1:]) + '\n'
new_t = new_head + new_refs_txt + ('\n\n' + KEEP_TAIL + '\n' if KEEP_TAIL else '')

# 硬校验
chk_first, chk_order = {}, []
for m in re.finditer(r'\[(\d+(?:\s*,\s*\d+)*)\]', new_t.split('## References')[0]):
    for x in re.findall(r'\d+', m.group(1)):
        x = int(x)
        if x not in chk_first:
            chk_first[x] = m.start(); chk_order.append(x)
ok_order = chk_order == list(range(1, N + 1))
ok_cover = set(chk_first) == set(range(1, N + 1))
ok_tok = n_tok_before == n_tok_after
print()
print('校验：首现序列=1..N 严格递增 %s | 1..N 全覆盖 %s | [n] token 数不变(%d→%d) %s'
      % (ok_order, ok_cover, n_tok_before, n_tok_after, ok_tok))
if not (ok_order and ok_cover and ok_tok):
    raise SystemExit('校验未通过，**不写盘**')
open(MS, 'w', encoding='utf-8', newline='\n').write(new_t)
print('已写盘：%d 条参考文献按首现顺序重编号完成' % N)
