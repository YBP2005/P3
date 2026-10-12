# True-zero detection on two all-true-zero pools

`raw/<build>.jsonl` holds the 299-image pool records; `raw/pool148_<build>.jsonl` holds the 148-image pool
records. `pool/target_map.csv` and `pool/target_map_148.csv` are the rosters, both all `true_zero = 1`.
`criteria_tables.md` states the counts, the rates and the two readings; `recount.py` recomputes them from
`raw/` and `pool/` alone. No model call and no GPU are needed.
