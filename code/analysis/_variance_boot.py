# -*- coding: utf-8 -*-
"""_variance_boot.py —— 给 M.18.8 的两因素方差分解补 **item 级 bootstrap 区间**（多条在册条目。

## 为什么
在册条目要"给 M.18.8 方差分解**补 bootstrap 区间**并进主稿"。现有点估计是
域 38.7% / 构建 33.9% / 交互 27.4%，**没有区间** ⇒ 无法判断"构建占主导"这一判定是否稳。
另有多家（多条在册条目）提"区间只是下界/未传播"（主题 T3，本轮真恶化 +12.5）——补区间同时打在 T3 上。

## 口径（与 `variance_decomp.py` **逐字同源**）
5 构建（同一份 Qwen3-VL-32B 权重的 5 种部署）× 4 域 = 20 格平衡设计；因变量 = 该格在**公共 item 子集**上的
答 0 率（%）；分解 = 经典两因素平方和占比（构建 / 域 / 交互残差）。
**bootstrap 取 item 级重采样**：每个域内**同一次抽样的下标用于该域的全部 5 个构建**
（因为 5 个构建跑的是同一批 item，这正是配对设计的来源），再重算 20 格 → 重算三个占比。
产物：`variance_boot_result.json`（+ .md5）。用法：python -u _variance_boot.py
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
import hashlib
import io
import json
import os
import random
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
E2 = RP('analysis', 'e2_newh20')
OUT = RP('analysis', 'work', 'variance_boot_result.json')
BUILDS = [('qwen3-vl-32b-awq', 'AWQ-4bit'), ('qwen3-vl-32b-awq8', 'AWQ-8bit'),
          ('qwen3-vl-32b-bf16', 'BF16'), ('qwen3-vl-32b-fp8', 'FP8'),
          ('qwen3-vl-32b-gptq', 'GPTQ-W4')]
DOMS = ['st_a', 'ucf', 'visdrone', 'aitod']
NBOOT, SEED = 2000, 20260924


def rows_of(model, ds, arm='base'):
    p = os.path.join(RP('analysis', 'e2_newh20'), 'e1_%s_%s_%s.csv' % (model, ds, arm))
    if not os.path.exists(p):
        return None
    with io.open(p, encoding='utf-8-sig') as f:
        return [r for r in csv.DictReader(f) if '#r' not in str(r.get('item') or '')]


def shares(mat):
    """mat: 5×4 的率矩阵（%）→ 三个平方和占比。"""
    a, b = len(mat), len(mat[0])
    vals = [v for row in mat for v in row]
    gm = sum(vals) / len(vals)
    ss_b = b * sum((sum(row) / b - gm) ** 2 for row in mat)
    ss_d = a * sum((sum(mat[i][j] for i in range(a)) / a - gm) ** 2 for j in range(b))
    ss_t = sum((v - gm) ** 2 for v in vals)
    ss_r = ss_t - ss_b - ss_d
    return [ss_b / ss_t, ss_d / ss_t, ss_r / ss_t]


def main():
    # 逐 (构建, 域) 的逐 item 真假数组 + 公共 item 子集
    raw, keys = {}, {}
    for ds in DOMS:
        sets = []
        for m, _ in BUILDS:
            rr = rows_of(m, ds)
            if rr is not None:
                raw[(m, ds)] = {r['item']: str(r.get('pred') or '').strip() in ('0', '0.0') for r in rr}
                sets.append(set(raw[(m, ds)]))
        keys[ds] = sorted(set.intersection(*sets)) if sets else []
    print('公共 item 子集：%s' % {ds: len(keys[ds]) for ds in DOMS})

    Z = {}          # (label, ds) -> 该域公共 item 上的 0/1 序列
    for m, label in BUILDS:
        for ds in DOMS:
            Z[(label, ds)] = [1.0 if raw[(m, ds)][it] else 0.0 for it in keys[ds]]
    point = [[100.0 * sum(Z[(l, ds)]) / len(keys[ds]) for ds in DOMS] for _, l in BUILDS]
    p_b, p_d, p_r = shares(point)
    print('\n点估计：构建 %.1f%% ｜ 域 %.1f%% ｜ 交互/残差 %.1f%%'
          % (100 * p_b, 100 * p_d, 100 * p_r))

    rnd = random.Random(SEED)
    bs = []
    for _ in range(NBOOT):
        idx = {ds: [rnd.randrange(len(keys[ds])) for _ in range(len(keys[ds]))] for ds in DOMS}
        mat = []
        for _, l in BUILDS:
            row = []
            for ds in DOMS:
                z = Z[(l, ds)]
                ix = idx[ds]
                row.append(100.0 * sum(z[i] for i in ix) / len(ix))
            mat.append(row)
        bs.append(shares(mat))
    bs_b = sorted(x[0] for x in bs); bs_d = sorted(x[1] for x in bs); bs_r = sorted(x[2] for x in bs)
    q = lambda v, p: round(100 * v[int(p * len(v))], 1)
    med = lambda v: round(100 * v[len(v) // 2], 1)
    res = dict(purpose='M.18.8 两因素方差分解的 item 级 bootstrap 区间（多条在册条目',
               design='5 构建 × 4 域平衡设计；因变量 = 公共 item 子集上的答 0 率；'
                      'bootstrap = 域内 item 重采样 %d 次（同一域内 5 个构建共用同一下标，保持配对）' % NBOOT,
               common_items={ds: len(keys[ds]) for ds in DOMS},
               point=dict(build=round(100 * p_b, 1), domain=round(100 * p_d, 1), resid=round(100 * p_r, 1)),
               boot=dict(build=[q(bs_b, 0.025), med(bs_b), q(bs_b, 0.975)],
                         domain=[q(bs_d, 0.025), med(bs_d), q(bs_d, 0.975)],
                         resid=[q(bs_r, 0.025), med(bs_r), q(bs_r, 0.975)]),
               p_build_ge_domain=round(sum(1 for x in bs if x[0] >= x[1]) / len(bs), 3),
               n_boot=NBOOT)
    print('\nbootstrap（%d 次）：' % NBOOT)
    print('  构建占比 点估计 %.1f%%  95%% 区间 [%.1f, %.1f]（中位 %.1f）'
          % (res['point']['build'], res['boot']['build'][0], res['boot']['build'][2], res['boot']['build'][1]))
    print('  域占比   点估计 %.1f%%  95%% 区间 [%.1f, %.1f]（中位 %.1f）'
          % (res['point']['domain'], res['boot']['domain'][0], res['boot']['domain'][2], res['boot']['domain'][1]))
    print('  交互/残差 点估计 %.1f%%  95%% 区间 [%.1f, %.1f]'
          % (res['point']['resid'], res['boot']['resid'][0], res['boot']['resid'][2]))
    print('  P(构建占比 ≥ 域占比) = %.3f' % res['p_build_ge_domain'])
    io.open(OUT, 'w', encoding='utf-8', newline='\n').write(json.dumps(res, ensure_ascii=False, indent=2))
    h = hashlib.md5(io.open(OUT, 'rb').read()).hexdigest()
    io.open(OUT + '.md5', 'w', encoding='utf-8', newline='\n').write(
        '%s  %s  (_variance_boot.py)\n' % (h, os.path.basename(OUT)))
    print('\n已冻结 %s（md5 %s）' % (os.path.basename(OUT), h[:12]))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
