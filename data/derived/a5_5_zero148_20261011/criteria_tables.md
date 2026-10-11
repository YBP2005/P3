# Criteria table — true-zero pool on natural images under an independent blind check

Design: a pool drawn from the **COCO subset** of the FSC-147 release (the `test_coco` and `val_coco`
splits, 487 images), which is not the frame used to estimate any rate in this work. Every image in the
pool was checked one at a time, blind, for whether the queried target word is absent from that image.
The check returned **148** `absent`, **1** `present` and **1** `unclear`. **The check was carried out by
a model, not by a human annotator.** The two images that did not pass were **excluded**, leaving a valid
pool of **148** images; exclusion was chosen over substitution so that no choice over which images enter
the pool is re-opened. Four builds were run on the `base` arm over the 148 images: **4 × 148 = 592**
cells, all served with HTTP 200, none missing.

## Per build, `base` arm

| build | images | answer zero | true-zero detection rate | Wilson 95% upper bound | image-level bootstrap one-sided UB95 |
|---|---:|---:|---:|---:|---:|
| rec_b03 | 148 | 40 | **27.0%** | 0.3340 | 0.3311 |
| rec_b01 | 148 | 110 | **74.3%** | 0.7976 | 0.7973 |
| rec_b02 | 148 | 135 | **91.2%** | 0.9434 | 0.9527 |
| rec_b04 | 148 | 148 | **100.0%** | 1.0000 | 1.0000 |

The reported quantity is the **true-zero detection rate**: the share of images whose target really is
absent on which the model answers zero.

## Quantity that is not informative here

Because every image in this pool is a true zero by construction, `P(true zero | answered zero)` is
**1.0 identically** and is **not reported as a finding**. A pool of only true zeros can measure whether
absence is *detected*; it cannot measure whether a zero answer is *warranted*. The latter requires a pool
that mixes images with and without the target.

## Blind-check sensitivity

If an object that merely resembles the queried target were also scored `unclear` rather than `absent`,
**4 further images** would need to be excluded, taking the total from **2** to **6**. The category
reading (a look-alike that is not the same class stays `absent`) is the one adopted; the stricter
alternative is recorded here so that its effect is visible.

## Pool composition

The pool list records, per image, the blind identifier, the image file, the image's own class, the class
asked, the image's own ground-truth count and the split it came from. The per-image verdicts of the blind
check are released alongside in `blind_verdicts.csv`.

## Parsing note

Numeric replies are matched in the verbatim reply text, and `abstain`, `cannot_judge` and `no_people` are
treated as non-numeric outlets.
