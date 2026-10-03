# PaperB · P2-E 证据记录（§M.43 两个缺失旋钮的等水平重扫：detector 与 density-regression）— 2026-10-02

> **本文件的地位**：与 `E1_evidence_record.md`、`E2_evidence_record.md`、`E3_evidence_record.md`、
> `review_control_evidence.md`、`P0A_evidence_record.md` 并列，是**数字来源的权威之一**。
> 凡补充材料 §M.43 里 detector 与 density-regression 两行的数字，以本文件 + 放行件
> `data/derived/p2e_a800/` 的冻结 md5 为准。
> **放行落位**：`data/derived/p2e_a800/`（5 个阶梯/逐检测 CSV + rows/verdict）＋ `env/`（判据件、探针、
> 编排、分析器与 README）。判据件 md5 `e5f3…`（见 `env/p2e_criteria_frozen.json`）。

---

## 0 一句话结论

§M.43 原先写这两个旋钮 *"neither can be driven here — their weights are not on this machine — so they are
reported as **not measured**"*。本轮把**两个都驱动了**（同一批 182 张 ShanghaiTech-A、整幅、无平铺、
同一起服配置），**并如实报告两行都没有落座**：detector 是**地板效应**（零样本 COCO 在每个档位只回收标注计数的
**1–6%**，五档 span 仅 **4.60 pp**），density 的响应**随密度模型换号**（官方 DM-Count 五档 span **13.71 pp** 且**全程负**；
同一把尺换 **CSRNet** 则 **668.92 pp** 且从 1.25 档起**转正**）⇒ **该旋钮的响应是「旋钮 × 模型」的属性，不是旋钮单独的属性**。
两行**都不并入 §M.43 的排序**，该节的排序陈述**保持原有的较窄说法**。

## 1 实验设计

| 项 | 内容 |
|---|---|
| 缺哪个格 | §M.43 的六旋钮设计里，机上能驱动的是四个 VLM 旋钮；**detector（τ × 输入尺度）与 density-regression（输入尺度）两行从未跑过** |
| 池 | **冻结 182 项 ShanghaiTech-A（part_A_test）**；gt 由机上 `counts.csv` 规范化而成（`item,gt`，与图目录交集 **182/182**） |
| detector 半 | **yolo11n 整幅**（§D.1 的 dense 端仪器）× 输入尺寸 **640/896/1024/1280/1536**（短边），**置信阈值固定 0.25**（主档）＋ τ∈{0.05…0.9} × 五个尺寸（**65 格**）全网格 |
| density 半 | **该域官方 DM-Count**（`model_sh_A.pth`，86,005,202 B，sha256 `810ea89b…`）× 缩放乘子 **0.5/0.75/1.0/1.25/1.5**（主口径）；副口径 = 六档（+2.0）与短边 384/512/768/1024；**交叉核对支** = CSRNet/st_a 同五档 |
| 起服 | **一次**起服（detector 与 density 共用），GPU 单卡 A800；`workers=4`、`temperature 0`、`max_tokens 128`（逐字沿用 `pf_p0_probe.py`） |
| 调用数 | density 910×3 支 + detector 546（5 档 τ=0.25）+ 全网格 65 格；总计 ≈2,700 次前向，**用时 ~3 分钟** |

## 2 预注册判据与结果

| 判据 | 结果 |
|---|---|
| **C1** 每档 182 项 | **PASS**（全部档位 n=182） |
| **C2** detector span 与 §F.2 印值 30.0–90.0 pp 同量级 | **FAIL**（实测 **4.60 pp**） |
| **C3** density span 与 §F.2 印值 20.1–34.3 pp | **不作判定**：§F.2 那条是**逐 (knob × domain) isotonic 校准**量，本读数是**未校准池化**量 ⇒ **不可直比**（判据件已写明；本行主用途是进六旋钮排序） |
| **C4** 两支 density 口径是否同向 | **FAIL**：逐档 Spearman **0.10**、同号仅 **2/5** |
| **C5** 六旋钮排序 | **FAIL**：对**显式写死**的已发表序（§F.2 中点升序）Spearman **+0.2**，6 个里 **5 个不在原位** |

## 3 ★ 两个口径错误是 G0 自检抓出来的（留档，供复算者避免重犯）

跑前用 §M.43 已印的**四行**做阴性对照（G0），**第一次跑就不过**，查出三件事——**这三条是本节估计器的正确口径**：

1. **必须用"每档在它自己的 182 项上池化"**（`dev = 100(Σpred−Σgt)/Σgt`）。我原先用的是**各档 item 交集**口径
   （那是 A39 **校准**用的），它把 n 压到 53–118 且数值全错。
2. **不过滤任何行**（不加 `parse_ok=1/abstain=0/rep=1`）；机上每档恰好 182 行。
3. **档位顺序按印值声明的顺序**对位（output contract 的印序是 `base/choice/forbid0/neutral0/range`）。

修完后 G0 **四行逐档复现**（−54.4/72.0/107.1/−98.5/245.1 等，容差 0.05 pp，各档 n=182）⇒ **估计器与印值同源**，才允许开跑。
另 **G1**（缩放约定）也对既有件逐行反解锁定：`mult v ⇒ 两边 ×v`；`short v ⇒ 令 min(W,H)=v`（各 100% 命中）。

## 4 口径红线

1. 这两行**与 §M.43 上面四行不是同一次 session** ⇒ 该节 **3.01 pp 同 session 噪声底不适用**于它们。
2. **不使用代理**；旋钮驱动不了就记"未落座"。
3. density 行**必须带口径名**（official DM-Count / CSRNet）——§D.1 要求 official 与 reproduction 权重分报。
4. 整幅、无平铺；若日后跑平铺变体，那是**另一层**，**不得与本层并池**。

## 4.1 ★ 两处**放行件与记录的口径关系**（2026-10-03 补记，勘误性质）

1. **C5 的排序统计有两版基准。** 放行的 `p2e_rows.json` 是**基准修正之前**那次分析的产物，其
   `C5-ordering.spearman_vs_published = **−0.8286**`；本节第 2 节印的 **+0.2** 是**基准修正之后**
   （基准显式写死为 §F.2 各 knob 池化跨度的**中点升序**）由同一支分析器重跑得到的。
   两者不是矛盾，是**同一统计量在"基准未写死"与"基准写死"下的两个值**；**以 +0.2 为准**，
   且**排序结论（FAIL，6 个里 5 个不在原位）在两版下相同**。
2. **判定书曾被截断。** 首次放行的 `data/derived/p2e_a800/p2e_verdict.md` 只有 46 字节（脚本在写人读版时
   因一处键名残留中断）；现放行的是**完整版**（含两行 span、判据与口径红线），旧壳另名留档为
   `p2e_verdict.md.AUTHOR_MACHINE_PATHS_20261003`。逐格数据与 `p2e_rows.json` 自始完整、未被影响。

## 5 复算入口

```
python3 env/p2e_selfcheck_m43.py      # G0：用本包估计器复现 §M.43 四行（必须 G0_PASS 才继续）
python3 env/p2e_protocol_check.py --ladder <csrsta ladder> --sizes <st_a sizes>   # G1：缩放约定
python3 env/p2e_analyze.py            # 重算本记录第 2 节全部数字
```
逐检测原始件 `p2e_detector_raw.csv`（9.5 MB）含每一格的 per-box 置信度 ⇒ **τ 可事后换值重算**，无需再跑模型。
