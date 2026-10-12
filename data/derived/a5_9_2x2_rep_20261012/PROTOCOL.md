# Protocol - repeated service starts on a 2x2 contract design

**Design.** Two binary factors are crossed, giving four conditions and nothing else: factor A names the
value zero (`name0`) or never mentions it (`no_name0`); factor B offers an abstention outlet (`exit`) or
does not (`no_exit`). The four conditions of one build share a single service start.

**Scale.** Three builds x four conditions x **three independent service starts** = **36 cells**, each of
**200** images, of which **100** are true-zero images. The image set is identical across the three starts
of a cell, so the starts are repeats of the same measurement.

**Frozen conventions.**
* Only rows with HTTP **200** enter a numerator or a denominator; non-200 rows are excluded.
* One vote per image: an image contributes once per cell.
* **Answered zero** is `is_zero is True`, which on these records is identical to `pred == 0`.
* The true-zero roster is the **frozen contract** `contracts/target_map_<condition>.csv`, read image by
  image for `true_zero == 1`; the record files carry no such field.
* Cell denominator is **100** true-zero images.
* Image-level bootstrap: average the three starts per image, resample images, `n_boot = 2000`,
  `LB = out[int(0.05*N)]`, `UB = out[int(0.95*N)]`, seed **20261011**.
* Wilson bounds are one-sided with `z = 1.6448536269514722`, on the mean count out of 100.
* Separation criterion: `UB(no_name0_exit) < LB(no_name0_no_exit)`.
