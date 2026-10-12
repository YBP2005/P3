# Point-named zero x abstention outlet: a 2x2 orthogonal design - criteria tables

Every number below is recomputed from `raw/*.jsonl` alone; no model call and no GPU are needed.
Pool sizes are **300** true-zero images (`gt = 0`) and **300** non-zero controls (`gt = 48`) per
cell; **5** weight builds x **4** conditions x **600** images = **12,000** cells, all served with
HTTP **200**, with **no** repeated key and **no** malformed JSON. A **sixth** build was served
separately, on the same four contract files, and its four record files are released in `raw/`
beside the others; its counts are in section 8 below and are **never** pooled with the five.

The four conditions are the cross of two two-level factors and nothing else:

| factor | level | the one sentence that varies |
|---|---|---|
| A: the value zero is named | `name0` | names zero as the answer when the target is absent |
| | `no_name0` | empty string: the instruction never mentions zero |
| B: an abstention outlet is offered | `exit` | offers `abstain` / `cannot_judge` and a two-form JSON output |
| | `no_exit` | single-form JSON output only |

Stripping both variable sentences leaves a byte-identical fixed part in all four conditions
(md5 `ffbbec0d020f4ad5d9e66567b43fbeb7`, 40 characters, for each of the four). The outlet sentence
necessarily also carries the output-format sentence, which is why that sentence belongs to the
variable block rather than the fixed block; `contracts_audit.md` states this explicitly. All other
strings, the image set, the required output format, `max_tokens` 1024 and the serving stack are
held fixed, and the four conditions of one build share a single service start.

## 1 Answered-zero count on the 300 true-zero images

One row per build; the four conditions are never pooled across builds.

| build | `no_name0_no_exit` | `no_name0_exit` | `name0_no_exit` | `name0_exit` |
|---|---:|---:|---:|---:|
| **InternVL3.5-8B** | 249 | 0 | 299 | 28 |
| **InternVL3.5-38B-FP8** | 299 | 55 | 300 | 296 |
| **llava-onevision-7B** | 162 | 3 | 207 | 30 |
| **Phi-3.5-vision** | 202 | 51 | 226 | 104 |
| **Qwen3-VL-32B-FP8** | 300 | 290 | 300 | 300 |

Each entry is a count out of **300**. Wilson 95% intervals on those counts:

| build | `no_name0_no_exit` | `no_name0_exit` | `name0_no_exit` | `name0_exit` |
|---|---:|---:|---:|---:|
| **InternVL3.5-8B** | [0.783, 0.868] | [0.000, 0.013] | [0.981, 0.999] | [0.065, 0.132] |
| **InternVL3.5-38B-FP8** | [0.981, 0.999] | [0.144, 0.231] | [0.987, 1.000] | [0.966, 0.995] |
| **llava-onevision-7B** | [0.483, 0.596] | [0.003, 0.029] | [0.636, 0.740] | [0.071, 0.139] |
| **Phi-3.5-vision** | [0.618, 0.724] | [0.132, 0.217] | [0.702, 0.799] | [0.295, 0.402] |
| **Qwen3-VL-32B-FP8** | [0.987, 1.000] | [0.940, 0.982] | [0.987, 1.000] | [0.987, 1.000] |

## 2 The outlet factor, read within each build at `no_name0`

| build | `no_name0_no_exit` | `no_name0_exit` | change |
|---|---:|---:|---:|
| **InternVL3.5-8B** | 249 | 0 | **-249** |
| **InternVL3.5-38B-FP8** | 299 | 55 | **-244** |
| **llava-onevision-7B** | 162 | 3 | **-159** |
| **Phi-3.5-vision** | 202 | 51 | **-151** |
| **Qwen3-VL-32B-FP8** | 300 | 290 | **-10** |

Four of the five builds collapse; the remaining build is nearly immune.

## 3 The named-zero factor, read within each build at both outlet levels

| build | no outlet: `no_name0` -> `name0` | outlet offered: `no_name0` -> `name0` |
|---|---:|---:|
| **InternVL3.5-8B** | 249 -> 299 (**+50**) | 0 -> 28 (**+28**) |
| **InternVL3.5-38B-FP8** | 299 -> 300 (**+1**) | 55 -> 296 (**+241**) |
| **llava-onevision-7B** | 162 -> 207 (**+45**) | 3 -> 30 (**+27**) |
| **Phi-3.5-vision** | 202 -> 226 (**+24**) | 51 -> 104 (**+53**) |
| **Qwen3-VL-32B-FP8** | 300 -> 300 (**+0**) | 290 -> 300 (**+10**) |

The direction is positive in **5 of 5** builds at both outlet levels, so naming zero recovers
part of what the outlet removes.

## 4 True-zero abstention count (out of 300)

| build | `no_name0_no_exit` | `no_name0_exit` | `name0_no_exit` | `name0_exit` |
|---|---:|---:|---:|---:|
| **InternVL3.5-8B** | 0 | 290 | 0 | 269 |
| **InternVL3.5-38B-FP8** | 0 | 245 | 0 | 4 |
| **llava-onevision-7B** | 0 | 240 | 0 | 208 |
| **Phi-3.5-vision** | 0 | 109 | 0 | 42 |
| **Qwen3-VL-32B-FP8** | 0 | 10 | 0 | 0 |

Abstention is exactly zero under `no_name0_no_exit` in every build, as the contract requires; it
is only reachable in the two `exit` conditions.

## 5 Non-zero controls (`gt = 48`, 300 images): the cost axis

| build | condition | exact-48 count | answered-zero count | abstention count |
|---|---|---:|---:|---:|
| **InternVL3.5-8B** | `no_name0_no_exit` | 3 | 0 | 0 |
| **InternVL3.5-8B** | `no_name0_exit` | 1 | 0 | 1 |
| **InternVL3.5-8B** | `name0_no_exit` | 4 | 0 | 0 |
| **InternVL3.5-8B** | `name0_exit` | 1 | 0 | 0 |
| **InternVL3.5-38B-FP8** | `no_name0_no_exit` | 20 | 0 | 0 |
| **InternVL3.5-38B-FP8** | `no_name0_exit` | 13 | 0 | 0 |
| **InternVL3.5-38B-FP8** | `name0_no_exit` | 10 | 1 | 0 |
| **InternVL3.5-38B-FP8** | `name0_exit` | 7 | 0 | 1 |
| **llava-onevision-7B** | `no_name0_no_exit` | 11 | 0 | 0 |
| **llava-onevision-7B** | `no_name0_exit` | 7 | 0 | 49 |
| **llava-onevision-7B** | `name0_no_exit` | 5 | 2 | 0 |
| **llava-onevision-7B** | `name0_exit` | 2 | 0 | 42 |
| **Phi-3.5-vision** | `no_name0_no_exit` | 2 | 12 | 0 |
| **Phi-3.5-vision** | `no_name0_exit` | 0 | 8 | 68 |
| **Phi-3.5-vision** | `name0_no_exit` | 0 | 89 | 0 |
| **Phi-3.5-vision** | `name0_exit` | 2 | 26 | 26 |
| **Qwen3-VL-32B-FP8** | `no_name0_no_exit` | 1 | 0 | 0 |
| **Qwen3-VL-32B-FP8** | `no_name0_exit` | 4 | 0 | 0 |
| **Qwen3-VL-32B-FP8** | `name0_no_exit` | 3 | 0 | 0 |
| **Qwen3-VL-32B-FP8** | `name0_exit` | 2 | 0 | 0 |

## 6 Integrity

| check | value |
|---|---|
| cells (rows) | 12000 |
| distinct `(build, condition, image)` keys | 12000 |
| repeated keys | 0 |
| rows with HTTP 200 | 12000 |
| rows with HTTP != 200 | 0 |
| malformed JSON lines | 0 |
| images per cell | 600 (300 true zero + 300 non-zero) |

## 7 Reproducing

This file is regenerated by `criteria_tables.py`, which reads `raw/*.jsonl` only. The stimulus pool
is `manifest.csv` (600 rows, each with its `sha256`); `render_2x2.py` rebuilds the images from the
frozen seed and `make_contracts_2x2.py` rebuilds the four contracts while asserting the fixed-part
equality above. `run_2x2.sh` is the orchestration that produced the raw records, and
`contracts_audit.md` is its own contract audit.

## 8 The sixth build, served separately

The five builds in sections 1-5 are the ones the original 2x2 design served. A **sixth** build,
**Pixtral-Large-w4a16**, was served separately on the **same four contract files** (the byte-identity of
the contract text is checked in the sibling directory `a5_11_nat2x2_20261012`). Its four record files are
`raw/pixtral__<condition>.jsonl`; each holds **600** unique images with HTTP **200**, no repeated key and
no malformed line. Its counted rows are **never** pooled with the five builds above.

| build | `no_name0_no_exit` | `no_name0_exit` | `name0_no_exit` | `name0_exit` |
|---|---:|---:|---:|---:|
| **Pixtral-Large-w4a16** | 178 | **5** | 269 | 140 |

Each entry is a count out of **300** true-zero images. The outlet effect on this build is
**178 -> 5**, a change of **-173** with **2.8%** of the baseline retained; the naming effect is
**178 -> 269** without the outlet and **5 -> 140** with it.

**Conventions, stated for all six builds.** Answered zero is `is_zero is True`, which on every row here
is identical to `pred == 0`. The true-zero roster is the **frozen contract** `target_map_<condition>.csv`,
read image by image for `true_zero == 1`, because the record files carry no `true_zero` field. Only rows
with HTTP **200** enter a numerator or a denominator. Two rows of the Phi-3.5-vision build satisfy **both**
`pred == 0` and `abstain == True` (image `t2x2_0433.png` under `no_name0_exit`, image `t2x2_0125.png`
under `name0_exit`); counting them as answered zeros gives **51** and **104**, excluding them gives 50 and
103, and the released table and records use the **inclusive** reading.
