# Protocol - true-zero detection on two all-true-zero pools

**Question.** How often does each build answer zero when the target is genuinely absent?

**Pools.** A 148-image pool (all true zero) and a 299-image pool (all true zero), each measured in a single
service start on the base arm. The larger pool's name records a quota of 300; its realised size is 299.

**Frozen conventions.**
* Only rows with HTTP **200** enter a numerator or a denominator.
* **Answered zero** is `is_zero is True`, measured identical to `pred == 0` on all 1,196 rows.
* Detection rate = answered-zero count / true-zero image count.
* Wilson upper bound is one-sided with `z = 1.6448536269514722`.
* The two pools are never merged and their rates are never averaged.
* Whenever the rate for the lowest build is quoted, the unparseable-row count is quoted with it, and the
  rate inside parseable rows is given as the second reading.
