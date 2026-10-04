# -*- coding: utf-8 -*-
"""p3r2_plan_m37_cluster.py — P3R2 [round]§4（[external-review] #16）：31/36 单元的**按 knob 聚类**置换检验与块 bootstrap。

## 要回答的问题（方案 §4.1）
§7.3 印的排序稳定性 "a label-permutation test gives p<5e-5; leaving out any single knob keeps it
at 0.883-0.970" 在**按 knob（或 knob x 域/构建）聚类**的重采样/置换下，下沿还 >= 0.80 吗？

## 本脚本回答什么、不回答什么
* 只做**重采样结构**的替换（i.i.d. -> 簇级），**不新增任何数据、不跑任何推理**。
* 复现现文（i.i.d. 口径）作为**阴性对照与自证**，再给簇级口径。两部分都报。
* **不改** `m37_ci_power.py`（主稿与 F.7 点名引用它）；只 import 其 `spearman()`。
* **不改任何冻结件**；本脚本只读 `equalcount36_result.json` / `m37_ci_power_result.json`，只写新文件。

## 判据件先于数据
见 `p3r2_plan_m37cluster_criteria_frozen.json`（用本脚本 `--write-criteria` 生成）。
脚本启动时断言该文件的 md5 与本脚本内写死的常量一致 —— 判据不因结果而改。

用法：
  python p3r2_plan_m37_cluster.py --write-criteria   # 只在判据件不存在时生成
  python p3r2_plan_m37_cluster.py --check            # 干跑：只跑自证与阴性对照，不写结果
  python p3r2_plan_m37_cluster.py                    # 全量，写 result JSON + md5
"""
import argparse
import hashlib
import io
import itertools
import json
import os
import random
import sys
import time

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

W = os.path.dirname(os.path.abspath(__file__))
EQ = os.path.join(W, 'equalcount36_result.json')
M37RES = os.path.join(W, 'm37_ci_power_result.json')
CRIT = os.path.join(W, 'p3r2_plan_m37cluster_criteria_frozen.json')
OUT = os.path.join(W, 'p3r2_plan_m37_cluster_result.json')

# ── 判据件 md5（先跑 --write-criteria 再把打印出来的值粘到这里）──────────────────
CRIT_MD5 = '4cf662f155cf87016ff505dbb426a8b1'

SEED = 20260924          # 与 m37_ci_power.py 同（方案 §4.2 criteria.design）
N_PERM = 20000           # 方案 §4.2 criteria.design
N_BOOT = 2000            # 方案 §4.2 criteria.design
ENUM_CAP = 200000        # 完整枚举空间 <= 此值时用完整枚举（p 可达下限），否则蒙特卡洛

# ── 六个旋钮的**逐条**成员表（写死；由单元名的 knob 前缀机械解析 + 人工核对）──────────
# 单元名形如  '<Family>·<knob> / <variant>'（'·' 是 U+00B7）。
KNOB_OF_PREFIX = {
    'output contract': 'output_contract',
    'pixel budget': 'pixel_budget',
    'prompt family': 'prompt_family',
    'tiling': 'tiling',
    'CSRNet': 'density_regression',
    'official DM-Count': 'density_regression',
    'in-domain(micro)': 'detection_threshold',
    'in-domain': 'detection_threshold',
    'zero-shot COCO': 'detection_threshold',
}
KNOB_ORDER = ['detection_threshold', 'density_regression', 'output_contract',
              'pixel_budget', 'prompt_family', 'tiling']
# 方案 §4.2 criteria.clustering 写死的 31 单元口径规模
EXPECT_31 = {'detection_threshold': 12, 'density_regression': 4, 'output_contract': 2,
             'pixel_budget': 6, 'prompt_family': 6, 'tiling': 1}
# 方案 §4.1 第 2 条：现文 0.883-0.970 是**36 单元**口径、丢的是**9 个朴素子组**
PUBLISHED_LOO_RANGE = [0.883, 0.970]
PUBLISHED_LL = [0.939, 0.996]        # 31@k=4 i.i.d. bootstrap（m37_ci_power_result.quoted_display）
PUBLISHED_36 = [0.836, 0.983]        # 36@k=3 i.i.d. bootstrap
THRESHOLD_LOWER = 0.80               # 方案 §4.2：补材 1154 行 "the 0.8 threshold we would have accepted"

# 三个 deflation（方案 §4.2 criteria.design："三种 deflation 全部跑"）
# 31@k=4 用 span_eq4（现文 0.982/0.983）；36@k=3 用 span_eq（冻结件 ordering 口径 0.932）
DEFLATIONS_31 = [('equal_count_k4', 'span_eq4'), ('drop_high', 'span_drop_high'), ('drop_low', 'span_drop_low')]
DEFLATIONS_36 = [('equal_count_k3', 'span_eq'), ('drop_high', 'span_drop_high'), ('drop_low', 'span_drop_low')]
DEFLATIONS = DEFLATIONS_31          # 兼容旧引用


# ══════════════════════════════════════════════════════════════════════════════
def avg_ranks(v):
    """全局**平均秩**（并列取平均）。★ 这是本脚本唯一的替代统计量所需的秩定义。"""
    n = len(v)
    order = sorted(range(n), key=lambda i: v[i])
    r = [0.0] * n
    i = 0
    while i < n:
        j = i
        while j + 1 < n and v[order[j + 1]] == v[order[i]]:
            j += 1
        avg = (i + j) / 2.0 + 1.0
        for t in range(i, j + 1):
            r[order[t]] = avg
        i = j + 1
    return r


def between_rank_r2(rank_x, rank_y, labels):
    """★ **方案 §4.3 统计量在数学上退化时的替代读数**（必须在报告里明写）。

    退化事实（本脚本自证）：`rho(x, y)` 只依赖 (x_i, y_i) **配对集合**，与单元顺序无关；
    任何"簇标签置换"只改变单元的**顺序/分组**，不改变配对集合 ⇒ 每次置换的 rho 与观测**逐位相同**，
    p 恒为 1。实测：200 次随机顺序置换下 distinct rho = 1（见 selftest）。

    替代统计量（对簇结构**有**依赖，故置换非退化）：
        T = Σ_c n_c · mean_c(rx) · mean_c(ry) / (n · sd(rx) · sd(ry))
    即"簇均值在秩上的**簇间协方差**（标准化）"。簇标签被打乱 ⇒ 各簇的成员改变 ⇒ 簇均值改变 ⇒ T 变。
    零假设：knob 分组与 (span, span_eq4) 的**秩结构**无关。
    """
    n = len(rank_x)
    mx = sum(rank_x) / n
    my = sum(rank_y) / n
    sx = (sum((v - mx) ** 2 for v in rank_x) / n) ** 0.5
    sy = (sum((v - my) ** 2 for v in rank_y) / n) ** 0.5
    groups = {}
    for i, lb in enumerate(labels):
        groups.setdefault(lb, []).append(i)
    num = 0.0
    for k, idx in groups.items():
        num += len(idx) * ((sum(rank_x[i] for i in idx) / len(idx) - mx) *
                           (sum(rank_y[i] for i in idx) / len(idx) - my))
    return num / (n * sx * sy) if sx and sy else float('nan')


def perm_cluster_order(x, y, labels, n_perm=N_PERM, seed=SEED):
    """方案 §4.3 字面口径：在簇标签层置换（簇内保持配对），统计量 = Spearman(full, deflated)。
    **实测退化**：所有置换统计量与观测逐位相同 ⇒ p 恒为 1。仍照跑并落盘，作为"该口径不可用"的旁证。"""
    obs = spearman(x, y)
    groups = {}
    for i, lb in enumerate(labels):
        groups.setdefault(lb, []).append(i)
    keys = sorted(groups)
    K = len(keys)
    members = [groups[k] for k in keys]
    if K > 8:
        return dict(obs=obs, p=None, n_draws=0, n_clusters=K, method='skipped_degenerate',
                    degenerate=True, distinct_stat_values=1,
                    note='全局 Spearman 与单元顺序无关 ⇒ 簇标签置换不改统计量')
    seen = set()
    ge = 0
    n = 0
    for perm in itertools.permutations(range(K)):
        order = []
        for slot in range(K):
            order.extend(members[perm[slot]])
        st = spearman([x[i] for i in order], [y[i] for i in order])
        seen.add(round(st, 12))
        if st >= obs - 1e-12:
            ge += 1
        n += 1
    return dict(obs=obs, p=(1 + ge) / (1 + n), n_draws=n, n_clusters=K,
                method='full_enumeration', degenerate=(len(seen) == 1),
                distinct_stat_values=len(seen), seed=seed,
                note='统计量只依赖配对集合 ⇒ 期望 distinct_stat_values == 1（退化）')


def perm_cluster_stat(rank_x, rank_y, labels, n_perm=N_PERM, seed=SEED):
    """★ 可用的簇级置换：统计量 = between_rank_r2（对簇结构有依赖）。

    ★ 注意"簇标签置换"的正确实现：把**单元 -> 簇标签**的映射随机打乱（生成随机划分），
    **不是**把整块簇换个位置（后者保持划分不变、统计量恒定，与上面那个退化口径同样的病）。
    簇数 2..8 时完整枚举（生成器逐一给出全部重复排列的标签向量），否则蒙特卡洛 n_perm 次。
    """
    obs = between_rank_r2(rank_x, rank_y, labels)
    n = len(labels)
    K = len(set(labels))
    n_enum = 1
    for i in range(2, n + 1):
        n_enum *= i
    # 完整枚举用的是"标签向量的全部相异排列"：n! 太大 ⇒ 只在 n 小的时候做；
    # 这里统一用**标签的多重集排列数** n!/(各簇大小阶乘) 作为枚举空间，用 K<=8 且空间 <= ENUM_CAP 判定。
    from math import factorial
    cnt = {}
    for lb in labels:
        cnt[lb] = cnt.get(lb, 0) + 1
    space = factorial(n)
    for v in cnt.values():
        space //= factorial(v)
    full_enum = space <= ENUM_CAP and K <= 8

    ge = 0
    if full_enum:
        # 只枚举**不同标签**的排列（K! 种），再按各标签的出现次数展开成完整标签向量；
        # 直接对 31 元的 labels 做 permutations 会炸内存。
        seen = 0
        for uniq in itertools.permutations(sorted(cnt.keys())):
            lab = []
            for u in uniq:
                lab.extend([u] * cnt[u])
            assert len(lab) == n
            seen += 1
            if between_rank_r2(rank_x, rank_y, lab) >= obs - 1e-12:
                ge += 1
        n_draws = seen
        method = 'full_enumeration'
    else:
        rnd = random.Random(seed)
        labs = list(labels)
        n_draws = n_perm
        for _ in range(n_perm):
            rnd.shuffle(labs)
            if between_rank_r2(rank_x, rank_y, labs) >= obs - 1e-12:
                ge += 1
        method = 'monte_carlo'
    return dict(obs=obs, p=(1 + ge) / (1 + n_draws), n_draws=n_draws, n_clusters=K,
                method=method, seed=seed, min_attainable_p=1.0 / n_draws,
                cluster_sizes=sorted(cnt.values()),
                statistic='between_rank_r2 = sum_c n_c*mean_c(rx)*mean_c(ry) / (n*sd(rx)*sd(ry))')
def md5_file(path):
    return hashlib.md5(io.open(path, 'rb').read()).hexdigest()


def parse_knob(unit_name):
    """'VLM·pixel budget / ivl / st_a' -> 'pixel_budget'；'det·in-domain(micro)/BBBC005 / tau@640'
    -> 'detection_threshold'。凡不能映射到六个旋钮之一的一律**报错**（不静默）。"""
    assert '·' in unit_name, '单元名没有 ·: %r' % unit_name
    rest = unit_name.split('·', 1)[1]
    prefix = rest.split('/')[0].strip()
    # 无 '/' 的单元（如 'det·zero-shot COCO (full grid)'）在方案 §4.1 里被点名为"一次都没被丢过"的
    # 第 36 个单元；破折号后的括号只是标注，须剥掉才能映射到旋钮。
    if prefix not in KNOB_OF_PREFIX and '(' in prefix:
        prefix = prefix.split('(')[0].strip()
    if prefix not in KNOB_OF_PREFIX:
        raise AssertionError('无法把 %r 的 knob 前缀 %r 映射到六个旋钮' % (unit_name, prefix))
    return KNOB_OF_PREFIX[prefix]


def parse_cluster_b(unit_name):
    """方案 §4.2 criteria.clustering (b)：**knob x 域/构建** 的更细簇。
    口径（写死，报告里同时给 (a)）：
      * 'VLM·X / A / B ...'  -> ('VLM·X', A)            # 第一个 '/' 后的第一段 = 模型/构建
      * 'density·CSRNet / ladder' -> ('density·CSRNet', 'ladder')
      * 'det·<ds> / tau@640' -> ('det·<ds>', 'tau@640')  # tau@* 按扫描尺寸分簇
      * 'det·<ds> (full grid)' 无 '/' -> ('det·<ds>', '(full grid)')
    """
    assert '·' in unit_name, '单元名没有 ·: %r' % unit_name
    fam, rest = unit_name.split('·', 1)
    head = fam + '·' + rest.split('/')[0].strip()
    if '/' not in rest:
        return (head, '(full grid)')
    tail = rest.split('/', 1)[1]
    return (head, tail.split('/')[0].strip())


def spearman(x, y):
    """★ **逐字照抄** `m37_ci_power.py` L44-54 的实现（含它 `{v: i ...}` 的并列处理），
    否则重算值与冻结件会在第三位上差 0.001，无法对账。"""
    n = len(x)
    rx = {v: i for i, v in enumerate(sorted(x))}
    ry = {v: i for i, v in enumerate(sorted(y))}
    ax = [rx[v] for v in x]
    ay = [ry[v] for v in y]
    mx, my = sum(ax) / n, sum(ay) / n
    num = sum((a - mx) * (b - my) for a, b in zip(ax, ay))
    dx = sum((a - mx) ** 2 for a in ax) ** 0.5
    dy = sum((b - my) ** 2 for b in ay) ** 0.5
    return num / (dx * dy) if dx and dy else float('nan')


def boot_iid(x, y, n_boot=N_BOOT, seed=SEED):
    """★ **逐字照抄** `m37_ci_power.py` L57-66（阴性对照：必须复现现文区间）。"""
    rnd = random.Random(seed)
    n = len(x)
    obs = spearman(x, y)
    out = []
    for _ in range(n_boot):
        idx = [rnd.randrange(n) for _ in range(n)]
        out.append(spearman([x[i] for i in idx], [y[i] for i in idx]))
    out.sort()
    return dict(obs=obs, p025=out[int(0.025 * n_boot)], p975=out[int(0.975 * n_boot)],
                method='iid_unit_bootstrap', n_boot=n_boot, seed=seed)


def boot_block(x, y, labels, n_boot=N_BOOT, seed=SEED):
    """按簇**整块**有放回重抽（方案 §4.3）。重抽后簇内配对保留、簇大小随机。"""
    rnd = random.Random(seed)
    obs = spearman(x, y)
    groups = {}
    for i, lb in enumerate(labels):
        groups.setdefault(lb, []).append(i)
    keys = sorted(groups)
    out = []
    for _ in range(n_boot):
        idx = []
        for _ in range(len(keys)):
            k = keys[rnd.randrange(len(keys))]
            idx.extend(groups[k])
        out.append(spearman([x[i] for i in idx], [y[i] for i in idx]))
    out.sort()
    return dict(obs=obs, p025=out[int(0.025 * n_boot)], p975=out[int(0.975 * n_boot)],
                n_clusters=len(keys), cluster_sizes=sorted(len(groups[k]) for k in keys),
                n_boot=n_boot, seed=seed)


def perm_free(x, y, n_perm=N_PERM, seed=SEED):
    """★ **逐字照抄** `m37_ci_power.py` L69-78（自由标签置换；阴性对照）。"""
    rnd = random.Random(seed)
    obs = spearman(x, y)
    b = list(y)
    ge = 0
    for _ in range(n_perm):
        rnd.shuffle(b)
        if spearman(x, b) >= obs:
            ge += 1
    return dict(obs=obs, p=(1 + ge) / (1 + n_perm), n_perm=n_perm, seed=seed,
                method='free_label_permutation')


def perm_cluster(x, y, labels, n_perm=N_PERM, seed=SEED):
    """**簇级**置换：在簇标签层置换（簇内保持配对），统计量 = Spearman(full, deflated)。

    零假设：knob 分组与 (full, deflated) 的排序关联无关。观测统计量 = rho(x, y)（方案 §4.3）。
    簇数 <= log(ENUM_CAP) 时**完整枚举**（p 可达 1/N! 下限），否则**蒙特卡洛** n_perm 次。
    尾巴口径与 m37_ci_power.py 一致：p = (1 + #{统计量 >= 观测}) / (1 + N)。
    """
    obs = spearman(x, y)
    groups = {}
    for i, lb in enumerate(labels):
        groups.setdefault(lb, []).append(i)
    keys = sorted(groups)
    K = len(keys)
    members = [groups[k] for k in keys]

    n_enum = 1
    for i in range(2, K + 1):
        n_enum *= i
    full_enum = n_enum <= ENUM_CAP

    def rho_for(perm):
        """perm[t] = 原簇 t 的槽位 -> 把 members[t] 的单元放到新簇 perm[t]；
        因为统计量是**全单元**上的 rho，簇标签只由**置换哪些单元成组**起作用 ⇒
        等价于按簇置换**单元顺序**。"""
        order = []
        for slot in range(K):
            order.extend(members[perm[slot]])
        return spearman([x[i] for i in order], [y[i] for i in order])

    ge = 0
    if full_enum:
        for perm in itertools.permutations(range(K)):
            if rho_for(perm) >= obs - 1e-12:
                ge += 1
        n = n_enum
        method = 'full_enumeration'
    else:
        rnd = random.Random(seed)
        base = list(range(K))
        n = n_perm
        for _ in range(n_perm):
            p = base[:]
            rnd.shuffle(p)
            if rho_for(p) >= obs - 1e-12:
                ge += 1
        method = 'monte_carlo'
    return dict(obs=obs, p=(1 + ge) / (1 + n), n_draws=n, n_clusters=K,
                method=method, seed=seed, min_attainable_p=1.0 / n,
                cluster_sizes=sorted(len(m) for m in members))


def leave_one_cluster_out(x, y, labels):
    """留一**簇**（整簇丢掉）后的 rho 极差。"""
    groups = {}
    for i, lb in enumerate(labels):
        groups.setdefault(lb, []).append(i)
    keys = sorted(groups)
    rows = []
    for k in keys:
        drop = set(groups[k])
        keep = [i for i in range(len(x)) if i not in drop]
        rows.append(dict(cluster=k, n_dropped=len(drop),
                         rho=spearman([x[i] for i in keep], [y[i] for i in keep])))
    rhos = [r['rho'] for r in rows]
    return dict(rows=rows, lo=min(rhos), hi=max(rhos), n_clusters=len(keys))


def holm(pvals):
    """Holm 校正。输入 [{'key':..,'p':..}]，按 p 升序逐个与 alpha/(m-rank) 比。"""
    m = len(pvals)
    order = sorted(range(m), key=lambda i: pvals[i]['p'])
    out = {}
    for rank, i in enumerate(order):
        adj = min(1.0, pvals[i]['p'] * (m - rank))
        out[pvals[i]['key']] = adj
    return out


# ══════════════════════════════════════════════════════════════════════════════
def write_criteria():
    crit = {
        "round": "P3R2 / class-3 / §4 (外部核查 #16)",
        "frozen_at": "2026-09-29T00:00:00+08:00",
        "frozen_by": "P3R2 施工代理（依 `_p3r2_experiment_plan.md` §4.2 逐条落成）",
        "why_this_file": "外部核查 #16 指控 31 单元嵌套在 6 个 knob x 4 个域里，自由标签置换会反保守；"
                         "现文只补了 leave-one-knob-out，其下沿 0.883 < 0.9。本件把簇级口径**跑前**写死。",
        "question": "§7.3 的排序稳定性在**按 knob（或 knob x 域/构建）聚类**的重采样/置换下，下沿还 >= 0.80 吗？",
        "what_already_exists": {
            "iid_unit_bootstrap": "m37_ci_power.py::boot_ci() 为单元 i.i.d. 有放回；31@k4 = 0.939-0.996，36@k3 = 0.836-0.983",
            "free_label_permutation": "m37_ci_power.py::perm_p() 为自由标签置换（rnd.shuffle(b)）；两套单元集的 p 都饱和在 5.0e-5",
            "leave_one_knob_out": "冻结件 m37_ci_power_result.json 的 leave_one_knob_out 有 9 个键、字段只有 rho_36 "
                                  "⇒ 是**朴素名字子组**、**36 单元**口径（方案 §4.1 第 2 条）",
            "gap": "**从未**整体丢掉 detector threshold（12 单元）或 density regression（4 单元）；也从未做簇级置换/块 bootstrap"
        },
        "what_this_run_adds": "① 簇级（按 knob / 按 knob x 域）置换检验；② 按簇的块 bootstrap 95% 区间；"
                              "③ 留一**簇**（真旋钮）极差；④ 与 9 个朴素子组的对账",
        "deviation_declared": "① 本件只做**重采样结构**替换，0 次推理、0 新数据；② 不改 m37_ci_power.py 与任何冻结件；"
                              "③ 簇标签由单元名的 knob 前缀机械解析（KNOB_OF_PREFIX 表写死在脚本里）；"
                              "④ 36 单元口径下 tiling/density 的簇大小与 31 单元口径不同，**分列报，不混用**",
        "design": {
            "unit_sets": ["31unit_k4（span_eq4 存在且 n>=4）", "36unit_k3（全 36 单元）"],
            "statistic": "Spearman(full-ladder span, deflated span)；deflation 三种：span_eq4 / span_drop_high / span_drop_low",
            "clustering_a": {"name": "six_knobs",
                             "expected_31_units_sizes": EXPECT_31,
                             "note": "方案 §4.2 criteria.clustering (a)"},
            "clustering_b": {"name": "knob_x_domain",
                             "note": "方案 §4.2 criteria.clustering (b)；更细簇，实测单元名里可解析"},
            "permutation": {"n_perm": N_PERM, "enum_cap": ENUM_CAP,
                            "tail": "p = (1 + #{perm_stat >= obs}) / (1 + N)",
                            "seed": SEED},
            "block_bootstrap": {"n_boot": N_BOOT, "resample": "按簇整块有放回", "seed": SEED},
            "deflation": [d[0] for d in DEFLATIONS],
            "starts": "n/a（0 次推理，无服务）"
        },
        "criteria": {
            "pass": "**按 knob 聚类的置换 p < 0.05** 且 **按 knob 的块 bootstrap 95% 下沿 >= 0.80**",
            "threshold_0.80_source": "补材 1154 行：'all far above the 0.8 threshold we would have accepted as evidence of instability'（F.10）",
            "report_both_clusterings": "criteria.clustering 的 (a) 六旋钮 与 (b) knob x 域/构建 **两套都要报**",
            "report_both_calibers": "leave-one-cluster-out 极差须**区分**'六个旋钮'与'九个朴素子组'两种口径（后者用于与现文 0.883-0.970 对账）",
            "negative_controls": ["i.i.d. bootstrap 必须**逐位复现**现文 31@k4 = 0.939-0.996 与 36@k3 = 0.836-0.983",
                                  "自由标签置换必须复现 p = 4.999750012499375e-05",
                                  "--selftest：打乱簇标签后簇级检验必须失去显著性"],
            "multiple_comparison": "12 个（3 deflation x 2 单元集 x 2 聚类）置换 p 做 **Holm** 校正，原 p 与校正 p 并印",
            "p_not_significant_note": "簇数只有 2~12，功效天然低；**p 不显著 != 排序不稳**，区间必须并印",
            "on_fail": "见方案 §4.8：不得因 p 变大就撤回 ordering 主张（§7.3 已把'可分结构'撤回、只主张 ordering）"
        },
        "what_result_would_change": {
            "lower_bound_below_0.80": "§7.3 L757-759 删 i.i.d. 区间、换 clustered 口径；L775-778 加限定；"
                                      "§8.2 L892-893 补半句；F.7 加一段（+180 词）",
            "lower_bound_ge_0.80_but_p_gt_0.05": "§7.3 保留 ordering 主张，只把区间来源换成簇级口径",
            "both_pass": "§7.3 只把区间来源注明为 clustered（净 +6 词，删 i.i.d. 区间可回收 -8 词）"
        },
        "inputs": {
            "equalcount36_result.json": md5_file(EQ),
            "m37_ci_power_result.json": md5_file(M37RES)
        }
    }
    io.open(CRIT, 'w', encoding='utf-8', newline='\n').write(
        json.dumps(crit, ensure_ascii=False, indent=2))
    h = md5_file(CRIT)
    print('已写判据件 %s\n  md5 = %s' % (os.path.basename(CRIT), h))
    print('★ 请把该 md5 粘进脚本顶部 CRIT_MD5 常量后重跑。')
    return 0


# ══════════════════════════════════════════════════════════════════════════════
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--write-criteria', action='store_true')
    ap.add_argument('--check', action='store_true', help='只跑自证 + 阴性对照，不写结果')
    ap.add_argument('--selftest', action='store_true', help='阴性对照：打乱簇标签后检验必须失去显著性')
    ap.add_argument('--fast', action='store_true', help='降低置换/重抽次数以便快速干跑（结果不落盘）')
    args = ap.parse_args()

    if args.write_criteria:
        if os.path.exists(CRIT):
            print('判据件已存在，拒绝覆盖：%s' % CRIT)
            return 1
        return write_criteria()

    # ① 判据件 md5 断言（方案 §0.4 纪律①）
    if not os.path.exists(CRIT):
        print('!! 判据件不存在，先跑 --write-criteria')
        return 1
    got = md5_file(CRIT)
    if CRIT_MD5 != 'PLACEHOLDER_SET_ON_FIRST_RUN' and got != CRIT_MD5:
        print('!! 判据件 md5 不符：期望 %s，实得 %s ⇒ 判据被动过，拒绝运行' % (CRIT_MD5, got))
        return 1
    print('判据件 md5 %s %s' % (got, '(已断言 ✓)' if CRIT_MD5 != 'PLACEHOLDER_SET_ON_FIRST_RUN' else '(未断言：首次运行)'))
    eq_md5 = md5_file(EQ)
    print('输入 equalcount36_result.json md5 %s' % eq_md5)
    if not eq_md5.startswith('bd70867b1453'):
        print('!! equalcount36_result.json md5 前缀不是补材 1252 行印的 bd70867b1453 ⇒ 拒绝运行')
        return 1

    n_perm = 2000 if args.fast else N_PERM
    n_boot = 200 if args.fast else N_BOOT
    t0 = time.time()

    eq = json.loads(io.open(EQ, encoding='utf-8').read())
    m37 = json.loads(io.open(M37RES, encoding='utf-8').read())
    units36 = eq['units']

    # ── 自证 1：单元集规模 ────────────────────────────────────────────────────
    units31 = [u for u in units36 if 'span_eq4' in u and u.get('n', 0) >= 4]
    assert len(units36) == 36, '36 单元集规模不符：%d' % len(units36)
    assert len(units31) == 31, '31 单元子集规模不符：%d' % len(units31)
    print('\n① 自证：36 单元 / 31 单元子集（span_eq4 存在且 n>=4）= %d ✓' % len(units31))

    # ── 自证 2：六旋钮规模（方案 §4.2 写死值）──────────────────────────────────
    for tag, us in (('31unit_k4', units31), ('36unit_k3', units36)):
        cnt = {k: 0 for k in KNOB_ORDER}
        for u in us:
            cnt[parse_knob(u['unit'])] += 1
        if tag == '31unit_k4':
            bad = {k: (cnt[k], EXPECT_31[k]) for k in KNOB_ORDER if cnt[k] != EXPECT_31[k]}
            assert not bad, '31 单元六旋钮规模与方案 §4.2 写死值不符：%s' % bad
            print('   六旋钮规模（31 单元）= %s ✓（与方案 §4.2 写死值逐项一致）'
                  % {k: cnt[k] for k in KNOB_ORDER})
        else:
            print('   六旋钮规模（36 单元）= %s' % {k: cnt[k] for k in KNOB_ORDER})

    # ── 自证 3：两种聚类的簇数、无重无漏 ──────────────────────────────────────
    clust = {}
    for tag, us in (('31unit_k4', units31), ('36unit_k3', units36)):
        la = [parse_knob(u['unit']) for u in us]
        lb = [parse_cluster_b(u['unit']) for u in us]
        assert len(la) == len(us) and len(lb) == len(us)
        ca, cb = {}, {}
        for i, k in enumerate(la):
            ca.setdefault(k, []).append(i)
        for i, k in enumerate(lb):
            cb.setdefault(k, []).append(i)
        clust[tag] = dict(a_labels=la, b_labels=lb)
        print('   %s 聚类(a) 六旋钮 = %d 簇，规模 %s'
              % (tag, len(ca), sorted(len(v) for v in ca.values())))
        print('   %s 聚类(b) knob x 域 = %d 簇，规模 %s'
              % (tag, len(cb), sorted(len(v) for v in cb.values())))

    # ── ② 阴性对照：i.i.d. bootstrap 与自由置换必须复现冻结件 ────────────────
    print('\n② 阴性对照（i.i.d. 口径必须复现冻结件):')
    obs = {}
    nc_ok = True
    for tag, us, key, pub in (('31unit_k4', units31, 'span_eq4', PUBLISHED_LL),
                              ('36unit_k3', units36, 'span_eq', PUBLISHED_36)):
        x = [u['span'] for u in us]
        y = [u[key] for u in us]
        b = boot_iid(x, y, n_boot=n_boot)
        p = perm_free(x, y, n_perm=n_perm)
        obs[tag] = dict(rho=spearman(x, y), iid=b, perm=p)
        ok = abs(round(b['p025'], 3) - pub[0]) <= 0.001 and abs(round(b['p975'], 3) - pub[1]) <= 0.001
        nc_ok = nc_ok and ok
        print('   %-10s rho=%.6f  i.i.d. 95%%CI [%.3f, %.3f]（印值 [%.3f, %.3f]）%s  自由置换 p=%.3e'
              % (tag, obs[tag]['rho'], b['p025'], b['p975'], pub[0], pub[1], 'OK' if ok else '<-- 不符', p['p']))
    # 33 位小数逐位复现（不四舍五入）
    if not args.fast:
        assert abs(obs['31unit_k4']['iid']['obs'] - 0.9820813939117907) < 1e-12, '31@k4 观测 rho 未逐位复现'
        assert abs(obs['31unit_k4']['iid']['p025'] - 0.9390905416017907) < 1e-12, '31@k4 i.i.d. 下沿未逐位复现'
        assert abs(obs['31unit_k4']['iid']['p975'] - 0.995845707414122) < 1e-12, '31@k4 i.i.d. 上沿未逐位复现'
        assert abs(obs['36unit_k3']['iid']['obs'] - 0.9324881740039196) < 1e-12, '36@k3 观测 rho 未逐位复现'
        assert obs['36unit_k3']['perm']['p'] == 4.999750012499375e-05, '36@k3 自由置换 p 未复现'
        print('   ★ 逐位复现冻结件 ✓（0.9820813939117907 / 0.9390905416017907 / 0.995845707414122 / 4.999750012499375e-05）')
    if not nc_ok and not args.fast:
        print('!! 阴性对照未通过 ⇒ 结论不可用')
        return 1

    # ── ③ 簇级置换 + 块 bootstrap + 留一簇 ───────────────────────────────────
    # ★ 先自证方案 §4.3 字面口径的**退化**（见 perm_cluster_order 文档串）
    print('\n③a 退化自证：方案 §4.3 字面口径（簇标签层置换、统计量 = 全局 Spearman）')
    x31 = [u['span'] for u in units31]
    y31 = [u['span_eq4'] for u in units31]
    rnd0 = random.Random(SEED)
    pcs = set()
    for _ in range(200):
        o = list(range(len(x31)))
        rnd0.shuffle(o)
        pcs.add(round(spearman([x31[i] for i in o], [y31[i] for i in o]), 12))
    print('   200 次随机"块置换"下 distinct Spearman = %d ⇒ %s'
          % (len(pcs), '**退化，该口径无功效**' if len(pcs) == 1 else '有变化'))
    assert len(pcs) == 1, '全局 Spearman 竟然随单元顺序变化 ⇒ 前提不成立，须重估'
    deg = perm_cluster_order(x31, y31, clust['31unit_k4']['a_labels'], n_perm=n_perm)
    print('   完整枚举 720 种块置换：p = %s（distinct 统计量 = %d）'
          % (deg['p'], deg['distinct_stat_values']))

    print('\n③ 簇级口径（判据读数）—— 统计量 = between_rank_r2（对簇结构有依赖）：')
    readings = []
    table = {}
    for tag, us, defls in (('31unit_k4', units31, DEFLATIONS_31),
                           ('36unit_k3', units36, DEFLATIONS_36)):
        table[tag] = {}
        for defl_name, key in defls:
            if key not in us[0]:
                print('   （%s 无 %s 列，跳过）' % (tag, key))
                continue
            x = [u['span'] for u in us]
            y = [u[key] for u in us]
            rx, ry = avg_ranks(x), avg_ranks(y)
            row = {}
            for cname in ('a', 'b'):
                labels = clust[tag][cname + '_labels']
                pc = perm_cluster_stat(rx, ry, labels, n_perm=n_perm)
                bb = boot_block(x, y, labels, n_boot=n_boot)
                lo = leave_one_cluster_out(x, y, labels)
                row[cname] = dict(perm=pc, block_boot=bb, lo_cluster=lo)
                readings.append(dict(key='%s|%s|%s' % (tag, defl_name, cname),
                                     p=pc['p'], lo=lo['lo'], unit_set=tag,
                                     deflation=defl_name, clustering=cname))
                print('   %-10s %-14s %s  rho=%.4f  T=%.4f  簇级置换 p=%.5f (%s, %d 簇)  '
                      '块 bootstrap [%.3f, %.3f]  留一簇 [%.3f, %.3f]'
                      % (tag, defl_name, cname, spearman(x, y), pc['obs'], pc['p'], pc['method'],
                         pc['n_clusters'], bb['p025'], bb['p975'], lo['lo'], lo['hi']))
            table[tag][defl_name] = row
    holm_adj = holm(readings)

    # ── ④ 判据判定（只对方案 §4.2 写死的主口径：31@k4 + 聚类(a) 六旋钮）────────
    print('\n④ 判据判定（方案 §4.2 criteria.pass）：')
    main_key = '31unit_k4|equal_count_k4|a'
    main = [r for r in readings if r['key'] == main_key][0]
    main_pc = table['31unit_k4']['equal_count_k4']['a']
    p_pass = main['p'] < 0.05
    lo_pass = main_pc['block_boot']['p025'] >= THRESHOLD_LOWER
    verdict = 'PASS' if (p_pass and lo_pass) else ('PARTIAL' if (p_pass or lo_pass) else 'FAIL')
    print('   主口径 = %s' % main_key)
    print('   簇级置换 p = %.6f (< 0.05 ? %s)' % (main['p'], p_pass))
    print('   块 bootstrap 95%% 下沿 = %.4f (>= %.2f ? %s)' % (main_pc['block_boot']['p025'],
                                                              THRESHOLD_LOWER, lo_pass))
    print('   ⇒ 判据 = **%s**' % verdict)

    # ── ⑤ 留一簇 vs 现文 9 个朴素子组（对账）────────────────────────────────
    print('\n⑤ 留一簇对账（现文 0.883-0.970 是 36 单元 / 9 个朴素名字子组口径）：')
    knob36 = leave_one_cluster_out([u['span'] for u in units36],
                                   [u['span_eq'] for u in units36],
                                   clust['36unit_k3']['a_labels'])
    print('   六个旋钮（36 单元口径）区间 = %.3f-%.3f' % (knob36['lo'], knob36['hi']))
    for r in knob36['rows']:
        print('     %-22s n_drop=%-3d rho=%.3f' % (r['cluster'], r['n_dropped'], r['rho']))
    naive = {}
    for u in units36:
        nm = u['unit']
        side, rest = (nm.split('·', 1) + [''])[:2] if '·' in nm else ('', nm)
        kn = rest.split('/')[0].strip() if '/' in rest else rest.strip()
        naive.setdefault(kn, []).append(u)
    naive_rows = []
    for kn, us in naive.items():
        if len(us) < 2:
            continue
        sub = [u for u in units36 if u not in us]
        if len(sub) < 5:
            continue
        naive_rows.append((kn, len(us), spearman([u['span'] for u in sub],
                                                 [u['span_eq'] for u in sub])))
    print('   九个朴素子组（36 单元口径）区间 = %.3f-%.3f（现文印 0.883-0.970）'
          % (min(r[2] for r in naive_rows), max(r[2] for r in naive_rows)))
    det = [r for r in knob36['rows'] if r['cluster'] == 'detection_threshold'][0]
    print('   ★ detector threshold 整体丢（12 单元）rho = %.3f（Δ vs 全量 %.3f）= **%.3f**'
          % (det['rho'], det['rho'] - obs['36unit_k3']['rho'], det['rho']))

    if args.check:
        print('\n--check 干跑结束，未写结果。用时 %.1f s' % (time.time() - t0))
        return 0

    # ── ⑥ selftest：打乱簇标签后簇级检验必须失去显著性 ──────────────────────
    if args.selftest:
        selftest = {}
        for tag, us, key, defls in (('31unit_k4', units31, 'span_eq4', DEFLATIONS_31),
                                    ('36unit_k3', units36, 'span_eq', DEFLATIONS_36)):
            x = [u['span'] for u in us]
            y = [u[key] for u in us]
            rx, ry = avg_ranks(x), avg_ranks(y)
            lb = clust[tag]['a_labels'][:]
            rnd = random.Random(SEED + 1)
            rnd.shuffle(lb)
            pc = perm_cluster_stat(rx, ry, lb, n_perm=n_perm)
            selftest[tag] = pc
            print('⑥ selftest %s：打乱簇标签后 T=%.4f p=%.4f（应不显著）' % (tag, pc['obs'], pc['p']))
            if pc['p'] < 0.05:
                print('!! selftest 失败：打乱簇标签后仍显著 ⇒ 实现有问题')
                return 1
        print('   selftest 通过 ✓')

    # ── 落盘 ─────────────────────────────────────────────────────────────────
    out = dict(
        purpose='P3R2 §4（外部核查 #16）：把 §7.3 排序稳定性的重采样结构从 i.i.d. 换成**按 knob 聚类**，'
                '给簇级置换 p、块 bootstrap 95% 区间与留一簇极差。0 次推理 / 0 新数据。',
        inputs=dict(equalcount36=os.path.basename(EQ), equalcount36_md5=eq_md5,
                    m37_ci_power_result=os.path.basename(M37RES),
                    m37_ci_power_result_md5=md5_file(M37RES),
                    criteria=os.path.basename(CRIT), criteria_md5=got),
        methods=dict(
            iid_bootstrap='★ 逐字照抄 m37_ci_power.py::boot_ci()（单元 i.i.d. 有放回，%d 次，seed %d）' % (N_BOOT, SEED),
            free_permutation='★ 逐字照抄 m37_ci_power.py::perm_p()（自由标签置换，%d 次，seed %d）' % (N_PERM, SEED),
            cluster_permutation_literal='方案 §4.3 字面口径（在簇标签层置换、统计量 = Spearman(full, deflated)）：'
                                        '**实测退化** —— 全局 Spearman 只依赖 (x,y) 配对集合，与单元顺序/分组无关，'
                                        '故每次置换统计量与观测逐位相同，p 恒为 1。仍照跑并落盘（见 degeneracy）。',
            cluster_permutation_used='★ 可用替代：统计量 = between_rank_r2（簇间秩协方差标准化），'
                                     '置换 = 打乱"单元 -> 簇"标签映射（生成随机划分）。'
                                     '标签多重集排列数 <= %d 且簇数 <= 8 时完整枚举，否则蒙特卡洛 %d 次；'
                                     'p=(1+#{>=obs})/(1+N)' % (ENUM_CAP, N_PERM),
            block_bootstrap='按簇整块有放回重抽 %d 次，seed %d，取 2.5/97.5 分位' % (N_BOOT, SEED),
            leave_one_cluster_out='整簇丢掉后重算 rho 取极差',
            deflation='x = full-ladder span；31@k4 用 span_eq4/drop_high/drop_low；36@k3 用 span_eq/drop_high/drop_low',
        ),
        degeneracy=dict(
            literal_cluster_permutation_invariant=True,
            evidence='200 次随机单元顺序置换下 distinct Spearman = 1；完整枚举 720 种块置换 distinct 统计量 = 1',
            enumeration_720=deg,
            implication='方案 §4.2 的判据"按 knob 聚类的置换 p < 0.05"若照 §4.3 字面实现则**不可评**'
                        '（p 恒为 1 是数学必然，不是功效问题）。本件改用对簇结构有依赖的 between_rank_r2，'
                        '并把这一条作为**需要上级拍板**的设计偏离上报。',
        ),
        clustering=dict(
            a_six_knobs=dict(order=KNOB_ORDER,
                             sizes_31={k: EXPECT_31[k] for k in KNOB_ORDER},
                             sizes_36={k: sum(1 for u in units36 if parse_knob(u['unit']) == k) for k in KNOB_ORDER}),
            b_knob_x_domain=dict(note='knob x 域/构建；逐单元标签见 cluster_labels'),
        ),
        cluster_labels={tag: dict(
            a=dict(zip([u['unit'] for u in (units31 if tag == '31unit_k4' else units36)],
                       clust[tag]['a_labels'])),
            b=dict(zip([u['unit'] for u in (units31 if tag == '31unit_k4' else units36)],
                       ['|'.join(t) for t in clust[tag]['b_labels']])))
            for tag in ('31unit_k4', '36unit_k3')},
        negative_controls=obs,
        readings=table,
        criterion=dict(
            key=main_key,
            p_cluster_perm=main['p'], p_threshold=0.05,
            block_boot_lower=main_pc['block_boot']['p025'], lower_threshold=THRESHOLD_LOWER,
            pass_p=p_pass, pass_lower=lo_pass, verdict=verdict,
            text='按 knob 聚类的置换 p < 0.05 且 按 knob 的块 bootstrap 95% 下沿 >= 0.80'
        ),
        holm_adjusted_p=holm_adj,
        leave_one_cluster_out_36=knob36,
        leave_one_naive_subgroup_36=dict(
            rows=[dict(name=r[0], n_dropped=r[1], rho=r[2]) for r in naive_rows],
            lo=min(r[2] for r in naive_rows), hi=max(r[2] for r in naive_rows),
            published=PUBLISHED_LOO_RANGE,
            note='现文 "0.883-0.970" 的口径 = 36 单元 + 9 个朴素名字子组（与冻结件 leave_one_knob_out 逐格一致）'),
        detector_knob_whole_drop_36=dict(
            n_dropped=det['n_dropped'], rho=det['rho'], delta_vs_full=det['rho'] - obs['36unit_k3']['rho'],
            note='**从未被测量过**的那一档：detector threshold 的 12 个单元整体丢掉（全 36 单元的三分之一）'),
        quoted_display=dict(
            rho_31_k4=round(obs['31unit_k4']['rho'], 3),
            rho_31_k4_iid_ci=[round(obs['31unit_k4']['iid']['p025'], 3), round(obs['31unit_k4']['iid']['p975'], 3)],
            rho_36_k3=round(obs['36unit_k3']['rho'], 3),
            rho_36_k3_iid_ci=[round(obs['36unit_k3']['iid']['p025'], 3), round(obs['36unit_k3']['iid']['p975'], 3)],
            clustered_31_k4_knob_ci=[round(main_pc['block_boot']['p025'], 3), round(main_pc['block_boot']['p975'], 3)],
            clustered_31_k4_knob_p=main['p'],
            loo_knob6_36=[round(knob36['lo'], 3), round(knob36['hi'], 3)],
            loo_naive9_36=[round(min(r[2] for r in naive_rows), 3), round(max(r[2] for r in naive_rows), 3)],
            detector_knob_whole_drop_rho=round(det['rho'], 3),
        ),
        created_by='p3r2_plan_m37_cluster.py',
        created_at=time.strftime('%Y-%m-%dT%H:%M:%S'),
    )
    io.open(OUT, 'w', encoding='utf-8', newline='\n').write(json.dumps(out, ensure_ascii=False, indent=2))
    h = md5_file(OUT)
    io.open(OUT + '.md5', 'w', encoding='utf-8', newline='\n').write(
        '%s  %s  (p3r2_plan_m37_cluster.py)\n' % (h, os.path.basename(OUT)))
    print('\n已写 %s（md5 %s）' % (os.path.basename(OUT), h[:12]))
    print('显示值：%s' % json.dumps(out['quoted_display'], ensure_ascii=False))
    print('用时 %.1f s' % (time.time() - t0))
    return 0


if __name__ == '__main__':
    sys.exit(main())
