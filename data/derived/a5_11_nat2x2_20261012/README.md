# The same four contracts on a natural-image pool

`raw/<build>/<condition>.jsonl` holds the per-call records (518 images per cell, 259 of them true-zero).
`pool/manifest.csv` is the 518-row stimulus manifest with each image's `sha256`. `contracts/` holds the four
contract texts (byte-identical to the rendered-pool copies released in the sibling directory
`a5_6_2x2_20261011`), the two sentence files and the per-image rosters. `criteria_tables.md` states the
counts, the rates and the cross-domain comparison; `recount.py` recomputes them from `raw/`, `pool/` and
`contracts/` alone. No model call and no GPU are needed.
