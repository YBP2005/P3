# Repeated service starts on the 2x2 contract design

`raw/<build>/start<K>/<condition>.jsonl` holds the per-call records of one condition in one service start
(200 images per cell, 100 of them true-zero). `contracts/` holds the four frozen contract texts, the
per-image rosters and the two sentence files. `criteria_tables.md` states every count and interval;
`recount.py` recomputes them from `raw/` and `contracts/` alone.

The four contract texts here are byte-identical to those used on the rendered 2x2 pool released in the
sibling directory `a5_6_2x2_20261011`; `criteria_tables.md` in `a5_11_nat2x2_20261012` records the md5
comparison. No model call and no GPU are needed to reproduce anything in this directory.
