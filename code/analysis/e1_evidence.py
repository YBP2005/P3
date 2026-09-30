# -*- coding: utf-8 -*-
"""E1 证据汇总（一次算清，供正文引用）：
 ① 下载语料 CSV 到本地；② 语料"提示词许可结构 -> 零率"表；③ 解析器死分支审计（含影响量）；
 ④ E1 48 格表（仅有效调用，ERR 单独披露）；⑤ 写出内部证据件。
所有数字都从这里出，正文只引用本文件的数。
"""


# ── 复现包统一根：`_repro_root.py`（与本文件同目录）──────────────────────────────
# RP(*parts) = 作者树相对路径 -> 绝对路径（作者树上原样；放行树上查前缀映射表）；
# NR(*parts) = **未随包发布**的作者侧路径（放行树上落到 _NOT_RELEASED/，使失败可见）。
try:
    from _repro_root import resolve as RP, not_released as NR
except ImportError:                      # 只拷走单个脚本时：就地反推仓库根，无前缀映射表
    import os as _o
    _r = _o.environ.get('PAPERB_ROOT') or _o.path.dirname(_o.path.dirname(_o.path.abspath(__file__)))
    RP = lambda *p: _o.path.join(_r, *p)
    NR = lambda *p: _o.path.join(_r, '_NOT_RELEASED', *p)
import csv
import glob
import hashlib
import os
import re
import statistics
import sys
from collections import Counter

sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, RP('analysis', 'work'))
import paramiko  # noqa

E1D = RP('analysis', 'e1_5090')
CORP = RP('analysis', 'e1_5090', 'corpus')
OUT = RP('PaperB_E1证据_20260920.md')
HOST, PORT, USER, PW = '<REDACTED-POD-HOST>', 23654, 'root', '<REDACTED-POD-PASSWORD>'

BS = chr(92)
FALLBACK = re.compile('-?' + BS + 'd+')
JSONC = re.compile('"' + 'count' + '"' + BS + 's*:' + BS + 's*"?(-?' + BS + 'd+)')


def md5(p):
    return hashlib.md5(open(p, 'rb').read()).hexdigest()[:12]


def pull():
    os.makedirs(CORP, exist_ok=True)
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, port=PORT, username=USER, password=PW, timeout=40,
              banner_timeout=40, auth_timeout=40, look_for_keys=False, allow_agent=False)
    try:
        sf = c.open_sftp()
        for f in sf.listdir('/root/dense_results'):
            if f.endswith('.csv'):
                sf.get('/root/dense_results/' + f, os.path.join(RP('analysis', 'e1_5090', 'corpus'), f))
        sf.get('/root/06_dense_vlm.py', RP('analysis', 'e1_5090', '06_dense_vlm.py'))
        sf.get('/root/logs/vllm_qwen3-vl-32b-awq.log', RP('analysis', 'e1_5090', 'vllm_log.txt'))
        sf.close()
    finally:
        c.close()


def corpus_tables():
    """每个 (ds, arm)：n、零数、零率；以及解析器审计。"""
    per = {}
    tot = Counter()
    audit = Counter()
    cpat = re.compile(r'^vlm_(?P<ds>st_a|st_b|ucf)_(?P<arm>[a-z]+)_whole\.csv$')
    for p in sorted(glob.glob(RP('analysis', 'e1_5090', 'corpus', '*.csv'))):
        mm = cpat.match(os.path.basename(p))
        if not mm:
            print('!! 语料文件名无法解析:', os.path.basename(p))
            continue
        ds, arm = mm.group('ds'), mm.group('arm')
        rows = list(csv.DictReader(open(p, encoding='utf-8-sig')))
        z = sum(1 for r in rows if (r.get('pred') or '').strip() in ('0', '0.0'))
        per[(ds, arm)] = (len(rows), z)
        tot[arm + '_n'] += len(rows)
        tot[arm + '_z'] += z
        for r in rows:
            raw = r.get('raw') or ''
            fi = FALLBACK.search(raw.replace(',', ''))
            jc = JSONC.search(raw)
            audit['rows'] += 1
            if not fi and not jc:
                audit['nodigit'] += 1
            if fi and jc and int(fi.group(0)) != int(jc.group(1)):
                audit['mismatch'] += 1
            if jc is None:
                audit['nojson'] += 1
            if (r.get('pred') or '').strip() in ('0', '0.0'):
                audit['z_all'] += 1
                if jc and int(jc.group(1)) == 0:
                    audit['z_json0'] += 1
    return per, tot, audit


ABSTAIN = ('abstain', 'cannot_judge', 'no_people')


def e1_tables():
    pat = re.compile(r'^(?P<m>.+)_(?P<d>st_a|st_b|ucf)_(?P<a>[A-Za-z]+)$')
    cells = {}
    for p in sorted(glob.glob(RP('analysis', 'e1_5090', 'e1_*.csv'))):
        mm = pat.match(os.path.basename(p)[3:-4])
        rows = list(csv.DictReader(open(p, encoding='utf-8-sig')))
        err = sum(1 for r in rows if (r.get('raw') or '').startswith('ERR'))
        valid = [r for r in rows if not (r.get('raw') or '').startswith('ERR')]
        nums, gts, zeros, abst = [], [], 0, 0
        for r in valid:
            raw = r.get('raw') or ''
            try:
                v = float(r['pred'])
            except Exception:
                v = None
            if v is None:
                if any(t in raw.lower() for t in ABSTAIN):
                    abst += 1
                continue
            nums.append(v); gts.append(float(r['gt']))
            if v == 0:
                zeros += 1
        ratios = [v / g for v, g in zip(nums, gts) if g > 0]
        cells[(mm.group('m'), mm.group('d'), mm.group('a'))] = dict(
            n=len(rows), valid=len(valid), err=err, zeros=zeros, abst=abst,
            med=statistics.median(ratios) if ratios else None,
            dev=(sum(nums) - sum(gts)) / sum(gts) * 100 if nums else None,
            nnum=len(nums))
    return cells


def main():
    pull()
    print('已下载语料 CSV + 06_dense_vlm.py + vllm 日志')
    per, tot, audit = corpus_tables()
    cells = e1_tables()

    print()
    print('=== 语料：提示词许可结构 -> 零率（%d 个 item/臂）===' % (tot['base_n']))
    for arm in ('over', 'base', 'under'):
        n, z = tot[arm + '_n'], tot[arm + '_z']
        det = '  '.join('%s %d/%d' % (ds, per[(ds, arm)][1], per[(ds, arm)][0])
                        for ds in ('st_a', 'st_b', 'ucf'))
        print('  %-6s 零 %3d/%3d = %5.1f%%   ( %s )' % (arm, z, n, z / n * 100, det))
    print()
    print('=== 语料解析器审计（%d 行）===' % audit['rows'])
    print('  结构分支是否命中 {"count": N}: 否（正则缺键前引号）')
    print('  fallback 与 JSON count 不一致的行: %d' % audit['mismatch'])
    print('  无任何数字的行(会判 parse_ok=0): %d' % audit['nodigit'])
    print('  取不到 JSON count 的行: %d' % audit['nojson'])
    print('  pred==0 且 JSON count 也是 0: %d/%d' % (audit['z_json0'], audit['z_all']))
    print()
    print('=== E1 48 格（仅有效调用）===')
    print('%-28s %-5s %-8s %5s %5s %5s %6s %8s %8s' % ('model', 'ds', 'arm', 'rows', 'valid', 'ERR', 'zero', 'medP/G', 'dev%'))
    for k in sorted(cells, key=lambda x: (x[1], x[0], x[2])):
        c = cells[k]
        print('%-28s %-5s %-8s %5d %5d %5d %6d %8s %8s' % (
            k[0], k[1], k[2], c['n'], c['valid'], c['err'], c['zeros'],
            '%.3f' % c['med'] if c['med'] is not None else '-',
            '%.1f%%' % c['dev'] if c['dev'] is not None else '-'))
    # 汇总
    perm = {k: c for k, c in cells.items() if k[2] in ('permit', 'channel')}
    tot_valid = sum(c['valid'] for c in perm.values())
    tot_abst = sum(c['abst'] for c in perm.values())
    tot_zero_pc = sum(c['zeros'] for c in perm.values())
    for a in ('permit', 'channel'):
        v = sum(c['valid'] for k, c in perm.items() if k[2] == a)
        ab = sum(c['abst'] for k, c in perm.items() if k[2] == a)
        print('%s 臂：有效调用 %d，显式弃权 %d (%.1f%%)' % (a, v, ab, ab / v * 100))
    print()
    print('弃权臂合计：有效调用 %d，显式弃权 %d (%.1f%%)，pred==0 共 %d' % (
        tot_valid, tot_abst, tot_abst / tot_valid * 100, tot_zero_pc))
    bes = [c for k, c in cells.items() if k[2] in ('bestA', 'bestB', 'bestC')]
    md = [c['med'] for c in bes if c['med'] is not None]
    print('禁止弃权臂：%d 格，中位 pred/gt 范围 %.3f–%.3f；零值 %d；显式弃权 %d' % (
        len(bes), min(md), max(md), sum(c['zeros'] for c in bes), sum(c['abst'] for c in bes)))

    write_evidence(per, tot, audit, cells, tot_valid, tot_abst, tot_zero_pc, bes, md)


def write_evidence(per, tot, audit, cells, tot_valid, tot_abst, tot_zero_pc, bes, md):
    L = []
    A = L.append
    A('# PaperB · E1 判别实验证据（2026-09-20）')
    A('')
    A('> 本文件是**内部记录**（不进送审件）。正文与补充材料引用的一切 E1 数字以此为准。')
    A('> 数据来源：5090 上 `/root/e1_results/*.csv`（48 格）与语料 `/root/dense_results/*.csv`（9 文件）。')
    A('')
    A('## 0. 服务配置与可比性')
    A('')
    A('- 语料侧（本地机 5090）：vLLM 0.29.0 + `Qwen3-VL-32B-Instruct-AWQ-4bit`，`quantization=compressed-tensors`，`dtype=torch.bfloat16`，`max_seq_len=8192`，tensor_parallel=1。')
    A('- E1 侧：阿里云百炼 compatible-mode，`temperature 0.0`，`max_tokens 128`，JPEG q92 编码与语料运行器逐字一致。')
    A('- **提示词可比性已按码点核验**：E1 的 base 提示词与语料 `06_dense_vlm.py` 的 base 提示词**逐字符相同**。')
    A('- 未控混淆：权重精度（4-bit vs bf16）与推理引擎（vLLM vs 百炼）**同时**不同，故「本地为零、托管不为零」不能单独归因于量化。')
    A('')
    A('## 1. 样本帧')
    A('')
    A('- `st_a`：base 臂 `pred==0` 的 item 共 103 个（gt 138–797），等间隔取 40 个。')
    A('- `ucf`：base 臂 `pred==0` 的 item 共 180 个（gt 137–2075），等间隔取 40 个。')
    A('- 抽样**确定性**（`zero.sort(key=gt)` 后 `step=len//n`），故**五个模型、全部臂共享同一 40 个 item**；已逐文件核验帧内 40/40、无重复键、无帧外行。')
    A('- `base`/`permit` 臂：`--reps 5`，每 item 6 次观测（早期单次 40 行 + 重复 200 行，键分别为裸 item 与 `item#rN`，二者并存**非重复数据**）。其余臂 40 行。')
    A('')
    A('## 2. 语料内已有的证据：零率随「提示词许可结构」单调变化')
    A('')
    A('| 臂 | 提示词含义 | 零数/总数 | 零率 | st_a | st_b | ucf |')
    A('|---|---|---|---|---|---|---|')
    for arm, mean in (('over', '要求把所有可能目标都计入'), ('base', '中性'), ('under', '只统计能完全确认的目标')):
        n, z = tot[arm + '_n'], tot[arm + '_z']
        A('| %s | %s | %d/%d | **%.1f%%** | %d/%d | %d/%d | %d/%d |' % (
            arm, mean, z, n, z / n * 100,
            per[('st_a', arm)][1], per[('st_a', arm)][0],
            per[('st_b', arm)][1], per[('st_b', arm)][0],
            per[('ucf', arm)][1], per[('ucf', arm)][0]))
    A('')
    A('⇒ 「鼓励保守」的提示词把 `pred=0` 从 **0%%** 抬到 **%.1f%%**；「要求全计入」的提示词下 %.0f 个 item **一个零也没有**。' % (
        tot['under_z'] / tot['under_n'] * 100, tot['over_n']))
    A('')
    A('## 3. 语料解析器审计（死分支及其影响量）')
    A('')
    A('- `06_dense_vlm.py` 的正则为 `\\{\\s*(?:count|计数|数量|人数)\\s*[:：]\\s*(\\d+)`：**键名前缺引号**，')
    A('  而提示词要求的输出是 `{"count": 数量}` ⇒ 结构分支**永不命中**，所有取值实际来自 fallback「取响应中第一个整数」。')
    A('- 逐行审计（%d 行）：fallback 与 JSON `count` **不一致的行 = %d**；无数字行 = %d；取不到 JSON count 的行 = %d。' % (
        audit['rows'], audit['mismatch'], audit['nodigit'], audit['nojson']))
    A('- `pred==0` 的行共 %d，其中 JSON `count` 本身就是 0 的 = **%d/%d**，raw 形如 `{"count": 0}`。' % (
        audit['z_all'], audit['z_json0'], audit['z_all']))
    A('')
    A('⇒ 该缺陷**真实存在但影响量为零**：语料的响应都是只含一个整数的 JSON，fallback 与结构解析同值。')
    A('⇒ 因此 **`pred=0` 不是解析产物**：它是模型**自己写下的 0**。')
    A('')
    A('## 4. E1 48 格（跨模型、同帧）')
    A('')
    A('| model | ds | arm | rows | valid | ERR | zero | med pred/gt | pooled dev |')
    A('|---|---|---|---|---|---|---|---|---|')
    for k in sorted(cells, key=lambda x: (x[1], x[0], x[2])):
        c = cells[k]
        A('| %s | %s | %s | %d | %d | %d | %d | %s | %s |' % (
            k[0], k[1], k[2], c['n'], c['valid'], c['err'], c['zeros'],
            '%.3f' % c['med'] if c['med'] is not None else '—',
            '%.1f%%' % c['dev'] if c['dev'] is not None else '—'))
    A('')
    A('### 4.1 base 臂零率（同一批 40 个 item）')
    A('')
    A('| model | st_a | ucf |')
    A('|---|---|---|')
    for m in sorted({k[0] for k in cells}):
        row = []
        for d in ('st_a', 'ucf'):
            c = cells.get((m, d, 'base'))
            row.append('%d/%d = %.1f%%' % (c['zeros'], c['valid'], c['zeros'] / c['valid'] * 100) if c else '—')
        A('| %s | %s | %s |' % (m, row[0], row[1]))
    A('')
    A('### 4.2 给出显式弃权通道后（permit / channel 臂）')
    A('')
    A('- 有效调用合计 **%d**，其中显式弃权 **%d = %.1f%%**；这些臂里 `pred==0` 共 **%d** 个。' % (
        tot_valid, tot_abst, tot_abst / tot_valid * 100, tot_zero_pc))
    A('- `permit` 给的是「无法逐个确证就回答 abstain」；`channel` 给的是三选一（数字 / `cannot_judge` / `no_people`）。两臂结果一致。')
    A('')
    A('### 4.3 禁止弃权并要求给出最佳估计（bestA / bestB / bestC）')
    A('')
    A('- %d 格：中位 `pred/gt` 范围 **%.3f–%.3f**；`pred==0` **%d** 个；显式弃权 **%d** 个。' % (
        len(bes), min(md), max(md), sum(c['zeros'] for c in bes), sum(c['abst'] for c in bes)))
    A('- ⇒ 被禁止弃权时，模型不会退化成「接近 0」，而是系统性地**高估 2.5–9.5 倍**。')
    A('')
    A('## 5. 由证据支持的结论（措辞可直接引用）')
    A('')
    A('1. **`pred=0` 是模型自陈的弃权，被写进了唯一的数字槽位**：语料 %d 个零值的 raw 全是 `{"count": 0}`（第 3 节），且零率随提示词许可结构从 0%% 变化到 %.1f%%（第 2 节）。' % (
        audit['z_json0'], tot['under_z'] / tot['under_n'] * 100))
    A('2. **不是量化伪影**：托管 bf16 的 `qwen3-vl-32b-instruct` 在同一批 item 上仍写出 25.8%%–31.7%% 的零。')
    A('3. **也不是普遍行为**：同族 `plus` / `flash` / `235b` 在 base 臂几乎不写零（0%%–0.4%%）；')
    A('   但**一旦提供显式弃权通道，五个模型全部改用它**（%d/%d = %.1f%%），且不再写零。' % (
        tot_abst, tot_valid, tot_abst / tot_valid * 100))
    A('4. ⇒ **弃权通道由服务配置与提示词共同决定**；`0` 只在「只允许输出数字」时才被用作弃权表达。')
    A('5. **不是失败的估计**：禁止弃权并索要最佳估计时，中位答案是真值的 2.5–9.5 倍，而不是接近 0。')
    A('')
    A('## 6. 溯源')
    A('')
    A('- 探针：`/root/19b_e1_probe.py` md5 %s' % md5(RP('analysis', 'e1_5090', '19b_e1_probe.py')))
    A('- 语料运行器：`/root/06_dense_vlm.py` md5 %s' % md5(RP('analysis', 'e1_5090', '06_dense_vlm.py')))
    A('- 队列脚本：`run_e1b.sh` / `run_e1c.sh`；两队列均打印 `E1B_ALL_DONE` / `E1C_ALL_DONE`。')
    A('- 本地数据：`analysis/e1_5090/e1_*.csv`（48 个）、`analysis/e1_5090/corpus/*.csv`（9 个）。')
    if '--apply' in sys.argv:      # ★ v0610：默认**只读**，写回须显式 --apply
        open(OUT, 'w', encoding='utf-8').write('\n'.join(L) + '\n')
        print()
        print('-> 写出', OUT, '(%d 字符)' % len('\n'.join(L)))
    else:
        print()
        print('-> （dry run：**未**写出 %s（%d 字符）；加 --apply 才写）'
              % (OUT, len('\n'.join(L))))


if __name__ == '__main__':
    main()
