# Protocol - asymmetric cost and the value of an answered zero

**Question.** When under-counting and over-counting are priced differently, does the best action change,
and what is an answered zero worth?

**Cost.** `C_r(cell) = [ c_u*sum_i max(gt_i - pred_i, 0) + c_o*sum_i max(pred_i - gt_i, 0) ] / sum_i gt_i`,
with `c_o = 1` and `r = c_u/c_o` in `{1, 2, 5, 10}`. `sum_i gt_i` is the frozen denominator: not `abs(gt)`
and not the item count. At `r = 1` the numerator is exactly `sum_i abs(pred_i - gt_i)`, so
`C_1 = (n / sum gt) * MAE`.

**Strategies compared for an answered zero.**
* `P0` - `pred` as it stands.
* `P2` - `pred` as it stands, with `pred_i = 0` read as an estimate of zero.
* `P1` (**frozen**) - `pred_i = 0` means the image does not enter the automatic decision and goes to a
  human, priced at `c_u*gt_i`, our own declared upper bound ("missed whole image"). A sensitivity reading
  that drops those items from the denominator instead is recorded separately and is not interchangeable
  with the frozen one.

**Decision units.** A `(domain x family)` pair; an arm is a candidate action inside it. The primary
reading is **paired**: only items that every arm parses successfully. The secondary reading is **full** and
unpaired. Non-numeric `pred` is excluded identically from all strategies.

**No model call, no GPU, no network.** The driver reads the released per-item records only.
