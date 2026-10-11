# Frozen protocol — point-named zero x abstention outlet, a 2x2 orthogonal design

This file records the design as fixed **before any model output existed**. Nothing here was relaxed
afterwards. It is a protocol record, not a narrative.

## The two factors, and why exactly two sentences vary

Two binary factors are crossed, giving four conditions:

- **A — the value zero is named.** `name0` inserts one sentence stating that if the target is absent the
  answer is zero. `no_name0` inserts the empty string, so the instruction never mentions zero at all.
- **B — an abstention outlet is offered.** `exit` inserts one sentence offering `abstain` /
  `cannot_judge` and a two-form JSON output. `no_exit` inserts the single-form JSON output only.

The outlet sentence **necessarily** also carries the output-format sentence, because permitting an
abstention changes the JSON shape. It is therefore declared as part of the variable block rather than
being smuggled into the fixed block. Stripping both variable blocks leaves the same fixed part in all
four conditions byte for byte, and the contract builder asserts this and refuses to emit the four files
otherwise. The check and the per-condition digests are recorded in `contracts_audit.md`.

The named-zero sentence is placed after the "do not double-count" sentence and before the output-format
sentence, so that it reads as a counting rule and does not displace any fixed sentence or move position
between conditions.

## Held fixed across the four conditions

The image set; the target word per image; the counting request and the no-double-count sentences; the
single-form JSON discipline in the two `no_exit` conditions; `max_tokens` = 1024; the protocol (text
first, PNG as-is, no `temperature` sent); and the service, port and build. The four conditions of a
build run inside **one service start**, so the start is not a degree of freedom between conditions.

## Stimulus

600 images rendered from a single frozen seed. Parameters and their balance:

| property | value |
|---|---|
| total | 600 (`t2x2_0001.png` ... `t2x2_0600.png`, blind names) |
| true-zero images | **300** (`true_zero = 1`, `count_gt = 0`): the asked target is drawn nowhere |
| non-zero controls | **300** (`count_gt = 48`, a single level) |
| `px` | 704 / 832 / 960 |
| `size` | 16 / 20 / 24 |
| `blur` | 0 / 1 |
| `overlap` | 0.1 / 0.3 |
| target words | four colour x shape families |
| seed | 20261012, with per-image `20261012 + i` so any image replays individually |

Orthogonality is enforced by the renderer's own gate, not by inspection:

- the true-zero and non-zero classes share the **same joint distribution** of `px`, `size`, `blur` and
  `overlap` **cell for cell** (36 combinations, 8 or 9 images each);
- `target_word` is balanced at 150 images per family within each class (75 true zero, 75 non-zero);
- a true-zero image's distractor family differs from the asked target in **colour and shape**, and is
  drawn in the same count (48), so visual load matches the control;
- the asked target lands on exactly **0** points in every true-zero image and exactly **48** in every
  control; a nonzero failure count aborts the render.

## Reading rules, fixed in advance

- **Sets.** The true-zero set Z (`count_gt = 0`, n = 300 per condition per build) and the non-zero set N
  (`count_gt = 48`, n = 300 per condition per build). **Every rate's denominator is 300**, not 600.
- **Values.** A cell's value is a number k, an abstention token (`abstain` / `cannot_judge`), or
  unparseable. Unparseable is reported as a missing value and is never imputed.
- **Reported quantities.** (P1) the answered-zero count on Z; (P2) the abstention count on Z; (P3) the
  exact-48 count on N, which is the **cost axis** — if P1 rises while P3 collapses, the named zero is a
  cheap degenerate solution rather than a better one; (P4) the answered-zero count on N, which separates
  a correct zero from "answer zero rather than abstain".
- **Main effects and interaction.** The difference in differences is read per quantity, taking the
  `name0` minus `no_name0` contrast inside each outlet level and then differencing across outlet levels.
- **Intervals.** Wilson for each rate. Cross-build and cross-condition comparisons use Fisher's exact
  test on 2x2 count tables; any comparison not shown here is labelled exploratory rather than
  confirmatory.
- **Never pooled.** The four conditions are reported and read **within each build**, one table row per
  build. Cross-build pooling is not performed anywhere, because the served build is the unit that the
  contract cannot equalise (its chat template ships with the weights).

## Acceptance gates, enforced by the analysis

1. each build x condition: 600 rows and 600 distinct image keys;
2. no `abstain` / `cannot_judge` output in either `no_exit` condition — a hard gate, and a violation is
   reported separately rather than folded into the main table;
3. neither `no_name0` condition may contain the named-zero sentence (contract gate);
4. the 5 x 4 x 600 = 12,000 keys are pairwise distinct: no duplicate and no omission;
5. image `sha256` re-checked against `manifest.csv`, so an image and its record cannot be mismatched.

## Scale and limits, stated because the intervals cannot show them

- 5 builds x 4 conditions x 600 images = **12,000** cells, all served with HTTP 200.
- **One service start per build, no repetition per cell.** The design therefore reads the **direction**
  of each factor and the **between-build heterogeneity**; it does not measure start-to-start variability
  and no such claim is made from it.

## Planned sixth build, not run

A sixth build (a 4-bit quantised large model) was planned with its own documented serving requirements.
It is reported as **not run**, and the family count is five, rather than being silently substituted with
a near neighbour. No conclusion in the release depends on it.

## Reproducing

`render_2x2.py` rebuilds the images and their manifest from the frozen seed; `make_contracts_2x2.py`
rebuilds the four contracts and asserts the fixed-part equality; `run_2x2.sh` is the orchestration;
`criteria_tables.py` regenerates every reported number from `raw/*.jsonl` alone.
