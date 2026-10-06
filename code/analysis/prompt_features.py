# -*- coding: utf-8 -*-
"""prompt_features.py —— 提示词**条款级**特征表（v2.1，零 GPU）

为什么升级
----------
v1 只用"整条提示词的 0/1 标志"讲契约，实测有**四处硬缺陷**（均由本版 --selftest 钉住）：

  ① `pos_of_abstain` 对 `bestA` 返回 -1，而同一行 `has_abstain_word=True`
     —— 检测与定位用了两套词表（检测含"无法分辨"，定位只找字面 `abstain`）。
  ② `has_neg` 把"**不要遗漏/不要重复**"（枚举**完备性**）与"**不允许回答 0**"
     （输出**契约**）混成同一类，归因无法做。
  ③ 没有**句位**特征。而 P1b 的结论恰是"同一条契约句放在 system 还是 user 位，效应不同"。
  ④ `w1_prereg` 的键路径写成 `d['arms']`（不存在）⇒ 静默 0 臂，FSC 两个示例臂一直没进表。
  ⑤ v2.0 首跑暴露的切分 bug：从属连接词合并**跨句号**，把 `报告一个数值人数。即使无法精确计数…`
     并成一条，`bestA` 由 4 条款塌成 3 条款。本版先按句末标点切句，再在句内按逗号切分，
     连接词合并**只在句内**发生。

v2 的做法
--------
切分（机械、可复核）：
  0) 逐位保护：数字千分位逗号 `(?<=\d),(?=\s*\d)` → `\\x02`（避免 choice 臂的选项列表被切碎）；
  1) 保护成对定界符内部：`{...}` → `**...**` → `（...）` → `(...)` → `"..."` → `“...”`
     （保护后内部的中文逗号不参与切分；切完再还原，标签匹配在还原后的文本上做）；
  2) 先按**句末**标点切句：`[。！？；.!?;]`；
  3) 再在句内按 `[，,]` 切分句；
  4) 若句内某段以从属连接词开头（如果/即使/若/倘若/假如/而/也/并/且/再把/那么/则/同时/但/然后），
     则并入**本句内**前一段；
  5) 去空白、丢空段。

标签（多标签，一个条款可同时属于多类）：
  TASK           任务谓词（数什么、怎么数、报告什么）
  ENUM           枚举**完备性**约束（不要遗漏/不要重复/逐块/每一个人/每个个体/…）
  ABSTAIN_PERMIT 弃答**许可**（abstain / cannot_judge / no_people / 无法确证 / 无法分辨 / 无法确认）
  ZERO_FORBID    零值**禁止**或强制给数（不允许回答 0 / 拒答 / 必须给出具体数字 / 估计值）
  FORMAT         输出格式（JSON / 只输出 / output only JSON）
  PREMISE        以如果/若/… 开头、但不匹配以上任何类型的条件前提

  关键设计点①：`拒答` **只**进 ZERO_FORBID，不进 ABSTAIN_PERMIT
    （`bestB` 写的是"不允许回答 0 或拒答"，是**禁止**弃答；v1 误判为含弃答词）。
  关键设计点②：`逐个确证` **不**算 ENUM。因为 `permit` 用它引出**弃答条件**，
    而 `permitB` 用 `每个个体` 引出**完备性要求**，两者语义不同，混在一起会把
    "完备性"这一干扰变量污染。

臂级特征：每类的 条款数 / 字符占比 / 首次出现位（归一化 0–1）/ 是否在首句 / 是否在末句，
外加 mentions_zero / mentions_noun / is_choice / is_english / has_contract / contract_kind。

数据来源**直读原始文件**（不手工转录）：
  * `19e_probe_multi.py` 的 `P`                    —— E2/E3 主实验 9 臂
  * `pod_evidence/scripts/probe_gen.py` 的 `PROMPTS` —— 语料普查 5 臂（含 `forbid0`）
  * `19c_probe_paraphrase.py` 的 `P`（permitB/permitC/channelB）—— **换措辞臂**
  * `w1_prereg.json` → design.arms.frozen_new_prompts —— FSC `exemplar3` / `exemplar3permit`
并在 `experiment_arms()` 里扫描实验目录，报告"实验中出现过但特征表未覆盖"的臂，防脱节。

用法：
  python -u prompt_features.py                # 出表 + 写 json
  python -u prompt_features.py --dump         # 打印逐条切分（人工核对用）
  python -u prompt_features.py --selftest     # 与 GOLDEN 逐臂比对；任何不符即 exit 1
"""
import argparse
import glob
import hashlib
import importlib.util
import io
import json
import os
import re
import sys
import tempfile

# ── 复现包统一根：`_repro_root.py`（与本文件同目录）──────────────────────────────
# ★ 2026-10-06（v0654）：本脚本此前**硬拼** `PAPER/analysis/…`（`PAPER` = 本文件的上两级）。
#   作者树上那是真的，**放行树上没有 `analysis/` 这一层** ⇒ 四个驱动脚本里至少两个读不到，
#   `build()` 只会打印"读取失败"然后**少出臂**（`--selftest` 直接红）。现在四个来源一律走
#   `_repro_root` 的前缀映射表（作者树原样；放行树落到 `code/experiments/**` 的同名件）。
try:
    from _repro_root import resolve as RP, not_released as NR
except ImportError:                      # 只拷走单个脚本时：就地反推仓库根，无前缀映射表
    import os as _o
    _r = _o.environ.get('PAPERB_ROOT') or _o.path.dirname(_o.path.dirname(_o.path.abspath(__file__)))
    RP = lambda *p: _o.path.join(_r, *p)
    NR = lambda *p: _o.path.join(_r, '_NOT_RELEASED', *p)

sys.stdout.reconfigure(encoding='utf-8')
W = os.path.dirname(os.path.abspath(__file__))


def _req(path, what):
    """读驱动脚本前先报缺件（**具名**失败，不许静默少读一臂）。"""
    if not os.path.exists(path):
        raise RuntimeError('缺驱动脚本（%s）：%s' % (what, path))
    return path


TYPES = ['TASK', 'ENUM', 'ABSTAIN_PERMIT', 'ZERO_FORBID', 'FORMAT', 'PREMISE']

SPANS = [r'\{[^{}]*\}', r'\*\*[^*]*\*\*', r'（[^（）]*）', r'\([^()]*\)', r'"[^"]*"', r'“[^”]*”']
CONNECTIVES = ('如果', '若', '倘若', '假如', '即使', '而', '也', '并', '且', '再把',
               '那么', '则', '同时', '但', '然后')
SENT_SPLIT = '。！？；.!?;'
CLAUSE_SPLIT = '，,'
DIGIT_COMMA = re.compile(r'(?<=\d),(?=\s*\d)')


def _protect(t):
    spans = []
    for pat in SPANS:
        def rep(m, _s=spans):
            _s.append(m.group(0))
            return '\x00%d\x00' % (len(_s) - 1)
        t = re.sub(pat, rep, t)
    return t, spans


def _restore(t, spans):
    t = re.sub(r'\x00(\d+)\x00', lambda m: spans[int(m.group(1))], t)
    return t.replace('\x02', ',')


def split_clauses(text):
    """条款切分。规则见模块 docstring，第 0–5 步。"""
    t = DIGIT_COMMA.sub('\x02', text)
    prot, spans = _protect(t)
    out = []
    for sent in re.split('[' + SENT_SPLIT + ']', prot):
        if not sent.strip():
            continue
        merged = []
        for seg in re.split('[' + CLAUSE_SPLIT + ']', sent):
            seg = seg.strip()
            if not seg:
                continue
            if merged and seg.startswith(CONNECTIVES):
                merged[-1] += seg
            else:
                merged.append(seg)
        out.extend(merged)
    return [_restore(s, spans).strip() for s in out]


# ── 标签 ──────────────────────────────────────────────────────────────────────
TASK_RE = re.compile(
    r'请数出|请判断|请定位|请估计|请从以下|请报告|请参考图中给出的|报告一个数值|数出总数|估计画面'
    r'|给出最终估计数字|对每个人都要给出位置与计数|给出数字|有多少'
    r'|count the|give a number', re.I)
ENUM_RE = re.compile(
    r'不要遗漏|不要重复|逐块|对每个人|每一个人|逐个找|逐个数|逐一|每个区域|每个个体'
    r'|every individual|every person|each person|do not (miss|double)', re.I)
ABSTAIN_RE = re.compile(
    r'abstain|cannot_judge|no_people|无法判断|无法(?:逐个)?确证|无法分辨|无法精确|无法确认'
    r'|没有可辨认|unresolved|cannot be confirmed', re.I)
ZERO_RE = re.compile(
    r'不允许回答|不要回答|拒答|必须给出一个具体数字|必须给出你最好的估计'
    r'|给出你最好的估计|估计值|可能是\s*0|具体数字')
FORMAT_RE = re.compile(r'JSON|json|只输出|output only', re.I)
PREMISE_RE = re.compile(r'^(如果|若|倘若|假如|即使)')
# 单字 0（前后不能再接数字或小数点/连字符），或汉字"零"。
# 连字符排除是为了 `已归一化到 0-1000` 这类**坐标范围**不被误当作"提到了零值"。
ZERO_TOK = re.compile(r'(?<![\d.\-])0(?![\d.\-])|零')


def label(clause):
    ts = set()
    for t, rx in (('TASK', TASK_RE), ('ENUM', ENUM_RE), ('ABSTAIN_PERMIT', ABSTAIN_RE),
                  ('ZERO_FORBID', ZERO_RE), ('FORMAT', FORMAT_RE)):
        if rx.search(clause):
            ts.add(t)
    if not ts and PREMISE_RE.search(clause):
        ts.add('PREMISE')
    return ts


def feats(text, arm, src):
    cls = split_clauses(text)
    labs = [label(c) for c in cls]
    n = len(cls) or 1
    f = dict(arm=arm, source=src, text=text, n_clauses=len(cls), chars=len(text),
             clauses=[dict(text=c, types=sorted(t)) for c, t in zip(cls, labs)])
    for t in TYPES:
        idx = [i for i, s in enumerate(labs) if t in s]
        chars = sum(len(cls[i]) for i in idx)
        f['n_' + t] = len(idx)
        f['has_' + t] = bool(idx)
        f['frac_' + t] = round(chars / max(1, len(text)), 4)
        f['pos_' + t] = round(idx[0] / max(1, len(cls) - 1), 4) if idx else -1.0
        f['first_' + t] = bool(idx) and idx[0] == 0
        f['last_' + t] = bool(idx) and idx[-1] == len(cls) - 1
    f['has_contract'] = f['has_ABSTAIN_PERMIT'] or f['has_ZERO_FORBID']
    f['contract_kind'] = ('permit' if f['has_ABSTAIN_PERMIT'] and not f['has_ZERO_FORBID']
                          else 'forbid' if f['has_ZERO_FORBID'] and not f['has_ABSTAIN_PERMIT']
                          else 'mixed' if f['has_ABSTAIN_PERMIT'] and f['has_ZERO_FORBID']
                          else 'none')
    f['mentions_zero'] = bool(ZERO_TOK.search(text))
    f['mentions_noun'] = any(k in text for k in ('人数', '人', '物体', '细胞', 'count', 'person', 'people'))
    f['is_choice'] = ('选项' in text) or ('choice' in text)
    f['is_english'] = not re.search(r'[\u4e00-\u9fff]', text)
    return f


# ── 读原始提示词 ──────────────────────────────────────────────────────────────
def _mod(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def load_19e():
    m = _mod(_req(RP('analysis', 'work', '19e_probe_multi.py'), '19e'), 'pf_19e')
    return {k: v for k, v in m.P.items() if isinstance(v, str)}, '19e(E2/E3 主实验)'


def load_probe_gen():
    p = _req(RP('analysis', 'pod_evidence', 'scripts', 'probe_gen.py'), 'probe_gen')
    # ★ 2026-10-06（v0654）：`probe_gen.py` 在 **import 期**就 `os.makedirs(PROBE_OUT)`。
    #   旧默认写在本脚本自己所在目录（`<pkg>/code/analysis/_promptfeat_tmp`）⇒ 评审者在**放行树内**
    #   跑一次本脚本就会在包里**多出一个目录**（正是任务书 §… 明令避免的写盘副作用）。
    #   改成临时目录：本脚本**只读** `PROMPTS`，产物落点与它无关。
    os.environ.setdefault('PROBE_OUT', os.path.join(tempfile.gettempdir(), '_promptfeat_tmp'))
    m = _mod(p, 'pf_pgen')
    return {k: v for k, v in dict(m.PROMPTS).items() if isinstance(v, str)}, 'probe_gen(语料普查)'


PARA_CANDIDATES = [
    ('analysis', 'h20_rescue_20260922', 'extract', '19c_probe_paraphrase.py'),
    ('analysis', 'work', '19c_probe_paraphrase.py'),
    ('analysis', 'e2xt_a800', 'env', 'a800_scripts', '19c_probe_paraphrase.py'),
]
PARA_ARMS = ('permitB', 'permitC', 'channelB')


def load_paraphrase():
    """换措辞臂。**必须**读到 3 臂；同时报出所用文件的 md5-12 供复核。"""
    tried = []
    for parts in PARA_CANDIDATES:
        p = RP(*parts)
        tried.append(p)
        if not os.path.exists(p):
            continue
        m = _mod(p, 'pf_19c')
        out = {k: v for k, v in m.P.items() if k in PARA_ARMS and isinstance(v, str)}
        if len(out) == 3:
            md5 = hashlib.md5(io.open(p, 'rb').read()).hexdigest()[:12]
            return out, '19c(换措辞臂) md5=%s' % md5
    raise RuntimeError('未找到含 %s 的 19c 驱动；候选路径都不可用：%s' % (PARA_ARMS, tried))


def load_w1():
    """★ v1 的 bug：键路径写成 d['arms']（不存在）⇒ 静默 0 臂。"""
    p = os.path.join(W, 'w1_prereg.json')
    d = json.loads(io.open(p, encoding='utf-8').read())
    fp = d['design']['arms']['frozen_new_prompts']
    out = {k: v for k, v in fp.items() if isinstance(v, str)}
    if len(out) < 2:
        raise RuntimeError('w1_prereg 只读到 %d 臂，键路径可能又变了' % len(out))
    return out, 'w1_prereg(FSC 示例臂)'


ARM_RE = re.compile(r'^(?:e1_)?.*?_(st_a|st_b|ucf|visdrone|aitod|countbench)_'
                    r'(base|permit|channel|enumAbstain|bestA|bestB|bestC|enum|locate|forbid0)'
                    r'(?:B|C)?\.csv$')


def experiment_arms():
    arms = set()
    dirs = [RP('analysis', 'e1_results_census'),
            RP('analysis', 'e2_newh20'),
            RP('analysis', 'e2xt_a800', 'merged')]
    for d in dirs:
        for f in glob.glob(os.path.join(d, '*.csv')):
            m = ARM_RE.match(os.path.basename(f))
            if m:
                arms.add(m.group(2))
    return arms


# ── 黄金标注（人工逐条核对后写死；--selftest 用它钉住切分与标签）────────────────
# 键 = (source-prefix, arm)；值 = 逐条款的类型集合（顺序 = 切分顺序）。
GOLDEN = {
    ('19e', 'base'): [{'TASK'}, {'ENUM'}, {'ENUM'}, {'FORMAT'}, {'FORMAT'}],
    ('19e', 'bestA'): [{'TASK'}, {'ABSTAIN_PERMIT', 'ZERO_FORBID'},
                       {'ABSTAIN_PERMIT', 'FORMAT'}, {'FORMAT'}],
    ('19e', 'bestB'): [{'ZERO_FORBID'}, {'ZERO_FORBID'}, {'PREMISE'}, {'ZERO_FORBID'},
                       {'FORMAT'}, {'FORMAT'}],
    ('19e', 'bestC'): [{'TASK', 'ENUM'}, {'TASK'}, {'ZERO_FORBID'}, {'ZERO_FORBID'},
                       {'FORMAT'}, {'FORMAT'}],
    ('19e', 'channel'): [{'TASK'}, {'TASK'}, {'ABSTAIN_PERMIT'}, {'ABSTAIN_PERMIT'},
                         {'FORMAT'}, {'FORMAT'}],
    ('19e', 'enum'): [{'TASK', 'ENUM'}, {'FORMAT'}, {'FORMAT'}],
    ('19e', 'enumAbstain'): [{'TASK', 'ENUM'}, {'ABSTAIN_PERMIT'}, {'ABSTAIN_PERMIT'},
                             {'ABSTAIN_PERMIT', 'FORMAT'}, {'FORMAT'}],
    ('19e', 'locate'): [{'TASK', 'ENUM'}, {'TASK', 'ENUM'}, {'FORMAT'}, {'FORMAT'}],
    ('19e', 'permit'): [{'TASK'}, {'ABSTAIN_PERMIT'}, {'ABSTAIN_PERMIT'},
                        {'ABSTAIN_PERMIT', 'FORMAT'}, {'FORMAT'}],
    ('probe_gen', 'base'): [{'TASK'}, {'ENUM'}, {'ENUM'}, {'FORMAT'}, {'FORMAT'}],
    ('probe_gen', 'cells'): [{'TASK'}, {'ENUM'}, {'ENUM'}, {'FORMAT'}, {'FORMAT'}],
    ('probe_gen', 'choice'): [{'TASK'}, {'FORMAT'}, {'FORMAT'}],
    ('probe_gen', 'forbid0'): [{'TASK'}, {'ENUM'}, {'ENUM'}, {'ZERO_FORBID'}, {'ZERO_FORBID'},
                               {'ZERO_FORBID'}, {'FORMAT'}, {'FORMAT'}],
    ('probe_gen', 'objects'): [{'TASK'}, {'ENUM'}, {'ENUM'}, {'FORMAT'}, {'FORMAT'}],
    ('probe_gen', 'range'): [{'TASK'}, {'FORMAT'}, {'FORMAT'}],
    ('19c', 'permitB'): [{'TASK'}, {'ENUM', 'TASK'}, {'ABSTAIN_PERMIT'}, {'ABSTAIN_PERMIT'},
                         {'ABSTAIN_PERMIT', 'FORMAT'}, {'FORMAT'}],
    ('19c', 'permitC'): [{'TASK'}, {'ENUM', 'TASK'}, {'ABSTAIN_PERMIT'}, {'ABSTAIN_PERMIT'},
                         {'ABSTAIN_PERMIT', 'FORMAT'}],
    ('19c', 'channelB'): [{'TASK'}, {'ABSTAIN_PERMIT'}, {'ABSTAIN_PERMIT'}, {'ABSTAIN_PERMIT'},
                          {'ABSTAIN_PERMIT'}, {'TASK'}, {'FORMAT'}, {'FORMAT'}],
    ('w1_prereg', 'exemplar3'): [{'TASK'}, {'TASK'}, {'ENUM'}, {'FORMAT'}, {'FORMAT'}],
    ('w1_prereg', 'exemplar3permit'): [{'TASK'}, {'TASK'}, {'ABSTAIN_PERMIT'}, {'ABSTAIN_PERMIT'},
                                       {'ABSTAIN_PERMIT', 'FORMAT'}, {'FORMAT'}],
}
SRC_KEY = {'19e': '19e(', 'probe_gen': 'probe_gen', '19c': '19c(', 'w1_prereg': 'w1_prereg'}


def build():
    rows = []
    for fn in (load_19e, load_probe_gen, load_paraphrase, load_w1):
        try:
            d, src = fn()
        except Exception as e:
            print('  !! 读取失败 %s：%s' % (fn.__name__, str(e)[:160]))
            continue
        for arm, txt in sorted(d.items()):
            if isinstance(txt, str) and len(txt) > 10:
                rows.append(feats(txt, arm, src))
        print('  %-32s 读入 %2d 臂' % (src, len(d)))
    return rows


def selftest(rows):
    print('\n=== --selftest：逐臂比对切分与标签 ===')
    bad = 0
    seen = set()
    for r in rows:
        k = None
        for slug, pref in SRC_KEY.items():
            if r['source'].startswith(pref):
                k = (slug, r['arm'])
        if k is None or k not in GOLDEN:
            bad += 1
            print('  FAIL 无黄金标注：%s / %s（新增臂须先人工核对再登记）' % (r['source'], r['arm']))
            continue
        seen.add(k)
        got = [set(c['types']) for c in r['clauses']]
        want = GOLDEN[k]
        if len(got) != len(want) or any(g != w for g, w in zip(got, want)):
            bad += 1
            print('  FAIL %s / %s' % k)
            for i in range(max(len(got), len(want))):
                g = sorted(got[i]) if i < len(got) else None
                w = sorted(want[i]) if i < len(want) else None
                mark = '  ' if g == w else '<<'
                txt = r['clauses'][i]['text'][:64] if i < len(r['clauses']) else ''
                print('    %s [%d] want=%-32s got=%-32s %s' % (mark, i, w, g, txt))
        else:
            print('  ok   %-18s %d 条款' % (r['arm'], len(got)))
    for k in GOLDEN:
        if k not in seen:
            bad += 1
            print('  FAIL 黄金标注中的 %s / %s 没有被加载到' % k)
    exp = experiment_arms()
    have = {r['arm'] for r in rows}
    miss = sorted(exp - have)
    print('  实验目录出现 %d 个臂；特征表未覆盖：%s' % (len(exp), miss if miss else '无'))
    print('\n  %s（%d 处不符）' % ('SELFTEST_OK' if bad == 0 else 'SELFTEST_FAIL', bad))
    return 1 if bad else 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default=os.path.join(W, 'prompt_features.json'))
    ap.add_argument('--dump', action='store_true')
    ap.add_argument('--selftest', action='store_true')
    a = ap.parse_args()
    print('=== 读取提示词 ===')
    rows = build()
    print('\n=== 条款级特征表（%d 条） ===' % len(rows))
    hdr = ['arm', 'src', '条款', '字符', 'TASK', 'ENUM', 'ABST', 'ZERO', 'FMT', '契约型', '零值']
    print('  ' + ' '.join('%-8s' % h for h in hdr))
    for r in sorted(rows, key=lambda x: (x['source'], x['arm'])):
        print('  %-8s %-8s %4d %4d %4d %4d %4d %4d %4d %-7s %-4s' % (
            r['arm'][:8], r['source'][:8], r['n_clauses'], r['chars'],
            r['n_TASK'], r['n_ENUM'], r['n_ABSTAIN_PERMIT'], r['n_ZERO_FORBID'],
            r['n_FORMAT'], r['contract_kind'], r['mentions_zero']))
    if a.dump:
        print('\n=== --dump：逐条切分 ===')
        for r in sorted(rows, key=lambda x: (x['source'], x['arm'])):
            print('\n[%s] %s' % (r['source'], r['arm']))
            for i, c in enumerate(r['clauses']):
                print('   %2d %-30s %s' % (i, ','.join(c['types']) or '-', c['text']))
    io.open(a.out, 'w', encoding='utf-8', newline='\n').write(
        json.dumps(rows, ensure_ascii=False, indent=1) + '\n')
    print('\n已写 %s' % a.out)
    if a.selftest:
        return selftest(rows)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
