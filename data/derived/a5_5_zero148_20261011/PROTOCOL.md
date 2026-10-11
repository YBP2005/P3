# Frozen protocol — true-zero pool on natural images, with an independent blind check

This file records the design parameters as fixed **before any new model output existed**, together with
one registered revision that was also made before any new model output. It is a protocol record, not a
narrative.

## Purpose

To test, on **natural** images rather than rendered ones, the quantity that the public-benchmark frame
cannot identify: when the asked target really is absent from the photograph, does the model report
absence? The pool is deliberately drawn from a source that does not overlap the frame used to estimate
any rate in this work.

## Frame

- **Source**: the **COCO subset** of the FSC-147 release — the `test_coco` and `val_coco` splits,
  **487** images. This subset was not used to estimate any rate, false-positive rate or rule in this
  work; the rules and rates come from the dense synthetic corpus and from the pools already reported.
- **Sampling**: a fixed-seed random draw of **150** images from the 487. The seed and the drawn list
  were fixed at freeze time and their digest recorded.
- **Construction of "true zero"**: for each drawn image, ask for a target word that is **not present** in
  that image, so that the correct answer is **0**. The target word is taken from the dataset's 147-class
  list and is different from the image's own class; the pairing table was fixed at freeze time.

## Independent blind check

- Every image was checked one at a time, **blind**: only the image under a blind name was presented, with
  no build, no arm and no model answer visible.
- Two questions were put for each image: whether the queried target word is in fact absent from the image
  (absent ⇒ the true-zero label holds), and whether an instance of that target is in fact present
  (present ⇒ the image does not qualify).
- **The check was carried out by a model, not by a human annotator.** It is an independent
  model-conducted verification, and it is recorded as such.
- Each entry is recorded individually in `blind_verdicts.csv` (blind name, class asked, verdict,
  confidence, note).

## Execution

- **Four builds**; the `base` arm only.
- Protocol and parsing as in the rest of this work.
- Intended scale: 150 images x 4 builds x 1 repetition = 600 cells.

## Criteria

- the pool's reported quantity is the **true-zero detection rate**: the share of true-zero images on
  which the model answers zero;
- `P(true zero | answered zero)`: because every image in the qualifying pool is a true zero by
  construction, this quantity is **1.0 identically** and is reported as such, explicitly **not as a
  finding**;
- intervals: Wilson 95% at cell level, and an image-level bootstrap one-sided 95% upper bound;
- missing records are listed separately and are never filled in or guessed.

## Registered revision (made before any new model output)

- The check returned **148** `absent`, **1** `present` and **1** `unclear`.
- **The disposition of the images that did not pass was changed to exclusion rather than positional
  substitution.** The reason is that substitution re-opens a choice over which images enter the pool,
  whereas excluding a verification failure has a fixed direction and no selectivity. The frozen
  recording order is retained so that the exclusion can be audited.
- **Result**: the qualifying pool is **148** images, all of them true zeros under the independent check.
- **Reading adopted**: an object that resembles the queried target but is not of that class stays
  `absent`. Under a stricter reading, in which any look-alike object counts as `unclear`, **4 further
  images** would need to be excluded, taking the total from **2** to **6**. Both the adopted reading and
  the stricter alternative are recorded, so that the sensitivity is visible.
- Everything else (criteria, intervals, four builds on the `base` arm, 600 intended cells) is unchanged;
  the qualifying pool of 148 images yields **592** cells.
