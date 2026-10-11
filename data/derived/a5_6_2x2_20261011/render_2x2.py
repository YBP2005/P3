# -*- coding: utf-8 -*-
"""A5-6（r20 评审 A5-第2条）"点名 0 × 弃答出口" 2x2 正交实验 —— 刺激渲染器。

★ 本件**只渲染**（云端由上级执行）：不联网、不连任何机器、不调用任何服务。
★ 设计冻结（照评审原文实现，因子不放宽）：
    600 张图 = 300 张**真零图**（被问目标**完全不出现**）+ 300 张**非零对照图**（被问目标存在，计数档 = 48）
    参数族 = 与既有 exp3（render_a55.py / render_domain2.py: px∈{640,768,896}、size∈{14,18,22,26}、
             blur∈{0,1,2}、overlap∈{0,0.2,0.4}、GT∈{12,24,48,96,160}）**完全不同的新档**，
             避免复用同一批刺激：
                 px     ∈ {704, 832, 960}      （exp3: 640/768/896）
                 size   ∈ {16, 20, 24}         （exp3: 14/18/22/26）
                 blur   ∈ {0, 1}               （exp3: 0/1/2）
                 overlap∈ {0.1, 0.3}           （exp3: 0.0/0.2/0.4）
                 GT(非零) = 48（唯一档）        （exp3: 12/24/48/96/160）
                 目标词族 = 颜色+形状 4 族       （同 exp3 的四族用词，但**渲染参数不同**）
★ GT 由构造保证：真零图的 GT=0 是"被问目标一个都没画"的结果；非零图的 GT=48 是"恰好画满 48 个"的结果。
   ★ 真零图与非零图的 **px/size/blur/overlap 边缘分布完全相同**（同一组候选档、同一抽取方式，与 true_zero 无关），
   且**目标词族计数相同**（4 族 × 每族 150 真零 + 150 非零）；真零图的干扰族个数与对照图的目标个数同为 48，
   ⇒ "真零 vs 非零"只由**被问目标是否存在**决定，其余视觉负担匹配。渲染器结尾**回数落点**自检，任何泄漏即计失败数。
★ 固定种子 20261012（每个 item 另有派生 seed = 20261012 + i，逐图可重放）。
★ 输出（<out> 默认 /root/a56_2x2/pool）：
      images/t2x2_0001.png … images/t2x2_0600.png   盲名，不含任何条件/零点线索
      manifest.csv：item,target_word,count_gt,true_zero,size,blur,overlap,seed,px,sha256
★ 契约文本不在本件内（见 make_contracts_2x2.py），本件只做图像与 GT。
用法：
      python3 render_2x2.py [out_dir]
"""
import os
import io
import csv
import sys
import random
import hashlib

from PIL import Image, ImageDraw, ImageFilter

OUT = sys.argv[1] if len(sys.argv) > 1 else '/root/a56_2x2/pool'
SEED = 20261012
N_IMG = 600
N_ZERO = 300
N_NONZERO = 300
NONZERO_GT = 48                     # ★ 计数档（单一档，与真零图一一配对）

PX_CHOICES = (704, 832, 960)        # ★ 与 exp3 不同
SIZE_CHOICES = (16, 20, 24)         # ★ 与 exp3 不同
BLUR_CHOICES = (0, 1)               # ★ 与 exp3 不同
OVERLAP_CHOICES = (0.1, 0.3)        # ★ 与 exp3 不同

# 图面几何（画圆用直径近似；落点用"中心距"排斥实现 overlap 语义）
R_FACTOR = 0.40                     # 个体半径 = size * 0.40（直径 = 0.8*size）
MARGIN_FACTOR = 1.20                # 落点距边距 = size * 1.20
MAX_TRIES = 60                      # 单点最大重试次数

COLORS = {
    'red': (200, 40, 40),
    'blue': (40, 60, 200),
    'green': (40, 160, 70),
    'yellow': (210, 180, 40),
}
# ★ 目标词族：颜色+形状（与 exp3 同一组用词，便于跨实验对读；渲染参数不同）
FAMS = [
    ('red circles', 'circles', 'red'),
    ('blue squares', 'squares', 'blue'),
    ('green circles', 'circles', 'green'),
    ('yellow squares', 'squares', 'yellow'),
]
FAM_WORDS = [f[0] for f in FAMS]
# 颜色×形状的完整积（本语料只用其中 4 族；真零图的干扰族 = 积里"两维都不同"的族）
ALL_FORMS = [('circles', 'red'), ('circles', 'blue'), ('circles', 'green'), ('circles', 'yellow'),
             ('squares', 'red'), ('squares', 'blue'), ('squares', 'green'), ('squares', 'yellow')]


def build_distractor_map():
    """★ 真零图用的干扰族：给每个目标族配一个"颜色与形状都不同"的族
    （确定性：取排序后第一个合格族）—— 保证"被问目标不存在"不含歧义。"""
    out = {}
    for word, shape, color in FAMS:
        cand = sorted('%s %s' % (c, s) for (s, c) in ALL_FORMS if s != shape and c != color)
        out[word] = cand[0]
    return out


DISTRACTOR = build_distractor_map()          # 目标词 → 真零图干扰族词
DISTRACTOR_FORM = dict((w, tuple(reversed(DISTRACTOR[w].split()))) for w in DISTRACTOR)  # → (shape, color)


def spacing(size, overlap):
    """中心距阈值：overlap=0.1 → 1.54*size；overlap=0.3 → 1.22*size（越大越挤）。"""
    return size * (4.0 * R_FACTOR - overlap)


def draw_shape(dr, shape, x, y, size, fill):
    r = size * R_FACTOR
    box = [x - r, y - r, x + r, y + r]
    if shape == 'circles':
        dr.ellipse(box, fill=fill)
    else:
        dr.rectangle(box, fill=fill)


def scatter(dr, rnd, shape, color, k, px, size, overlap):
    """在同一张图上落 k 个 (shape,color) 个体；返回 (落点列表: [(x,y,r)], 失败数)。"""
    thr = spacing(size, overlap)
    marg = size * MARGIN_FACTOR
    lo = int(marg)
    hi = int(px - marg)
    placed = []
    failed = 0
    for _ in range(k):
        ok = False
        for _try in range(MAX_TRIES):
            x = rnd.randint(lo, hi)
            y = rnd.randint(lo, hi)
            if all(abs(x - ox) >= thr or abs(y - oy) >= thr for (ox, oy, _r) in placed):
                placed.append((x, y, size * R_FACTOR))
                draw_shape(dr, shape, x, y, size, COLORS[color])
                ok = True
                break
        if not ok:
            failed += 1
    return placed, failed


PH_FIELDS = [('px', PX_CHOICES), ('size', SIZE_CHOICES), ('blur', BLUR_CHOICES), ('overlap', OVERLAP_CHOICES)]


def balanced_param_plan(n_per_class, rnd):
    """★ 两类的 (px,size,blur,overlap) 组合**逐格完全相同**（不是"近似平衡"，也不是"同分布抽样"）：
    设 C = 36 个组合，每类 n=300 张 ⇒ 每类每个组合取 q=8 或 q+1=9 张（300 = 36×8 + 12）。
    把 9 张的那 12 个组合**同时**分给两类 ⇒ 两类的联合分布（以及一切边缘分布）逐格相等。
    每类内部顺序再洗牌（位置随机，避免"参数档成块出现"与图序混淆）。
    """
    combos = [(px, size, blur, ov)
              for px in PX_CHOICES for size in SIZE_CHOICES
              for blur in BLUR_CHOICES for ov in OVERLAP_CHOICES]
    c = len(combos)
    q, r = divmod(n_per_class, c)            # 300 = 36*8 + 12
    extra = set(range(r))                    # 前 r 个组合每类多 1 张
    half_a, half_b = [], []
    for k, cb in enumerate(combos):
        cnt = q + (1 if k in extra else 0)
        half_a.extend([cb] * cnt)
        half_b.extend([cb] * cnt)
    assert len(half_a) == n_per_class and len(half_b) == n_per_class, (len(half_a), len(half_b))
    assert sorted(half_a) == sorted(half_b)
    rnd.shuffle(half_a)
    rnd.shuffle(half_b)
    return half_a, half_b


def main():
    os.makedirs(os.path.join(OUT, 'images'), exist_ok=True)
    # 逐图种子（固定）：先定族与参数计划（E1/E2 两个独立种子流），再逐图重建 rnd 落点
    plan_rnd = random.Random(SEED)
    zero_plan, nonzero_plan = balanced_param_plan(N_ZERO, plan_rnd)

    rows = []
    render_fail = 0          # 落点失败（画不满）总数
    verify_fail = 0          # 回数自检失败（真零图混入被问目标 / 非零图数目不符）总数
    iz = 0
    inz = 0

    for i in range(N_IMG):
        item = 't2x2_%04d.png' % (i + 1)
        seed = SEED + i
        rnd = random.Random(seed)

        # ★ 真零图/非零图严格各半（i 偶=真零，i 奇=非零），族索引**各自独立推进**，
        #   使 4 个目标词族在两类里都各 150 张（word 与 true_zero 完全正交）
        true_zero = (i % 2 == 0)
        if true_zero:
            g_idx = iz % 4
            iz += 1
            px, size, blur, overlap = zero_plan[(iz - 1)]
        else:
            g_idx = inz % 4
            inz += 1
            px, size, blur, overlap = nonzero_plan[(inz - 1)]
        target_word, target_shape, target_color = FAMS[g_idx]

        img = Image.new('RGB', (px, px), (250, 250, 250))
        dr = ImageDraw.Draw(img)

        if true_zero:
            # ★ 被问目标**完全不画**：只画一个"颜色与形状都不同"的干扰族，个数 = 48（与对照图同负担）
            d_shape, d_color = DISTRACTOR_FORM[target_word]
            placed, failed = scatter(dr, rnd, d_shape, d_color, NONZERO_GT, px, size, overlap)
            target_drawn = 0
        else:
            # ★ 非零对照：只画目标族、恰好 NONZERO_GT 个（无干扰族，保证"目标存在且计数=48"）
            placed, failed = scatter(dr, rnd, target_shape, target_color, NONZERO_GT, px, size, overlap)
            target_drawn = len(placed)
        render_fail += failed

        if blur:
            img = img.filter(ImageFilter.GaussianBlur(blur))

        path = os.path.join(OUT, 'images', item)
        img.save(path)
        sha = hashlib.sha256(open(path, 'rb').read()).hexdigest()

        # ★ 构造自检（回数落点，不依赖眼睛）：
        #    真零图：被问目标的落点数必须 = 0；非零图：被问目标的落点数必须 = 48
        expect = 0 if true_zero else NONZERO_GT
        if target_drawn != expect:
            verify_fail += 1

        rows.append(dict(item=item, target_word=target_word, count_gt=(0 if true_zero else NONZERO_GT),
                         true_zero=int(true_zero), size=size, blur=blur, overlap=overlap,
                         seed=seed, px=px, sha256=sha))

    assert iz == N_ZERO and inz == N_NONZERO, (iz, inz)
    fields = ['item', 'target_word', 'count_gt', 'true_zero', 'size', 'blur', 'overlap', 'seed', 'px', 'sha256']
    man = os.path.join(OUT, 'manifest.csv')
    with io.open(man, 'w', encoding='utf-8', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow(r)

    # ---- 结尾打印：图像数 / 真零数 / 目标词分布 / GT 分布 / 失败数 ----
    words = sorted({r['target_word'] for r in rows})

    def dist(key, choices, z):
        return {c: sum(1 for r in rows if r['true_zero'] == z and r[key] == c) for c in choices}

    bal = {}
    for key, choices in PH_FIELDS:
        bal[key] = (dist(key, choices, 1), dist(key, choices, 0),
                    dist(key, choices, 1) == dist(key, choices, 0))
    words_bal = ({k: sum(1 for r in rows if r['true_zero'] == 1 and r['target_word'] == k) for k in words},
                 {k: sum(1 for r in rows if r['true_zero'] == 0 and r['target_word'] == k) for k in words})
    words_ok = words_bal[0] == words_bal[1]
    all_bal = all(v[2] for v in bal.values()) and words_ok

    print('[render_2x2] out=%s seed=%d' % (OUT, SEED))
    print('[render_2x2] 图像数 = %d（images/%s … %s）' % (len(rows), rows[0]['item'], rows[-1]['item']))
    print('[render_2x2] 真零数 = %d ｜ 非零数 = %d ｜ manifest = %s'
          % (sum(r['true_zero'] for r in rows), len(rows) - sum(r['true_zero'] for r in rows), man))
    print('[render_2x2] 目标词分布 = %s' % {k: sum(1 for r in rows if r['target_word'] == k) for k in words})
    print('[render_2x2] 目标词×真零 = %s'
          % {(k, z): sum(1 for r in rows if r['target_word'] == k and r['true_zero'] == z)
             for k in words for z in (1, 0)})
    print('[render_2x2] GT 分布 = %s' % {g: sum(1 for r in rows if r['count_gt'] == g)
                                         for g in sorted({r['count_gt'] for r in rows})})
    print('[render_2x2] 参数档 = px%s × size%s × blur%s × overlap%s'
          % (list(PX_CHOICES), list(SIZE_CHOICES), list(BLUR_CHOICES), list(OVERLAP_CHOICES)))
    for key, choices in PH_FIELDS:
        z, nz, ok = bal[key]
        print('[render_2x2] 平衡闸 %-8s 真零=%s 非零=%s ⇒ %s' % (key, z, nz, 'MATCH ✅' if ok else 'MISMATCH ❌'))
    print('[render_2x2] 平衡闸 target_word 真零=%s 非零=%s ⇒ %s'
          % (words_bal[0], words_bal[1], 'MATCH ✅' if words_ok else 'MISMATCH ❌'))
    print('[render_2x2] 真零图干扰族映射 = %s' % DISTRACTOR)
    print('[render_2x2] 失败数：落点失败 = %d ｜ 构造自检失败 = %d' % (render_fail, verify_fail))
    print('[render_2x2] sha256 唯一值 = %d（须 = 600，无重复图）'
          % len({r['sha256'] for r in rows}))
    print('[render_2x2] ★ 总闸门 = %s' % ('PASS' if (all_bal and render_fail == 0 and verify_fail == 0
                                                     and len(rows) == N_IMG
                                                     and len({r['sha256'] for r in rows}) == N_IMG)
                                          else 'FAIL'))


if __name__ == '__main__':
    main()
