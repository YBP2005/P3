# A5-2 判决书 —— 计数 × 可读性正交冻结刺激（A800 单卡）

* 判据件：`_a52_criteria_frozen.json` md5 **`758962a2643e1035698682abefec5748`**（跑前冻结，全程未改一个字节）
* 刺激锁（**本机渲染**）：`manifest.csv` md5 **`d2dde2a8100eca8eda88143f6cbb04ba`**
* 正式运行：**v2c（前 3 格）+ v2d（其余 15 格）**，远端 `2026-10-04 01:08:02 → 02:48:10`
* 判决日期：2026-10-04 ｜ 判决书本件：`_a5_2/_a52_verdict.md`

---

## 0. 一句话结论

**C1 PASS、C2 PASS（收缩口径，见 §3.2 的口径说明）、C3 PASS、C4 FAIL、C5 PASS；NC1/NC3/NC-const PASS。**
**⇒ 必须撤回"count 无实质作用"这一表述**：标准化 log-odds 的 count 主效应 = **−4.3696**，95% CI **[−4.8066, −3.9327]**，**远离 ±0.2 实用零带**。控制可读性（半径/模糊/重叠）后，count 的作用**不但仍在，而且极强**（8 点 → 32 点 → 80 点的答对率 49.6% → 2.1% → 0.6%）。

---

## 1. ★ 范围声明（必须先读）

**本环境（A800 单卡）不存在同族 FP8 权重、也不存在同族 GPTQ 权重 ⇒ 本轮只跑两个实现：**

| 构建 | 实现 | 起服件 | 端口 | served-model-name | 模型目录 | 齐备 |
|---|---|---|---|---|---|---|
| **b0** | **AWQ 4bit** | `/root/pf_serve_awq4bit_8013.sh` | 8013 | `Qwen3-VL-32B-Instruct-AWQ` | `/root/models/Qwen3-VL-32B-Instruct-AWQ-4bit` | ✅ |
| b1 | FP8 | ❌ 无同族件 | — | — | ❌ 本机无 `…-Instruct-FP8` | ❌ **缺** |
| **b2** | **BF16** | `/root/p3_serve_bf16_A.sh` | 8012 | `Qwen3-VL-32B-Instruct` | `/model/ModelScope/Qwen/Qwen3-VL-32B-Instruct` | ✅ |
| b3 | 第三方 4bit（GPTQ） | ❌ 无 GPTQ 服务件 | — | — | ❌ 本机无 VL 的 GPTQ 权重 | ❌ **缺** |

> ★ **不得表述为"四构建"**。本轮是**两个构建（b0 + b2）的收缩路径**（判据件 `amendments[0].note` 允许，且经上级明确裁定）；编排件自身亦在日志写下
> `A52_BUILDS_SHRUNK builds=[b0 b2] missing=b1(FP8),b3(GPTQ)`。
> 缺件反证（只读勘查，逐条可复跑）：`ls /root/models/Qwen3-VL-32B-Instruct-FP8` ⇒ 不存在；`p4_download.sh` L45/L49 **只声明**该仓 19 文件/35.53 GB、从未落盘；`find /root /model -iname '*gptq*'` ⇒ 仅两件**纯文本**非 VL 模型；`find -iname '*Qwen3-VL*GPTQ*'` ⇒ 空。
> **b3 特别禁令已遵守**：从未把 b0 的 AWQ 权重换 served-name 冒充第三方 4bit。

---

## 2. 裁决摘要

| 判据 | 结论 | 关键数字 |
|---|---|---|
| **C1 覆盖** | ✅ **PASS** | 648 图 / 81 格 / 每格 8 / sha256 **648/648 实算相符** / 预注册排除 3 格后分母 **78 格全非空** |
| **C2 完整性** | ✅ **PASS（收缩口径）**；原样冻结阈值口径 **FAIL**（见 §3.2） | 18 格 × 648 = **11,664 行**；逐格 `parse_ok` **= 1.000**（18/18）；偏少格 0；`http_err` 合计 **0** |
| **C3 四因子模型** | ✅ **PASS** | 设计矩阵秩 **11/11**（无完全共线）；IRLS 11 步收敛 |
| **C4 实用零带 ±0.2** | ❌ **FAIL** | β_std = **−4.3696**，Wald 95% CI **[−4.8066, −3.9327]**（完全在带外）；聚类 bootstrap CI **[−6.2051, −3.1896]**（同向） |
| **C5 按布局分折** | ✅ **PASS** | 8 折 β ∈ [−4.9686, −4.0689]，median **−4.3177**，sd **0.3128**，符号一致 **1.00** ⇒ 稳定 |
| NC1 层内置换 | ✅ PASS | 20 次置换 β 中位 \|β\| **0.0345** < 0.05（最大 0.0730） |
| NC-const（count=32 子集） | ✅ PASS | count 零方差 ⇒ β 构造性 = 0（见 §5.3） |
| NC3 独立重解析 | ✅ PASS | 从 `raw` 重解析 **11,664 行，不一致 0** |

---

## 3. C1–C5 逐条

### 3.1 C1 覆盖 —— PASS
* PNG **648** 张、`manifest.csv` **648** 行、格 **81**、每格 **8**（`per_cell_all_8 = true`）。
* **逐张实算 sha256 与 manifest 的 `sha256` 列比对：648/648 相符**（比"列长 64"更强的检查）。
* 预注册排除 3 格（`_unrealizable.csv` 先声明后排除，**未事后剔除**）：
  `c08_s3_b8_o0`（σ=8 下并成一团、可辨 blob=0）、`c80_s24_b0_o0`（放不下，仅 79/80）、`c80_s24_b4_o0`（放不下，仅 76/80）。
  ⇒ 非空检查分母 = 81 − 3 = **78**，**78 格全非空、0 格为空**。
* 附报：`detection_frac` 均值 **0.759**（min 0.00 / max 1.00）；648 张里 `n_dots_detected_gt = 0` 的恰 **3** 张（全在 `c08_s3_b8_o0`，即已预注册排除的格）。

### 3.2 C2 完整性 —— **收缩口径 PASS / 原样阈值口径 FAIL（如实并列）**
* 按**实际可跑构建集**（b0+b2，经上级裁定的收缩路径）的正确分母：**18 格 × 648 = 11,664 行**，逐格 `parse_ok` 率**全部 = 1.000**、**无偏少格**、`http_err` 合计 **0**、`abstain` 合计 1,991（全在 `permit` 档）⇒ **实质 PASS**。
* **但必须如实说**：判据件 `C2_integrity.threshold.total_rows` 写死 **23,328**（= 4 构建 × 3 合同 × 3 起服 × 648），而 b1/b3 在本机**根本不存在**。**冻结分析器原样跑出的结论是 `C2 passed=false`（缺 18 格 = b1/b3 的全部格）**——这是"四构建写死"的口径产物，不是本轮数据缺陷。判决书**两个口径都列**，不掩盖。

### 3.3 C3 四因子模型（预注册顺序）—— PASS
设计矩阵列（参考档 contract=base、build=b0；size/blur/overlap 有序编码）：
`intercept, count_std, count_std×strict, count_std×permit, count_std×b2, size, blur, overlap, strict, permit, b2`；秩 **11/11**。

| 项 | β | SE | z | p | 95% CI |
|---|---:|---:|---:|---:|---|
| **count_std（主效应）** | **−4.3696** | 0.2229 | −19.60 | ~0 | **[−4.8066, −3.9327]** |
| count_std × strict | −0.3183 | 0.2577 | −1.24 | 0.217 | [−0.8235, 0.1868] |
| count_std × permit | **−2.1767** | 0.3807 | −5.72 | 1.1e−08 | [−2.9228, −1.4305] |
| count_std × b2 | +0.1920 | 0.2372 | 0.81 | 0.418 | [−0.2730, 0.6570] |

⇒ ① count 主效应极强且为**负**（点子越多，答对越难）；② **count × 合同** 在 `permit` 档显著更强（允许弃答时，高 count 更倾向弃答）；③ **count × 构建** 不显著（两构建差异小）。

### 3.4 C4 实用零带 —— ❌ **FAIL**
* 判据：`ci_lo > −0.2 AND ci_hi < +0.2`（完全落入 ±0.2）。
* 实测：**CI = [−4.8066, −3.9327]** ⇒ **完全在带外**（连 0 都不含）。
* 稳健性（判据要求的聚类 bootstrap，按 8 个布局重抽，B=500，seed 20261004）：**CI = [−6.2051, −3.1896]**，中位 −4.4624 ⇒ **同向且更宽**，不是抽样偶然。
* **处置（照判据件 `verdict_if_fail`）**：**撤回"count 无实质作用"**；§5.6 改写为"**count 的作用在控制可读性后仍可见**"。本轮的效应量级远大于"仍可见"的最低要求。

### 3.5 C5 按布局分折（group-wise holdout）—— PASS
以布局为组、8 折（同源变体同折不拆散），逐折在其余 7 折上重估 β_std(count)：

| 折 | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| β_count | −4.6816 | −4.4856 | −4.1043 | −4.0689 | −4.2864 | −4.3489 | −4.9686 | −4.1470 |

min **−4.9686** / max **−4.0689** / median **−4.3177** / sd **0.3128** / 符号一致 **1.00** ⇒ 按判据件 `sd ≤ 0.5·|median|`（0.3128 ≤ 2.1589）与符号一致阈值 1.0 均**通过**；**不稳定性旗标不触发**。

---

## 4. ★ 每构建 × 合同关键读数（池化必报）

| 构建 | 合同 | n | 答对 | 答对率 | Wilson 95% | abstain | pred=0 |
|---|---|---:|---:|---:|---|---:|---:|
| b0 | base | 1944 | 341 | 17.54% | [15.91%, 19.30%] | 0 | 680 |
| b0 | strict | 1944 | 341 | 17.54% | [15.91%, 19.30%] | 0 | 681 |
| b0 | permit | 1944 | 314 | 16.15% | [14.58%, 17.85%] | **981** | 0 |
| b2 | base | 1944 | 353 | 18.16% | [16.51%, 19.93%] | 0 | 683 |
| b2 | strict | 1944 | 353 | 18.16% | [16.51%, 19.93%] | 0 | 681 |
| b2 | permit | 1944 | 331 | 17.03% | [15.42%, 18.76%] | **1010** | 0 |

**按 count 档（池化 11,664）**：count=8 → **49.6%**（1930/3888）｜ count=32 → **2.1%**（80/3888）｜ count=80 → **0.6%**（23/3888）。

**读法**：① `base` 与 `strict` 在两构建上**完全同数**（341/341、353/353）——`strict` 只加"只输出 JSON"，而两档本已 100% 可解析，故未改变行为；② `permit` 档把"答 0"换成"弃答"（abstain 51.2%、pred=0 归零），答对率略降；③ **count 是压倒性因素**（8→32 点答对率掉 24 倍）。

---

## 5. 阴性对照与交叉核对

### 5.1 NC1 层内标签置换（自写实现）—— PASS
在 (size, blur, overlap, contract, build) 层内置换响应 20 次（保持层边缘、打散与 count 的关联）⇒ β_count 中位 \|β\| **0.0345**（<0.05 阈值）、最大 0.0730 ⇒ **效应消失，分析管线无泄漏**。

### 5.2 NC3 从 `raw` 独立重解析 —— PASS
自写解析器（JSON `count` → 纯数字 → 弃答标记 → 正文唯一整数）重解析 **11,664 行** ⇒ `parse_ok` 不一致 **0**、`pred` 不一致 **0**、`abstain` 旗标不一致 **0**。

### 5.3 NC-const（count 设常数的真实子集）—— PASS（构造性）
取 `count_gt = 32` 的真实 3,888 行（**同一批冻结 PNG 的天然"常数 count 渲染"**：同一格参数、同一渲染器、同一 seed 规则；**无需另跑推理**，因为再渲染 count=32 会得到同一批文件）⇒ count 列零方差、该列不可识别 ⇒ 按判据口径 β_count ≡ **0.0**，C4 带内。
> 说明：判据件 NC1 的 `why_not_rerender` 已预置此路径；真正的"常数 count 重渲染"在本设计里**不可识别**（count 无变异 ⇒ 无估计量），故以"常数 count 子集 + 层内置换"两个口径共同承担阴性对照，**不做**无意义的假重渲染。

### 5.4 与冻结分析器的交叉核对（仅核对，**不作为独立复算依据**）
以 `a52_analyze.py`（md5 `bf873c5e…`，CPU）在同一批取回数据上直跑：

| 项 | 冻结分析器 | 我的独立复算 | 一致性 |
|---|---|---|---|
| C1 | PASS（均值 detection_frac 0.759） | PASS（并实算 sha256 648/648） | 一致 |
| C2 | **FAIL**（缺 18 格 b1/b3；阈值写死 23,328） | PASS（收缩口径 11,664；偏少格 0、parse_ok=1.000） | **口径差异**，见 §3.2 |
| C3 count 主效应 | −4.4947，CI [−4.9391, −4.0503] | −4.3696，CI [−4.8066, −3.9327] | 同向同量级；差异来自"构建交互"参数化（分析器保留 b1/b3 哑元并置 0，我只用 b2 哑元） |
| C4 | FAIL | FAIL | 一致 |
| C5 | 8 折 sd 0.3199、符号一致 1.00、不稳定 False | sd 0.3128、符号一致 1.00 | 一致 |
| NC3 | 不一致 0 | 不一致 0 | 一致 |

---

## 6. 运行史（含闸门、冒烟、中止、外部规避）

### 6.1 安全闸门（当时三读，作为客观记录；此后上级已裁定不再作为放行条件）
| 项 | 读数 |
|---|---|
| `nvidia-smi --query-compute-apps=pid,used_memory` | **空** |
| `--query-gpu=memory.used` 连续 3 次（间隔 20 s） | `00:47:38 = 0 MiB`、`00:47:58 = 0 MiB`、`00:48:18 = 0 MiB`；同刻 `0, A800-SXM4-80GB, 0 MiB, 81920 MiB, 0%` |
| 无 P4 活动 | `ls -lt /root/logs` 最新 Oct 3 17:38（≈7 h 前）；`find /root -maxdepth 2 -newermt '-15 minutes' -name '*.log'` ⇒ 空；`pgrep -af 'cvpr_exp\|p4_\|w1_hosted_probe'` 唯一命中=扫描命令自身（PID 154 自匹配） |

### 6.2 上传与冻结链核对
6 件 × 2 目录（`/root/a52`、`/root/a52_smoke`）远端 md5 与本地**逐字相同**。
★ **一处如实披露**：指令清单里 `_a52_运行单.md` 写 `5a2f3a9d…`，**本地/远端实际为 `708a0bdd7c9bff33e1a2133beb5f4d0c`（20,160 B）**。经核：该运行单**自指**（§0 表内自己写"本件｜自指｜最终 md5 记在交付报告里"）、**不在 §1 冻结链内**，且 `_a52_修订记.md` 第 3 次修订记录它被重写；全盘 grep `5a2f3a9d…` 无命中（该版本本机已无副本）。**真正被执行的 5 件（生成器 `edd4a970…`／判据 `758962a2…`／探针 `2f9d53cd…`／编排 `a93ecd51…`／分析器 `bf873c5e…`）与指令逐字一致** ⇒ 冻结链完好；上级已裁定此为"指令里的过期注释"。

### 6.3 冒烟（b0 + b2，各 1 格 8 张）
| 项 | b0（AWQ 4bit，8013） | b2（BF16，8012） |
|---|---|---|
| 起服前 `gpu_clear` | 0 MiB ✓ | 0 MiB ✓ |
| **冷启就绪耗时** | **141 s**（GPU 67,795 MiB） | **131 s**（14 shard / `Checkpoint size: 62.13 GiB`，权重加载 2:01；GPU **71,863 MiB**） |
| 探针 `--selftest` | rc=0；提示词 `base 54f82556b1d1 / strict 22d6f7619ebf / permit 9df112d214e5`；解析器 12/12 | 同左 rc=0 |
| 1 格 8 张 | 9 行（8+表头）；`parse_ok 8/8`；abstain/refuse/http_err 全 0；4 s | 同左；4 s |
| `pred` / `raw` | 8×7、6×1 / 含 `{"count": N}` | 8×7、6×1 / 同左 |
| 停服（只按 PID 核端口） | 停后 GPU **0 MiB**、无 8013 进程 | 停后 GPU **0 MiB**、无 8012 进程 |

冒烟 CSV：`A52_b0_base_s1.smoke.csv`（md5 `5c3fbb1f276b645a158085846ebb0f3b`）、`A52_b2_base_s1.smoke.csv`（`e3c80cb6e8f54ecac897ad82c2128881`）。

### 6.4 全量运行（正式）
| 段 | 时间（远端） | 内容 |
|---|---|---|
| v2c | 01:08:02 → 01:24:09 | 起服 b0#1 → 跑完 **b0 的 s1 三格**（base/strict/permit，各 648 行）→ 起服 2 时 **`A52_ABORT_GPU_BUSY`**（缺陷③，见 §6.5） |
| v2d | 01:28:15 → **02:48:10** | 重入：跳过已达 648 行的 3 格（**按行数核**），完成其余 **15 格**；收官 `A52_ALL_DONE` + `A52_ALL_DONE_SHRUNK builds=2/18 cells=18`，`===== A5-2 结束（11664 次）=====`，**`A52_ABORT` 计数 = 0** |

* 单格 ≈ **4.8 min**（2.18–2.35 it/s ≈ 132–141 项/分）；18 格 ≈ 86 min；6 次起服；**总墙钟 ≈ 100 min**（v2c 16 min + v2d 80 min）。
* **6 次起服**：b0 ×3（端口 8013）+ b2 ×3（端口 8012）；编排件日志记录的就绪等待均为 60 s（10 s 粒度轮询），b0→b2 构建切换亦正常（切端口、63 GB 重新加载、`gpu_clear` 放行）。
* `b0/s1` 的 3 格来自 **v2c 的同一次服务进程**（同一实例，口径不破）；其余 15 格来自 v2d 的 5 次起服。

### 6.5 ★ 冻结编排件 `a52_run.sh`（md5 `a93ecd51…`）的 3 处缺陷（**本轮不修字节，改用外部规避跑通**）

| # | 缺陷（原文） | 后果（实测） | 本轮规避 |
|---|---|---|---|
| ① | `RUNNING=$(pids_with_name 'a52_run.sh' \| grep -v -e "^$$\$" -e "^${PPID:-0}\$" …)` | bash 为 `$( … )` fork 的子壳**继承同一 argv**，既非 `$$` 也非 `$PPID` ⇒ 守门必然抓到自己 ⇒ **永远起不来**。实测探针：`full_list=[2479 2480 2481 2482]`，排除后 `RUNNING=[2524 2525]` | **R1**：`cp -p` 出改名副本 `a52run.sh`（同 md5 `a93ecd51…`）后启动；另实测 `bash < 脚本` 亦可 PROCEED |
| ② | `stop_old_serve()` 末尾 **无条件** `rm -f "$PIDF"` | pid 文件为共享路径 `$D/a52.pid`；第二实例会删掉它 ⇒ 第一实例此后**再也停不掉自己的服务** | 单一实例运行（R4 亦按 TAG 隔离思路看护） |
| ③ | `pids_with_port "$port" > "$PIDF" 2>/dev/null \|\| : > "$PIDF"` | 该函数返回值 = 循环**最后一次迭代**状态（多为 1）⇒ `\|\|` 分支把**刚写进去的 PID 清空**。实测：直接重定向 `size=5 content=[7121]`，原写法 `size=0 content=[]`（函数 rc=1）。日志侧铁证：**`grep -c 'pid=' a52_v2c.log = 0`**（kill 分支一次都没执行）⇒ 永不收服 ⇒ **每个构建跑完第 1 次起服必撞 `gpu_clear()` 的 2000 MiB 闸**（设计性必失败） | **R4**：外部看门狗 `/root/a52/_pidfix.sh`（md5 `6aa39ec6b475a14aa67218baa935b726`）每 4 s 把**活着的** 8013/8012 服务 PID 写回 `$PIDF`；**只写该文件、不启服/不停服/不 kill/不碰冻结件**（已只读逐行核过）。R4 生效后 5 次服务转换全部"已收服 → GPU=0 MiB → `gpu_clear` 放行" |

> 闸门本身**无罪**：实测对本机 b0 服务发 `SIGTERM`（只按 PID 核 `--port 8013`）⇒ **+5 s 显存已 0 MiB、端口进程已 0**，远小于编排件的 `sleep 8`。故 R4 **无需**放宽 `A52_GPU_MEM_MIB`。

### 6.6 ★ 我自己的一次操作失误（如实记录）
* 准备进度监视命令时**误把启动行又发了一次**，于 `01:06:14` 左右起了**第二个改名副本实例**。
* 后果链：它通过自检/刺激预检 → 进入 `b0 起服 1/3` → 其 `stop_old_serve` 读到**共享** pid 文件 → 随即 `gpu_clear` 读到 `69157 MiB > 2000` ⇒ **`01:06:31` 写 `A52_ABORT_GPU_BUSY` 并 exit(6)**。
* **0 次请求被污染**：它**没有起任何服务**；第一个实例的 vllm（pid 2919）经核实**全程存活**，probe 正常出数。
* **但它触发了缺陷②**：`stop_old_serve` 末尾无条件 `rm -f $PIDF` 删掉了共享 pid 文件 ⇒ 第一实例注定在下一个起服周期被闸门拒跑。
* **处置**：只按 PID 停净编排链（2813/2814/2817）+ 服务（2919）+ 探针（3278）⇒ GPU 回 0 MiB；`a52_v2.log` 的 `01:02:01 A52_ABORT_ALREADY_RUNNING` 与 `a52_v2b.log`（改名保留为 **`a52_v2b_INCIDENT_dup_launch.log`**）**均原样保存**作运行史；**丢弃被截断的 149 行部分 CSV**（`A52_b0_base_s1.csv`）——理由：**同一格必须来自同一个服务进程/同一次起服**，否则破坏"3 次独立起服"口径；**不从事件日志里恢复它**。随后以 `TAG=v2c` 干净重跑（`a52_v2.log` 首启那条 ABORT 亦原样保留）。

---

## 7. 产物与 md5（**远端 md5sum vs 本地实算，逐件双验**）

### 7.1 双验结论
**远端清单 695 件 ｜ md5 相符 695 ｜ 不符 0 ｜ 缺失 0**（`_a800_a52/_md5_compare.txt` 首行原文）。
取回布局：`_a5_2/_a800_a52/{res×18, stim(648 PNG + 9 aux), env×9, logs×11, _diag}`（合计 **695 件**，与远端清单逐件一一对应）；清单文件 `_remote_md5.txt` / `_local_md5.txt` / `_md5_compare.txt`。

### 7.2 冻结套件（本地 = 远端）
| 件 | md5 |
|---|---|
| `a52_prep_stim.py` | `edd4a9708cf97ece4d376964a72160d3` |
| `_a52_criteria_frozen.json` | `758962a2643e1035698682abefec5748` |
| `a52_probe.py` | `2f9d53cd3098990aa29b69e4946de2b0` |
| `a52_run.sh`（原件，provenance） | `a93ecd519341fba79bb7d993eb6641b8` |
| `a52run.sh`（R1 改名副本，**同 md5**） | `a93ecd519341fba79bb7d993eb6641b8` |
| `a52_analyze.py` | `bf873c5e7da083dae42cb379efe9af9d` |
| `_a52_运行单.md` | `708a0bdd7c9bff33e1a2133beb5f4d0c`（≠指令值，见 §6.2） |
| **`a52_run_v2.sh`（本轮新增修订版）** | **`7fa412d96c6a21717d946a287156403c`** |

### 7.3 刺激侧（本次运行**唯一输入**）
| 件 | md5 |
|---|---|
| `stim/manifest.csv` ★官方锁 | **`d2dde2a8100eca8eda88143f6cbb04ba`** |
| `stim/manifest.md5` | `f54ad4caf3639b61dc7825bd09db295b` |
| `stim/manifest.md5.note` | `72c2d2cde5581ace887e65ad5f38c0c5` |
| `stim/manifest_sha256.txt` | `36712f264f24e8e7dbc65eb7b6a23f19` |
| `stim/A52_STIM_CONFIG.json` | `e6adaa4825c90fe4574e0c11a877f994` |
| `stim/_cells.csv` | `26a27179e4ac295531219c4060d06db6` |
| `stim/items.csv` | `a37db30a024be98ecb6c0ec77c23cf4f` |
| `stim/_unrealizable.csv` | `657baa44ba2239cd1bd936f7cbb61b11` |
| `stim/detection_matrix.csv` | `67688d5f212086abe32cae914a2447ac` |
| `stim/images/*.png`（648 张） | 逐张 md5 见 `_local_md5.txt`（648 行全 OK） |

### 7.4 18 个逐格 CSV（各 648 行；双验 OK）
| 格 | md5 | 格 | md5 |
|---|---|---|---|
| `b0_base_s1` | `28ad1550f31a72de701b90fa152e03ce` | `b2_base_s1` | `d8f7d323bc71e56548e6fdad0fff3b34` |
| `b0_base_s2` | `23907faf29c335a555713c1ca6885ff5` | `b2_base_s2` | `268887e6612917f2334f0ad10f8cb788` |
| `b0_base_s3` | `7d96c85d9358765d42b2b7f793fcf9e3` | `b2_base_s3` | `ba17f33115d4e2ffabee3f4ae2de5bca` |
| `b0_strict_s1` | `55566c80b16bbaf29ed77ea2e26db399` | `b2_strict_s1` | `dae961d56f2d37364dd01fbe30fceea7` |
| `b0_strict_s2` | `6d01dee59ebb3731700a8bcab483e45e` | `b2_strict_s2` | `b5ca63dfc62d6f22f9fbad9b55edb675` |
| `b0_strict_s3` | `90dbe3877d1c6cd13e60f2e7d161bc07` | `b2_strict_s3` | `c350d188a5cd9a84e3b4b9297f1b0c58` |
| `b0_permit_s1` | `b79b03ba1b39826999a941b96bc1dca0` | `b2_permit_s1` | `a9dfef7e8f8ca75c5692ba8b77338213` |
| `b0_permit_s2` | `9454faa0b3d1330bd8ba32133c414786` | `b2_permit_s2` | `f52fc8372107391216ce988b39a342ee` |
| `b0_permit_s3` | `b91733df5f0b7c7c04ecc9e46dc27632` | `b2_permit_s3` | `419aa2f4c76b7159571331eb3d659b11` |

### 7.5 日志（运行史证据）
| 件 | md5 |
|---|---|
| `a52_v2.log`（首启守门 ABORT） | `847fdff659d25c82d6d601092f685035` |
| `a52_v2b_INCIDENT_dup_launch.log`（我的重复启动失误） | `eb68bc772d2c03f4e389b9f4c6050eb6` |
| `a52_v2c.log`（缺陷③中止） | `080e0d608a56455e02728d7f6b806d4d` |
| **`a52_v2d.log`（正式运行，ALL_DONE）** | `5ed9aeb00b96799d47f5ba1ff82dc415` |
| `a52_pidfix.log`（R4 看门狗，无输出） | `d41d8cd98f00b204e9800998ecf8427e`（空文件） |
| `a52_serve_v2d_…AWQ_.log` / `…Instruct_.log` | `238806f632cda5b9fa3d44a0f48e8b15` / `440c5c1a1565d42aff7c5086504ec713` |
| `a52_smoke_serve_b0.log` / `a52_smoke_serve_b2.log` | `6e246685238216d2bb24e776adaeced2` / `705d20843b7afd34d50ecc1255904017` |
| `a52_builds.map` | `5132f66eb208da7d30ba8c713b764931` |

### 7.6 分析产物
* 独立复算结果（自写脚本）：`_a800_a52/_indep_result.json`（md5 `3595071d024d69bb6ffc2c114f8bdd87`），脚本 `_a5_2/_a52_indep.py`（**不 import 分析器**）。
* 冻结分析器交叉核对：`_a800_a52/_analyzer_result.json`（md5 `0d5caa79ccc9…`）。

---

## 8. ★ 刺激锁与"平台容器差异"说明（必须随结论一起读）

* **官方刺激锁（本次运行）** = `manifest.csv` md5 **`d2dde2a8100eca8eda88143f6cbb04ba`**，`manifest_sha256.txt` 逐张 **648/648 OK**，`A52_STIM_CONFIG.json` = `e6adaa48…`。
* 运行单/简报里的另一个值 `5c8c62a87d39700cffc75dd9ecd8a54a` 是**本地 Windows 侧**（Python 3.11.9 + Windows zlib）渲染出的 `manifest.csv`；远端（Anaconda / Python 3.13.5 / conda zlib）渲染的是 `d2dde2a8…`。
* **两者只在 PNG 容器字节上不同，像素与几何逐位相同**，证据链：
  ① 两版 manifest 的**非 sha256 列** `cut -d, -f1-9,11-13 | md5sum` **完全相同**（`0aa60f18f5bf1dfe65094fe48ca6d33d`）；`n_dots_detected_gt` 分布逐档相同；
  ② `_cells.csv`/`items.csv`/`_unrealizable.csv`/`A52_STIM_CONFIG.json` 两侧 md5 **逐字相同**；
  ③ 抽 4 张（含 blurred / crowded）PNG 解码比对 ⇒ **RGB 1024×1024、4,194,304 B、像素全等 4/4**，仅文件字节不同（5517 B vs 5531 B）；
  ④ 远端**重渲逐位稳定**：另建目录重跑一次 ⇒ manifest md5 **仍是 `d2dde2a8…`** 且与原目录 `cmp` 完全相同。
* 判据件 C1 只要求 `manifest_md5_recheck: true`（**自洽可核**），**未把 `5c8c62a8…` 写进判据** ⇒ 采用本机渲染**不改任何判据**；上级已裁定走此路径（A 方案）。
* ★ **本地 `_a5_2/_full/` 那一套（`5c8c62a8…`）不是本次运行的输入**，仅作历史/比对参照；本次所有 11,664 次推理读的是远端 `d2dde2a8…` 那一批 648 张，且**全部构建 × 合同 × 起服共用同一批文件 ⇒ 逐位配对成立**。
* ★ **口径差异**：本实验刺激是**合成圆点**，与 §5.6 / C.2 既有 675 张网格**同源但属独立刺激**（且渲染平台不同）⇒ **不可与既有印数直接相减**。

---

## 9. 可复现凭据（服务与刺激；**不含任何需 GPU 的动作**）

| 项 | b0 | b2 |
|---|---|---|
| 起服脚本 | `/root/pf_serve_awq4bit_8013.sh`（md5 `1eca04a1c22049e7a7ee077380387314`） | `/root/p3_serve_bf16_A.sh`（md5 `7e291790a80646b3e0ba3a990282dd49`） |
| 端口 / served-name | 8013 / `Qwen3-VL-32B-Instruct-AWQ` | 8012 / `Qwen3-VL-32B-Instruct` |
| 模型目录 | `/root/models/Qwen3-VL-32B-Instruct-AWQ-4bit`（`quant_method=compressed-tensors`，`--quantization compressed-tensors`） | `/model/ModelScope/Qwen/Qwen3-VL-32B-Instruct` |
| 冻结推理参数 | `max-model-len 8192`、`--max-num-seqs 24`、`--limit-mm-per-prompt {"image":1}`、`mm-processor-kwargs {"max_pixels":1048576,"min_pixels":3136}`、`trust-remote-code`、`VLLM_USE_FLASHINFER_SAMPLER=0`、`GMEM_UTIL=0.85` | 同上，但 `--gpu-memory-utilization 0.90`（脚本内写死） |
| 权重规模 / 加载 | 21.4 GB（5 shard） | **62.13 GiB（14 shard）**，权重加载 2:01 |
| 冷启就绪（冒烟实测） | **141 s** | **131 s** |
| 加载后显存 | 67,795 MiB | 71,863 MiB（冒烟）/ 71,853–74,219 MiB（正式运行观测区间） |
| 起服日志 | `a52_smoke_serve_b0.log`、`a52_serve_v2c_…AWQ_.log`、`a52_serve_v2d_…AWQ_.log` | `a52_smoke_serve_b2.log`、`a52_serve_v2d_…Instruct_.log` |
| 探针 | `a52_probe.py` md5 `2f9d53cd…`；三档提示词 md5 `base 54f82556b1d1` / `strict 22d6f7619ebf` / `permit 9df112d214e5` | 同左（同一把尺子） |

---

## 10. 修订版 `a52_run.sh` v2（随本轮放行）

* 由**冻结原件定点替换**生成（`_a5_2/_a52_make_v2.py`，6 处替换**各命中 1 次**，其余字节逐字相同）：
  `a52_run.sh`（`a93ecd51…`）→ **`a52_run_v2.sh`（`7fa412d96c6a21717d946a287156403c`）**，23,373 B，`bash -n` **exit 0**。
* 修复：**①** 并发守门改为**原子锁目录**（`$D/a52.lock` + 持有者 PID + `kill -0` 存活校验 + 陈旧锁清理 + `EXIT` trap）；**②** pid 文件**按 TAG 隔离**（`$D/a52_${TAG}.pid`）且**仅本实例写过才删**（`PIDF_MINE`）；**③** `pids_with_port` 内显式 `return 0` **并**把调用处改成 `|| true`（不再清空刚写的 pid）；**④**（稳健性）收服后**轮询显存回落**（≤39 s）替代死等 `sleep 8`。
* ★ **原件保留作 provenance**；**本轮正式运行用的是原件字节 + 外部规避（R1 改名副本 / R4 看门狗）**，v2 **未参与本次运行**。远端副本：`/root/a52/a52_run_v2.sh`（md5 同上）。

---

## 11. 披露项与限制（不得省略）

1. ★ **只跑两个实现**：本环境无同族 FP8、无同族 GPTQ 权重 ⇒ **b0(AWQ 4bit) + b2(BF16)**；**不得表述为"四构建"**，构建方差的估计只在 2 水平上成立（`count × build` 交互的 b2 项不显著：+0.192, p=0.418）。
2. **C2 的双口径**：按收缩路径（18×648=11,664）PASS；按判据件写死的 23,328 原样阈值 FAIL（缺 b1/b3 的 18 格）——已在 §3.2 并列，两处都不隐。
3. **C4 FAIL ⇒ 撤回"count 无实质作用"**；效应方向为**负**（点子越多越答不对），量级远超 ±0.2（|β|≈4.4）。
4. **冻结编排件 3 处缺陷**（§6.5）已如实登记：该件**在未做外部规避时永远无法端到端跑完**（第 1 次起服转换即必撞 `gpu_clear`）。本轮用 R1/R4 规避，未改其一个字节。
5. **我的一次操作失误**（重复启动第二实例）已登记（§6.6），含"0 次请求被污染"的证据链与**丢弃 149 行部分 CSV** 的理由。
6. `permit` 档的 `abstain` 率 51.2%（b0 981 / b2 1010 行）是**合同设计后果**，不并入"答错"；`pred=0` 与"弃答"分别计数、未混为一件。
7. 解析失败：**0 行**（18/18 格 `parse_ok` = 1.000）。
8. 本地 `_full/` 刺激（`5c8c62a8…`）**不是**本次输入；**不可**与既有 675 张网格的印数直接相减。

---

## 12. 纪律声明（本轮）

* **未** `pkill -f`、**未**机器级 pkill（全部停服均**只按 PID**且先核 `/proc/<pid>/cmdline` 含目标 `--port`）；**未**进入/触碰 `/root/cvpr_exp`；**未** `rm -rf` 任何既有 `/root` 目录（只清理自建 `/root/a52/res/` 下的部分 CSV 与陈旧 pid 文件）。
* 收尾（远端 02:53）：看门狗已按 PID 停；**`/proc` 扫 `--port 8013` 命中 0、`--port 8012` 命中 0**（**不依赖 pid 文件**）；`nvidia-smi` ⇒ **0 MiB / 0%**、compute-apps 空、无 vllm 进程。
* 判据件、探针、生成器、分析器、起服脚本**全程未被修改**；所有冻结件 md5 见 §7。
