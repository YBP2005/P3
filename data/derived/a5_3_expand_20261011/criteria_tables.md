# Criteria table — enlarged target-matched sample on the public benchmark

Design: the **5,846** images of the FSC-147 release that the earlier 300-image panel did not use, each
asked its **own** per-image class name as the target word, under three response contracts and two builds.
All cells were served with HTTP 200: **5,846 × 3 × 2 = 35,076** cells, none missing. One repetition per
cell. The frozen sampling frame, thresholds, interval algorithm and stopping rule are recorded in
`PROTOCOL.md` and were fixed before any new model output was produced.

## Per build × arm

| build | arm | images | numeric replies | zero among those | zero rate among numeric | distinct images with a zero | median MAE | mean MAE |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| rec_b01 | base | 5846 | 5841 | 24 | 0.0041 | 24 | 3 | 17.31 |
| rec_b01 | permit | 5846 | 4421 | 0 | 0.0000 | 0 | 2 | 7.47 |
| rec_b01 | channel | 5846 | 5008 | 0 | 0.0000 | 0 | 3 | 10.91 |
| rec_b03 | base | 5846 | 5298 | 58 | 0.0109 | 58 | 6 | 29.72 |
| rec_b03 | permit | 5846 | 3775 | 19 | 0.0050 | 19 | 5 | 359097.01 |
| rec_b03 | channel | 5846 | 1605 | 5 | 0.0031 | 5 | 4 | 641.55 |

## Pooled over the two builds

| arm | numeric replies | zero among those | zero rate among numeric | distinct images with a zero |
|---|---:|---:|---:|---:|
| base | 11139 | 82 | 0.0074 | 79 |
| permit | 8196 | 19 | 0.0023 | 19 |
| channel | 6613 | 5 | 0.0008 | 5 |

## Gate (pre-registered)

- images in the frame **5846**; pooled `base` distinct images with a zero **79**; image-level zero rate **0.0135**
- image-level bootstrap one-sided 95% upper bound (one vote per image) = **0.0159**
- gate: distinct zero-answer images ≥ **60** **True**; upper bound ≤ **0.05** **True** ⇒ **PASS**
- the two readings are stated side by side: the pooled reading **passes**; the single-build reading does
  **not** (`rec_b03` supplies **58** such images and `rec_b01` **24**, each below 60).
- limitation: FSC-147 contains **no image whose ground-truth count of the asked class is zero**, so
  `P(true zero | answered zero)` is **not identifiable** in this frame. Only behavioural zero rates and
  errors are reported here.

## Parsing note

Numeric replies are matched in the verbatim reply text, and `abstain`, `cannot_judge` and `no_people` are
treated as non-numeric outlets. A strict JSON parse of the same records does **not** reproduce the
`numeric` column, because several replies quote the number as a JSON string.
