# -*- coding: utf-8 -*-
"""_repro_root.py —— 复现包／工作树的**统一根**（release root）。

第三方把本仓库解到**任意目录**后直接跑 `code/analysis/*.py` 即可：脚本里所有数据路径都
经由本模块解析，不再依赖作者的机器布局。

根按此顺序确定：
  1. 环境变量 `PAPERB_ROOT`（显式指定优先）；
  2. 由本文件位置反推 —— 放行树 `<root>/code/analysis/` 与作者树 `<root>/analysis/work/`
     **都是上两级**，故同一段代码在两种布局下都对；
  3. 再向上找带 `data/` 或 `code/` 的目录。

`resolve(*parts)`（脚本里以 `RP` 引入）按**作者树相对路径**给路径，例如
`resolve('analysis', 'work', 'f9_quoted.json')`：
  · 作者工作树上该路径存在（或整体就是作者树）⇒ 原样返回，**行为与本次改动前逐字一致**；
  · 否则套用下面的「前缀映射表」，落到放行包里的等价位置。

`not_released(*parts)`（脚本里以 `NR` 引入）用于**未随包发布**的作者侧路径：
  · 作者树上原样可用；
  · 其它机器上返回 `PAPERB_ROOT/_NOT_RELEASED/<tag>` —— 一个**故意不存在**的路径，
    使调用方的 `open()` / `os.path.isdir()` 照常失败并报出可读的文件名，
    而不是悄悄指到另一棵自己造出来的树。

前缀映射表的每一条都在 2026-09-30 的 v0608 轮用**文件名集合逐一比对**实测过
（`analysis/<X>` 与放行树对应目录的递归文件名集合相等，或为实测的包含关系）。
"""
import os
import re

_HERE = os.path.dirname(os.path.abspath(__file__))
_UP2 = os.path.dirname(os.path.dirname(_HERE))

# 作者工作树是否就在眼前：判据是 `<root>/analysis/work/`（放行树里没有这一层）。
# 它决定 `resolve()`/`not_released()` 走"作者树原样"还是走"映射表"。
AUTHOR_TREE = os.path.isdir(os.path.join(_UP2, 'analysis', 'work'))


def _infer():
    for c in (_UP2, _HERE):
        if (os.path.isdir(os.path.join(c, 'data'))
                or os.path.isdir(os.path.join(c, 'code'))
                or os.path.isdir(os.path.join(c, 'analysis'))):
            return c
    return _UP2


ROOT = os.environ.get('PAPERB_ROOT') or _infer()

# 作者机的**共享语料盘**（`E:\Edu_workplace` 一类）：本论文之外的东西，未随包发布。
# 它以前以盘符字面量散落在 10 余个脚本里；现在只在这一个地方出现，且可用环境变量覆盖。
SHARED = os.environ.get('PAPERB_SHARED') or 'E:/Edu_workplace'

# ── 作者树相对路径前缀 -> 放行树相对路径前缀（按段数从长到短匹配）────────────────
_ALIAS = (
    # `sync_repro.py` 的落点，逐条实测
    ('analysis/work', 'code/analysis'),
    # ★ 2026-10-08（v0663）：作者机**共享语料盘**下的两个校准阶梯件已随本轮放行
    #   （`data/derived/unit_ladders/`）。它们是 `a39_unit_calib_heldout.py` 的 36-unit 单元集里
    #   此前**未随包发布**的 5 个单元的来源（官方 DM-Count ×2；BBBC005 ×3）。
    #   作者树上这两条路径实存 ⇒ `resolve()` 第一步就返回真实路径，**行为与本次改动前逐字一致**。
    ('@shared/work/b_harvest_20260917/bbbc_eval', 'data/derived/unit_ladders/bbbc_eval'),
    ('@shared/work', 'data/derived/unit_ladders'),
    ('analysis/e2xt_a800', 'data/derived/e3'),
    ('analysis/e1_results_census', 'data/derived/e3/zero'),
    ('analysis/e1_results_nonzero', 'data/derived/e3/nonzero'),
    ('analysis/e1_5090/corpus', 'data/derived/corpus'),
    ('analysis/e1_5090', 'data/derived/e1'),
    ('analysis/e2_5090', 'data/derived/e2'),
    ('analysis/e2_h20', 'data/derived/e2'),
    ('analysis/e2_newh20/logs_h20_v7c', 'env/h20_v7c_logs'),
    ('analysis/e2_newh20', 'data/derived/e2'),
    ('analysis/fsc_res', 'data/derived/fsc_res'),
    ('analysis/fsc_a800', 'data/derived/fsc_res/frozen384'),
    ('analysis/ea2_z0', 'data/derived/ea2'),
    ('analysis/A_res_20260928', 'data/derived/A_res_20260928'),
    ('analysis/B_res_20260928', 'data/derived/B_res_20260928'),
    ('analysis/h20_rescue_20260922/extract', 'data/derived/e2_pools'),
    # ★ 2026-10-06（v0653）：`pod_mirror` 是**整棵语料镜像**，而放行树把它**按子目录平铺**到
    #   `data/derived/<子目录>`；旧表只有最后那一条 `pod_mirror -> data/derived/pA`，而 `pA`
    #   只是 20 件受控网格输入（`b2__out_*_blurct` / `*_occlct` / `ivl_blurct`），**不含**任何
    #   `vlm_/aer_/ext_` 结果。于是 `resolve('analysis','data','pod_mirror','dense_results', ...)`
    #   落到一条**不存在**的 `data/derived/pA/dense_results/...`。
    #   实测后果：`p4_decomp_verify.py` 在放行树上 `os.walk` 命中 **0** 份，
    #   并在 §5.11(a) 复现段 `FileNotFoundError` ⇒ 附录 J.1 的「136 / 131」在包内**不可复算**。
    #   下表每条都按 `sync_repro.py` 的落点实测：作者树子目录与放行树同名子目录**逐文件比对**，
    #   作者侧文件**全部**都在放行侧（覆盖率 100%）。映射按段数从长到短匹配 ⇒ 这些更长前缀先命中；
    #   `pA` 那 5 个子目录**不在**下表里，仍由最后那条兜底映射接住，行为一字不变。
    ('analysis/data/pod_mirror/abstain_results', 'data/derived/abstain_results'),
    ('analysis/data/pod_mirror/aerial_results', 'data/derived/aerial_results'),
    ('analysis/data/pod_mirror/aerial_tile_results', 'data/derived/aerial_tile_results'),
    ('analysis/data/pod_mirror/b2__out_32b_ctile', 'data/derived/b2__out_32b_ctile'),
    ('analysis/data/pod_mirror/b2__out_8b_ctile', 'data/derived/b2__out_8b_ctile'),
    ('analysis/data/pod_mirror/decouple_results', 'data/derived/decouple_results'),
    ('analysis/data/pod_mirror/dense_prompt_results', 'data/derived/dense_prompt_results'),
    ('analysis/data/pod_mirror/dense_results', 'data/derived/dense_results'),
    ('analysis/data/pod_mirror/dose_results', 'data/derived/dose_results'),
    ('analysis/data/pod_mirror/dose_tile_results', 'data/derived/dose_tile_results'),
    ('analysis/data/pod_mirror/e4_results', 'data/derived/e4_results'),
    ('analysis/data/pod_mirror/e8b_aerial', 'data/derived/e8b_aerial'),
    ('analysis/data/pod_mirror/e8b_results', 'data/derived/e8b_results'),
    ('analysis/data/pod_mirror/ext_results', 'data/derived/ext_results'),
    ('analysis/data/pod_mirror/ivl_abstain_results', 'data/derived/ivl_abstain_results'),
    ('analysis/data/pod_mirror/ivl_aerial_results', 'data/derived/ivl_aerial_results'),
    ('analysis/data/pod_mirror/ivl_aerial_tile_results', 'data/derived/ivl_aerial_tile_results'),
    ('analysis/data/pod_mirror/ivl_dense_prompt_results', 'data/derived/ivl_dense_prompt_results'),
    ('analysis/data/pod_mirror/ivl_dense_results', 'data/derived/ivl_dense_results'),
    ('analysis/data/pod_mirror/ivl_dose_results', 'data/derived/ivl_dose_results'),
    ('analysis/data/pod_mirror/ivl_dose_tile_results', 'data/derived/ivl_dose_tile_results'),
    ('analysis/data/pod_mirror/ivl_e4_results', 'data/derived/ivl_e4_results'),
    ('analysis/data/pod_mirror/ivl_ext_results', 'data/derived/ivl_ext_results'),
    ('analysis/data/pod_mirror/ivl_occl_results', 'data/derived/ivl_occl_results'),
    ('analysis/data/pod_mirror/ivl_person_results', 'data/derived/ivl_person_results'),
    ('analysis/data/pod_mirror/ivl_ref_results', 'data/derived/ivl_ref_results'),
    ('analysis/data/pod_mirror/ivl_selfconsist_results', 'data/derived/ivl_selfconsist_results'),
    ('analysis/data/pod_mirror/legigap_results', 'data/derived/legigap_results'),
    ('analysis/data/pod_mirror/occl_results', 'data/derived/occl_results'),
    ('analysis/data/pod_mirror/occl_results_8b', 'data/derived/occl_results_8b'),
    ('analysis/data/pod_mirror/person_results', 'data/derived/person_results'),
    ('analysis/data/pod_mirror/q25_aerial_results', 'data/derived/q25_aerial_results'),
    ('analysis/data/pod_mirror/q25_dense_results', 'data/derived/q25_dense_results'),
    ('analysis/data/pod_mirror/res_ctrl__ivl', 'data/derived/res_ctrl__ivl'),
    ('analysis/data/pod_mirror/res_ctrl__q32', 'data/derived/res_ctrl__q32'),
    ('analysis/data/pod_mirror/selfconsist_results', 'data/derived/selfconsist_results'),
    ('analysis/data/pod_mirror/selfconsist_results_8b', 'data/derived/selfconsist_results_8b'),
    ('analysis/data/pod_mirror/t2_results', 'data/derived/t2_results'),
    ('analysis/data/pod_mirror/t2_results_32b', 'data/derived/t2_results_32b'),
    ('analysis/data/pod_mirror/tile_results', 'data/derived/tile_results'),
    # ★ 2026-10-06（v0654）：`pod_mirror/A` 与 `pod_mirror/B` 是**另两个平铺子目录**，放行树落成
    #   `data/derived/A`（实测 3 件；作者侧 9 件里只有这 3 件随包，其余 6 件是**同内容的重命名副本**
    #   与未放行件，`st_a` 那一条另在 `data/derived/p2e_a800/`）。旧表没有这条 ⇒ `resolve(...)`
    #   落到兜底的 `data/derived/pA/A/…`（不存在）⇒ `f10_grid8_declared.py` **开箱即崩**：
    #   `FileNotFoundError: …\data\derived\pA\A\det_yolo_ladder_yolo12n.csv`。
    #   实测：A 的作者侧 3 个已放行件与 `data/derived/A` 同名件 **md5 逐一相同**、无只在一侧的件；
    #   `B` 的唯一件（`visdrone_det.pt`）**不在放行树**，故**不给 B 加别名**（加了只会把一个
    #   不存在的路径换成另一个不存在的路径，不产生信息）。
    ('analysis/data/pod_mirror/A', 'data/derived/A'),
    # ★ 2026-10-06（v0654）：两件**先前未放行的阶梯输入**。README 的"如何复现主要结果"一表把
    #   §7.3 的"跨度不是扫描网格的函数（24 个 knob×域单元）"挂在 `code/analysis/span_equalcount2.py`
    #   **over `data/derived/`** 上，而该脚本的 ① 检测 τ 阶梯与 ② 密度回归阶梯读的正是这两件；
    #   它们此前只走 `not_released()` ⇒ 放行树上**静默少掉 10 个单元**（24 → 14），
    #   且 `_f10_random_drop.py` 直接崩在 `NR(...)` 上。两件都只有 5,792 / 10,151 字节，
    #   是**既有派生产物的逐字节副本**（不新造数据、不新增任何调用），故放行。
    ('analysis/data/threeway_curves_v2.csv', 'data/derived/threeway_curves_v2.csv'),
    ('analysis/data/threeway_curves.csv', 'data/derived/threeway_curves.csv'),
    ('analysis/data/pod_mirror', 'data/derived/pA'),
    # ★ 2026-10-06（v0654）：三条**脚本件**的映射。`prompt_features.py` 要读三个"驱动脚本"来取
    #   提示词原文（`19e_probe_multi.py` 的 `P`、`probe_gen.py` 的 `PROMPTS`、
    #   `19c_probe_paraphrase.py` 的换措辞臂），而它们随包发布在 `code/experiments/**` **而不是**
    #   作者侧的那几个目录 ⇒ 旧写法（`PAPER/analysis/…` 硬拼）在放行树上必崩/静默少读。
    ('analysis/work/19e_probe_multi.py', 'code/experiments/19e_probe_multi.py'),
    ('analysis/pod_evidence/scripts/probe_gen.py', 'code/experiments/probe_gen.py'),
    ('analysis/h20_rescue_20260922/extract/19c_probe_paraphrase.py',
     'code/experiments/h20_e2_scripts/19c_probe_paraphrase.py'),
    ('analysis/figures', 'figures'),
    ('analysis/g2_neutral0', 'data/derived/g2_neutral0'),
    ('analysis/p2_a800', 'data/derived/p2_noise4'),
    ('analysis/p1_results_w5', 'data/derived/p1/csv'),
    ('analysis/p1b_results2', 'data/derived/p1b/csv'),
    ('analysis/p1c_results', 'data/derived/p1c/csv'),
    ('analysis/p1d_results', 'data/derived/p1df/csv'),
    ('analysis/p5c_results', 'data/derived/p5c'),
    ('analysis/p5a_results_ml16384', 'data/derived/p5b/csv'),
    ('analysis/ctxctrl/ctxctrl_result.json', 'code/analysis/ctxctrl_result.json'),
    ('analysis/m5090_archive/unpacked_all/root/dense_results', 'data/derived/dense_results'),
    ('analysis/m5090_archive/unpacked_all/root/tile_results', 'data/derived/tile_results'),
    ('analysis/m5090_archive/unpacked/dense/shanghaitech/counts.csv',
     'data/gold/shanghaitech_counts.csv'),
    ('analysis/m5090_archive/unpacked/dense/ucf_qnrf/counts.csv',
     'data/gold/ucf_qnrf_counts.csv'),
    # 整棵复现仓库自身 / 权威稿
    ('repro_github', ''),
    ('PaperB_英文稿_PR_20260919.md', 'manuscript/PaperB_manuscript_EN.md'),
    ('PaperB_英文补充材料_PR_20260919.md', 'manuscript/PaperB_supplementary_EN.md'),
    ('PaperB_E1证据_20260920.md', 'manuscript/E1_evidence_record.md'),
    ('measurement_pr_docx.json', 'manuscript/pagination_measurement.json'),
)
_ALIAS = tuple(sorted(_ALIAS, key=lambda kv: -len(kv[0].split('/'))))


def _join(parts):
    """把 parts 拼成绝对路径。首元素可以是 `@up1`（ROOT 的上一级）、`@shared`（共享语料盘），
    或一个带盘符的绝对路径。"""
    parts = [str(p) for p in parts]
    if not parts:
        return ROOT
    head = parts[0]
    if head == '@up1':
        return os.path.normpath(os.path.join(os.path.dirname(ROOT), *parts[1:]))
    if head == '@shared':
        return os.path.normpath(os.path.join(SHARED.replace('/', os.sep), *parts[1:]))
    if len(head) > 1 and head[1] == ':':
        return os.path.normpath(os.path.join(head.replace('/', os.sep), *parts[1:]))
    return os.path.normpath(os.path.join(ROOT, *parts))


def _mapped(parts):
    """放行树相对路径；不可映射（盘符路径、无别名命中）返回 None。

    ★ 2026-10-08（v0663）：`@shared`（作者机共享语料盘）**也走别名表** —— 但只在
      `resolve()` 里（`_join` 落到的真实路径不存在之后）。新增的 `@shared/...` 别名条目
      把**已经随包放行的两个校准阶梯件**接上（`data/derived/unit_ladders/`），从而
      `a39_unit_calib_heldout.py` 的 36-unit 单元集在放行树上**不再缺那 5 个单元**。
      在此之前 `@shared` 一律 return None（→ 落 `_NOT_RELEASED/`，故意不存在），
      故本改动对**其它** `@shared` 路径的行为不变：没有别名命中时仍返回 None。
      ★ 作者树侧完全不受影响：`resolve()` 在作者树上第一步就返回 `_join(parts)`（实测存在）。
    """
    parts = [str(p) for p in parts]
    if not parts or (len(parts[0]) > 1 and parts[0][1] == ':'):
        return None
    rel = '/'.join(parts)
    for a, b in _ALIAS:
        if rel == a or rel.startswith(a + '/'):
            tail = rel[len(a):].lstrip('/')
            return (b + '/' + tail).strip('/') if b else tail
    return None


def resolve(*parts):
    """作者树相对路径 -> 可用绝对路径（作者树上原样；否则查映射表）。"""
    if AUTHOR_TREE:
        return _join(parts)
    p = _join(parts)
    if os.path.exists(p):
        return p
    rel = _mapped(parts)
    if rel is None:
        return p
    return os.path.join(ROOT, *rel.split('/')) if rel else ROOT


def not_released(*parts):
    """**未随包发布**的作者侧路径。作者树上原样可用；否则返回 `_NOT_RELEASED/` 下的标记路径。"""
    if AUTHOR_TREE:
        return _join(parts)
    p = _join(parts)
    if os.path.exists(p):
        return p
    tag = re.sub(r'[^0-9A-Za-z_.\u4e00-\u9fff-]+', '-', '_'.join(str(x) for x in parts))
    return os.path.join(ROOT, '_NOT_RELEASED', tag.strip('-'))


# 兼容：本模块自身也供"只想拿根"的调用方使用
REPO_ROOT = ROOT
