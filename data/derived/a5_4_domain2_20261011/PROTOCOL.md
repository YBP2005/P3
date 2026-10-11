# Frozen protocol — second target-matched domain (rendered family)

This file records the design parameters as fixed **before any new model output existed**. None was
relaxed afterwards. It is a protocol record, not a narrative.

## Corpus

- **New rendering parameter family**: image size, blur and overlap settings drawn from values disjoint
  from the corpora used elsewhere in this work, so that a property of the new family cannot be inherited
  from the corpora already reported.
- **Per-image target word**: each image's target word names an object **actually present in that image**
  (drawn from a colour x shape family, e.g. *red circles*, *blue circles*, *green squares*). The target
  class is fixed by construction and its ground truth is exact.
- **True-zero images**: a fixed proportion of the images — **10%** — contain **no** instance of the
  target asked (`count_gt = 0`). This is what makes `P(true zero | answered zero)` identifiable in this
  domain, in contrast to the public-benchmark frame.
- **Scale**: **1,000** images, rendered from a fixed seed, with the sha256 of every image recorded
  individually in `manifest.csv`.
- Each image is described by: `item`, `target_word`, `count_gt`, `family`, `color`, `size`, `blur`,
  `overlap`, `seed`, `px`, `sha256`, `true_zero`.

## Execution

- **Four builds**, three response contracts (`base`, `permit`, `channel`), one repetition per cell:
  **1,000 × 3 × 4 = 12,000** cells.
- Protocol and parsing as in the rest of this work: text-first prompt form, images as PNG,
  `max_tokens = 1024`, no temperature sent, parser accepting both `{"count": N}` and `{"response": N}`.

## Criteria

- zero rate, with the denominator stated;
- error on the numeric subset — median and mean MAE aggregated per image;
- image-level one-sided 95% upper bound;
- **conditional precision `P(true zero | answered zero)`**, which **is** identifiable in this domain
  because the pool contains true zeros, and which must therefore be reported — this is the key increment
  of this domain over the public-benchmark frame;
- the two domains are tabulated side by side: the natural frame (no true zeros) and this rendered family
  (true zeros present).

## The proportion of true-zero images must be stated with every rate

The 10% share is a design property, not an estimate. Any rate quoted from this domain must be accompanied
by it, otherwise this domain's higher zero rates are read as a property of the models.

## Common discipline

- Criteria, thresholds and interval algorithms are fixed and are not changed after the fact.
- Missing records are listed separately and are never filled in or guessed.
- If a build cannot be served, it is recorded and skipped; the criteria are not changed. If a build's run
  is short of its intended volume, that is reported as not reached rather than adjusted.
