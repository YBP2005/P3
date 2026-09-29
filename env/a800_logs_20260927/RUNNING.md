# A800 交接说明（2026-09-26 04:10 UTC）—— 交 P3 使用

> **2026-09-26 09:50 UTC 状态更新（会议侧）**：机器**全空、GPU 0 MiB**，
> 六个队列全部收尾。此后我只做了两件占卡工作：Step3-VL-10B 的加载器修复与预算扫，
> 以及一次**默认路径回归探针**（见文末 §7）。**GPU 现已再次归零，可继续交回。**

## 1. 当前状态：**机器全空，可以放心用**
- `nvidia-smi`：**0 MiB / 0%**，没有任何进程占卡。
- 我的**所有队列都已结束**（日志里都有 DONE 标记）：

| 队列 | 结束标记 | 日志 |
|---|---|---|
| E · P2PNet 9 臂 | `E_P2P_ARMS_DONE` | `results/logs/e_p2p_arms_outer.log` |
| 32B 面板第二批 | `B3_PANEL2_DONE` | `results/logs/b3_panel2.log` |
| 32B 面板第三批 | `B3_PANEL3_DONE` | `results/logs/b3_panel3.log` |
| 航拍专家矩阵 18 臂 | `E_AERIAL_ARMS_DONE` | `results/logs/e_aerial_arms_outer.log` |
| 剂量-反应 12 臂 | `E_DOSE_ARMS_DONE` | `results/logs/e_dose_arms_outer.log` |

- 我已停掉自己的状态监视脚本。**在你说"任务结束"之前，我不会在 A800 上起任何新任务。**

## 2. 请勿覆盖的目录（都是我的产物）
- `/root/cvpr_exp/`（整个工作目录：`cache/`、`maps/`、`manifests/`、`results/`、各脚本）
- `/root/p2pnet/`（P2PNet 仓库 + SHTechA 权重，md5 `f2b448cc81137a78beae90fc119c70ef`）
- `/root/dense/`、`/root/aerial/`、`/root/fsc147/`、`/root/z0/`（评测图，共 2064 项）
- `/root/RUNNING.md`（本文件）

可以自由使用的：`/model`（共享模型库，`df` 显示 40 T / 已用约 29 T）。

## 3. 共享库里**没有** InternVL / Phi（今天我做过全量普查）
`/root/_search_vlm.log` 里的结论，摘要：
- `*InternVL*`、`*Phi-3*` **0 命中**（`/model` 下没有 `OpenGVLab` 这个组织）
- 有：`Qwen3-VL-{4B,8B,32B,32B-Thinking,30B-A3B}`、`Qwen2.5-VL-{3B,72B}`、
  `stepfun-ai/Step3-VL-10B`、`llava-hf/llava-onevision-qwen2-0.5b-ov-hf`
- **A800 有完整公网**（modelscope 302 / huggingface 200 / github 200），真要 InternVL3.5-8B
  可以 `modelscope download --model OpenGVLab/InternVL3_5-8B` 直接拉

## 4. 本机可用的传输工具（今天实测过）
`/usr/local/miniconda3/bin/python /root/cvpr_exp/bxfer.py pull|push|gets`，A800 主动连 B机 25046 一跳，
**实测 10.4 MB/s（拉）/ 12.1 MB/s（推）**，自动核 md5；凭据只从环境变量读。
> 注意：pod 只对外暴露 25046，**A800 反起 http.server 给别人 curl 是通不了的**。
> paramiko 已装在 miniconda（5.0.0）。

## 5. 三个容易踩的坑（我今天各踩了一次）
1. **不要用全局 `pkill python`**；`pkill -f "关键词"` 会匹配到**执行它的那个 shell 自己**，
   要用字符类绕开（例：`pkill -f 'run_arm\.p[y]'`）。清理请只按自己的 PID / 端口。
2. **显存要按"最坏那一张图"算，不是按权重算**：P2PNet 的 VGG16 对 2500×1875 图的激活要 5–9 GB；
   它的匈牙利匹配还会建 (锚点数 × 点数) 的代价矩阵（UCF-QNRF 最密的图 12,865 点 ⇒ 单次 2.25 GB）。
3. **官方 P2PNet 把 anchor points 硬编码 `.cuda()`**（`models/p2pnet.py` 的 `AnchorPoints.forward`）
   ⇒ 想用第二张卡必须 `CUDA_VISIBLE_DEVICES=1` 再用 `cuda:0`，直接 `--gpu 1` 会报
   `Expected all tensors to be on the same device`。

## 6. 你完工后我会做什么（只需要你一句"结束了"）
我这边积压的 A800 任务（全部已写好脚本、可直接跑）：
1. **密集域适配的对称矩阵**：B机正在训 UCF-QNRF 专家 ×2 seed，训完要拉过来建 cache + 跑臂
   （`e_aerial_infer.py` + `e_aerial_arms.sh` 已经在机，改一行 tag 即可）。
2. **剂量-反应补 field 接口**：现在剂量面板只跑了 `symbol_text`，
   补 `dense_field` 才能把"场接口不随专家变好"这条画完整。
3. 可选：32B 侧的 P2PNet 对照臂。

请完工后告诉我，我会确认 GPU 真的空出来（`nvidia-smi` + `pgrep`）再起任务。

---

## P3（PaperB 分支）接手记录 —— 2026-09-26 04:25 UTC

**接手人**：P3 / PaperB 分支（`<WORKDIR>\PaperB\`）。
**用途**：P2 实验包（PaperB 内部编号，对外任务号 P3）的"外部真零池"VLM 探针。

### 我方会做什么

* **只跑推理，不训练。** 单卡串行：一族起服 → 跑完 → 停服 → 起下一族。
  **绝不并发**（单卡 0.85 利用率并发会 OOM —— 沿用机上既有纪律）。
* 四个构建与既有语料**完全一致**（否则与已发表数字不可比）：
  | 构建 | 路径 | 端口 | 显存比例 | maxlen |
  |---|---|---|---|---|
  | Qwen3-VL-32B-Instruct | `/model/ModelScope/Qwen/Qwen3-VL-32B-Instruct` | 8006 | 0.85 | 4096 |
  | gemma3-12b | `/model/ModelScope/LLM-Research/gemma-3-12b-it` | 8001 | 0.40 | 8192 |
  | InternVL3_5-8B | `/root/models/InternVL3_5-8B` | 8002 | 0.28 | 8192（`--trust_remote_code`）|
  | Phi-3.5-vision-instruct | `/root/models/Phi-3.5-vision-instruct` | 8003 | 0.30 | 8192（`--trust_remote_code`）|
* **停服纪律**：**不** `pkill -9 -i -f vllm`；只杀本脚本自己记下的 SPID。
  每族前后用 `/root/_p1d_reaper.sh` 检查并回收 **PPID==1 的孤儿 `VLLM::EngineCore`**
  （父进程被 -9 后子进程会被 init 收养并继续占显存——机上已有此教训记录）。

### 我方不会动

* `/root/cvpr_exp/` 及其下全部内容（你方工作目录），你方的 `*.pid` 与端口。
* `/root/models/`、`/model/` 下任何文件（只读使用）。
* 你方 `/root/RUNNING.md` 已有的内容（本段为**追加**，未改动上方任何一行）。

### 我方产物位置

* `/root/p2/`（池与判据留档）、`/root/p2_probe_results/`（探针逐条结果）、`/root/p2_pool_imgs/`（池图像）。
* 日志：`/root/logs/p2_*.log`。

### 结束时会做什么

* 停掉全部我方服务、跑一次 `_p1d_reaper.sh`、确认 `nvidia-smi` 归零，并在本文件追加一行"P3 完成"。

### P3（PaperB）完成 —— 2026-09-26 05:15 UTC

**P2 实验包（对外任务号 P3）的 A800 段已全部结束。**

* 已完成：**4 构建 × 3 臂 × 300 张 = 3,600 次调用**（Qwen3-VL-32B-Instruct / gemma-3-12b-it /
  InternVL3_5-8B / Phi-3.5-vision-instruct）；
  **噪声底自测**（锚构建 × 同一 20 张 × 两遍：pred 与 raw 均 20/20 一致 ⇒ 点估计 0.00 pp）；
  产物 QA（12 个臂文件全部 n=300，其中 Phi 的 permit 臂有 2 条未解析，已如实记录）。
* 唯一用到的起服参数变更：**32B 去掉 `--gpu-memory-utilization`**（用 vLLM 默认 0.90）。
  原因：0.85 时 63 GB 权重装入后 KV cache 只剩 0.76 GiB，而 `--max-model-len 4096` 需 1.0 GiB
  （`ValueError: … estimated maximum model length is 3104`）。
  **`--max-model-len 4096` 未改**——它是与已发表语料可比的配置。
* **机器状态**：`nvidia-smi` **0 MiB / 0%**、**无 vLLM 进程**、无我方残留脚本进程
  （已核验；我方曾因本地超时留下过卡住的 `bash -c`，已全部清理）。
* 我方产物：`/root/p2_probe_results/`（原始）、`/root/p2_probe_results_reparsed/`（**修正后，结论以这份为准**）、
  `/root/p2_noise_rep{1,2}/`、`/root/p2/`、`/root/p2_pool_imgs/`、`/root/logs/p2_*.log`。
  **全部已取回 P3 侧工作机**，A800 上的副本可随时删除。
* **一条给后来者可复用的教训**：`/root/_p1d_reaper.sh` 是 `while true; … sleep 15; done` 的
  **常驻守护**，**不能同步调用**（会让调用方永久挂住）。需要一次性回收时，用一次性扫描：
  `ps -eo pid,ppid,comm | awk '$2==1 && $3 ~ /^VLLM::EngineCor/ {print $1}'` 后 `kill -9`。

---

## 7. 会议侧追加（2026-09-26 09:50 UTC）：Step3-VL-10B 查清 + 冻结判据机回归

**GPU 状态：0 MiB，无残留进程。** 本节只追加，未改动上面任何一行。

### 7.1 Step3-VL-10B 的三层结论（推翻了"这个模型不能用"）

1. **HF `transformers` 进程内加载会静默损坏**：`model.safetensors` 用**去壳**键名
   （`model.embed_tokens.weight` / `model.layers.*` / `vision_model.*` / `vit_large_projector.*`），
   而模型类要**带壳**键名（`model.language_model.*` / `model.vision_model.*` / `model.vit_large_projector.*`）。
   `from_pretrained` **不抛异常**，只报 **MISSING 1065 / UNEXPECTED 1065**（1066 个键里只有
   `lm_head.weight` 对上），⇒ 随机初始化 ⇒ **前向照常跑完、输出乱码**。
   修法：`exp/run_arm.py --key-mapping /root/step3_keymap.json`（新加，默认关），
   表由 `exp/make_key_mapping.py` 生成（`--expect-entries 1066` 防半表）⇒ **MISSING 0 / UNEXPECTED 0**。
2. **改它自己的源码也做了，但只在私有副本里做**：`/root/step3_local/`（19 GB 副本，
   原文件备份 `modeling_step_vl.py.orig`），两处最小补丁（用 `model_inputs["cache_position"]`；
   解码步丢弃 `pixel_values/patch_pixel_values/patch_newline_mask/num_patches`）。
   **共享库 `/model/ModelScope/stepfun-ai/Step3-VL-10B` 一个字没动。**
3. **但它在级联面板的提示词下进不了面板 —— 理由是预算，不是模型**：
   冻结 16 token ⇒ 5/5 `format_violation`（0 个整数）；256/512/1024 token ⇒ `</think>` **都不闭合**
   （1024 时 36 s/项）。而 **P-W1 面板**（`/root/w1_results/`）里同一个 checkpoint 走 **vLLM**
   是正常的：`</think>` 正常闭合、JSON 契约满足、`parse_ok` 48–93%。
   ⇒ **"预算够不够"是"提示词 × 预算 × 服务栈"的函数。**

**顺带做的栈级体检**（这条对 P3 也有用）：对 `/root/w1_results/` 全部存档做乱码 QC
（非 ASCII/非 CJK/非常见标点字符占比 > 30% 判乱码）⇒ **165 文件 / 66,174 行 / 乱码 0 行**，
`results/report/w1_gibberish_qc.json`。**P-W1 面板没有被这条加载器缺陷污染。**

### 7.2 冻结判据机 `run_arm.py` 的改动与回归

新加 4 个**默认关**的开关：`--trust-remote-code`、`--model-class {image_text,causal}`、
`--inject-cache-position`、`--key-mapping PATH`。
**回归证据**（不给任何新开关，7B，3 项，`visdrone_aerial_vis_eval · symbol_text · base`）：
`raw` = `69 / 2 / 3`、`score` = `1.000000`，与既有臂
`results/arms_full/visdrone_aerial_vis_eval__symbol_text__base__qwen3vl8b.csv` 前 3 行
**逐字段 IDENTICAL**。`key_mapping*` 三个新字段在 `logs/serving_*.json` 里为 `null`，
**不进 CSV**，所以既有的 200+ 条臂语义一字未变。

### 7.3 新增/更新的产物

- `/root/step3_keymap.json`（1066 条，md5 `4f4356f739f0c51c3fe11dec1380cf8e`）
- `/root/cvpr_exp/results/report/`：`w1_gibberish_qc.json`、`probe_step3_nt{16,128}.csv`、
  `probe_step3_budget.log`、`_parse_step3.py`、`_step3_budget.py`、`w1_gibberish_qc.py`
- `/root/cvpr_exp/exp/`→`make_key_mapping.py`（`run_arm.py` 已更新，md5 见 `md5sum`）

**A800 可以继续交回。**

**A800 现在可以交回会议侧。**

---

## 8. 正式交接回 P3（2026-09-26 10:00 UTC）

**★ 请先读独立交接文档：`/root/A800交接说明_给P3_20260926.md`**（11 KB，
覆盖机器现状 / 环境版本 / 共享模型库 / 我方目录 / 单卡纪律 / 磁盘回收表 /
Step3-VL-10B 的两个坑 / 可复用工具 / 我还需不需要卡）。

交接时的实测状态：

| 项 | 状态 |
|---|---|
| GPU | **0 MiB / 0%**，`nvidia-smi -L` 仍是单卡 `GPU 0: A800-SXM4-80GB` |
| 残留进程 | **无**（`run_arm.py` / `vllm` / 训练 / 我的脚本全部为空） |
| 磁盘 | overlay **286 G，可用 113 G（59%）** —— 我清掉了 Step3 的 20 G 权重 |
| 我回收了什么 | `/root/step3_local` 的 5 个 `*.safetensors` + 索引（20 G）。**源码补丁保留**（现 16 MB），权重在共享库里随时可重建副本 |
| 我新增了什么 | `/root/bin/tectonic`（单文件 LaTeX 引擎，**纯 CPU**，30 MB）、`/root/paper_build`（论文编译目录，< 1 MB）、`pypdf` |
| GPU 侧新增 | **无**。`run_arm.py` 加了 4 个**默认关**的开关，默认路径回归已验 `raw` = 69/2/3 逐字段 IDENTICAL |

**我这边不再需要 GPU。** 只需保留 `/root/cvpr_exp/`（25 G，论文数字的唯一来源）与
`/root/w1_results/`（374 个逐项 CSV）；其余按交接文档 §6 的回收表处理即可。

**P3 可以接手了。**

---

## P3 / PaperB（期刊扩展版）接手段 —— 2026-09-26（P3 侧智能体追加，未改动上方任何内容）

**结论：P3 侧已用完 A800，可再次交还会议侧。**

### 我做了什么（全部单卡串行，**未并发**）

| 实验 | 内容 | GPU 用量 | 结果 |
|---|---|---|---|
| ① `--workers 4` 噪声底 | 锚构建 × `base` 臂 × **全 300 项池** × **4 并发** × **3 遍** | ≈8 分钟（含起停服） | **900/900 逐项一致**；报单侧 Clopper–Pearson 界：按批 **3.92 pp** / 逐项 0.99 pp / 按池聚类 77.6 pp |
| ③ 英文提示下的弃权份额 $S$ | 锚构建 × `base` × 四头条域 × **M.39 那张冻结英文表** | ≈6.6 分钟（0.7/2.0/3.0/0.9） | 中文侧口径先自证 **4/4 对上 J.1**；英文下 st_a 的 $S$ **越过 100%**（离开定义域）、两个航拍域 −4.1/−5.5 pp、**ucf 因 HTTP 400 不可测** |
| ② 混合池真值 $\pi$ | —— | **0**（决定不做：瓶颈是标注人力，用户裁定） | 已记档，未跑 |

**未使用的余额**：约 **160 GPU·h** 仍在，**我一分钟都没多占**。

### 我用了哪些冻结件（**一个字节都没改**）

| 文件 | md5 | 用途 |
|---|---|---|
| `/root/19e_probe_multi.py` | `03edb14c98ffa3aea9ffa20f59b00bc8` | ① 与 ③ 的探针（与交接件 §5 记录一致） |
| `/root/p2/pool_all/pool_frozen_a800.csv` | `25ee5c02109937753aa52c433fd8876a` | ① 的 300 项池 |
| M.39 英文提示词表（在 `ec3_run_en.py` 内，逐字复制自 `20b_probe_lang.py`） | `a31bd97c6b70` | ③（与补充材料 M.39 记录的表 md5 一致） |

### 我在 A800 上新增的文件（**都与会议侧目录不重名**）

- `/root/ec3_run_en.py`、`/root/ec3_share3.py`、`/root/ec3_compare2.py`、`/root/ec3_share2.py`
- `/root/p2_noise4.sh`、`/root/p2_noise3_cmp.py`
- `/root/ec3_en/`（64 KB，四域英文臂记录）
- `/root/p2_noise4_rep{1,2,3}/`（各 ~25 KB）
- `/root/logs/p2_noise4.log`、`/root/logs/ec3_serve.log` 等日志

**⇒ 这些全部是我的产物，可随时删；会议侧的 `/root/cvpr_exp/`、`/root/w1_*`、`/root/models/`
（InternVL3_5-8B / Phi-3.5-vision）**我一行未动**。**

### 交接时的实测状态（2026-09-26 10:26 UTC）

| 项 | 状态 |
|---|---|
| GPU | **0 MiB / 81920 MiB，利用率 0%** |
| 计算进程 | **空**（`nvidia-smi --query-compute-apps` 权威判据） |
| 残留 | 无 `python` / `vllm` / `VLLM::EngineCore`（已按下文 §5 的有界扫描回收） |
| 磁盘 | overlay **286 G，可用 113 G（59%）** —— 与接收时**一致**（我的产物共 < 1 MB） |

### 两条给下一位的操作提醒（我实际踩到过）

1. **`/root/...` 作为参数传给 Windows 侧的 python 会被 Git Bash 改写成
   `D:/腾讯电脑管家软件搬家/…/Git/root/...`** ⇒ 传远端路径前必须
   `export MSYS_NO_PATHCONV=1 MSYS2_ARG_CONV_EXCL='*'`。
2. **A800 上 `python3` 没有 PIL**；要用 **`/usr/local/miniconda3/bin/python`**。
   否则 `b64_of` 会**每一条都失败**，而脚本**仍然正常退出**（"看起来跑完了、其实全失败"）。

**P3 侧完毕，卡可交还会议侧。**

---

## 9. 会议侧接手：末批单卡任务（2026-09-26 10:39 UTC 起）

**P3 已交还（GPU 0 MiB、无残留进程），会议侧正在跑最后一批单卡任务。**
5 个 job 全部自动接力，**一次启动、后面自动排队**：

| # | job | 内容 | 依赖 |
|---|---|---|---|
| 1 | `b2_xdom_extract.sh` | **B2 跨域**：16 个池各用**自己的专家符号**重抽冻结特征（prefill-only） | — |
| 2 | `e_final_queue.sh` | **补表**：18 条 8B 臂（`dense_field`×2 专家 + `symbol_image`×4 新专家）+ 5 条 32B 臂 | 等 1 |
| 3 | `b5_pipeline.sh` | **B5 航拍 adapter**：专家打符号 → 训 real/shuf 两个 adapter → 4 条臂 | 等 2 |
| 4 | `b2_xdom_head_watch.sh` | B2 跨域**判据**（纯 CPU，不占卡） | 等 1 |
| 5 | `e_report_after_final.sh` | **全套判据自动重算**（纯 CPU） | 等 2+3 |

**为什么串行**：单卡。1/2/3 各占满显存；4/5 只读 CSV/npz，不占卡。

### 9.1 ★ 新增的一条纪律：汇总表必须**由脚本自己写文件**

今天发现论文 §3/§6/§7/§8 引用的三口径 w 表是**手工重定向留下的过期快照**
（`results/report/wdef_table.txt` 停在 05:37 的 **26 桶**，而臂清单早已是 **35 桶**：
w1 = 27/35、w2 = 0/35、w3 = 0/35）。
根因是 `b64_wdef.py` **只 print、不写文件**。

**已修**：`b64_wdef.py` 现在把 stdout **tee** 进 `results/report/wdef_table.txt`，
并在末尾写**输入指纹**（臂文件数 + 名字与大小 md5 + 生成时间）。
`e_report_all.sh` 也新增了第 7/8/9 节，把这张表和两个新判据都纳进来。
⇒ **教训：凡被论文引用的汇总表，必须由脚本自己写文件；"我跑过了"可能只是打到了屏幕上。**

### 9.2 跑臂前的预检结论（省下的是白跑的时间）

* `maps/{ucf,fsc}_index.csv` / `maps/bay_eval_index.csv` 与 cache **2064 = 2064**，
  `count_cached` 与 cache `count` 相对差 **中位/p90/max 全为 0.0000**，抽样 200 个 PNG **全在**。
* **`maps/*_index.csv` 的 `bad` 列不是布尔，是 QC 代码，且不是阻断项**：
  论文自己在用的 `dmcount_eval` 索引有 **61.8%** 行 `bad=2`，`bay_eval` 有 70.0%，
  而 `bad!=0` 行的 `rel_err_png_vs_clamped` 中位只有 **6.4e-7 / 7.6e-7**
  ⇒ 渲染 PNG 忠实重建了被截断的场。
  **判据**：只要 `rel_err_png_vs_clamped` 在 1e-5 量级且 PNG 存在即可用；
  **不能因为 `bad != 0` 就跳过**——那会把论文里已经用着的臂一起否掉。

### 9.3 后台作业的启动方式（今天踩到的）

`nohup bash x.sh &` 在 SSH 会话里**会被会话退出带走**（第一次启动的作业连日志都没建）。
必须 **`setsid nohup bash x.sh > /dev/null 2>&1 < /dev/null &`**，
并立刻用 `pgrep -af "x.s[h]"`（字符类，避免匹配到自己）确认进程活着。
另外：`cd A && nohup B & sleep 10; tail C` 里 **`cd` 也在后台子壳内**，
前台用的是原工作目录 ⇒ 后续命令要用**绝对路径**或另起一行 `cd`。

### 9.5 ★ 看门狗的等待上限必须大于整条链的最坏耗时

`e_report_after_final.sh`（等补表与 B5 都结束后自动重算全部判据）第一版的等待上限是
$480\times30\,\mathrm{s}=4.0$ 小时，而整条链（⑤ 8B 段 + 32B 段 + ④ B5）约 4.5 小时
⇒ 它会**提前放弃并产出一份 ⑤/④ 尚未完成的"最终"报告**。
**这类错误比崩溃更危险：报告看起来是完整的。**
已修：上限改为 $2880\times30\,\mathrm{s}=24$ 小时，每 10 分钟打一次进度，
真超时则**显式打印警告**。
⇒ 凡是"等前置完成再干活"的脚本，上限请设成**最坏耗时 × 3 以上**，并留进度日志。

### 9.6 当前(self-healing)运行状态

`_supervise.sh` 每 120 s 检查这 5 个 job：DONE 标记未出现而进程也没了 ⇒ 用 `setsid` 重启
（每个最多 5 次，并记录重启次数）。因为每个脚本内部都有"已完成则跳过"逻辑，重启是安全的。
⇒ **即使没人盯着，这条链也会自己跑完并自动产出判据报告。**

---

## 10. 末批单卡任务已全部收尾（2026-09-26 16:00 UTC）—— **机器已空闲，可交回**

三个任务全部落地、产出具在、判据已跑：

| 任务 | 结束标记 / 时间 | 产物 | 结论 |
|---|---|---|---|
| **③ B2 跨域读出头** | `B2_XDOM_HEAD_WATCH_DONE` | `results/b2feat_xdom/`（16 个 npz）+ `results/report/b2_xdom.json` + `b2_xdom_verdict_16pools.txt` | **15/16 池区间不含 0**；9 个 2064 项池**全胜**、7 个航拍池**全负**；零容量对照 **0/16** |
| **⑤ 面板补表** | `E_FINAL_QUEUE_DONE` 15:14:07 | arms_full **120→135**、b3_32b **20→25** | `arm_matrix.py` = **`ARM_MATRIX_OK`**、行数全一致 |
| **④ B5 航拍 adapter** | `B5_PIPELINE_DONE` 15:46:31 | `runs/b5_{real,shuf}/adapter` + 4 条臂（各 400 行）+ `results/report/b5_adapter.json` | **C4 在航拍域再次被否**：微调后口径B $0.526\to0.833$（**比不微调还差**）；但真标签明显好于打乱标签（$2/2$）⇒ 学到了东西却没用 |
| 全套判据 | `REPORT_AFTER_FINAL_DONE` 15:52:45 | `results/report/summary_20260926_1555.md`（**10 节**）+ `wdef_table.txt`（**自写 + 输入指纹**） | 三口径 w 表定型：**w1 = 33/41、w2 = 0/41、w3 = 0/41** |

**当前机器状态：`nvidia-smi` = 0 MiB，无任何我方进程，GPU 完全空闲。**

### 10.1 交接时请留意三件事

1. **`b64_wdef.py` 现在自己写 `results/report/wdef_table.txt`**（tee + 输入指纹：臂数/md5/时间）。
   不要再手工重定向 —— 那正是 26 桶旧快照事故的成因。
2. **跑臂前的两个预检别跳过**：`arm_matrix.py`（面板完整性）、`maps/*_index.csv` 与 cache 的行数一致性。
   `bad` 列是 QC 代码不是布尔，**不能因为 `bad != 0` 就跳过**（论文自己在用的 `dmcount` 索引有 61.8% 行 `bad=2`）。
3. **看门狗的等待上限必须 > 最坏耗时**：这一条当晚踩了两次
   （`e_report_after_final.sh` 与 `b5_pipeline.sh` 都是 4.0 h 上限，而链子要 4.5 h），
   第二次直接把 ④ 训成了 OOM 空跑。两处都已改成 24 h，并给训练加了"空闲显存 ≥ 40 GB"守卫。

**可回收（我方）**：`/root/step3_local` 权重已删（只留源码）；`/root/fsc147_orig.zip` 1.5 G、
`/root/cvpr_big.tgz` 162 M 可删；`/root/cvpr_exp/models/Qwen3-VL-8B-Instruct` 17 G
与共享库 `/model/ModelScope/Qwen/Qwen3-VL-8B-Instruct` **逐字节同源**，可删并改路径。
`/root/cvpr_exp/`、`/root/w1_results/`、`/root/aerial_train_vis/` 请保留（论文数字的来源）。

### 9.4 仍需保留的目录（会议侧还要用）

`/root/cvpr_exp/`（含 `cache/`、`maps/`、`results/`、脚本）、`/root/w1_results/`、
`/root/aerial_train_vis/`（B5 训练图 2000 张，409 MB）、`/root/aerial`、`/root/dense`、
`/root/fsc147`、`/root/z0`。可回收项见 §6 的回收表。
## §11 单卡面板补全（2026-09-27 02:19 UTC 起）

### 11.1 背景与范围
P3 的 vLLM 于 02:18 UTC 退出后 A800 空出（`0 MiB / 81920 MiB`），立即用
`e_panel_fill.sh`（md5 `81a474dc17668f1f58c9e2a8c7ea1685`）补全三块面板：

| 块 | 内容 | 臂数 | 状态 |
|---|---|---|---|
| §2.1 | `dense_field` × 6 池 × 3 契约 | 18 | ✅ 04:30:58 全收 |
| §2.2 | `symbol_image` × 4 池 × 3 契约 | 12 | ✅ 04:30:58 全收 |
| §2.3 | 32B `symbol_text` × 4 池 × {enumerated, permit} | **8**（清单原写 7 是笔误） | 🔄 串行中 |

纪律：8B 段 3 进程并发、32B 段串行；`claim` 目录防重复 + `--resume` + 失败释放 claim 重试；
启动前显存守卫（空闲 < 40 GB 则**一条臂都不开**）。
实测：8B 段墙钟 **2 h 11 min**（单卡占满 ⇒ **2.18 GPU·h**，与逐臂系数估 2.21 一致）；
单条 32B 臂 **18.9 min**。`arms_full` 136 → 166 个 csv。

### 11.2 新工具：`_panelfill_qc.py`（今后补臂都该先跑它）
`arm_matrix.py` 只看"文件在不在、行数够不够"，看不见更隐蔽的失效。本工具对期望臂逐条查：
行数、**item 集合与 cache 完全相等**、**attach 取值与老臂同接口基准一致**
（`dense_field/symbol_image → image,image,text`；`symbol_text → image,text`）、
`pool` 列与 cache 一致、`format_violation` 占比、**跨契约给数率**（base 必须 ≥ enumerated）、
**跨专家 raw 一致率**（同接口同契约不同池不能几乎相同——防"拿错专家"，此坑有过先例）。

三种模式：
```bash
python _panelfill_qc.py              # 全量；未跑完即 INCOMPLETE（退出码 2）
python _panelfill_qc.py --partial    # 只看已完成部分（退出码 3 = PARTIAL_OK）
python _panelfill_qc.py --list       # 打印期望臂名，可与队列日志对账
python _panelfill_qc.py --reconcile  # ★ 权威计数：期望 / 开跑 / 完成 三者齐平才放行
```
**注意**：监控时不要用 `grep -c 结束` 数臂（会把"8B 第 N 轮结束""32B 第 1 轮"也数进去，多 1 条）。

### 11.3 三口径 w 表定稿：51 桶
`b64_wdef.py` **只读 `arms_full` 的 8B 臂** ⇒ 8B 段收工它即定稿，与 32B 无关：

```
04:36:44  C2 桶数 51   w1 42/51   w2 0/51   w3 0/51   反向 47.0–94.5 pp
指纹 833bd65bb4bedd0679869cf1b029ed9e（158 条 8B 臂；脚本自写文件 + 输入指纹）
```
新增 10 个 (池 × 接口) 桶里 **9 个显著降、1 个平**（`visdrone_aerial_aitod·dense_field`，航拍池）。
`w2/w3` 始终 0 ⇒ "没有 definition-free 版本"的定性结论不变。论文 6 文件 21 处已同步，
编译 13 页、`texcheck` + `LAYOUT_AUDIT` PASS、`pdftotext` 逐处复核。

### 11.4 ⚠️ 两个必须记住的坑
1. **`b64_wdef.py` 建桶只看"文件在不在"**，不看跑完没有。中途跑会把只写了 600 行的臂当成一个桶
   ⇒ 中途数字无意义，**必须等 `--reconcile` 齐平再算**。
2. **同一失效模式的第二例**：`e_table.py` 的产物 `table_7b_vs_32b.json` 长期停在 16 格，
   而 ⑤c 之后面板真值是 **25 格**（且有一格 32B 显著更差）。凡"脚本会算"的产物，
   改面板后都要**重跑并核对**，不能假定它自己会更新。

### 11.5 论文数字的三个来源与机械更新工具
论文里读臂的产物有三个，补臂后都要重刷（`bash e_report_all.sh` 一次全做）：

| 产物 | 现状 → 补臂后 | 论文里的引用 | 更新工具 |
|---|---|---|---|
| `wdef_table.txt` | 41 → **51 桶** | §0/§1/§3/§6/§7 + 附录 | `exp/_wdef_apply.py`（含自检 `_wdef_apply_selftest.py`） |
| `table_7b_vs_32b.json` | 16（真值 25）→ ~33 格 | 摘要 + §6b | `exp/_etable_apply.py`（有反向格时自动点名） |
| `aerial_matrix.json` | 42 → 48 行 | `tab:channel` 与 37%/2.6% 那句 | `exp/_aerial_claim_check.py`（判定那句话能否推广到两个适配专家） |

三个工具都是"**扫引用点 + 逐条校验命中 1 次 + 未命中就拒绝写入**"，不是无脑替换；
dry-run 会按顺序模拟前一条的改动（否则会出现"dry-run 说跳过、apply 却成功"的假象）。

### 11.6 收尾顺序（照这个顺序做）
```bash
python _panelfill_qc.py --reconcile        # ① 闸门：期望=开跑=完成 38
cd /root/cvpr_exp && bash e_report_all.sh  # ② 一次全刷所有读臂判据（零 GPU）
# ③ 本地：两个 planner dry-run → apply → texcheck → 重编译 → pdftotext 逐处复核
# ④ 本地：_aerial_claim_check.py 判定 §6b 那句是否需加限定
```

### 11.7 实际收尾结果（2026-09-27 06:29:38 UTC 全部完成）
```
E_PANEL_FILL_DONE 06:29:38 UTC     reconcile: 期望 38 | 开跑 38 | 完成 38（异常 0）
本批卡时 = 8B 2.18 + 32B 1.98 = 4.16 GPU·h（计划 4.2）
```
* **w 表**：51 桶 / w1 42/51 / w2·w3 0/51 / 反向 47.0–94.5 pp ⇒ 论文 21 处已改。
* **配对表**：33 格（29 更好 / 1 平 / **3 更差**；三格都是航拍 `visdrone_aerial_vis·symbol_text`
  的三个契约，其中 2 个显著）⇒ 论文摘要与 §6b 已改，并逐一点名。
* **航拍矩阵**：48 行；判定 **NARROW** —— `P2PNet←AI-TOD` 的场通道在 aitod 池上动了 **+14.4%**
  （←VisDrone 只 1.5–2.6%）⇒ `tab:channel` 标题与正文那句已收窄为"符号通道移动**远大于**场通道"，
  并同时把弃答率范围 $99.1$–$99.6\%$ 修正为 **$99.0$–$99.6\%$**（6b 与 suppl 各一处）。
* **面板完整性**：`ARM_MATRIX_OK`，`!!` 缺口 0。
* **编译**：13 页，STATIC_CHECK PASS + LAYOUT_AUDIT PASS；`pdftotext` 逐处命中。
* **刷新方式**：只跑读臂的快集（`e_table / e_aerial_matrix / e_copycheck / e_relay_all /
  e_p2p_vs_dmc / arm_matrix`，3.5 min）；**故意不跑 `e_report_all.sh` 里的 `b2_head_xdom.py`**
  （读 ③ 的 npz，与本次无关，且要 ~15 min，会撞上单次执行 10 min 上限）。
  长任务一律 `setsid nohup ... < /dev/null &` 脱离 SSH 会话。
* **该记的教训**：本日三起"产物停在旧快照 / 结论悄悄变宽"（w 表 26→51 桶、配对表 16→33 格、
  "场通道没动"只在部分专家成立）。**补臂前先跑一次脚本自检**，是发现第 2 起的唯一原因。


---

## §12 PaperB / P3 分支：2026-09-27 07:26–07:52 UTC 用卡记录（**已交还**）

- **用途**：G8（UCF-QNRF 英文臂补完）、G9（倒数第二层 L2 范数，**因闸门未过而报"不可测"**）、
  G3（第三方协议外验：JHU-Crowd++ test + TallyQA-short × 4 家族 × 2 域 × 300 项 × 3 臂）。
- **规模**：G8 1,002 次 + G3 7,200 次 + G9 只有闸门（判据件 md5 `cd4d138bfe50a51c172d8648933bf955`）。
- **产物**：`/root/g8_res/`、`/root/g3_res/`（四个家族各 1,800 行）、`/root/g9_res/g9_guard.json`；
  新增语料 `/root/g3_corpora/`（JHU 400 张 + TallyQA parquet，共约 430 MB，**可用性未过期前留着**）。
- **起服两坑（供你复用）**：
  ① `setsid nohup` 起的 vLLM 进程 **PATH 里没有 conda 的 bin** ⇒ `FileNotFoundError: 'ninja'`；
  ② 本镜像**只有 gcc 没有 g++**（无 `cc1plus`），FlashInfer 的采样算子缓存只剩 `build.ninja`
     ⇒ 每次起服都重编、每次必失败 ⇒ 我们改用 `export VLLM_USE_FLASHINFER_SAMPLER=0`（temperature 0，
     取值不变）。两条都写进了三个编排脚本的头部。
- **另外一条**：`--mm-processor-kwargs '{"max_pixels":...}'` **InternVL 的 image processor 不接受**
  （`TypeError: unexpected keyword argument 'max_pixels'`）⇒ 按家族分派：Qwen 系带上限，InternVL 不带。
- **交还状态**：`nvidia-smi` = **0 MiB / 0%**，无 vllm 进程、无孤儿 `VLLM::EngineCore`，
  未动 §3 那批路径（`/root/cvpr_exp`、`/root/w1_results`、`/root/aerial_train_vis`、
  `/root/RUNNING.md` 上方内容、`/root/dense`、`/root/aerial`、`/root/fsc147`、`/root/z0`）。


---

## §13 PaperB / P3 分支：2026-09-27 08:13–09:30 UTC 收官批（**已交还**）

- **用途**：G7（服务栈因子：5 次起服 × 7 配置 = 4,200 次）、G8b（另三格的英文/中文 base，1,616 次）、
  placebo 锚（4 臂 × 150 项 = 600 次）、G10 同批效应（2 构建 × 564 = 1,128 次）、
  G9b（倒数第二层 L2，135 项 × 3 臂 = 405 次，**先过污染闸门**）。
- **结果一句话**：G7 三个可测因子里最大的一个（固定 system 消息）只把答零率动了 **−14.0 pp**（<30 pp 判据）；
  G8b 把英文四格补成**同一构建**后，$S$ **2/4 落 $[0,1]$**（判据不成立）；placebo 锚 **4/4 中位答数恰等于被命名值**
  （ρ=1.000）；G10 同批效应 **|Δ| ≤ 1.0 pp**；G9b 判为**主动拒答**（范数比 0.976/0.991、余弦 0.992/0.995）。
- **产物**：`/root/g7_res/`（7 个 CSV）、`/root/gx_res/`（4 个）、`/root/g9_res/g9_hidden.csv` + `g9_guard.json`。
- ★ **新增一条坑（比上一条更阴）**：`pkill -9 -i -f vllm` 杀得掉 API 服务进程，
  **但孤儿 `VLLM::EngineCore` 仍攥着 ~75 GB**；而编排脚本的第二道闸"显存已占 ≥1000 MiB 就拒绝执行"
  会让脚本**静默退出、连日志都不建**（我这边表现为"脚本跑了但什么都没发生"）。
  可靠做法是**按 PID 杀**：先 `nvidia-smi --query-compute-apps=pid` 取 PID，
  再 `ps -eo pid,comm | awk '/VLLM::EngineCor|resource_tracker/{print $1}'` 补一刀，最后核 `compute-apps` 为 0。
  已把这条写进 `_a800_killgpu.py` 与各编排脚本的 `gpu_clear()`。
- **交还状态**：`nvidia-smi` = **0 MiB / 0%**，`--query-compute-apps` 为空，无孤儿 `VLLM::EngineCore`，
  未动 §3 那批路径与 `/root/RUNNING.md` 上方内容。
