# -*- coding: utf-8 -*-
"""gen_m40_wilson.py —— 给 M.40 的**逐构建表**每个率格配 Wilson 95% 区间（零格与非零格同一把尺子）。

## 为什么（多条预注册条款的 D1d）
M.40 的逐构建表原先**只给零格**加 `≤x%` 上界（如 `0.0% (≤1.6%)`），而非零格（如 `24.6%`、`43.7%`，
n=199）**裸报**。这与本稿自订规则不一致：非零池有它自己的 $n$ 与抽样误差，一边给界一边不给，
会读成"两边用了两套标准"。本器把**每一格**都算上区间，并把区间一并冻结（门禁只认冻结件里的值）。

## 口径
* 数据源只用冻结件：`ea2_contrast_result.json`（按 raw-match 分类的逐条件 n 与百分比）。
* 逐构建表的真零行取 **cn 侧**（与表内数值一致，n = 153 × 3 次起服 = 459）；
  非零行取该构建在 **dense / aerial** 池上的 `channel`/`base`（n = 229 / 199）。
* Wilson 95% 双侧区间，公式与 `anchor_m40m41.py` 的 `wilson_hi` **同源**；端点保留 2 位小数
  （否则 0/9180 的上界 0.04% 会塌成 0.0，正好违反"不许把 0 印成精确的 0"）。

用法：python -u gen_m40_wilson.py [--apply]
"""
import hashlib
import io
import json
import os
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
WORK = os.path.dirname(os.path.abspath(__file__))
CON = os.path.join(WORK, 'ea2_contrast_result.json')
OUT = os.path.join(WORK, 'm40_wilson_result.json')

# 表内显示名 ← 冻结件里的构建键
DISP = {'InternVL3_5-8B': 'InternVL3.5-8B',
        'Phi-3.5-vision-instruct': 'Phi-3.5-vision-instruct',
        'Qwen3-VL-32B-Instruct': 'Qwen3-VL-32B-Instruct',
        'gemma3-12b': 'gemma-3-12b',
        'llava-onevision-qwen2-7b-ov': 'LLaVA-OneVision-7B'}
ROWS = [('InternVL3_5-8B', 'true zero (z0easy)', 'z0', 'cn', 'z0easy'),
        ('InternVL3_5-8B', 'true zero (z0hard)', 'z0', 'cn', 'z0hard'),
        ('InternVL3_5-8B', 'non-zero (dense)', 'nz', 'dense', None),
        ('InternVL3_5-8B', 'non-zero (aerial)', 'nz', 'aerial', None),
        ('Phi-3.5-vision-instruct', 'true zero (z0easy)', 'z0', 'cn', 'z0easy'),
        ('Phi-3.5-vision-instruct', 'true zero (z0hard)', 'z0', 'cn', 'z0hard'),
        ('Phi-3.5-vision-instruct', 'non-zero (dense)', 'nz', 'dense', None),
        ('Phi-3.5-vision-instruct', 'non-zero (aerial)', 'nz', 'aerial', None),
        ('Qwen3-VL-32B-Instruct', 'true zero (z0easy)', 'z0', 'cn', 'z0easy'),
        ('Qwen3-VL-32B-Instruct', 'true zero (z0hard)', 'z0', 'cn', 'z0hard'),
        ('gemma3-12b', 'true zero (z0easy)', 'z0', 'cn', 'z0easy'),
        ('gemma3-12b', 'true zero (z0hard)', 'z0', 'cn', 'z0hard'),
        ('gemma3-12b', 'non-zero (dense)', 'nz', 'dense', None),
        ('gemma3-12b', 'non-zero (aerial)', 'nz', 'aerial', None),
        ('llava-onevision-qwen2-7b-ov', 'true zero (z0easy)', 'z0', 'cn', 'z0easy'),
        ('llava-onevision-qwen2-7b-ov', 'true zero (z0hard)', 'z0', 'cn', 'z0hard'),
        ('llava-onevision-qwen2-7b-ov', 'non-zero (dense)', 'nz', 'dense', None),
        ('llava-onevision-qwen2-7b-ov', 'non-zero (aerial)', 'nz', 'aerial', None)]


def wilson(k, n, z=1.959964):
    if not n:
        return (0.0, 0.0)
    p = k / float(n)
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    h = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5)
    return (round(100.0 * max(0.0, (c - h) / d), 2), round(100.0 * min(1.0, (c + h) / d), 2))


def main():
    apply = '--apply' in sys.argv
    con = json.loads(io.open(CON, encoding='utf-8').read())
    out = dict(purpose='M.40 逐构建表每格的 Wilson 95% 区间（零格与非零格同一把尺子）',
               source='ea2_contrast_result.json（raw-match 口径）；真零行取 cn 侧，非零行取 dense/aerial 池',
               rows=[])
    print('=' * 118)
    print('■ M.40 逐构建表：每格 Wilson 95% 区间')
    print('=' * 118)
    print('%-26s %-20s %-22s %-22s %-22s' % ('build', 'pool', 'channel→no_people', 'channel→cannot_judge', 'base answers 0'))
    md = ['| build | pool | `channel` → `no_people` | `channel` → `cannot_judge` | `base` answers `0` |',
          '|---|---|---|---|---|']
    for model, pool, side, a, b in ROWS:
        if side == 'z0':
            key = '%s|%s|%s|' % (model, a, b)
            rec_c = con['z0'][key + 'channel']
            rec_b = con['z0'][key + 'base']
        else:
            key = '%s|%s|' % (model, a)
            rec_c = con['nonzero'][key + 'channel']
            rec_b = con['nonzero'][key + 'base']
        n = rec_c['n']
        cells = []
        for rec, kk in ((rec_c, 'no_people'), (rec_c, 'cannot_judge'), (rec_b, 'zero')):
            p = rec['pct'][kk]
            cnt = round(p * rec['n'] / 100.0)
            lo, hi = wilson(cnt, rec['n'])
            cells.append((kk, rec['n'], cnt, p, lo, hi))
        fmt = lambda c: ('**%.1f%%** [%.2f, %.2f]' % (c[3], c[4], c[5])) if c[6 - 1] is not None else ''
        # no_people 加粗（与表内原样式一致）
        def cell(c, bold=False):
            s = '%.1f%% [%.2f, %.2f]' % (c[3], c[4], c[5])
            return ('**%s**' % s) if bold else s
        out['rows'].append(dict(model=DISP[model], pool=pool,
                                n_people=cells[0][1], no_people=cells[0][3], no_people_ci=[cells[0][4], cells[0][5]],
                                cannot_judge=cells[1][3], cannot_judge_ci=[cells[1][4], cells[1][5]],
                                base_zero=cells[2][3], base_zero_ci=[cells[2][4], cells[2][5]],
                                base_n=cells[2][1]))
        print('%-26s %-20s %-22s %-22s %-22s' % (DISP[model], pool, cell(cells[0], True), cell(cells[1]),
                                                 cell(cells[2], cells[2][3] == 0.0)))
        md.append('| %s | %s | %s | %s | %s |' % (DISP[model], pool, cell(cells[0], True), cell(cells[1]),
                                                 cell(cells[2], cells[2][3] == 0.0)))
    out['markdown'] = '\n'.join(md)
    print('\n' + out['markdown'])
    if apply:
        io.open(OUT, 'w', encoding='utf-8', newline='\n').write(json.dumps(out, ensure_ascii=False, indent=2))
        h = hashlib.md5(io.open(OUT, 'rb').read()).hexdigest()
        io.open(OUT + '.md5', 'w', encoding='utf-8', newline='\n').write(
            '%s  %s  (gen_m40_wilson.py)\n' % (h, os.path.basename(OUT)))
        print('\n已冻结 %s（md5 %s）' % (os.path.basename(OUT), h[:12]))
    else:
        print('\n（未写盘；加 --apply 冻结）')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
