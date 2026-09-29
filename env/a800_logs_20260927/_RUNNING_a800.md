# A800 交接说明（2026-09-26 04:10 UTC）—— 交 P3 使用

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
