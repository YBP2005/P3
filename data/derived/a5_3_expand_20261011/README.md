# Enlarged target-matched sample on the public benchmark — release record

Reported in the supplementary material at **M.24.5** (and summarised in the main text at 5.13).

## Contents

| file | what it is |
|---|---|
| `raw/rec_b01_class_rep1.jsonl` | per-call records, build `rec_b01`, 17,538 rows |
| `raw/rec_b03_class_rep1.jsonl` | per-call records, build `rec_b03`, 17,538 rows |
| `build_pool.py` | builds the frame manifest (per-image class name, ground truth, split) |
| `criteria_tables.md` | every reported number, per build x arm and pooled |
| `PROTOCOL.md` | the frozen frame, thresholds, interval algorithm and stopping rule |

Each record file holds 5,846 images x 3 arms, one row per image x arm. Every row carries `http = 200`;
no cell is missing.

## Fields used by the reported quantities

| field | meaning |
|---|---|
| `image` | image identifier in the frame |
| `class_name` | the target word asked for that image (its own class name) |
| `arm` | `base` (number only), `permit` (number or abstention token), `channel` (three-option reply) |
| `gt` | ground-truth point count for that image |
| `pred` | numeric prediction parsed from the verbatim reply, where one is present |
| `http` | transport status; only `200` rows enter the analysis |

## Build identity

Per-call records are released under neutral build identifiers. `rec_b01` is `InternVL3_5-8B` and
`rec_b03` is `llava-onevision-qwen2-7b-ov`; the full mapping is in the release README one level above.

## Reproducing the table

Regenerate `criteria_tables.md` from `raw/*.jsonl` alone; no model call is required. Numeric replies are
matched in the verbatim reply text, and `abstain`, `cannot_judge` and `no_people` count as non-numeric
outlets. A strict JSON parse will **not** reproduce the numeric column, because several replies quote the
number as a JSON string.

## Limit that this frame cannot lift

This frame contains **no image whose ground-truth count of the asked class is zero**, so
`P(true zero | answered zero)` is **not identifiable** here at any sample size. Only behavioural zero
rates and errors are reported.
