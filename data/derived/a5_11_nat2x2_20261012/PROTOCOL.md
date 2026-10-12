# Protocol - the same four contracts on a natural-image pool

**Question.** Is the outlet result a property of the rendered stimulus distribution, or of the contract?

**Design.** The four contract texts used on the rendered 2x2 pool are re-served unchanged on a
natural-image pool, so the only variable between the two columns is the corpus domain. The contract texts
are released in both directories, and the byte equality is checked by md5.

**Scale.** Three builds x four conditions = **12 cells** over **518** natural images, of which **259** are
true-zero and **259** non-zero. The pool name records a quota of 600; its realised size is 518 and it is
never rounded.

**Frozen conventions.**
* Only rows with HTTP **200** enter a numerator or a denominator.
* The true-zero roster is the pool's own `contracts/target_map_<condition>.csv`, read image by image for
  `true_zero == 1`; the records carry no such field.
* **Answered zero** is `is_zero is True`.
* Cell denominator is **259** true-zero images.
* Because the two domains have different denominators, the comparison of record is the rate difference in
  percentage points; count differences are a secondary, rescaled figure.
* Where a row satisfies both `pred == 0` and `abstain == True`, the inclusive reading is used and the
  alternative is printed beside it.
