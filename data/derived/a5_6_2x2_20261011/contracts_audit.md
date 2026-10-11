# A5-6 「点名 0 × 弃答出口」2×2 契约审计（逐字可回溯）

本件由 `make_contracts_2x2.py` 生成，**不含任何人工自由创作**：四条件 = 同一固定骨架 + 2 句可变句的组合。

## 0. 固定模板来源（逐字节）

| 模板 | 路径 | 存在 | 字节 | md5 | strip 后长度 |
|---|---|---|---|---|---|
| base.txt | `/root/incoming/x01_corpus/contracts/base.txt` | yes | 179 | `a7f75469c636c3b3e3a3d23e4841f171` | 72 |
| permit.txt | `/root/incoming/x01_corpus/contracts/permit.txt` | yes | 242 | `09da563b2ad0e15c16179ad2de801325` | 113 |
| channel.txt | `/root/incoming/x01_corpus/contracts/channel.txt` | yes | 250 | `657917c9212d0abf01b1fb63777f4eae` | 119 |

* 本件实际使用的**件级骨架模板**：`/root/incoming/x01_corpus/contracts/base.txt`（md5=`1aa6d8fa597f67ffb9504ec8b6c1075b`）。
* 骨架改写只有两步，且每步都断言"恰好命中 1 次"，不成立即拒绝生成：
  1. 逐图目标槽：**literal 目标物体**；
  2. 输出格式句：**identity（模板格式句已是基线格式句）**。
* 若云端 `/root/incoming/x01_corpus/contracts` 与上述 md5 不同，**以云端字节为准**（本表即为对账凭据）。

## 1. 两个因子的可变句（★ 只有这两句可变）

| 因子 | 取值 | 逐字文本 |
|---|---|---|
| A 是否点名 0 | `no_name0` | `""`（空串：完全不提 0） |
| A 是否点名 0 | `name0` | `若图中没有该目标，答案就是 0。` |
| B 是否给弃答出口 | `no_exit` | `以JSON格式输出：{"count": 数量}，只输出JSON。` |
| B 是否给弃答出口 | `exit` | `若无法逐个确证，请回答 abstain 或 cannot_judge，不要猜测。以JSON格式输出：{"count": 数量} 或 {"count": "abstain"}，只输出JSON。` |

* `no_exit` 的输出格式句**逐字取自** x01 冻结臂 `base.txt`。
* `exit` 的弃答措辞**逐字复用** x01 冻结臂 `permit.txt` 的 abstain 子句措辞（`如果你无法逐个确证，请回答 abstain，而不要猜测。`），
  按本实验设计把出口 token 扩为 `abstain` / `cannot_judge`（评审原文：允许输出 abstain/cannot_judge）。
* ★ 声明：出口句**本身含输出格式**（因为"允许弃答"必须同时改变 JSON 形态），因此 exit 条件下的输出格式句**属于可变句 V_B**，不是被偷偷改动的固定句。

## 2. 固定句等价性证明（四条件逐字相同）

把每条件的 V_A（点名 0 句）与 V_B（出口句）**同时抹去**后，剩余文本必须逐字相同。实测：**PASS ✅**

| 条件 | 抹去 V_A/V_B 后的"固定部分"md5 | 长度 |
|---|---|---|
| `no_name0_no_exit` | `ffbbec0d020f4ad5d9e66567b43fbeb7` | 40 |
| `no_name0_exit` | `ffbbec0d020f4ad5d9e66567b43fbeb7` | 40 |
| `name0_no_exit` | `ffbbec0d020f4ad5d9e66567b43fbeb7` | 40 |
| `name0_exit` | `ffbbec0d020f4ad5d9e66567b43fbeb7` | 40 |

共同固定部分（逐字，`<target_word>` 为逐图目标词槽）：
```
请数出图片中的<target_word>的数量（画面中每一个属于该类的个体），不要遗漏，不要重复，
```

## 3. 逐条：条件名 / 完整文本 / 与基线的逐字 diff

### 3.1 `no_name0_no_exit`（★ 基线）

* 因子：A=`no_name0`，B=`no_exit`
* 可变段：V_A=``，V_B=`以JSON格式输出：{"count": 数量}，只输出JSON。`
* 与基线逐字 diff：（基线自身，无 diff）
* 完整文本（件级，目标槽写作 `目标物体`，与既有 A5-1/A5-3/A5-5 的逐图替换约定一致）：
```
请数出图片中的目标物体的数量（画面中每一个属于该类的个体），不要遗漏，不要重复，以JSON格式输出：{"count": 数量}，只输出JSON。
```
* 逐图形态示例（`<X>` = 该图 target_word）：
```
请数出图片中的<X>的数量（画面中每一个属于该类的个体），不要遗漏，不要重复，以JSON格式输出：{"count": 数量}，只输出JSON。
```
* 字节：178 ｜ md5=`a7f75469c636c3b3e3a3d23e4841f171`

### 3.2 `no_name0_exit`

* 因子：A=`no_name0`，B=`exit`
* 可变段：V_A=``，V_B=`若无法逐个确证，请回答 abstain 或 cannot_judge，不要猜测。以JSON格式输出：{"count": 数量} 或 {"count": "abstain"}，只输出JSON。`
* 与基线逐字 diff：
```diff
--- contract_no_name0_no_exit.txt
+++ contract_no_name0_exit.txt
@@ -1 +1 @@
-请数出图片中的目标物体的数量（画面中每一个属于该类的个体），不要遗漏，不要重复，以JSON格式输出：{"count": 数量}，只输出JSON。
+请数出图片中的目标物体的数量（画面中每一个属于该类的个体），不要遗漏，不要重复，若无法逐个确证，请回答 abstain 或 cannot_judge，不要猜测。以JSON格式输出：{"count": 数量} 或 {"count": "abstain"}，只输出JSON。
```
* 完整文本（件级，目标槽写作 `目标物体`，与既有 A5-1/A5-3/A5-5 的逐图替换约定一致）：
```
请数出图片中的目标物体的数量（画面中每一个属于该类的个体），不要遗漏，不要重复，若无法逐个确证，请回答 abstain 或 cannot_judge，不要猜测。以JSON格式输出：{"count": 数量} 或 {"count": "abstain"}，只输出JSON。
```
* 逐图形态示例（`<X>` = 该图 target_word）：
```
请数出图片中的<X>的数量（画面中每一个属于该类的个体），不要遗漏，不要重复，若无法逐个确证，请回答 abstain 或 cannot_judge，不要猜测。以JSON格式输出：{"count": 数量} 或 {"count": "abstain"}，只输出JSON。
```
* 字节：279 ｜ md5=`3afc29d16a331d75419653252d5ed830`

### 3.3 `name0_no_exit`

* 因子：A=`name0`，B=`no_exit`
* 可变段：V_A=`若图中没有该目标，答案就是 0。`，V_B=`以JSON格式输出：{"count": 数量}，只输出JSON。`
* 与基线逐字 diff：
```diff
--- contract_no_name0_no_exit.txt
+++ contract_name0_no_exit.txt
@@ -1 +1 @@
-请数出图片中的目标物体的数量（画面中每一个属于该类的个体），不要遗漏，不要重复，以JSON格式输出：{"count": 数量}，只输出JSON。
+请数出图片中的目标物体的数量（画面中每一个属于该类的个体），不要遗漏，不要重复，若图中没有该目标，答案就是 0。以JSON格式输出：{"count": 数量}，只输出JSON。
```
* 完整文本（件级，目标槽写作 `目标物体`，与既有 A5-1/A5-3/A5-5 的逐图替换约定一致）：
```
请数出图片中的目标物体的数量（画面中每一个属于该类的个体），不要遗漏，不要重复，若图中没有该目标，答案就是 0。以JSON格式输出：{"count": 数量}，只输出JSON。
```
* 逐图形态示例（`<X>` = 该图 target_word）：
```
请数出图片中的<X>的数量（画面中每一个属于该类的个体），不要遗漏，不要重复，若图中没有该目标，答案就是 0。以JSON格式输出：{"count": 数量}，只输出JSON。
```
* 字节：222 ｜ md5=`623dbea85a1e8cbb26f58ff1271c00dc`

### 3.4 `name0_exit`

* 因子：A=`name0`，B=`exit`
* 可变段：V_A=`若图中没有该目标，答案就是 0。`，V_B=`若无法逐个确证，请回答 abstain 或 cannot_judge，不要猜测。以JSON格式输出：{"count": 数量} 或 {"count": "abstain"}，只输出JSON。`
* 与基线逐字 diff：
```diff
--- contract_no_name0_no_exit.txt
+++ contract_name0_exit.txt
@@ -1 +1 @@
-请数出图片中的目标物体的数量（画面中每一个属于该类的个体），不要遗漏，不要重复，以JSON格式输出：{"count": 数量}，只输出JSON。
+请数出图片中的目标物体的数量（画面中每一个属于该类的个体），不要遗漏，不要重复，若图中没有该目标，答案就是 0。若无法逐个确证，请回答 abstain 或 cannot_judge，不要猜测。以JSON格式输出：{"count": 数量} 或 {"count": "abstain"}，只输出JSON。
```
* 完整文本（件级，目标槽写作 `目标物体`，与既有 A5-1/A5-3/A5-5 的逐图替换约定一致）：
```
请数出图片中的目标物体的数量（画面中每一个属于该类的个体），不要遗漏，不要重复，若图中没有该目标，答案就是 0。若无法逐个确证，请回答 abstain 或 cannot_judge，不要猜测。以JSON格式输出：{"count": 数量} 或 {"count": "abstain"}，只输出JSON。
```
* 逐图形态示例（`<X>` = 该图 target_word）：
```
请数出图片中的<X>的数量（画面中每一个属于该类的个体），不要遗漏，不要重复，若图中没有该目标，答案就是 0。若无法逐个确证，请回答 abstain 或 cannot_judge，不要猜测。以JSON格式输出：{"count": 数量} 或 {"count": "abstain"}，只输出JSON。
```
* 字节：323 ｜ md5=`524bb5645301855a237d3ce70b669b66`

## 4. 判据（供上级验收）

* [x] 四条件文件的**固定部分 md5 全等**（上表 4 行同值）。
* [x] 四条件**只有那两句**不同（每条件 diff 至多 1 行增删，且增删内容 = V_A/V_B）。
* [x] `no_exit` 两条件内**不含** `abstain` / `cannot_judge`（硬闸，见 `_build_receipt.json` 的 `gates.no_exit_has_no_abstain`）。
* [x] `no_name0` 两条件内**不含** `若图中没有该目标，答案就是 0` 这句（见 `gates.no_name0_has_no_zero`）。
* [x] 四条件均含 `只输出JSON`（输出纪律一致）。

## 5. target_map 的列名与用法（★ 两套列名同义）

| 文件 | 列 |
|---|---|
| `target_map.csv` | `image,class_name,gt_count,true_zero` + `cond_b_<cond>`（4 列，兼容既有 `runner_a51.py` 的 `cond_b_<A51_ARMS>` 取值）+ `cond_<cond>_base`（4 列，长名） |
| `target_map_no_name0_no_exit.csv` | `image,class_name,gt_count,true_zero,cond_b_no_name0_no_exit`（★ runner 读这列）+ `cond_no_name0_no_exit_base`（长名，逐字同值） |
| `target_map_no_name0_exit.csv` | `image,class_name,gt_count,true_zero,cond_b_no_name0_exit`（★ runner 读这列）+ `cond_no_name0_exit_base`（长名，逐字同值） |
| `target_map_name0_no_exit.csv` | `image,class_name,gt_count,true_zero,cond_b_name0_no_exit`（★ runner 读这列）+ `cond_name0_no_exit_base`（长名，逐字同值） |
| `target_map_name0_exit.csv` | `image,class_name,gt_count,true_zero,cond_b_name0_exit`（★ runner 读这列）+ `cond_name0_exit_base`（长名，逐字同值） |

* ★ 本目录 CSV **不含注释行**（既有 runner 按标准 CSV 读，注释行会变成坏行）；用法写在 `target_map_README.txt`。
* ★ 本件**不伪造** `cond_b_base/permit/channel` 三臂列：三臂 ≠ 2×2 四条件，照抄会把 A5-5 的三臂文本误当本实验条件。四条件请用上表的 8 列之一。
