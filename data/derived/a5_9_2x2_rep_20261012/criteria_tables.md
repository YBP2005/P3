# The outlet factor across independent service starts - criteria tables

Every number below is recomputed from `raw/` alone; no model call and no GPU are needed.

Three builds (`ivl358b`, `q32fp8`, `lov7b`) were each served in **three independent service
starts** under the same four conditions, giving **36 cells** of **200** images, of which **100**
per cell are true-zero images. All 36 cells delivered 200 rows with HTTP **200**, with no repeated
image and no missing parse status.

## 1 Per (build x condition) interval table

| build | condition | rep1 | rep2 | rep3 | mean | range | mean rate | boot LB95 | boot UB95 | Wilson LB95 | Wilson UB95 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| InternVL3.5-8B | `no_name0_no_exit` | 77 | 82 | 83 | 80.67 | 6 | 0.8067 | 0.7433 | 0.8633 | 0.7376 | 0.8660 |
| InternVL3.5-8B | `no_name0_exit` | 0 | 0 | 0 | 0.00 | 0 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0263 |
| InternVL3.5-8B | `name0_no_exit` | 98 | 99 | 99 | 98.67 | 1 | 0.9867 | 0.9667 | 1.0000 | 0.9564 | 0.9978 |
| InternVL3.5-8B | `name0_exit` | 5 | 4 | 6 | 5.00 | 2 | 0.0500 | 0.0233 | 0.0800 | 0.0245 | 0.0992 |
| Qwen3-VL-32B-FP8 | `no_name0_no_exit` | 100 | 100 | 100 | 100.00 | 0 | 1.0000 | 1.0000 | 1.0000 | 0.9737 | 1.0000 |
| Qwen3-VL-32B-FP8 | `no_name0_exit` | 95 | 96 | 97 | 96.00 | 2 | 0.9600 | 0.9333 | 0.9833 | 0.9138 | 0.9819 |
| Qwen3-VL-32B-FP8 | `name0_no_exit` | 100 | 100 | 100 | 100.00 | 0 | 1.0000 | 1.0000 | 1.0000 | 0.9737 | 1.0000 |
| Qwen3-VL-32B-FP8 | `name0_exit` | 100 | 100 | 100 | 100.00 | 0 | 1.0000 | 1.0000 | 1.0000 | 0.9737 | 1.0000 |
| llava-onevision-7B | `no_name0_no_exit` | 47 | 54 | 52 | 51.00 | 7 | 0.5100 | 0.4367 | 0.5800 | 0.4286 | 0.5909 |
| llava-onevision-7B | `no_name0_exit` | 1 | 0 | 3 | 1.33 | 3 | 0.0133 | 0.0033 | 0.0267 | 0.0022 | 0.0436 |
| llava-onevision-7B | `name0_no_exit` | 66 | 63 | 69 | 66.00 | 6 | 0.6600 | 0.5967 | 0.7233 | 0.5788 | 0.7328 |
| llava-onevision-7B | `name0_exit` | 12 | 11 | 15 | 12.67 | 4 | 0.1267 | 0.0833 | 0.1733 | 0.0843 | 0.1952 |

The denominator is the **100** true-zero images, not the 200 images in the cell; the other 100
images are non-zero controls and do not enter this table.

**Interval conventions.** The image-level bootstrap gives one vote per image: the three starts are
averaged per image first, images are then resampled, `n_boot = 2000`, the lower bound is read at
`out[int(0.05*N)]` and the upper bound at `out[int(0.95*N)]`, with seed **20261011**. The Wilson
bounds are one-sided with `z = 1.6448536269514722` and are computed on the mean count out of the
100 true-zero images. The separation criterion is the frozen one: the upper bound of
`no_name0_exit` must lie below the lower bound of `no_name0_no_exit`.

## 2 Separation

| build | `no_name0_no_exit` mean | its LB (boot) | its LB (Wilson) | `no_name0_exit` mean | its UB (boot) | its UB (Wilson) | separated (boot) | separated (Wilson) | reading |
|---|---:|---:|---:|---:|---:|---:|---|---|---|
| InternVL3.5-8B | 80.67/100 | 0.7433 | 0.7376 | 0.00/100 | 0.0000 | 0.0263 | yes | yes | **separated** |
| Qwen3-VL-32B-FP8 | 100.00/100 | 1.0000 | 0.9737 | 96.00/100 | 0.9833 | 0.9819 | yes | no | formally separated under bootstrap only |
| llava-onevision-7B | 51.00/100 | 0.4367 | 0.4286 | 1.33/100 | 0.0267 | 0.0436 | yes | yes | **separated** |

* `ivl358b` and `lov7b` separate under **both** interval conventions, so their collapse does not
  depend on the interval method.
* `q32fp8` **is not a collapse.** Its `no_name0_no_exit` cell is **100 of 100 true-zero images in
  all three starts**, so its rate sits exactly on the ceiling of 1.0 and its bootstrap lower bound
  is exactly 1.0000; any upper bound below 1.0 then "separates". Its actual outlet effect is only
  **100 -> 96** (**-4 pp**, **96.0%** retained), the smallest of the builds measured in the sibling
  directory `a5_6_2x2_20261011`. The formal criterion is met; the reading attached to it is that it
  is uninformative for this build, and this table must **not** be cited as evidence that the outlet
  removes answered zeros in that build.

## 3 Limits

* Each cell holds only **100** true-zero images, so the intervals are wide (the `lov7b`
  `no_name0_no_exit` lower bound is only 0.4367). The width is a property of the cell size.
* The bootstrap is seeded (**20261011**); a different seed moves the last decimal but does not
  reverse any separation reported here.
* Only three of the six builds measured in the sibling directory are covered here, so the
  cross-build statement rests there, and this table supplies only sign-level confirmation.
* The three starts are repeats of the same images under the same condition, so the 36 cells share
  one image set.

## 4 Recomputing

`recount.py` reads `raw/` and `contracts/` only and prints every number in this file; run it from
this directory with `python recount.py`.
