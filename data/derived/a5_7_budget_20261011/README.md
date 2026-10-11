# The ordering under a common error and cost budget: a pre-registered re-check on a new synthetic domain — release record

Reported in the supplementary material at **M.51**.

## Contents

| file | what it is |
|---|---|
| `raw/<alias>__<knob>__<level>__start<K>.jsonl` | per-call records, **200 rows each**, 54 files = **10,800** analysis calls |
| `work/<alias>/<knob>/<level>/start<K>/run.jsonl` | the same records in the hierarchy the analyzer reads |
| `manifest.csv` | the frozen stimulus manifest: 1,200 rows, all six level cells, each with its physical `image` path, `sha256`, seed and ground-truth count |
| `contracts.csv` | the per-cell contract strings as served |
| `PREREGISTRATION.md` | the frozen criteria file: the quoted caliber, both pre-run revisions, the `(B, C)` pairs, the cost proxies, the stop rules and the limits |
| `render_a57.py` | renders the new synthetic domain from the frozen seed |
| `run_a57.sh` | the orchestration: one independent service start per `(alias, knob, level, start)` |
| `analyze_a57.py` | the analyzer, **with the two defects of §"Analyzer repair" repaired** |
| `analyze_a57_prefix.py` | the analyzer exactly as first shipped, kept so the unrepaired reading is checkable |
| `selftest_after_fix.txt` | the repair's self-proof: the four printed reference readings, reproduced bit for bit |
| `reproduce_a57.py` | a **second, independent** implementation that re-derives the readings from `raw/` alone |
| `reproduce_a57.out.txt` | that implementation's output, including the unrepaired comparison reading |
| `criteria_tables.md` | every reported number |

## Design

The published ordering compares each knob at its own extreme, and those extremes are not equally
affordable. This re-check asks what survives when every knob is held to the **same budget**: a pair of a
unit's levels may be compared only if their mean absolute errors are within a pre-registered factor
`1 + B` of each other **and** their inference costs are within a pre-registered factor `C`.

| item | frozen value |
|---|---|
| primary `(B, C)` | **(0.10, 2.0)** |
| secondary `(B, C)` | (0.25, 4.0) |
| comparable pair | `max(MAE)/min(MAE) <= 1 + B` **and** `max(cost)/min(cost) <= C` |
| unit | one `(build, knob)` pair: **6** units = 3 builds x 2 knobs |
| `rho(l)` | `100 * (sum(pred) - sum(gt)) / sum(gt)` at level `l` |
| `span` | `max rho - min rho` over the levels |
| retention | `span_BM / span_full`, **upper** median |
| criterion | Spearman(full-level, budget-matched) = 1.00 **and** the top knob unchanged |

Cost is a **declared proxy**, as in the published caliber: `ceil(d / 8)` for the density knob (so 3 / 4 /
5 at densities 24 / 30 / 36) and `px^2` for the resolution knob. A unit with no admissible pair is
recorded as **not computable** and is **left in the denominator** — never imputed and never dropped.

## Domain

The domain is **synthetic and newly rendered**; it is not a public benchmark, and no number here is
comparable to one measured on a public corpus. Two knobs, three levels each:

| knob | levels | construction |
|---|---|---|
| `density` | 24 / 30 / 36 targets | same canvas (832 px), re-rendered **per level** from the same seed, so the three levels are nested rather than resampled |
| `res` | 640 / 704 / 832 px | target count fixed at **48** |

## Scale, and the two revisions recorded before the result

- 3 builds x 2 knobs x 3 levels x **200 images** x **3 independent service starts** = **10,800** calls,
  from **54** independent service starts.
- **Revision A.** The per-cell image count was raised to 200 before any statistic was computed.
- **Revision B.** A contract-path change mid-run caused the same 200 images in one build x knob to be
  served twice, and one other cell to be attempted with no image resolvable at all. Both are disclosed
  below rather than silently dropped.

## What was actually served, and what enters the analysis

| quantity | count |
|---|---|
| independent service starts | **54** |
| raw rows over all 54 files | **14,400** |
| rows with `http == 200` (real calls) | **12,600** |
| rows with `http == NOIMG` (no call made) | **1,800** |
| rows entering the analysis, after de-duplication by image identity | **10,800** |

**Duplicate vintages (1,800 rows).** In one build x knob the image field was changed from a bare name to
a prefixed path while the runner's key embeds that field, so the same 200 images really were called
twice, in two rounds about 32 minutes apart. De-duplication is by **image identity**, keeping the newer
vintage, and it removes exactly 1,800 rows.

**NOIMG rows (1,800 rows).** In the other build x knob, one of the two vintages has no resolvable image,
so **no call was made**. These rows are retained in the release as the audit evidence for that cell and
are **not** counted as calls.

**Missing values.** One build contributes **121 rows (3.36%** of that build's 3,600 rows**)** with no
parseable number. They are recorded as missing and are never imputed. That build's two units therefore
have valid-reading common-item intersections of **194** and **175** items, against **200** for each of
the other four units; both are still above the 0.80 valid-share gate.

**Image identity.** The `density` knob requires the three levels to share a seed and canvas while
differing in bytes; the `res` knob requires the same scene while differing in bytes. The analyzer
asserts both, and asserts that the three byte strings within a level set are pairwise distinct, before
computing anything.

## Analyzer repair

The analyzer as first shipped disagreed with the frozen criteria in **two** places. Both were repaired,
and **no criterion was relaxed**: the `(B, C)` pairs, the comparability condition, the top-knob rule and
the `min(cost) <= 0` skip rule are unchanged.

**D1 — the density cost proxy was mis-parsed.** The cost parser for the resolution knob strips a two-
character prefix, which is right for labels like `px640`. The same parser was applied to the density
knob, whose labels are bare numbers, so `'24'` was read as `4`, `'30'` as `0` and `'36'` as `6`, giving
`ceil(d / 8)` = **1 / 0 / 1** instead of 3 / 4 / 5. The consequence was not only a wrong cost: because
`min(cost) = 0` trips the `min(cost) <= 0` skip rule, two level pairs per density unit were **silently
skipped**, and every density unit lost its comparability.

**D2 — ground truth was reused from level 0.** Ground truth was taken once, from the unit's first level,
and reused at all three levels. For the resolution knob the count is fixed at 48, so nothing changed; for
the density knob the GT is 24 / 30 / 36, so levels 30 and 36 were scored against **24**. Both the MAE and
the denominator of `rho` were therefore wrong at two of three levels.

**Self-proof.** `analyze_a57.py --selftest` feeds the frozen 28-unit reference construction embedded in
the file through the repaired code and reproduces the four published readings **bit for bit**:

| tag | units | Spearman | retention |
|---|---|---|---|
| `(0.10, 2.0)` | **14** | **0.7674** | **0.477** |
| `(0.25, 4.0)` | **20** | **0.8227** | **0.582** |
| cost ceiling only | **17** | **0.9275** | **1.000** |
| error budget only | **16** | **0.8292** | **0.477** |

The pre-fix analyzer is released alongside as `analyze_a57_prefix.py` so the unrepaired reading
stays checkable.

## Readings

**Pre-registered caliber (cost `ceil(d/8)` and per-level ground truth):**

| quantity | primary `(0.10, 2.0)` | secondary `(0.25, 4.0)` |
|---|---|---|
| units meeting the comparability condition | **2 of 6 = 0.3333** | 3 of 6 = 0.5000 |
| Wilson 95% interval | **[0.097, 0.700]** | [0.188, 0.812] |
| Spearman vs. the full-level ordering | **-1.0000** | -0.5000 |
| median span retention | **0.456** | 0.612 |
| top knob changes | **yes** | yes |
| criterion | **missed** | **missed** |

**The criterion is missed and is reported as missed.** Under the repaired caliber the density knob
additionally admits **no** pair at `B = 0.10`, so three density units and one resolution unit are not
computable; all four stay in the denominator.

**The unrepaired reading, printed alongside.** With both defects present the analyzer reports **5 of 6 =
0.8333**, Spearman **0.8000**, retention **0.456** and a changed top knob. Both readings are reported;
the pre-registered one is the one the criterion is judged against.

**The post-hoc one-sided diagnostics, which are the positive finding:**

| diagnostic | units | Spearman | retention | top knob |
|---|---|---|---|---|
| cost ceiling released, error budget kept | 6 | 1.0000 | 1.000 | **unchanged** |
| error budget released, cost ceiling kept | 2 | **-1.0000** | 0.456 | changes |

Releasing the cost ceiling leaves the ordering **exactly** as published, while releasing the error
budget leaves it failing. On this independently constructed domain the **error budget, not the cost
ceiling, is the binding constraint** — the same direction as the published caliber.

**Sensitivity, reported as printed.** The result is not uniformly robust and the release says so:
excluding one build gives 2 of 4; the density knob alone gives 0 of 3 (not computable); the resolution
knob alone gives 2 of 3. Imputing the not-computable units at their best and worst values — **post-hoc
and labelled as such** — moves Spearman to 0.7714 and -0.4395; **both directions still miss**, but the
top-knob verdict is sensitive to the imputation direction, which is disclosed rather than resolved.

## Reproducing

`analyze_a57.py --selftest` reproduces the four reference readings and needs no data. To read this
domain, run the fixed analyzer with `--out .` over this directory (it reads `manifest.csv` and `work/`),
or run `reproduce_a57.py`, which recomputes the comparability proportions, the Spearman values, the
retention and the two one-sided diagnostics straight from `raw/` and prints them for checking. No model
call and no GPU are needed for either.
