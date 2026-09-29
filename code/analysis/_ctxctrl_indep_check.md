# S1（服务栈对照）独立重算 —— 绕开分析器，直读原始逐项 CSV

| 判定 | 检查 | 详情 |
|---|---|---|
| OK | 冻结件逐格一致 Phi-3.5-vision-instruct 4096 base s1 | 重算 0.0 vs 冻结 0.0（n=300） |
| OK | 冻结件逐格一致 Phi-3.5-vision-instruct 4096 permit s1 | 重算 95.3 vs 冻结 95.3（n=300） |
| OK | 冻结件逐格一致 Phi-3.5-vision-instruct 4096 channel s1 | 重算 0.0 vs 冻结 0.0（n=300） |
| OK | 冻结件逐格一致 Phi-3.5-vision-instruct 4096 enumAbstain s1 | 重算 48.7 vs 冻结 48.7（n=300） |
| OK | 冻结件逐格一致 Phi-3.5-vision-instruct 4096 base s2 | 重算 0.0 vs 冻结 0.0（n=300） |
| OK | 冻结件逐格一致 Phi-3.5-vision-instruct 4096 permit s2 | 重算 95.0 vs 冻结 95.0（n=300） |
| OK | 冻结件逐格一致 Phi-3.5-vision-instruct 4096 channel s2 | 重算 0.0 vs 冻结 0.0（n=300） |
| OK | 冻结件逐格一致 Phi-3.5-vision-instruct 4096 enumAbstain s2 | 重算 48.7 vs 冻结 48.7（n=300） |
| OK | 冻结件逐格一致 Phi-3.5-vision-instruct 4096 base s3 | 重算 0.0 vs 冻结 0.0（n=300） |
| OK | 冻结件逐格一致 Phi-3.5-vision-instruct 4096 permit s3 | 重算 95.0 vs 冻结 95.0（n=300） |
| OK | 冻结件逐格一致 Phi-3.5-vision-instruct 4096 channel s3 | 重算 0.0 vs 冻结 0.0（n=300） |
| OK | 冻结件逐格一致 Phi-3.5-vision-instruct 4096 enumAbstain s3 | 重算 49.0 vs 冻结 49.0（n=300） |
| OK | 冻结件逐格一致 Phi-3.5-vision-instruct 8192 base s1 | 重算 0.0 vs 冻结 0.0（n=300） |
| OK | 冻结件逐格一致 Phi-3.5-vision-instruct 8192 permit s1 | 重算 99.7 vs 冻结 99.7（n=300） |
| OK | 冻结件逐格一致 Phi-3.5-vision-instruct 8192 channel s1 | 重算 0.0 vs 冻结 0.0（n=300） |
| OK | 冻结件逐格一致 Phi-3.5-vision-instruct 8192 enumAbstain s1 | 重算 12.7 vs 冻结 12.7（n=300） |
| OK | 冻结件逐格一致 Phi-3.5-vision-instruct 8192 base s2 | 重算 0.0 vs 冻结 0.0（n=300） |
| OK | 冻结件逐格一致 Phi-3.5-vision-instruct 8192 permit s2 | 重算 99.7 vs 冻结 99.7（n=300） |
| OK | 冻结件逐格一致 Phi-3.5-vision-instruct 8192 channel s2 | 重算 0.0 vs 冻结 0.0（n=300） |
| OK | 冻结件逐格一致 Phi-3.5-vision-instruct 8192 enumAbstain s2 | 重算 12.3 vs 冻结 12.3（n=300） |
| OK | 冻结件逐格一致 Phi-3.5-vision-instruct 8192 base s3 | 重算 0.0 vs 冻结 0.0（n=300） |
| OK | 冻结件逐格一致 Phi-3.5-vision-instruct 8192 permit s3 | 重算 99.7 vs 冻结 99.7（n=300） |
| OK | 冻结件逐格一致 Phi-3.5-vision-instruct 8192 channel s3 | 重算 0.0 vs 冻结 0.0（n=300） |
| OK | 冻结件逐格一致 Phi-3.5-vision-instruct 8192 enumAbstain s3 | 重算 12.3 vs 冻结 12.3（n=300） |
| OK | 冻结件逐格一致 InternVL3.5-8B 4096 base s1 | 重算 0.0 vs 冻结 0.0（n=300） |
| OK | 冻结件逐格一致 InternVL3.5-8B 4096 permit s1 | 重算 94.0 vs 冻结 94.0（n=300） |
| OK | 冻结件逐格一致 InternVL3.5-8B 4096 channel s1 | 重算 0.0 vs 冻结 0.0（n=300） |
| OK | 冻结件逐格一致 InternVL3.5-8B 4096 enumAbstain s1 | 重算 91.7 vs 冻结 91.7（n=300） |
| OK | 冻结件逐格一致 InternVL3.5-8B 4096 base s2 | 重算 0.0 vs 冻结 0.0（n=300） |
| OK | 冻结件逐格一致 InternVL3.5-8B 4096 permit s2 | 重算 94.0 vs 冻结 94.0（n=300） |
| OK | 冻结件逐格一致 InternVL3.5-8B 4096 channel s2 | 重算 0.0 vs 冻结 0.0（n=300） |
| OK | 冻结件逐格一致 InternVL3.5-8B 4096 enumAbstain s2 | 重算 91.7 vs 冻结 91.7（n=300） |
| OK | 冻结件逐格一致 InternVL3.5-8B 4096 base s3 | 重算 0.0 vs 冻结 0.0（n=300） |
| OK | 冻结件逐格一致 InternVL3.5-8B 4096 permit s3 | 重算 94.0 vs 冻结 94.0（n=300） |
| OK | 冻结件逐格一致 InternVL3.5-8B 4096 channel s3 | 重算 0.0 vs 冻结 0.0（n=300） |
| OK | 冻结件逐格一致 InternVL3.5-8B 4096 enumAbstain s3 | 重算 92.0 vs 冻结 92.0（n=300） |
| OK | 冻结件逐格一致 InternVL3.5-8B 8192 base s1 | 重算 0.0 vs 冻结 0.0（n=300） |
| OK | 冻结件逐格一致 InternVL3.5-8B 8192 permit s1 | 重算 94.0 vs 冻结 94.0（n=300） |
| OK | 冻结件逐格一致 InternVL3.5-8B 8192 channel s1 | 重算 0.0 vs 冻结 0.0（n=300） |
| OK | 冻结件逐格一致 InternVL3.5-8B 8192 enumAbstain s1 | 重算 91.7 vs 冻结 91.7（n=300） |
| OK | 冻结件逐格一致 InternVL3.5-8B 8192 base s2 | 重算 0.0 vs 冻结 0.0（n=300） |
| OK | 冻结件逐格一致 InternVL3.5-8B 8192 permit s2 | 重算 94.0 vs 冻结 94.0（n=300） |
| OK | 冻结件逐格一致 InternVL3.5-8B 8192 channel s2 | 重算 0.0 vs 冻结 0.0（n=300） |
| OK | 冻结件逐格一致 InternVL3.5-8B 8192 enumAbstain s2 | 重算 92.0 vs 冻结 92.0（n=300） |
| OK | 冻结件逐格一致 InternVL3.5-8B 8192 base s3 | 重算 0.0 vs 冻结 0.0（n=300） |
| OK | 冻结件逐格一致 InternVL3.5-8B 8192 permit s3 | 重算 94.0 vs 冻结 94.0（n=300） |
| OK | 冻结件逐格一致 InternVL3.5-8B 8192 channel s3 | 重算 0.0 vs 冻结 0.0（n=300） |
| OK | 冻结件逐格一致 InternVL3.5-8B 8192 enumAbstain s3 | 重算 92.0 vs 冻结 92.0（n=300） |
| OK | 冻结件逐格一致 gemma-3-12b 4096 base s1 | 重算 0.0 vs 冻结 0.0（n=300） |
| OK | 冻结件逐格一致 gemma-3-12b 4096 permit s1 | 重算 91.0 vs 冻结 91.0（n=300） |
| OK | 冻结件逐格一致 gemma-3-12b 4096 channel s1 | 重算 0.0 vs 冻结 0.0（n=300） |
| OK | 冻结件逐格一致 gemma-3-12b 4096 enumAbstain s1 | 重算 81.0 vs 冻结 81.0（n=300） |
| OK | 冻结件逐格一致 gemma-3-12b 4096 base s2 | 重算 0.0 vs 冻结 0.0（n=300） |
| OK | 冻结件逐格一致 gemma-3-12b 4096 permit s2 | 重算 91.3 vs 冻结 91.3（n=300） |
| OK | 冻结件逐格一致 gemma-3-12b 4096 channel s2 | 重算 0.0 vs 冻结 0.0（n=300） |
| OK | 冻结件逐格一致 gemma-3-12b 4096 enumAbstain s2 | 重算 81.0 vs 冻结 81.0（n=300） |
| OK | 冻结件逐格一致 gemma-3-12b 4096 base s3 | 重算 0.0 vs 冻结 0.0（n=300） |
| OK | 冻结件逐格一致 gemma-3-12b 4096 permit s3 | 重算 91.3 vs 冻结 91.3（n=300） |
| OK | 冻结件逐格一致 gemma-3-12b 4096 channel s3 | 重算 0.0 vs 冻结 0.0（n=300） |
| OK | 冻结件逐格一致 gemma-3-12b 4096 enumAbstain s3 | 重算 81.0 vs 冻结 81.0（n=300） |
| OK | 冻结件逐格一致 gemma-3-12b 8192 base s1 | 重算 0.0 vs 冻结 0.0（n=300） |
| OK | 冻结件逐格一致 gemma-3-12b 8192 permit s1 | 重算 91.7 vs 冻结 91.7（n=300） |
| OK | 冻结件逐格一致 gemma-3-12b 8192 channel s1 | 重算 0.0 vs 冻结 0.0（n=300） |
| OK | 冻结件逐格一致 gemma-3-12b 8192 enumAbstain s1 | 重算 81.0 vs 冻结 81.0（n=300） |
| OK | 冻结件逐格一致 gemma-3-12b 8192 base s2 | 重算 0.0 vs 冻结 0.0（n=300） |
| OK | 冻结件逐格一致 gemma-3-12b 8192 permit s2 | 重算 91.3 vs 冻结 91.3（n=300） |
| OK | 冻结件逐格一致 gemma-3-12b 8192 channel s2 | 重算 0.0 vs 冻结 0.0（n=300） |
| OK | 冻结件逐格一致 gemma-3-12b 8192 enumAbstain s2 | 重算 81.0 vs 冻结 81.0（n=300） |
| OK | 冻结件逐格一致 gemma-3-12b 8192 base s3 | 重算 0.0 vs 冻结 0.0（n=300） |
| OK | 冻结件逐格一致 gemma-3-12b 8192 permit s3 | 重算 91.0 vs 冻结 91.0（n=300） |
| OK | 冻结件逐格一致 gemma-3-12b 8192 channel s3 | 重算 0.0 vs 冻结 0.0（n=300） |
| OK | 冻结件逐格一致 gemma-3-12b 8192 enumAbstain s3 | 重算 81.0 vs 冻结 81.0（n=300） |

**① 本轮均值与极差（独立重算）**

| 构建 | 臂 | ctx | 三次弃权率 | 均值 | 极差 |
|---|---|---|---|---|---|
| Phi-3.5-vision-instruct | base | 4096 | 0.0 / 0.0 / 0.0 | **0.0** | **0.0** |
| Phi-3.5-vision-instruct | base | 8192 | 0.0 / 0.0 / 0.0 | **0.0** | **0.0** |
| Phi-3.5-vision-instruct | permit | 4096 | 95.3 / 95.0 / 95.0 | **95.1** | **0.3** |
| Phi-3.5-vision-instruct | permit | 8192 | 99.7 / 99.7 / 99.7 | **99.7** | **0.0** |
| Phi-3.5-vision-instruct | channel | 4096 | 0.0 / 0.0 / 0.0 | **0.0** | **0.0** |
| Phi-3.5-vision-instruct | channel | 8192 | 0.0 / 0.0 / 0.0 | **0.0** | **0.0** |
| Phi-3.5-vision-instruct | enumAbstain | 4096 | 48.7 / 48.7 / 49.0 | **48.8** | **0.3** |
| Phi-3.5-vision-instruct | enumAbstain | 8192 | 12.7 / 12.3 / 12.3 | **12.4** | **0.4** |
| InternVL3.5-8B | base | 4096 | 0.0 / 0.0 / 0.0 | **0.0** | **0.0** |
| InternVL3.5-8B | base | 8192 | 0.0 / 0.0 / 0.0 | **0.0** | **0.0** |
| InternVL3.5-8B | permit | 4096 | 94.0 / 94.0 / 94.0 | **94.0** | **0.0** |
| InternVL3.5-8B | permit | 8192 | 94.0 / 94.0 / 94.0 | **94.0** | **0.0** |
| InternVL3.5-8B | channel | 4096 | 0.0 / 0.0 / 0.0 | **0.0** | **0.0** |
| InternVL3.5-8B | channel | 8192 | 0.0 / 0.0 / 0.0 | **0.0** | **0.0** |
| InternVL3.5-8B | enumAbstain | 4096 | 91.7 / 91.7 / 92.0 | **91.8** | **0.3** |
| InternVL3.5-8B | enumAbstain | 8192 | 91.7 / 92.0 / 92.0 | **91.9** | **0.3** |
| gemma-3-12b | base | 4096 | 0.0 / 0.0 / 0.0 | **0.0** | **0.0** |
| gemma-3-12b | base | 8192 | 0.0 / 0.0 / 0.0 | **0.0** | **0.0** |
| gemma-3-12b | permit | 4096 | 91.0 / 91.3 / 91.3 | **91.2** | **0.3** |
| gemma-3-12b | permit | 8192 | 91.7 / 91.3 / 91.0 | **91.3** | **0.7** |
| gemma-3-12b | channel | 4096 | 0.0 / 0.0 / 0.0 | **0.0** | **0.0** |
| gemma-3-12b | channel | 8192 | 0.0 / 0.0 / 0.0 | **0.0** | **0.0** |
| gemma-3-12b | enumAbstain | 4096 | 81.0 / 81.0 / 81.0 | **81.0** | **0.0** |
| gemma-3-12b | enumAbstain | 8192 | 81.0 / 81.0 / 81.0 | **81.0** | **0.0** |

**② 关键格判定（`Phi-3.5-vision-instruct` / `enumAbstain`）**

- 4096：48.8%（极差 0.3 pp）｜8192：12.4%（极差 0.4 pp）｜上下文之差 **36.4 pp**
| OK | 上下文之差远大于同上下文极差（判定"服务配置可解释"） | 36.4 pp ≫ 0.4 pp |
| OK | 冻结件的判定与独立重算一致 | {'delta_ctx_pp': 36.4, 'range_4096_pp': 0.3, 'range_8192_pp': 0.4, 'reading': '服务配置（上下文长度）可解释'} |
| OK | 冻结件记的差值与独立重算一致 | 冻结 36.4 vs 重算 36.4 |

**③ 12 格里跨上下文移动 > 0.5 pp 的**：Phi-3.5-vision-instruct/permit 4.6 pp、Phi-3.5-vision-instruct/enumAbstain 36.4 pp
| OK | 跨上下文移动 >0.5 pp 的格恰为 2 个且都属于 Phi-3.5 | 实际：[('Phi-3.5-vision-instruct', 'permit', 4.6000000000000085), ('Phi-3.5-vision-instruct', 'enumAbstain', 36.366666666666674)] |
| OK | 其余 10 格跨上下文移动 ≤0.5 pp |  |

**④ 与两个历史件逐格核对（同上下文的那一对应最接近）**

| 构建 | 臂 | 本轮 4096 | 冻结面板(4096) | 差 | 本轮 8192 | E1 列(8192) | 差 |
|---|---|---|---|---|---|---|---|
| Phi-3.5-vision-instruct | base | 0.0 | 0.0 | +0.0 | 0.0 | 0.0 | +0.0 |
| Phi-3.5-vision-instruct | permit | 95.1 | 95.0 | +0.1 | 99.7 | 99.7 | +0.0 |
| Phi-3.5-vision-instruct | channel | 0.0 | 0.0 | +0.0 | 0.0 | 0.0 | +0.0 |
| Phi-3.5-vision-instruct | enumAbstain | 48.8 | 48.7 | +0.1 | 12.4 | 12.7 | -0.3 |
| InternVL3.5-8B | base | 0.0 | 0.0 | +0.0 | 0.0 | 0.0 | +0.0 |
| InternVL3.5-8B | permit | 94.0 | 94.0 | +0.0 | 94.0 | 94.0 | +0.0 |
| InternVL3.5-8B | channel | 0.0 | 0.0 | +0.0 | 0.0 | 0.0 | +0.0 |
| InternVL3.5-8B | enumAbstain | 91.8 | 92.0 | -0.2 | 91.9 | 91.7 | +0.2 |
| gemma-3-12b | base | 0.0 | 0.0 | +0.0 | 0.0 | 0.0 | +0.0 |
| gemma-3-12b | permit | 91.2 | 91.3 | -0.1 | 91.3 | 91.3 | +0.0 |
| gemma-3-12b | channel | 0.0 | 0.0 | +0.0 | 0.0 | 0.0 | +0.0 |
| gemma-3-12b | enumAbstain | 81.0 | 81.0 | +0.0 | 81.0 | 81.0 | +0.0 |
| OK | 与两个历史件逐格差 ≤1.0 pp（24 格） | 最大 |差| = 0.3 pp |
| OK | 每个臂文件的行数一致（同一批样本） | 行数取值集合 [300] |
| OK | 样本规模 = 300（探针 --n 300；与冻结面板同一批） | [300] |

**独立重算：80 项通过 ｜ 0 项失败**
