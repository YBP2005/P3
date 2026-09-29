# PaperB · E1 判别实验证据（2026-09-20）

> 本文件是**内部记录**（不进送审件）。正文与补充材料引用的一切 E1 数字以此为准。
> 数据来源：5090 上 `/root/e1_results/*.csv`（48 格）与语料 `/root/dense_results/*.csv`（9 文件）。

## 0. 服务配置与可比性

- 语料侧（本地机 5090）：vLLM 0.29.0 + `Qwen3-VL-32B-Instruct-AWQ-4bit`，`quantization=compressed-tensors`，`dtype=torch.bfloat16`，`max_seq_len=8192`，tensor_parallel=1。
- E1 侧：阿里云百炼 compatible-mode，`temperature 0.0`，`max_tokens 128`，JPEG q92 编码与语料运行器逐字一致。
- **提示词可比性已按码点核验**：E1 的 base 提示词与语料 `06_dense_vlm.py` 的 base 提示词**逐字符相同**。
- 未控混淆：权重精度（4-bit vs bf16）与推理引擎（vLLM vs 百炼）**同时**不同，故「本地为零、托管不为零」不能单独归因于量化。

## 1. 样本帧

- `st_a`：base 臂 `pred==0` 的 item 共 103 个（gt 138–797），等间隔取 40 个。
- `ucf`：base 臂 `pred==0` 的 item 共 180 个（gt 137–2075），等间隔取 40 个。
- 抽样**确定性**（`zero.sort(key=gt)` 后 `step=len//n`），故**五个模型、全部臂共享同一 40 个 item**；已逐文件核验帧内 40/40、无重复键、无帧外行。
- `base`/`permit` 臂：`--reps 5`，每 item 6 次观测（早期单次 40 行 + 重复 200 行，键分别为裸 item 与 `item#rN`，二者并存**非重复数据**）。其余臂 40 行。

## 2. 语料内已有的证据：零率随「提示词许可结构」单调变化

| 臂 | 提示词含义 | 零数/总数 | 零率 | st_a | st_b | ucf |
|---|---|---|---|---|---|---|
| over | 要求把所有可能目标都计入 | 0/832 | **0.0%** | 0/182 | 0/316 | 0/334 |
| base | 中性 | 283/832 | **34.0%** | 103/182 | 0/316 | 180/334 |
| under | 只统计能完全确认的目标 | 519/832 | **62.4%** | 171/182 | 43/316 | 305/334 |

⇒ 「鼓励保守」的提示词把 `pred=0` 从 **0%** 抬到 **62.4%**；「要求全计入」的提示词下 832 个 item **一个零也没有**。

## 3. 语料解析器审计（死分支及其影响量）

- `06_dense_vlm.py` 的正则为 `\{\s*(?:count|计数|数量|人数)\s*[:：]\s*(\d+)`：**键名前缺引号**，
  而提示词要求的输出是 `{"count": 数量}` ⇒ 结构分支**永不命中**，所有取值实际来自 fallback「取响应中第一个整数」。
- 逐行审计（2496 行）：fallback 与 JSON `count` **不一致的行 = 0**；无数字行 = 0；取不到 JSON count 的行 = 0。
- `pred==0` 的行共 802，其中 JSON `count` 本身就是 0 的 = **802/802**，raw 形如 `{"count": 0}`。

⇒ 该缺陷**真实存在但影响量为零**：语料的响应都是只含一个整数的 JSON，fallback 与结构解析同值。
⇒ 因此 **`pred=0` 不是解析产物**：它是模型**自己写下的 0**。

## 4. E1 48 格（跨模型、同帧）

| model | ds | arm | rows | valid | ERR | zero | med pred/gt | pooled dev |
|---|---|---|---|---|---|---|---|---|
| qwen3-vl-235b-a22b-instruct | st_a | base | 240 | 237 | 3 | 0 | 0.670 | -13.9% |
| qwen3-vl-235b-a22b-instruct | st_a | bestA | 40 | 39 | 1 | 0 | 7.519 | 719.8% |
| qwen3-vl-235b-a22b-instruct | st_a | bestB | 40 | 40 | 0 | 0 | 8.040 | 732.6% |
| qwen3-vl-235b-a22b-instruct | st_a | bestC | 40 | 39 | 1 | 0 | 9.452 | 1471.7% |
| qwen3-vl-235b-a22b-instruct | st_a | channel | 40 | 39 | 1 | 0 | — | — |
| qwen3-vl-235b-a22b-instruct | st_a | permit | 240 | 236 | 4 | 0 | — | — |
| qwen3-vl-32b-instruct | st_a | base | 240 | 240 | 0 | 76 | 0.635 | -34.3% |
| qwen3-vl-32b-instruct | st_a | bestA | 40 | 40 | 0 | 0 | 6.354 | 676.9% |
| qwen3-vl-32b-instruct | st_a | bestB | 40 | 40 | 0 | 0 | 6.017 | 521.8% |
| qwen3-vl-32b-instruct | st_a | bestC | 40 | 40 | 0 | 0 | 4.263 | 400.8% |
| qwen3-vl-32b-instruct | st_a | channel | 40 | 40 | 0 | 0 | — | — |
| qwen3-vl-32b-instruct | st_a | permit | 240 | 240 | 0 | 0 | — | — |
| qwen3-vl-8b-instruct | st_a | base | 40 | 40 | 0 | 0 | 0.276 | -75.7% |
| qwen3-vl-8b-instruct | st_a | bestA | 40 | 40 | 0 | 0 | 2.463 | 307.2% |
| qwen3-vl-8b-instruct | st_a | channel | 40 | 40 | 0 | 0 | — | — |
| qwen3-vl-8b-instruct | st_a | permit | 40 | 40 | 0 | 0 | — | — |
| qwen3-vl-flash | st_a | base | 40 | 40 | 0 | 0 | 0.990 | 37.6% |
| qwen3-vl-flash | st_a | bestA | 40 | 40 | 0 | 0 | 6.868 | 875.5% |
| qwen3-vl-flash | st_a | channel | 40 | 40 | 0 | 0 | — | — |
| qwen3-vl-flash | st_a | permit | 40 | 40 | 0 | 0 | — | — |
| qwen3-vl-plus | st_a | base | 40 | 40 | 0 | 0 | 0.627 | -36.8% |
| qwen3-vl-plus | st_a | bestA | 40 | 40 | 0 | 0 | 7.689 | 1123.6% |
| qwen3-vl-plus | st_a | channel | 40 | 40 | 0 | 0 | — | — |
| qwen3-vl-plus | st_a | permit | 40 | 40 | 0 | 0 | — | — |
| qwen3-vl-235b-a22b-instruct | ucf | base | 240 | 238 | 2 | 1 | 0.573 | -18.1% |
| qwen3-vl-235b-a22b-instruct | ucf | bestA | 40 | 39 | 1 | 0 | 4.315 | 906.9% |
| qwen3-vl-235b-a22b-instruct | ucf | bestB | 40 | 39 | 1 | 0 | 4.704 | 778.3% |
| qwen3-vl-235b-a22b-instruct | ucf | bestC | 40 | 39 | 1 | 0 | 6.903 | 1340.0% |
| qwen3-vl-235b-a22b-instruct | ucf | channel | 40 | 39 | 1 | 0 | — | — |
| qwen3-vl-235b-a22b-instruct | ucf | permit | 240 | 237 | 3 | 0 | — | — |
| qwen3-vl-32b-instruct | ucf | base | 240 | 240 | 0 | 62 | 0.691 | -38.0% |
| qwen3-vl-32b-instruct | ucf | bestA | 40 | 40 | 0 | 0 | 4.480 | 622.2% |
| qwen3-vl-32b-instruct | ucf | bestB | 40 | 40 | 0 | 0 | 4.002 | 438.9% |
| qwen3-vl-32b-instruct | ucf | bestC | 40 | 40 | 0 | 0 | 3.787 | 415.7% |
| qwen3-vl-32b-instruct | ucf | channel | 40 | 40 | 0 | 0 | — | — |
| qwen3-vl-32b-instruct | ucf | permit | 240 | 240 | 0 | 0 | — | — |
| qwen3-vl-8b-instruct | ucf | base | 40 | 40 | 0 | 2 | 0.002 | -94.5% |
| qwen3-vl-8b-instruct | ucf | bestA | 40 | 40 | 0 | 0 | 2.565 | 269.8% |
| qwen3-vl-8b-instruct | ucf | channel | 40 | 40 | 0 | 0 | — | — |
| qwen3-vl-8b-instruct | ucf | permit | 40 | 40 | 0 | 0 | — | — |
| qwen3-vl-flash | ucf | base | 40 | 40 | 0 | 0 | 0.654 | -1.3% |
| qwen3-vl-flash | ucf | bestA | 40 | 40 | 0 | 0 | 6.135 | 873.0% |
| qwen3-vl-flash | ucf | channel | 40 | 40 | 0 | 0 | — | — |
| qwen3-vl-flash | ucf | permit | 40 | 40 | 0 | 0 | — | — |
| qwen3-vl-plus | ucf | base | 40 | 40 | 0 | 0 | 0.501 | -41.2% |
| qwen3-vl-plus | ucf | bestA | 40 | 40 | 0 | 0 | 7.255 | 1145.6% |
| qwen3-vl-plus | ucf | channel | 40 | 40 | 0 | 0 | — | — |
| qwen3-vl-plus | ucf | permit | 40 | 40 | 0 | 0 | — | — |

### 4.1 base 臂零率（同一批 40 个 item）

| model | st_a | ucf |
|---|---|---|
| qwen3-vl-235b-a22b-instruct | 0/237 = 0.0% | 1/238 = 0.4% |
| qwen3-vl-32b-instruct | 76/240 = 31.7% | 62/240 = 25.8% |
| qwen3-vl-8b-instruct | 0/40 = 0.0% | 2/40 = 5.0% |
| qwen3-vl-flash | 0/40 = 0.0% | 0/40 = 0.0% |
| qwen3-vl-plus | 0/40 = 0.0% | 0/40 = 0.0% |

### 4.2 给出显式弃权通道后（permit / channel 臂）

- 有效调用合计 **1591**，其中显式弃权 **1591 = 100.0%**；这些臂里 `pred==0` 共 **0** 个。
- `permit` 给的是「无法逐个确证就回答 abstain」；`channel` 给的是三选一（数字 / `cannot_judge` / `no_people`）。两臂结果一致。

### 4.3 禁止弃权并要求给出最佳估计（bestA / bestB / bestC）

- 18 格：中位 `pred/gt` 范围 **2.463–9.452**；`pred==0` **0** 个；显式弃权 **0** 个。
- ⇒ 被禁止弃权时，模型不会退化成「接近 0」，而是系统性地**高估 2.5–9.5 倍**。

## 5. 由证据支持的结论（措辞可直接引用）

1. **`pred=0` 是模型自陈的弃权，被写进了唯一的数字槽位**：语料 802 个零值的 raw 全是 `{"count": 0}`（第 3 节），且零率随提示词许可结构从 0% 变化到 62.4%（第 2 节）。
2. **不是量化伪影**：托管 bf16 的 `qwen3-vl-32b-instruct` 在同一批 item 上仍写出 25.8%%–31.7%% 的零。
3. **也不是普遍行为**：同族 `plus` / `flash` / `235b` 在 base 臂几乎不写零（0%%–0.4%%）；
   但**一旦提供显式弃权通道，五个模型全部改用它**（1591/1591 = 100.0%），且不再写零。
4. ⇒ **弃权通道由服务配置与提示词共同决定**；`0` 只在「只允许输出数字」时才被用作弃权表达。
5. **不是失败的估计**：禁止弃权并索要最佳估计时，中位答案是真值的 2.5–9.5 倍，而不是接近 0。

## 6. 溯源

- 探针：`/root/19b_e1_probe.py` md5 7ce966d3a357
- 语料运行器：`/root/06_dense_vlm.py` md5 cc94af35ada9
- 队列脚本：`run_e1b.sh` / `run_e1c.sh`；两队列均打印 `E1B_ALL_DONE` / `E1C_ALL_DONE`。
- 本地数据：`analysis/e1_5090/e1_*.csv`（48 个）、`analysis/e1_5090/corpus/*.csv`（9 个）。
