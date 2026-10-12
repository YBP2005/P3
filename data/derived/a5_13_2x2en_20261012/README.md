# `a5_13_2x2en_20261012` — Cross-language replication of the four output contracts (English prompt, same pool)

Released for Appendix **M.58** of the supplementary material. Neutral naming; no author-side paths and no credentials are carried.

## What is here

* `work/<family>/<condition>/run.jsonl` — one record per served image, exactly as produced.
* `contracts/` — the contract text(s) actually served and the per-image roster (`target_map*.csv`). The `image` column is a **basename**; the original archive stored a server-side path, which is not reproduced here.
* `criteria_20261012.json` — the decision table, **restated in English**: the counting rules, the pools and the replication definition.
* `FINGERPRINTS.txt` — md5 and byte count of every released file, plus the source archive.

## How to recompute

`code/analysis/recompute_a5_13_15.py --derived <this directory>` recomputes every count and every rate printed in Appendix M.58 from these files alone: no model call and no GPU.

## Counting rules in one place

* **rows_counted** — only rows with http == 200; other rows enter neither numerator nor denominator
* **deduplication** — one image one vote (deduplicate by `image`)
* **true_zero_roster** — the frozen contract `target_map_<cond>.csv`, column `true_zero == 1`
* **answered_zero** — `pred == 0`
* **abstention** — `abstain is True` (the contract's own refusal token)
* **unparseable** — `parse_ok is False`, reported in its own column and never merged into abstention
* **double_annotation** — a row that is both `pred == 0` and `abstain is True`; the inclusive reading counts it as an answered zero and the exclusive reading does not, and both are printed where the case arises
* **partition_identity** — answered zero + non-zero + unparseable == denominator
