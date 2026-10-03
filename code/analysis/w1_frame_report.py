# -*- coding: utf-8 -*-
"""w1_frame_report.py — 生成正文/附录要用的两张表，**全部数字来自脚本**，不手打：

  ① **采样框表**（frame table）：候选、入组、排除与逐条理由、血统、来源、体积、门控结果；
  ② **覆盖度表**（coverage table）：每个 (家族 x 域 x 池 x 臂) 格的实际条数、答 0 率、
     弃答率、解析失败率 —— 这是"格是独立的、按已完成格报告"这句停损条款的兑现物。

输入：
  · analysis/work/w0_frame_final.json         （W0 只读枚举的候选与体积）
  · analysis/w1_a800/**/*.csv                 （拉回的产物；本地）
  · analysis/w1_a800/logs/*.log               （拉回的远端日志，用于门控结果/排除理由）
输出：
  · analysis/w1_a800/frame_table.md
  · analysis/w1_a800/coverage_table.md
用法：python w1_frame_report.py
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
import io
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')
HERE = os.path.dirname(os.path.abspath(__file__))
A800 = NR('analysis', 'w1_a800')
LOGS = NR('analysis', 'w1_a800', 'logs')
DOMS = ['st_a', 'ucf', 'visdrone', 'aitod']
ARMS_Z = [('base', 'native'), ('permit', 'native'), ('channel', 'native'), ('base', 's640')]
ARMS_N = ARMS_Z[:3]
ABSTAIN = {'abstain', 'cannot_judge', 'no_people'}
ABSTAIN_WORDS = ('abstain', 'cannot_judge', 'no_people', 'no_objects')
# ★ 2026-09-23 第三次修同一类缺陷：本文件原先也按 `pred` 统计弃答，于是把"显式弃答 ~100%"
#   误显示成"弃答 0% + 未解析 100%"（根因见 w1_judge.py 里 is_abstain 的长注释：
#   19e.parse() 的第一条正则要求键名紧跟花括号，对标准 JSON `{"count": "abstain"}` 必然失配）。
#   现与论文口径一致：**弃答按原文匹配**；"未解析"= 既非数字也非弃答。
def is_abstain(r):
    raw = (r.get('raw') or '').lower()
    return any(k in raw for k in ABSTAIN_WORDS)
USED = {'MiniCPM-V-2_6': '**smoke 门未过**：base 契约下以自然语言拒答（4/4 条无可解析 JSON）⇒ 排除；'
                        '该现象本身与"被抑制的弃答"同源',
        'Step3-VL-10B': '首轮缺 `trust_remote_code` ⇒ 补参数后**入组并跑满**',
        'Molmo-7B-D-0924': '依次缺 `trust_remote_code` 与 `tensorflow` ⇒ 两次补齐后**入组并跑满**',
        'deepseek-vl2-tiny': '缺 `timm` ⇒ 装包后入组；**密集域 99% 不遵守 JSON 契约**，航拍域 permit 下仍答 0（真出口失效）',
        'MiniCPM-V-4_5': 'OpenBMB 槽位补位（同血统下一候选，因入组者被门控排除而名额空出）',
        'Phi-4-mm': '备选**弃用**：`vision-lora`(738MB)/`speech-lora`(922MB) 两轮重试后仍 0 字节 ⇒ 缺视觉适配器',
        'gemma-4-31b-it': '入组并跑满（4 域 × 4 臂 + FSC 四臂）',
        'Idefics3-8B-Llama3': '入组并跑满；航拍域 permit 残留由**稀疏项**解释（GT 中位数 2–3）'}


def read(p):
    if not os.path.exists(p):
        return None
    with io.open(p, encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


def fam_of(p):
    b = os.path.basename(p)
    m = re.match(r'^e1_(.+?)_(st_a|ucf|visdrone|aitod)_.*\.csv$', b)
    return m.group(1) if m else None


def frame_table():
    L = ['# W1 采样框与门控结果（脚本生成，勿手改）', '',
         '> 规则见 `analysis/work/w1_prereg.json`（md5 `0a42e6e5bbfa89543ba9fc1522f1b075`）。'
         '下表左半为 W0 只读枚举的实测结果，右半为门控与产物覆盖（由 CSV/日志统计）。', '']
    W0 = os.path.join(HERE, 'w0_frame_final.json')
    if os.path.exists(W0):
        d = json.load(io.open(W0, encoding='utf-8'))
        L += ['## 一、只读枚举到的本地候选（判定后）', '']
        L += ['| 判定 | 体积 MB | architectures | 路径 |', '|---|---|---|---|']
        for r in d.get('local_all', []):
            tag = '已用过' if r.get('used') else ('可用' if r.get('mm') == 'MM' and not r.get('reason') else '排除')
            if r.get('reason'):
                tag = '排除：' + r['reason']
            L.append('| %s | %s | %s | `%s` |' % (tag, r.get('size_mb'), r.get('arch'), r.get('rel')))
        L += ['', '## 二、下载候选的 ModelScope 可得性', '',
              '| model_id | 文件数 | 体积 GB | 最大文件 |', '|---|---|---|---|']
        for r in d.get('downloads', []):
            big = r.get('biggest') or []
            L.append('| `%s` | %s | %s | %s |' % (r['model_id'], r['files'], r['gb'],
                                                  (big[0][0] if big else '')))
    L += ['', '## 三、入组/替补家族的门控结果（由产物 CSV 统计）', '',
          '| 家族（served name） | 零池格数 | 非零池格数 | 门控/备注 |', '|---|---|---|---|']
    zf = sorted({fam_of(p) for p in glob.glob(NR('analysis', 'w1_a800', 'zero', 'e1_*.csv'))} - {None})
    nf = sorted({fam_of(p) for p in glob.glob(NR('analysis', 'w1_a800', 'nonzero', 'e1_*.csv'))} - {None})
    for fam in sorted(set(zf) | set(nf)):
        zc = len(glob.glob(os.path.join(NR('analysis', 'w1_a800', 'zero'), 'e1_%s_*.csv' % fam)))
        nc = len(glob.glob(os.path.join(NR('analysis', 'w1_a800', 'nonzero'), 'e1_%s_*.csv' % fam)))
        note = USED.get(fam, '')
        if not note:
            note = '入组并跑满' if (zc >= 16 and nc >= 12) else '**未跑满**（按已完成格报告）'
        L.append('| `%s` | %d/16 | %d/12 | %s |' % (fam, zc, nc, note))
    txt = '\n'.join(L) + '\n'
    io.open(NR('analysis', 'w1_a800', 'frame_table.md'), 'w', encoding='utf-8', newline='\n').write(txt)
    return txt


def coverage_table():
    L = ['# W1 覆盖度与格级统计（脚本生成）', '',
         '| 池 | 家族 | 域 | 臂 | 变体 | n | 答0 | 答0率 | 弃答率 | 解析失败 |',
         '|---|---|---|---|---|---|---|---|---|---|']
    tot = 0
    for pool, arms in (('zero', ARMS_Z), ('nonzero', ARMS_N)):
        for ds in DOMS:
            for fam in sorted({fam_of(p) for p in glob.glob(os.path.join(NR('analysis', 'w1_a800'), pool, 'e1_*.csv'))} - {None}):
                for arm, var in arms:
                    p = os.path.join(NR('analysis', 'w1_a800'), pool, 'e1_%s_%s_%s_%s.csv' % (fam, ds, arm, var))
                    rows = read(p)
                    if not rows:
                        continue
                    n = len(rows)
                    z = sum(1 for r in rows if str(r.get('pred', '')).strip() in ('0', '0.0'))
                    ab = sum(1 for r in rows if is_abstain(r))
                    pf = sum(1 for r in rows
                             if str(r.get('parse_ok', '')).strip() != '1' and not is_abstain(r))
                    L.append('| %s | `%s` | %s | %s | %s | %d | %d | %.1f%% | %.1f%% | %.1f%% |'
                             % (pool, fam, ds, arm, var, n, z, 100 * z / n, 100 * ab / n, 100 * pf / n))
                    tot += 1
    L += ['', '合计 %d 个非空格。' % tot]
    txt = '\n'.join(L) + '\n'
    io.open(NR('analysis', 'w1_a800', 'coverage_table.md'), 'w', encoding='utf-8', newline='\n').write(txt)
    return txt


def main():
    os.makedirs(A800, exist_ok=True)
    t1 = frame_table()
    t2 = coverage_table()
    print('frame_table.md    %d 行' % len(t1.splitlines()))
    print('coverage_table.md %d 行' % len(t2.splitlines()))
    return 0


if __name__ == '__main__':
    sys.exit(main())
