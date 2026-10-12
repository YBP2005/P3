# Asymmetric cost and the answered-zero channel

`cost_asymmetry.py` is the driver: `--selftest` runs the hand-computed assertions and the negative cases,
`--all --outdir <dir>` re-derives every reading. `analysis_input.csv` is the per-item analysis input it
consumes; `E5_zero_channel_audit.csv` is the per-source audit of the answered-zero channel;
`criteria_tables.md` states the definitions, the identity, its failure boundaries and both E1 readings.

The experiment is pure CPU and needs no model call, no GPU and no network.
