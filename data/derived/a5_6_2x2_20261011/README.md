# Point-named zero x abstention outlet: a 2x2 orthogonal design — release record

Reported in the supplementary material at **M.50**.

## Contents

| file | what it is |
|---|---|
| `raw/<build>__<condition>.jsonl` | per-call records, **600 rows each**, 20 files = **12,000** cells, one `base` arm only |
| `manifest.csv` | the frozen stimulus pool: 600 rows, each with target word, ground-truth count, the true-zero flag, all four rendering parameters, seed and `sha256` |
| `render_2x2.py` | the renderer that rebuilds the 600 images from the frozen seed |
| `make_contracts_2x2.py` | builds the four condition contracts and **asserts** the fixed-part equality below |
| `run_2x2.sh` | the orchestration that produced the raw records |
| `contracts_audit.md` | the contract audit: verbatim variable sentences, per-condition md5, the fixed-part equality |
| `FIXED_SENTENCES.txt`, `VARIABLE_SENTENCES.txt` | the two sentence blocks, as used |
| `_build_receipt.json` | the contract builder's receipt |
| `criteria_tables.py` | regenerates `criteria_tables.md` from `raw/*.jsonl` alone |
| `criteria_tables.md` | every reported number |

## Design

The four conditions are the full cross of two two-level factors. **Every** other string, the image set,
the required output format, `max_tokens` and the serving stack are held fixed, and the four conditions of
one build run inside **one service start**.

| factor | level | the one sentence that varies |
|---|---|---|
| A: the value zero is named | `name0` | names zero as the answer when the target is absent |
| | `no_name0` | empty string: the instruction never mentions zero |
| B: an abstention outlet is offered | `exit` | offers `abstain` / `cannot_judge` and a two-form JSON output |
| | `no_exit` | single-form JSON output only |

`no_name0_no_exit` is the baseline. Stripping both variable sentences leaves a byte-identical fixed part
in all four conditions (md5 `ffbbec0d020f4ad5d9e66567b43fbeb7`, 40 characters, for each of the four);
`make_contracts_2x2.py` refuses to emit the four files otherwise, and `contracts_audit.md` records the
check. The outlet sentence necessarily also carries the output-format sentence, which is why that
sentence belongs to the variable block and not to the fixed block — stated explicitly in the audit
rather than left implicit.

## Stimulus pool

600 images, all four rendering parameters jointly balanced **cell by cell** between the two classes:

| property | value |
|---|---|
| true-zero images | **300** — the asked target is **absent** by construction (`count_gt = 0`) |
| non-zero controls | **300** — the asked target is present, `count_gt = 48` |
| `px` | 704 / 832 / 960 |
| `size` | 16 / 20 / 24 |
| `blur` | 0 / 1 |
| `overlap` | 0.1 / 0.3 |
| seed | 20261012 (per image `20261012 + i`, so any image replays individually) |

The two classes share the same joint parameter distribution **cell for cell** (36 combinations, 8 or 9
images each), and each class carries 150 images per target word. A true-zero image's distractor family
differs from the asked target in **both** colour and shape, and is drawn in the same count (48), so
visual load matches the control. The renderer's own gate asserts that the asked target lands on exactly
0 points in a true-zero image and exactly 48 in a control image.

The manuscript reports the rate over **300** items per cell, not 600: the two classes answer different
questions and are never pooled.

## Fields used by the reported quantities

| field | meaning |
|---|---|
| `image` | image identifier (`t2x2_0001.png` ...), matching `manifest.csv` |
| `class_name` | the target word asked for that image |
| `arm` | the condition (`no_name0_no_exit`, `no_name0_exit`, `name0_no_exit`, `name0_exit`) |
| `gt` | exact ground-truth count for that image (`0` or `48`) |
| `pred` | numeric prediction parsed from the verbatim reply, where one is present |
| `abstain` | whether the reply was an abstention token |
| `http` | transport status; only `200` rows enter the analysis |

## Build identity

`ivl358b` is `InternVL3_5-8B`, `ivl38fp8` is `InternVL3_5-38B-FP8`, `lov7b` is
`llava-onevision-qwen2-7b-ov`, `phi35v` is `Phi-3.5-vision-instruct`, and `q32fp8` is
`Qwen3-VL-32B-Instruct-FP8` (served with `--quantization fp8`). The build is recorded per row in
`model`.

## Integrity

5 builds x 4 conditions x 600 images = **12,000** cells. Every cell carries `http = 200`; there are
**no** repeated `(build, condition, image)` keys and **no** malformed JSON lines. `criteria_tables.md`
§6 prints each check.

## What is and is not claimed

Each condition is measured in **one service start per build**, with no repetition. The release therefore
supports statements about the **direction** of each factor and about **between-build heterogeneity**; it
does not support a claim about start-to-start variability, and no such claim is made.

## Reproducing the tables

`criteria_tables.py` reads `raw/*.jsonl` alone and rewrites `criteria_tables.md`; no model call and no
GPU are needed. `render_2x2.py` re-derives the images from the frozen seed, and `make_contracts_2x2.py`
re-derives the four contracts while asserting the fixed-part equality.
