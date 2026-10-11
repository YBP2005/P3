# Second target-matched domain (rendered family) — release record

Reported in the supplementary material at **M.24.6** (and summarised in the main text at 5.13).

## Contents

| file | what it is |
|---|---|
| `raw/rec_b01.jsonl`, `raw/rec_b02.jsonl`, `raw/rec_b03.jsonl`, `raw/rec_b04.jsonl` | per-call records, 3,000 rows each (1,000 images x 3 arms) |
| `manifest.csv` | per-image manifest: target word, ground-truth count, rendering parameters, seed, sha256 |
| `target_map.csv` | per image, the frozen prompt strings for the three contracts |
| `render_domain2.py` | the renderer that regenerates the images from the frozen seed |
| `criteria_tables.md` | every reported number, per build on the `base` arm |
| `PROTOCOL.md` | the frozen corpus construction and criteria |

Every record carries `http = 200`; no cell is missing. **100 of the 1,000 images (10%) contain no target
at all** (`count_gt = 0`), which is what makes the conditional precision identifiable in this domain.

## Fields used by the reported quantities

| field | meaning |
|---|---|
| `image` | image identifier (`img_0001.png` ...), matching `manifest.csv` and `target_map.csv` |
| `class_name` | the per-image target word, naming an object actually drawn |
| `arm` | `base`, `permit`, `channel` |
| `gt` | exact ground-truth count for that image (`0` for the true-zero images) |
| `pred` | numeric prediction parsed from the verbatim reply, where one is present |
| `http` | transport status; only `200` rows enter the analysis |

## Build identity

`rec_b01` is `InternVL3_5-8B`, `rec_b02` is `InternVL3_5-38B-FP8`, `rec_b03` is
`llava-onevision-qwen2-7b-ov` and `rec_b04` is `Qwen3-VL-32B-Instruct-FP8`.

## Reproducing the corpus and the table

`render_domain2.py <out-dir> 1000` regenerates the images and `manifest.csv` from the frozen seed; the
sha256 column of `manifest.csv` is the per-image check on that regeneration. `criteria_tables.md` is
regenerated from `raw/*.jsonl` alone, so no model call and no image are needed to check the numbers.

## Scope statement that must accompany this table

The **10%** share of true-zero images is a property of the design. Any rate quoted from this directory
must be accompanied by it, otherwise this domain's higher zero rates are misread as a property of the
models rather than of the pool.
