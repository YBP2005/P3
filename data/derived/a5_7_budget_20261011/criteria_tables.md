# The ordering under a common error and cost budget: a pre-registered re-check

Every number below is produced by `analyze_a57.py` (the repaired analyzer) over `manifest.csv`
and `work/`, and is reproduced independently by `reproduce_a57.py`. The domain is **synthetic and
newly rendered**; it is not a public benchmark and no number here is comparable to one measured on
a public corpus.

**Comparability rule, frozen in advance.** A pair of a unit's levels may be compared only if
`max(MAE)/min(MAE) <= 1 + B` **and** `max(cost)/min(cost) <= C`. Cost is a declared proxy:
`ceil(d/8)` for the density knob (3 / 4 / 5) and `px^2` for the resolution knob. A unit with no
admissible pair is recorded as **not computable** and stays in the denominator; it is never
imputed and never dropped.

**Criterion, frozen in advance.** Spearman(full-level ordering, budget-matched ordering) `= 1.00`
**and** the top knob unchanged. A miss is reported as a miss.

## 1 Scale and integrity

| quantity | value |
|---|---|
| independent service starts | 54 |
| raw rows across all 54 files | 14,400 |
| rows with `http == 200` (real calls) | 12,600 |
| rows with `http == NOIMG` (no call made) | 1,800 |
| rows entering the analysis after de-duplication by image identity | **10,800** |
| images per cell | **200** |
| starts per cell | **3** |
| units (`build x knob`) | **6** |
| missing (`http == 200`, unparseable) in one build | **121** (3.36% of that build's 3,600 rows) |

Image identity is asserted before any statistic is computed: for the density knob the three levels
must share a seed and canvas while differing in bytes; for the resolution knob they must share the
scene while differing in bytes. Both gates pass with zero violations.

## 2 Main and secondary criteria (repaired caliber)

| criterion | units meeting it | proportion | Wilson 95% | Spearman | median retention | top knob changes | verdict |
|---|---:|---:|---|---:|---:|---|---|
| **pre-registered primary** `(B, C) = (0.10, 2.0)` | 2/6 | **0.3333** | [0.097, 0.700] | **-1.0000** | **0.456** | yes | **FAIL** |
| pre-registered secondary `(0.25, 4.0)` | 3/6 | **0.5000** | [0.188, 0.812] | **-0.5000** | **0.612** | yes | **FAIL** |
| post-hoc one-sided: cost ceiling only | 6/6 | **1.0000** | [0.610, 1.000] | **1.0000** | **1.000** | no | **PASS** |
| post-hoc one-sided: error budget only | 2/6 | **0.3333** | [0.097, 0.700] | **-1.0000** | **0.456** | yes | **FAIL** |

**Both pre-registered criteria are missed, and are reported as missed.** Under the repaired caliber
the density knob admits no admissible pair at `B = 0.10`, so three density units and one resolution
unit are not computable; all four remain in the denominator.

## 3 The unrepaired reading, printed alongside

The analyzer as first shipped carried two defects against the frozen criteria: the density cost
proxy was parsed with the resolution knob's prefix-stripping rule (`'24'` -> 4, `'30'` -> 0,
`'36'` -> 6, giving `ceil(d/8)` = 1 / 0 / 1 and silently tripping the `min(cost) <= 0` skip), and
ground truth was taken once from the unit's first level and reused at all three. Both are repaired
with **no criterion relaxed**. The unrepaired numbers:

| criterion | units meeting it | Spearman | median retention | top knob changes | verdict |
|---|---:|---:|---:|---|---|
| **pre-registered primary** `(B, C) = (0.10, 2.0)` | 5/6 | 0.8000 | 0.456 | yes | **FAIL** |
| pre-registered secondary `(0.25, 4.0)` | 6/6 | 0.7714 | 0.625 | yes | **FAIL** |

Both readings are released: the unrepaired one as `results/*_as_shipped.csv` and
`analyze_a57_prefix.py`, the repaired one as `results/*.csv` and `analyze_a57.py`.
The pre-registered reading is the one the criterion is judged against.

## 4 Self-proof of the repair

`analyze_a57.py --selftest` feeds the frozen 28-unit reference construction embedded in the file
through the repaired code. All four published readings reproduce **bit for bit**:

| tag | units | Spearman | median retention |
|---|---:|---:|---:|
| `(0.10, 2.0)` | 14 | 0.7674 | 0.477 |
| `(0.25, 4.0)` | 20 | 0.8227 | 0.582 |
| cost ceiling only | 17 | 0.9275 | 1.000 |
| error budget only | 16 | 0.8292 | 0.477 |

The log is released as `selftest_after_fix.txt`; the pre-fix analyzer is released alongside so the
comparison stays checkable.

## 5 Per-unit readings (repaired caliber, primary criterion)

| unit | levels | MAE per level | rho per level | cost per level | full span | admissible pairs | budget-matched span | retention | status |
|---|---|---|---|---|---:|---:|---:|---:|---|
| ivl358b / density | 24|30|36 | 7.3250;2.8900;5.1850 | 30.5208;4.5333;-12.8750 | 3;4;5 | 43.3958 | 0 | - | - | **NO_ADMISSIBLE_PAIR** |
| ivl358b / res | px640|px704|px832 | 9.5250;8.6700;7.7800 | -19.8438;-17.9375;-15.6667 | 4.096e+05;4.956e+05;6.922e+05 | 4.1771 | 1 | 1.9062 | 0.4564 | **COMPARABLE** |
| lov7b / density | 24|30|36 | 16.6186;11.8918;9.1598 | 67.6117;34.7251;11.5550 | 3;4;5 | 56.0567 | 0 | - | - | **NO_ADMISSIBLE_PAIR** |
| lov7b / res | px640|px704|px832 | 12.7943;25.0114;12.8286 | 5.1310;38.8452;6.4881 | 4.096e+05;4.956e+05;6.922e+05 | 33.7143 | 1 | 1.3571 | 0.0403 | **COMPARABLE** |
| q32fp8 / density | 24|30|36 | 8.0350;2.0200;3.9400 | 33.4792;6.7333;-10.9444 | 3;4;5 | 44.4236 | 0 | - | - | **NO_ADMISSIBLE_PAIR** |
| q32fp8 / res | px640|px704|px832 | 4.7650;4.1750;5.6950 | -9.9271;-8.6979;-11.8646 | 4.096e+05;4.956e+05;6.922e+05 | 3.1667 | 0 | - | - | **NO_ADMISSIBLE_PAIR** |

Note the density costs: **3 / 4 / 5**, which is `ceil(d/8)` at densities 24 / 30 / 36 and is the
value the repair restores. Every density unit reports **zero** admissible pairs at `B = 0.10` even
though its cost is now correct, so the not-computable verdict is driven by the error budget and not
by the cost proxy.

## 6 Coverage, duplication and missing values

| build | knob | level | start | rows | parseable | `http != 200` |
|---|---|---|---:|---:|---:|---:|
| ivl358b | density | 24 | 1 | 200 | 200 | 0 |
| ivl358b | density | 24 | 2 | 200 | 200 | 0 |
| ivl358b | density | 24 | 3 | 200 | 200 | 0 |
| ivl358b | density | 30 | 1 | 200 | 200 | 0 |
| ivl358b | density | 30 | 2 | 200 | 200 | 0 |
| ivl358b | density | 30 | 3 | 200 | 200 | 0 |
| ivl358b | density | 36 | 1 | 200 | 200 | 0 |
| ivl358b | density | 36 | 2 | 200 | 200 | 0 |
| ivl358b | density | 36 | 3 | 200 | 200 | 0 |
| ivl358b | res | 640 | 1 | 200 | 200 | 0 |
| ivl358b | res | 640 | 2 | 200 | 200 | 0 |
| ivl358b | res | 640 | 3 | 200 | 200 | 0 |
| ivl358b | res | 704 | 1 | 200 | 200 | 0 |
| ivl358b | res | 704 | 2 | 200 | 200 | 0 |
| ivl358b | res | 704 | 3 | 200 | 200 | 0 |
| ivl358b | res | 832 | 1 | 200 | 200 | 0 |
| ivl358b | res | 832 | 2 | 200 | 200 | 0 |
| ivl358b | res | 832 | 3 | 200 | 200 | 0 |
| lov7b | density | 24 | 1 | 200 | 195 | 0 |
| lov7b | density | 24 | 2 | 200 | 194 | 0 |
| lov7b | density | 24 | 3 | 200 | 195 | 0 |
| lov7b | density | 30 | 1 | 200 | 194 | 0 |
| lov7b | density | 30 | 2 | 200 | 195 | 0 |
| lov7b | density | 30 | 3 | 200 | 194 | 0 |
| lov7b | density | 36 | 1 | 200 | 195 | 0 |
| lov7b | density | 36 | 2 | 200 | 195 | 0 |
| lov7b | density | 36 | 3 | 200 | 194 | 0 |
| lov7b | res | 640 | 1 | 200 | 191 | 0 |
| lov7b | res | 640 | 2 | 200 | 192 | 0 |
| lov7b | res | 640 | 3 | 200 | 191 | 0 |
| lov7b | res | 704 | 1 | 200 | 190 | 0 |
| lov7b | res | 704 | 2 | 200 | 189 | 0 |
| lov7b | res | 704 | 3 | 200 | 190 | 0 |
| lov7b | res | 832 | 1 | 200 | 196 | 0 |
| lov7b | res | 832 | 2 | 200 | 194 | 0 |
| lov7b | res | 832 | 3 | 200 | 195 | 0 |
| q32fp8 | density | 24 | 1 | 200 | 200 | 0 |
| q32fp8 | density | 24 | 2 | 200 | 200 | 0 |
| q32fp8 | density | 24 | 3 | 200 | 200 | 0 |
| q32fp8 | density | 30 | 1 | 200 | 200 | 0 |
| q32fp8 | density | 30 | 2 | 200 | 200 | 0 |
| q32fp8 | density | 30 | 3 | 200 | 200 | 0 |
| q32fp8 | density | 36 | 1 | 200 | 200 | 0 |
| q32fp8 | density | 36 | 2 | 200 | 200 | 0 |
| q32fp8 | density | 36 | 3 | 200 | 200 | 0 |
| q32fp8 | res | 640 | 1 | 200 | 200 | 0 |
| q32fp8 | res | 640 | 2 | 200 | 200 | 0 |
| q32fp8 | res | 640 | 3 | 200 | 200 | 0 |
| q32fp8 | res | 704 | 1 | 200 | 200 | 0 |
| q32fp8 | res | 704 | 2 | 200 | 200 | 0 |
| q32fp8 | res | 704 | 3 | 200 | 200 | 0 |
| q32fp8 | res | 832 | 1 | 200 | 200 | 0 |
| q32fp8 | res | 832 | 2 | 200 | 200 | 0 |
| q32fp8 | res | 832 | 3 | 200 | 200 | 0 |

The 1,800 duplicated rows and the 1,800 `NOIMG` rows are described in `README.md` and counted in
`results/normalize_report.txt`. Neither enters the analysis.

## 7 Sensitivity, as printed

| restriction | units | units meeting the criterion | Spearman | verdict |
|---|---:|---:|---:|---|
| all six units (primary) | 6 | 2 | -1.0000 | FAIL |
| excluding one build | 4 | 2 | -1.0000 | FAIL |
| density knob only | 3 | 0 (not computable) | - | FAIL |
| resolution knob only | 3 | 2 | -1.0000 | FAIL |
| not-computable units imputed at best span | 6 | - | 0.7714 | FAIL |
| not-computable units imputed at worst | 6 | - | -0.4395 | FAIL |

The two imputation rows are **post-hoc** and are labelled as such. Both directions still miss, but
the top-knob verdict is sensitive to the imputation direction, which is disclosed rather than
resolved.

## 8 The positive finding: which constraint binds

| diagnostic | units | Spearman | median retention | top knob | verdict |
|---|---:|---:|---:|---|---|
| cost ceiling released, error budget kept | 6 | **1.0000** | 1.000 | unchanged | PASS |
| error budget released, cost ceiling kept | 2 | **-1.0000** | 0.456 | changes | FAIL |

Releasing the cost ceiling leaves the ordering exactly as published; releasing the error budget
leaves it failing. On this independently constructed domain the **error budget, not the cost
ceiling, is the binding constraint** — the same direction as the published caliber. Both rows are
post-hoc one-sided diagnostics, not pre-registered criteria.

## 9 Reproducing

`analyze_a57.py --selftest` needs no data. To read this domain, run the repaired analyzer with
`--out .` over this directory, or run `reproduce_a57.py`, a second implementation that recomputes
the proportions, the Spearman values, the retention and the two one-sided diagnostics straight
from `raw/`; its output is released as `reproduce_a57.out.txt`. Neither needs a model call or a
GPU.
