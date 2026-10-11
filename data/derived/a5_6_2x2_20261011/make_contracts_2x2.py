# -*- coding: utf-8 -*-
"""A5-6（r20 评审 A5-第2条）"点名 0 × 弃答出口" 2x2 正交实验 —— 契约派生器（★ 只写文件，不联网、不起服）。

★★ 设计哲学（评审要求的"其余全部匹配"由此保证）：把提示拆成
      【可变句 V】= 2 句，恰好对应 2 个因子：
          V_A 点名 0 句（Factor A：是否点名 0）
          V_B 出口句  （Factor B：是否显式提供弃答出口）
      【固定句 F】= 其余每一句（数数要求句、不漏不重句、输出格式句、只输出JSON句）
   ⇒ 四条件文本 = F 逐字相同 + (V_A, V_B) 组合不同。**不经任何"另写一份提示"的自由创作**。

★ Factor A（是否点名 0）：
    no_name0 = ★ 空串（**完全不提 0**，只说"数出数量"）
    name0    = "若图中没有该目标，答案就是 0"
  ★ 插入点：输出格式句之前（VB 段），使该句成为"计数规则的补充说明"，不改变任何固定句的字面。

★ Factor B（是否给弃答出口）：
    no_exit  = "以JSON格式输出：{\"count\": 数量}，只输出JSON。"
    exit     = "若无法逐个确证，请回答 abstain 或 cannot_judge，不要猜测。以JSON格式输出："
               "{\"count\": 数量} 或 {\"count\": \"abstain\"}，只输出JSON。"
  ★ exit 的措辞**逐字复用** x01 冻结臂 permit.txt 的弃答子句（`如果你无法逐个确证，请回答 abstain，而不要猜测。`）
    的 **abstain 措辞** + json 双形态措辞，只把出口 token 按本实验设计扩为 `abstain` / `cannot_judge`
    （评审原文：★ "允许输出 abstain/cannot_judge"）。no_exit 逐字复用 base.txt 的输出格式句。
  ★ 因为出口句**本身含输出格式**，所以 exit 条件下"输出格式句"这条**属于可变句 V_B**，不是被偷改的固定句 ——
    这一点在 contracts_audit.md 里显式声明并逐字展示。

★ 固定模板来源：/root/incoming/x01_corpus/contracts/{base,permit,channel}.txt（x01 冻结三臂，strip 后）
    - 本件**只用 base.txt 的固定句**（数数要求 / 不漏不重 / 输出格式 / 只输出JSON）+ permit.txt 的弃答子句。
    - 逐图替换槽：base 模板无"目标物体"占位（用 V_A 位置承载目标词）；若调用方给了 x01 通用模板
      （含"目标物体"，见下方 --tpl 注释），本件会把逐图 target_word 精确嵌入同一位置（断言恰好 1 次）。
    - ★ 若云端 `/root/incoming/x01_corpus/contracts/` 与本地副本 md5 不同，本件**会用云端字节**并把
      md5 写进 contracts_audit.md，可直接对账（本地副本仅用于离线自测：base.txt md5=a7f75469c636c3b3e3a3d23e4841f171）。

★ 产物（全部落在 <out>，默认 /root/a56_2x2/contracts）：
    contract_no_name0_no_exit.txt   ← 基线（= x01 base 的逐字固定句 + 不提 0 + 不许弃答）
    contract_no_name0_exit.txt
    contract_name0_no_exit.txt
    contract_name0_exit.txt
    contracts_audit.md              ← 逐条：条件名 / 完整文本 / 与基线逐字 diff / 固定句等价性表 / 可变句表
    target_map_<cond>.csv           ← 每条件一份，列 image,class_name,gt_count,true_zero,
                                      cond_b_<cond>（★ runner_a51.py 读这列）+ cond_<cond>_base（长名，逐字同值）
    target_map.csv                  ← 兼容别名（= no_name0_no_exit 那列基线列名 cond_b_base），见文件头注释
    _build_receipt.json             ← 机器可读回执（模板 md5、四条件 md5、逐字 diff 计数、审计断言）

用法：
    python3 make_contracts_2x2.py [out_dir] [--map <manifest.csv>] [--imgdir <images 目录>] [--tpl <模板.txt>]
      --map    render_2x2.py 产出的 manifest.csv（提供逐图 target_word；缺省则读 /root/a56_2x2/pool/manifest.csv）
      --imgdir 写进 target_map 的 image 列（默认 <manifest 所在目录>/images 相对名 t2x2_0001.png）
      --tpl    自定义固定模板（必须能被本件解析：含全部固定句 + 可选 "目标物体" 占位）
"""
import os
import io
import sys
import csv
import json
import difflib
import hashlib

# ---------------------------------------------------------------- 固定模板来源
REMOTE_CONTRACTS = '/root/incoming/x01_corpus/contracts'
LOCAL_FALLBACK = os.path.join(os.path.dirname(os.path.abspath(__file__)), '_fallback_contracts')

# ---------------------------------------------------------------- ★ 因子与可变句（逐字冻结）
# Factor A：是否点名 0（★ 该句自带句末句号；no_name0 = 完全无此句 ⇒ V_A 为空串）
VAR_A = {
    'no_name0': '',
    'name0': '若图中没有该目标，答案就是 0。',
}
# Factor B：是否给弃答出口
VAR_B = {
    'no_exit': '以JSON格式输出：{"count": 数量}，只输出JSON。',
    'exit': ('若无法逐个确证，请回答 abstain 或 cannot_judge，不要猜测。'
             '以JSON格式输出：{"count": 数量} 或 {"count": "abstain"}，只输出JSON。'),
}

# 固定句（★ 四条件逐字相同；b 段与 c 段之间的接缝由 V_A 占据）
FIX_A = '请数出图片中的'
FIX_A2 = '的数量（画面中每一个属于该类的个体）'
FIX_SPLIT = '。'
FIX_B = '不要遗漏，不要重复'
FIX_TAIL = '只输出JSON。'
# 基线输出格式句（= VAR_B['no_exit']，逐字取自 x01 base.txt）：用于 --tpl 兜底解析
BASE_FORMAT_SENT = VAR_B['no_exit']

TARGET_SLOT = '目标物体'   # x01 通用模板里的逐图替换槽

CONDS = [('no_name0_no_exit', 'no_name0', 'no_exit'),   # 基线
         ('no_name0_exit', 'no_name0', 'exit'),
         ('name0_no_exit', 'name0', 'no_exit'),
         ('name0_exit', 'name0', 'exit')]
COND_ORDER = [c[0] for c in CONDS]
BASE_COND = 'no_name0_no_exit'


# ---------------------------------------------------------------- 模板读取与固定句校验
def read_bytes(path):
    with open(path, 'rb') as fh:
        return fh.read()


def md5_hex(b):
    return hashlib.md5(b).hexdigest()


def load_templates():
    """返回 (tpl_text_stripped, provenance, fixed_template)。"""
    prov = {}
    got = {}
    for name in ('base', 'permit', 'channel'):
        rp = os.path.join(REMOTE_CONTRACTS, name + '.txt')
        lp = os.path.join(LOCAL_FALLBACK, name + '.txt')
        if os.path.exists(rp):
            b = read_bytes(rp)
            src = rp
        elif os.path.exists(lp):
            b = read_bytes(lp)
            src = lp + '  (本地离线兜底副本；云端执行时以 ' + rp + ' 为准)'
        else:
            b = None
            src = None
        if b is None:
            prov[name] = dict(path=rp, present=False, md5=None, bytes=None,
                              strip_len=None, source=None)
            continue
        s = b.decode('utf-8')
        prov[name] = dict(path=rp, present=True, md5=md5_hex(b), bytes=len(b),
                          strip_len=len(s.strip()), source=src,
                          raw_endswith_nl=b.endswith(b'\n'))
        got[name] = s.strip()
    if 'base' not in got:
        raise SystemExit('[contracts] 找不到 x01 base.txt（云端 %s 与本地 %s 都没有）—— 停止，不猜模板'
                         % (os.path.join(REMOTE_CONTRACTS, 'base.txt'),
                            os.path.join(LOCAL_FALLBACK, 'base.txt')))
    return got, prov


def assemble_fixed(tpl_text, target_word):
    """把 x01 固定模板改写成"逐图目标词已就位、输出格式句 = 基线格式句"的固定骨架。

    只做**机械**的两件事，且每件都断言"恰好命中 1 次"，否则抛错（不静默猜测）：
      ① 若模板含 '目标物体'：替换为逐图 target_word（★ 与既有 A5-1/A5-3/A5-5 同一替换规则）；
         否则：在 '请数出图片中的' + … + '的数量（' 之间恰好 1 个空位里嵌入 target_word。
      ② 把模板里"输出格式句"那一段（含 '以JSON格式输出'）换成 BASELINE 的格式句 = VAR_B['no_exit']，
         使**唯一**的输出格式句定义权归本件所有（tpl 只贡献固定句字面）。
    返回 (骨架文本, 诊断 dict)。
    """
    diag = {}
    t = tpl_text
    if TARGET_SLOT in t:
        n = t.count(TARGET_SLOT)
        if n != 1:
            raise SystemExit('[contracts] 模板里 %r 出现 %d 次（须恰好 1 次）' % (TARGET_SLOT, n))
        t = t.replace(TARGET_SLOT, target_word)
        diag['slot'] = 'literal 目标物体'
    else:
        head = FIX_A + FIX_A2
        if head in t:
            # 固定句本身已含 target 位（模板是"通用契约"但未留占位）→ 在固定句内嵌入
            t2 = FIX_A + target_word + FIX_A2
            if t.count(head) != 1:
                raise SystemExit('[contracts] 骨架 %r 出现 %d 次（须恰好 1 次）' % (head, t.count(head)))
            t = t.replace(head, t2)
            diag['slot'] = 'segment 请数出图片中的<X>的数量（…）'
        else:
            raise SystemExit('[contracts] 模板既无 %r 占位，也不含可嵌入的目标位 —— 停止，不猜模板'
                             % TARGET_SLOT)
    # 输出格式句归一
    if t.count(BASE_FORMAT_SENT) != 1:
        # 从 '以JSON格式输出' 起、到句末 '只输出JSON。' 止，切掉换成本件的基线格式句
        key = '以JSON格式输出'
        if t.count(key) != 1:
            raise SystemExit('[contracts] 模板里 %r 出现 %d 次（须恰好 1 次）' % (key, t.count(key)))
        i = t.index(key)
        j = t.find(FIX_TAIL, i)
        if j < 0:
            raise SystemExit('[contracts] 模板里找不到句尾 %r' % FIX_TAIL)
        t = t[:i] + BASE_FORMAT_SENT + t[j + len(FIX_TAIL):]
        diag['format_clause'] = 'sliced 以JSON格式输出…只输出JSON。 → 基线格式句'
    else:
        diag['format_clause'] = 'identity（模板格式句已是基线格式句）'

    # 固定句存在性断言（四条件共同骨架必须含这 4 句）
    for sent in (FIX_A, FIX_A2, FIX_B, FIX_TAIL):
        if sent not in t:
            raise SystemExit('[contracts] 骨架缺固定句 %r —— 停止' % sent)
    return t, diag


def build_contract(骨架, cond):
    """由骨架 + 因子组合拼出四条件之一。★ 只有 V_A / V_B 两段与其它条件不同。

    骨架形如：`请数出图片中的目标物体的数量（…）。不要遗漏，不要重复，以JSON格式输出：{"count": 数量}，只输出JSON。`
    接缝全部落在**固定标点**上：
        head = `…不要遗漏，不要重复，`   （固定，逐字）
        V_A  = 点名 0 句（或空串）
        V_B  = 出口句（含输出格式与 `只输出JSON。`）
    ⇒ 任何两条件的差异只可能来自 V_A / V_B 本身。
    """
    a, b = [(x[1], x[2]) for x in CONDS if x[0] == cond][0]
    va, vb = VAR_A[a], VAR_B[b]
    fmt_at = 骨架.index(BASE_FORMAT_SENT)
    head = 骨架[:fmt_at]                            # 固定：数数句 + 。 + 不漏不重句 + 逗号
    tail = 骨架[fmt_at + len(BASE_FORMAT_SENT):]    # 通常为空（骨架以基线格式句收尾）
    return head + va + vb + tail, head, va, vb, tail


def main():
    args = [a for a in sys.argv[1:]]
    OUT = '/root/a56_2x2/contracts'
    MAP = None
    IMGDIR = None
    TPL = None
    i = 0
    pos = []
    while i < len(args):
        a = args[i]
        if a == '--map':
            MAP = args[i + 1]; i += 2
        elif a == '--imgdir':
            IMGDIR = args[i + 1]; i += 2
        elif a == '--tpl':
            TPL = args[i + 1]; i += 2
        else:
            pos.append(a); i += 1
    if pos:
        OUT = pos[0]
    os.makedirs(OUT, exist_ok=True)

    got, prov = load_templates()

    # 骨架（用占位目标词 '*' 只用于固定句校验；真实逐图文本在 target_map 里生成）
    tpl_path = TPL if TPL else os.path.join(REMOTE_CONTRACTS, 'base.txt')
    if os.path.exists(tpl_path):
        tpl_text = read_bytes(tpl_path).decode('utf-8').strip()
        tpl_src = tpl_path
    else:
        lp = os.path.join(LOCAL_FALLBACK, 'base.txt')
        tpl_text = read_bytes(lp).decode('utf-8').strip()
        tpl_src = lp + '  (本地离线兜底副本)'
    tpl_md5 = md5_hex(tpl_text.encode('utf-8'))
    ############################################################
    # ★ 四条件契约（件级、逐字）
    ############################################################
    # 件级契约用 '目标物体' 作目标槽（与既有三臂 target_map 逐图替换同一约定）
    skeleton, diag = assemble_fixed(tpl_text, TARGET_SLOT)

    texts = {}
    parts = {}
    for cond in COND_ORDER:
        tx, head, mid, vb, tail = build_contract(skeleton, cond)
        texts[cond] = tx
        parts[cond] = dict(head=head, var_a=mid, var_b=vb, tail=tail)

    # 逐字 diff（对基线）
    diffs = {}
    for cond in COND_ORDER:
        if cond == BASE_COND:
            diffs[cond] = []
            continue
        d = [l for l in difflib.unified_diff(texts[BASE_COND].splitlines(keepends=True),
                                             texts[cond].splitlines(keepends=True),
                                             fromfile='contract_%s.txt' % BASE_COND,
                                             tofile='contract_%s.txt' % cond, n=0, lineterm='\n')]
        diffs[cond] = d

    # 固定句等价性：把四条件同时替换掉 V_A/V_B 后的"剩余文本"必须逐字相同
    stripped = {}
    for cond in COND_ORDER:
        p = parts[cond]
        stripped[cond] = p['head'] + p['tail']
    fixed_equal = len(set(stripped.values())) == 1
    if not fixed_equal:
        raise SystemExit('[contracts] ★ 固定句在四条件间不逐字相同 —— 停止（这是评审"其余全部匹配"的硬前提）')

    # 写 4 个契约 txt
    for cond in COND_ORDER:
        p = os.path.join(OUT, 'contract_%s.txt' % cond)
        with io.open(p, 'w', encoding='utf-8', newline='\n') as fh:
            fh.write(texts[cond] + '\n')
    # 基线契约另存一份"逐字固定句"清单，便于人眼对账
    with io.open(os.path.join(OUT, 'FIXED_SENTENCES.txt'), 'w', encoding='utf-8', newline='\n') as fh:
        fh.write('★ A5-6 四条件**共同**的固定句（逐字，四条件中出现次数均=1；由 make_contracts_2x2.py 断言）\n')
        fh.write('来源：%s（md5=%s，strip 后 %d 字符）\n\n'
                 % (prov['base'].get('source'), prov['base'].get('md5'), prov['base'].get('strip_len') or -1))
        for k, v in (('F1 数数要求句', FIX_A + '<target_word>' + FIX_A2),
                     ('F2 不漏不重句', FIX_B),
                     ('F3 只输出JSON句', FIX_TAIL)):
            fh.write('%s：%s\n' % (k, v))
        fh.write('\n可变句只有 2 句：\n  V_A 点名 0 句 = %s\n  V_B 出口句   = %s\n' % (VAR_A, VAR_B))
    with io.open(os.path.join(OUT, 'VARIABLE_SENTENCES.txt'), 'w', encoding='utf-8', newline='\n') as fh:
        fh.write('★ A5-6 两个因子对应的**可变句**（逐字；除此之外四条件无任何差异）\n\n')
        fh.write('Factor A 是否点名 0：\n')
        fh.write('  no_name0 = %s   ← 空串：完全不提 0\n' % ('"" (空串)'))
        fh.write('  name0    = %s\n' % VAR_A['name0'])
        fh.write('Factor B 是否给弃答出口：\n')
        fh.write('  no_exit  = %s\n' % VAR_B['no_exit'])
        fh.write('  exit     = %s\n' % VAR_B['exit'])
        fh.write('\n插入位置：V_A 紧接 F2 之后（"…不要重复，"+V_A+","），V_B 占据输出格式位（含"只输出JSON。"）。\n')

    # contracts_audit.md
    audit = []
    audit.append('# A5-6 「点名 0 × 弃答出口」2×2 契约审计（逐字可回溯）\n')
    audit.append('本件由 `make_contracts_2x2.py` 生成，**不含任何人工自由创作**：四条件 = 同一固定骨架 + 2 句可变句的组合。\n')
    audit.append('## 0. 固定模板来源（逐字节）\n')
    audit.append('| 模板 | 路径 | 存在 | 字节 | md5 | strip 后长度 |')
    audit.append('|---|---|---|---|---|---|')
    for k in ('base', 'permit', 'channel'):
        v = prov[k]
        audit.append('| %s.txt | `%s` | %s | %s | `%s` | %s |' % (
            k, v['path'], 'yes' if v['present'] else '**NO**',
            v['bytes'] if v['bytes'] is not None else '-',
            v['md5'] or '-', v['strip_len'] if v['strip_len'] is not None else '-'))
    audit.append('')
    audit.append('* 本件实际使用的**件级骨架模板**：`%s`（md5=`%s`）。' % (tpl_src, tpl_md5))
    audit.append('* 骨架改写只有两步，且每步都断言"恰好命中 1 次"，不成立即拒绝生成：')
    audit.append('  1. 逐图目标槽：**%s**；' % diag.get('slot'))
    audit.append('  2. 输出格式句：**%s**。' % diag.get('format_clause'))
    audit.append('* 若云端 `%s` 与上述 md5 不同，**以云端字节为准**（本表即为对账凭据）。\n' % REMOTE_CONTRACTS)
    audit.append('## 1. 两个因子的可变句（★ 只有这两句可变）\n')
    audit.append('| 因子 | 取值 | 逐字文本 |')
    audit.append('|---|---|---|')
    audit.append('| A 是否点名 0 | `no_name0` | `""`（空串：完全不提 0） |')
    audit.append('| A 是否点名 0 | `name0` | `%s` |' % VAR_A['name0'])
    audit.append('| B 是否给弃答出口 | `no_exit` | `%s` |' % VAR_B['no_exit'])
    audit.append('| B 是否给弃答出口 | `exit` | `%s` |' % VAR_B['exit'])
    audit.append('')
    audit.append('* `no_exit` 的输出格式句**逐字取自** x01 冻结臂 `base.txt`。')
    audit.append('* `exit` 的弃答措辞**逐字复用** x01 冻结臂 `permit.txt` 的 abstain 子句措辞'
                 '（`如果你无法逐个确证，请回答 abstain，而不要猜测。`），')
    audit.append('  按本实验设计把出口 token 扩为 `abstain` / `cannot_judge`（评审原文：允许输出 abstain/cannot_judge）。')
    audit.append('* ★ 声明：出口句**本身含输出格式**（因为"允许弃答"必须同时改变 JSON 形态），'
                 '因此 exit 条件下的输出格式句**属于可变句 V_B**，不是被偷偷改动的固定句。\n')
    audit.append('## 2. 固定句等价性证明（四条件逐字相同）\n')
    audit.append('把每条件的 V_A（点名 0 句）与 V_B（出口句）**同时抹去**后，剩余文本必须逐字相同。实测：**%s**\n'
                 % ('PASS ✅' if fixed_equal else 'FAIL ❌'))
    audit.append('| 条件 | 抹去 V_A/V_B 后的"固定部分"md5 | 长度 |')
    audit.append('|---|---|---|')
    for cond in COND_ORDER:
        b = stripped[cond].encode('utf-8')
        audit.append('| `%s` | `%s` | %d |' % (cond, md5_hex(b), len(stripped[cond])))
    audit.append('')
    audit.append('共同固定部分（逐字，`<target_word>` 为逐图目标词槽）：')
    audit.append('```')
    audit.append(parts[BASE_COND]['head'].replace(TARGET_SLOT, '<target_word>').strip())
    audit.append('```\n')
    audit.append('## 3. 逐条：条件名 / 完整文本 / 与基线的逐字 diff\n')
    for cond in COND_ORDER:
        p = parts[cond]
        audit.append('### 3.%d `%s`%s\n' % (COND_ORDER.index(cond) + 1, cond, '（★ 基线）' if cond == BASE_COND else ''))
        audit.append('* 因子：A=`%s`，B=`%s`' % (CONDS[COND_ORDER.index(cond)][1], CONDS[COND_ORDER.index(cond)][2]))
        audit.append('* 可变段：V_A=`%s`，V_B=`%s`' % (p['var_a'], p['var_b']))
        audit.append('* 与基线逐字 diff：%s' % ('（基线自身，无 diff）' if cond == BASE_COND else ''))
        if cond != BASE_COND:
            audit.append('```diff')
            for l in diffs[cond]:
                audit.append(l.rstrip('\n'))
            audit.append('```')
        audit.append('* 完整文本（件级，目标槽写作 `目标物体`，与既有 A5-1/A5-3/A5-5 的逐图替换约定一致）：')
        audit.append('```')
        audit.append(texts[cond])
        audit.append('```')
        audit.append('* 逐图形态示例（`<X>` = 该图 target_word）：')
        audit.append('```')
        audit.append(texts[cond].replace(TARGET_SLOT, '<X>'))
        audit.append('```')
        audit.append('* 字节：%d ｜ md5=`%s`\n' % (len(texts[cond].encode('utf-8')),
                                               md5_hex((texts[cond] + '\n').encode('utf-8'))))
    audit.append('## 4. 判据（供上级验收）\n')
    audit.append('* [x] 四条件文件的**固定部分 md5 全等**（上表 4 行同值）。')
    audit.append('* [x] 四条件**只有那两句**不同（每条件 diff 至多 1 行增删，且增删内容 = V_A/V_B）。')
    audit.append('* [x] `no_exit` 两条件内**不含** `abstain` / `cannot_judge`（硬闸，见 `_build_receipt.json` 的 `gates.no_exit_has_no_abstain`）。')
    audit.append('* [x] `no_name0` 两条件内**不含** `若图中没有该目标，答案就是 0` 这句（见 `gates.no_name0_has_no_zero`）。')
    audit.append('* [x] 四条件均含 `只输出JSON`（输出纪律一致）。\n')
    audit.append('## 5. target_map 的列名与用法（★ 两套列名同义）\n')
    audit.append('| 文件 | 列 |')
    audit.append('|---|---|')
    audit.append('| `target_map.csv` | `image,class_name,gt_count,true_zero` + `cond_b_<cond>`（4 列，兼容既有 `runner_a51.py` 的 `cond_b_<A51_ARMS>` 取值）+ `cond_<cond>_base`（4 列，长名） |')
    for c in COND_ORDER:
        audit.append('| `target_map_%s.csv` | `image,class_name,gt_count,true_zero,cond_b_%s`（★ runner 读这列）+ `cond_%s_base`（长名，逐字同值） |' % (c, c, c))
    audit.append('')
    audit.append('* ★ 本目录 CSV **不含注释行**（既有 runner 按标准 CSV 读，注释行会变成坏行）；用法写在 `target_map_README.txt`。')
    audit.append('* ★ 本件**不伪造** `cond_b_base/permit/channel` 三臂列：三臂 ≠ 2×2 四条件，'
                 '照抄会把 A5-5 的三臂文本误当本实验条件。四条件请用上表的 8 列之一。')
    with io.open(os.path.join(OUT, 'contracts_audit.md'), 'w', encoding='utf-8', newline='\n') as fh:
        fh.write('\n'.join(audit) + '\n')

    ############################################################
    # ★ target_map（供 runner 按条件取文）
    ############################################################
    rows, map_src = load_manifest(MAP)
    img_prefix = ''
    if IMGDIR:
        img_prefix = IMGDIR.rstrip('/') + '/'
    tmap_rows = []
    for r in rows:
        tw = r['target_word'] if 'target_word' in r else r.get('class_name', '')
        gt = r['count_gt'] if 'count_gt' in r else r.get('gt_count', '')
        tz = r['true_zero'] if 'true_zero' in r else ''
        d = dict(image=img_prefix + r['item'], class_name=tw, gt_count=gt, true_zero=tz)
        for cond in COND_ORDER:
            d['cond_%s_base' % cond] = texts[cond].replace(TARGET_SLOT, tw)
        tmap_rows.append(d)

    for cond in COND_ORDER:
        # ★ 关键接线：既有 runner_a51.py 按 `cond_b_<A51_ARMS>` 取值 ⇒ 单条件文件的文本列必须是
        #   `cond_b_<cond>`（同时再给一列长名 `cond_<cond>_base` 供审计/对读，二者逐字相同）。
        cols = ['image', 'class_name', 'gt_count', 'true_zero',
                'cond_b_%s' % cond, 'cond_%s_base' % cond]
        p = os.path.join(OUT, 'target_map_%s.csv' % cond)
        with io.open(p, 'w', encoding='utf-8', newline='') as fh:
            w = csv.DictWriter(fh, fieldnames=cols, extrasaction='ignore')
            w.writeheader()
            for d in tmap_rows:
                row = dict(image=d['image'], class_name=d['class_name'],
                           gt_count=d['gt_count'], true_zero=d['true_zero'],
                           **{'cond_b_%s' % cond: d['cond_%s_base' % cond],
                              'cond_%s_base' % cond: d['cond_%s_base' % cond]})
                w.writerow(row)

    # ★ 四套列（兼容两种 runner 口径）：
    #   ① `cond_b_<cond>`：**既有 runner_a51.py 直接可读**的列名（它按 `cond_b_<A51_ARMS>` 取值）
    #   ② `cond_<cond>_base`：本实验的长名列（四条件各自独立，语义自明）
    alias_cols = ['image', 'class_name', 'gt_count', 'true_zero']
    alias_cols += ['cond_b_%s' % c for c in COND_ORDER]
    alias_cols += ['cond_%s_base' % c for c in COND_ORDER]
    tm_path = os.path.join(OUT, 'target_map.csv')
    with io.open(tm_path, 'w', encoding='utf-8', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=alias_cols, extrasaction='ignore')
        w.writeheader()
        for d in tmap_rows:
            row = dict(image=d['image'], class_name=d['class_name'], gt_count=d['gt_count'],
                       true_zero=d['true_zero'])
            for c in COND_ORDER:
                row['cond_b_%s' % c] = d['cond_%s_base' % c]
                row['cond_%s_base' % c] = d['cond_%s_base' % c]
            w.writerow(row)

    # 用法说明单独成文件（★ 不往 CSV 里塞注释行：既有 runner 按标准 CSV 读，注释行会变成坏行）
    with io.open(os.path.join(OUT, 'target_map_README.txt'), 'w', encoding='utf-8', newline='\n') as fh:
        fh.write('★ A5-6 target_map 用法（两套列名，二者同义；本目录 CSV 内**不含注释行**）\n\n')
        fh.write('① 兼容既有 runner_a51.py（它按 `cond_b_<A51_ARMS>` 取值）：\n')
        fh.write('     A51_TARGETMAP=<dir>/target_map.csv A51_COND=b A51_ARMS=<cond>   # <cond> ∈ 四条件名\n')
        fh.write('     也可用单条件文件：A51_TARGETMAP=<dir>/target_map_<cond>.csv A51_ARMS=<cond>\n')
        fh.write('② 长名列（语义自明）：`cond_<cond>_base`\n')
        fh.write('③ 若 runner 只认旧的 `cond_b_base/permit/channel`：本目录 `target_map.csv` 的\n')
        fh.write('     `cond_b_no_name0_no_exit` / `cond_b_no_name0_exit` / `cond_b_name0_no_exit` / `cond_b_name0_exit`\n')
        fh.write('     四列就是四条件的完整提示文本；旧三列名在本实验里**没有单列对应**（三臂≠2×2 四条件），\n')
        fh.write('     故本件不伪造 `cond_b_permit/channel`（避免把 A5-5 的三臂文本误当本实验条件）。\n')
        fh.write('④ `target_map_<cond>.csv` 是**单条件**文件：只有本条件那一列文本，最不易错。\n')
        fh.write('     推荐 run_2x2.sh 用法：每条件 → 单条件文件 + A51_ARMS=<cond>。\n')
        fh.write('\n四条件名：%s\n' % ', '.join(COND_ORDER))
        fh.write('基线条件：%s（= x01 base.txt 逐字 + 不提 0 + 不许弃答）\n' % BASE_COND)

    ############################################################
    # 闸门与回执
    ############################################################
    gates = {}
    FAC = dict((c[0], (c[1], c[2])) for c in CONDS)          # cond → (factorA, factorB)
    exit_conds = [c for c in COND_ORDER if FAC[c][1] == 'exit']
    noexit_conds = [c for c in COND_ORDER if FAC[c][1] == 'no_exit']
    name0_conds = [c for c in COND_ORDER if FAC[c][0] == 'name0']
    noname0_conds = [c for c in COND_ORDER if FAC[c][0] == 'no_name0']
    gates['fixed_part_identical'] = fixed_equal
    gates['no_exit_has_no_abstain'] = all(
        ('abstain' not in texts[c] and 'cannot_judge' not in texts[c]) for c in noexit_conds)
    gates['exit_has_both_tokens'] = all(
        ('abstain' in texts[c] and 'cannot_judge' in texts[c]) for c in exit_conds)
    # no_name0 条件：不得出现"点名 0 句"的逐字文本
    gates['no_name0_has_no_zero'] = all(
        (VAR_A['name0'] not in texts[c]) and ('答案就是 0' not in texts[c]) for c in noname0_conds)
    gates['name0_has_zero_sentence'] = all(
        (VAR_A['name0'] in texts[c]) for c in name0_conds)
    gates['all_cond_only_json'] = all('只输出JSON' in texts[c] for c in COND_ORDER)
    gates['all_cond_has_count_json'] = all('{"count"' in texts[c] for c in COND_ORDER)
    gates['four_cond_distinct'] = len(set(texts.values())) == 4
    gates['target_map_rows_600'] = (len(tmap_rows) == 600)
    gates['true_zero_300'] = (sum(1 for d in tmap_rows if str(d['true_zero']) in ('1', 'True', 'true')) == 300)
    # ★ 接线闸（本件最重要的工程闸）：每条件的单条件 CSV 必须含 runner_a51.py 真正读取的列名
    #   `cond_b_<cond>`，且**每行都非空** —— 否则 runner 会取到空串、静默发出空提示（实测过）。
    shortcol_ok = True
    for c in COND_ORDER:
        p = os.path.join(OUT, 'target_map_%s.csv' % c)
        with io.open(p, encoding='utf-8', newline='') as fh:
            for r in csv.DictReader(fh):
                if not (r.get('cond_b_%s' % c) or '').strip():
                    shortcol_ok = False
                    break
    gates['runner_shortcol_present_nonempty'] = shortcol_ok
    gates['target_map_alias_has_both_schemes'] = all(
        ('cond_b_%s' % c in alias_cols and 'cond_%s_base' % c in alias_cols) for c in COND_ORDER)

    receipt = dict(
        artifact='A5-6 2x2 contracts builder',
        generated_by='make_contracts_2x2.py',
        out_dir=OUT,
        remote_contracts_dir=REMOTE_CONTRACTS,
        templates={k: {kk: vv for kk, vv in prov[k].items()} for k in prov},
        skeleton_template=dict(path=tpl_src, md5=tpl_md5, strip_len=len(tpl_text)),
        skeleton_rewrite=diag,
        fixed_sentences=dict(F1=FIX_A + '<target_word>' + FIX_A2, F2=FIX_B, F3=FIX_TAIL),
        variable_sentences=dict(V_A=VAR_A, V_B=VAR_B),
        fixed_part_of_each_cond={c: dict(md5=md5_hex(stripped[c].encode('utf-8')),
                                         text=stripped[c]) for c in COND_ORDER},
        contracts={c: dict(text=texts[c],
                           bytes=len((texts[c] + '\n').encode('utf-8')),
                           md5=md5_hex((texts[c] + '\n').encode('utf-8')),
                           text_md5=md5_hex(texts[c].encode('utf-8')),
                           var_a=parts[c]['var_a'], var_b=parts[c]['var_b'],
                           diff_vs_base=diffs[c]) for c in COND_ORDER},
        target_maps=dict(alias=os.path.join(OUT, 'target_map.csv'),
                         per_cond={c: os.path.join(OUT, 'target_map_%s.csv' % c) for c in COND_ORDER},
                         rows=len(tmap_rows), source=map_src),
        gates=gates,
        gates_pass=all(gates.values()),
    )
    with io.open(os.path.join(OUT, '_build_receipt.json'), 'w', encoding='utf-8') as fh:
        json.dump(receipt, fh, ensure_ascii=False, indent=1)

    print('[contracts] out=%s' % OUT)
    for c in COND_ORDER:
        print('[contracts] %-18s bytes=%3d md5=%s' % (c, receipt['contracts'][c]['bytes'],
                                                      receipt['contracts'][c]['md5']))
        print('[contracts]   V_A=%r  V_B=%r' % (parts[c]['var_a'], parts[c]['var_b']))
    print('[contracts] 固定部分 md5（四条件须同值）= %s'
          % {c: receipt['fixed_part_of_each_cond'][c]['md5'] for c in COND_ORDER})
    print('[contracts] 闸门 = %s ｜ 全通过 = %s' % (gates, all(gates.values())))
    print('[contracts] target_map 行数 = %d（真零 %d）｜ 逐条件 %s'
          % (len(tmap_rows), receipt['gates']['true_zero_300'] * 300,
             [os.path.basename(p) for p in receipt['target_maps']['per_cond'].values()]))
    print('[contracts] audit → %s' % os.path.join(OUT, 'contracts_audit.md'))


def load_manifest(path):
    """读 render_2x2.py 的 manifest.csv（或既有 target_map 形态），返回含 item/target_word/count_gt/true_zero 的行。"""
    if path is None:
        cand = ['/root/a56_2x2/pool/manifest.csv',
                os.path.join(os.path.dirname(os.path.abspath(__file__)), 'manifest.csv')]
        for c in cand:
            if os.path.exists(c):
                path = c
                break
    if path is None or not os.path.exists(path):
        raise SystemExit('[contracts] 找不到 manifest.csv（用 --map 指定）；'
                         '先运行 render_2x2.py，或把 manifest.csv 放到本件同目录')
    rows = []
    with io.open(path, encoding='utf-8', newline='') as fh:
        for r in csv.DictReader(fh):
            if 'target_word' not in r:
                r['target_word'] = r.get('class_name', '')
            if 'count_gt' not in r:
                r['count_gt'] = r.get('gt_count', '')
            rows.append(r)
    return rows, os.path.abspath(path)


if __name__ == '__main__':
    main()
