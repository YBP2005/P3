# -*- coding: utf-8 -*-
"""render_a57.py —— 实验 1「预算匹配预注册复验」的**未用计数域**刺激渲染器（合成域）。

★ 本件**只渲染**（云端由上级执行）：不联网、不连任何机器、不调用任何服务、不下载任何东西。
★ 未用域声明：本域是**我方合成的计数域，不是公开基准**（预注册 §2）。参数区间与既有语料
  （exp3 `render_a55.py` / `render_domain2.py`：px∈{640,768,896}、size∈{14,18,22,26}、
   blur∈{0,1,2}、overlap∈{0,0.2,0.4}、GT∈{12,24,48,96,160}；A5-6 `render_2x2.py`：
   px∈{704,832,960}、size∈{16,20,24}、blur∈{0,1}、overlap∈{0.1,0.3}、GT=48）
  **不重合**：px∈{640,704,832}（与 2x2 只共 704/832，但 blur=0 全程关掉、overlap=0.25
  为该两族都没用过的档、size 由 0.020·px 派生 ⇒ 逐项 (px,size,blur,overlap) 组合均为新组合）。

## 单元与档（**冻结**；与 PREREGISTRATION.md §3 一字不差）
  单元 = (家族, knob)；档 = knob 的 3 级。**同一 knob 的各级共用同一批 item 主干名**：
    * knob = density：档 ∈ {24, 30, 36}（= 每图目标数），画布固定 px=832；item 名**不带档**，
      ⇒ 三档同名；三档**逐档渲染**（GT 就是画了几个），同 seed ⇒ 三张图互相嵌套（低档是高阶前缀）。
      size 固定 14，blur=0，overlap=0.25。
      ★ 声明：本 knob 的"成本"是**声明代理** ceil(d/8)（计数算力位数块），不是真实延迟。
    * knob = res：档 ∈ {640, 704, 832}（像素数），目标数固定 48，size = round(0.020·px) ∈ {13,14,17}，
      blur=0，overlap=0.25；同 item 的图在不同 px 下**重渲**（seed/GT 逐级相同 ⇒ 场景同一）。
      ★ 声明：此时 span 是"像素档 + 重渲"的合成效应，不是纯像素效应（预注册 §8 已列此限制）。
  ⇒ 每 item 出 **3（density 名，同一文件）+ 3（res 名，三个像素档）= 6 个文件**。

## 输出（<out> 默认 ./pool）
    images/den_0000.png …                     （density 名：832×832 ×3 档，同名不同内容，互相嵌套）
    images/res_0000_px640.png / _px704.png / _px832.png   （res：item 名 res_0000.png 恒定，物理文件带 px）
    manifest.csv：item,target_word,count_gt,knob,level,px,seed,sha256,image  ← item=逻辑名（同 knob 各级同名）
    contracts.csv：item,knob,level,count_gt,px,prompt                 ← 交给 run_a57.sh 的契约表
★ GT 由构造保证（画几个就是几个；渲染器结尾回数落点自检，任何失败即打印出来）。
★ 固定种子 SEED=20261011，每 item 派生 seed = SEED + i（逐图可重放）。

用法：
    python render_a57.py [out_dir] [--per-knob 200]
"""
import argparse
import csv
import hashlib
import io
import os
import random
import sys

from PIL import Image, ImageDraw

SEED = 20261011
PER_KNOB = 200                       # 每 knob 的 item 数（100 图/格 × 3 档共用同一批名）
DENSITY_LEVELS = (24, 30, 36)        # 档 = 目标数
RES_LEVELS = (640, 704, 832)         # 档 = 像素数
DENSITY_CANVAS_PX = 832              # density knob 的画布（固定；成本由 ceil(d/8) 声明）
RES_COUNT = 48                       # res knob 的目标数（固定）
DENSITY_SIZE = 14                    # density knob 的个体尺寸（固定）
BLUR = 0                             # 全程无模糊（与两族既有语料的 blur 档都不同组合）
OVERLAP = 0.25                       # 与 exp3 {0,0.2,0.4} / 2x2 {0.1,0.3} 均不同
R_FACTOR = 0.40
MARGIN_FACTOR = 1.20
MAX_TRIES = 80
BG = (250, 250, 250)
COLORS = {'red': (200, 40, 40), 'blue': (40, 60, 200),
          'green': (40, 160, 70), 'yellow': (210, 180, 40)}
WORDS = (('red circles', 'circles', 'red'),
         ('blue squares', 'squares', 'blue'),
         ('green circles', 'circles', 'green'),
         ('yellow squares', 'squares', 'yellow'))


def spacing(size):
    """中心距阈值：overlap=0.25 ⇒ 1.35·size。"""
    return size * (4.0 * R_FACTOR - OVERLAP)


def draw_one(dr, shape, x, y, size, fill):
    r = size * R_FACTOR
    box = [x - r, y - r, x + r, y + r]
    if shape == 'circles':
        dr.ellipse(box, fill=fill)
    else:
        dr.rectangle(box, fill=fill)


def scatter(dr, rnd, shape, color, k, px, size):
    """在同一张图上落 k 个个体；返回 (实际落点数, 失败数)。落点规则与既有语料一致。"""
    thr = spacing(size)
    marg = size * MARGIN_FACTOR
    lo, hi = int(marg), int(px - marg)
    placed, failed = 0, 0
    pts = []
    for _ in range(k):
        ok = False
        for _try in range(MAX_TRIES):
            x = rnd.randint(lo, hi)
            y = rnd.randint(lo, hi)
            if all(abs(x - ox) >= thr or abs(y - oy) >= thr for (ox, oy) in pts):
                pts.append((x, y))
                draw_one(dr, shape, x, y, size, COLORS[color])
                placed += 1
                ok = True
                break
        if not ok:
            failed += 1
    return placed, failed


def prompt_for(word, count_gt, px):
    """真实契约（含目标词与图像尺寸），与 A5 系列 text-first 形态一致。"""
    return ('Count the %s in this image. Answer with a single JSON object of the form '
            '{"count": <integer>} and nothing else. The image is %d by %d pixels.' % (word, px, px))


def render_density(outdir, words_rows, render_fail):
    """density knob：每个 item 在三个目标数档各渲一张（832×832，同 seed、各档恰好画满该档数目）。

    ★ 为什么必须逐档渲而不是共用一张图：GT 就是"画了几个"。若共用一张 36 个目标的图而把
      低档的 GT 写成 24，**构造 GT 就错了**（完美计数者也会被记成大误差）。
      ⇒ 逐档渲染；同 item 同 seed ⇒ 各档图像**互相嵌套**（低档的落点集是高阶的前缀），
        这一点由 seed 复用保证（见 PREREGISTRATION.md §3.3）。
    """
    rows, contracts = [], []
    for i in range(PER_KNOB):
        word, shape, color = WORDS[i % 4]
        seed = SEED + i
        for lv in DENSITY_LEVELS:
            img = Image.new('RGB', (DENSITY_CANVAS_PX, DENSITY_CANVAS_PX), BG)
            dr = ImageDraw.Draw(img)
            rnd = random.Random(seed)               # 同 seed ⇒ 同一条落点序列
            placed, failed = scatter(dr, rnd, shape, color, lv, DENSITY_CANVAS_PX, DENSITY_SIZE)
            render_fail += failed
            item = 'den_%04d.png' % i          # ★ 同 knob 各档共用同一 item 名（M.45 的公共 item 交集）
            path = os.path.join(outdir, 'images', item)
            img.save(path)
            sha = hashlib.sha256(open(path, 'rb').read()).hexdigest()
            assert placed == lv, 'density item %s 落点失败：%d/%d' % (item, placed, lv)
            rows.append(dict(item=item, target_word=word, count_gt=lv, knob='density',
                             level=str(lv), px=DENSITY_CANVAS_PX, seed=seed, sha256=sha,
                             image='images/' + item))
            contracts.append(dict(item=item, knob='density', level=str(lv), count_gt=lv,
                                  px=DENSITY_CANVAS_PX,
                                  prompt=prompt_for(word, lv, DENSITY_CANVAS_PX)))
    return rows, contracts, render_fail


def render_res(outdir, render_fail):
    """res knob：每个 item 在三个像素档各渲一张（同 seed、同目标数 ⇒ 场景同一、字节不同）。"""
    rows, contracts = [], []
    for i in range(PER_KNOB):
        word, shape, color = WORDS[i % 4]
        seed = SEED + 100000 + i
        for px in RES_LEVELS:
            size = max(6, int(round(0.020 * px)))    # 640→13 / 704→14 / 832→17
            img = Image.new('RGB', (px, px), BG)
            dr = ImageDraw.Draw(img)
            rnd = random.Random(seed)                # 同 seed ⇒ 同一场景序列（重渲）
            placed, failed = scatter(dr, rnd, shape, color, RES_COUNT, px, size)
            render_fail += failed
            item = 'res_%04d.png' % i          # ★ item 名不带档（公共 item 交集靠它）
            fn = 'res_%04d_px%d.png' % (i, px)   # 物理文件名带 px（三档三文件）
            path = os.path.join(outdir, 'images', fn)
            img.save(path)
            sha = hashlib.sha256(open(path, 'rb').read()).hexdigest()
            assert placed == RES_COUNT, 'res item %s 落点失败：%d/%d' % (item, placed, RES_COUNT)
            rows.append(dict(item=item, target_word=word, count_gt=RES_COUNT, knob='res',
                             level='px%d' % px, px=px, seed=seed, sha256=sha,
                             image='images/' + fn))
            contracts.append(dict(item=item, knob='res', level='px%d' % px, count_gt=RES_COUNT,
                                  px=px, prompt=prompt_for(word, RES_COUNT, px)))
    return rows, contracts, render_fail


def main():
    global PER_KNOB
    ap = argparse.ArgumentParser()
    ap.add_argument('out', nargs='?', default='./pool')
    ap.add_argument('--per-knob', type=int, default=PER_KNOB)
    args = ap.parse_args()
    PER_KNOB = args.per_knob

    out = args.out
    os.makedirs(os.path.join(out, 'images'), exist_ok=True)
    render_fail = 0
    rows, contracts = [], []
    r1, c1, render_fail = render_density(out, None, render_fail)
    r2, c2, render_fail = render_res(out, render_fail)
    rows += r1 + r2
    contracts += c1 + c2

    # ---- 逐件同 sha256 自检（density：三档必须同 sha；res：三档必须互异）----
    by = {}
    for r in rows:
        by.setdefault((r['knob'], r['item']), {})[r['level']] = r
    bad_same, bad_distinct, bad_size = 0, 0, 0
    for (knob, item), d in by.items():
        if knob != 'density':
            continue
        # density：各档**必须不同 sha**（GT 就是画了几个 ⇒ 逐档渲染），但**必须同 seed 与同画布**
        # ⇒ 各档图像互相嵌套（低档落点集是高阶前缀），这是本域"同 item 换档"的可核查代理。
        if len({v['sha256'] for v in d.values()}) != len(DENSITY_LEVELS):
            bad_same += 1
        if len({v['seed'] for v in d.values()}) != 1 or len({v['px'] for v in d.values()}) != 1:
            bad_size += 1
    for (knob, item), d in by.items():
        if knob == 'res' and len({v['sha256'] for v in d.values()}) != len(RES_LEVELS):
            bad_distinct += 1

    man = os.path.join(out, 'manifest.csv')
    fields = ['item', 'target_word', 'count_gt', 'knob', 'level', 'px', 'seed', 'sha256', 'image']
    with io.open(man, 'w', encoding='utf-8', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow(r)
    cpath = os.path.join(out, 'contracts.csv')
    with io.open(cpath, 'w', encoding='utf-8', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=['item', 'knob', 'level', 'count_gt', 'px', 'prompt'])
        w.writeheader()
        for c in contracts:
            w.writerow(c)

    print('[render_a57] out=%s ｜ seed=%d ｜ 每 knob item 数=%d' % (out, SEED, PER_KNOB))
    print('[render_a57] manifest 行 = %d（%d 行 density + %d 行 res）｜ 图像文件 = %d'
          % (len(rows), len(r1), len(r2),
             len({r['item'] for r in rows})))
    print('[render_a57] density 档 = %s（画布 %d，size=%d, blur=%d, overlap=%.2f）｜ GT/档 = 档值本身'
          % (list(DENSITY_LEVELS), DENSITY_CANVAS_PX, DENSITY_SIZE, BLUR, OVERLAP))
    print('[render_a57] res 档 = %s（目标数 %d，size = round(0.020·px) = %s, blur=%d, overlap=%.2f）'
          % (list(RES_LEVELS), RES_COUNT,
             [max(6, int(round(0.020 * p))) for p in RES_LEVELS], BLUR, OVERLAP))
    print('[render_a57] GT 分布 = %s'
          % {g: sum(1 for r in rows if r['count_gt'] == g)
             for g in sorted({r['count_gt'] for r in rows})})
    print('[render_a57] 自检：density 各档 sha 未全异的 item = %d（须 0）｜ density seed/画布不一致 = %d（须 0）'
          '｜ res 各档 sha 未全异的 item = %d（须 0）' % (bad_same, bad_size, bad_distinct))
    print('[render_a57] 失败数：落点失败 = %d' % render_fail)
    print('[render_a57] manifest -> %s ｜ contracts -> %s' % (man, cpath))
    return 0 if (bad_same == 0 and bad_size == 0 and bad_distinct == 0 and render_fail == 0) else 5


if __name__ == '__main__':
    sys.exit(main())
