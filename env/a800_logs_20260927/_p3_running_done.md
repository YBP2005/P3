
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

**A800 现在可以交回会议侧。**
