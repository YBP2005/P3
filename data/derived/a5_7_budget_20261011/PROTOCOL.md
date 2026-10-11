# Frozen protocol — the ordering under a common error and cost budget, re-checked on a new domain

This file records the design and the criteria as fixed **before the runs**. It is a protocol record, not
a narrative. Two revisions were made before any statistic was computed and are part of the record; they
are named below rather than silently applied.

## What is re-checked

The published ordering compares each knob at its own extreme, and those extremes are not equally
affordable. This re-check asks what survives when every knob is held to the **same budget**.

## Comparability rule

A pair of a unit's levels may be compared only if

- `max(MAE) / min(MAE) <= 1 + B`, **and**
- `max(cost) / min(cost) <= C`.

| item | frozen value |
|---|---|
| primary `(B, C)` | **(0.10, 2.0)** |
| secondary `(B, C)` | **(0.25, 4.0)** |
| post-hoc one-sided | cost ceiling only (`B` infinite, `C = 2`), error budget only (`B = 0.10`, `C` infinite) |

The two one-sided rows are **post-hoc diagnostics**, not pre-registered criteria, and are labelled as
such wherever they are reported.

## Cost proxy

Cost is a **declared proxy**, as in the published caliber. It is fixed here, before the runs:

| knob | proxy | values at the three levels |
|---|---|---|
| `density` | `ceil(d / 8)`, the counting-compute block count at a fixed canvas | **3 / 4 / 5** at densities 24 / 30 / 36 |
| `res` | `px^2`, the actual input pixel count | 640^2 / 704^2 / 832^2 |

## Unit, span and retention

- **Unit** = one `(build, knob)` pair: **6** units = 3 builds x 2 knobs.
- **Level reading** `rho(l) = 100 * (sum(pred) - sum(gt)) / sum(gt)` at level `l`.
- **Span** = `max rho - min rho` over the levels, taken as the largest span realised by any pair the
  budget admits.
- **Retention** = `span_BM / span_full`, aggregated with the **upper** median, i.e. `sorted(xs)[n // 2]`.
  This is the convention of the published implementation; the textbook median would change the primary
  retention from 0.477 to 0.453 on the reference construction, so the two are not interchangeable.
- **Not computable** = a unit with no admissible pair. Such a unit is **kept in the denominator**; it is
  never imputed and never dropped.

## Criterion

Spearman(full-level ordering, budget-matched ordering) `= 1.00` **and** the top knob unchanged. A miss is
reported as a miss, and the criteria are not adjusted after the fact.

## Domain

The domain is **synthetic and newly rendered** for this re-check. It is not a public benchmark, and no
number measured here is comparable to a number measured on a public corpus. Two knobs, three levels:

| knob | levels | construction |
|---|---|---|
| `density` | 24 / 30 / 36 targets | same canvas (832 px), **re-rendered per level** from the same seed so the three levels are nested; ground truth is the drawn count and therefore differs per level (24 / 30 / 36) |
| `res` | 640 / 704 / 832 px | target count fixed at **48** |

Ground truth is taken **per level**. This matters for the density knob and is exactly the point that the
D2 repair below restores.

## Scale, and the two pre-run revisions

- 3 builds x 2 knobs x 3 levels x **200 images** x **3 independent service starts** = **10,800** calls
  from **54** independent service starts.
- **Revision A.** The per-cell image count was raised to **200** before any statistic was computed.
- **Revision B.** After the runs began, a contract-path change made the image field of one build x knob
  a prefixed path while the runner's key embeds that field, so those 200 images were served twice; in
  one other cell the image was not resolvable and no call was made. De-duplication is therefore defined
  on **image identity**, keeping the newer vintage, and the two affected cells are disclosed in full.

## Execution

- One **independent service start per `(build, knob, level, start)`**, so the start is not a degree of
  freedom within a cell; per-call values are the median over the three starts.
- Serving: the same stack and protocol as the rest of this work; one image per prompt; a JSON count
  requested; no `temperature` sent.

## Reading rules fixed in advance

- Every rate's denominator is the **unit**, and the not-computable units stay in the denominator of the
  comparability proportion.
- The comparability proportion is reported with a Wilson interval; a unit-level bootstrap of the
  Spearman is reported alongside as a supplementary quantity, not as a substitute.
- Missing values (a reply with no parseable number) are recorded as missing and are never imputed. The
  valid-share gate is **0.80** per cell.
- Subset sensitivities (excluding a build, one knob at a time, and imputing the not-computable units at
  their best and worst) are reported as printed, and any imputation is labelled **post-hoc**.

## What this design cannot show

The domain is synthetic and the knob levels are nested by construction, so the spans are properties of
this rendering family and not of any corpus. The re-check can confirm or fail to confirm a **direction**
about which constraint binds; it cannot establish a general law of knob ordering, and no such claim is
made from it.

## Reproducing

`analyze_a57.py --selftest` reproduces the four published reference readings and needs no data. The
domain is read by `analyze_a57.py --out .` over this directory, and independently by
`reproduce_a57.py`, which re-derives the readings from `raw/` with a second implementation.
`render_a57.py` rebuilds the images and `run_a57.sh` is the orchestration.
