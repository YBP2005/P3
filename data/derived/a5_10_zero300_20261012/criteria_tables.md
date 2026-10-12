# True-zero detection rate on two all-true-zero pools - criteria tables

This file answers one question: how often does each build answer zero when the target genuinely is
absent? Two pools are used, and they are reported **side by side and never merged**, because they
differ in size and in provenance.

* The **148-image** pool holds 148 images, all true zero, measured in one service start on the base
  arm.
* The **299-image** pool holds 299 images, all true zero, measured in one service start on the base
  arm. The pool name records a quota of 300; the realised size is **299** and it is never rounded to
  300 in this file.

**Conventions.** The detection rate is the answered-zero count over the true-zero image count.
Answered zero is `is_zero is True`, measured identical to `pred == 0` on all 1,196 rows of the larger
comparison. The upper bound is a **Wilson** one-sided bound with `z = 1.6448536269514722`. Only rows
with HTTP **200** enter a numerator or a denominator.

## 1 The two pools side by side

| build | 148-pool answered zero | rate | Wilson UB95 | unparseable | 299-pool answered zero | rate | Wilson UB95 | unparseable |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| **InternVL3.5-8B** | 110/148 | **74.3%** | 0.7976 | 0 | 205/299 | **68.6%** | 0.7280 | 0 |
| **Qwen3-VL-32B-FP8** | 148/148 | **100.0%** | 1.0000 | 0 | 298/299 | **99.7%** | 0.9993 | 0 |
| **llava-onevision-7B** | 40/148 | **27.0%** | 0.3340 | 66 | 77/299 | **25.8%** | 0.3012 | 133 |
| **InternVL3.5-38B-FP8** | 135/148 | **91.2%** | 0.9434 | 0 | 279/299 | **93.3%** | 0.9532 | 1 |
| **pooled** | 433/592 | **73.1%** | 0.7603 | 66 | **859/1196** | **71.8%** | 0.7391 | 134 |

## 2 Which pool each number belongs to

The correct figure for `lov7b` on the **148-image** pool is **27.0%** (40/148). The figure
**25.8%** belongs to the **299-image** pool (77/299). The two pools are reported separately here so
that a single pooled number cannot hide the difference.

## 3 The double reading for the lowest rate

`lov7b` has **133 rows out of 299** in the larger pool whose output cannot be parsed into a number
(`parse_ok` false). That gives two legitimate readings of the same cell:

| reading | numerator | denominator | rate | what the denominator is |
|---|---:|---:|---:|---|
| strict, whole pool | 77 | 299 | **25.8%** | every true-zero image, including rows that do not parse |
| inside parseable rows | 77 | 166 | **46.4%** | the 299 images minus the 133 unparseable rows |

The same direction holds on the 148-image pool, and more strongly: **66 of 148** rows are unparseable,
so the strict reading of **27.0%** corresponds to **40/82 = 48.8%** inside parseable rows.

**What the low strict rate does and does not mean.** The low rate for this build is **not** evidence
that the model explicitly answered a non-zero number when the target was absent. It is first of all
evidence that the output failed the contract format in nearly half of the cells, which is a counting
or compliance weakness. The unparseable count must therefore be quoted next to the rate, and the
strict rate must not be read as a measure of the model's belief about the target.

## 4 Limits

* Each pool is measured in a single service start, so the rates are point facts about those runs; the
  Wilson bounds account for sampling of images but not for start-to-start variation.
* Both pools contain **only** true-zero images, so a rate here says nothing about precision: what
  fraction of answered zeros occurs where a target really is present. Precision would need a mixed
  pool, and neither pool here is one.

## 5 Recomputing

`recount.py` reads `raw/` and `pool/` only and prints every number in this file; run it from this
directory with `python recount.py`.
