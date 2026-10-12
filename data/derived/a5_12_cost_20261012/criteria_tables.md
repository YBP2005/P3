# Asymmetric cost, and what an answered zero is worth - criteria tables

Pure CPU: this file needs no model call, no GPU and no network. Every reading is recomputed by
`cost_asymmetry.py` from the per-item records released under `data/derived/`.

## 1 Frozen definitions

| quantity | definition |
|---|---|
| cell | a `(domain x family x arm/condition)` triple |
| MAE | `mean_i abs(pred_i - gt_i)` |
| asymmetric cost `C_r` | `[ c_u*sum max(gt-pred,0) + c_o*sum max(pred-gt,0) ] / sum gt`, with `c_u/c_o = r` and `c_o = 1` |
| ratios | `r` in `{1, 2, 5, 10}`; `r = 1` is the symmetric baseline, where `C_1 = n*MAE/sum gt` |
| E1 decision unit | a `(domain x family)` pair; an arm is a candidate action within that unit |
| E1 primary reading | **paired**: the same item parses successfully in every arm |
| E1 secondary reading | **full, unpaired**: each arm uses all of its own parseable items |
| E5 `P0` / `P2` | use `pred` as given; `P2` additionally reads `pred_i = 0` as **an estimate of zero** |
| E5 `P1` (**frozen**) | `pred_i = 0` means the image does not enter the automatic decision and goes to a human; the declared abstention cost is `c_u*gt_i`, our own definition, the "missed whole image" upper bound |
| E5 `P1` (**contrast only**) | the same abstention instead booked as an over-count, `c_o*gt_i = gt_i`. This is not the frozen convention and is reported only as a comparison quantity |
| unparsed rows | a non-numeric `pred` is excluded identically from all three strategies |

## 2 The main E5 reading: an identity, not a fit

**Proposition.** With `c_o = 1` and with `P1`'s abstention priced on the under-count side at `c_u*gt_i`,
`P1(i) = P2(i)` for every item, so `C(P2) - C(P1)` is identically zero.

**One-line proof.** Let `c_u = r` and `c_o = 1`, and let the true count `gt_i >= 0` (counts cannot be
negative; a negative value is rejected on read):

* if `pred_i = 0`, then `P2(i) = c_u*max(gt_i - 0, 0) + c_o*max(0 - gt_i, 0) = r*gt_i + 0 = r*gt_i`, and
  `P1(i) = c_u*gt_i = r*gt_i`, so the two are equal;
* if `pred_i != 0`, the two billing expressions are literal copies of one another, so they are equal.

Dividing both by the same `sum_i gt_i` preserves the equality. Therefore `C(P2) - C(P1)` is identically
zero.

**Boundary of the identity, to be quoted with it.**

| condition | identity |
|---|---|
| `c_o = 1` (the frozen convention here) | holds |
| `P1`'s abstention cost taken on the **under-count** side, `c_u*gt_i` | holds |
| `gt_i >= 0` | holds |
| `P1`'s abstention cost moved to the **over-count** side, `c_o*gt_i` | **fails**: the per-item difference becomes `(c_u - c_o)*gt_i = (r-1)*gt_i` (section 4) |
| `c_u` fixed at 1 while `c_o = r` varies | **fails**: both sides of the ratio then move together and the conclusion reverses |

**The reading this licenses.** *Treating an answered zero as an estimate of zero is cost-identical to
discarding the whole image (the abstention upper bound); the answered zero therefore carries no usable
count information under asymmetric cost.* A value that cannot be distinguished, in cost, from throwing the
image away is not information about the count. This is stronger than "some difference is significantly
positive", which is only a numerical direction.

## 3 Numerical verification of the identity

| r | decision units | units with difference exactly 0 | max absolute difference |
|---|---:|---:|---:|
| 1 | 10 | **10/10** | 0.000e+00 |
| 2 | 10 | **10/10** | 0.000e+00 |
| 5 | 10 | **10/10** | 0.000e+00 |
| 10 | 10 | **10/10** | 0.000e+00 |

The units are the ten `(domain x family)` pairs on the paired reading; the measured difference is
**0.000000000**. The wider reading, which also admits unpaired items, likewise gives a maximum absolute
difference of 0.0000 with 10 of 10 units at zero for every `r`.

## 4 The secondary E5 reading: booking the abstention as an over-count

Under that alternative booking the per-item difference is `(r-1)*gt_i`, so the cell difference is positive
by construction whenever the cell contains an answered zero. It is reported as a comparison quantity, not
as a finding.

| r | units | units with difference > 0 | median difference | range |
|---|---:|---:|---:|---|
| 1 | 10 | 0/10 | 0.000000 | [0.000000, 0.000000] |
| 2 | 10 | **7/10** | **0.171694** | [0.000000, 0.268610] |
| 5 | 10 | **7/10** | 0.686775 | [0.000000, 1.074441] |
| 10 | 10 | **7/10** | 1.545243 | [0.000000, 2.417492] |

At `r = 2` the median difference is **+0.171694**, seven of the ten units are positive, and the bootstrap
interval over those units excludes zero. The three units that do not move are those containing no answered
zero, where the quantity is undefined rather than zero.

## 5 E1: does asymmetry change which arm is best?

The decision-relevant question is whether the arm that is optimal under the asymmetric cost differs from
the arm that is optimal under mean absolute error. The frozen criterion asks for a change in **more than
half** of the decision units. On the ten paired units (6,712 items):

| r | units with a changed best arm | ratio | Wilson 95% | cost-optimal differs from MAE-optimal | median overpayment of the MAE-chosen arm |
|---|---:|---:|---|---:|---:|
| 1 | 0/10 | 0.0000 | [0.0000, 0.2775] | 0/10 | 0.00% |
| 2 | **5/10** | **0.5000** | [0.2366, 0.7634] | 5/10 | 34.25% |
| 5 | **8/10** | **0.8000** | [0.4902, 0.9433] | 8/10 | **23.53%** |
| 10 | **8/10** | **0.8000** | [0.4902, 0.9433] | 8/10 | **62.01%** |

**The negative result.** At `r = 2` the count is **5 of 10 = 0.5000**, which sits exactly on the threshold
and therefore **does not clear it**. The smallest asymmetry tested is not enough to change the best arm in
more than half of the units, and the criterion is missed by exactly the margin that a strict reading of
"more than half" implies. This is reported as a negative result rather than rounded up.

**The positive result.** At `r = 5` and `r = 10` the count is **8 of 10 = 0.8000** with the Wilson interval
`[0.4902, 0.9433]`, so the criterion is met at both, and the same counts hold for the difference between
the cost-optimal and error-optimal arm. Choosing the arm by mean absolute error and then paying the
asymmetric cost overpays at the median by **+23.5%** at `r = 5` and **+62.0%** at `r = 10`.

## 6 The answered-zero channel: how thin the base is

In the local-arm sources that carry an explicit abstention flag, **every** row with `pred = 0` also carries
the flag set, so the number of records in which a genuinely answered zero was used as an estimate of zero
is **zero** there. The only sources in which zero-valued rows appear without the flag are a family whose
flag is not set for numeric base-arm output, which cannot distinguish "the model estimated zero" from "the
refusal was not annotated"; that family is used as supporting material only and its base is thin. The
identity in section 2 does not depend on that base, because it is algebra; the empirical claim that such
rows occur in practice does.

## 7 Not computed here

* No variance analysis or significance test over service starts: the experiment has no service-start
  replication of its own.
* No pooled answer-zero count across families.
* No precision on a true-zero-only pool, where it is 1 by construction.

## 8 Recomputing

`cost_asymmetry.py --selftest` runs hand-computed bit-exact assertions plus negative cases that must raise
an input error rather than silently returning zero. `cost_asymmetry.py --all --outdir <dir>` re-derives
every number above from the released per-item records into `<dir>`. The driver makes no model call and
needs no GPU.
