# PLAN.md —— 实验 1「预算匹配的预注册复验」执行计划与**规模警告**

> ★ 本件是 `PREREGISTRATION.md` 的**执行说明**，不含任何判据（判据只在预注册件里）。
> ★ 只写本地文件；不连机器、不执行、不下载（真正的执行在云端，由上级做）。

## 0 四文件与用途

| 文件 | 用途 | 何时跑 | 在哪跑 |
|---|---|---|---|
| `PREREGISTRATION.md` | 冻结件（口径 + 常数 + 档位 + 判据 + 停止规则） | 执行前**已冻结** | 本地 |
| `render_a57.py` | 渲染新域（图像 + `manifest.csv` + `contracts.csv`） | 冻结后、上机前 | **本地**（零网络） |
| `run_a57.sh` | 编排（复用 `/root/a51_work/start_a51.sh` + `runner_a51.py`） | 图像上机后 | **云端**（上级） |
| `analyze_a57.py` | §M.45(b) 统计 + 回归自证 | 放量完成后 | 云端或取回后本地 |

## 1 规模（★ 逐项算清）

设 `F` = 家族数、`K` = knob 数、`L` = 每 knob 档位数、`N` = 每格图数、`S` = 每格起服数。

| 量 | 公式 | 本设计（F=3, K=2, L=3, N=100, S=3） |
|---|---|---|
| 单元数（family × knob） | `F·K` | **6** |
| 格数（family × knob × level） | `F·K·L` | **18** |
| **模型调用总数** | `F·K·L·N·S` | **5,400** |
| **独立服务启动次数** | `F·K·L·S` | **54** |
| 渲染物理图像数 | `K·L·N·F` | **1,800** |
| 逻辑 item 数 | `K·N·F` | **600** |
| 每个单元内的候选档对 | `C(L,2)` | **3** |
| 每单元参与排序的行 | 1 | 6 行（Spearman 用） |

### 1.1 ★ 规模警告（必须转达）

1. ★ **54 次冷起服是主要成本，不是 5,400 次调用**：每次 `start_a51.sh` 要加载权重并等
   `/v1/models` 200。按 **每次 3–8 分钟**（8B 与 32B-FP8 差别很大）估：
   * `icpt` 54 × 3 min ≈ **2.7 h**（乐观，仅 8B 级）；
   * 54 × 6 min ≈ **5.4 h**（中性，含 32B-FP8 与 llava-onevision）；
   * 54 × 8 min ≈ **7.2 h**（悲观，含失败重试）。
   ★ 这一段**不随图数减少**：哪怕把 `N` 降到 50，起服开销仍是 54 次起步。
2. ★ **调用吞吐另算**：5,400 次调用 ÷ 8 lane ÷ 每次约 3–12 s ≈ **0.6–2.3 h**（总量，跨 3 家族）。
3. ★ **总墙钟（3 家族串行）粗估 ≈ 3.3–9.5 h**，另加渲染、传输、失败重跑。
   ★ 若上级要求缩短：**先减家族数或档位数**（这两者同时减起服与调用），**不要减 `N`**
   （减 `N` 只减调用、不减起服，还会放大 MAE 抽样误差）——但任何减法都必须在执行前改预注册件。
4. ★ **磁盘/传输**：1,800 个 PNG（832² 与 640–832²，PNG 压缩后约 **20–120 KB/张**）≈
   **36–216 MB**（中性约 **100 MB**）+ `manifest.csv`/`contracts.csv`。上机需一次传输。
5. ★ **同一次起服内跑完该 (family, knob, level) 的全部 100 图**（预注册 §5）：因此单次起服的
   放量时长 = 100 图 ÷ 8 lane × 单图 3–12 s ≈ **0.6–2.5 min**，即**起服时间 ≫ 放量时间**
   （这正是警告 1 的算术来源）。
6. ★ **每格 100 图的 MAE 抽样误差**：100 图交集上 MAE 的标准误约 `σ(|err|)/√100`；
   本域的合成 GT 为精确值，故误差只来自模型。★ 但预注册固定 `N=100`，**不得**因看起来噪声大而中途加样
   （§7 停止规则）。

## 2 执行顺序（★ 每一步的输入/输出都写清）

```
本地（零网络）
 ① python render_a57.py <POOL> --per-knob 100
      → <POOL>/images/*.png（1,800）、<POOL>/manifest.csv、<POOL>/contracts.csv
      → 自检：density 三档 sha 互异 + 同 seed/同画布；res 三档 sha 互异 + 同场景；落点失败 = 0
 ② python analyze_a57.py --selftest
      → 用内嵌 §M.45 冻结核回归自证；**必须先过**（不过就如实写"未能自证"，见预注册 §9）
 ③ 把 <POOL>/ 与两个 .py/.sh 送上机：
      /root/a57_work/pool/         ← images/ + manifest.csv + contracts.csv
      /root/a57_work/run_a57.sh
      /root/a57_work/analyze_a57.py
      （start_a51.sh / runner_a51.py 留在 /root/a51_work/，**不改动**）

云端（上级）
 ④ bash /root/a57_work/run_a57.sh --dry-run
      → 打印 54 组「起服 + 放量」命令；★ 逐行核对模型目录名（尤其 lov7b）与端口
 ⑤ bash /root/a57_work/run_a57.sh
      → 54 次独立起服；每格打印「唯一 200 数 / 可解析数 / MAE / rho」
      → 产物：/root/a57_work/work/<alias>/<knob>/<level>/start<K>/run.jsonl
 ⑥ python3 /root/a57_work/analyze_a57.py --out /root/a57_work --results /root/a57_work/results
      → results/a57_budget_matched_summary.csv（主/次/两个事后诊断 + R2 对照）
      → results/a57_budget_matched_units.csv（逐单元 MAE/ρ/cost/span/可保留档对）
      → results/a57_cell_coverage.csv（每格覆盖：行数/唯一200/未解析/重复）
      → results/RESULTS_a57.md（含 selftest 对照表与图像同一性闸门结论）
```

## 3 目录布局（与 `analyze_a57.py` 的读入约定一致）

```
/root/a57_work/                         ← --out（分析根）
├── manifest.csv                        ← run_a57.sh 从 pool/ 拷一份（分析器读这一份）
├── pool/                               ← render_a57.py 的 out
│   ├── images/  den_0000.png … res_0099_px832.png   （1,800 个）
│   ├── manifest.csv                    ← 9 列：item,target_word,count_gt,knob,level,px,seed,sha256,image
│   └── contracts.csv                   ← 6 列：item,knob,level,count_gt,px,prompt
├── work/                               ← run_a57.sh 写
│   └── <alias>/<knob>/<level_label>/start<K>/
│       ├── cell_contracts_base.csv     ← 本格 100 行的 base 契约（runner_a51 读）
│       ├── run.jsonl                   ← 放量逐格记录（runner_a51 写；断点续跑）
│       ├── start.log / run.log
└── results/                            ← analyze_a57.py 写
```

★ **`item` 是逻辑名、`image` 是物理名**（预注册 §3.2）：`res` 的 `item=res_0000.png` 在三个档
对应三个物理文件 `images/res_0000_px640.png|px704|px832`。分析器**只**用 `image` 列定位文件，
用 `item` 做公共交集键。

## 4 `run_a57.sh` 对上机环境的假设（★ 上机前逐条核对）

| 假设 | 默认值 | 覆盖方式 |
|---|---|---|
| 既有编排脚本 | `/root/a51_work/start_a51.sh`、`/root/a51_work/runner_a51.py` | `A57_A51=...` |
| 服务端口 | `8021` | `A57_PORT=...` |
| 并发 lane | `8` | `A57_LANES=...` |
| `max_tokens` | `1024` | `A57_MAX_TOKENS=...` |
| 模型目录 | `/root/models/<DIR>`；`DIR` 见 `run_a57.sh` 的 `CELLS` | 直接改 `CELLS` |
| 起服方式 | `bash start_a51.sh <alias> <modeldir> <port> [quant]` | 同上 |
| 只跑主臂 | `A51_ARMS=base` | 同上 |
| 断点续跑 | `runner_a51.py` 自带 `done_keys()`（`run.jsonl` 只追加） | — |
| 单格选择 | 全 54 格 | `--only alias,knob,level` |

★ **`llava-onevision-qwen2-7b-ov` 目录名未在本机核实**；`q32fp8`/`ivl358b` 的目录名取自 A5-1/A5-2
既有件。★ `--dry-run` 的目的就是让上级在上机前把这三行目录名与实际 `/root/models/` 逐个对上。

## 5 失败处置（★ 与预注册 §7 一致，不得放宽）

| 情形 | 处置 |
|---|---|
| 某次起服失败（连续 3 次） | 该家族**整批中止**；不得换家族补位；如实报告 |
| 某格有效读数 < 80 图（HTTP 非 200 / 解析失败 / 截断） | 允许该次起服**最多重跑 2 次**补基础设施缺口；仍不足 ⇒ 单元 `INCONCLUSIVE`（不填数） |
| 档间同一性闸门不通过 | `analyze_a57.py` **中止**（返回码 4），不产出读数 |
| selftest 不通过 | 报告**必须**写"未能自证"；本实验统计量降级为"口径未对齐的探索性读数" |
| 中途需要停 | 保留完整留档；恢复后按同一 `cell` 续跑（`run.jsonl` 追加） |

## 6 已在本地验证过的部分（★ 有据可查）

| 验证 | 结果 |
|---|---|
| `analyze_a57.py --selftest` | **通过**：`primary` usable=14 / ρ=0.7674 / ret=0.477、`secondary` 20 / 0.8227 / 0.582、`cost_only` 17 / 0.9275 / 1.000、`mae_only` 16 / 0.8292 / 0.477，四者与已印 §M.45(b) **逐位一致**（退出码 0） |
| 已印 `n6_budget_matched.py` 本机复跑 | 四个读数**逐位复现**；28 单元集合 = 36 − 8（排除 output contract / prompt family）⇒ 佐证预注册 §1.3 的 R1 读法 |
| `render_a57.py` 小样（`--per-knob 8`） | 通过：48 行 manifest、32 个物理文件、落点失败 0、density 三档 sha 互异且同 seed/同画布、res 三档 sha 互异且同场景 |
| `analyze_a57.py` 全链路小样（合成 run.jsonl） | 通过：图像同一性闸门 OK、6 个单元可算、摘要/逐单元/覆盖/Markdown 四件产物齐全，读数形态正确（"符合可比条件的单元比例"分母 = 6） |
| `run_a57.sh --dry-run` | 打印 **108 行** = 54 组 × (1 起服 + 1 放量)，格数与预注册一致 |
| `run_a57.sh` 语法 | `bash -n` 通过 |

★ **未做（明确留空）**：真实渲染 1,800 张、上机、调用模型、取回数据。**本计划不包含任何实测读数。**

## 7 待上级裁定（同预注册 §11，便于一处看全）

1. 未用域：**合成新渲染族（默认）** vs 公开集（需先解决 TRANCOS 中间页 / CARPK 加密包）。
2. 家族数：3 个（下限）vs 更多（每 +1 家族 ⇒ +1,800 次调用 / +18 次起服）。
3. 每单元图数：100（默认）vs 更多（只加调用、不加起服；每翻倍 ⇒ 调用翻倍）。
4. 是否接受 §1.3 的 R2（严格成本语义）作为一行 post-hoc 口径对照。
5. 档位集是否在执行前改动（`density` {24,30,36}、`res` {640,704,832}）；**执行后不得改**。
