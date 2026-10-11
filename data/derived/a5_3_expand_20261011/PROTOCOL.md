# Frozen protocol — enlarged target-matched sample on the public benchmark

This file records the design parameters as they were fixed **before any new model output existed**.
None of them was relaxed afterwards. It is a protocol record, not a narrative.

## Frame

- **Population**: the FSC-147 release as distributed, **5,846** images — the images of the release that
  the earlier 300-image panel did not use.
- **Target word**: the **per-image official class name**, taken from the dataset's own class list
  (tab-separated; class names containing spaces are used verbatim). The earlier 300-image panel used the
  same construction for its matched condition.
- **No subsampling**: the whole remaining frame was run, to avoid a sampling bias.
- **Ground truth**: the point count of the release's annotation file.

## Contracts and protocol

- **Three arms**: `base` (number only), `permit` (number, or an explicit abstention token), `channel`
  (a three-option reply). The contract texts are the same ones used by the earlier target-matched panel.
- **Protocol**: text-first prompt form; images supplied as PNG; `max_tokens = 1024`; no temperature is
  sent. The reply parser accepts both `{"count": N}` and `{"response": N}` forms.
- **Repetition**: one repetition per cell. The gate concerns the number of *distinct images*, not the
  number of repetitions.

## Builds and stopping rule

- First batch: `rec_b03` and `rec_b01`, the two builds with the lowest measured per-cell latency.
- The second batch (two further builds) was to start only if the first batch's distinct zero-answer
  image count under `base` was still below 60. It was not started.
- **Stopping rule**: stop as soon as the matched condition under the load-bearing `base` arm reaches
  at least 60 distinct zero-answer images; if the frame is exhausted below that, report the gate as not
  reached and neither widen the threshold nor drop images.

## Criteria

1. zero rate under each arm, with the denominator stated (all cells of that arm, and separately the
   numeric replies);
2. error on the numeric subset — median and mean MAE aggregated per image;
3. conditional precision `P(true zero | answered zero)`, whose denominator is the answered-zero cells and
   whose truth is per-image `GT = 0`; because this frame contains no zero-GT image, that quantity is
   reported as **not identifiable** here and only the behavioural rates are given;
4. intervals: Wilson 95% at cell level, and an image-level bootstrap one-sided 95% upper bound with one
   vote per image.

## Gate

Distinct zero-answer images ≥ 60 **and** image-level one-sided 95% upper bound ≤ 0.05, both required
before a residual below 5% may be claimed; otherwise the result is reported as not determinate.

## Blind marking (recorded, not used by any reported quantity)

Where a zero appeared, the image was to be marked blind on two questions: whether the target class
matched the class asked, and whether the zero was accompanied by an explicit refusal or
cannot-judge statement. Marking was to use blind names only, with no build, arm or other build's answer
visible, and each entry recorded individually.

## Limits recorded in advance

- This frame has no ground-truth-zero image, so conditional precision and the true-zero base rate are
  not identifiable here. They are reported as not identifiable, not as 0 or 1.
- A target class may be ambiguous or may not match the visible object exactly; such cases are listed
  separately and are not folded into the principal criteria.
