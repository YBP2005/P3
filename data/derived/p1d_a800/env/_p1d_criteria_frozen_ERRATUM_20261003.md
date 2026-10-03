# `_p1d_criteria_frozen.json` 勘误（2026-10-03）

**结论：冻结件本身的 md5 与判据阈值一律不变；本节只说明它的一处文字与实际执行不符。**

* 该文件的 `title` / `estimator.span` / `criteria[].C2-levels` / `criteria[].C3-spans` 里写的是
  **"eight levels"**（八档），那是**并集方案确定之前**的措辞。
* **实际执行的是 11 档**：`design.levels` 有 11 项
  （`0, 104856, 145698, 200000, 202447, 281300, 390867, 400000, 543118, 754655, 800000`），
  `calls_check` 也写 **16,500 = 2 × 11 × 250 × 3**；同一文件的 `appendices.A1_union_of_level_labels`
  已解释为什么并成 11 档（= 该节 8 个 matched-travel 乘子 ∪ 放行对照梯子的 4 个公共标签，native 标签吸收重复项）。
* 因此**只有描述性文字是旧的**，**判据（C1–C5 的阈值、bootstrap 口径、NOT COVERED 规则）未受影响**，
  放行脚本 `p1d_analyze.py` 的档位数判定为 `len(lv) < 8`，11 档自然满足。
* 运行日志/判据件 md5 锚：正文 md5 `6ad6f1510c82e8d12c423b7f3a42a963`（**未改动**）。
