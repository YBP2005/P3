# A5-2 API 臂 — 分析件清单（analysis manifest）

本件记录**可追溯性**：输入件的字节级身份、行数、脚本路径、缺失格清单、以及本次分析
与既有冻结件的**一致性核验**。所有数字由 `_api_analysis_raw.json` 逐字导出。

| 项 | 值 |
|---|---|
| 分析对象 | A5-2「计数 × 可读性正交冻结刺激」API 对照臂（6 个 API 模型） |
| 生成时间（本地） | 2026-10-07 22:27:06 |
| 刺激集 | 与本地臂**同一批** 648 张 PNG（逐位配对；本次未重渲染、未缩放） |

## 1. 输入件（只读，未改动）

| 文件 | md5 | 行数/规模 | 说明 |
|---|---|---|---|
| `merged_best.jsonl` | `a32bcdf21c03129169df678f1ff8fed1` | 34992 行 | 每行 = 一格（同一 `key` 的最佳尝试，优先 `http==200`） |
| `_a52_criteria_frozen.json` | `758962a2643e1035698682abefec5748` | — | 冻结判据件（档位线 / β 定义 / C4 判决规则） |
| `detection_matrix.csv` | `67688d5f212086abe32cae914a2447ac` | 81 格 × 8 布局 | 每图 `n_dots_detected_gt`（独立来源） |
| `stim/manifest.csv`（源包副本） | `d2dde2a8100eca8eda88143f6cbb04ba` | 648 行 | 每图 `count_gt` / `n_dots_detected_gt` / `radius,blur,overlap` |
| `MANIFEST.tsv` | — | 702 行 | 源包逐件清单（含 `stim/manifest.csv` 的 md5） |
| `README_实验说明.md` | — | — | 实验说明（计数口径、三合同提示词） |
| `manifest.csv` | — | **0 字节（空）** | ★ 见 §5「冲突与限度」第 1 条 |
| 本地基线结果 | b0/b2：`_a5_2/_a800_a52/res/A52_{b0,b2}_{base,strict,permit}_s{1,2,3}.csv`；b1：`_a5_2/_a800_a52_ext/a52__res__A52_b1_*.csv` | 27 格 × 648 = 17,496 行 | 与 API 臂**同判据**复算的并列基线 |

复算逐件 md5（本次实算）：

```
a32bcdf21c03129169df678f1ff8fed1  merged_best.jsonl
758962a2643e1035698682abefec5748  _a52_criteria_frozen.json
67688d5f212086abe32cae914a2447ac  detection_matrix.csv
d2dde2a8100eca8eda88143f6cbb04ba  a52__stim__manifest.csv
```

## 2. 脚本路径（**运行本次分析的全部代码**）

| 脚本 | md5 | 作用 |
|---|---|---|
| `[author-workdir]\_a52_api_work\_a52_api_analyze.py` | `b353d545621b122c406b305db28dbbd2` | 主驱动：读 `merged_best.jsonl` + 冻结判据 + manifest + detection_matrix；逐档 / β / C4 / C5 / 重复一致性 / 分层 / 抽检；写 3 个 CSV 与 `_api_analysis_raw.json` |
| `[author-workdir]\_a52_api_work\_mk_md.py` | `9e9f074f8c1b65e6fd99b6ac10422034` | 由 `_api_analysis_raw.json` 导出 markdown 表块（供报告粘贴，保证数字不转写错） |
| `[author-workdir]\_a52_api_work\_mk_reports.py` | `2f09a4c09d84747ee782f5b786974f65` | 由 `_api_analysis_raw.json` 生成 `API_six_implementations_analysis.md` 与本件 |
| `data/derived/a5_2_a800/env/a52_analyze.py` | `77f87f49b0e447fba54ea2a0435f80c8` | ★ **frozen analyzer as shipped**（机上实跑那一版 `bf873c5e…` 登记在 `data/derived/a5_2_a800/archives/NOTICE_superseded_20261006.md`，标 do-not-use）：`is_correct` / `wilson` / `fit_logit`(IRLS) 由本驱动 `import` **直接复用**，未复制、未改写 |
| `[author-workdir]\_a5_2\_a800_a52_ext\a52_ext_b1_analyze.py` | `25ee1e3b2f3a34efc88cc3141b0c11d4` | 既有 b1 延伸分析器；本次逐模型拟合的**模型形式**与其 build-free 补充口径**完全一致** |

机器可读中间件（工作目录，非交付件）：`[author-workdir]\_a52_api_work\_api_analysis_raw.json`（4.2 MB）

## 3. 行数与格数核算

| 项 | 值 |
|---|---|
| 设计格数 | 6 模型 × 648 图 × 3 合同 × 3 重复 = **34,992** |
| `merged_best.jsonl` 实际行数 | **34992**（逐 `key` 唯一，无重复行） |
| `http==200`（本分析的分析集） | **34950** |
| 未服务（`http!=200`） | **42** |
| 已回 200 但正文无可解析计数 | **48**（其中 47 格为 grok-4.7 的纯文字前言、1 格为 gpt-6.1-sol 的空正文；按冻结判据 **计为答错**，不剔除） |

逐模型解析结果（`pred` 类别；`unserved` = 未服务，其余为已回 200）：

| 模型 | 整数 pred | abstain | 无可解析计数 | 未服务 | 合计 |
|---|---|---|---|---|---|
| gpt-6.1-sol | 5018 | 813 | 1 | 0 | 5832 |
| grok-4.7 | 4252 | 1518 | 47 | 15 | 5832 |
| gemini-3.8-flash | 4560 | 1245 | 0 | 27 | 5832 |
| qwen3.8-max | 4891 | 941 | 0 | 0 | 5832 |
| qwen3.8-flash | 4751 | 1081 | 0 | 0 | 5832 |
| glm-4.6v | 4426 | 1406 | 0 | 0 | 5832 |
| **合计** | 27898 | 7004 | 48 | 42 | 34992 |

## 4. 缺失格清单（未服务的 42 格，全量）

| 模型 | n |
|---|---|
| gemini-3.8-flash | 27 |
| grok-4.7 | 15 |

HTTP 类别分布（仅作数据完整性记录）：`503` × 9、`524` × 31、`EXC` × 2

逐格：

```
gemini-3.8-flash|strict|1|c80_s24_b0_o2_L05  http=524
gemini-3.8-flash|strict|1|c80_s24_b0_o2_L07  http=524
gemini-3.8-flash|strict|1|c80_s24_b4_o2_L01  http=524
gemini-3.8-flash|strict|1|c80_s24_b4_o2_L03  http=524
gemini-3.8-flash|strict|1|c80_s24_b4_o2_L06  http=524
gemini-3.8-flash|strict|1|c80_s24_b8_o2_L01  http=524
gemini-3.8-flash|strict|1|c80_s3_b0_o0_L01  http=524
gemini-3.8-flash|strict|1|c80_s3_b0_o0_L04  http=524
gemini-3.8-flash|strict|1|c80_s8_b0_o0_L02  http=524
gemini-3.8-flash|strict|1|c80_s8_b0_o0_L05  http=524
gemini-3.8-flash|strict|1|c80_s8_b0_o0_L06  http=524
gemini-3.8-flash|strict|1|c80_s8_b0_o0_L07  http=524
gemini-3.8-flash|strict|1|c80_s8_b0_o1_L00  http=524
gemini-3.8-flash|strict|1|c80_s8_b0_o1_L01  http=524
gemini-3.8-flash|strict|1|c80_s8_b0_o1_L02  http=524
gemini-3.8-flash|strict|1|c80_s8_b0_o1_L04  http=524
gemini-3.8-flash|strict|1|c80_s8_b0_o1_L07  http=524
gemini-3.8-flash|strict|1|c80_s8_b0_o2_L03  http=524
gemini-3.8-flash|strict|1|c80_s8_b0_o2_L05  http=524
gemini-3.8-flash|strict|1|c80_s8_b4_o0_L00  http=524
gemini-3.8-flash|strict|1|c80_s8_b4_o0_L06  http=524
gemini-3.8-flash|strict|2|c32_s8_b4_o0_L01  http=524
gemini-3.8-flash|strict|2|c32_s8_b4_o0_L06  http=524
gemini-3.8-flash|strict|2|c80_s24_b0_o2_L01  http=524
gemini-3.8-flash|strict|2|c80_s8_b0_o0_L05  http=524
gemini-3.8-flash|strict|2|c80_s8_b0_o1_L00  http=524
gemini-3.8-flash|strict|3|c80_s8_b0_o0_L06  http=524
grok-4.7|base|2|c80_s24_b0_o0_L07  http=503
grok-4.7|base|2|c80_s24_b0_o2_L05  http=503
grok-4.7|base|2|c80_s24_b0_o2_L06  http=503
grok-4.7|base|2|c80_s24_b4_o0_L01  http=503
grok-4.7|base|2|c80_s24_b4_o1_L02  http=503
grok-4.7|base|3|c80_s24_b0_o0_L00  http=503
grok-4.7|base|3|c80_s24_b0_o0_L04  http=503
grok-4.7|base|3|c80_s24_b0_o2_L01  http=503
grok-4.7|base|3|c80_s24_b4_o2_L03  http=503
grok-4.7|strict|1|c80_s24_b4_o2_L03  http=EXC
grok-4.7|strict|2|c80_s24_b0_o0_L02  http=EXC
grok-4.7|strict|2|c80_s24_b0_o1_L04  http=524
grok-4.7|strict|2|c80_s24_b0_o2_L04  http=524
grok-4.7|strict|3|c80_s24_b0_o2_L02  http=524
grok-4.7|strict|3|c80_s24_b0_o2_L03  http=524
```

已回 200 但正文里没有可解析计数的 48 格（**不是**服务缺失；按冻结判据 `correct=0`）：

```
gpt-6.1-sol|strict|1|c80_s24_b0_o0_L02  raw=' '
grok-4.7|base|1|c32_s24_b0_o2_L03  raw='我先用图像处理把蓝色圆点逐个定位并计数，避免目测遗漏或重复。'
grok-4.7|base|1|c80_s3_b8_o0_L03  raw='我先检查图片里的圆点分布，再给出准确计数。'
grok-4.7|base|1|c80_s8_b0_o1_L03  raw='我先用图像处理精确统计蓝色圆点，避免肉眼漏计或重复。'
grok-4.7|base|1|c80_s8_b4_o1_L00  raw='我先精确识别画面左侧的蓝色圆点，再只给出计数结果。'
grok-4.7|base|1|c80_s8_b4_o2_L07  raw='我先用图像处理把左侧蓝色圆点分离出来再计数，避免肉眼漏数或重数。'
grok-4.7|base|1|c80_s8_b8_o0_L07  raw='我先用图像处理精确分割左侧蓝色圆点，再统计连通区域数量。'
grok-4.7|base|2|c32_s24_b8_o0_L03  raw='我先用图像处理精确统计蓝色圆点，避免目测遗漏或重复。'
grok-4.7|base|2|c32_s3_b4_o1_L01  raw='我先读取图片并定位蓝色圆点，再逐个计数。'
grok-4.7|base|2|c32_s8_b4_o0_L07  raw='我先对图片做像素级检测，精确数出左侧蓝色圆点，避免目测遗漏或重复。'
grok-4.7|base|2|c80_s24_b8_o0_L02  raw='我先用图像处理把蓝色圆点分割出来再计数，避免肉眼漏数或重数。'
grok-4.7|base|3|c32_s8_b4_o2_L07  raw='我先对图片做像素级检测，精确统计左侧蓝色圆点，避免目测遗漏或重复。'
grok-4.7|base|3|c32_s8_b8_o0_L05  raw='我先用图像处理把左侧蓝色圆点分割出来再计数，避免肉眼遗漏或重复。'
grok-4.7|base|3|c80_s24_b0_o0_L05  raw="I'll count the circles programmatically so none are missed or double-counted."
grok-4.7|base|3|c80_s3_b0_o0_L01  raw='我先用图像处理精确检测左侧蓝色圆点，再只给出计数 JSON。'
grok-4.7|base|3|c80_s8_b0_o2_L02  raw='我先用图像处理把蓝色圆点精确分离出来再计数，避免目测遗漏或重复。'
grok-4.7|base|3|c80_s8_b4_o2_L02  raw='我先用图像处理把左侧蓝色圆点分割出来，再逐个计数，避免漏计或重复。'
grok-4.7|permit|1|c32_s8_b4_o0_L01  raw='我先对图片做像素级检测，逐个确认圆点后再给出数量。'
grok-4.7|permit|1|c80_s3_b0_o1_L07  raw='我先用图像处理把蓝色圆点分离出来再逐个计数，避免目测重叠。'
grok-4.7|permit|1|c80_s8_b4_o0_L07  raw='我先用图像处理逐个定位蓝点，避免凭肉眼估算。'
grok-4.7|permit|2|c32_s8_b4_o2_L06  raw='我先放大并逐个核对左侧蓝点，确认每个圆点后再给出数量。'
grok-4.7|permit|2|c80_s24_b0_o2_L04  raw="I'll count the circles programmatically to avoid guessing. Let me analyze the image."
grok-4.7|permit|2|c80_s3_b0_o0_L01  raw="I'll count the circular dots by analyzing the image directly rather than guessing."
grok-4.7|permit|2|c80_s3_b0_o0_L03  raw='我先用图像处理逐个定位蓝点，再给出计数。'
grok-4.7|permit|2|c80_s3_b0_o1_L04  raw="I'll count the dots by inspecting the image pixels so the total is verified rather than guessed."
grok-4.7|permit|2|c80_s3_b0_o1_L07  raw='我用像素连通域把每个蓝点分开计数，避免目测重叠。'
grok-4.7|permit|2|c80_s8_b0_o0_L00  raw='我先用图像处理把每个蓝点逐个定位出来，避免目测漏数。'
grok-4.7|permit|2|c80_s8_b0_o0_L04  raw="I'll count the blue circular dots programmatically so each one is verified rather than guessed."
grok-4.7|permit|2|c80_s8_b0_o1_L03  raw="I'll count the blue circular dots programmatically so each one is verified rather than guessed."
grok-4.7|permit|2|c80_s8_b0_o2_L02  raw="I'll count the dots programmatically so each circle is verified rather than guessed."
grok-4.7|permit|2|c80_s8_b4_o0_L07  raw='我用程序检测每个蓝点的位置，再逐个核对数量。'
grok-4.7|permit|3|c08_s3_b0_o1_L00  raw="I'll inspect the image pixels and count distinct circular dots rather than guess."
grok-4.7|permit|3|c08_s3_b0_o1_L07  raw='I will isolate the blue dots and count each connected circular blob.'
grok-4.7|permit|3|c80_s24_b0_o2_L04  raw="I'll count the circles by detecting the blue blobs in the image so the total is exact. Let me run a quick analysis."
grok-4.7|permit|3|c80_s3_b0_o0_L01  raw="I'll count the dots by detecting each circular mark in the image rather than estimating."
grok-4.7|permit|3|c80_s3_b0_o0_L03  raw='我先用图像处理逐个定位蓝点，再给出计数。'
grok-4.7|permit|3|c80_s3_b0_o1_L04  raw="I'll count the dots by inspecting the image pixels so the total is verified rather than guessed."
grok-4.7|permit|3|c80_s3_b0_o1_L05  raw="I'll count the dots by detecting blue circular blobs in the image rather than guessing."
grok-4.7|permit|3|c80_s3_b0_o1_L07  raw='我先把蓝点从背景里分离出来，再按连通区域逐个核对数量。'
grok-4.7|permit|3|c80_s3_b0_o2_L05  raw="I'll count the dots programmatically so each one is verified rather than guessed."
grok-4.7|permit|3|c80_s3_b4_o1_L06  raw="I'll analyze the image programmatically to count the dots reliably."
grok-4.7|permit|3|c80_s8_b0_o0_L00  raw='我用程序把蓝色圆点逐个检测出来，避免目测漏数。'
grok-4.7|permit|3|c80_s8_b0_o0_L04  raw="I'll count the blue circular dots programmatically so each one is verified rather than guessed."
grok-4.7|permit|3|c80_s8_b0_o1_L03  raw="I'll count the blue circular dots programmatically so each one is verified rather than guessed."
grok-4.7|permit|3|c80_s8_b0_o2_L02  raw="I'll count the blue dots by detecting each connected component so the total is verified, not estimated."
grok-4.7|permit|3|c80_s8_b0_o2_L03  raw='我来用图像处理精确检测并计数这些圆点，而不是凭眼睛估。'
grok-4.7|permit|3|c80_s8_b4_o0_L07  raw='我先对图像做圆点检测，确认每个点的位置后再给出数量。'
grok-4.7|strict|1|c32_s8_b8_o2_L05  raw='我先用图像处理精确数一下左侧蓝点，避免目测漏计。'
```

## 5. 与既有冻结件的一致性核验（★ 关键）

1. **β 函数逐位复现**：用本次驱动对既有 b1 全量 9 格（本地 CSV）做 build-free 拟合，
   得 β = `-4.209594349795038`，SE = `0.252058482477508`；`a52_ext_b1_analyze.py` 在 2026-10-06 刊载的值为
   β = `-4.209594349791142`，SE = `0.25205848247725443`。**前 12 位有效数字一致** ⇒
   本次 API 臂使用的估计量与既有冻结/已刊载口径**同一实现**。
2. **逐档答对率逐位复现**：本次用本地 CSV + 冻结 `is_correct` 复算 b0/b1/b2，得
   b0 = 48.82% / 1.90% / 0.51%，b1 = 50.26% / 2.57% / 0.72%，b2 = 50.46% / 2.21% / 0.67%（c08/c32/c80），
   与 `A800_A5-2_最终报告_b1全量+b3定案_20261006.md` §1.3 刊载的 48.82/1.90/0.51、50.26/2.57/0.72、50.46/2.21/0.67 **逐位吻合**。
3. **判据件 md5 三方一致**：`_p3_api_results_20261007/`、`_a5_2/`、`_a5_2/_a800_a52/env/` 三份
   `_a52_criteria_frozen.json` 的 md5 均为 `758962a2643e1035698682abefec5748`。
4. **真值双来源一致**：648 格逐位比对 `stim/manifest.csv` 的 `n_dots_detected_gt` 与
   `detection_matrix.csv` 的对应列 —— **0 处不一致**（抽检表中逐行列出）。

### 5.1 冲突 / 差异（如实列出）

| # | 事项 | 处置 |
|---|---|---|
| 1 | 交付目录里的 `manifest.csv` 是 **0 字节空文件**，无法作为逐图真值来源。 | 改用源包的 `stim/manifest.csv`（md5 `d2dde2a8100eca8eda88143f6cbb04ba`，与 `MANIFEST.tsv` 记载一致），并用 `detection_matrix.csv`（md5 `67688d5f…`）**独立交叉验证**（648/648 一致）。**未修改该空文件**。 |
| 2 | 冻结判据的 C1「预注册排除 3 格」只写在 **C1 覆盖**条下，冻结分析器**并未**把这 3 格移出 C3 的拟合池。 | 主口径**跟随冻结分析器**（保留全部格，与已刊载 b0/b1/b2 数字可比）；另给「排除 3 格」的敏感性列（报告 §7），结论不变。 |
| 3 | 2026-10-06 通宵监视件的口径写「主分析用每格 3 次的多数值，附录给逐次原始值」；而冻结判据的 C3 响应是**逐行**的（`a52_analyze.py` 把 3 次起服的全部行池化）。 |**两套口径都报**：C4 主判定用**冻结的逐行口径**（与 b0/b1/b2 可比），多数值口径作为并列的稳健性列（报告 §5）。两套口径的 C4 判决一致。 |
| 4 | 冻结分析器的设计矩阵含 `build` 因子（b0 为参考档）。API 臂无 `build`，其对应物是 6 个 API 模型。 | 逐模型拟合 **去掉模型项**（与 `a52_ext_b1_analyze.py` 的 build-free 补充口径同一模型形式，且该形式已在本机复现出刊载值）；池化拟合以 `model` 哑变量**替代** `build` 哑变量（参考档 `gpt-6.1-sol`）。 |
| 5 | `_p3_api_results_20261007/raw/`（若干 `run*.jsonl`）在本次分析**开始之后**出现于交付目录，**非本次分析产出**，本次分析未读取、未改动它。 | 如实记录；本件的 5 个交付件与之无关。 |

## 6. 交付件

| 文件 | 说明 |
|---|---|
| `API_six_implementations_analysis.md` | 结果导向分析报告 |
| `table_per_model_band_accuracy.csv` | 6 模型 × 逐档 n/命中率(Wilson)/MAE/塌缩众数；并列 b0/b1/b2 与多数值口径 |
| `table_repeat_consistency.csv` | 逐模型重复一致性 + 两套口径逐档命中率与 β |
| `table_stratified_served_ptok.csv` | served / ptok 分簇后的分层拟合 |
| `analysis_manifest.md` | 本件 |

逐件 md5 与字节数（写本件之前即时实算；本件自身不自指）：

| 文件 | md5 | 字节 |
|---|---|---|
| `API_six_implementations_analysis.md` | `567d7432fa294a4b2fa69a7467361607` | 23425 |
| `table_per_model_band_accuracy.csv` | `d124b4173ed9626734784f54d0ee015c` | 5398 |
| `table_repeat_consistency.csv` | `ebeb30865efea710bfe748ea87dd71f7` | 2463 |
| `table_stratified_served_ptok.csv` | `508026b99e4b648049e92fc7b1c04b31` | 7450 |

（`analysis_manifest.md` 自身的 md5 随本表写入而变化 ⇒ 不自指，其值在交付说明中单独给出。）

## 7. 抽检（随机 20 行，种子 20261007）

通过率 = **20/20 = 100.0%**。四项判据：`http==200` / 冻结解析器与独立解析器取值一致 / `manifest` 与 `detection_matrix` 的真值逐位一致 / `correct` 用冻结容差重算一致。

| # | key | http | raw | 冻结解析 | 独立解析 | `n_dots_detected_gt`(manifest) | (detection_matrix) | 容差 | correct | 通过 |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | `gemini-3.8-flash|base|1|c32_s8_b0_o1_L07` | 200 | ````json {"count": 31} ```` | 31 | 31 | 32 | 32 | ±1 | 1 | PASS |
| 2 | `gemini-3.8-flash|strict|2|c80_s24_b4_o0_L06` | 200 | `{"count": 80}` | 80 | 80 | 80 | 80 | ±4 | 1 | PASS |
| 3 | `glm-4.6v|base|2|c08_s8_b0_o2_L03` | 200 | ` {"count": 4}` | 4 | 4 | 6 | 6 | ±1 | 0 | PASS |
| 4 | `glm-4.6v|base|2|c08_s8_b8_o0_L00` | 200 | ` {"count": 1}` | 1 | 1 | 8 | 8 | ±1 | 0 | PASS |
| 5 | `glm-4.6v|base|2|c32_s24_b8_o2_L02` | 200 | ` {"count": 28}` | 28 | 28 | 17 | 17 | ±1 | 0 | PASS |
| 6 | `glm-4.6v|base|3|c08_s3_b0_o0_L04` | 200 | ` {"count": 3}` | 3 | 3 | 8 | 8 | ±1 | 0 | PASS |
| 7 | `glm-4.6v|permit|1|c08_s3_b0_o0_L01` | 200 | ` {"count": 1}` | 1 | 1 | 8 | 8 | ±1 | 0 | PASS |
| 8 | `glm-4.6v|permit|1|c80_s8_b8_o1_L03` | 200 | ` {"count": "abstain"}` | abstain | abstain | 73 | 73 | ±3 | 0 | PASS |
| 9 | `glm-4.6v|strict|2|c80_s3_b0_o1_L07` | 200 | ` {"count": 100}` | 100 | 100 | 80 | 80 | ±4 | 0 | PASS |
| 10 | `glm-4.6v|strict|3|c80_s3_b0_o2_L02` | 200 | ` {"count": 100}` | 100 | 100 | 37 | 37 | ±1 | 0 | PASS |
| 11 | `gpt-6.1-sol|base|2|c08_s8_b4_o0_L01` | 200 | `{"count":8}` | 8 | 8 | 8 | 8 | ±1 | 1 | PASS |
| 12 | `gpt-6.1-sol|base|2|c80_s8_b4_o0_L03` | 200 | `{"count": 80}` | 80 | 80 | 80 | 80 | ±4 | 1 | PASS |
| 13 | `gpt-6.1-sol|permit|3|c08_s24_b8_o2_L03` | 200 | `{"count":8}` | 8 | 8 | 5 | 5 | ±1 | 0 | PASS |
| 14 | `grok-4.7|base|2|c08_s8_b8_o2_L02` | 200 | `{"count": 7}` | 7 | 7 | 5 | 5 | ±1 | 0 | PASS |
| 15 | `grok-4.7|base|3|c32_s3_b0_o1_L00` | 200 | `{"count": 42}` | 42 | 42 | 32 | 32 | ±1 | 0 | PASS |
| 16 | `grok-4.7|permit|2|c80_s8_b0_o2_L02` | 200 | `I'll count the dots programmatically so each circle is verif` | None | None | 50 | 50 | ±2 | 0 | PASS |
| 17 | `grok-4.7|strict|3|c80_s3_b8_o1_L03` | 200 | `{"count": 0}` | 0 | 0 | 23 | 23 | ±1 | 0 | PASS |
| 18 | `qwen3.8-flash|base|1|c80_s24_b0_o0_L02` | 200 | `{"count": 78}` | 78 | 78 | 79 | 79 | ±3 | 1 | PASS |
| 19 | `qwen3.8-max|permit|1|c08_s24_b0_o0_L00` | 200 | `{"count": 8}` | 8 | 8 | 8 | 8 | ±1 | 1 | PASS |
| 20 | `qwen3.8-max|permit|3|c32_s8_b8_o0_L02` | 200 | `{"count": "abstain"}` | abstain | abstain | 32 | 32 | ±1 | 0 | PASS |

