# True-zero pool on natural images, under an independent blind check — release record

Reported in the supplementary material at **M.24.7** (and summarised in the main text at 5.13).

## Contents

| file | what it is |
|---|---|
| `raw/rec_b01.jsonl`, `raw/rec_b02.jsonl`, `raw/rec_b03.jsonl`, `raw/rec_b04.jsonl` | per-call records, 148 rows each, `base` arm only |
| `pool_list.csv` | the frozen pool: blind identifier, image file, the image's own class, the class asked, the image's own ground-truth count, split |
| `target_map.csv` | per image, the frozen prompt strings for the three contracts |
| `blind_verdicts.csv` | the blind check's per-image verdicts (blind name, class asked, verdict, confidence, note) |
| `select_pool.py` | builds the pool: the fixed-seed draw from the source frame plus the true-zero pairing |
| `criteria_tables.md` | every reported number, per build on the `base` arm |
| `PROTOCOL.md` | the frozen frame, the blind-check rule and the registered revision |

Four builds x 148 images = **592** cells, all served with HTTP 200, none missing.

## Fields used by the reported quantities

| field | meaning |
|---|---|
| `image` | image identifier (`blind_001.png` ...), matching `pool_list.csv` and `target_map.csv` |
| `class_name` | the target word asked for that image (absent from it by construction) |
| `arm` | `base` only in this release |
| `gt` | ground-truth count of the asked target in that image (`0` throughout the qualifying pool) |
| `pred` | numeric prediction parsed from the verbatim reply, where one is present |
| `http` | transport status; only `200` rows enter the analysis |

## Build identity

`rec_b01` is `InternVL3_5-8B`, `rec_b02` is `InternVL3_5-38B-FP8`, `rec_b03` is
`llava-onevision-qwen2-7b-ov` and `rec_b04` is `Qwen3-VL-32B-Instruct-FP8`.

## The blind check was model-conducted

The per-image check of whether the queried target is absent was carried out **by a model, not by a human
annotator**. `blind_verdicts.csv` records it as such. Its verdicts were **148** `absent`, **1**
`present` and **1** `unclear`; the two images that did not pass were **excluded**, leaving a qualifying
pool of **148** images.

## Reproducing the table

`criteria_tables.md` is regenerated from `raw/*.jsonl` alone; no model call is needed. `select_pool.py`
re-derives the pool list from the source frame under the frozen seed.

## Quantity that is not informative here

Because every image in the qualifying pool is a true zero by construction, `P(true zero | answered zero)`
is **1.0 identically** and is **not reported as a finding**. A pool of only true zeros measures whether
absence is *detected*; it does not measure whether a zero answer is *warranted*.
