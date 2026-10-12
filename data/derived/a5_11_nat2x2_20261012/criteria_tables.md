# The same four contracts on a natural-image pool - criteria tables

The rendered 2x2 experiment serves its stimuli from a synthetic renderer. This file reports the same
four contracts re-served on **natural images**, and compares the two domains directly.

## 1 The contracts are byte-identical across the two domains

| condition | rendered-pool contract md5 | natural-pool contract md5 | identical |
|---|---|---|---|
| `no_name0_no_exit` | `a7f75469c636c3b3e3a3d23e4841f171` | `a7f75469c636c3b3e3a3d23e4841f171` | yes |
| `no_name0_exit` | `3afc29d16a331d75419653252d5ed830` | `3afc29d16a331d75419653252d5ed830` | yes |
| `name0_no_exit` | `623dbea85a1e8cbb26f58ff1271c00dc` | `623dbea85a1e8cbb26f58ff1271c00dc` | yes |
| `name0_exit` | `524bb5645301855a237d3ce70b669b66` | `524bb5645301855a237d3ce70b669b66` | yes |

Both copies of each contract text are released - the rendered copies and the natural copies - so the
equality can be checked with a single `md5sum` over the two files. The fixed-sentence and
variable-sentence files are also byte-identical across the two domains. The per-image
`target_map_<condition>.csv` files necessarily differ, because the images and the target words differ;
they are instantiations of the same four contract texts. **The only variable between the two columns
in section 3 is therefore the corpus domain**, with the prompt text, the contract, the output format
and the scoring conventions held fixed.

## 2 The natural pool is 518 images (259 + 259), not 600

The pool holds **518** images: **259** true-zero and **259** non-zero, an exact balance. It is not a
truncated 600-image quota; it is the pool that the quota constraint admits (nine natural target words,
`test_coco` 250 plus `val_coco` 268). The rendered pool has 300 true-zero images and the natural pool
has 259, so the denominators differ and the comparison of record is the **rate difference in
percentage points**; count differences are given only as a rescaled secondary figure.

## 3 Cross-domain counts and rates

| build | condition | rendered: count | rate | natural: count | rate | rate difference (pp) |
|---|---|---:|---:|---:|---:|---:|
| InternVL3.5-8B | `no_name0_no_exit` | 249 | 83.0% | 198 | 76.4% | -6.6 |
| InternVL3.5-8B | `no_name0_exit` | 0 | 0.0% | 0 | 0.0% | +0.0 |
| InternVL3.5-8B | `name0_no_exit` | 299 | 99.7% | 244 | 94.2% | -5.5 |
| InternVL3.5-8B | `name0_exit` | 28 | 9.3% | 53 | 20.5% | +11.1 |
| llava-onevision-7B | `no_name0_no_exit` | 162 | 54.0% | 83 | 32.0% | -22.0 |
| llava-onevision-7B | `no_name0_exit` | 3 | 1.0% | 6 | 2.3% | +1.3 |
| llava-onevision-7B | `name0_no_exit` | 207 | 69.0% | 91 | 35.1% | -33.9 |
| llava-onevision-7B | `name0_exit` | 30 | 10.0% | 21 | 8.1% | -1.9 |
| Qwen3-VL-32B-FP8 | `no_name0_no_exit` | 300 | 100.0% | 259 | 100.0% | +0.0 |
| Qwen3-VL-32B-FP8 | `no_name0_exit` | 290 | 96.7% | 109 | 42.1% | -54.6 |
| Qwen3-VL-32B-FP8 | `name0_no_exit` | 300 | 100.0% | 259 | 100.0% | +0.0 |
| Qwen3-VL-32B-FP8 | `name0_exit` | 300 | 100.0% | 258 | 99.6% | -0.4 |

## 4 The outlet direction is the same in both domains

| build | rendered `no_name0_no_exit` -> `no_name0_exit` | natural `no_name0_no_exit` -> `no_name0_exit` | same direction |
|---|---|---|---|
| InternVL3.5-8B | 249 -> 0 | 198 -> 0 | yes |
| llava-onevision-7B | 162 -> 3 | 83 -> 6 | yes |
| Qwen3-VL-32B-FP8 | 300 -> 290 | 259 -> 109 | yes |

Every one of the six domain-by-build combinations falls, so the **sign** of the outlet effect is not a
property of the rendered distribution. The **magnitude** is a different matter; section 6 reports the
case where the two domains disagree most.

## 5 The naming direction

| build | outlet level | rendered change | natural change | same direction |
|---|---|---:|---:|---|
| InternVL3.5-8B | no outlet | +50 | +46 | yes |
| InternVL3.5-8B | outlet offered | +28 | +53 | yes |
| llava-onevision-7B | no outlet | +45 | +8 | yes |
| llava-onevision-7B | outlet offered | +27 | +15 | yes |
| Qwen3-VL-32B-FP8 | no outlet | +0 | +0 | yes |
| Qwen3-VL-32B-FP8 | outlet offered | +10 | +149 | yes |

All **6 of 6** pairs move the same way, so naming zero and offering an outlet are separable in both
domains, not only in the rendered one.

## 6 A negative result: the 32B near-immunity does not survive the domain change

The rendered pool makes `q32fp8` the least responsive of the builds: **300 -> 290**, a drop of **10**
with **96.7%** retained and a rate difference of **-3.3 pp**. Read alone, that row invites the summary
that a 32B build is immune to the outlet. The natural pool moves the same build **259 -> 109**, a drop
of **150** with **42.1%** retained and a rate difference of **-57.9 pp**.

| domain | true-zero images | `no_name0_no_exit` | `no_name0_exit` | change | retained | rate difference |
|---|---:|---:|---:|---:|---:|---:|
| rendered | 300 | 300 | 290 | -10 | 96.7% | -3.3 pp |
| natural | 259 | 259 | 109 | **-150** | **42.1%** | **-57.9 pp** |

The rate difference grows from **-3.3 pp** to **-57.9 pp**, so the effect on the natural pool is
roughly **13 times** the effect on the rendered pool for this build. The direction is preserved; the
magnitude and the immunity are not.

**The conclusion this licenses.** Outlet suppression is **strong in most builds**, and **its strength
varies with the model and with the corpus domain**. No statement that a particular build or scale is
immune to the outlet is supported, and no extrapolation from the rendered pool to a natural one is
supported. What survives is the sign: offering an outlet lowers the answered-zero count in 6 of 6
builds on rendered stimuli and in 3 of 3 builds here, and it is the **size** of that lowering that must
be quoted with the build and the domain that produced it.

## 7 One row carries a double annotation

In the natural pool the `lov7b` `no_name0_exit` cell contains **one** row with both `pred == 0` and
`abstain == True`. Counting it as an answered zero gives **6**; excluding it gives **5**. Both readings
are printed here, and section 3 uses the inclusive reading (**6**), matching the convention stated for
all the 2x2 tables. The other eleven cells of section 3 are identical under the two readings.

The natural-domain `lov7b` column also sits far below its rendered counterpart (**32.0%** against
**54.0%** on the `no_name0_no_exit` cell), and that cell has **122 of 259** rows (**47.1%**) whose
output cannot be parsed into a number. Under the double reading of the sibling directory
`a5_10_zero300_20261012`, the strict rate of 32.0% corresponds to **60.6%** inside parseable rows.
The gap between the two domains is therefore a joint effect of the model and the corpus, and it cannot
be attributed to the corpus alone.

## 8 Recomputing

`recount.py` reads `raw/`, `pool/` and `contracts/` only and prints every number in this file; run it
from this directory with `python recount.py`.
