# Supplementary Material

**Abstention dominates the aggregate under-count on dense scenes: signed error direction in object
counting with vision-language models**

> This file contains the methodological detail whose conclusions are stated in the main text.
> **Appendix Z** states the move convention, where the review requests below came from, and the
> corrections log.

**Where things are.** **A** conventions, metrics and statistical protocol; **B** abstention; **C** legibility;
**D** datasets; **E** detection ladders; **F** the spectrum, its deflations and intervals; **G–I** corpus
construction and hygiene; **J** proofs (Propositions 4–8); **K** detector-failure controls; **L**
per-property numbers; **M** hypotheses, pre-registered criteria and census grids; **Z** provenance and
corrections.

> **Where a review request came from** — the generative-AI declaration it belongs to, and the fact that
> **no review by this journal has taken place and the manuscript has not been submitted before** — is
> stated once in **Appendix Z**.

---

## Appendix A. Conventions, metrics and statistical protocol

### A.1 Metric definitions

Magnitude metrics are MAE, RMSE, normalised MAE, and tolerance-based scores
($\text{tol} \le 1$, exact match, $P(\text{over})$). The signed relative deviation is

$$\rho \;=\; \frac{\overline{\text{pred}} - \overline{\text{gt}}}{\overline{\text{gt}}}
\quad\text{(in percent, signed),}$$

computed under two sub-conventions: the **pooled ratio** (means taken separately in numerator and
denominator) and the **per-image ratio mean**. The main text's definition of $\rho$ and Proposition 2
state their relation. An anomalous-prediction rule applies throughout: records with `pred ≥ 1e5`, and the
exact sentinel value 1234567890, are removed before any rate is computed (Appendix I).

Density is summarised by **OPM**, objects per megapixel; §7.1 gives its applicability boundary.

### A.2 Statistical protocol

Bootstrap with 10,000 resamples under block resampling by image; paired Wilcoxon tests; Holm
correction for multiplicity. Where a per-cell span is reported, the bootstrap interval resamples
images, which **under-states** the uncertainty contributed by the small number of levels within a
cell; the intervals are therefore lower bounds on uncertainty rather than calibrated coverage
statements.

### A.3 Non-determinism and the noise band

Aggregate and per-image stability differ sharply, and we declare this rather than discover it. With
temperature 0 under 4-bit AWQ, the per-image disagreement rate is **22–27%**, while the aggregate change
in ME stays within **0.19** counts. Magnitude and direction conclusions at the aggregate level are
therefore robust, whereas per-image conclusions must be read against the noise band. For a hosted API,
item-level reproducibility falls to roughly **15%**, whereas a locally controlled stack at batch ≤ 2
agrees at essentially 100% for the same configuration. The per-image figure above covers **both** kinds of
movement, and the paper's rates depend on only one of them. Separating them on the four M.21.10 builds
across **three fresh service starts at four-worker concurrency**, the **answered-zero classification**
flips on **4 of 4,136 items (0.097%)**, while the reported count differs by **±1–2 on 4.28%** of items.
(The per-item records behind this split are those of §M.21.10 and are in the released package, in the released per-item record directory listed in `MANIFEST.csv`.)
The two settings are not comparable — the 22–27% above is a 4-bit stack and counts value differences as
well — so this is a **boundary on a different setting, not a correction of that figure**. Consequently,
model-to-model differences below
**7 pp** are treated as indistinguishable throughout, and one difference that flips under repetition is
not reported at all. The noise floor is the **across-repeat standard deviation of $\rho$** for a fixed configuration on a hosted
endpoint — computed from the repeated runs of `ds_repeat.py`, whose item-level agreement is the ≈**15%**
above — and is **2.15–6.46 pp** across cells; §7.3 uses it as such.

**Can the band be re-measured on the local stack the main tables use?** We re-ran the **same instrument**
(`ds_repeat.py`, unchanged) with its endpoint pointed at the locally served AWQ-4-bit build, on **seven**
120-item cells drawn from the corpora already in the released package (VisDrone, AI-TOD, ShanghaiTech-A,
UCF-QNRF, MTDC), **five independent repeats** each. The counts are complete (5 repeats \times 120 items per
cell) and the per-cell standard deviations are small: **0.00–0.63 pp** on the pooled relative deviation (up to
**1.32 pp** on the answered-only variant). **We do not adopt that as the noise floor — the conservative
choice.** On these cells the model **saturates**: the pooled deviation averages **−57% to −100%** because it
answers zero for essentially every item (on MTDC the answered-only deviation is undefined in **all five**
repeats), so a small standard deviation is partly a statement about **how little the answer changes**; the
quantity is better read as a **lower bound** than as a floor. The informative comparison is a cell that is
**not** saturated: in the synthetic-grid cell of Appendix J.8, re-running with the render seed held **fixed**
moved the largest single-cell under-count by **2.47 pp** — **inside** the 2.15–6.46 pp band above. We
therefore keep the hosted-endpoint band, which is the **wider (hence more conservative)** of the two, and
record the local attempt here so that the borrowing is **disclosed rather than implicit**.

---

### A.4 Detail for §2.7 (evaluation validity)

We therefore treat model-to-model
differences below **7 pp** as indistinguishable and decline to report one difference that flips under
repetition (Appendix A.3).

### A.5 Per-level mean/median note

A curve drawn through per-level medians can
therefore differ from the scatter of per-image values by more than the effects being discussed, so
per-level medians are always shown with their interquartile spreads.

### A.6 Note on cascade errors

We use
such a decomposition explicitly as a **definitional identity** ($\delta_U = \delta_T - \delta_H$,
verified exactly per image, §4.7), and warn against treating it as an empirical finding: any two of the
three quantities determine the third.

## Appendix B. Abstention: full operationalisation

### B.1 The five mutually exclusive classes

For every record we read both the pipeline's declared columns (`zero`, `refuse`, `abstain`, `error`) and
values re-derived from `pred`, `parse_ok` and `raw`, then assign exactly one class:

| Class | Criterion | Meaning |
|---|---|---|
| `normal` | `parse_ok = 1` and `pred > 0` | Normal answer |
| `answer_zero` | `parse_ok = 1` and `pred = 0` | **The abstention body of this paper** |
| `refuse` | declared `refuse = 1`, or `parse_ok = 0` with a natural-language refusal in `raw` | **Textual refusal** |
| `format_drift` | a response that is neither a number nor a refusal | Format drift |
| `api_error` | HTTP 4xx/5xx, timeout, or insufficient balance in `raw`/`error` | Service failure, **excluded from the denominator** |

The five classes sum to $n$ by construction. Records whose declared and derived values disagree — 238
across the entire corpus — are counted separately and inspected by hand rather than resolved by rule.

### B.2 De-duplication protocol

**File level.** The corpus contains byte-identical mirrors: the same result appears under several
harvest directories. Files are de-duplicated by MD5.

**Row level.** Rows are de-duplicated by **identity of the experimental condition**, not by item,
because the prompt-dose experiment places **the same item at seven strength levels inside a single
file**; item-level de-duplication would compress seven conditions into one row and destroy the design.
The identity is `all columns except the outcome columns`, and when merging we keep the row with
`parse_ok = 1`.

**Tiled rows.** For tiled experiments a single row's `raw` field is a **concatenation of per-tile
answers** (`{"count": a} | {"count": b} | …`). These are parsed per tile and summed; failing to do so
misclassifies the entire row as format drift (Appendix Z).

### B.3 Encoding differences between lineages

In certain file families the column layout differs: `parse_ok` is always 1 and there is no `refuse`
column, and the two lineages encode abstention differently — **Qwen writes `pred = "0"`, InternVL
writes `pred = ""` (empty string)**. We therefore adopt the unified criterion "**`pred` is not a
positive number ⇒ abstention**", which is inconsistent in **zero of 15** files carrying an `abstain`
column. Judging by `pred = "0"` alone would **report InternVL's abstention rate as 0.0%**; the true
values are ShanghaiTech-A **21.4%**, ShanghaiTech-B 0.0%, UCF **28.4%**, AI-TOD **47.8%** and VisDrone
**50.2%**. Note also that answered zeros on sparse images with GT = 1 are mostly **genuine misses**
rather than abstentions, which is why abstention rates are always discussed stratified by GT.

### B.4 The natural-language refusals, verbatim

The refusals are not distributed uniformly across prompt families. They concentrate on prompts that
demand per-instance enumeration; the wording itself names the reason:

> "cannot be counted precisely; the crowd in the image is dense, and individual heads/bodies cannot be
> located one by one."
> "cannot be counted precisely; the crowd is overly dense and partly occluded; the estimated number is
> in the thousands."

Under all prompt families that permit an overall estimate, the explicit refusal count is zero.

### B.5 Scope of the identification argument

The lineage stratification uses the whole corpus. The corpus-wide **global**
answered-zero-to-refusal ratio is **12.1 : 1**, with format drift at about
**1.9%**, for two reasons: the corpus gained a large number of InternVL results, whose refusal
rate is markedly higher, and a global ratio computed without parsing the multi-tile `raw` of tiled
experiments is biased low. **The two lineage-stratified conclusions of §3.6(c) are unaffected**,
because they are the product of the per-lineage re-computation rather than of any global ratio.
The superseded global figures are listed in Appendix Z.

---

## Appendix C. The legibility proxy in full

### C.1 Definition

For each instance $i$, take $a_i$, the number of pixels inside its annotation box that are **not
covered by another instance's box**; the image-level proxy is the median over instances,
$p = \operatorname{median}_i a_i$, in pixels per instance. The proxy requires instance-level boxes,
which is what makes it a diagnostic rather than a deployment-time decision rule.

### C.2 The three factors and their unequal effects

The construct has three directly manipulable factors: **instance size** (scale factor or fixed short
side), **blur** $\sigma$ (a degradation mode decoupled from resolution), and **overlap** (arrangement
on a synthetic grid at fixed size and blur, varying only spacing and packing). Their effect sizes are
not equal. Holding the image and the frames fixed and changing only the degradation mode, downscaling
to 15% of the pixels still produces almost no abstention (**0.6%**), whereas blurring the *same* image
and frames produces **9.1%** — a difference of **+8.6 pp** under paired comparison ($n = 900$). Blur is
therefore the strongest single gate, and the per-instance pixel budget is a **covariate**: informative
within a domain (blur and px/obj correlate strongly there), but at fixed scale it co-varies with the
number of instances per image, and across the aerial and microscopy domains the two decouple.

### C.3 Why we do not use attention or confidence

Recent mechanistic work shows that attention sharpness is very nearly uninformative about correctness
($R \approx 0.001$). A legibility criterion built on attention would therefore have no grounding, and
ours is computed from images and annotations only.

---

### C.4 Aerial contract-effect detail for §5.10

Lowering the pixel budget raises abstention monotonically in both lineages: InternVL **41.5% → 54.5%**,
Qwen **59.5% → 72.5%**. The "forbid 0" instruction works only partly for Qwen (**59.5% → 45.5%**) and
hardly at all for InternVL (**41.5% → 40.0%**).

## Appendix D. Implementations, fairness and the dataset table

### D.1 Implementations

**Detection.** YOLOv12n with nine variants plus budget × source-domain combinations; for the dense end,
zero-shot COCO person detectors under a tiling protocol; two label conventions (original and cleaned).
A structurally different detector family — Faster R-CNN, and RetinaNet for the tiling ladder — is used
to separate implementation effects from paradigm effects.

**Vision-language models.** Qwen3-VL-32B-Instruct, primarily through a self-hosted 4-bit AWQ stack and
cross-checked against a BF16 hosted API, with an 8B scale control, a Qwen2.5-VL-7B generation control,
and InternVL2.5-8B as a second lineage. Three directional arms (base/over/under) use **byte-identical
prompts across datasets**; the prompt texts are released verbatim with the reproduction package (`code/analysis/p1d_prompts.json`, `p1e_prompts.json`, `p1f_prompts.json`).

**Density regression.** BL, CSRNet and DM-Count trained on SFCHD; public in-domain weights for the dense
end. Where a reproduction is used instead of official code this is marked explicitly, and the
corresponding span figures are reported under the official weights as well.

### D.2 Fairness statement

| Family | Pretraining source | Capacity | Input scale | Notes |
|---|---|---|---|---|
| Detection | COCO and in-domain (VisDrone) | 2.6 M–37 M parameters (YOLOv12n family); RetinaNet R50 | 640 / 1024 / 1280 / 1536 short side | both zero-shot and in-domain weights reported |
| Density regression | ImageNet classification (VGG-16 backbone) | 16.3 M | fixed short side and multiplicative scale ladders | official and reproduction weights reported separately |
| VLM | Qwen3-VL and InternVL2.5 lineages | 7 B / 8 B / 32 B | whole image, tiled (2×2…6×6), pixel budgets | same prompts across datasets by construction |

### D.3 Dataset table

| Dataset | $n$ | Mean targets/image | OPM median | Instance state | Role |
|---|---|---|---|---|---|
| SFCHD | 12,066 | 1.45 | 1.11 | Large, clear | Sparse primary benchmark |
| ShanghaiTech-B test | 316 | 123.8 | 118.3 | Medium, partly occluded | Medium density |
| UCF-QNRF test | 334 | 718.9 | 96.3 | Small, densely overlapping | High density, large images |
| ShanghaiTech-A test | 182 | 433.3 | 784.7 | Very small, severe overlap | Very high density |
| CountBench | 491 | 6.04 | 31.1 | Large, clear | VLM-native benchmark |
| TallyQA | 498 | 8.2 | 48.0 | Large, clear | External validity |
| FSC-147 | 600 | 80.8 | ~180 | Medium, class-agnostic | External validity; the 600 are a fixed-seed, GT-stratified sample drawn from the release's full **6,146**-image annotation file rather than from a split (realized: 332 train / 134 val / 134 test), while §5.13 uses a separate fixed-seed, GT-stratified sample of **300** of the official **1,190**-image test split |
| VisDrone (person) | 400 | 22.4 | — | Very small, low contrast | Aerial extreme |
| AI-TOD (person) | 226 | 17.0 | — | Very small, near-indistinguishable | Aerial extreme |

---

### D.4 Figure and table plan for §3.9

The remaining figures — per-cell
detection ladders, per-level saturation curves, the contract prediction distribution, the cross-implementation
knob curves and the scale-invariance panels — are provided in the supplementary file, as are the per-cell
tables referenced from Appendices E–G. Table 1 is the numerosity-stimulus comparison of §2.4; the lineage-stratified abstention table of §3.6 is Table 2.

Main-text figure list (the pointer of §3.9): **Fig. 1** tiling removes the abstention; **Fig. 2** the prompt-strength dose–response; **Fig. 3** the threshold-cleaning curve that separates reachable from unreachable levels; **Fig. 4** the four-panel separation of the two failure modes. All tables are supplied as editable text with no
vertical rules and no shading.

## Appendix E. Detection ladders in full

### E.1 The fine $\tau$ ladder in full

**Protocol, and which bootstrap applies where.** All four tables scan the same grid — $\tau$ from 0.02 to
0.90 in steps of 0.005 (**177 points**), with the zero crossing located by linear interpolation between
adjacent grid points and NMS IoU 0.7 unless a row says otherwise (RetinaNet fixes IoU 0.5 inside its own
NMS). The bootstrap that produces the 95% interval of $\tau^\*$ differs by scan and is stated where it
applies: **4,000×** image resampling for **E.1–E.2** — the fine ladder of §4.3 and its knob series — and
**3,000×** for the tiling ladders **E.3–E.4**. The density-bin refinement of §4.2 is a separate scan on the
same step size with a **10,000×** image-resampling bootstrap (its per-bin numbers are in Appendix M.9);
the three counts are not interchangeable, and a $\tau^\*$ quoted without its scan is not reproducible.

| Input regime | Domain (mean GT) | min $\lvert$ME$\rvert$ | $\tau^\*$ | 95% CI | Reachable |
|---|---|---|---|---|---|
| Whole image | SFCHD test (1.4) | 0.0 | **0.259** | [0.236, 0.277] | yes |
| Whole image | ShanghaiTech-B (123.8) | 0.2 | **0.130** | [0.118, 0.144] | yes |
| Whole image | **ShanghaiTech-A (433.3)** | **140.9** | — | — | **no** (100% bootstrap-unreachable) |
| Whole image | **UCF-QNRF (718.9)** | **543.1** | — | — | **no** (100%) |
| Tiled 1024 | UCF-QNRF (718.9) | 1.9 | **0.131** | [0.105, 0.162] | yes |
| Tiled 1024 | **ShanghaiTech-A (433.3)** | **141.1** | — | — | **no** (100%) |


### E.2 NMS IoU and input scale

| NMS IoU | $\tau^\*$ | 95% CI |
|---|---|---|
| 0.5 | **0.038** | [0.027, 0.054] |
| 0.6 | **0.073** | [0.055, 0.097] |
| 0.7 | **0.121** | [0.099, 0.148] |

The second half of the same knife, on the same configurations (UCF-QNRF, tile-1024, NMS IoU 0.7) — this is
the series §4.4 quotes:

| Input scale (short side) | min $\lvert$ME$\rvert$ | $\tau^\*$ | 95% CI |
|---|---|---|---|
| 640 | 4.4 | **0.117** | [0.096, 0.139] |
| 1024 | 2.2 | **0.121** | [0.099, 0.148] |
| 1280 | 1.9 | **0.131** | [0.105, 0.162] |

Both knobs are real, and they are not the same size: over the widest range measured here, NMS IoU moves
$\tau^\*$ by **0.083** (0.038 to 0.121) while the input scale moves it by **0.014** (0.117 to 0.131) — the
IoU knob is about six times the stronger of the two. That asymmetry is why §4.4 reports IoU as the second
knob and the input scale as a third, weaker one.


### E.3 The two-family tiling ladder

| Family | Dataset | Whole | tile-1024 | tile-512 | tile-256 |
|---|---|---|---|---|---|
| YOLO | UCF-QNRF | — | **0.121** | **0.176** | **0.173** |
| YOLO | **ShanghaiTech-A** | — | **no** (min $\lvert$ME$\rvert$ **141.1**) | **0.260** | **0.183** |
| YOLO | ShanghaiTech-B | — | 0.128 | 0.420 | 0.240 |
| RetinaNet | **UCF-QNRF** | **no** (**531.2**) | **0.124** | 0.225 | 0.306 |
| RetinaNet | **ShanghaiTech-A** | **no** (**244.3**) | **no** (**244.3**) | **0.124** | 0.237 |
| RetinaNet | ShanghaiTech-B | 0.060 | 0.060 | 0.278 | 0.376 |


### E.4 Monotonicity of $\tau^\*$ under finer tiling

| Dataset | Family | tile-1024 | tile-512 | tile-256 | Trend |
|---|---|---|---|---|---|
| UCF-QNRF | YOLO | 0.121 | 0.176 | 0.173 | **non-monotone** |
| UCF-QNRF | RetinaNet | 0.124 | 0.225 | 0.306 | monotone increasing |
| ShanghaiTech-A | YOLO | unreachable | 0.260 | 0.183 | **non-monotone** |
| ShanghaiTech-A | RetinaNet | unreachable | 0.124 | 0.237 | monotone increasing |


### E.5 The two zeros, by source-domain weights

| Source-domain weights | $\tau^\*(\delta_U = 0)$ (95% CI) | $\tau^\*(\delta_T = 0)$ (95% CI) |
|---|---|---|
| Fusion (in-domain) | **0.1106** [0.1004, 0.1205] | **0.2347** [0.2258, 0.2440] |
| COCO-pretrained | **0.0980** [0.0872, 0.1122] | **0.2236** [0.2159, 0.2317] |
| SHWD-pretrained | **0.1048** [0.0921, 0.1186] | **0.2142** [0.2059, 0.2226] |


---

### E.6 Non-monotonicity detail for §4.6

This is
one more instance of the paper's rule: **every entry in the response spectrum must be labelled with
{implementation × training domain × data domain × protocol}**, since generalising either family's trend
would be wrong.

## Appendix F. Span spectrum in full

### F.1 Same-scale accuracy across the three families

| Dataset | Detection (native 1024 tiling at $\tau^\*$) | VLM-32B (best tiling level) | Density regression (best weight) | Density regression (weight range) |
|---|---|---|---|---|
| ShanghaiTech-A | 220.5 | 201.7 (5×5) | **71.3** | 71.3–383.4 (**5.4×**) |
| UCF-QNRF | 287.3 | 284.3 (6×6) | **221.3** | 221.3–1240.1 (**5.6×**) |
| ShanghaiTech-B | 31.2 | 33.2 (3×3) | **9.8** | 9.8–133.4 (**13.6×**) |


### F.2 The six knobs, their sides, and their spans

| Family | Knob | Side | Pooled span | Zero-crossing units | Primary target |
|---|---|---|---|---|---|
| Detection / enumeration | threshold $\tau$ × input size | parameter side | **30.0–90.0 pp** | 3/4 | direction |
| Density regression | input scale (multiplier / fixed short side) | input-scale side | **20.1–34.3 pp** (official DM-Count) | 3/4 | direction |
| VLM | output contract (span over `forbid0`/`choice`/`range`; zero-crossing count over the six arms of Appendix M.18.1) | language side | **26.8–53.7 pp** | 6/6 | direction |
| VLM | prompt family (V1…V5) | language side | pooled **25–2008 pp** / per-item median **19–70 pp** | 12/15 pooled / 3–6/15 median | direction |
| VLM | tiling level | vision side | **1.9–28.6 pp** | 7/13 | abstention, secondarily direction |
| VLM | pixel budget | vision side | **4.0–14.6 pp** | 0/6 | abstention only |

**Reconciling the three unit sets.** The same knob's span appears at three different magnitudes in this
paper, and the differences are **unit set and calibration**, not disagreement. The table above reports
**one span per knob**, pooling that knob over its domains on the **uncalibrated** pooled relative deviation,
with the detector row flagged below (**the six rows are tabulated in `code/analysis/a39_disp4.py`**, whose
embedded table carries all six ranges and their per-domain breakdown; released with the package); §F.9 splits **four of the six** knobs into **ten (knob × domain) units**
and reports them **isotonic-calibrated**;
§M.37 rebuilds **36 configuration-level units** from the same per-item records, uncalibrated. For the two
knobs a reader is most likely to try to line up:

| unit set | output contract (VLM) | tiling level (VLM) |
|---|---|---|
| §F.2, one span per knob, uncalibrated | **26.8–53.7 pp** | **1.9–28.6 pp** |
| §F.9, one per (knob × domain) unit, isotonic | **85.9 / 97.7** (2 units) | not among the ten |
| §M.37, one per configuration unit, uncalibrated | **160.7 / 259.4** (2 units) | **32.9 / 40.0 / 40.5 / 61.6 / 114.6 / 260.4** (6 units) |

So for the output-contract knob the three rows differ by **3.0–9.7×**, and the §M.37 tiling units run from
32.9 to 260.4 pp around §F.2's 1.9–28.6 pp. The three are not competing measurements of one quantity: a §F.2
row is a range over the knob's domains, a §F.9 row is one calibrated unit, and a §M.37 row is one
configuration — and the largest tiling unit (**260.4**) is a **contract × tiling combination**, not a bare
tiling level. **Subtracting one row from another is the construction §F.10's caliber rule already
forbids.** The three sets agree on the **ordering**, which is the claim §7.3 makes; the reconciliation is a
recomputation over the printed tables (`span_caliber_reconcile.py`), not a transcription.

**Which of these sets is load-bearing.** §7.3 carries four unit counts — the **ten** (knob × domain)
units of §F.9, the **24** (knob × domain) units of the common-level-count re-estimation, the **31**
fully recomputable units at that same level count, and the **36** configuration units of §M.37, the
**six** knob rows above being the per-knob view — and they are four unit sets, not four competing
measurements; **the load-bearing ordering set is §M.37's recomputable 36 units**, every Spearman in
§7.3 is labelled with the unit set it was computed on, and the 10-, 24- and 31-unit readings are
supporting re-estimations of the same ordering rather than competing claims.

**The detector row.** The paragraph above reconciles **two of the six** rows; the detector knob needs
its own note rather than a third column, because its **30.0–90.0 pp** is a **calibrated** per-knob span
and not an uncalibrated one. The same three in-domain VisDrone ladders read **95.8–195.7 pp**
person-matched and **352.8–508.4 pp** all-detections on the **uncalibrated** pooled caliber (§F.10, at
640 / 1024 / 1536 px). Its per-unit counterparts are §F.9's three isotonic detection units — **49.0**
(in-domain BBBC005), **54.2** (zero-shot COCO) and **150.7** (in-domain VisDrone) pp — and the twelve
detector configuration units of §M.37, which run **16.4–204.9 pp** uncalibrated. The four readings are
four different unit sets — a per-knob pooled range, three single ladders, three (knob × domain) units
and twelve configuration units — and for this knob they do not share one caliber either, so **none of
them is a term-by-term counterpart of another** and no two may be subtracted: that is the construction
§F.10's caliber rule forbids, and it is why a magnitude is quoted together with its caliber. A reader
who wants this row's ordering evidence should use the recomputable per-unit set of §M.37, exactly as
§7.3 says for the spectrum as a whole.


### F.3 The split-point enumeration

| Split | Max upper bound, low group | Min lower bound, high group | Gap | Verdict |
|---|---|---|---|---|
| $k = 1$ (pixel budget / ShanghaiTech-A alone) | 4.2 | 4.5 | **+0.3 pp** | separated, but a single unit |
| **$k = 3$ (three pixel-budget units)** | **22.4** | **24.0** | **+1.6 pp** | **the only meaningful separation** |
| $k = 2, 4, 5, 6, 7, 8, 9$ | — | — | −5.4 to −81.0 pp | intervals overlap |

The ten units over which these splits are enumerated are listed with their spans and
half-sample-split intervals in **F.9**; the three that form the low group at $k = 3$ are the pixel-budget
units, and the remaining seven are the high group.

---

### F.4 Saturation-slope detail

For the clean 4× parameter pair the difference is
$\Delta b = +0.00124$, paired bootstrap 95% CI $[+0.00079, +0.00165]$, $p < 0.0001$, against a replication
baseline of $0.00012$ and $0.00001$ — a scale effect **10–124×** the baseline. Both split-half checks
reproduce the same sign and magnitude.

### F.5 Enumeration-versus-regression support for §7.8

The dense-end results here quantify why —
the density-regression family's scale freedom parameter and its weight-set spread (5.4–13.6×) together
dominate any directional difference between families, so a regression-style model must be calibrated per
domain before its direction can be compared at all.

### F.6 Reporting-norm recommendation detail

**Match the effective target scale** — comparisons at unmatched scale are not
comparisons. **Report the weight-set distribution** rather than a single number, since the same
architecture spans 5.4–13.6× across usable weights. **Report the abstention rate separately**, with its
own convention label, since without it a refusal is recorded as a small estimate. Where these are not
observed, the scale and weight nuisance parameters can each produce differences of **90–275 pp**, enough
to invert the ranking of the paradigms being compared.

### F.7 Statistical-structure arithmetic for §7.3

Only one split separates: three pixel-budget units with a maximum upper bound of **22.4 pp** against the
remaining seven with a minimum lower bound of **24.0 pp** — a gap of **1.6 pp**, permutation
$p \approx 0.008$ **before** any correction for the nine enumerated split points. The smallest attainable
corrected value is therefore $0.075$, which is not significant at this sample size, and the
1.6 pp gap is itself **below the paper's own noise floor of 2.15–6.46 pp**. Within the high-response
group **6 of 6 adjacent pairs overlap**.

**The ordering, with intervals.** On the same unit sets the ordering is *certified* rather than asserted: over
the **36** units at a common level count $k=3$ the Spearman between the two readings is **0.933** with a 95%
interval **0.834–0.984** from a **unit bootstrap of 2,000 draws** (`m37_ci_power.py`; frozen
`m37_ci_power_result.json`), and over the **31** fully
recomputable units at $k=4$ it is
**0.983** (**0.943–0.996**). Both are the **smallest of the three endpoint rules**, whose three values M.37
prints in full (0.933 / 0.947 / 0.983 at $k=3$; 0.983 / 0.987 / 0.983 at $k=4$), and the frozen
`equalcount36_result.json` carries both the three values and this minimum; a label-permutation test gives $p<5\times10^{-5}$, and on the same **36** units
dropping any single one of the **six** knobs **whole** — the detector-threshold block (12 units), density
regression (4), output contract (2), pixel budget (6), prompt family (6) and tiling (6) — leaves
**0.883–0.970**. That reading is recomputed from the released `equalcount36_result.json`; the frozen
`m37_ci_power_result.json` stores the same quantity over the **nine** name-parsed subgroups instead, whose
`n_dropped` (2/6/6/6/2/2/4/4/3) never removes the detector block whole and leaves one unit un-dropped — the
two agree because the interval's two ends are two of the six knobs. The **31**-unit set above carries no
leave-one-out reading, and `m37_ci_power.py` is the generator of the frozen field only.

**The intervals do not depend on treating the units as independent.** The units are nested in six knobs, so we re-ran the resampling at the **cluster** level: resampling whole knobs with replacement gives a 95% interval of **0.913–0.994** over the **31** unit set (2,000 draws, seed 20260924), against **0.943–0.996** under the unit bootstrap printed above — a lower bound **2.6 pp** below the i.i.d. one and still well above the **0.80** bar this paper would have read as instability (F.10). The same substitution on the **36** unit set gives **0.711–0.998** (the 36-unit clustered reading stored in the frozen clustered result file released with this appendix, 2,000 draws, seed 20260924) — a lower bound **below** the **0.80** bar, so this wider-set robustness check does **not** clear the bar that the 31-unit interval clears; the registered criterion value (`block_boot_lower`) is the 31-unit one, **0.913**. Removing any one knob whole leaves **0.883–0.970** as above. We report the clustered interval alongside the unit one rather than instead of it. **Why the interval is the right instrument here, stated exactly.** A permutation test is informative only if it perturbs what the statistic depends on, and this statistic is a rank correlation over the **paired** unit readings: permuting *whole knobs* moves those pairs about but does not break them, so the statistic is
bit-identical under all 720 block permutations and `p = 1`. **This is not a defect of this implementation but a
theorem about the class of statistics it belongs to: any symmetric function of a set of *paired* readings —
Spearman, Kendall, distance correlation, a two-sample $U$ — is invariant under every permutation that keeps the
pairs together, so its permutation null is a point mass at the observed value and the test has zero power by
construction, not merely low power. The instrument for a paired design is a null that breaks the pairing —
redrawing one member of each pair, equivalently redrawing the span values from their own distribution — and that is the null we use.** Resampling whole pairs is a different operation and does *not* break the pairing: it keeps both members of each pair together — the point-mass null of this appendix — so it is not the instrument. **The nulls are reported separately, not as equivalents.** Redrawing the span values from their own distribution breaks the pairing, and there the ordering separates on all three deflations and both unit sets: the **free label-permutation** null returns **0 of 20,000** draws at least as extreme, i.e. the Monte-Carlo floor `1/(B+1) = 5.0×10^{-5}`. **Three objects, not two, and they do not all read the same.** (i) The **whole-pair** null is the degenerate point mass, `p = 1`. (ii) The **free label-permutation** null breaks the pairing and sits at the floor, `5.0×10^{-5}` (0 of 20,000). (iii) The **clustered** null — the one the pre-registered criterion is defined on — uses a statistic that depends on the *cluster structure of the labels* (`between_rank_r2` over the unit→knob label map, with the unit-to-knob assignment shuffled), and it is **not** at the floor: on the registered reading it returns **1 of 20,000** draws at least as extreme, i.e. **`p = 1.0×10^{-4}` (= `2/20001`)**, one Monte-Carlo step above the floor. We therefore report the clustered result as **`p = 1.0×10^{-4}` (1 of 20,000)** against the pre-registered `p < 0.05` bar; the floor `5.0×10^{-5}` is a different number and is named as the budget's own resolution, not as the clustered reading. The floor itself is a property of the budget, not a measurement.** We therefore rest the claim on the interval, not on a clustered $p$ — the units are six knobs and the test cannot separate them. Reproduction: the clustered-interval driver script released with this appendix, its pre-registered criteria file and its frozen result file — **all three are in the released reproduction package**, each listed in `MANIFEST.csv`; the script reads only the two released inputs (`equalcount36_result.json`, `m37_ci_power_result.json`) and refuses to run unless the first one's md5 matches the value printed earlier in this appendix, so the clustered interval above **is** independently recomputable from the package; the span-value null is recomputed from the released `equalcount36_result.json` by a second released script; the point readings it is compared against are recomputed from the released `equalcount36_result.json`.

The two quantities printed above are linked by the same arithmetic, which is worth stating because it makes the choice of a 0.80 lower bound non-arbitrary: with `ICC(1) = 0.645` the variance ratio is `σ_w²/σ_b² = (1 − 0.645)/0.645 = 0.5504`, and Spearman–Brown at six units returns `6 × 0.645 / (1 + 5 × 0.645) = 0.916`, the reliability printed for `m = 6`. The allocation formula is the inverse of that step, so the four targets are recovered from the same two numbers: `m*` = **2.20 / 4.95 / 10.46 / 54.49** for `ρ*` = 0.80 / 0.90 / 0.95 / 0.99. Nothing here is new theory; it is the arithmetic of the data structure, and it is what makes "six units, 0.80" a defensible design point rather than a convention.

The null that permutes **whole pairs** — relabelling the units while keeping each unit's two members together — leaves every **symmetric function of the paired multiset** literally unchanged. The resampling distribution is therefore a **point mass**, and a test against that null has **zero power by construction**. This is a property of the design, not of our implementation. A numerical check agrees **to machine precision**; at full float precision it does **not** return a single distinct value, because the summation order inside the correlation differs across permutations, so we do not quote "one distinct value" as the evidence. The **pair-breaking** null is the informative one: over the 720 permutations of a six-unit set it returns **470 distinct values** spanning **−0.90 to +0.95**, which is what separates the orderings — and it is why the claim rests on the interval rather than on a clustered $p$.

The block bootstrap resamples whole knobs, and with six knobs it draws from a set of only `C(11,6) = 462` distinct resamples, so a 2,000-draw run repeats each of them several times over and its interval is reported to three decimals rather than at full float precision. The **permutation** budget is separate: `B = 20,000` draws, so `p = (1 + #as-extreme)/(1 + B)` is quantised at `1/20001 = 5.0×10^{-5}`, and the registered clustered reading sits **one step above that floor** at `2/20001 = 1.0×10^{-4}`. We state the design fact behind it: **the six knobs are a design choice, not a random sample of clusters**, which is why the clustered interval is used as a robustness check on the pooled one and not as the interval of record.

**How many units are enough, when the knob means are what is being read.** The same six-knob nesting also
prices a design. Treating the 36 log-spans as one-way nested in the six knobs — detector 12, density 4,
output contract 2, pixel budget 6, prompt family 6, tiling 6 — and estimating the variance components by
moments with the unbalanced-group constant $m_0 = (N - \sum_i n_i^2/N)/(k-1) = 5.6889$ gives
$\sigma_b^2 = 1.706$ and $\sigma_w^2 = 0.940$, hence $\mathrm{ICC}(1) = 0.645$ and a knob-mean reliability at
six units per knob of $\rho_6 = 0.916$. The reading does not depend on the deflation: the per-unit reliability
is **0.645** on full levels, **0.596** under the equal-count $k=3$ restriction, **0.651** dropping the highest
level and **0.634** dropping the lowest. To reach a target $\rho^\star$ a design needs

$$ m^\star = \left\lceil \frac{\sigma_w^2}{\sigma_b^2} \cdot \frac{\rho^\star}{1-\rho^\star} \right\rceil $$

units per knob — **3, 5, 11, 55** for $\rho^\star = 0.80, 0.90, 0.95, 0.99$, i.e. **18, 30, 66, 330** units in
total against the 36 analysed here. This is the arithmetic behind the bar of §M.45(a): at six units per knob
the measured $\rho_6$ is **0.916**, so a pre-registered $0.80$ is met with margin while $0.95$ is out of reach
at this unit count, and raising the bar is a matter of units rather than of effort. The object here is the
reliability of a **knob mean under the observation design**, which is not the same object as the
certifiability of a partition in the rule above.

**Why no split could be certified.** The observed split is **3 vs 7**, and $\binom{10}{3} = 120$ assignments
put a floor of $1/120 = 0.0083$ under the permutation $p$ *before* correction; with the nine enumerated split
points the smallest attainable corrected $p$ is **0.075** — above 0.05 for **any** gap, so this split cannot be
certified at this sample size whatever the separation. A 5-vs-5 split of the same ten units
($\binom{10}{5} = 252$) would need **6.5 pp** for 80% power at the low end of the noise band (uncorrected
reference: **3.95 pp**). This is why §7.3 states the ordering and not a partition.

**Held-out calibration, with intervals.** Under **200** random one-third held-out splits of the same unit set,
the shared and global affine families keep the ordering at median **0.995** (**0.984–0.998**), above 0.9 in
**200 of 200** splits, whereas the per-unit families collapse to medians **0.41–0.54** — the quantitative form
of the statement that the ordering claim is scoped to the first two calibers.

**The suggested fix was tried, and it fails — which is itself the answer.** Raising the unit count by
**splitting the detector-$\tau$ knob by input size** (the three detector units are pooled over
$640/1024/1536$) would take the spectrum from **10 to 16 units** and lift the structural floor: the corresponding **3 vs 13** split has $\binom{16}{3} = 560$ assignments, so its smallest
attainable corrected $p$ would be $15/560 = 0.027$, i.e. **inside** the significant region. We ran it on the
same per-item records with the same unit construction and the same random half-sample split, resampled over 200 seeds
(`a44_split16.py`; frozen `a44_split16_result.json`; the script first **reproduces the 10-unit table
bit-for-bit** as a check that it is the same pipeline):

| unit set | corresponding split | gap | permutation $p$ | smallest attainable corrected $p$ |
|---|---|---|---|---|
| **10 units** (as published) | 3 vs 7 | **+1.58 pp** | 0.0082 (164/20,000) | $9/120 = $ **0.075** |
| **16 units** ($\tau$ split by input size) | 3 vs 13 | **−2.58 pp** | — (overlaps) | $15/560 = $ 0.027 *(were the gap positive)* |

The two columns are computed differently: the permutation $p$ is a **Monte-Carlo** estimate (164 of 20,000 draws), and nine times it gives **0.074** — marginally below the exhaustive floor $9/120 = 0.075$ that complete enumeration over the 120 assignments could return. The paper quotes the floor, which is the value an exact test cannot go below; both are above 0.05, so the verdict does not turn on the choice.

**When a split can be certified at all.** The two rows of the table above are the ends of one rule. With $n$ units, a $k$-vs-$(n-k)$ reading and $n-1$ enumerated split points — the enumeration design both rows use — complete enumeration has $\binom{n}{k}$ assignments, so the smallest attainable corrected $p$ is $(n-1)/\binom{n}{k}$ and the split is certifiable at level $\alpha$ exactly when $\binom{n}{k}>(n-1)/\alpha$. The published ten-unit split gives $9/120=0.075$ and cannot be certified; the sixteen-unit construction gives $15/560=0.027$ and can. For $k=3$ and $\alpha=0.05$ the rule needs $\binom{n}{3}>20(n-1)$, first satisfied at $n=13$ — so **thirteen units would have sufficed** for the construction this appendix ran with sixteen, and "how many units must I add?" has a one-line answer. This is a statement about **certifying a partition**, not about the ordering: §M.45 asks the different question of how the full ordering behaves under an equal level count and under a common error budget, and answers it there.

**One premise carries this rule: $k$ must be fixed before the data are seen.** If the cut size is chosen from
the same data, the multiplicity to correct for grows from $\binom{n}{k}$ to
$\sum_{k}\binom{n}{k} = 2^n - 2$, so an *observed* corrected $p$ then carries a larger correction. The
enumeration's floor moves the other way — it is $(n-1)/(2^n-2)$ — so the rule above, which is a statement
about what an enumeration **can** return, is quoted for the **pre-registered** case only, and is not offered
as a bound in the data-chosen one.

**The separation does not survive the finer unit set.** With the detector knob split, the largest
non-overlapping gap anywhere in the 16-unit spectrum is **0.2 pp** (a 1-vs-15 split), and the split that
corresponds to the published low cluster now has a **negative** gap: the third pixel-budget unit's upper
bound (19.6 pp) overlaps the lower bound of the `det · in-domain BBBC005 / tau@640` unit (19.8 pp) once that
unit is measured on its own. ⇒ **The "low-response cluster" is a property of the coarser unit set, not a
feature that survives unit refinement**, and the lifting of the structural floor is therefore moot: a design
that could in principle certify a split finds nothing to certify. This is a stronger and more specific reason
for the candidate wording of §7.3 than the power limit alone, and we report it as a **negative result about
our own candidate**, not as a defence of it.

*Reproduction: `a44_split16.py` (unit construction, iso-calibrated spans, 200-seed half-sample-split CIs, cut-point
enumeration, 20,000-permutation test) over the frozen detector ladders and per-item records of the reproduction
package; frozen `a44_split16_result.json`. Both unit tables and both split tests are in the frozen file.*

### F.8 Span is not a single construct: per-unit values for §7.2

Endpoint spans derive **54–80%** of their magnitude from the single most extreme level, and the mean
absolute deviation is a different quantity: the VisDrone pixel-budget unit has the **highest** mean
$\lvert\rho\rvert$ at 32.7 with one of the smallest spans.

### F.9 The ten (knob × domain) units, isotonic-calibrated

The span spectrum of F.2 pools each knob over its domains; the split-point enumeration of F.3 instead runs
over **ten (knob × domain) units**, listed here in full so that the enumeration is reproducible. Spans are
in percentage points of the pooled relative deviation; the interval is a **random half-sample split, resampled
over 200 seeds**, 95% CI under the
isotonic-calibrated (monotone, shape-free) reading, which is the reading §7.3 quotes. The **group** column
gives the $k = 3$ split of F.3: the three pixel-budget units form the low group, the other seven the high
group.

| Unit (knob / domain) | Shared affine | **Isotonic** | Quantile map | Isotonic 95% CI | Group at $k=3$ |
|---|---|---|---|---|---|
| Detection, in-domain / VisDrone | 103.9 | **150.7** | 254.8 | [98.3, 172.2] | high |
| VLM, output contract / InternVL | 23.0 | **97.7** | 87.9 | [74.0, 179.2] | high |
| VLM, output contract / Qwen3-VL-32B | 58.5 | **85.9** | 90.0 | [71.1, 109.0] | high |
| Detection, zero-shot COCO | 56.0 | 54.2 | 283.1 | [43.3, 93.0] | high |
| Detection, in-domain / BBBC005 | 79.4 | **49.0** | 61.2 | [45.0, 57.7] | high |
| Density regression, official DM-Count / UCF-QNRF | 31.9 | 36.6 | 37.5 | [24.0, 48.7] | high |
| Density regression, official DM-Count / ShanghaiTech-A | 32.5 | 33.5 | 34.3 | [29.5, 42.3] | high |
| VLM, pixel budget / UCF-QNRF | 8.6 | 17.2 | 4.7 | [4.5, 19.6] | **low** |
| VLM, pixel budget / VisDrone | 14.2 | 16.8 | 32.9 | [11.4, 22.4] | **low** |
| VLM, pixel budget / ShanghaiTech-A | 1.5 | **1.1** | 1.4 | [0.4, 4.2] | **low** |

The two numbers that appear in §7.3 are visible here: the high-response group spans **33.5–150.7 pp**
(its minimum and maximum isotonic values) and the low group is bounded above by **22.4 pp** (the upper end
of the VisDrone pixel-budget interval), against a high-group minimum lower bound of **24.0 pp** (the
DM-Count/UCF interval) — the 1.6 pp gap of F.3.

Two readings of this table matter for the paper's claims. First, the **noise floor** is 2.15–6.46 pp, so
the pixel-budget unit on ShanghaiTech-A (**1.1**, CI [0.4, 4.2]) lies inside it and is not used for any
claim; the other two pixel-budget units (16.8 and 17.2) do exceed it. Second, calibration family changes
individual units substantially — BBBC005 falls from 79.4 to **49.0** and the pixel-budget/VisDrone unit
*rises* from 14.2 to 16.8 — which is why the table reports all three families rather than one.

**Provenance and caliber.** This table is a **transcription**: its values are reproduced verbatim from
the Chinese working skeleton's §8.10 table and verified row by row against it (`f9_transcribe_check.py`; all ten rows and four numeric columns match). It is **not** independently reproducible from the released records:
under the pooled caliber declared above, an in-sample isotonic calibration is not a distinct reading. The
column is quoted **as transcribed**, and §7.3 names the caliber when it uses it. **The main-text uses of this
column are illustrative only and no load-bearing claim rests on it**: the load-bearing ordering evidence is the **recomputable** set of Appendix M.37, built on
the same ten constructs at **36 units** and computed from released records, which is the version to cite.
**Can these ten rows be recomputed instead?** Run with the rule fixed in advance (`f9_repro.py`; within 5%
is a match, above 20% on both families is "no implementation here"), only the two density-regression units
reproduce — pooled caliber, isotonic fitted in the **oracle** direction (**32.6** vs 33.5, **35.1** vs 36.6)
— while in-domain VisDrone, BBBC005 and both output-contract units differ by **more than 20%** in both
directions and the zero-shot COCO unit matches neither. The ten rows are a **verifiable transcription**
(row-by-row against the working skeleton, `f9_transcribe_check.py`), not a reproducible pooled table
(`f9_repro_result.json`); the ordering claim therefore rests on the recomputable 36-unit set.

### F.10 Does the spectrum survive equal-count gridding and endpoint removal?

F.2/F.9 compare knobs whose ladders contain **different numbers of levels** (4 for the fixed-short-side
scale, 5 for tiling and pixel budget, 6 for the input multiplier, 8–16 for the detector threshold). That
raises the objection that a span is partly a function of **how finely the knob was scanned** and of
**where the endpoints fell**. We tested both, on the released per-image records only (no new inference):

* **Equal-count re-estimation.** Every ladder-level sequence was reduced to a common **k = 4** levels,
  taken at evenly spaced quantile positions of its own grid, and the span recomputed.
* **Endpoint removal.** Each lens was recomputed with its single highest level dropped, and again with its
  single lowest level dropped.

**Both deflations are applied within one caliber at a time.** The detector-τ ladders admit two calibers
(person-matched and all-detections) and they are **not the same quantity**, so every detector row below
reports both and neither is ever subtracted from the other. The corrected analysis is in
`span_equalcount2.py`, which asserts per-ladder caliber uniqueness and reproduces the superseded values
under `--reproduce-bug` (Appendix Z).

The **ordering is robust**: over all **24 units** (six knobs × domains/models), the Spearman rank
correlation between the full-ladder ordering and the re-estimated ordering is **0.999** (equal-count),
**0.981** (highest level dropped) and **0.991** (lowest level dropped) person-matched (**1.000 / 0.978 /
0.990** all-detections) — all far above the 0.8 threshold we would have accepted as evidence of
instability.

The **magnitudes**, by contrast, are governed by the caliber, not by the grid:

| Ladder family | levels | full span (pp), person / all-det. | equal-count span (pp), person / all-det. | retention |
|---|---|---|---|---|
| Detector $\tau$, in-domain / VisDrone (imgsz 1536) | 8 | 195.7 / 508.4 | **195.7 / 508.4** | 1.00 / 1.00 |
| Detector $\tau$, in-domain / VisDrone (imgsz 1024) | 8 | 159.3 / 438.1 | **159.3 / 438.1** | 1.00 / 1.00 |
| Detector $\tau$, in-domain / VisDrone (imgsz 640) | 8 | 95.8 / 352.8 | **95.8 / 352.8** | 1.00 / 1.00 |


**Level count and grid, declared.** The detector rows above are computed on the level grids of the
artefact that produced them: the **in-domain** ladder has **8** τ levels and the **zero-shot COCO** ladder
**16**. §4.1 quotes the same ladders on an **8-level** grid for both, so the two sets of spans are **not
interchangeable**: at 1536 px they coincide (**55.5** person-matched, **156.0** all-detections), while at
640 and 1024 px they read **16.4 / 30.3** on the person-matched caliber and **63.1 / 94.3** on the
all-detections caliber (§4.1, 8 levels) against **20.2 / 33.7** and **78.3 / 105.0** here (16 levels).
Neither set is wrong; they are different grids, and subtracting one from the other is exactly the
construction this appendix withdrew. **The 8-level column is recomputed cell for cell from the per-item
ladder records in `f10_grid8_declared.py`, which asserts all twelve of its values**; that is where §4.1's
**63.1** endpoint is traceable, since the table above prints only the 16-level column. Two further 0.1 pp
differences are declared rather than reconciled, and both are ties at the third decimal: the in-domain 640
row is **95.85** pp, printed **95.8** here and **95.9** in §4.1; and the in-domain 1536 span endpoint is
**508.35** pp, printed **508.4** here and **508.3** there. The same recomputation produces both.

| Detector $\tau$, zero-shot COCO (imgsz 1536) | 16 | 55.5 / 156.0 | **54.1 / 149.9** | 0.97 / 0.96 |
| Detector $\tau$, zero-shot COCO (imgsz 1024) | 16 | 33.7 / 105.0 | **29.4 / 87.6** | 0.87 / 0.83 |
| Detector $\tau$, zero-shot COCO (imgsz 640) | 16 | 20.2 / 78.3 | **15.8 / 57.7** | 0.78 / 0.74 |
| Density regression, input multiplier / st_a | 6 | 1432.9 / — | 1432.9 / — | 1.00 |
| Tiling / st_a | 5 | 33.3 / — | 33.3 / — | 1.00 |
| Pixel budget (res_ctrl) / q32 / visdrone | 5 | 14.6 / — | 14.6 / — | 1.00 |
| Output contract (E2) / q32 / st_a | 6 | — | — | see M.18.3 |

Two consequences, and we state both in the main text:

1. **Whether the spans are a function of the scanning density depends on how the levels are thinned — and we
   report both.** *(a) Quantile
   equal-count, as above, keeps the first and last level by construction, and the extremes sit at the ladder
   ends, so it leaves the span where it was: median retention **1.00**, worst case **0.542601**. *(b) **Random**
   deletion to the same $k = 4$ — which does **not** guarantee the endpoints and is therefore the honest
   perturbation — tells a different story: over the six detector-$\tau$ ladders the median retention is
   **0.51–0.67** (person-matched; **0.52–0.66** all-detections) with a minimum of **0.06**, and pooled over
   all 24 units the retention has median **1.00** but a 5th percentile of **0.32** and a minimum of **0.06**
   (person-matched), with only **58%** of draws retaining $\ge 90\%$. The shrinkage is concentrated in the **fine-grid units**
   (the $\tau$ ladders carry 8–16 levels; the 4–6-level ladders are barely affected). ⇒ The fine-grid knobs
   **do** owe a substantial part of their headline magnitude to how finely the knob was scanned; the
   reading that "the objection is not supported" holds only for the endpoint-preserving construction
   (Appendix Z).
   **What survives random deletion is the ordering**: the Spearman between the full-ladder and the
   randomly-thinned ordering over all 24 units has median **0.963** (person) / **0.977** (all-detections),
   5–95% **[0.924, 0.987]** / **[0.959, 0.992]**, minimum **0.885** / **0.937**. So a cross-knob **magnitude**
   must be quoted with its grid density **and** its caliber (all-detections over person-matched on the same
   ladder moves it by **2.6–3.9×** — the six caliber-split detector-$\tau$ ladders of the table above, three in-domain VisDrone and three zero-shot COCO, each at its own level count; the distinction §4.1 corrects), while the spectrum's *ordering* is what
   carries the claim.
2. **Endpoints carry a large share of individual spans**, consistently with F.8 (54–80% from the single
   most extreme level): dropping one endpoint costs a median of only **4%** (highest) and **7%** (lowest)
   of the span, but the worst case (the three-way pixel-budget ladder on InternVL3.5-8B under UCF-QNRF) loses **65.2%**.
   Spans whose extreme level is degenerate should therefore be read as endpoint-bounded, which is also why
   F.9 reports isotonic-calibrated spans with half-sample-split intervals rather than raw endpoints.

*Reproduction: `code/analysis/span_equalcount2.py` over `data/derived/` (quantile equal-count and the ordering
under the three deflations) and `_f10_random_drop.py` / `_f10_random_drop_order.py` over the same ladders
(**random** deletion to $k=4$, with the ordering test importing the unit construction of
`span_equalcount2.py` rather than restating it); frozen `span_equalcount2_result.json`,
`f10_random_drop_result.json`, `f10_random_drop_order_result.json`. The superseded script `span_equalcount.py`
(and its `span_equalcount_result.json`) is retained byte-identical for audit; it is the caliber-mixed version
and should not be used.*

**Unit coverage.** Of the 24 units here, 16 are drawn from pre-computed pooled-relative-deviation tables
rather than per-item records and cannot enter a per-item held-out analysis; **M.37** uses the 8 that can, and
recomputes the three deflations of this section on a 36-unit set of the same per-item sources.

**Is the span just the knob's travel?** A span is a range that a knob moves a quantity over, so the rival
reading is that it measures each knob's *allowed travel* rather than the model's behaviour. Normalising
every unit by its knob's **relative travel on the ladder actually scanned** — detector $\tau$ 0.05→0.5
(8 levels, **10.0×**), density-regression input multiplier 0.5→2 (**4.0×**), pixel budget 5.242× over its
non-zero segment, tiling **6×** by side length — **preserves the ordering**: Spearman **+0.966** over the 28
normalisable units of M.37's 36-unit set (**+0.958** after the two retired reproduction units are removed)
and **+0.810** over the ten units of F.9; the top-ranked unit does not change and the six pixel-budget units
stay at the bottom. Two knobs cannot be normalised at all, being categorical (the contract's four arms, the
prompt family's five instructions), and they occupy the **top** of the ordering — normalisation has nothing
to say about them. The normalisation is also not unique in three places: tiling can be measured by side
length (6×) or by tile count (36×), which lowers the 36-unit Spearman to +0.819; a density unit mixes two
protocols, so its travel is 4.0× or 2.667×; and a categorical knob's travel can only be set to 1 by fiat.
**Read as a monotone law the rival reading fails** — the knob-level correlation of travel with the median
span is **−0.200** and with the maximal span **−0.400**, and the smallest-travel knob (density regression,
4.0×) has by far the largest span. It is nevertheless **weakened, not excluded**: if "travel" is read as the
knob's physically allowed range rather than the ladder scanned, detector $\tau$ becomes 45× and the
ordering partly collapses (36-unit Spearman **+0.667**, **+0.584** after removal of the retired units, and
the top rank changes on the F.9 set) — a reading that is itself unbounded for $\tau$, for the pixel budget
and for the density multiplier. We therefore report the normalised magnitudes rather than claiming the
reading is dismissed. **Span per unit of relative travel** (pp per 1×, M.37's 36-unit set, largest first):
density·CSRNet/st **363** ｜ density·CSRNet/ladder 97 ｜ tiling·choice 43 ｜ det·VisDrone (full grid) 20.5 ｜
det·$\tau$@1536 19.6 ｜ det·$\tau$@1024 15.9 ｜ det·BBBC005 11.2 ｜ density·DM-Count/ucf 8.8 ｜
density·DM-Count/st_a 8.2 ｜ det·COCO/$\tau$@640 1.6 ｜ pixel-budget 2.78 → 0.20.

*Reproduction: `analysis/work/g15_travel_extract.py`, `g15_levels.py`, `g15_normalise.py`; spans from
`equalcount36_result.json` (md5 `bd70867b1453`). Travel is taken from the ladder files that construct M.37 —
not from §4.3's 177-point reachability grid (0.02→0.90) or §5.7's down-15% legibility contrast, neither of
which is a span ladder; the travel ratios of 45× and 6.7× are those two other measurements.*


### F.11 Two falsification controls

Both are analyses of already-released records — no new inference (provenance: Appendix Z):

| Objection | Control | Outcome |
|---|---|---|
| "Span is a function of the scanning grid and of the endpoints" | **quantile** equal-count subsampling + endpoint removal over 24 (knob × domain) units, plus **random** deletion to $k=4$, **within one caliber at a time** (F.10) | **ordering stable** — Spearman **0.981–0.999** under the three endpoint-preserving deflations and **0.963 / 0.977** (median, 5–95% [0.924, 0.987] / [0.959, 0.992]) under random deletion. The *magnitudes* are **not** grid-independent: quantile equal-count leaves them where they are (median retention **1.00**, because it keeps the endpoints by construction), whereas **random** deletion costs the fine-grid ladders a median **38%** of their span (retention 0.51–0.67; 5th percentile 0.32) — so the objection **does** bite for magnitudes, and a magnitude is quoted with its grid density **and** its caliber (2.6–3.9×, all-detections over person-matched on the same detector-$\tau$ ladder; F.10). |
| "The dense-scene headline may be a property of the build, not of the task" | two-way variance decomposition (build × domain) on the E2 census, five deployments of **one** 32B checkpoint (M.18.8) | **38.7% domain / 33.9% build / 27.4% interaction**; within dense domains the five deployments differ by up to **90.3 pp**, within aerial domains by **2.7–8.7 pp** ⇒ the dense headline is build-specific, the aerial one domain-specific (stated in §9) |
| "The contract result holds only for the Qwen and InternVL lineages" | the **same instrument** re-run as a cross-family grid: four further open-weight families (all unquantised builds) plus three E2 anchors, four domains, two pools (M.19) | **7 of 7 families drop the answered zero** when the contract offers an outlet (pooled residual ≤ **2.1%**), direction consistent in every family and domain; the two-kinds claim sharpened inside one family: dense zero rate moves **81.3 pp** across five builds, aerial **5.7 pp** |

---

### F.12 Span intervals, and the span in units of the noise floor

Each span should be visible **with its own sensitivity range**. Figure F.17 plots all **36** recomputable
units: the point is the span over all levels, the bar spans the three deflations of §F.10 (equal-count
gridding at $k=4$, and removal of each ladder's extreme level), so it is a *caliber* interval, not a
sampling one (`F17_span_forest.png`, from `equalcount36_result.json` via `span_forest_norm.py`). Dividing
by the across-repeat noise floor of §A.3 (**2.15–6.46 pp**) puts the units on one scale: the largest spans
are **225–675** noise-floor units, the smallest **0.16–0.48**, about **three orders of magnitude** apart —
which is why magnitudes are not portable across knobs while the ordering is. Inside the model's nominal
operating range the spans are small by construction — the low-response units sit at **1.0–17.2 pp** — so the
ordering is read from the full ladder rather than from that range. Note also that rescaling every span by a
**common** factor (the noise floor here) cannot change the ordering at all, which is Proposition 5 read
backwards: the invariance is exactly what makes the normalized view safe and the magnitude claims unsafe.

## Appendix G. The three excluded mechanism hypotheses: pre-registered criteria and per-cell data

§7.6 states that all three candidate explanations for the directional effect of `forbid0` are excluded.
This appendix carries the pre-registered criteria and the per-cell data behind that statement.

### G.1 Mediation by abstention rate: pre-registered, and negative

**Background.** On BBBC005 (abstention ≈ 1%) the effect of `forbid0` is near zero, which suggests a
mechanistic reading: *the effect of `forbid0` is proportional to the amount of abstention it can convert*.
That inference confounds domain with abstention rate, because the two happen to move in the same direction
between BBBC005 and the dense domains. The correct test **manipulates abstention rate** and asks whether
the effect follows.

**Design — criteria fixed before the numbers were seen.** The tiling level is a ready-made abstention
manipulator (32B on ST-A: whole image **56.6%** → 2×2 **6.0%** → 3×3 **0.55%** → 4×4 **0.0%**). A contract-arm ×
tiling-level factorial was run over 8B and 32B × {`base`, `forbid0`, `choice`, `range`} ×
{whole, 2×2, 3×3} × {ST-A, UCF}, reusing the tiling and aggregation logic byte-identically.

- **H**: if the effect of `forbid0` is proportional to convertible abstention, then |Δ| must tend to zero
  as abstention falls.
- **C**: if the `choice` channel is independent of abstention, then |Δ| must **not** vanish as abstention falls.

| Configuration / domain | Abstention (whole → 2×2 → 3×3) | `forbid0` Δ | `choice` Δ |
|---|---|---|---|
| 32B / ST-A | **56.6% → 6.0% → 0.55%** | +185.2 → +194.7 → +166.5 pp (flat) | +153.9 → +351.6 → **+412.3** pp |
| 32B / UCF | **53.6% → 9.9% → 1.2%** | +166.1 → +200.2 → +161.9 pp (flat) | +99.3 → +258.9 → **+319.6** pp |
| 8B / ST-A | 0.0% → 0.0% → 0.0% | +27.6 → +34.1 → +24.2 pp | +136.7 → +434.4 → **+689.9** pp |
| 8B / UCF | 0.6% → 0.0% → 0.0% | +27.1 → +39.5 → +36.7 pp | +78.6 → +282.5 → **+433.6** pp |

Δ is the item-intersection paired difference against `base` at the same model, domain and level, with
20,000 permutation draws. The `range` arm is likewise a strong directional knob, **+72 to +370 pp**.

**Result: H is rejected; C is confirmed and strengthened.**

1. **H fails.** With 32B abstention compressed to **0.0%** at 4×4, Δ for `forbid0` is nearly unchanged
   (+185 → +195 → +167 pp). More decisively, 8B has **0.0% abstention at every level** and still shows a
   non-zero Δ of **+24 to +40 pp**. `forbid0` therefore does not act by converting answers of zero; it
   moves the **location** of the answered distribution.
2. **C holds, and is strengthened.** Δ for `choice` **increases monotonically with tiling depth in all four
   cells**, while abstention falls to zero. The channel is entirely independent of abstention, and its
   authority **grows as input legibility improves** — a stronger and more useful statement than the one it
   replaces: high legibility does not merely remove abstention, it enlarges the authority of the
   language-side knobs.
3. **There is no two-branch split.** `forbid0` is a strong directional knob at every abstention level in the
   dense domains (+160 to +200 pp for 32B), yet near zero on BBBC005 (+0.6 to +5.8 pp); its magnitude is
   set by the **domain**, not by the abstention rate.

### G.2 The decisive controlled test: a synthetic grid with n and σ varying independently

To turn "ground-truth magnitude sets the scale" from an observed association into a controlled conclusion,
the three contract arms were added to a **synthetic disc grid on which ground-truth count n and blur σ vary
independently** (n ∈ {100, 400, 800} × r ∈ {2, 4, 8} × σ ∈ {0, 1, 2, 4, 8} × 15 = **675 items**), run on
three configurations: Qwen3-VL-8B, Qwen3-VL-32B and InternVL2.5-8B.

**Pre-registered criterion.** If Δ grows strongly with n and only weakly with the answered-zero flux, the
scale factor is the ground-truth magnitude. If the reverse holds, the observational conclusion is a domain
artefact. If Δ ≈ 0 and uncorrelated with both, the magnitude-factor account holds.

| Configuration | Abstention channel | max abs Δ(`forbid0`) | r(~n) | r(~answered-zero flux) | Δ stratified by n (100/400/800) |
|---|---|---|---|---|---|
| Qwen3-VL-8B | answered zero | 40.0 pp | −0.005 | −0.053 | 23.2 / 3.4 / 21.2 pp |
| Qwen3-VL-32B | answered zero | 31.3 pp | +0.645 | +0.487 | −2.6 / −4.0 / +17.3 pp |
| **InternVL2.5-8B** | refusal / non-numeric | **42.2 pp** | +0.527 | +0.130 | **−24.3 / −9.3 / −4.0 pp** |

**Three negations.**

1. **Magnitude mismatch.** On ST-A, Δ for 32B in the observational data is of order **+184 to +185 pp**,
   whereas on the controlled grid the largest value in any configuration is **31–42 pp**.
2. **The predicted null fails.** InternVL2.5-8B was expected to show Δ ≈ 0, on the reasoning that its
   abstention travels through a refusal / non-numeric channel with no answered zeros to rewrite; on the
   grid its Δ spans **−24.3 to +18.9 pp**, reaching **42.2 pp** in absolute value — the same order as Qwen.
3. **The most direct refutation.** At σ = 8, n = 800 the 32B base abstention rate is **100%** — every item
   answered zero. If `forbid0` acted by converting answered zeros, this cell should show a very large Δ.
   The measured value is **+14.2 pp**. This removes both the answered-zero-flux mechanism and a strong
   ground-truth effect; the n-stratified means show no monotone trend either.

The mechanism claim is therefore **downgraded**: `forbid0` is strongly associated with ground-truth
magnitude on real crowd and aerial images (r = +0.91 **within the Qwen family**, see G.3), but the
association **does not reproduce** on the controlled grid, and its cause remains open. This points to an
unexamined domain dependence — the strong effect may require some property of real images (crowding,
semantic ambiguity) rather than the numerical magnitude of the ground truth. **This is the most important
unresolved mechanism question in the paper.**

### G.3 Mediator correlation analysis, and the downgraded statement

Across the 13 (model, domain) units:

| Candidate mediator | correlation with Δ(`forbid0`) | reading |
|---|---|---|
| **median ground truth** | **r = +0.779** (within the Qwen family **+0.914**) | strong |
| base abstention rate | r = +0.078 | unrelated |
| P(pred = 0) over all items | r = +0.078 | unrelated (identical to abstention rate for Qwen) |
| P(pred = 0) over abstaining items | r = +0.270 | weak |
| Δ(`choice`) against all four of the above | abs r ≤ 0.26 | no single predictor |

Grouped by the abstention-channel structure of the lineage (§3.6, Appendix B.3):

| Family | Abstention channel | median GT range | Δ(`forbid0`) | within-family r(Δ~GT) |
|---|---|---|---|---|
| **Qwen** (32B / 8B / 2.5-7B) | **answered zero** | 18 – 388 | **+0.5 to +248.3 pp** | **+0.914** |
| **InternVL2.5-8B** | **refusal / non-numeric** | 18 – 273 | **−2.0 to +4.3 pp** | +0.995 (magnitude negligible) |

The earlier mechanism statement is hereby **downgraded to unconfirmed**. It read that the effect of
`forbid0` is the product of a *magnitude factor* — whether the model expresses uncertainty as an answered
zero, giving up to +250 pp for Qwen and no object to rewrite for InternVL — and a *scale factor*, the
ground-truth magnitude. The controlled grid of G.2 does not support it. What survives is narrower and is
what the main text claims: **abstention rate itself is not a mediator** (r = +0.08). Compressing 32B
abstention on ST-A to **0.0%** (2×2: 6.0%, 3×3: 0.55%) leaves Δ unchanged, and Qwen2.5-7B abstains only 1.6% on ST-A yet still shows
**+136.7 pp**.

Two things remain unseparated: (i) "answered-zero flux × ground truth" and "the whole distribution shifts,
by an amount that grows with ground truth" cannot be distinguished with the present data; (ii) the
interaction is observed on **two lineages only** and is not extrapolated to a general law.

### G.4 The methodological criterion this case yields

The difficulty here was **treating "domain" as a mechanistic variable**: BBBC005 and the dense domains
differ in domain *and* in abstention rate simultaneously, so without manipulation the two cannot be told
apart. The generalisable criterion is therefore: **to claim that A acts on C through B, B must be actively
manipulated**; otherwise the effects of A and of B are not identifiable.

### G.5 Per-cell numbers for §7.6

**Conclusion:** `forbid0`'s effect is **stably observable** but its mechanism is **undetermined**;
it is reported as a **usable directional knob** (§5.8), not as a mechanistically explained finding
(pre-registered criteria and per-cell data in Appendix G).

### G.6 An attempted factorial on the controlled grid, and why it does not adjudicate the mechanism

We attempted to separate the two candidate real-image properties named at the end of G.2 by a $2\times2$
factorial on the same controlled grid — crowding (fraction of discs placed within $2r$ of another disc:
$0$ vs $0.40$) × semantic ambiguity (fraction of non-circular "person-like" distractors injected: $0$ vs
$0.20$) — with $n = 400$, $r = 2$, $\sigma = 2.0$, 150 images per cell, three arms (`base`, `forbid0`,
`neutral0`), **three builds** and three fresh service starts (600 images × 3 arms × 3 builds × 3 starts =
16,200 calls pre-registered).

**The pre-registered design could not be measured, and we report that rather than a null.** At the frozen
parameter point **both arms saturate**: `base` answers zero on **150 of 150** images in every cell and
`forbid0` — whose instruction **forbids** answering zero — answers zero on **149–150 of 150**. The
difference the design exists to measure therefore has **no range**, and this is not evidence that the
effect is absent: reporting it as "not separated" would treat an unmeasured quantity as a measured one.

**The instrument, not the hypothesis, is what failed.** At $r = 2$ the discs are 4 px across on a $1024^2$
canvas — **smaller than a single ViT patch** — the image is **99.5% uniform background** (blue channel
$p_1 = 225$, $p_{99} = 235$ against a background of 235), and a geometric check of the manipulation itself
passes exactly (realized overlap $0.000$ and $0.400$). A dynamic-range pilot run afterwards maps the
region: abstention on this grid is a **cliff** between $0\%$ and $100\%$, the two builds' transition bands
**do not overlap**, and the 31–42 pp effects published above live on the **saturated side** ($\sigma = 8$,
$n = 800$, where the 32B `base` rate is 100% and $\Delta$ is still **+14.2 pp**) — a point the frozen
design, with $n$ fixed at 400 and a single $\sigma$, does not occupy.

**What this costs and what it leaves standing.** The three exclusions of G.2 stand; the crowding and
semantic-ambiguity readings remain **untested**, and we now say why, instead of reporting a factorial we
could not run. **A general lesson, recorded because it is cheap to state and was expensive to learn:** for
any new synthetic stimulus, a **dynamic-range pilot** — a small batch confirming that the target quantity
has a middle range at the *designed* parameter point — must precede freezing the criteria; geometric or
pixel-level verification of the construction **does not substitute for it**, because it can show that the
manipulation was built correctly but not that the model can see it.

## Appendix H. Density-regression protocols and measurements

### H.1 A log-ratio counting consistency loss

Adding a counting-consistency term on the log ratio between the predicted integral and the ground-truth
count reduces the seed-to-seed spread by roughly an order of magnitude and removes most of the systematic
positive offset that the uncorrected training objective leaves behind. We report this as a remedy for a
training artefact rather than a new architecture: part of what is usually attributed to the family is
attributable to the objective.

### H.2 Abstention is stably measurable only under greedy decoding

Under sampling-based decoding the abstention rate is not a stable property of the model, since it
co-varies with the sampling temperature and the number of samples. Under greedy decoding the answer is
deterministic and the rate reproducible. This is why the VLM protocol fixes temperature at 0 and why
the non-determinism that remains is attributed to the serving stack rather than to the model
(Appendix A.3).

### H.3 Collapse under overlap is independent of model scale

A 2×2 factorial contrast (8B versus 32B) shows that the collapse of predicted counts under
overlap — where the prediction ceases to respond to further increases in the true count — occurs
for both models at comparable overlap levels. The collapse is therefore a property of the task structure
rather than of model capacity, and is a further instance of the capacity floor of §5.7.

---

## Appendix I. Data-hygiene ledger

**Quarantine tiers.** Records whose key fields could not be read are isolated in graded tiers rather
than dropped silently. Tier 1 contains runs whose result files were unavailable because of server-side
errors during collection; tier 2 contains runs superseded by a corrected re-execution; tier 3 contains
files whose declared configuration columns disagree with the values re-derived from the outcome columns.
Every analysis reported in the main text was recomputed without tier 1 and tier 2, and the affected
figures are reported on the cleaned set; the corresponding per-tier item counts are recorded in the
project's data-freeze manifest, which accompanies this submission as a separate file.

**Sentinel and range rules.** A predicted value at or above `1e5`, or equal to the exact sentinel
value 1234567890, is treated as an unparsed response rather than as a count, and is excluded before any
rate is computed. Records with a non-positive ground truth are excluded from ratio computations, since
the per-image ratio is undefined for them; this affects the sparse sets only, and the affected rows are
counted rather than dropped implicitly.

**Declared-versus-derived disagreements.** In 238 records the pipeline's declared abstention flags
disagree with the values re-derived from `pred`, `parse_ok` and `raw`. These are enumerated individually
and resolved by hand; they are never resolved by a precedence rule, so that the resolution cannot
silently propagate an assumption.

**Reversal.** Because the tiers and the sentinel rule are recorded rather than applied in place, a reader
who prefers the uncleaned view can reconstruct it: the freeze manifest names the files in each tier, and
no row was deleted from the underlying result tables.


### I.1 Anomalous records, exclusions and data hygiene (for §3.7)

Anomalous predictions (`pred ≥ 1e5`, plus one exact sentinel) are removed before any rate is computed; a
corpus-wide scan shows a **single** anomalous item can move a row's headline figure by hundreds of
percentage points, so this is a precondition rather than a refinement. Records whose key data could not be
read are quarantined and counted rather than silently dropped. Where a comparison depends on matching
annotations — detector boxes whose class set includes vehicles while the ground truth counts people only —
we recompute under a person-matched convention and report both.

### I.2 Figure list (for §3.9)

Figures **1–4** are carried in the main text at the point where their claim is stated (the
abstention-versus-tiling mechanism, the prompt-strength dose–response, the threshold-cleaning curve, and
the four-panel separation of the two failure modes).

### I.3 Runner-defect detail for §8.1

**Two runner defects, located, with stated workarounds.** The first could write results into a directory
already populated by a different model, producing **duplicate rows for the same item** or, more
insidiously, silently writing nothing while reporting success — leaving "new" results that were the
previous model's. The second concerned a missing field in one output format. Both are mitigated by
model-specific output directories and by de-duplicating on `item` while counting duplicates; we report
them because the affected numbers would otherwise be silently contaminated rather than visibly wrong.

## Appendix J. Proofs and verification evidence for Propositions 4–8 (Propositions 1–3 are stated in full in §M.21; this appendix carries 4–8)

Every number in this appendix is **computed from the corpus** by `p4_decomp_verify.py`, not transcribed;
re-running that script reproduces the tables below. The corpus conventions are those of Appendix I
(de-duplicate by `item`, drop `pred ≥ 1e5`, drop unparseable `pred`, drop `gt ≤ 0` from ratio
computations).

### J.1 Proposition 4: the identity and its closed form

With $G$, $G_N$, $P$ and $w=G_N/G$ as defined in §3.8, and abstained items contributing $pred=0$:

$$\rho_{\text{total}}=\frac{P-G}{G},\quad \rho_{\text{answered}}=\frac{P-G_N}{G_N},\quad P=G_N(1+\rho_{\text{answered}})
\ \Longrightarrow\ \rho_{\text{total}}=w(1+\rho_{\text{answered}})-1 .$$

| Quantity | Result |
|---|---|
| Result files scanned / logical units | **136 / 131** |
| Files where the identity applies | **95** |
| Maximum residual $\lvert\rho_{\text{total}}-w(1+\rho_{\text{answered}})+1\rvert$ | **$1.9\times10^{-16}$** |
| Structurally inapplicable | **41** (no abstention: every item answered) |
| Closed form $S$: files checked, max $\lvert S_{\text{measured}}-S_{\text{closed}}\rvert$ | **88**, **$7.5\times10^{-14}$** |
| Scope boundary: residual under the per-image-median convention | **0.01–47.38 pp** |

**Additive decomposition, by dataset** (Qwen3-VL-32B, `base` contract arm, whole-image;
**canonical primary runs only**, i.e. the same runs as the table above):

| Dataset | $\rho_{\text{total}}$ | abstention term $-(1-w)$ | answering term $w\,\rho_{\text{answered}}$ | sum | $w$ | $\rho_{\text{answered}}$ |
|---|---|---|---|---|---|---|
| ShanghaiTech-A | -81.07% | -76.41% | -4.67% | -81.07% | 0.2359 | -19.79% |
| UCF-QNRF | -86.75% | -81.27% | -5.48% | -86.75% | 0.1873 | -29.25% |
| VisDrone | -71.10% | -58.39% | -12.71% | -71.10% | 0.4161 | -30.54% |
| AI-TOD | -80.16% | -67.17% | -12.99% | -80.16% | 0.3283 | -39.57% |
| FSC-147 | -68.55% | -24.89% | -43.66% | -68.55% | 0.7511 | -58.13% |
| TallyQA | -21.78% | -2.75% | -19.03% | -21.78% | 0.9725 | -19.57% |
| CountBench | 2.09% | -0.81% | 2.90% | 2.09% | 0.9919 | 2.92% |

Every row satisfies $\rho_{\text{total}}=-\!(1-w)+w\,\rho_{\text{answered}}$ to rounding, and $w$ and
$\rho_{\text{answered}}$ here reproduce both the closed-form $S$ of the table above and the dual-convention
gaps quoted in §5.11(a) (61.3 / 57.5 / 40.6 / 40.6 pp) — the reconciliation is asserted by the build's
arithmetic check rather than left to the reader.

The two extremes are instructive: on the dense crowd domain almost the whole under-count is abstention
(−76.41 of −81.07 pp), whereas on FSC-147 the answering term dominates (−43.66 of −68.55 pp), and on
CountBench the two terms have opposite signs.

**Consistency check, not an independent prediction.** §5.11(a) reports a dual-convention gap of **61.3 / 57.5 / 40.6 / 40.6 pp**.
Proposition 4 predicts that gap as $\rho_{\text{total}}-\rho_{\text{answered}}=-(1-w)(1+\rho_{\text{answered}})$;
the four reported values are reproduced to within **0.04 pp**. The proposition therefore derives a number
the paper had obtained by a separate route, rather than restating it.

**Abstention share $S$, canonical primary runs only** (the corpus also holds derived re-runs of some cells;
those are excluded here — the largest divergence between a primary run and its re-run is **0.809 pp** on
$\rho$, Appendix J.4):

| Unit (base contract arm) | $S$ measured | $S$ closed form | abstention rate, item-count convention |
|---|---|---|---|
| Qwen3-VL-32B / ShanghaiTech-A | 94.2% | 94.2% | 56.6% |
| Qwen3-VL-32B / UCF-QNRF | 93.7% | 93.7% | 53.9% |
| Qwen3-VL-32B / AI-TOD | 83.8% | 83.8% | 68.1% |
| Qwen3-VL-32B / VisDrone | 82.1% | 82.1% | 68.2% |

**Scope of the 82–94% headline.** Those four cells are the **base contract arm**, and they are what the main
text's 82–94% refers to. Across the contract arms and domains other than the `over` arm — where there are no abstentions at all, below — the same quantity ranges from **42.5%**
(ShanghaiTech-B, `under` arm — a cell whose abstention rate is itself only 13.6%) to **99.4%**
(ShanghaiTech-A, `under` arm). The `over` arm has **no abstentions at all** — its prompt requires every
possible target to be counted — so its abstention share is **0%** in every domain, and the dense
`base` cells sit at **93.7–94.2%** with their `under` counterparts at **98.4–99.4%**. The claim the paper makes — that the dominant component of the aggregate under-count is
abstention rather than estimation error — holds on the base and `under` arms across these domains, and is not claimed for the `over` arm, where the abstention share is 0%; the narrower 82–94% is the base-arm
range and is not presented as a universal bound.

### J.2 Proposition 5

The proof is the two-line computation given in §3.8. Its purpose is to make the calibration objection
**falsifiable**: an affine recalibration of a unit's admitted levels multiplies every span by one number,
the fitted slope $s$, so a claim that spans are calibration artefacts must report $s$. Non-affine
recalibration is outside the proposition's scope and is why the quantile map is treated separately.

### J.3 Proposition 6

The witness is the pair (VisDrone or AI-TOD) versus ShanghaiTech-A: the lowest targets-per-image
(17–22) alongside ShanghaiTech-A's 433, with comparable abstention (68% vs. 57%). The
operational criterion that follows — *a candidate stratifier must show monotone abstention in it* — is
what the paper applies when it stratifies by legibility rather than by OPM.

### J.4 An observed bound on run-to-run non-determinism

The corpus holds, for six configurations, an independent re-run of the same (model, dataset, contract
arm, tiling level). Their aggregate $\rho$ differs by at most **0.81 pp**:

| Configuration | copies' $\rho_{\text{total}}$ | spread |
|---|---|---|
| 32B / st_a / base / whole | −80.286% / −81.075% | 0.789 pp |
| 32B / st_a / base / tile2 | −50.799% / −51.608% | 0.809 pp |
| 32B / st_a / base / tile3 | −36.370% / −36.801% | 0.431 pp |
| 32B / ucf / base / whole | −86.245% / −86.750% | 0.505 pp |
| 32B / ucf / base / tile2 | −58.727% / −59.104% | 0.377 pp |
| 32B / ucf / base / tile3 | −46.236% / −45.697% | 0.539 pp |

This bounds the fragility disclosed in §8.1 with a measured value, and it sits far inside the paper's own
indistinguishability threshold of 7 pp. Numbers reported in the main text are taken from the **primary
run directories** (`dense_results`, `aerial_results`, `ext_results`, `e8b_*`, `q25_*`, `ivl_*`), never
from the derived re-run directory `b2__out_*`.

### J.5 Proofs and verification for Propositions 7–8

**Proposition 7.** With two exhaustive abstention channels and refusal fraction $f$
($0 < f < 1$), the number of items a report records as abstaining is $(1-f)A$ where $A$ is the true
abstention count, so the relative error is $f$. Writing $\kappa$ for answered zeros divided by refusals,
$\kappa = (1-f)A / (fA) = (1-f)/f$, hence $f = 1/(\kappa+1)$ — the identity is independent of $A$ and
therefore of the corpus size. Substituting the measured $\kappa$ values of §3.6 Table 2 gives
$1/551.6 = 0.18\%$ and $6{,}096/20{,}111 = 30.31\%$ (equivalently $1/(\kappa+1)$ with
$\kappa = 14{,}015/6{,}096 = 2.2990$, which rounds to the 2.3 : 1 printed in Table 2; the rounded
$\kappa = 2.3$ gives 30.30%, so the exact ratio is used here).

**Proposition 8.** The bound follows from the identity of Proposition 4 by taking absolute values. The
$\lvert\rho_{\text{answered}}\rvert$ form holds with **equality if and only if** $\rho_{\text{answered}} \ge 0$ (§M.21); for $\rho_{\text{answered}} < 0$ it is **strict**, and at $w = 1$ both sides are $0$. All four measured cells have $\rho_{\text{answered}} < 0$, so the exact form $\lvert\rho_{\text{total}} - \rho_{\text{answered}}\rvert = (1-w)(1+\rho_{\text{answered}})$ is the one used there.
using the canonical primary runs of Appendix J.1 ($w$ and $\rho_{\text{answered}}$ printed in that table):

| Domain | $w$ | $\rho_{\text{answered}}$ | identity $(1-w)(1+\rho_{\text{ans}})$ | observed gap |
|---|---|---|---|---|
| ShanghaiTech-A | 0.2359 | −19.79% | **61.33 pp** | 61.3 pp |
| UCF-QNRF | 0.1873 | −29.25% | **57.50 pp** | 57.5 pp |
| VisDrone | 0.4161 | −30.54% | **40.56 pp** | 40.6 pp |
| AI-TOD | 0.3283 | −39.57% | **40.59 pp** | 40.6 pp |

All four cells reproduce the reported gap to within **0.04 pp**, so the identity above is what generates the
dual-convention gap in every domain measured (Appendix Z). The distinction that matters for §5.7 is unaffected: the gap
is a function of the abstention mass $1-w$ and of $\rho_{\text{answered}}$, and both are reported.

**What a third channel does to that error.** §3.6 and M.38 show that abstentions need not be exhausted by the
two channels Proposition 7 assumes: a true zero emitted as `0`, or a `cannot_judge` / `no_people` token, is a
third outlet. If a share $\varepsilon$ of abstentions takes it, then $a = (1-\varepsilon)\kappa/(\kappa+1)$ and
the reported count carries relative error

$$1/(\kappa+1) + \varepsilon\,\kappa/(\kappa+1)$$

— the two-channel error **plus a linear term** in the third channel's share. For Qwen3-VL-32B
($\kappa = 550.6$) a 1% third channel moves **0.18%** to **1.18%**, a 10% one to **10.16%**; for
InternVL2.5-8B ($\kappa = 2.299$) they move **30.31%** to **31.01%** and **37.28%**. §8.2's scope note is
therefore a quantitative range, not a hedge.

### J.6 Numeric examples for §5.11(b)–(c) (ground-truth trend and scale effect)

Proposition 4 expresses this gap as $-(1-w)(1+\rho_{\text{answered}})$, so the four reported values are a **consistency check on the numbers printed in this paper** rather than an independent empirical prediction: all four values are
reproduced to within **0.04 pp**, so the convention gap is a **derived** quantity rather than a
bookkeeping artefact. **(b) The abstention rate rises steeply with ground truth, flipping the sign of the slope between
conventions.** In the dense synthetic domains the rate climbs with GT (32B: ShanghaiTech-A **27.5% →
85.7%**, $r = +0.490$; UCF **22.0% → 86.1%**, $r = +0.529$), so the slope of $\rho = a + b\,\text{GT}$
**reverses sign** (**−0.00051 → +0.00037**): much of the reported "negative saturation slope" is
manufactured by abstention rather than being a scale response. ShanghaiTech-B is the only domain whose
abstention rate is identically zero, and its two-convention slopes agree exactly (**−0.00168 to
−0.00230**) — the only uncontaminated testbed. **Every directional conclusion here is reported under both
conventions.**

**(c) The scale effect is domain-dependent.** A 4× parameter increase (8B → 32B) enlarges the directional
span by **2.5–3.1×** and the abstention amplitude by **7.4–7.5×** in the dense synthetic domains, but
neither in the aerial domain (**0.66–1.18×** and **0.8–1.3×**). We do **not** claim larger models are
always more directionally controllable.

### J.7 Per-cell values behind the capacity floor, for §5.7

Real images restricted to the answered subset give $\rho = -19.8\%$ (ShanghaiTech-A) and $-29.2\%$
(UCF-QNRF). Its order of magnitude is lower than previously thought: on microscopy it appears from about
**ten targets onwards**, and the whole-domain pooled figure — the **−50.1%** printed in §5.7 — is
approached monotonically across count bins ($[1,10)$ is exactly **+0.0%**; $[60,101)$ reaches
**−53.8%**). The two microscopy numbers are therefore the *same* quantity at two calibers (whole-domain
pooled versus top count bin), both under the pooled convention and confined to these models and domains.

### J.8 The clean synthetic grid: the single-render per-cell values behind the "up to 50%" of §5.7

A deterministic disc grid on which the ground-truth count $n$ and the disc radius $r$ vary independently
($n \in \{50, 100, 200, 400, 800\}$ × $r \in \{2, 4, 8, 16\}$ px = **20 cells**), rendered once with an
explicit seed and read by every arm. The `base` contract **never abstains on any of the 20 cells** — the
answered-zero rate is 0.0% in every cell — and the pooled relative deviation $\rho$ is:

| $n$ | $r$ (px) | px/obj | abstention | mean pred | $\rho$ |
|---|---|---|---|---|---|
| 50 | 2 | 16 | 0.0% | 40 | −19.5% |
| 50 | 4 | 64 | 0.0% | 40 | −20.0% |
| 50 | 8 | 256 | 0.0% | 40 | −20.0% |
| 50 | 16 | 1024 | 0.0% | 40 | −20.6% |
| 100 | 2 | 16 | 0.0% | 100 | +0.0% |
| 100 | 4 | 64 | 0.0% | 85 | −15.4% |
| 100 | 8 | 256 | 0.0% | 91 | −9.3% |
| 100 | 16 | 1024 | 0.0% | 84 | −16.2% |
| 200 | 2 | 16 | 0.0% | 115 | −42.5% |
| 200 | 4 | 64 | 0.0% | 145 | −27.6% |
| 200 | 8 | 256 | 0.0% | 174 | −12.8% |
| 200 | 16 | 1024 | 0.0% | 160 | −20.2% |
| 400 | 2 | 16 | 0.0% | 251 | −37.3% |
| 400 | 4 | 64 | 0.0% | 255 | −36.2% |
| 400 | 8 | 256 | 0.0% | 255 | −36.2% |
| 400 | 16 | 1024 | 0.0% | 287 | −28.2% |
| 800 | 2 | 16 | 0.0% | 490 | −38.8% |
| 800 | 4 | 64 | 0.0% | 460 | −42.5% |
| 800 | 8 | 256 | 0.0% | 525 | −34.4% |
| 800 | 16 | 1024 | 0.0% | 605 | −24.4% |

**Scope of the number printed in §5.7.** The table's own maximum, **−42.5%**, is the largest $\lvert\rho\rvert$
in this table, and it is stated without further qualification. For a reader who wants
the distribution rather than its maximum: the under-count reaches 20% or more in **14 of the 20 cells**
(20.0%–42.5% across those cells), the full range over all 20 cells is **+0.0%** to **−42.5%**, and the
per-$n$ means are −20.0% / −10.2% / −25.8% / −34.5% / −35.0% for $n$ = 50 / 100 / 200 / 400 / 800, so the
growth with $n$ is **not monotone at $n = 100$** and no trend statement is attached to this table.

**This table is one render, and the render seed is not the seed it appears to be.** The grid was rendered
**once**. The renderer (`12_abstain_causal.py`, released under `code/experiments/`) draws each image with the
seed `hash(item) & 0xffff` — i.e. from **CPython's built-in string hash**, which is **randomised per process**;
the module-level `random.seed(20260911)` never enters the drawing routine. A fresh process therefore draws
**different** images, and the per-cell values above are **not byte-reproducible**. We re-rendered the identical
grid five times (controlled by `PYTHONHASHSEED` $\in \{0,1,2,3,4\}$; three arms $\times$ 400 images each,
**6,000** calls) and re-read it with the same probe. The `base` arm's largest single-cell under-count is
**45.05 / 50.00 / 46.25 / 50.00 / 47.50 %** (median **47.50%**; the extremal cell is `n200_r2` in four of the
five renders and `n800_r4` in the fifth). The **structure** reproduces exactly — `base` and `over` abstain on
**0 of 400** items in **all five** renders, and only `under` abstains — while the **magnitude of the extreme
does not**: **every one of the five renders exceeds the 42.5% tabulated above**. That number is therefore a
**conservative single realisation, not a bound**. We accordingly state the clean-input under-count as **up to
50%**, and where the single-cell maximum is quoted we quote it as **45–50%** across renders. The reproduction
note below is amended to match: the table above is one realisation, and reproducing it exactly requires fixing
`PYTHONHASHSEED`.

**Eight frozen render seeds, and a re-run at a fixed seed.** We extended the check to **eight** explicit seeds
(`PYTHONHASHSEED` \in \{0,\ldots,7\}). The `base` arm's largest single-cell under-count per seed is
**47.52 / 50.00 / 46.25 / 50.00 / 47.50 / 47.52 / 50.00 / 50.00 %** (median **48.76%**, minimum **46.25%**):
**no seed exceeds 50%**, and four of the eight reach exactly **50.00%** — which is why the main text states the
clean-input under-count as *up to 50%* rather than as a tighter value. In the same eight runs the `base` arm
abstained on **0 of 400** items in **every** seed, so the structural claim is unchanged.
\* **Residual spread at a fixed seed.** Re-running seed 0 returned **47.52%** where the original five-render
sweep recorded **45.05%** for that same seed — a **2.47 pp** shift **with the render seed held fixed**, i.e.
inside the across-repeat band reported in Appendix A.3 (**2.15–6.46 pp**). The render seed is therefore **not**
the only source of variation in this quantity, and "up to 50%" is the **observed maximum over these seeds**,
not a seed-independent bound. (The five original per-seed files are reproduced exactly by their archived
records: 45.05 / 50.00 / 46.25 / 50.00 / 47.50 %.)

*Reproduction: `synthetic_grid_cells.py` carries the 20 frozen per-cell values and all derivations above,
and its `--check` mode re-reads this table and asserts cell by cell that it still matches them, that
abstention is 0.0% in every cell, and that $\max\lvert\rho\rvert$ is 42.5%. That check verifies the table
against itself; it does **not** re-render. The renderer is `12_abstain_causal.py` (released); because its
image seed is `hash(item) & 0xffff`, reproducing this exact table requires running it under a fixed
`PYTHONHASHSEED`, and the value used for the table above is not recorded — which is why we report the
five-render range instead of a point value.*

### J.9 Proposition 2: the divergence condition, verified

Proposition 2 says the two conventions coincide exactly when the per-image ratio is uncorrelated with ground
truth, and that their gap carries the sign of that covariance. Both halves are checked on the same corpus and
the same conventions as J.1, in the same script's per-unit pass over the per-item records: over **136**
(configuration × arm × granularity) files the identity
$\rho_{\text{pooled}}-\bar\rho=\operatorname{Cov}(g,r)/\bar g$ with $r_i=(p_i-g_i)/g_i$ holds with a
maximum residual of **$2.2\times10^{-16}$** — a float-level identity, not a fit. The two conventions differ
in **all 136** files, the gap's sign equals the covariance's sign in **136 of 136**, and no file has a zero
covariance. Proposition 2 therefore **describes** the corpus rather than being assumed of it.

## Appendix K. Implementation-span readings behind the §1 evidence

The three implementation-level readings quoted in §1 and F.4 are listed here with their protocol so that
they can be checked against the same rules as every other span in the paper. All three are pooled relative
deviations over the **density-regression input-scale knob**, evaluated on the **common item intersection**
of the compared runs, at the same task, domain and protocol.

| Implementation | Pooled span | levels | Zero-crossing cells | Note |
|---|---|---|---|---|
| Official **DM-Count** weights | **20.1–34.3 pp** | 5 | 3/4 | common item intersection; the implementation of record |
| Official **P2PNet** weights | **10.1 pp** | 5 | — | official weights, same protocol |
| A superseded reproduction of the same CSRNet architecture | **107.0–1432.9 pp** | 5 | 3/4 | **implementation defect**, not a paradigm difference; retained only as the reason the Abstract and §6.1 report the implementation effect as 2–3.4× across official implementations |

The ratio quoted in Appendix M.17 (5–42×) is the ratio between the last row and the official rows; it is a
statement about **implementation quality within one architecture family**, and the paper does not use it to
argue that density regression is intrinsically less directionally controllable. The same distinction is
applied in F.4, where the official-implementation effect is reported as **2–3.4×** and the defective
reproduction is labelled as the cost of an implementation defect.

## Appendix L. Per-property numbers for §1

The four statements in §1 are summarised without their numbers; the numbers themselves are given below verbatim, and each also appears where it is first used in §5.

Measured, that ratio is **550.6 : 1** for
Qwen3-VL-32B, unbounded for Qwen3-VL-8B and Qwen2.5-VL-7B (no refusals at all), and only **2.3 : 1** for
InternVL2.5-8B. The indicator is complete for the Qwen family — the source of all our abstention
headlines — and covers only about **70%** for InternVL, so **cross-lineage comparison requires
lineage-specific channel definitions** (§3.6).

A further consequence is that the
abstention rate rises steeply with ground truth (27.5% → 85.7%, $r = +0.490$), flipping the slope of the
"relative deviation vs. GT" relation between conventions (**−0.00051 → +0.00037**) — so much of the
reported "negative saturation slope" on dense domains is manufactured by abstention (§5.11).

### L.1 Scale contrast details for §5.9

The 32B abstention amplitude is **7.4–7.5×** larger than the 8B's and its directional span 2.5–3.1×
larger. Comparing 8B and 32B alone suggests that scale enables zero crossing, but the smallest
configuration (Qwen2.5-VL-7B) crosses in **2/5** units exactly as the 32B does, while both 8B
configurations cross in **0/5**.

## Appendix M. The channel is set by the output contract: the discriminating experiment (E1)

### M.1 Design and comparability

The corpus leaves one question open: an answered zero may be an abstention, or a genuine estimate of
zero. E1 makes the channel an experimental variable. The sample is the items on which the corpus
configuration answered exactly 0 — **103** on ShanghaiTech-A (ground truth 138–797) and **180** on
UCF-QNRF (137–2075) — from which **40 per domain** are drawn at equal spacing after sorting by ground
truth. Sampling is deterministic, so all configurations and all arms share the same 40 items per
domain; frame membership, duplicate keys and out-of-frame rows were checked file by file (40/40, no
duplicates). Arms: `base` (the corpus prompt, unchanged), `permit` (explicitly allowed to answer
`abstain`), `bestA`/`bestB`/`bestC` (abstention forbidden and a best estimate demanded, three
phrasings), and `channel` (an explicit three-way option: a number, `cannot_judge`, or `no_people`).
The `base` and `permit` arms carry five repeats per item.

Comparability was verified rather than assumed: the `base` prompt, the image encoding (JPEG q92), the
parsing and the output columns are reused verbatim from the corpus runner, and the `base` prompt was
compared **codepoint by codepoint** against it (identical). Hosted calls use temperature 0,
`max_tokens` 128, with exponential backoff on 429/5xx. **The comparison is at the level of
configurations, not of precision**: the corpus ran a 4-bit `compressed-tensors` AWQ checkpoint on
vLLM 0.29.0, while the hosted endpoints differ in **both** weight precision and serving engine, so E1
establishes configuration dependence without attributing it to either cause.

### M.2 All 48 cells

Counts are over successful calls; `ERR` counts the 429-driven failures, which are excluded from every
rate below rather than counted as abstentions.

| model | ds | arm | rows | valid | ERR | answered 0 | median pred/gt | pooled dev |
|---|---|---|---|---|---|---|---|---|
| `qwen3-vl-235b-a22b-instruct` | st_a | base | 240 | 237 | 3 | 0 | 0.670 | -13.9% |
| `qwen3-vl-235b-a22b-instruct` | st_a | bestA | 40 | 39 | 1 | 0 | 7.519 | 719.8% |
| `qwen3-vl-235b-a22b-instruct` | st_a | bestB | 40 | 40 | 0 | 0 | 8.040 | 732.6% |
| `qwen3-vl-235b-a22b-instruct` | st_a | bestC | 40 | 39 | 1 | 0 | 9.452 | 1471.7% |
| `qwen3-vl-235b-a22b-instruct` | st_a | channel | 40 | 39 | 1 | 0 | — | — |
| `qwen3-vl-235b-a22b-instruct` | st_a | permit | 240 | 236 | 4 | 0 | — | — |
| `qwen3-vl-32b-instruct` | st_a | base | 240 | 240 | 0 | 76 | 0.635 | -34.3% |
| `qwen3-vl-32b-instruct` | st_a | bestA | 40 | 40 | 0 | 0 | 6.354 | 676.9% |
| `qwen3-vl-32b-instruct` | st_a | bestB | 40 | 40 | 0 | 0 | 6.017 | 521.8% |
| `qwen3-vl-32b-instruct` | st_a | bestC | 40 | 40 | 0 | 0 | 4.263 | 400.8% |
| `qwen3-vl-32b-instruct` | st_a | channel | 40 | 40 | 0 | 0 | — | — |
| `qwen3-vl-32b-instruct` | st_a | permit | 240 | 240 | 0 | 0 | — | — |
| `qwen3-vl-8b-instruct` | st_a | base | 40 | 40 | 0 | 0 | 0.276 | -75.7% |
| `qwen3-vl-8b-instruct` | st_a | bestA | 40 | 40 | 0 | 0 | 2.463 | 307.2% |
| `qwen3-vl-8b-instruct` | st_a | channel | 40 | 40 | 0 | 0 | — | — |
| `qwen3-vl-8b-instruct` | st_a | permit | 40 | 40 | 0 | 0 | — | — |
| `qwen3-vl-flash` | st_a | base | 40 | 40 | 0 | 0 | 0.990 | 37.6% |
| `qwen3-vl-flash` | st_a | bestA | 40 | 40 | 0 | 0 | 6.868 | 875.5% |
| `qwen3-vl-flash` | st_a | channel | 40 | 40 | 0 | 0 | — | — |
| `qwen3-vl-flash` | st_a | permit | 40 | 40 | 0 | 0 | — | — |
| `qwen3-vl-plus` | st_a | base | 40 | 40 | 0 | 0 | 0.627 | -36.8% |
| `qwen3-vl-plus` | st_a | bestA | 40 | 40 | 0 | 0 | 7.689 | 1123.6% |
| `qwen3-vl-plus` | st_a | channel | 40 | 40 | 0 | 0 | — | — |
| `qwen3-vl-plus` | st_a | permit | 40 | 40 | 0 | 0 | — | — |
| `qwen3-vl-235b-a22b-instruct` | ucf | base | 240 | 238 | 2 | 1 | 0.573 | -18.1% |
| `qwen3-vl-235b-a22b-instruct` | ucf | bestA | 40 | 39 | 1 | 0 | 4.315 | 906.9% |
| `qwen3-vl-235b-a22b-instruct` | ucf | bestB | 40 | 39 | 1 | 0 | 4.704 | 778.3% |
| `qwen3-vl-235b-a22b-instruct` | ucf | bestC | 40 | 39 | 1 | 0 | 6.903 | 1340.0% |
| `qwen3-vl-235b-a22b-instruct` | ucf | channel | 40 | 39 | 1 | 0 | — | — |
| `qwen3-vl-235b-a22b-instruct` | ucf | permit | 240 | 237 | 3 | 0 | — | — |
| `qwen3-vl-32b-instruct` | ucf | base | 240 | 240 | 0 | 62 | 0.691 | -38.0% |
| `qwen3-vl-32b-instruct` | ucf | bestA | 40 | 40 | 0 | 0 | 4.480 | 622.2% |
| `qwen3-vl-32b-instruct` | ucf | bestB | 40 | 40 | 0 | 0 | 4.002 | 438.9% |
| `qwen3-vl-32b-instruct` | ucf | bestC | 40 | 40 | 0 | 0 | 3.787 | 415.7% |
| `qwen3-vl-32b-instruct` | ucf | channel | 40 | 40 | 0 | 0 | — | — |
| `qwen3-vl-32b-instruct` | ucf | permit | 240 | 240 | 0 | 0 | — | — |
| `qwen3-vl-8b-instruct` | ucf | base | 40 | 40 | 0 | 2 | 0.002 | -94.5% |
| `qwen3-vl-8b-instruct` | ucf | bestA | 40 | 40 | 0 | 0 | 2.565 | 269.8% |
| `qwen3-vl-8b-instruct` | ucf | channel | 40 | 40 | 0 | 0 | — | — |
| `qwen3-vl-8b-instruct` | ucf | permit | 40 | 40 | 0 | 0 | — | — |
| `qwen3-vl-flash` | ucf | base | 40 | 40 | 0 | 0 | 0.654 | -1.3% |
| `qwen3-vl-flash` | ucf | bestA | 40 | 40 | 0 | 0 | 6.135 | 873.0% |
| `qwen3-vl-flash` | ucf | channel | 40 | 40 | 0 | 0 | — | — |
| `qwen3-vl-flash` | ucf | permit | 40 | 40 | 0 | 0 | — | — |
| `qwen3-vl-plus` | ucf | base | 40 | 40 | 0 | 0 | 0.501 | -41.2% |
| `qwen3-vl-plus` | ucf | bestA | 40 | 40 | 0 | 0 | 7.255 | 1145.6% |
| `qwen3-vl-plus` | ucf | channel | 40 | 40 | 0 | 0 | — | — |
| `qwen3-vl-plus` | ucf | permit | 40 | 40 | 0 | 0 | — | — |

### M.3 Answered zeros by configuration (`base` arm)

| configuration | st_a: answered 0 | ucf: answered 0 |
|---|---|---|
| `qwen3-vl-235b-a22b-instruct` | 0/237 = 0.0% | 1/238 = 0.4% |
| `qwen3-vl-32b-instruct` | 76/240 = 31.7% | 62/240 = 25.8% |
| `qwen3-vl-8b-instruct` | 0/40 = 0.0% | 2/40 = 5.0% |
| `qwen3-vl-flash` | 0/40 = 0.0% | 0/40 = 0.0% |
| `qwen3-vl-plus` | 0/40 = 0.0% | 0/40 = 0.0% |

### M.4 The abstention arms and the forbidden-abstention arms

| arm | valid calls | explicit abstentions | answered 0 |
|---|---|---|---|
| `permit` | 1193 | 1193 (100.0%) | 0 |
| `channel` | 398 | 398 (100.0%) | 0 |
| **total** | **1591** | **1591 (100.0%)** | **0** |

In the **18** forbidden-abstention cells there are **no** answered zeros and **no** refusals, and the
median predicted/true ratio runs **2.463–9.452** — i.e. forbidding abstention does not produce small
numbers, it produces systematic **over**-estimation.

**The caliber of that interval, stated once because two calibers live in this appendix.** `2.463–9.452`
is the **per-item median** of $\text{pred}/\text{gt}$ over the items of a cell (the column headed
`median pred/gt` in the table above). It is **not** the **pooled** deviation
$\rho=100\,(\sum\text{pred}-\sum\text{gt})/\sum\text{gt}$, which is the caliber of the `pooled` column and
of §M.2's summary table; the same cells give pooled values of **269.8%–1471.7%**, i.e. an order of
magnitude larger, because a pooled ratio is dominated by the highest-count items. The two are neither
interchangeable nor comparable, and quoting one without its caliber is exactly the failure mode §4.1
corrects for the detector ladder — so the main text says "per-item median" explicitly and both columns are
printed above.

### M.5 The corpus already contains the same structure

The corpus varies the prompt's permission to be conservative, and the answered-zero rate follows it
monotonically (**832** items per arm):

| prompt arm | instruction | answered 0 | st_a | st_b | ucf |
|---|---|---|---|---|---|
| `over` | count every possible target | **0/832 = 0.0%** | 0/182 | 0/316 | 0/334 |
| `base` | neutral | **283/832 = 34.0%** | 103/182 | 0/316 | 180/334 |
| `under` | count only what you can fully confirm | **519/832 = 62.4%** | 171/182 | 43/316 | 305/334 |

The arm instructed to include every possible target produced **no** answered zeros at all, over 832
items — the same mechanism, visible inside the original corpus and independent of E1.

### M.6 The runner's parse branch is dead, with zero measured impact

The corpus runner's pattern expects the object key **unquoted** — an opening brace, optional
whitespace, the key `count` (or one of the runner's non-English synonyms for that key), a colon and a
digit run — whereas the prompt asks for `{"count": N}`; the structured branch therefore never matches
and
every stored value comes from the fallback "first integer anywhere in the response". A row-by-row audit
of all **2496** rows of the three-arm prompt experiment (832 items x 3 arms) shows the two readings agree in **2496** rows, with **0**
rows containing no digit at all and **0** rows where the JSON value could not be recovered;
all **802** answered zeros are literally `{"count": 0}`. The defect is therefore real but has
**no** effect on the released values, and it independently rules out a parsing artefact as the origin
of the zeros. **The same defect, with the opposite sign of consequence, is recorded twice more**: on the exit arms the abstention token contains no integer, so it is stored as a *parse failure* rather than as a value (M.31.6, M.19.12(e)). The boundary between the two readings is exactly whether the reply contains a digit — documented, not incidental.

### M.7 What E1 establishes, and what it does not

**Established.** (i) On the items the corpus answered 0, an answered zero is not what these
configurations do when an alternative is available: **1591/1591** successful calls abstained
explicitly and none answered 0. (ii) The zero does not require the quantised local deployment — the
hosted checkpoint of the corpus configuration reproduces it on **25.8–31.7%** of the same items — and
is not a universal family behaviour, since `plus`, `flash` and `235b` answer 0 on **0–0.4%**. (iii) A
zero is not a failed estimate: with abstention forbidden the model over-estimates by a median of
**2.463–9.452×** rather than approaching zero. (iv) The corpus's own `over` arm, instructed to
include everything, produced no answered zeros in **832** items.

**Not established.** The re-query confounds weight precision with serving engine; the item set is
selected for having been answered 0, so a genuine estimate of zero outside it is not excluded; and the
experiment covers the dense crowd domains only, not the aerial ones.

### M.8 Numeric detail for §§5.8, 5.9, 5.10, 7.4, 7.6 and 5.11


These are the per-cell numbers behind the corresponding claims in the main text; the
claims themselves remain in the main text with a pointer to this subsection.

**§5.8.** Across seven prompt-strength levels the accepted integer set contracts and its mean is pushed
toward zero, the extreme level driving abstention to **94.0% / 91.3%** on two configurations — the knob
acts on the distribution of the emitted value rather than on a perception threshold.

**§5.8 (Route A: the prompt knob is gated, not disabled).** On the aerial domain the loosest of the seven
prompt-strength levels moves $\rho$ from **+13.9%** at whole image to **+160.4%** at 3×3 — an **11.5×**
amplification — while the neutral level moves from **−71.3%** to **−17.7%** and the abstention rate falls
from **68.2%** to **31.8%**. The knob is therefore suppressed by the whole-image legibility limit rather
than inactive, which is what Route A means by *preserves accuracy while raising legibility*. Both aerial
figures are the canonical filtered-caliber value; the superseded unfiltered figure for that cell was
**+1277.6%**, driven by a single item with a predicted count of **100,025** against a ground truth of
**24** — which is why the filter is stated alongside the number rather than assumed. Recomputed from the
frozen per-item dose records in `dose_routeA_visdrone.py`, which also reproduces the whole-image **36.5%**
abstention at the loosest level and the **11.5×** ratio.

**§5.9.** Answered-only relative deviation: ShanghaiTech-A **−67.5%** (8B) vs. **−19.8%** (32B);
UCF-QNRF **−69.7%** vs. **−29.2%**.

**§5.10.** 2×2 tiling lowers VisDrone abstention from **68.2%** to about **47%**, against the crowd
domain's **56.6% → 6.0%**.

**§5.10 (arms).** The *over* arm reaches only **−56.3% / −66.3%** on the two aerial domains.

**§7.4.** Aerial: the in-domain ladder moves $\rho$ from **+109.4%** to **−86.3%** (person-matched;
under the all-detections convention **+507.4% → −0.9%**). Dense crowds: no
lineage reaches `pred/gt ≥ 1` at any threshold and the span collapses to **6–19 pp**. Training-domain
swap alone: **55.5 → 195.7 pp** (3.5×). Zero-shot COCO detectors move from 2/3 to 0/3 zero-crossing
units once model-appropriate matching is applied.

**§7.5.** `choice` moves the relative deviation across zero by **+238.4 pp** while the abstention rate
moves by **0.08 pp**. `forbid0`: ShanghaiTech-A **+115.6 pp**, UCF **+76.0 pp**, BBBC005 **+0.6 to +5.8 pp**.

**§5.11(a).** The dual-convention gap is **61.3 pp** (ShanghaiTech-A), **57.5 pp** (UCF) and **40.6 pp**
(AI-TOD and VisDrone).

### M.9 Numeric detail for §§4.1, 4.3, 4.7, 5.5, 7.3 and 7.9

Per-cell numbers behind the corresponding main-text claims, moved verbatim; each
claim remains in the main text with a pointer here.

**§4.3.** Across the ladder **21
configurations are reachable and 5 are not**, with reachable $\tau^\*$ values in **0.021–0.259**; the full
table is in Appendix E.1. The essential qualification is that **the unreachable configurations are not
marginally out of reach** — the minimum $\lvert$ME$\rvert$ is **140.9–141.1** for ShanghaiTech-A and
**543.1** for whole-image UCF. This converts "unreachable" from "a little more tuning would do" into **the
absence of directional controllability under $\tau$ for that configuration**.

**§4.1.** The reason is measurable: the **highest** `pred/gt` reached
anywhere on the $\tau$ ladder is **1.004 / 1.688 / 2.094** for the in-domain YOLO weights but only
**0.179 / 0.339 / 0.631** for the same architecture with COCO-pretrained weights, and on the dense domains
COCO detectors reach only **≈ 0.10–0.21** at any threshold. Reachability therefore has a checkable criterion (**Fig. 3**) — is `pred/gt ≥ 1` attained at the lowest threshold? —
which gives **zero exceptions** across three lineages and nine cells.

**§4.7.** Decomposing the cascade error on a safety-helmet task
into a user-side error $\delta_U$ and a head-level error $\delta_H$ with total $\delta_T$, and locating
both zeros on **the same 12,066 images** (the full cleaned corpus, of which the 6,033 of §4.7 are the held-out split), gives $\tau^\*(\delta_U = 0)$ in **0.0980–0.1106** and
$\tau^\*(\delta_T = 0)$ in **0.2142–0.2347** across three source-domain weight sets (Appendix E.5). **The two differ by a factor of about 2.1–2.3 and their intervals do not overlap**, so quoting one number
is not reproducible. **Each zero is individually stable** (ranges only **0.0126** and **0.0205** across
three weight sets), so §4.1's domain conditionality is consistent with a stable zero *within* a domain.

**§7.3.** Only one split
separates, by **1.6 pp**, at $p \approx 0.008$ before correction — which neither the paper's own noise
floor (**2.15–6.46 pp**) nor the nine enumerated split points allows us to treat as established (the
arithmetic, including the $0.075$ corrected value, is in Appendix F.7). We therefore report the
separable low-response cluster as a **candidate structure** rather than an established partition, and we
retain **one low-response cluster** (VLM pixel budget, ≤ 22.4 pp) alongside an **internally
continuous high-response spectrum** (33.5–150.7 pp, from F.9's **transcribed** column) — and explicitly **not** two anchor zones or
bimodality, since with four knob **sides** collapsed into ten units a bimodality test has very low power.

**§5.5.** Across the other arms the same quantity runs from **42.5%** — ShanghaiTech-B under the `under` arm, a cell
whose abstention rate is itself only 13.6% — to **99.4%** (ShanghaiTech-A, `under` arm); the `over` arm has **0%** — its prompt requires every
possible target to be counted, so it never abstains — and the dense `base` cells sit at
**93.7–94.2%**. The same abstention **rate** under the item-count convention is 53.9–68.2% — under that
convention an abstained item contributes $pred=0$, so this term is **identically** the abstention rate itself
(the last column of Table 3), which is why it is printed as a positive percentage while the ground-truth-weighted
term beside it is negative. The
two differ by **38–40 pp** on ShanghaiTech-A and UCF, which is why both must be reported. Case-resampling the per-item records (2,000 draws, seed 20260924, the convention of §7.3) puts $S$ at **90.8–97.0%** on ShanghaiTech-A and **91.2–96.0%** on UCF-QNRF. (*Reproduction: a released resampling script.*) Setting refusals
aside entirely, the answered-only relative deviation is only **−19.8%** and **−29.2%** — these models are
much closer to unbiased than the aggregate suggests.

### M.11 Numeric detail for §4, §5 and §6

Per-cell numbers behind the corresponding main-text claims, moved verbatim; every
claim sentence remains in the main text with a pointer here.

**5.7 Abstention and under-counting are two separable failure modes.** Its signature is severe output degeneracy:
the number of unique predicted values per configuration has a median of only **17–23** (range 9–29)
against hundreds of distinct ground-truth values — abstention is the extreme point of this collapse. **The channel is set by the output contract, not by the lineage (E1).** On the 40 items per dense
domain that the corpus configuration answered exactly 0, four further configurations were queried
under identical prompts. Given an explicit abstention option, **1591 of 1591** successful calls
abstained explicitly and **none** answered 0; forbidding abstention produced **no** zeros and **no**
refusals but a median of **2.463–9.452×** the true count, so a zero is neither a failed estimate nor
a small one. The zero reappears only under the numeric-only contract, and then only for part of the
family: the corpus-matched hosted checkpoint answers 0 on **25.8–31.7%** of these items, whereas
`plus`, `flash` and `235b` answer 0 on **0–0.4%**.

**5.6 Causal attribution of abstention: count beyond legibility.** On
**count-controlled synthetic grids**, changing only arrangement and blur drives abstention from 0% to
90%. **Across domains**, the raw association between abstention and target count is weak ($r = +0.33$;
ShanghaiTech-B with 124 targets abstains at 0% while VisDrone with 22 abstains at 68%) — but a raw
association cannot separate count from legibility. And **within a grid**, holding count,
size and blur fixed and varying only arrangement: dispersed gives 0% abstention and $\rho = -58\%$,
clustered gives 90% and $\rho = -100\%$ — a 90 pp jump in abstention and 42 pp in bias from arrangement
alone. **Once legibility is held fixed, count's role remains clearly visible**; the earlier reading that
count has no material effect is therefore **withdrawn** (new synthetic-dot experiment, §M.11.1).

**7.2 Same-scale accuracy comparison across the three families.** **Density regression attains the highest accuracy** on all three datasets once the scale
protocol is matched — 71.3 / 221.3 / 9.8 against 220.5 / 287.3 / 31.2 for detection and 201.7 / 284.3 /
33.2 for the 32B VLM. **Its reliability is the lowest**: across eleven usable weight sets for the same
architecture and data, MAE differs by **5.4–13.6×**. **Detection is the best value**, within roughly
1.6–3× of the best density regression while offering a directional knob.

**7.6 Language-side contracts: channel independence, and one excluded branch.** And **`forbid0` is the strongest directional contract in dense domains** yet nearly inert on BBBC005 [48] (*per-arm values in Appendix M.8*). **The cause of that boundary is not "no answered zero left to rewrite"** (see §7.6: after tiling drives
the 32B abstention rate from **56.6%** to **0.0%** (2×2: 6.0%, 3×3: 0.55%), the effect is essentially unchanged,
**+185 → +195 → +167 pp**).

**5.9 Model scale: what is bought is knowing whether to answer.** What scale changes is **abstention** — the 32B model abstains where
the 8B answers confidently and wrongly. **The ability to cross zero does not emerge with scale**: a
Qwen2.5-VL-7B configuration — the smallest — crosses in **2/5** units exactly as the 32B does, while both
8B configurations cross in **0/5**.

**1. Introduction.** Counting
evaluation, however, reports **symmetric magnitude** metrics — MAE, RMSE and their normalised forms —
for which counting 100 objects as 50 and as 150 are indistinguishable, although the two are not
interchangeable in any deployment decision.

**2.8 Crowded-scene occlusion counting.** The separation is
measured here: when the occluded position **can** be inferred the abstention rate equals the unoccluded
control exactly (both 0%), and when it cannot the rate rises to **60–90%**.

**5.8 The two routes to removing abstention, and their price.** **Route B — relaxing the prompt (bypass
legibility; destroys accuracy)** also drives abstention from **53–57%** to zero, but flips $\rho$ from
**−82%** to **+234%…+345%** (canonical convention, anomalies removed).

**5.10 Aerial domain: the legibility extreme.** Whole-image abstention rates are **68.2%** and **68.1%**,
and **none** of the three arms moves the direction positive — the opposite of the crowd domain.

### M.11.1 New synthetic-dot experiment: count visible under a legibility control

**Status: a newly run experiment, reported here for the first time.** It is **not** the corpus grid of
§C.2 and it is **not** the source of any other number printed in this paper.

**Stimulus (synthetic).** A full **3⁴ factorial** over count × dot radius (size) × blur × overlap factor
gives **81 cells**, **8 layouts per cell ⇒ 648 rendered images**. **3 cells were pre-registered as
unrealizable** (`_unrealizable.csv`: one where the blurred small dots merge into no discernible blob,
two where 80 targets do not fit at the required minimum spacing) and are excluded **before any analysis — from the C1 non-empty check *and* from the C3/C4/C5/NC3 fits**, leaving **78 non-empty cells = 11,232 records** (the previously printed 11,664-record readings included the three excluded cells and are reported below as the contrast caliber). Count is therefore pushed to its extremes (8 / 32 / 80 dots) while
legibility (radius, blur, overlap) is varied orthogonally — exactly the contrast the corpus panel of
§5.6 could not isolate. The stimulus is **synthetic dots**, rendered on a different platform, and is an
**independent stimulus** from the 675-image grid of §5.6 / §C.2; its readings **must not be differenced
against those already-printed numbers**.

**Implementations: two, not four.** Only **b0 = AWQ 4-bit** and **b2 = BF16** were run. **No same-family
FP8 and no same-family GPTQ weights exist in this environment** ⇒ the pre-registered four-build budget
was **shrunk before the run started**, and this must **not** be described as a "four-build" experiment.
Build variance is estimated on **two levels only**; the `count × build` term for b2 is not significant in
either caliber (**−0.2083**, p = 0.408 on the primary n = 11,232; **+0.1920**, p = 0.418 on the contrast
n = 11,664).

**Design and budget (post-shrink).** 3 output contracts (base / strict / permit) × 3 independent service
starts = **18 cells × 648 items = 11,664 calls**, **0 aborts**.

| | pre-registered | as run (shrunk before start) |
|---|---:|---:|
| implementations | 4 (b0, b1, b2, b3) | **2 (b0 = AWQ 4-bit, b2 = BF16)** |
| cells | 36 | **18** |
| service starts | 12 | **6** |
| calls | 23,328 | **11,664** |

**Criterion C4 read out: FAIL ⇒ the "count has no material effect" reading is withdrawn.** Two
regressions are reported with the **same** legibility covariates (size, blur, overlap, in the ordinal
`*_level` coding registered in the frozen criteria file) and the same contract/build terms; they differ
**only in the record set** — **primary = whole-cell exclusion of the three pre-registered unrealizable
cells (n = 11,232)**; **contrast = including them (n = 11,664, the caliber printed in the previous release)**.

**Primary caliber (whole-cell exclusion, n = 11,232):**

| term | β | SE | z | p | Wald 95% CI |
|---|---:|---:|---:|---:|---|
| `count_std` (main effect) | **−4.2059** | 0.2248 | −18.71 | ~0 | **[−4.6465, −3.7653]** |
| `count_std × strict` | −0.4224 | 0.2677 | −1.58 | 0.115 | [−0.9471, 0.1023] |
| `count_std × permit` | **−3.4937** | 0.5504 | −6.35 | 2.2e−10 | [−4.5725, −2.4149] |
| `count_std × b2` | −0.2083 | 0.2519 | −0.83 | 0.408 | [−0.7019, 0.2854] |

**Contrast caliber (including the three excluded cells, n = 11,664)** — the readings printed in the previous release. They are **not superseded or withdrawn**: they are the correct readings of the same records under that caliber, retained here for comparability, and **both calibers FAIL C4**.

| term | β | SE | z | p | Wald 95% CI |
|---|---:|---:|---:|---:|---|
| `count_std` (main effect) | **−4.3696** | 0.2229 | −19.60 | ~0 | **[−4.8066, −3.9327]** |
| `count_std × strict` | −0.3183 | 0.2577 | −1.24 | 0.217 | [−0.8235, 0.1868] |
| `count_std × permit` | **−2.1767** | 0.3807 | −5.72 | 1.1e−08 | [−2.9228, −1.4305] |
| `count_std × b2` | +0.1920 | 0.2372 | 0.81 | 0.418 | [−0.2730, 0.6570] |

The pre-registered practical-null band was **±0.2** (`ci_lo > −0.2 AND ci_hi < +0.2`).
**In both calibers the interval lies entirely outside that band — it does not even contain 0 ⇒ C4 FAIL**, with a **negative** sign (more dots, fewer correct answers): the primary interval is **[−4.6465, −3.7653]**, the contrast interval **[−4.8066, −3.9327]**. A layout-clustered bootstrap (8 layouts resampled, B = 500, seed 20261004) on the primary caliber gives **[−6.3291, −2.7775]** (median −4.2571) — the same sign and wider, so this is not a sampling accident. Because C4 failed in both calibers, the pre-registered disposition `verdict_if_fail` applies verbatim: **the claim that count has no material effect is withdrawn**, and §5.6 is rewritten as "count's role remains visible after controlling legibility".

**Pooled by count level — primary caliber (whole-cell exclusion, n = 11,232).**

| count level | correct | rate |
|---|---:|---:|
| 8 | 1870 / 3744 | **49.9%** |
| 32 | 80 / 3888 | **2.1%** |
| 80 | 17 / 3600 | **0.5%** |

**Pooled by count level — contrast caliber (including the excluded cells, n = 11,664; the values printed in the previous release).**

| count level | correct | rate |
|---|---:|---:|
| 8 | 1930 / 3888 | **49.6%** |
| 32 | 80 / 3888 | **2.1%** |
| 80 | 23 / 3888 | **0.6%** |

**Per build × contract — primary caliber (n = 1872 per cell).**

| build | contract | n | correct | rate | abstain | pred = 0 |
|---|---|---:|---:|---:|---:|---:|
| b0 (AWQ 4-bit) | base | 1872 | 326 | **17.41%** | 0 | 656 |
| b0 (AWQ 4-bit) | strict | 1872 | 326 | **17.41%** | 0 | 657 |
| b0 (AWQ 4-bit) | permit | 1872 | 314 | **16.77%** | **933** | 0 |
| b2 (BF16) | base | 1872 | 337 | **18.00%** | 0 | 659 |
| b2 (BF16) | strict | 1872 | 336 | **17.95%** | 0 | 657 |
| b2 (BF16) | permit | 1872 | 328 | **17.52%** | **962** | 0 |

**Per build × contract — contrast caliber (n = 1944 per cell; the values printed in the previous release).**

| build | contract | n | correct | rate | abstain | pred = 0 |
|---|---|---:|---:|---:|---:|---:|
| b0 (AWQ 4-bit) | base | 1944 | 341 | **17.54%** | 0 | 680 |
| b0 (AWQ 4-bit) | strict | 1944 | 341 | **17.54%** | 0 | 681 |
| b0 (AWQ 4-bit) | permit | 1944 | 314 | **16.15%** | **981** | 0 |
| b2 (BF16) | base | 1944 | 353 | **18.16%** | 0 | 683 |
| b2 (BF16) | strict | 1944 | 353 | **18.16%** | 0 | 681 |
| b2 (BF16) | permit | 1944 | 331 | **17.03%** | **1010** | 0 |

`base` and `strict` are **numerically identical** within each build in the contrast caliber (341/341 and 353/353), and differ by at most one item in the primary caliber (326/326 and 337/336): `strict` only adds "output JSON only", and both were already 100% parseable, so it changed almost nothing. In both calibers the `permit` contract converts "answers 0" into "abstains" at a small cost in correctness.

**Independent recomputation.** A separately written parser and analysis (an independent script that **does not import the frozen analyzer**) re-derived the panel from the released per-item records: **C1 PASS, C2 PASS (shrunk accounting), C3 PASS, C4 FAIL, C5 PASS**; the negative controls NC1, NC3 and NC-const all PASS. Reparsing the primary 11,232 rows independently gave **0** disagreements in `parse_ok`, `pred` and the abstain flag (the 11,664-row contrast is likewise 0).

**Two honest registrations (thresholds unchanged).**

1. **Pre-run shrinkage.** The four-build budget (23,328 calls / 36 cells / 12 starts) became
   **11,664 calls / 18 cells / 6 starts**, because FP8 and same-family GPTQ weights do not exist in this
   environment. The shrink happened **before the run began** and is recorded, not hidden.
2. **C2 has two accounting calibers, and both are reported.** The frozen criteria file writes
   `C2_integrity.threshold.total_rows = 23,328`, so the **frozen analyzer, run as-is, returns
   `C2 passed = false`** (the 18 b1/b3 cells are missing). The **independent recomputation judges C2
   PASS** on the attained **18 × 648 = 11,664** rows (per-cell `parse_ok` = 1.000 for 18/18 cells, no
   short cells, `http_err` = 0). Neither caliber is suppressed: the PASS caliber reflects the experiment
   that was actually run, the FAIL caliber reflects the pre-registered threshold.

**Provenance (md5).** criteria `758962a2643e1035698682abefec5748`; stimulus generator
`edd4a9708cf97ece4d376964a72160d3`; probe `2f9d53cd3098990aa29b69e4946de2b0`; frozen orchestration
`a93ecd519341fba79bb7d993eb6641b8`; revised orchestration driver script
`7fa412d96c6a21717d946a287156403c`; analyzer `77f87f49b0e447fba54ea2a0435f80c8`; official stimulus lock
`stim/manifest.csv` = `d2dde2a8100eca8eda88143f6cbb04ba`, with `manifest_sha256.txt` **648/648 OK**;
stimulus config `e6adaa4825c90fe4574e0c11a877f994`; run log (ALL_DONE) `5ed9aeb00b96799d47f5ba1ff82dc415`.
Released under two `data/derived/` subdirectories, each listed in `MANIFEST.csv`.

### M.14 Numeric detail for §§6.2, 7.7 and 7.9

Per-cell numbers behind the corresponding main-text claims, moved verbatim.

**§7.7.** Its boundary must be stated at the same time: across ten independent family × dataset
combinations, restricting to the most legible 20% leaves $\lvert\rho\rvert$ reduced to a median retention
ratio of **0.69** (range **0.61–0.83**), never to zero.

### M.16 Detail for §§4–7

Moved verbatim; the topic sentence and every claim sentence remain in the main text. **§4.5 Tile granularity: a third knob, which can turn unreachable into reachable.** First, **tile granularity can rescue an
unreachable configuration**: ShanghaiTech-A is unreachable for YOLO at tile-1024 (min
$\lvert$ME$\rvert$ = **141.1**) but reachable from **tile-512** ($\tau^\*$ = 0.260), and for RetinaNet it
is unreachable even at tile-1024 (**244.3**) and becomes reachable only at **tile-512** (0.124). "This
domain is unreachable" is therefore not an absolute property of the domain but a **joint property of
{domain × input protocol}**. Second, **the two families unseal at different granularities**: RetinaNet, a
pre-FPN architecture, needs finer tiling than YOLO to unseal the same domain.

**7.6 Three mechanism hypotheses, tested and excluded.** **Synthetic reproduction — fails**: the effect is **+124 to +248 pp** on crowd images against only
**+20 pp** on synthetic discs even at $\sigma = 0$, a tenfold difference. **Overlap/occlusion — not
supported**: a 2×2×4×10 factorial decoupling crowding from size gives $\Delta = +0.3$ pp in the critical
cell. 

### M.17 Detail for §1, §6.2 and §7.3

Moved verbatim; every claim sentence remains in the main text.

**§1 supporting result.** Three independent pieces of evidence: official DM-Count
weights give **20.1–34.3 pp** and official P2PNet **10.1 pp** within one task, domain, protocol and item
intersection, whereas a retired reproduction of the same CSRNet [44] architecture gives **107–1433 pp** on the
same ladder — a **5–42× implementation difference within one architecture family** (per-implementation readings and protocol in Appendix K; this is the cost of an implementation defect, not a paradigm difference); the same detection architecture under a
training-domain swap changes span from **55.5 pp** to **195.7 pp** (**3.5×**); and "side of action" does
not predict span.

### M.18 The expanded channel experiment (E2): a census over six domains and fourteen configurations

E1 (§M.1–M.7) establishes that the *channel* is set by the output contract on two dense domains with
40 items per domain and hosted endpoints. E2 repeats the design **on locally served open weights, as a
census rather than a sample**, adds the two aerial domains and the cross-lineage and quantisation
variants, and adds three arms that separate the two candidate causes of a refusal. Everything below is
recomputed from the raw result CSVs; the analysis scripts and the verification script that asserts
every number in this appendix are listed in §M.18.7.

#### M.18.1 Design, and the three added arms

| Item | Setting |
|---|---|
| Serving | `vLLM` 0.29.0, one H20 (97,871 MiB), temperature 0, `max-model-len` 8192, one image per prompt, `--workers 8` |
| Contracts | `base` (the corpus prompt, unchanged), `permit` (allowed to answer `abstain`), `bestA` / `bestB` / `bestC` (abstention **forbidden**, a best estimate demanded, three phrasings), `channel` (three options: a number, `cannot_judge`, `no_people`) |
| Added arms (E2) | `enum` — **requires per-instance enumeration** ("find every person one by one and count them") but exposes only a numeric field; `locate` — requires localisation ("locate every person"), numeric field only; `enumAbstain` — the **same** enumeration demand **plus** an abstention token |
| Domains | st_a (ShanghaiTech-A), st_b (ShanghaiTech-B), ucf (UCF-QNRF), visdrone (VisDrone), aitod (AI-TOD); countbench is **excluded** (see §M.18.6) |
| Configurations | 14, spanning Qwen3-VL 2B/4B/8B/30B-A3B(MoE)/32B and Qwen2.5-VL 7B/72B, InternVL2.5-8B and InternVL3.5-38B, in AWQ-4bit, AWQ-8bit, GPTQ-W4 [41], FP8 and BF16 builds |
| Two pools | **zero pool** = items that the domain's corpus configuration answered exactly 0; **non-zero pool** = items it answered with a number, so the two pools are complementary within a domain |
| Comparability | `base` prompt, image encoding, parsing and output columns reused verbatim from the corpus runner; the image encoder and parser are the same as E1's; sampling is **fixed-seed**, so every configuration at a given `--n` receives the **same items** (checked by set intersection, all pairs identical), and the 150-item sample is a subset of the full pool (VisDrone 273, AI-TOD 154) |

#### M.18.2 The decisive arm comparison: the gate is the abstention token

Two configurations × four domains. "Zeros" is the answered-zero count; "refusals" is the count of
explicit abstention outputs; `n` is the pool size. `enum` and `locate` **require** per-instance work but
expose only a number; `enumAbstain` keeps that demand and adds one abstention token.

| config | domain | n | `base` zeros | `enum` zeros (refusals) | `locate` zeros (refusals) | `enumAbstain` zeros (refusals) | `permit` refusals |
|---|---|---|---|---|---|---|---|
| Qwen3-VL-32B-AWQ-4bit | st_a | 103 | 102 | 92 (**0**) | 99 (**0**) | 0 (**103**) | 103 |
| Qwen3-VL-32B-AWQ-4bit | ucf | 180 | 166 | 159 (**0**) | 155 (**0**) | 0 (**180**) | 180 |
| Qwen3-VL-32B-AWQ-4bit | visdrone | 273 | 268 | 258 (**0**) | 263 (**0**) | 4 (**268**) | 273 |
| Qwen3-VL-32B-AWQ-4bit | aitod | 154 | 149 | 136 (**0**) | 136 (**0**) | 15 (**133**) | 152 |
| Qwen3-VL-32B-BF16 | st_a | 103 | 64 | 103 (**0**) | 86 (**0**) | 0 (**103**) | 103 |
| Qwen3-VL-32B-BF16 | ucf | 180 | 120 | 180 (**0**) | 119 (**0**) | 0 (**180**) | 180 |
| Qwen3-VL-32B-BF16 | visdrone | 273 | 254 | 254 (**0**) | 262 (**0**) | 4 (**266**) | 273 |
| Qwen3-VL-32B-BF16 | aitod | 154 | 143 | 137 (**0**) | 143 (**0**) | 19 (**129**) | 152 |

Three readings, all of them first-person and all on identical items:

1. **Requiring per-instance enumeration does not produce refusals.** Across all eight cells the
   `enum` and `locate` arms produce **zero explicit refusals**; the answered zeros persist at roughly
   `base` levels (in one cell, BF16 on ucf, `enum` raises them from 120 to 180).
2. **Adding one abstention token to the same demand does.** `enumAbstain` moves 98–100% of the pool
   into explicit refusal (e.g. 268/273 on VisDrone).
3. **Relaxing the demand without adding a token does not.** On VisDrone the `bestA` arm — which
   explicitly permits imprecision — leaves the answered-zero count **unchanged** (121 → 121 on
   Qwen2.5-VL-72B-AWQ) or slightly higher (232 → 235 on Qwen3-VL-4B), whereas `permit`, which adds
   only the token, clears it to 0.

**Median predicted/true ratio on the zero pool** (identical items within a domain; rows are the two
32B builds of one checkpoint). This is the table behind the main text's §7.6 corroboration: forbidding
the zero does not determine the direction.

| config | domain | `base` | `bestA` | `bestB` | `bestC` |
|---|---|---|---|---|---|
| Qwen3-VL-32B-AWQ-4bit | st_a | 0.000 | 6.281 | 5.155 | 4.854 |
| Qwen3-VL-32B-AWQ-4bit | ucf | 0.000 | 5.168 | 4.487 | 4.045 |
| Qwen3-VL-32B-AWQ-4bit | visdrone | 0.000 | 0.000 | 0.250 | 0.469 |
| Qwen3-VL-32B-AWQ-4bit | aitod | 0.000 | 0.062 | 0.500 | 0.833 |
| Qwen3-VL-32B-BF16 | st_a | 0.000 | 5.365 | 4.500 | 4.027 |
| Qwen3-VL-32B-BF16 | ucf | 0.000 | 4.921 | 3.949 | 3.458 |
| Qwen3-VL-32B-BF16 | visdrone | 0.000 | 0.000 | 0.333 | 0.500 |
| Qwen3-VL-32B-BF16 | aitod | 0.000 | 0.171 | 0.511 | 0.662 |

The three arms that forbid the zero all overshoot on the dense domains (**3.5–6.3×**) and all remain
**below 1** on the aerial domains: the same contract change produces over-estimation in one domain and
continues to under-estimate in the other.

*The three added arms were run for the two 32B configurations on all four domains; the census in
M.18.3–M.18.5 uses the six original contracts for all 14 configurations.*

#### M.18.3 Item-level pairing: what happens to an answered zero when an outlet appears

For each (model, domain) cell, the items are those that **that model's own `base` arm** answered 0, and
the table asks where they go under `permit` and `channel`. This is a paired transition, not a
comparison of aggregate rates.

| model / domain | `base` zeros | `permit` → refusal | `permit` → a number | **`permit` → still 0** | **`channel` → still 0** |
|---|---|---|---|---|---|
| Qwen3-VL-32B-AWQ-4bit / st_a | 102 | 102 | 0 | **0** | **0** |
| Qwen3-VL-32B-FP8 / st_a | 82 | 82 | 0 | **0** | **0** |
| Qwen3-VL-32B-AWQ-8bit / ucf | 125 | 125 | 0 | **0** | **0** |
| Qwen2.5-VL-72B-AWQ / visdrone | 121 | 121 | 0 | **0** | **0** |
| Qwen3-VL-32B-GPTQ-W4 / visdrone | 145 | 145 | 0 | **0** | **0** |
| Qwen3-VL-8B-AWQ / visdrone | 136 | 136 | 0 | **0** | **0** |
| InternVL2.5-8B-AWQ / visdrone | 128 | 128 | 0 | **0** | **0** |
| Qwen3-VL-32B-AWQ-4bit / aitod | 149 | 148 | 0 | 1 | **0** |
| Qwen3-VL-2B / visdrone | 194 | 34 | 52 | **108** | **0** |
| Qwen3-VL-2B / aitod | 101 | 48 | 11 | **42** | **0** |

Aggregated over all **52** (model × domain) cells: `permit` removes the answered zero outright in
**46** cells and leaves a single residual item in four of the remaining six; the six exceptions are
those four single-item residuals (the 32B AWQ-4bit / AWQ-8bit / BF16 / FP8 cells on AI-TOD) plus
**Qwen3-VL-2B on both aerial domains**, the smallest configuration, which partly re-answers instead.
The three-option `channel` contract removes the answered zero in **52 of 52** cells, 2B included.

#### M.18.4 The answered zero has two sources

**Zero pool, `base` arm, identical items within a domain.** Left column reports the four builds of *one*
32B checkpoint plus its siblings on st_a; right columns report the two aerial domains at the common
150-item sample.

| configuration | st_a (dense) | visdrone | aitod |
|---|---|---|---|
| Qwen3-VL-32B-AWQ-4bit | **99%** | 99% | 97% |
| Qwen3-VL-32B-AWQ-8bit | 65% | 97% | 93% |
| Qwen3-VL-32B-BF16 | 62% | 97% | 93% |
| Qwen3-VL-32B-FP8 | 80% | 97% | 93% |
| **Qwen3-VL-32B-GPTQ-W4** | **9%** | **97%** | **89%** |
| Qwen3-VL-4B | 23% | 92% | 77% |
| Qwen3-VL-8B-AWQ | 0% | 91% | 79% |
| InternVL3.5-38B-FP8 | 9% | 87% | 69% |
| InternVL2.5-8B-AWQ | 0% | 85% | 68% |
| Qwen3-VL-2B | **0%** | 82% | 67% |
| Qwen2.5-VL-72B-AWQ | **0%** | 81% | 62% |
| Qwen3-VL-30B-A3B-FP8 (MoE) | 0% | **15%** | **7%** |
| Qwen3-VL-8B-BF16 / Qwen2.5-VL-7B-AWQ | 2% / 1% | — | — |

Two facts follow, and they are the reason the main text no longer calls the answered zero a general
failure mode:

1. **In dense scenes the answered zero is build-specific.** Four builds of one 32B checkpoint give
   62–99%; a fifth build of the *same* checkpoint (GPTQ-W4) gives **9%**, and the remaining
   configurations give 0–23%.
2. **In aerial scenes it is near-universal**: 11 of 12 configurations give 62–99%. The one exception is
   the MoE configuration, and its low answered-zero rate is not better counting — it is a **different
   failure**: 17% of its VisDrone rows and 21% of its AI-TOD rows are unparseable output, so the
   abstention is expressed as format failure rather than as a zero.
3. **The same weights span both rows of the classification.** GPTQ-W4: 9% → 97% across domains;
   Qwen3-VL-2B: 0% → 82%; 8B-AWQ: 0% → 91%; InternVL2.5-8B: 0% → 85%; 72B: 0% → 81%. Domain is the
   dominant variable; the build is the modulator *within* the dense domain.

#### M.18.5 The saturation boundary, and the 2B exception

Non-zero pool (items the corpus answered **with a number**), `permit` arm refusal rate:

| pool | range across configurations | reading |
|---|---|---|
| st_a / st_b / ucf (dense) | **88.6–100%**, in **28 of the 30** (model × domain) cells; the exceptions are Qwen3-VL-2B (**24%** on st_a, **3%** on ucf) | the outlet is **saturated**: it carries almost no selectivity, so no per-item gating claim can be tested there |
| visdrone / aitod (aerial) | **36.1–92.9%** (16 cells; 8 configurations × 2 domains) | the outlet is **selective**, and it is exercised on more than half the items |

The exception in the dense pool is Qwen3-VL-2B (24% on st_a, 3% on ucf): the smallest configuration
keeps answering instead of using the outlet. A related asymmetry must be reported with any abstention
rate: the `channel` contract is **not** uniformly more abstentious than `permit`. It is higher for the
8B-class and 32B-class configurations (+5 to +28 pp) but **lower for Qwen2.5-VL-72B-AWQ** (VisDrone
83% → 46%, AI-TOD 62% → 24%), consistent with `permit`'s wording binding abstention to a failed
per-instance verification ("do not guess") whereas `channel` is a neutral three-way choice. Because the
two arms also differ in the output key (`count` vs `response`) and in the number of options,
`permit` vs `channel` is **not** a single-variable contrast.

#### M.18.6 What E2 does and does not establish

**Establishes.** (i) The answered zero is a **suppressed abstention**, not an estimate of zero, at item
level and across 14 configurations and 5 usable domains: offering an outlet removes it, forbidding the
outlet or demanding enumeration without adding one does not. (ii) The answered-zero phenomenon has two
distinguishable sources, one build-specific (dense) and one domain-specific (aerial). (iii) The
abstention outlet is saturated in dense domains and selective in aerial ones, so any claim about
selection must be made where the outlet is not saturated.

**Does not establish.** (i) That the abstention tendency itself is a capability limit: on the aerial
domains the outlet is used on the majority but not all of the items the corpus had answered with a
number, and we have no independent per-item legibility measurement for those items. (ii) Any conclusion
from CountBench: its corpus query puts the caption text in the prompt (`08_ext_vlm.py`) while these probes
send the image only, so the condition is ill-posed and is **excluded from every number above**. (iii) That
the corpus `abstain` column in the aerial domains is a contract abstention — it is a keyword proxy
(`pred == 0` or a few Chinese phrases), i.e. mostly answered zeros. (iv) Any cross-configuration claim
about visual-token cost: InternVL2.5 uses dynamic tiling, so its per-request latency (~11.4 s) is not
comparable with the Qwen
scaling (1.56 → 2.73 → 6.68 s).

#### M.18.7 Cost, and reproduction entry points

Same work load (six arms × 150 items on the dense-vs-aerial contrast), wall-clock on one H20:
Qwen2.5-VL-72B-AWQ **1451 s** on VisDrone and 583 s on AI-TOD; Qwen3-VL-32B-FP8 146 / 116 s;
Qwen3-VL-32B-GPTQ-W4 188 / 148 s; Qwen3-VL-8B-AWQ 84 / 62 s; InternVL2.5-8B-AWQ 117 / 72 s. The 72B
aerial cell alone is **17×** the 8B cell, which is the practical reason the census is limited to 14
configurations.

Entry points (all under the project's analysis tree): `e2_v7c_analysis.py` (arm tables and item-level
pairing), `e2_v7c_subset.py` (common-150 comparison), `e2_all_models.py` (cross-configuration summary),
`verify_s11.py` (asserts every number quoted in this appendix against the raw CSVs), plus the archived
serving and probe logs. Raw results: **558 result CSVs** (414 from the zero pools, 144 from the
non-zero pools), one per (configuration × domain × contract × pool).

#### M.18.8 Build versus domain: a two-way variance decomposition

The census contains five deployments of **one set of weights** (Qwen3-VL-32B-Instruct in AWQ-4bit,
AWQ-8bit, BF16, FP8 and GPTQ-W4 [41] builds), each measured on the same items in four domains. That is a
balanced 5 × 4 design in which the "build" factor carries no change of model, only of deployment. The
dependent variable is the answered-zero rate of the `base` arm on that domain's zero pool.

| build | st_a | ucf | VisDrone | AI-TOD |
|---|---|---|---|---|
| AWQ-4bit | 99.0 | 92.2 | 99.3 | 97.3 |
| AWQ-8bit | 65.0 | 69.4 | 97.3 | 92.7 |
| BF16 | 62.1 | 66.7 | 97.3 | 93.3 |
| FP8 | 79.6 | 79.4 | 97.3 | 92.7 |
| GPTQ-W4 | 8.7 | 16.1 | 96.7 | 88.7 |

Common item sets: 103 (st_a), 180 (ucf), 150 (VisDrone), 150 (AI-TOD) — identical across the five builds.

**The five builds, cell for cell, from the frozen per-item records.** The table above is recomputed by
`build_span_panel.py`, which reproduces **all twenty cells** (largest deviation **0.04 pp**) and pins the
two choices the reproduction depends on. First, each rate is **zeros over the pool size**, not over the
parsed subset: the two differ only where a build leaves items unparsed, and only the pool-size denominator
returns the printed `8.7` (9 of 103) rather than 9 of 99. Second, each domain's pool is the **common item
intersection across the five builds**, which is load-bearing on two of the four columns because the
per-build files are not the same size (VisDrone **273** for three builds against **150** for two; AI-TOD
**154** against **150**).

**And the build spread does not transfer to §7.3's unit.** On that same pool the two arms that remove the
zero behave identically in all five builds: `permit` and `channel` answer on at most **2.7%** of the pool's
items (0.0% in 33 of the 40 build × domain × arm cells). So although the **level** of the base-arm
answered-zero rate is build-dependent across **90.3 pp**, the **contract's effect on that pool** is
saturated in every build — which is why §7.3's VLM unit is measured on the corpus items rather than on this
pool, and why the two numbers are not in tension.

Two-way decomposition of the total sum of squares: **domain 38.7%**, **build 33.9%**,
**interaction/residual 27.4%**. **With intervals** (item-level bootstrap, $2{,}000$ resamples, the same index
draw shared by all five builds within a domain so that the pairing is preserved): domain
**[32.2, 45.3]**, build **[29.6, 37.9]**, interaction **[24.5, 30.7]** — and
$P(\text{build share} \ge \text{domain share}) = 0.17$. **The two shares are therefore not separated by
this design**, so the decomposition alone does not license the "build- versus domain-specific" reading. The
two factors do not act additively, and the reading rests on the **spread contrast** below, which is far
larger than the sampling error on either share:

* **Within the dense domains the build dominates**: the five deployments of one checkpoint differ by
  **90.3 pp** on ShanghaiTech-A (8.7 → 99.0) and **76.1 pp** on UCF-QNRF (16.1 → 92.2).
* **Within the aerial domains it does not**: the same five deployments differ by **2.7 pp** on VisDrone
  (96.7 → 99.3) and **8.7 pp** on AI-TOD (88.7 → 97.3); in both cases the gap
  is computed from the unrounded values, so the printed endpoints do not subtract to it.
* **Within a build the domain effect is large exactly when the build is not saturated**: GPTQ-W4 spans
  87.9 pp across domains and BF16 35.2 pp, whereas AWQ-4bit — already at 92–99% everywhere — spans only
  7.1 pp.

This is the quantitative form of §5.7's two-kinds statement, and it is why §9 states the scope of the
frequency claims explicitly: the **dense-scene answered zero is a property of the deployment**, while the
**aerial-scene answered zero is a property of the task**.

*Reproduction: `code/analysis/variance_decomp.py`; frozen result `variance_decomp_result.json`. The intervals
are from `_variance_boot.py`; frozen `variance_boot_result.json` (which also reproduces the three point
estimates exactly, 33.9 / 38.7 / 27.4).*

---

#### M.18.9 The same five deployments on the headline quantity $S$

M.18.8 compares the five deployments on the **answered-zero rate**. The paper's headline is not that rate but
the **abstention share of the under-count**, $S=(G-G_N)/(G-P)$ (Proposition 4, §5.5). Recomputed on the same
census files:

| build | st_a | ucf | VisDrone† | AI-TOD† |
|---|---|---|---|---|
| AWQ-4bit | 95.02 | 93.44 | 34.35 | 79.56 |
| AWQ-8bit | 91.39 | 86.11 | 30.55 | 68.73 |
| BF16 | 92.53 | 85.37 | 28.72 | 69.14 |
| FP8 | **97.51** | **96.28** | 29.80 | 68.22 |
| GPTQ-W4 | **undefined** | *321.65* | 28.43 | 64.14 |
| corpus anchor, comparable set | 94.24 | 93.69 | 31.05 | 74.90 |
| **spread, defined cells only** | **6.13** | **10.91** | 5.91 | 15.42 |
| same cells, answered-zero rate | **50.99** | **41.56** | 1.81 | 7.21 |

† The comparable item set is **truncated** in these two domains (VisDrone 277 of 400, AI-TOD 222 of 226), so
those columns cannot be read against the 82–94% headline — the anchor's own share falls to 31.05 and 74.90
there. Only **st_a and ucf** sit at the headline's item sets.

Three qualifications are load-bearing.
**(i) The deployment dependence is largely absorbed.** In the two comparable domains the answered-zero rate
spreads **50.99** and **41.56 pp** across the five deployments, while $S$ spreads only **6.13** and
**10.91 pp**: a deployment that answers fewer zeros also over-counts its answered items more, and the two
movements cancel in the ratio. M.18.8's contrast is therefore a statement about the **answered-zero rate**,
and is read that way. The five deployments' $S$ reaches **97.5%**, so 82–94% must **not** be carried over to
them unchanged.
**(ii) $S$ is not everywhere defined.** On GPTQ-W4 / st_a the pooled deviation is *positive*
($\rho_{\text{total}} = +33.72\%$, a net over-count), so $S$ is undefined; on GPTQ-W4 / ucf it is
**321.65%**, outside the share's range — the crossing M.39 already states. Both cells are left unfilled
rather than clipped. GPTQ-W4 is also the only build with empty `pred` fields (4 on st_a, 13 on ucf), and on
ucf the two conventions for those fields give **321.65%** versus **173.36%**; its $S$ is therefore **not
quoted**. The other four builds are insensitive to that choice.
**(iii) $S$ and the answered-zero rate do not rank the deployments alike.** The zero rate orders the five
identically in three of the four domains; $S$ gives a different order in every one, and the two orders agree
in **none** of the four. They are not two readings of one quantity.

*Reproduction: `analysis/work/s15_five_build_S.py`, cross-checked against
`p4_decomp_verify.py::unit_stats()`; the corpus anchor reproduces J.1 to its printed precision
(94.24 / 93.69 on the two untruncated domains).*

---

### M.19 The cross-family grid (E3): does the contract result belong to the contract, or to the lineage?

§M.18 measures the contract effect inside a fixed serving stack, but every configuration in it descends
from two lineages (Qwen and InternVL). E3 asks the narrower question the reviewers posed: **given an
abstention token, is the answered zero removed in families we have never measured?** Design, criteria and
instrument were fixed **before** the runs (criteria frozen by md5 `eaeafbc4ad4602e0a0f092d1306aea3c`), and
both outcomes — cross-family replication or a reported family dependence — were publishable in advance.

#### M.19.1 Design, and what is held fixed

| Item | Setting |
|---|---|
| Families added | **Gemma-3-12B** (`bfloat16`), **InternVL3.5-8B** (`bfloat16`), **Phi-3.5-Vision-4.2B** (`bfloat16`), **LLaVA-OneVision-7B** (`float16`) — four new lineages, three vendors/communities, all unquantised official builds; anchors: Qwen3-VL-32B-AWQ-4bit, Qwen2.5-VL-72B-AWQ, InternVL2.5-8B-AWQ (E2 records, same domains) |
| Serving | `vLLM` 0.29.0 on one **A800-SXM4-80GB** (driver 595.71.05, Python 3.13.5, transformers 5.17.0), temperature 0, `max-model-len` 8192 (unrelaxed), one image per prompt, `--gpu-memory-utilization 0.85`, `--max-num-seqs 24`, `--workers 8`; LLaVA-OneVision needed one documented import patch (§M.19.5) |
| Instrument | the **identical** probe file used by E2, md5 `03edb14c98ffa3aea9ffa20f59b00bc8` (re-verified on the A800) |
| **Prompt, and the one wrapper that cannot be equalised** | Every family received the **byte-identical contract prompt set** of §3.6/E2 — the same file, the same arms, **no per-family prompt and no system message**. The one wrapper that *cannot* be equalised across vendors is each build's own **chat template**, which ships with the weights; it is therefore held **constant between the two arms of every contrast** (same family, same items, same wrapper, `base` vs `permit`), so it cancels from the comparison rather than confounding it. M.19.8 measures what a *changed* template does to an **absolute** rate (up to −56.6 pp), which is why no absolute rate is compared across families. |
| Domains / pools / arms | st_a, ucf (dense) and visdrone, aitod (aerial); zero pool (`base` 6 arms) and non-zero pool (3 arms); fixed seed, **same items** as E2 where the pools coincide |
| Frozen criteria | **P1**: per family, `permit` leaves ≤5% of the base zeros answered as 0 (replication needs ≥5/6 families), a family above 30% being a **counterexample** to be reported; **P2**: the dense-minus-aerial base-zero gap is ≥30 pp; **P3**: the direction of the contraction is the same in every family. Reporting was frozen with them: Wilson CIs, cross-family comparison **only on the intersection of item sets**, `pred ≥ 1e5` an anomaly, an empty `pred` reported but excluded from pooled rates |

#### M.19.2 P1 — the contract gate reproduces in 7 of 7 families

Items the `base` contract answered exactly 0, paired against their own `permit` answer:

| Family | base zeros | still 0 under `permit` | rate | Wilson 95% CI | per domain (still 0 / zeros) |
|---|---|---|---|---|---|
| Gemma-3-12B | 9 | 0 | **0.0%** | [0.0%, 29.9%] | VisDrone 0/5, AI-TOD 0/4 |
| InternVL3.5-8B | 156 | 0 | **0.0%** | [0.0%, 2.4%] | st_a 0/1, ucf 0/1, VisDrone 0/95, AI-TOD 0/59 |
| Phi-3.5-Vision-4.2B | 197 | 0 | **0.0%** | [0.0%, 1.9%] | VisDrone 0/92, AI-TOD 0/105 |
| LLaVA-OneVision-7B | 235 | 5 | **2.1%** | [0.9%, 4.9%] | VisDrone 2/134, AI-TOD 3/101 |
| Qwen3-VL-32B-AWQ (anchor) | 685 | 1 | **0.1%** | [0.03%, 0.8%] | st_a 0/102, ucf 0/166, VisDrone 0/268, AI-TOD 1/149 |
| Qwen2.5-VL-72B-AWQ (anchor) | 214 | 0 | **0.0%** | [0.0%, 1.8%] | VisDrone 0/121, AI-TOD 0/93 |
| InternVL2.5-8B-AWQ (anchor) | 230 | 0 | **0.0%** | [0.0%, 1.6%] | VisDrone 0/128, AI-TOD 0/102 |

**Verdict: 7 of 7 configurations ≤ 5%, with no counterexample.** The panel as run carries **seven checkpoints across five vendor lineages** (two are Qwen and two are InternVL), so it clears the frozen criterion — which required **≥ 5 of 6 families** — by one lineage rather than by seven; the counts differ because the criterion was written for six families and the panel gained a seventh checkpoint. **Resolution must be
stated, not implied:** Gemma-3-12B offered only 9 zeros to replace (hence the 29.9% upper bound) and
InternVL3.5-8B drew 2 of 156 from the dense domains, where **none of the four new families reproduces the
corpus zero** (0.0–0.8%), as the build-specific reading predicts.

#### M.19.3 P2 — the configuration-level gap has no resolution; the build-spread form does

`base`-arm answered-zero rate on the intersection of item sets (dense = st_a + ucf, aerial = VisDrone + AI-TOD):

| Family | dense | aerial | aerial − dense (pp) | 95% CI of dense − aerial (pp) | \|gap\| ≥ 30 pp |
|---|---|---|---|---|---|
| Gemma-3-12B | 0.0% [0, 1.5] (n=253) | **3.0%** [1.6, 5.6] (n=300) | +3.0 | [−5.6, −0.9] | no |
| InternVL3.5-8B | 0.8% [0.2, 2.8] | 51.3% [45.7, 56.9] | +50.5 | [−56.2, −44.5] | yes |
| Phi-3.5-Vision-4.2B | 0.0% [0, 1.5] | 65.7% [60.1, 70.8] | +65.7 | [−70.8, −59.9] | yes |
| LLaVA-OneVision-7B | 0.0% [0, 1.5] † | 78.3% [73.3, 82.6] | +78.3 | [−82.6, −73.1] | yes |
| Qwen3-VL-32B-AWQ (anchor) | **95.3%** [91.9, 97.3] | 98.3% [96.2, 99.3] | +3.1 | [−6.6, −0.1] | no |
| Qwen2.5-VL-72B-AWQ (anchor) | 0.0% [0, 1.5] | 71.3% [66.0, 76.2] | +71.3 | [−76.2, −65.8] | yes |
| InternVL2.5-8B-AWQ (anchor) | 0.0% [0, 1.5] | 76.7% [71.6, 81.1] | +76.7 | [−81.1, −71.3] | yes |

† defined on the parsed subset only (see §M.19.5).

**The aerial denominators above are the raw 300-item intersections.** Two arms — Phi-3.5-Vision-4.2B and
LLaVA-OneVision-7B — lose unparsed items on these domains, and §M.19.15 prints the same two arms after the
frozen empty-`pred` exclusion, where the denominators are **297** and **293**: there the values are
**66.33%** and **80.20%** against the **65.7%** and **78.3%** here. The numerators are identical
(197 and 235); only the denominator moves, and each table names its own.

**Verdict, stated both ways because the frozen rule says "≥ 5/6 families": 5 of 7 families pass the
literal count, and 5 < ⌈5·7/6⌉ = 6, so the proportional reading fails.** **A literal miss is a miss**: we do not rescale the denominator after seeing the data, so the honest
summary is **≥ 5 of 7 but not 6 of 7**, and the boundary case is **Gemma-3-12B at 3.0%**. Neither non-passing family is a
counterexample — each is one on which the statistic has no resolution: Qwen3-VL-32B-AWQ is the one measured
build whose **dense** zero rate is itself 95.3%, and Gemma-3-12B answers a number in *both* domains. The
sharper form is measured **inside** one family, weights fixed: across the five Qwen3-VL-32B deployments the
dense zero rate spans **81.3 pp** (13.4% → 94.7%) against **5.7 pp** aerially (92.7% → 98.3%). "Aerial zeros
are near-universal" now carries **two** exceptions — the MoE build of §M.18.6 (11.0%) and **Gemma-3-12B
(3.0%)**: 14 of 17 measured conditions, i.e. all four new unquantised builds except Gemma.

#### M.19.4 P3, and a correction the cross-family data force

**Direction (P3): 7/7.** In every family and domain, offering the abstention token lowers the answered-zero
rate on items that previously carried a zero.

**Correction — the dense-domain channel is saturated.** On the **non-zero pool** (items the corpus
answered with a number), the fraction that the `permit` contract leaves as a number is:

| Family | st_a | ucf | VisDrone | AI-TOD |
|---|---|---|---|---|
| Phi-3.5-Vision-4.2B | **0.0%** | **0.0%** | **0.0%** | **0.0%** |
| InternVL3.5-8B | **0.0%** | **0.0%** | 54.8% | 69.0% |
| Gemma-3-12B | **2.5%** | **0.7%** | 52.8% | 61.1% |
| InternVL2.5-8B-AWQ (anchor) | **0.0%** | **0.0%** | 19.8% | 23.9% |
| Qwen3-VL-32B-AWQ (anchor) | **1.3%** | **0.0%** | 34.1% | 46.4% |
| Qwen2.5-VL-72B-AWQ (anchor) | **0.0%** | **0.0%** | 16.7% | 39.7% |
| LLaVA-OneVision-7B | 13.9% | 21.1% | 98.4% | 89.9% |

Five of the seven families convert **97.5–100%** of items that already contained a number into abstentions
in the dense domains, whereas the same channel stays selective in the aerial domains (0–98%, wide spread
across families). This reproduces, on new lineages, the boundary recorded for E2 (§M.18.6): the contract
sets the **channel**; whether it carries selective information is **domain-conditional**. §3.5 and §7.6 are
worded accordingly.

**A build axis outside the Qwen lineage (partial).** Serving the *same* Gemma-3-12B weights with online
int8 weight-only quantisation (W8A16) changes no rate — dense 0.000 → 0.000, VisDrone 0.032 → 0.033,
`permit` leaving 0/5 zeros in both — so an 8-bit requantisation does not induce the dense zero in a family
that lacks it; what moved the 32B anchor by 81.3 pp was a change *within* its 4/8-bit, GPTQ, FP8 and BF16
builds. A true 4-bit build of a new family was not obtainable on this image (FP8 unsupported on `sm_80`;
`gemma3` refuses float16; no bitsandbytes in this vLLM build; no quantised checkpoint locally), so the axis
is **partially** established and §9 says so.

#### M.19.5 Quality control, exclusions, and the one stack patch

| Check | Outcome |
|---|---|
| Parse rate, `base` arm (st_a / ucf / VisDrone / AI-TOD) | Gemma-3-12B 100/100/100/100; InternVL3.5-8B 100/100/100/100; Phi-3.5-Vision 100/100/100/98.0; LLaVA-OneVision **38.8/75.3**/97.3/98.0 |
| Why LLaVA's dense parse rate is low | its `raw` output is a **prose refusal in the prompt's language** (the prompts are Chinese; translated: "because the crowd is dense an exact count is not possible, though a rough estimate can be given"), holding neither a digit nor an abstention token ⇒ empty `pred`, excluded from pooled rates per the frozen rule; its dense zero rate is stated **on the parsed subset only** |
| HTTP errors | 3 ucf items (`img_0003`, `img_0120`, `img_0209`) return `400` under **every** arm of LLaVA-OneVision (AnyRes vision tokens exceeding the 8192 context), so the exclusion is **arm-invariant** and pairing is unaffected; `max-model-len` was **not** relaxed, being a protocol parameter |
| Item sets | st_a identical across all 7 families (n=103); ucf [150, 180], VisDrone [150, 158, 273], AI-TOD [150, 154] ⇒ every cross-family rate is computed on the **intersection** (150, 150) |
| Serving stack | one documented, reversible import patch for LLaVA-OneVision (vLLM 0.29 importing two transformers-4 symbols that transformers 5 renamed/removed; script and md5s in the reproduction package's `env/`), used **only** in its Pixtral path — the other three families ran untouched |

#### M.19.7 The mechanism replicates cross-family: the gate is the token, not the enumeration demand

§M.18.2 showed, for two builds of one checkpoint, that a prompt demanding per-instance enumeration or
localisation but exposing **only a numeric field** leaves the zero in place, while adding a single
abstention token to the *same* prompt removes it. E3 repeats that arm comparison on new families. Rates are
computed **on the common item set** (E2's `base` files accumulated several runs, so raw counts would read a
denominator difference as a mechanism difference):

| family | domain | common n | `base` | `enum` | `locate` | `enumAbstain` |
|---|---|---|---|---|---|---|
| Gemma-3-12B | VisDrone | 150 | 0.033 | **0.387** | 0.087 | **0.000** (120 refusals) |
| InternVL3.5-8B | VisDrone | 150 | 0.633 | 0.593 | 0.753 | **0.000** (136) |
| Phi-3.5-Vision | VisDrone | 150 | 0.613 | 0.233 | 0.847 | **0.000** (150) |
| Qwen3-VL-32B-AWQ (anchor) | st_a | 103 | 0.990 | 0.893 | 0.961 | **0.000** (103) |
| Qwen3-VL-32B-AWQ (anchor) | ucf | 180 | 0.922 | 0.883 | 0.861 | **0.000** (180) |
| Qwen3-VL-32B-AWQ (anchor) | VisDrone | 273 | 0.982 | 0.945 | 0.963 | **0.015** (268) |
| Qwen3-VL-32B-AWQ (anchor) | AI-TOD | 154 | 0.968 | 0.883 | 0.883 | **0.097** (133) ← only exception |

(i) With a numeric-only field, demanding enumeration or localisation **does not remove the zero**: `enum` and
`locate` stay at 23.3–89.3% (the dense 32B anchor: 89.3% and 88.3%). (ii) Adding one abstention token to that
same prompt removes it on **6 of 7 cells (≤1.5%)**, the exception being the AI-TOD cell of §M.18.2. (iii) **A
new directional finding**: enumeration pressure *raises* the zero rate — Gemma-3-12B on VisDrone 3.3% →
**38.7%**, InternVL3.5-8B/Phi-3.5-Vision under `locate` on the dense domains 0.7%/0.0% → **29–32%** — so the
contract decides the **outlet**, enumeration pressure decides **how many items arrive at it**. The three-leg
reading rule (`enumAbstain ≤ 5%`, `enum ≥ 5%`, `enum/base ≥ 0.25`) is **post hoc**: the frozen criteria cover
only the `base`/`permit`/`channel` arms.

#### M.19.7.1 The pooled AUC is carried by between-unit differences, not by within-unit ranking

The deployment statement in the main text is qualitative; this is its quantitative form on the same frozen
records. Stacking the twenty (family $\times$ domain) units, the pooled AUC of the dispersion statistic is
**0.586**. Two decompositions show what that number is made of. Predicting from **unit identity alone** gives
**0.767** — *higher* than the statistic itself — while centring the statistic **within** each unit leaves
**0.575**, essentially chance; and **96.1%** of the positive–negative pairs over which the pooled AUC is
computed are **between** units, only **3.9%** within. The pooled figure is therefore carried by between-unit
base-rate differences, and the statistic's genuine within-unit ranking power is close to chance. This is the
mechanism behind the qualitative statement, and it is why the pooled number is **not** used as cross-domain
evidence. As a reference for how much room a mixture of the two components leaves, the within-unit ceiling is
**0.967**, the between-unit ceiling **0.519** and the mixture **0.537** — so the observed 0.586 sits **above**
that mixture ceiling, and no information-theoretic impossibility is being claimed here.

*Reproduction: the decomposition is a two-step procedure — a stratified decomposition followed by a ceiling
arithmetic — carried out on the released per-item records. (The two author-side scripts that performed it,
`_strat_decomp.py` and `_bound_check.py`, are **not part of the released package**; the procedure is stated in
full above and the records it consumes are released, so the arithmetic is reproducible from the package even
though those two files are not.); the twenty units are the same (family $\times$ domain) units used
in the table above.*

#### M.19.8 Ablations: the contract effect is scale- and template-invariant; the zero *rate* is not

A separate derived instrument (`19f_probe_ablation.py`, generated from 19e by `make_19f.py`, which asserts
19e is byte-unchanged) varies **input scale** (longest side 640 / native / 1536) and **template** (one system
message prepended). Gemma's dense domains have no zeros to test (base rate 0.000), so the informative
variants are on families that do produce them:

| family / domain | base zero rate | `s640` | `s1536` | `+system` | contract effect (still 0 under `permit`) |
|---|---|---|---|---|---|
| InternVL3.5-8B / VisDrone | 0.633 | 0.627 (−0.6 pp) | 0.627 (−0.6 pp) | 0.560 (**−7.3 pp**) | **0** of 95, 94, 94, 84 |
| Phi-3.5-Vision / VisDrone | 0.613 | 0.620 (+0.7 pp) | 0.613 (0.0 pp) | 0.047 (**−56.6 pp**) | **0** of 92, 93, 92, 7 |
| Qwen3-VL-32B-Instruct BF16 / st_a (dense) | 0.602 | 0.670 (+6.8 pp) | — | 0.670 (+6.8 pp) | **0** of 62, 69, 69 |
| Gemma-3-12B / st_a, ucf | 0.000 | 0.000 | 0.000 | 0.000 | no zeros to replace |

The dense row is also a cross-check on the E2 record: this BF16 build's `base` zero rate on st_a,
**60.2%**, reproduces the 62.1% recorded in §M.18.8 for the same checkpoint and build.

(i) **Input scale is nearly inert for the rate** — Δ ≤ 0.7 pp in the aerial domains, +6.8 pp in the dense one,
across 640 → 1536. (ii) **The template is not inert and its effect is family-dependent**: one system message
takes Phi-3.5-Vision's VisDrone zero rate from 61.3% to 4.7%, moves InternVL3.5-8B by −7.3 pp and the dense
32B case by +6.8 pp, and does nothing to Gemma-3-12B — so the zero rate is a function of **contract × family
× template**, and cross-family *rate* comparisons are read with that caveat. (iii) **The contract effect
survives every variant**: across four family/domain units and eleven variant-cells the `permit` arm leaves
**zero** residual zeros. Repeatability, same condition `reps = 3` (Gemma-3-12B, st_a, first 60 items):
**60/60 identical** in both arms, and the `native` variant agrees with the main run at class level **1.000**.

**(iv) What the template column is, and what it is not.** The `+system` column measures a **sensitivity of an
absolute rate** — what would move if the prompt were changed — and it is **not** a confound in this grid: E3
gave every family the byte-identical contract prompt set (`19e_probe_multi.py`, md5
`03edb14c98ffa3aea9ffa20f59b00bc8`, the same file E2 used) with **no system message**, so the prompt text is
constant across families. The one wrapper that genuinely cannot be equalised across vendors is each build's
own **chat template**, because it ships with the weights; every cross-family claim in this appendix is
therefore a **within-family paired** contrast on the same items — `base` against `permit`, same family, same
wrapper — in which that wrapper is held constant between the arms and cannot drive the contrast. What a
template *can* do is move an **absolute** rate, by up to **56.6 pp** here, and it is for that reason that no
absolute rate is compared across families anywhere in this paper. The residual exposure is therefore an
**interaction** between the wrapper and the contract wording, which this grid does not test and does not
claim.

*Reproduction: `code/analysis/a5_*.py` (judge, report, two_kinds, qc, qc_matrix, rawsamples, pull), the
frozen criteria `a5_criteria_frozen.json` (+ `.md5`), the grid driver `a5_grid.sh` /
`a800_chain_families.py`, the stack patch `a800_fix_llava.sh`, the environment snapshot
`data/derived/e3/env/a800_env_snapshot.txt`, and the raw CSVs under `data/derived/e3/`.*

---

#### M.19.9 The frozen-criteria reading of the E3 table

**(P1)** pooled residual **≤2.1%** (worst-case Wilson bound **4.9%**). **(P3)** the direction is unanimous:
the answered-zero rate falls in **every family and every domain (7 of 7)**. **(P2)** the two kinds of zero do
**not** reduce to one contrast: the dense-minus-aerial base-zero gap reaches **≥30 pp in 5 of 7 families**
and fails exactly in the two cells where the statistic has no resolution — the one measured build whose
*dense* rate is itself **95.3%**, and Gemma-3-12B, which answers a number in both domains (**3.0%**
aerially) — whereas measured **inside** one family across five builds the contrast is unambiguous
(**81.3 pp** dense against **5.7 pp** aerial). **The gate itself also replicates**: prompts that demand
per-instance enumeration or localisation but expose only a numeric field leave **23–89%** of the zeros in
place, while the *same* prompt plus one abstention token leaves **0–1.5%** (6 of 7 cells; the exception is
the AI-TOD cell of Appendix M.18.2). Two boundaries survive, reported rather than smoothed: the aerial zeros
are near-universal but **not** universal (**Gemma-3-12B answers a number even there, 3.0%**; the MoE build of
M.18.4 is the other exception), and in the dense domains the channel is **saturated** — five of the seven
families convert **97.5–100%** of already-numeric answers into abstentions — so what the contract fixes is
the *channel*, not its selectivity (Appendix M.19).

#### M.19.10 The legibility gate reproduces in other lineages: a controlled disc grid

§M.19.1–M.19.9 measure the contract on **real corpus images**, where the families that produce the
answered zero are dominated by one lineage. This section closes that gap the other way round: instead of
adding corpora, it **manufactures the condition the paper claims gates the zero** — low legibility — on a
grid where the ground-truth count and the degradation are controlled independently, and asks whether the
zero then appears in lineages that never showed it on the corpus.

**Design.** A synthetic disc grid on which the ground-truth count $n$ and a Gaussian blur $\sigma$ vary
independently: $n \in \{100, 400, 800\}$ × disc radius $r \in \{2, 4, 8\}$ px × $\sigma \in \{0, 1, 2, 4, 8\}$
× 15 renders = **675 items** on a 1024×1024 canvas, drawn with the same routine as the earlier synthetic
work in this paper. Every render is written to disk **once** with an explicit seed, and every arm and every
service start reads the same files (675/675 md5-verified; manifest `9eef8a074cf1`); an earlier instrument
of this family derived its seed from `abs(hash(item))`, which Python randomises per process, so arms
launched separately saw the same *distribution* of discs but not the same images — here the comparison is
**item-paired by construction**. The prompt is the frozen contract arm with **only the object noun changed**
(person → disc); everything after the first full stop — the abstention clause and the JSON instruction — is
byte-identical and asserted to be so at run time. The probe is the frozen instrument of §M.19.1 (md5
`03edb14c98ff…`), imported at run time with its md5 asserted; the parser is unchanged. Arms `base` and
`permit`, temperature 0, one image per prompt, 675 items each arm. The criteria were frozen before the runs
(`p1_criteria_frozen.json`, md5 `209e18d5011e`; re-issued: external-check traces removed only, values and criteria unchanged): **H1** two of the three pre-registered new families reach a
base answered-zero rate ≥ 20% at $\sigma = 8$; **H2** the permitted-abstention arm leaves ≤ 5% of the base
zeros answered as 0; **H3** fewer than two families ⇒ record *lineage-specific* and narrow §5.7;
**H4** the anchor cell closes on the published value.

| family | $n$ at $\sigma{=}8$ | base answered zero at $\sigma = 8$ | Wilson 95% | base zeros (all $\sigma$) | under `permit` | \(\sigma\) trend |
|---|---|---|---|---|---|---|
| Qwen3-VL-32B (anchor) | 135 | **67.4%** | [59.1, 74.7] | 104 | **0** | 0, 0, 0, 9.6%, 67.4% |
| Qwen3-VL-8B (anchor) | 135 | **43.0%** | [34.9, 51.4] | 67 | **0** | 0, 0, 0, 6.7%, 43.0% |
| **Phi-3.5-Vision** | 135 | **34.1%** | [26.6, 42.4] | 91 | **0** | 11.1%, 5.2%, 5.9%, 11.1%, 34.1% |
| **LLaVA-OneVision-7B** | 105 | **42.9%** | [33.8, 52.4] | 45 | **0** | 0, 0, 0, 0, 42.9% |
| gemma-3-12b | 135 | 0.0% | [0.0, 2.8] | 0 | — | 0, 0, 0, 0, 0 |
| InternVL3.5-8B | 135 | 0.0% | [0.0, 2.8] | 0 | — | 0, 0, 0, 0, 0 |

**Verdicts, as frozen.** **H1 passes:** two of the three pre-registered new families cross the threshold
(Phi-3.5-Vision 34.1%, LLaVA-OneVision-7B 42.9%), and both anchors are higher still. **H2 passes:** of the
items the `base` contract answered as 0, the permitted-abstention contract answers **none** as 0 — 0/104,
0/91, 0/67 and 0/45 (Wilson upper bounds 3.6%, 4.1%, 5.4%, 7.9%). **H3 is not triggered.** **H4 closes
exactly:** the published anchor — Qwen3-VL-32B answering zero on **every** item at $\sigma = 8, n = 800$ —
re-measures at **100%** (45 of 45), a difference of **0.0 pp** against a 10 pp allowance, although that cell
is *saturated* and therefore a weak test of stimulus identity. **H1b, the secondary dose–response
criterion, does not pass:** the gate behaves as a **threshold rather than a ramp** — Phi-3.5-Vision is
non-monotone across $\sigma = 0 \ldots 8$ (11.1, 5.2, 5.9, 11.1, 34.1%; Spearman 0.56 against the
pre-registered 0.8) and LLaVA's four exact zeros at the lower levels leave ties (0.71). Both are reported
as measured.

**Two boundaries, stated rather than smoothed.** (i) **gemma-3-12b and InternVL3.5-8B answer a number on all
675 items**, including at $\sigma = 8$: in these two the *answered-zero channel is absent*, yet the
abstention channel is present — under `permit` they decline in prose on **65.5%** and **75.4%** of items
(no numeric field, hence counted as parsing failures by the reporting rule and excluded from pooled rates).
That asymmetry — abstention available, an answered zero not — is the same one §M.19.9 records at corpus
level (Gemma-3-12B offered only 9 zeros to replace), and it is why the criterion is "two of three" rather
than "all". (ii) The counts here are **within-family, item-paired** contrasts on a controlled grid; they do
not license comparing absolute zero rates between families, for the reasons §M.19.8 gives.

**What this does and does not change.** It changes the reading of §5.7: the answered zero under dense,
low-legibility input is **not a property of one lineage** — it is reproducible in three further lineages
whenever the legibility stress is made large enough — and the permitted-abstention contract extinguishes it
in every family that produces it. It does **not** turn the corpus-level frequency claim into a cross-family
one: the corpus remains dominated by one lineage (§8.2), and two of the six builds measured here never
answer zero at all.

*Reproduction: `p1_prep_grid.py` (grid and manifest), `p1_criteria_frozen.json` + `.md5` (criteria, frozen
before the runs), `p1_probe.py` (imports the frozen probe and asserts its md5; stores the **complete** raw
reply, which is what makes the independent re-parse possible), `p1_analyze.py` (Wilson intervals, item-paired
residuals, H1–H4) and `p1_indep_check.py`, which recomputes every reported quantity from the raw replies
along an independent code path: **27 checks, 0 failures** on the six-family set.*

#### M.19.11 The template axis, and the same manipulations on real images

§M.19.10 established the legibility gate on a controlled disc grid. This section closes the two questions
that grid cannot answer: whether the *wrapper* changes the gate (a template × contract interaction), and
whether the same legibility manipulations reproduce on **real corpus images** rather than discs.

**(a) Template × contract, at the blur level that induces the zero.** The four cells repeat the $\sigma = 8$
stratum (135 items) of §M.19.10 under two wrappers: `native` (the frozen transport, no system message) and
`sys` — one system message prepended, byte-identical to the one this paper's earlier ablation used
("You are a careful visual counting assistant. Follow the requested output format exactly."), so the column
is comparable with §M.19.8. Criteria were frozen before the runs (`p1b_criteria_frozen.json`, md5
`64d673639c93`; re-issued: external-check traces removed only, values and criteria unchanged).

| family | base answered zero, `native` | base answered zero, `sys` | \(\Delta\)(sys − native) | permit residual, `native` | permit residual, `sys` |
|---|---|---|---|---|---|
| LLaVA-OneVision-7B | 42.9% (45/105) | 42.9% (45/105) | **0.0 pp** | **0/45** | **0/45** |
| Phi-3.5-Vision | 33.3% (45/135) | 40.7% (55/135) | **+7.4 pp** | **0/45** | **0/55** |
| Qwen3-VL-8B | 43.7% (59/135) | 39.3% (53/135) | **−4.4 pp** | **0/59** | **0/53** |

**Verdicts.** **H5 passes in 3 of 3 families:** under *both* wrappers the permitted contract leaves **no**
base zero answered as 0. **H6:** no family is first-order modulated by the wrapper (all |Δ| < 20 pp), which
is worth juxtaposing with §M.19.8, where the *same* system message moved Phi-3.5-Vision's VisDrone zero rate
by **−56.6 pp** on real images. The wrapper's effect is therefore **stimulus-dependent** — large on the
aerial corpus, small here — while the **contract** effect is **wrapper-invariant**. **H7:** the interaction
is measurable in all three families (each has ≥ 20% zeros under `sys`), so this is a measurement rather than
a null of convenience.

**(b) The same manipulations on real images.** Discord is easy to make artificial and hard to make real, so
the blur and resolution manipulations were repeated on **300 real images** — 150 ShanghaiTech-A (dense) and
150 VisDrone (aerial), deterministically sampled — under three conditions: `clean`, `blur4`
(Gaussian $\sigma = 4$), and `down15` (rescaled to **15% of the pixels**, the same manipulation §5.7 uses),
on the same three families (`p1c_criteria_frozen.json`, md5 `b27d6df39bca`; re-issued: external-check traces removed only, values and criteria unchanged; 5,400 calls).

| family | condition | base answered zero | dense subset ($n = 150$) | permit residual |
|---|---|---|---|---|
| Qwen3-VL-8B | `clean` | 30.3% (91/300) | 2 | 0/91 |
| Qwen3-VL-8B | **`blur4`** | **93.7% (281/300)** | **141** | 0/281 |
| Qwen3-VL-8B | `down15` | 40.3% (121/300) | 22 | 0/121 |
| Phi-3.5-Vision | `clean` | 19.4% (58/299) | 0 | 0/58 |
| Phi-3.5-Vision | **`blur4`** | **28.6% (78/273)** | **2** | 0/78 |
| Phi-3.5-Vision | `down15` | 22.0% (66/300) | 0 | 0/66 |
| LLaVA-OneVision-7B | `clean` | 32.8% (77/235) | 0 | **7/77 (9.1%)** |
| LLaVA-OneVision-7B | `blur4` | 59.6% (34/57) | 0 | 0/34 |
| LLaVA-OneVision-7B | `down15` | 42.6% (89/209) | 0 | 4/89 |

**What replicates and what does not.** **Blur raises the zero on real images** in two of three families
(Phi-3.5-Vision 19.4% → 28.6%; Qwen3-VL-8B 30.3% → **93.7%**), and the resolution manipulation moves it far
less (the negative control of §5.7: +13.3 pp for the anchor, 0.0 pp for the other two) — **H8 passes**. The
contract still extinguishes the zeros in every cell except one (LLaVA's `clean` cell, 7 of 77 = **9.1%**,
above the 5% allowance) — **H9 fails in exactly that cell and is reported as a failure**. And the lineage
picture on real images differs from the discs: in the **dense** subset the zero remains **Qwen-dominated**
(141/150 under blur, against **2/146** for Phi-3.5 and **0/150** for LLaVA-OneVision), whereas on the
synthetic grid at $\sigma = 8$ both of those families did produce zeros.

**The honest reading of the two experiments together.** The *mechanism* — an answered zero is what a model
does when the input becomes unreadable, and the permitted-abstention contract replaces it — reproduces
across lineages when the legibility stress is made strong enough on a controlled grid (M.19.10), and it is
insensitive to the prompt wrapper (this section). The *corpus-level frequency* claim does **not** generalise
the same way: on real dense images the answered zero remains concentrated in one lineage (§8.2's bound is
unchanged by these runs), and two of the families measured here never answer zero on real dense images at
all. Both statements are in the paper; neither replaces the other.

*Reproduction: `p1_prep_grid.py`, `p1b_freeze_criteria.py`, `p1b_criteria_frozen.json`, `p1c_prep.py`,
`p1c_freeze_criteria.py`, `p1c_criteria_frozen.json`, `p1_probe.py --system/--tag`, `p1b_analyze.py`,
`p1c_analyze.py`, runners `p1b_run.sh` / `p1c_run.sh`, and the per-item CSVs of both experiments, which are
released with the grid manifest.*

#### M.19.12 Clause-level attribution: which clause carries the effect, and which does not

§M.19.10 and §M.19.11 measure the *contract* as a whole. That leaves the mechanism one level short: the arms
differ in several clauses at once, so "the contract matters" is still a statement about a bundle. This section
decomposes the prompts into **clauses**, labels each clause with a type, and then uses **minimal pairs whose
typed clause sets differ in exactly one clause**. It costs no model calls: every number below is recomputed from
data already released. The typing instrument is `prompt_features.py`, whose `--selftest` pins a hand-checked
golden annotation for all **20** arms (clause boundaries *and* per-clause types); it passes, and two negative
controls (one corrupted label, one deleted golden entry) both make it exit non-zero, so the gate can fail.

Clause types are `TASK`, `ENUM` (exhaustiveness: "do not miss", "do not double-count", "each individual"),
`ABSTAIN_PERMIT`, `ZERO_FORBID` (forbid the answer 0, or force a number), `FORMAT`, and `PREMISE`. Two typing
decisions are load-bearing and are asserted rather than assumed. First, the refusal verb that one arm carries
counts only as `ZERO_FORBID`, never as `ABSTAIN_PERMIT`, because in the arm that contains it the phrase is
*prohibiting* abstention rather than offering a way out. Second, the phrase best rendered "verify one by one" is
**not** `ENUM`, because one arm uses it to introduce the abstention condition while a paraphrase arm uses "each
individual" to introduce a genuine exhaustiveness demand. The literal prompt strings behind both decisions are
themselves released in the clause table (`prompt_features.json`), so the reader can re-check the annotation
without relying on this gloss. Criteria were frozen before any rate was computed
(`pA_criteria_frozen_v2.json`, md5 `feef927f6cc6`); the evidence blocks are the released E1 corpus arms (Block A:
489 cells with $n \ge 20$, 18 families, 12 arms), the controlled blur grid (Block B: 675 items, arms paired
**by item**), and the controlled occlusion grid (Block C: 160 items, likewise paired).

**(a) The clause that permits abstention is the one that carries the effect.** `enumAbstain` and `enum` have
*identical* typed clause sets except that `enumAbstain` adds the `ABSTAIN_PERMIT` clause. Across four lineages
the answered zero collapses and reappears as an explicit abstention:

| lineage | answered zero, `enum` | answered zero, `enumAbstain` | \(\Delta\)zero | \(\Delta\)abstention |
|---|---|---|---|---|
| InternVL3.5-8B | 25.3% (102/403) | **0.0%** | **−25.3 pp** | **+96.5 pp** |
| Phi-3.5-Vision | 10.4% (42/403) | **0.0%** | **−10.4 pp** | **+100.0 pp** |
| gemma-3-12b | 14.4% (58/403) | **0.0%** | **−14.4 pp** | **+90.8 pp** |
| Qwen3-VL-32B | 90.8% (645/710) | 2.7% (19/710) | **−88.2 pp** | **+96.3 pp** |

**H_A1 passes (4 of 4 lineages, against a 3-of-4 criterion).** The zero does not merely fall; it is converted,
almost point for point, into a declared abstention.

**(b) Wording is essentially irrelevant; the clause type is not.** Paraphrase arms hold the typed clause sets
fixed and change the words — including one arm translated wholesale into English. Across the three families that
have them, every wording-only contrast moves the zero rate by at most **0.1 pp** (nine family-pair cells:
`permitB − permit` +0.0/+0.1/+0.0; `permitC − permit` +0.0/+0.1/+0.0, the English arm; `channelB − channel`
+0.0/+0.0/+0.0), and the abstention rate moves by at most 3.3 pp. Type-changing pairs reach **96.3 pp**.
**H_A3 passes**: an effect two orders of magnitude larger attaches to *whether the clause is present* than to
*how the clause is worded*.

**(c) The clause that forbids the answer 0 does *not* carry the effect, and on one lineage it reverses.**
`forbid0` adds only the `ZERO_FORBID` clause to `base`. On the paired blur grid it fails the 10 pp bar in two of
three runs and **reverses sign** in the third:

| run | items | answered zero, `base` | answered zero, `forbid0` | \(\Delta\)zero |
|---|---|---|---|---|
| Qwen3-VL-32B | 675 | 16.7% | 10.2% | −6.5 pp |
| Qwen3-VL-8B | 675 | 45.0% | 33.6% | −11.4 pp |
| InternVL2.5-8B-AWQ | 675 | 2.7% (18/675) | **45.5% (307/675)** | **+42.8 pp** |
| Qwen3-VL-32B (occlusion) | 160 | 22.5% | 15.6% | −6.9 pp |
| Qwen3-VL-8B (occlusion) | 160 | 33.1% | 25.0% | −8.1 pp |

**H_A2 and its occlusion replication both fail** (1 of 3 and 0 of 2 runs reach the bar). The reversal is not a
parsing artefact: for all 307 of those items the stored response is literally `{"count": 0}`. That is, telling
InternVL2.5-8B-AWQ not to answer 0 raised its answered-zero rate from 2.7% to 45.5%. Since this rests on a
single lineage and a single run, it is reported as a **negative result with a flagged reversal** rather than as
a general claim.

**(d) The association, computed as a screening step and explicitly not as a cause.** With 10,000 stratified
permutations over 71 strata and 15 arms, `has_ABSTAIN_PERMIT` tracks the arm-level zero rate
($\rho = -0.630$, $p = 0.0014$) and `has_FORMAT` is exactly null ($\rho = 0.000$, $p = 1.000$), while
`has_ZERO_FORBID` is **not** individually significant ($\rho = +0.284$, $p = 0.240$). Leave-one-arm-out MAE
improves when the two contract features replace the intercept (0.1790 → **0.1612**) but degrades when all seven
features are used (0.1724), i.e. the small arm count overfits. The frozen criterion required *both* contract
features to be significant, so **H_A5 fails as specified**. The honest reading matches (c): essentially all of
the signal sits in the abstention-permission clause.

**(e) A measurement note.** In the released corpus
files the exit arms store the abstention as a **parse failure**: 86.9–100% of their rows have an empty `pred`
while `raw` contains the abstention token verbatim (`permit` 16,647 of 19,051 empty against 16,555 containing
it; `channel` 18,219 against 18,212; `permitB`/`permitC`/`channelB` 1,981 against 1,981). Reading `pred` alone
would silently convert "abstention rate" into "parse-failure rate" and produce a self-contradictory
$\Delta$zero without a matching $\Delta$abstention. The amended criteria only repair the instrument and leave
every threshold unchanged. The paper's own corpus numbers are unaffected, because the authority analyser
counts abstention by scanning all columns other than `pred`/`gt`, which already includes `raw` (Appendix Z). **This is the same dead parse branch as M.6 and M.31.6**; here the abstention token carries no digit, so the recovery that works in M.6 does not apply.

**(f) Independent recomputation.** `pA_indep_check.py` re-derives every headline number above from the raw CSVs
with a separately written implementation (different file discovery, count-based rather than rate-based
aggregation, an independent abstention regex) and reports 0 discrepancies. The one initial discrepancy, 0.8 pp
on Qwen3-VL-32B, was traced to the frozen `min_cell_n = 20` filter excluding a 6-item cell, and is printed
rather than absorbed. `pA_analyze.py --selftest` provides positive *and* negative controls for both the
clause-permission and clause-forbidding criteria.

**What this adds, stated within its limits.** The bundle-level claim of §M.19.10–§M.19.11 can now be assigned to
a clause: on a minimal pair the abstention-permission clause alone moves the zero rate by 10–88 pp across four
lineages, and wording — including language — moves it by at most 0.1 pp. The forbidding clause does not behave
symmetrically, and on one lineage it backfires. Blocks B and C are controlled synthetic grids and Block A is an
observational comparison across arms, so no clause-level claim here is extended to the corpus-frequency
statement of §8.2.

*Reproduction: `prompt_features.py` (with `--selftest`), `pA_freeze_criteria_v2.py`,
`pA_criteria_frozen_v2.json`, `pA_analyze.py` (with `--selftest` and `--audit`), `pA_result_v2.json`,
`pA_indep_check.py`, and the twenty paired grid CSVs released under `data/derived/pA/`. The void first-version
criteria and result are retained alongside.*

#### M.19.13 What actually moves the zero is the *value named in the instruction*, not the prohibition of zero

§M.19.12 attributed the contract effect at clause level, but did so on the real-image corpus, where arms are
*pairwise* rather than experimentally composed. This section repeats the question on the **deterministic disc
grid** of §M.19.10 (675 images, explicit seeds, per-image md5, manifest `9eef8a074cf1`) and adds a diagnostic
that separates two things the earlier arms confounded: *mentioning* a candidate value, and *prohibiting* one.
Four arms share one TASK/ENUM/FORMAT skeleton and differ only in the sentence after the first full stop:

| arm | tail clause | mentions `0` | permits `0` |
|---|---|---|---|
| `base` | none | no | yes (implicitly) |
| `neutral0` | "it may be 0; if your judgment is 0, answer 0" | **yes** | **yes** |
| `forbid0` | "do not answer 0; if you think it may be 0, give your closest estimate" | **yes** | **no** |
| `placebo100` | "it may be 100; if your judgment is 100, answer 100" | no | yes |

All six families were run over all 675 items in one serving session per family, with criteria frozen before any
rate was computed (`p1d_criteria_frozen.json`, `p1e_criteria_frozen.json`, `p1f_criteria_frozen.json`).

| family | `base` | `forbid0` | `neutral0` | `placebo100` | \(\Delta\)(`forbid0`−`base`) | \(\Delta\)(`neutral0`−`base`) |
|---|---|---|---|---|---|---|
| Phi-3.5-Vision | 13.5% | 8.0% | **100.0%** | **0.0%** | −5.5 pp | **+86.5 pp** |
| Qwen3-VL-8B | 9.9% | 13.9% | **78.7%** | **0.0%** | +4.0 pp | **+68.7 pp** |
| llava-OneVision-7B | 6.7% | 2.8% | 46.7% | 0.7% | −3.9 pp | **+40.0 pp** |
| gemma-3-12b | 0.0% | 0.0% | 0.1% | 0.0% | 0.0 pp | +0.1 pp |
| Qwen3-VL-32B | 15.4% | 3.7% | 63.7% | **0.0%** | **−11.7 pp** | **+48.3 pp** |
| InternVL3.5-8B | 0.0% | 0.0% | 2.1% | 0.0% | 0.0 pp | +2.1 pp |

**The prohibition does not carry the effect.** `forbid0` reaches the −10 pp bar in **one** of six families
(Qwen3-VL-32B, −11.7 pp); the rest are −5.5, +4.0, −3.9, 0.0 and 0.0 pp — **H_A2p fails as specified**. Nor does
the reversal reported at corpus level (§M.19.12) reproduce here: the largest positive movement is +4.0 pp against
a +10 pp trigger, so that reversal is a property of the one lineage it was measured in rather than of the
instruction.

**The mention does.** `neutral0` — which *permits* zero and only differs by naming it — raises the zero rate by
+40.0 to +86.5 pp in every family that answers zero at all, while `placebo100`, identical except that the named
value is 100, lowers it in every such family. Under the frozen ratio test the effect is **token-specific in five
of six families**; Qwen3-VL-32B lands at ratio 0.32 against a 0.30 bar and is reported as **partial**, not folded
into the pass.

**The ladder: the median answer is the named value.** Fixing the sentence and varying only the named number over
{0, 5, 50, 100, 800} gives, for Phi-3.5-Vision and Qwen3-VL-8B, medians of exactly **0 / 5 / 50 / 100 / 800** —
\(\rho(\text{median},\text{anchor}) = +1.00\) for both. The frozen monotonicity test on the zero rate
(\(\rho \le -0.8\)) **fails in three of four families** at \(\rho = -0.71\), and the reason is a floor rather than
a contradiction: once the anchor is 5 or larger the zero rate is pinned at 0.0%, so four of five points tie and
the rank correlation cannot fall below −0.71. That is a defect in how the criterion was written, and it is
recorded as a failure rather than repaired after the fact.

**The zero anchor is the special case.** Anchors 5, 50, 100 and 800 are obeyed by every family measured; anchor
`0` is obeyed only by lineages that already answer zero under `base` (Phi-3.5-Vision 100.0%, Qwen3-VL-8B 78.7%,
Qwen3-VL-32B 63.7%). The pre-registered negative control was gemma-3-12b, expected not to move. Its **zero rate**
indeed does not (0.0% → 0.1% → 0.0%), but its **median answer is fully captured**, collapsing from 246 under
`base` to 5, 50, 100 and 800 under the corresponding anchors. The control is therefore **partially falsified**,
and the honest statement is narrower than the one it was meant to license: the anchor is obeyed universally, but
the *zero* exit is only available to lineages that already use it.

**Noise.** The `base` arm was re-run in the new session and reproduced the published per-family zero rate to
**0.00 pp in all six families**. Three same-session repeats of `base` were byte-identical in **100.0%**, 99.3% and
99.3% of items with \(\Delta\)zero = **0.000 pp**; the cross-session comparison was 97.5% byte-identical, again at
\(\Delta\)zero = 0.000 pp. Token-level near-ties do flip occasionally; the aggregate rate does not move.

**What this changes.** The bundle-level claim of §M.19.10–§M.19.11 survives, but its mechanism statement has to
be re-worded: what the zero responds to is the **value named in the instruction**, and the prohibition of zero is
a weak, lineage-dependent modulation on top of that. The corpus-level §M.19.12 result is consistent with this —
there, the arm that permits abstention also names the exit token, and the arm that forbids zero also names zero.

*Reproduction: `p1d_make_prompts.py`, `p1d_freeze_criteria.py`, `p1d_probe.py`, `p1e_make.py`, `p1f_make.py`,
`p1x_run.sh`, `p1q_gpu0.sh`, `p1q_gpu1.sh`, `p1df_analyze.py`, `p1df_result.json`, `_p1d_indep_check.py`, and the
per-item CSVs of all four arms; the frozen criteria and prompt files are released with them.*

#### M.19.14 Where the effect lives: the value-position distribution, and the residual stream

§7.6 leaves the mechanism of the directional contract effect open. Two probes address it, both on
Qwen3-VL-8B-Instruct, both with criteria frozen before the numbers were seen.

**(a) The value-position distribution.** Reading `logprobs` with `top_logprobs = 20` at the first digit-bearing
token over the dense-domain zero pool, the zero mass at that position collapses under `forbid0` by a median
relative amount of **0.999** (32B) and **0.672** (8B), and the value the arm finally emits lies in `base`'s top-5
at that position in **0.0%** and **2.7%** of items. The suppression is therefore not a reallocation of mass onto
candidates the zero already dominated. Coverage of the aerial pool was incomplete in the original run and has
been completed at a longer context: **179 of 180** items for both families, against 78 of 180 and 117 of 180
before. The remaining single item still exceeds the context.

**(b) The residual stream.** For the same family on the σ = 8 stratum (135 items), three arms were generated
greedily and the hidden states were read at the position that *predicts* the first generated token, for all 37 tensors
(embedding output plus 36 layers). At that position the probability of the token `0` averages **0.432** under
`base`, **0.355** under `forbid0` and **0.998** under `neutral0` — so the arm that merely names zero all but
guarantees it, as §M.19.13 would predict.

The layerwise cosine between the residual stream under `base` and under each arm stays above **0.968**
(`forbid0`) and **0.914** (`neutral0`); the representation barely moves in magnitude. Its *direction* is where
the two arms differ. Projecting the mean change onto the unembedding row of the token `0`:

| arm | at the first below-0.99 layer | at the last layer | largest magnitude, any layer |
|---|---|---|---|
| `forbid0` | +0.040 | −0.085 | 0.085 (last layer) |
| `neutral0` | +0.036 | +0.020 | **+0.267** (layer 33) |

For `neutral0` the projection grows steadily through the late layers, reaching +0.267 at layer 33: naming zero
drags the representation toward the zero readout direction, concentrated in the last third of the network. For
`forbid0` **no layer shows a projection beyond 0.085 in magnitude**, i.e. the change is essentially orthogonal to
the zero direction at every depth. The prohibition moves the value-position probability by 0.077 while leaving
the representation's component along the zero axis untouched.

**Two criteria are reported as failures rather than resolved in the favourable direction.** The layer-selection
criterion did not define its denominator — the first crossing is at 18 of 37 tensors, which is 0.486 under one
reading and 0.500 under the other — so it is recorded as **undetermined** rather than as a pass. And the
direction criterion specified both "negative projection" and "magnitude below 0.1" without ordering them; the
measured −0.085 satisfies both, and the **weaker** claim (a readout-level change) is the one adopted.

**The tension with (a), stated rather than smoothed.** Reading (a) as "recomputation rather than reallocation"
and (b) as "orthogonal to the readout direction" are different statements, and only the first is supported by
emitted-value evidence. What (b) adds is that the prohibition's effect is **not** explained by the representation
moving along the zero axis; the model reaches a different output distribution without that particular movement.
The mechanism therefore remains open in the specific sense §7.6 meant, and is not closed here.

*Reproduction: `p5a_probe.py`, `p5b_run.sh`, `p5c_hidden.py`, `p5c_analyze.py`, `p5c_result.json`,
`p5c_results2_summary.json`, `_p1d_indep_check.py` (which re-derives the hidden-state summary from the per-item
records without reading it), and the per-item records of both probes.*

#### M.19.15 The same panel in the headline's own quantity: the dense result is a *build* property

M.19.3 compares the seven families on the **answered-zero rate**. The headline is the **abstention share**
$S$, so we computed it on the same census files and on each family's comparable item sets (dense =
st_a + ucf, aerial = VisDrone + AI-TOD). The two denominators are reported separately, because $S$ requires
the **full** item set and not the zero pool: computing it on the zero pool alone inflates it, for one family
to 71.50% against the correct 28.78%.

| family | dense zero-pool rate | dense $S$ | aerial zero-pool rate | aerial $S$ |
|---|---|---|---|---|
| Gemma-3-12B | 0.00% | *n/a* | 3.00% | *n/a* |
| InternVL3.5-8B | 0.79% | 1.43% | 51.33% | 19.56% |
| Phi-3.5-Vision-4.2B | 0.00% | *n/a* | 66.33% | *n/a* |
| LLaVA-OneVision-7B | 0.00% | *n/a* | 80.20% | 28.78% |
| InternVL2.5-8B-AWQ | 0.00% | *n/a* | 76.67% | 27.07% |
| **Qwen3-VL-32B-AWQ** | **95.26%** | **90.30%** | 98.33% | 59.12% |
| **Qwen3-VL-32B-BF16** | **64.03%** | **82.27%** | 95.33% | 49.66% |
| Qwen2.5-VL-72B-AWQ | 0.00% | *n/a* | 71.33% | 51.82% |
| InternVL3.5-38B-fp8 | 7.38% | 18.28% | 78.00% | *n/a* |
| **InternVL3.5-38B-BF16** | **9.56%** | **23.20%** | **76.33%** | **31.91%** |

*`n/a` marks a cell with no abstentions. That is **not** the same as $S$ being undefined: the closed form
$S=(1-w)/[1-w(1+\rho_{\text{answered}})]$ is defined at $w=1$, where it returns **$S=0$** (no abstention,
no abstention share), and the cell would then print `0`. `n/a` is reserved for the genuinely undefined case,
a **net over-count on the answered subset**, $\rho_{\text{answered}}>0$, which carries $S$ above 1 — the
denominator $1-w(1+\rho_{\text{answered}})$ itself vanishes only at the boundary
$w(1+\rho_{\text{answered}})=1$, which is a different condition — so
the share has no interpretation; that is the same condition §3.8 states in closed form and the one §M.46(b)
uses to mark ShanghaiTech-A's English share. A no-abstention cell and a net-over-count cell therefore do not
belong under one label.* Comparable item sets:
253 dense and 300 aerial on the zero pool; 482 and 499 on the full set. Qwen3-VL-32B-AWQ is the
configuration that **defined** the zero pool. **The fp8 38B row's denominator is 244, not 253.** Nine of the 253 dense items returned an empty `pred`
and are excluded from pooled rates, so the row reads **18/244 = 7.38%**, Wilson 95% **[4.72, 11.36]**
(the exclusion rule itself is stated with the frozen criteria above). **Two of these cells are quoted
elsewhere under the raw intersection instead, and the two calibers are not interchangeable:** applying the
frozen exclusion rule leaves LLaVA-OneVision-7B's aerial arm at **235/293 = 80.20%** and Phi-3.5-Vision's at
**197/297 = 66.33%**, whereas on the raw **300**-item intersection the same two arms read **235/300 = 78.3%**
and **197/300 = 65.7%** — the caliber §M.19.3 (and §M.22) quotes. The numerators are identical; only the
denominator moves, and each statement names its own.

**On the dense domains the headline does not reproduce in any other family.** Of the **ten** families and
builds screened, **none** other than the two Qwen3-VL-32B precisions reaches either a dense zero rate of
30% or a **dense** share of 50% — a qualifier the table needs, because an **aerial** share of 51.82%
does occur elsewhere on it (Qwen2.5-VL-72B-AWQ) — including a **larger build of a non-Qwen family**
(InternVL3.5-38B-fp8: dense
zero-pool rate **7.38%** [4.72, 11.36] over **244** items — the nine of 253 with an empty `pred` are
excluded from the rate, per this appendix's rule — share **18.28%**), whose printed dense reading is a **single** run — re-run here over **three fresh service starts** (§M.19.17) — and which is an **fp8** build,
so its precision axis moves with its family axis and the two cannot be separated from this row alone. **Its rebuild at BF16 — a larger non-Qwen build at the anchor's own precision, the cell this panel was missing — reaches only 9.56% (24/251, Wilson 95% [6.51, 13.83]) with a dense share of 23.20% over three fresh service starts, so it clears neither bar; and on the 244 items its two weight formats share, its fp8 and BF16 builds differ by +0.41 pp (95% [−2.05, +2.87]).** The precision axis on the **anchor's** own checkpoint spans three weights on the identical 253 items and is reported there as **indeterminate**, not as a small effect (§M.19.17). Eight of the ten rows therefore fall below the bar, and the two that clear it are the
same checkpoint at two precisions. **The count in §8.2 is this panel minus the anchor row itself**: the ten rows here
are the anchor build (Qwen3-VL-32B-AWQ, the configuration that defined the zero pool) plus nine further
families and builds, of which eight fall short and the ninth is the same checkpoint at BF16 — so the
"eight of nine" of §8.2 and the "eight of the ten" above are the same eight failures, and the two rows
that clear the bar are one checkpoint at two precisions. **The same checkpoint at BF16 clears the bar and does not reproduce it whole**: on the identical item sets it holds **82.27%** of the share (against **90.30%**, a paired bootstrap difference of **−8.03 pp**, 95% **[−12.37, −3.75]**) while the answered-zero rate falls from **95.26%** to **64.03%**. The **share** is therefore a build-level quantity and the **rate** is a build-and-precision one on this checkpoint — though not on every one: on the 38B build the weight format does not move it at all (0.41 pp; §M.19.17) — which is the narrower reading §8.2 now states. Three denominators must not be crossed here: **64.03%** is the dense **intersection** (253 items), **65.02%** is this build's **own** dense zero pool (283 items), and **33.61%** is the dense rate on the **full** item set (482 items). This is sharper than "lineage- or build-specific": **the other Qwen anchor (AWQ) fails
as well** (dense 0.00%); the BF16 build of that same checkpoint clears it (64.03% / 82.27%). What the cross-family grid therefore supports is that the dense abstention channel
belongs to **that build in that configuration** — the same conclusion §8.2 reaches from the five-deployment
spread, now measured in the headline's own quantity.

**The aerial half is the mirror image, and the more informative one.** There the **five non-Qwen families** answer zero on
**51–80%** of the items, with Wilson lower bounds of **46–75%**, so the difference from the corpus
configuration is real — yet their **share is only 19.6–28.8%** (defined for three of the five), because
their *answered* items under-count
heavily in their own right and the ratio absorbs it. "The model answers zero often" and "the under-count is
dominated by abstention" are therefore separable within one table: the two-kinds statement of §5.7, in the
headline's quantity. On the **aerial** domains the same BF16 rebuild answers zero on **76.33%** of the aerial pool — **1.67 pp** below the fp8 row's **78.00%**, the three fresh starts spanning **76.33–76.67%** — while its aerial **share** is only **31.91%**: about half the third-party 4-bit anchor's **59.12%**, and above the **19.6–28.8%** of the five smaller non-Qwen families. **On these domains a family's rate and its share therefore come apart**: this build matches the fp8 row's rate while its selectivity sits at roughly half the anchor's.

*Reproduction: `analysis/work/n4_cross_family_dense_panel.py` (historical digest `9c74db226c1b785361807ebc7e069771`; the shipped file hashes to `be89dd9821b1b796d6d26765b760c92c`, which is its `MANIFEST.csv` row, a literal-only change disclosed in the release README, behaviour unchanged, and re-issued with external-check traces removed only, values unchanged); it
reproduces M.19.2's per-family base zeros and M.19.3's dense rates exactly. **One trap is worth recording**:
the anchor family's files carry duplicate rows with a `#r` suffix (309 of 412 on st_a, 540 of 720 on ucf);
the analyser's loader excludes them, and not excluding them **quadruples** the count (407 and 673 rather
than 103 and 180, i.e. 102 and 166 zeros) and silently breaks agreement with M.19.2.*

##### M.19.15.1 A same-family cross-precision sidelight (not a precision axis)

A **directional sidelight, not a precision axis**: the **8B** BF16 build of this family answers zero on **0.79%** of its dense pool against **7.38%** for its **38B** FP8 build (paired bootstrap over the 244 shared items, seed 20260930: **+6.97 pp, 95% [+4.10, +10.66]**), and the same 8B build is itself at **51.33%** on the aerial domains, well below the 38B build's **78.00%**. Both dense readings sit far below the 30% bar, so the direction is compatible with a
family-level rather than precision-level reading, without measuring it. The sample is **one family at two scales**, so it supports no family-level or lineage-level statement, and its denominators (253 / **244** dense, 300 aerial) are its own — on the **244** items the two builds share, this 8B BF16 build reads **1/244 = 0.41%** against **18/244 = 7.38%** for the 38B FP8 build, a difference of **17 of the 244 items (6.97 pp)**, which is the **+6.97 pp** quoted just above. (The **+0.41 pp** quoted in §M.19.15 is a *different* contrast — that build's own fp8 against its own BF16, on the same 244 items.)

---

#### M.19.16 The value named in the instruction, on the four headline cells and in English

§M.19.13 established on the deterministic disc grid that what moves the zero is the **value named in the
instruction** rather than the prohibition of zero: adding "it may be 0; if your judgement is 0, answer 0"
raised the zero rate by up to **+86.5 pp**, while prohibiting 0 barely moved it. Two questions follow that
the grid cannot answer — does the mechanism hold on the **real corpus** in the headline configurations, and
does it survive a change of **prompt language**? A reviewer asked for exactly this closure.

**Design, frozen before the run** (`g_criteria_frozen.json`, md5 `d95d7466b482f575dc781d152e5ddf23`; re-issued: external-check traces removed only, values and criteria unchanged): five
arms on the **same item sets as the corpus pools**, one serving session per arm, the frozen probe of §M.19
with its md5 asserted, and the criteria fixed in advance — the **+10 pp** action threshold of §M.19.13 and
the two robustness thresholds below. Every `neutral0` arm is its language's own `base` prompt **plus one
sentence**, asserted character-by-character at start-up, so each contrast is single-variable.

| domain | cn `base` | cn `neutral0` | Δcn | en `base` | en `neutral0` | Δen | δ | δe |
|---|---|---|---|---|---|---|---|---|
| ShanghaiTech-A | 31.9 | **92.3** | **+60.4** | 10.4 | **89.0** | **+78.6** | +18.1 | +2.2 |
| UCF-QNRF | 30.0 | **92.3** | **+62.3** | 11.6 | **92.3** | **+80.7** | +18.4 | 0.0 |
| VisDrone | 63.8 | **76.2** | +12.5 | 64.2 | **74.0** | +9.8 | −2.8 | +1.2 |
| AI-TOD | 63.7 | **77.9** | +14.2 | 64.2 | **75.2** | +11.1 | −3.1 | +0.9 |

All entries are answered-zero rates in percent. `δ` is the Chinese-versus-English difference of the effect;
`δe` is the difference between the two English renderings of the tail clause (with and without the emphasis
markers the archived Chinese string carries, which we could not resolve from the archive). Item counts are
the full corpus pools (182 / 334 / 400 / 226); UCF-QNRF loses **127 of 334** items to the context-limit
error of the same kind disclosed in §M.39 (which reports **203 of 334** for its own run — the two runs differ),
and those are reported as **unmeasured rather than filled in**.

**The mechanism reproduces on real images, and it is larger on the dense domains.** The added sentence lifts
the zero rate by **+60 to +81 pp** on the two dense domains and by **+10 to +14 pp** on the two aerial ones —
the ordering the corpus-wide statistics show, and the opposite of what the prohibition arm did on the grid.
**It is language-robust**: the effect differs between Chinese and English by **3 to 18 pp**, inside the
pre-registered 20 pp band in **4 of 4** domains. **It is insensitive to the rendering of the tail clause**:
the two English variants differ by **0.0 to 2.2 pp** (4 of 4 inside the band), so the emphasis markers are
not what carries the effect.

**Three further results, one of which is a criterion we fail.**
*(i) The English prompt suppresses abstention on the dense domains only.* The English `base` arm answers zero
at **10.4%** and **11.6%** where the Chinese does at **31.9%** and **30.0%** — 18 to 22 pp lower — but on the
two aerial domains the languages are indistinguishable (**64.2% vs 63.8%** and **64.2% vs 63.7%**). The
language effect is a **dense-domain** effect, which narrows the scoping statement of §8.2.
*(ii) The share is not always a share.* Three of the twenty cells leave the unit interval: **102.9%** on
UCF-QNRF `cn-base`, **610.8%** on ShanghaiTech-A `en-base`, and **undefined** on UCF-QNRF `en-base`, whose
net deviation is **+0.4%** (49% of its bootstrap draws are undefined too). This is not a formula error:
`S = (G−G_N)/(G−P)` leaves `[0,1]` exactly when the **answered** subset over-counts, making the answering
term positive. It is the crossing §M.39 already reports for the English headline cell, here reproduced in a
second configuration. We report it as a **failed pre-registered criterion** and state the limitation in the
main text rather than dropping the cells.
*(iii)* On UCF-QNRF the three arms `cn-neutral0`, `en-neutral0` and `en-neutral0em` agree to the item —
**92.3%, 92.3%, 92.3%**, with identical shares — so that arm saturates.

*Reproduction: runner `g2_neutral0.py` (md5 `3517fcd0061842b1d84dbad50a260f34`), analysis `g2_analyze.py`,
design and criteria `g_criteria_frozen.json` (md5 `d95d7466b482f575dc781d152e5ddf23`; re-issued: external-check traces removed only, values and criteria unchanged); the twenty per-arm
CSVs and their md5s are listed in the result JSON. The harness is validated against a known result: the
`en-base` arm re-run here reproduces §M.39's own English `base` arm at **180 of 182 items (98.9%)** on
ShanghaiTech-A. Absolute rates are **not** comparable to the corpus pool's, which was drawn from a 4-bit
build, whereas this run uses the BF16 build (the quantised build is not on this machine); every difference
above is within-run and within-language.*


#### M.19.17 The missing cell, filled: a larger non-Qwen build at the anchor's own precision

M.19.15's 38B row is the panel's only large non-Qwen build, and it is an fp8 one, so its two axes move
together. The cell that separates them — **same family, same size, at the anchor's own precision** — had not
been run. We ran it: **InternVL3.5-38B rebuilt at BF16**, on the same frozen item sets and the same
prompt set and parser, with **three fresh service starts** and the served configuration held to the panel's own
(`max-model-len` 8192, `max-num-seqs` 24, one image per prompt, temperature 0, four-way concurrency).

| start | dense zero-pool rate | Wilson 95% | $n$ | dense $S$ |
|---|---|---|---|---|
| 1 | **24/251 = 9.56%** | [6.51, 13.83] | 251 | 23.20% |
| 2 | **21/251 = 8.37%** | [5.54, 12.45] | 251 | 20.41% |
| 3 | **23/251 = 9.16%** | [6.18, 13.37] | 251 | 21.90% |

**The denominator is 251, not 253**, for the reason this appendix's rule states: two of the 253 dense items
returned an empty `pred` in each start and are excluded from the pooled rate. The share $S$ is computed on
the **full** dense set (480 items after the same exclusions), not on the zero pool. All three starts fall
below both bars — a dense rate of 30% and a share of 50% — and the Wilson **upper** bounds are
13.83 / 12.45 / 13.37%, so the failure does not turn on which start is read. The most conservative of the
three starts — the largest, 9.56% — is also below both bars; the three
starts' zero / non-zero classification flips on 12 of 753 item pairs (1.59%).

*Reproduction: the three service starts' per-item records for this build are released
(`data/derived/e2/e1_internvl35-38b-bf16_{densezero,densenonzero,aerialzero,aerialnonzero}_s{1,2,3}.csv`,
twelve files). Recomputing from them reproduces every number in the table above directly: the dense zero-pool
rate is **24/251 = 9.56%**, **21/251 = 8.37%** and **23/251 = 9.16%** (the denominator is 251 because two of the
253 items return an empty `pred` in each start), the aerial arm answers zero on **229 / 230 / 230 of the 300**
pool items, and the share $S$ — the answered-zero channel's contribution to the dense set's under-count,
$\sum \mathrm{gt}$ over answered-zero items divided by $\sum \mathrm{gt} - \sum \mathrm{pred}$ over the full
dense set (the 253-item pool plus the 229-item non-zero control, **480 items after the same exclusions** —
the two zero-pool rows with an empty `pred` are dropped from $\sum \mathrm{gt}$ as well as from
$\sum \mathrm{pred}$) — is **25{,}874/111{,}503 = 23.20%**,
**22{,}168/108{,}640 = 20.41%** and **24{,}290/110{,}906 = 21.90%** for starts 1–3.*

**The aerial arm of the same build, and the fp8 row's cross-start check.** The identical serving configuration answers zero on **229 / 230 / 230** of the **300** aerial-pool items across the three fresh starts (**76.33 / 76.67 / 76.67%**, Wilson lower bounds **71.21 / 71.56 / 71.56%**), with the zero/non-zero classification flipping on at most **2 of 300** item pairs (**0.67%**) — inside the ≤1% band, so the three starts may be pooled. Its aerial share $S$ is **31.91 / 31.76 / 31.98%**. The fp8 row, by contrast, is archived as a **single** run, so we re-ran it on the identical dense item set with three fresh service starts: **8.87 / 8.91 / 8.47%** (**22/248**, **22/247**, **21/248**), $S$ **22.37 / 21.50 / 20.48%**, with **1.21%** of item pairs flipping — the (1%, 5%] band, where the three starts are read side by side and the most conservative (**8.91%**) is quoted. The archived single run's own per-item records are in the released package, so the re-runs can be paired against it item by item on the **244** items both parse: the differences are **+0.41 / +0.41 / +0.00 pp** (95% **[−1.64, +2.87] / [−1.65, +2.47] / [−2.05, +2.46]**, all crossing zero), with **236–237 of 244** items agreeing in classification. **The "run once" qualifier on that row is therefore a provenance statement, not a stability one**: nothing in these three starts separates them from the single run they repeat.

*Reproduction: the archived single run is in the released package (`data/derived/e2/e1_internvl35-38b-fp8_{st_a,ucf}_base.csv`); recomputing from it reproduces that row's **18/244 = 7.38%** and **[4.72, 11.36]** exactly, which is the acceptance check for the pairing above. The aerial arm and the three fp8 re-runs are per-item records in the released package (the released aerial per-item records `E5_aerial_{zero,nonzero}_start{1,2,3}.csv` and `E1_fp8_dense{zero,nonzero}_start{1,2,3}.csv`).*

| axis | held fixed | items | readings | paired difference, 95% |
|---|---|---|---|---|
| **family** | BF16 | 251 | Qwen3-VL-32B **63.75%** vs InternVL3.5-38B **9.56%** | **−54.18 pp** [−60.56, −47.81] |
| **weight format** | InternVL3.5-38B | 244 | fp8 **7.38%** vs BF16 **7.79%** | **+0.41 pp** [−2.05, +2.87] |
| **weight format** | Qwen3-VL-32B | 253 | AWQ-4bit **95.26%** / BF16 **64.03%** / FP8 **80.24%** | span **31.23 pp** |

Three things follow, and one of them is a limit. (i) **With the weight format fixed, the family difference
is large and its paired interval does not cross zero.** (ii) **With this build fixed, re-weighting it does
not move the quantity**: its own fp8 and BF16 builds differ by 0.41 pp over the 244 items they share, so
the weight format does not account for the 38B row's distance from the anchor. (iii) **On the anchor's
checkpoint the same axis is indeterminate rather than small**: three weights span 31.23 pp on the identical
253 items, which is neither "the axis explains the 87.88 pp gap" nor "it does not", so we report it as a
band and not as a magnitude. That band is the pre-registered reading for the anchor's checkpoint; the
0.41 pp above is a **two**-point figure on a **different** checkpoint and is not a substitute for it.

A same-family, cross-scale sidelight bearing on the same question — and the confound that keeps it
directional rather than a precision measurement — is recorded separately in §M.19.15.1.

*Reproduction and scope: the BF16 rebuild's per-item records are in the released reproduction
package (the released per-item records `B1_{zero,nonzero}_start{1,2,3}.csv`); the frozen item list, the served configuration, and the instrument — a derived probe whose prompt
set and parser are taken verbatim from the panel's own (`19e_probe_multi.py`, md5
`03edb14c98ffa3aea9ffa20f59b00bc8`), itself at md5 `e7a65fd47345c2fe040fa4d05a3b1d86` — are recorded with
them. The 38B-fp8 reading is this appendix's existing single-run row and
carries the cross-session term that a multi-start reading would not, so the second row of the table above is
item-paired but not start-paired.*


#### M.19.17.1 The language axis, measured on the same build instead of left to the scope clause

§M.19.17 separated the family axis with the weight format held fixed. The **language** axis on the same build had
not been run: the table above, like the anchor's own rows, is a Chinese-prompt reading, and §5.5 and §M.39
therefore scope their shares to "Chinese prompts" and to one anchor build. We ran that missing cell directly — the
**same BF16 build**, the **same frozen 482 dense items**, the same parser and the **same served configuration** as
the table above (`max-model-len` 8192, `max-num-seqs` 24, one image per prompt, temperature 0, four-way
concurrency), over the **same three fresh service starts**, with **only the prompt language changed**. Five cells
were run per start (Chinese `permit` / `channel`; English `base` / `permit` / `channel`) plus a Chinese `base`
control on start 1, 7{,}712 calls in all. The criteria were frozen before the run
(`_p0a_criteria_frozen.json`, md5 `0313b1ad829dd6afd2657f85a37dbffd`).

| dense zero pool (253 items), start 1 | answered zero, of 253 | answered zero, of the answered | refuses to give a number |
|---|---|---|---|
| Chinese `base` (this run) | **25 = 9.88%** | 25/250 = 10.00% | 3 = 1.19% |
| Chinese `base` (archived start 1, §M.19.17) | 24 = 9.49% | **24/251 = 9.56%** | 2 = 0.79% |
| **English `base` (this run)** | **1 = 0.40%** | 1/156 = 0.64% | **97 = 38.34%** |

**Two readings of the English refusal must be separated, because the difference is a lexicon difference and not a
type difference.** This appendix's existing analyses recognise a refusal by three words in the raw response
(`abstain`, `cannot_judge`, `no_people`). Under that lexicon **none of the 97 rows above is recognisable**:
**95** are prose — *"I'm unable to count the exact number of people in the image."* — carrying **no `count`
field and no digits at all**, so the instrument's own fallback (a search for `-?\d+` over the whole response)
finds nothing and records `parse_ok = 0` exactly as it does for an explicit `{"count": "abstain"}`; the remaining
**2** carry a `count` string that the three words do not cover (`"large crowd"`). The English refusal rate is
therefore **0.00% (0/253)** on the narrow lexicon and **38.34% (97/253)** on the reading that treats a refusal as
a refusal however it is worded. Both are reported; neither is used to the exclusion of the other, and the same
gap applies to this appendix's own Chinese rows, whose refusals are a short Chinese sentence rather than any of
the three words — which is why the two calibers are reported side by side wherever a refusal rate appears.

**What is invariant across those two readings: the English arm stops producing numbers.** Numeric answers fall
from **250 of 253** items to **156 of 253**, and the answered-zero count falls from **25 to 1**. The language axis
therefore neither creates nor removes the abstention channel — it decides **which form the channel takes**. Read
with §5.5 that is the expected direction: the answered zero is the form the channel takes when the prompt neither
offers an outlet nor is answered in prose, and an English prompt is answered in prose. The residual *rate* is what
does not transfer, which is exactly why the shares of §5.5 are scoped to the prompt language: this subsection
turns that scope from a caveat into a measurement.

Three further readings from the same run. (i) **The build's distance from the anchor survives the language
change**: over the identical 253 items the Chinese arm is **−54.15 pp** from the anchor's printed `64.03%`
(itself 162/253 on the dense intersection) and the English arm **−63.63 pp**, both same-signed and both large, so
§M.19.17's family reading is corroborated on a second axis rather than weakened. (ii) **The contract arms are saturated in both languages**: `permit` and
`channel` answer zero on none of the 253 items and refuse on **100%** of them, and the same holds on the 229-item
non-zero control, inside the **88.6–100%** band §M.18.5 already prints for the dense non-zero pool — a
consistency check, not a new finding. (iii) **The three starts agree**: across starts the answered-zero rate spans
at most **0.21 pp** and the share $S$ at most **0.74 pp**, well inside the across-repeat band of §A.

**The pre-registered control, reported as it came out.** The Chinese `base` control was frozen with the
expectation that it reproduces the archived start's **24/251**. **It does not reproduce at that level**: the
re-run gives **25/253 = 9.88%** (9.49% of 253, 10.00% of the 250 it answered). We record that gate as **failed as
written** rather than redefining it after the fact. The context that makes it readable is that the archived row is
itself one of **three** starts whose own answered-zero counts are **24 / 21 / 23** (9.56 / 8.37 / 9.16% — a 1.19 pp
span on the same instrument), that the re-run lands **+0.32 pp** above that maximum and inside the across-repeat
band this appendix already prints (**2.15–6.46 pp**, §A), that **239 of 253 items (94.47%)** agree item by item
and **252 of 253 (99.60%)** agree in answer type, and that all 13 disagreements are single-tier flips of the
count. A locally served greedy decoder under continuous batching is not bit-identical item by item, which is what
§A already reports for four-worker concurrency (**4.28%** of items differing by ±1–2). The control's purpose —
establishing that the wrapper is the same instrument as the archived run — is met at that level; the pre-registered
wording was stricter than the instrument can deliver, and is recorded as such in the run's own criteria addenda
rather than silently relaxed.

*Reproduction: all 32 per-cell records are released
(`data/derived/p0a_a800/P0A_{cn,en}_{base,permit,channel}_{zero,nonzero}_start{1,2,3}.csv`, with the Chinese
`base` control's two files also under `start1`), together with the instrument actually used (the derived probe
`pf_p0_probe.py` md5 `e7a65fd47345c2fe040fa4d05a3b1d86`, the wrapper `pf_p0a_probe.py` md5
`fe83046e7e430bd949fce816fc8b76c6`, the runner `pf_p0a_run.sh` md5 `372d5f71d1b11abcfac3efe1119a2762` and the
served configuration `pf_serve_b1_tp2_8021.sh` md5 `8b2c48458f8da5200bf0975af67798ff`), the frozen criteria and
its three addenda, the row classifier (`env/_p0a_cls.py`) and the recomputation script
(`env/_p0a_recompute.py`, self-contained and path-relative, printing `P0A_RECOMPUTE_OK`), which recomputes every
number above — both refusal calibers and the control's item-level agreement included — from the released CSVs and
the archived start. The English arms are the first English readings this build has been run under; before this run
the A800 side held Chinese arms only.*

### M.20 The annotation-free legibility proxy, tested rather than promised

§3.3 states that the proxy needs instance-level boxes and is therefore a diagnostic. The obvious
annotation-free substitute keeps the *same* functional form — per-instance pixels inside a box not covered
by another box, image-level median — but takes the boxes from a **detector**. We implemented it on
ShanghaiTech-A (182 images with corpus predictions), with criteria fixed before the runs (AUC ≥ 0.65 for a
usable triage signal; detector-to-detector spread ≤ 0.05 for stability):

| detector setting | detections per image (median) | AUC (proxy → non-zero answer) | MAE change, most-legible 20% |
|---|---|---|---|
| YOLO tiled, tile 256 | 227 | 0.629 | +47.6% |
| YOLO tiled, tile 512 | 208 | 0.559 | −20.1% |
| RetinaNet, whole image | 36 | 0.517 | +12.9% |
| RetinaNet, tile 256 | 200 | 0.492 | −47.5% |

**It fails both criteria, and not for want of tuning.** Sweeping detection score ≥ {0.20, 0.30, 0.50, 0.70}
× NMS IoU {0.5, 0.7, 0.9} (twelve settings on the best detector) gives a **best AUC of 0.641**, below the
threshold, with a spread of **0.143** and a selective-prediction gain from **−24.7% to +65.1%** — it changes
sign. The trivial baseline (number of detections) is no more stable (0.30–0.82).

**What this establishes.** The proxy's discriminating power comes from the **annotation geometry** (which
instances are genuinely separate) and is *not* recovered by swapping in detector boxes, so the "just use a
detector" route is retired. Other routes — a learned estimator, or detector-free image statistics — are not
excluded, and §7.7 states what such a rule would have to satisfy.

*Reproduction: `code/analysis/a_lightfree.py` (four detectors), `a_lightfree_grid.py` (twelve
post-processing settings), frozen results `a_lightfree_result.json`, `a_lightfree_grid.json`; inputs are
the detector box archives `analysis/data/harvest_A/{gaps__,rn__}boxes_st_a_test_*.npz` (**detector outputs on the public
corpus images; not part of the released package**) and the corpus predictions
`data/derived/e2_pools/dense_results/vlm_st_a_base_whole.csv`.*

### M.21 The formal framework in full

§3.8 in the main text states only what each statement *buys* the reader. The full statements,
derivations, verification records and scope notes are reproduced **in full** below; nothing here is
new, and none of it is offered as an empirical finding — the eight statements are either identities of
the reporting convention (2, 4, 8), decidability statements about observable quantities (1, 3),
equivariance statements (5), or a monotonicity argument that licenses a stratifier (6).

#### M.21.1 Statements 1–7 (Proposition 8 is stated at the end of §M.21.9)

**Proposition 1 (abstention is not identified by outputs alone).** Let a system map an input to a reported
value $y \in \{0\} \cup \mathbb{Z}_{>0} \cup \{\bot\}$. Two distinct latent events — the model *abstains*,
and the model *estimates zero* — both produce $y = 0$. The output therefore does **not** identify
abstention, and identification requires an **auxiliary channel** that reacts differently to the two
events. We use $\kappa = \#\{y = 0\} / \#\{\text{textual refusals}\}$; the identifying condition is
the lineage under study has a **large** $\kappa$ (we treat the criterion as operational rather than asymptotic: a lineage is usable when almost every abstention is expressed as an answered zero, and we report the measured $\kappa$ rather than asserting identification in the limit). **Corollary:** the paper's abstention headlines are
identified for the Qwen family ($\kappa = 550.6$, 0.18% missed-refusal share) and **not** for InternVL2.5-8B
($\kappa = 2.3$, 30.31%), which is why §3.6 reports the two separately rather than pooled.

**Proposition 2 (the two conventions diverge exactly when the per-image ratio correlates with ground
truth).** With $r_i = (p_i - g_i)/g_i$, the pooled convention is the $g$-weighted mean of $r$ and the
per-image convention its unweighted mean, so

$$\rho_{\text{pooled}} - \bar\rho = \frac{\operatorname{Cov}_g(g, r)}{\overline{g}}.$$

The two coincide **iff** the per-image ratio is uncorrelated with ground truth, and the divergence has
the sign of that covariance. Because abstention is itself GT-dependent (§5.11(b)), the covariance is
non-zero in dense domains by construction — which is why both are always reported here.

**Proposition 3 (span is a functional of the admitted level set).** For levels $\ell = 1,\dots,L$ with
ratios $q_\ell$, $\text{span} = 100\,(\max_\ell q_\ell - \min_\ell q_\ell)$. Two consequences: (i) any
candidate predictor built from $\max_\ell q_\ell$ or $\min_\ell q_\ell$ is a **component of the
definition**, and conditioning on the other extreme gives a partial correlation of **exactly $\pm 1$** —
which is what we observe for our own candidate (Appendix F.3) and why we withdraw it; (ii) **availability**
*is* decidable from the same quantities, since it holds iff $\max_\ell q_\ell \ge 1$ at the loosest
admitted level. The paper's position is therefore deliberately asymmetric: **availability is a decidable
property of observable quantities; magnitude is not predicted by any quantity we have been able to
construct.**

**Proposition 4 (the aggregate bias decomposes exactly).** Let $G=\sum_i gt_i$ over all items, and let
$G_N$ and $P$ be the ground truth and the predicted total over the **answered** items ($pred_i>0$), with
$w=G_N/G$. Since an abstained item contributes $pred=0$,
$$\rho_{\text{total}}=w\,(1+\rho_{\text{answered}})-1=-(1-w)+w\,\rho_{\text{answered}},$$
an identity rather than an approximation. **(i)** The aggregate under-count is therefore exactly an
**abstention term** $-(1-w)$ plus a **scaled answering term** $w\,\rho_{\text{answered}}$, which makes the
separation asserted in §5.7 a matter of construction rather than of observation. **(ii)** The abstention
share of the under-count has the closed form $S=(1-w)/[1-w(1+\rho_{\text{answered}})]$ — a function of two
observables and nothing else, and the identity behind the **82–94%** (base contract arm) of §5.5. The proof, the verification
over 95 result files, and the scope boundary are in Appendix J. **Scope:** the decomposition requires an
**additive** (ground-truth-weighted) convention and fails under the per-image-median convention — the
quantitative reason both conventions are reported, complementing Proposition 2.

**Proposition 5 (span is equivariant, not invariant, under shared affine calibration).** For
$c(q)=a+s\,q$ with $s>0$ applied to every admitted level of a unit,
$\text{span}(c\circ q)=s\cdot\text{span}(q)$. A fitted slope must therefore accompany every reported span,
and the objection that a large span is a calibration artefact **requires exhibiting $s\ll1$**, since an
affine calibration compresses a span by at most the factor $s$. Non-affine recalibration lies outside the
proposition and can compress spans, which is why the quantile map is classed as undeployable.

**Proposition 6 (targets-per-image is not a legibility-consistent stratifier).** Call a stratifying
variable $X$ *legibility-consistent* if the order it induces refines the legibility order. Then
targets-per-image $M$ is **not** legibility-consistent. VisDrone and AI-TOD have the lowest $M$
(17–22) and ShanghaiTech-A has $M=433$, yet abstention is comparable (68% vs. 57%); with abstention
monotone in legibility — which §5.6 supports causally — the two orders disagree on this pair. $\qed$ A
candidate stratifier must thus pass *monotonicity of abstention in it*; correlation with legibility alone
does not suffice, and this is what licenses stratifying by legibility rather than by OPM.


**Proposition 7 (under the two-channel assumption the identification error of the answered-zero channel is
$1/(\kappa+1)$, a lower bound).** Let a
lineage express every abstention through one of two channels only: an **answered zero** or a **textual
refusal**, and let $f$ be the fraction of abstentions that take the refusal channel. The measured
answered-zero count then estimates the true abstention count with **relative error $f$ conditional on that
same assumption** (a third channel would make it a lower bound), and since
$\kappa = (1-f)/f$ by definition, $f = 1/(\kappa+1)$.

**A usability threshold.** We treat $\kappa \ge 50$ as *complete*, since the identification error is then
$1/(\kappa+1) \le 2\%$; below that the error bar is quoted alongside every rate.

**The three quantities, and the denominator.** (i) The **observed channel fraction** is the share of
answered zeros among all outputs the system emitted, $G_N/G$ — what a report prints. (ii) The **latent
abstention rate** is the share of **items** that are not true zeros but on which the system declines to
estimate — an item-denominated quantity, **not** the abstention-denominated $f$ above, which counts only
the refusal channel among abstentions ($f = 1/(\kappa+1)$); it is **not** observable from outputs alone. (iii) The **answered-zero
channel's coverage of abstention** is the share of abstentions that this channel captures, $1-f$; its
complement $f$ is the identification error Proposition 7 bounds. Like (ii) it holds only under the
two-channel assumption.

**One symbol, three quantities — disambiguated here and used consistently below.** The written form
`G_N/G` has been used in this paper for three different ratios, and they are **not** interchangeable:
(a) **the item-denominated answered-zero rate** $G_N/G$ as just defined — the printed channel fraction;
(b) the **ground-truth-weighted answered share** $w = G_N/G$ of Proposition 4 and §3.8, i.e. the share of
*annotated objects*, not of items, that sits in the answered set; and (c) the **abstention-channel
coverage** $1-f = 1/(\kappa+1)$-complement of §M.21.10, i.e. the share of *abstentions* the answered-zero
channel captures. Every occurrence in this appendix and in §3.8 now carries its own symbol — $q_C$ for (a),
$w$ for (b), $1-f$ for (c) — and a rate quoted without its conditioning event and denominator should be
read as (a) only.

**Coverage is not precision, and $\kappa$ bounds only the former.** $1-f$ is
$P(\text{answered zero}\mid\text{abstention})$ — how much of the abstention the channel *catches*.
The **precision** of the channel, $P(\text{genuine zero}\mid\text{answered zero})$, is a different
quantity: it is $Z/\bigl(Z+(1-f)A\bigr)$ with $Z$ the number of genuine-zero items in the pool, so it
depends on the pool composition and **is not a function of $\kappa$**. A lineage with $\kappa\to\infty$
has a channel that misses no abstention, which says nothing about how many of its answered zeros are
genuine. Precision is therefore **measured, never derived** — and the two measurements in §M.38/§M.40
must **not** be read as *being* that precision, because they are taken on **different pools and under a
different arm**. What they measure is the behaviour of the two outlets on two **stated pools under the
three-option `channel` contract**: on $306$ independently verified empty crops that contract returns
`no_people` on **47.9–86.9%** — the emptiness outlet's **sensitivity** to emptiness — and on non-empty
items the census had answered zero it returns `no_people` on **0.0–1.7%** and `cannot_judge` on
**92.1–100%**, i.e. near-perfect **specificity**, since the opposite outlet is chosen instead. The quantity
this section defines, $P(\text{genuine zero}\mid\text{answered zero})$ for the **`base`** contract, is a
third thing again: it additionally requires the **base rate of genuinely empty items in the mixed corpus**,
which we do not have. That is why those two conditional rates are quoted as a **bounded, pool-stated
substitute** and never as the precision itself, and why neither of them is recoverable from $\kappa$ (Appendix Z). The bound is one-sided, and it is worth stating positively: because this precision **rises** with the base rate of genuinely empty items in the pool — writing it as $p\,\pi/q$ with $p$ the answered-zero rate on truly empty items and $q$ the corpus answered-zero rate, both measured, the right-hand side increases in $\pi$ — and our pools bound that rate only from **below**, **the measurements here give the answered-zero channel's precision a lower bound on a mixed corpus, not an upper one**; the trivial upper bound is 1, and nothing informative is available above it.

**Every rate in this appendix, with its contract, conditioning event, pool and denominator.** The four
quantities above are easy to conflate in prose, so they are written out once:

| quantity | contract | conditioning event | pool, and denominator | status |
|---|---|---|---|---|
| observed channel fraction $G_N/G$ | any | — | every item the configuration ran on ($G$) | measured |
| latent abstention rate (share of **items**, not of abstentions) | any | not a true zero | every item run on | **not observable from outputs alone** |
| answered-zero **coverage** $1-f$ | any | answered zero $\mid$ abstention | the abstentions $A$ (not the pool) | identified under the two-channel assumption |
| emptiness outlet's **sensitivity** (**47.9–86.9%**) | **`channel`** | `no_people` $\mid$ item truly empty | the **306** verified-empty crops $\times$ 3 starts | measured (M.38/M.40) |
| emptiness outlet's **specificity** (**0.0–1.7%** false `no_people`) | **`channel`** | ¬`no_people` $\mid$ item non-empty | the census-answered-zero dense items | measured (M.38/M.40) |
| answered zero's **sensitivity on genuine zeros** (**98–100%** on pool S-1, three of four builds) | **`base`** | answered zero $\mid$ item truly empty | **two external** true-zero pools, 300 items $\times$ 4 builds | measured (§M.21.9) |
| zero-channel **precision** $P(\text{genuine zero}\mid\text{answered zero})$ | **`base`** | genuine zero $\mid$ answered zero | the **mixed** corpus | **still not identified, but its conditioning numerator is now measured** (§M.21.9): precision $=p\,\pi/q$, where $p=P(\text{answered zero}\mid\text{truly empty})$ is measured on those pools but **assumed, and re-measured on a constructed mix** (M.21.10), domain-invariant, $q$ the corpus's answered-zero rate is measured, and $\pi$ — the corpus's base rate of truly empty items — remains the **only** unmeasured factor **on the mixed corpus**; on the census corpora it is **zero by annotation** (§M.21.9) |

The last row is the quantity the section is *about*, and the table is the reason we do not quote a number for
it: every pool we have is single-sided, so what can be measured is the **pair** of conditional rates above,
under a *different* contract from the one the corpus rate is defined on. Reading either of those two as "the
zero-channel precision" would repeat the error this appendix corrects (below).

#### M.21.9 Two **external** true-zero pools, and what they do and do not identify

The pools above are all ours: the corpus has no true zeros, and the verified pool was cut from a single
source. **That first clause is a count, not an impression**: over the corpus's own pools — **182**
(ShanghaiTech-A), **316** (ShanghaiTech-B), **334** (UCF-QNRF), **273** (VisDrone) and **154** (AI-TOD) —
**1,259** items in all, and the count of items with a ground-truth count of zero is **0**
(`corpus_pi_zero.py`). So on this corpus the base rate $\pi$ that the precision would need is **zero by
annotation**, and the precision $p\,\pi/q$ is zero with it: every answered zero the corpus contains is a
zero the annotation says is wrong. That is why the identification argument does not rest on an unmeasured
$\pi$ here, and why we still report **coverage rather than precision** as the general statement — the
residual assumption is that the source annotations are complete, which we name rather than measure.
To widen the conditioning event, we built **two external true-zero pools** under three gates —
(i) the dataset annotation contains no person box; (ii) **two independent detectors** (YOLO11n and RT-DETR,
at `conf ≥ 0.05`, IoU 0.5/0.7) also report no person; (iii) a deterministic 30-image sample per pool was
inspected by eye, with the images archived. **S-1** = VisDrone-DET val + test-dev ∪ AI-TOD val (3091
candidates); **S-2** = COCO val2017 images with other-class objects and no person box (2259 candidates);
150 images were frozen per pool (S-1 = AI-TOD 149 + VisDrone 1; S-2 = COCO 150, manifest md5
`432212b6a3fb16646e4b3a5c00816161`). Four builds ran three contracts over all 300 items (3,600 calls).

| build | `base` zero rate S-1 | `base` zero rate S-2 | `permit` zero rate S-1 / S-2 | `channel` outlet S-1 / S-2 |
|---|---|---|---|---|
| Qwen3-VL-32B-Instruct | 100.0% [97.50, 100.00] | 99.3% [96.32, 99.88] | 1.3% [0.37, 4.73] / **97.3%** [93.34, 98.96] | 100% [97.50, 100.00] / 100% [97.50, 100.00] |
| InternVL3.5-8B | 98.0% [94.29, 99.32] | 100.0% [97.50, 100.00] | 0% [0.00, 2.50] / 0% [0.00, 2.50] | 100% [97.50, 100.00] / 100% [97.50, 100.00] |
| Phi-3.5-Vision | 99.3% [96.32, 99.88] | 65.3% [57.42, 72.48] | 0% [0.00, 2.50] / 0% [0.00, 2.50] | 100% [97.50, 100.00] / 100% [97.50, 100.00] |
| gemma-3-12b | 34.0% [26.90, 41.90] | 88.7% [82.60, 92.80] | 0% [0.00, 2.50] / 0% [0.00, 2.50] | 100% [97.50, 100.00] / 99.3% [96.32, 99.88] |

**Each cell carries a Wilson 95% interval on its own $n$ (150 per pool), the same convention as §M.40** — the intervals are quoted on the saturated cells as well as on the zero cells, so that a cell reading `0%` is not held to a stricter standard than one reading `100%`, and each is computed from the integer count behind the printed rate. Reproduction: `m219_wilson_bounds.py`.

**What this establishes.** On pool S-1 the `base` contract answers zero on **98–100%** of genuinely empty
items for three of the four builds — i.e. the conditional $p=P(\text{answered zero}\mid\text{truly empty})$ is close
to one. This is the numerator the precision lacked, and it reduces the precision's unknowns from two to
one (table above). **It does not identify the precision**: on a pool that is *entirely* true zeros the
precision is $1$ by construction, so these pools cannot stand in for the mixed corpus. **Using $p$ for the corpus is an assumption we state rather than test:** the precision of
the mixed corpus is $p\,\pi/q$ only if $p$ is **domain-invariant**, and nothing here measures
that. Our own table is the counterexample — gemma-3-12b sits at 34.0% on S-1 and 88.7% on S-2 and
Phi-3.5-Vision at 99.3% and 65.3%, so the same channel moves by **54.7 pp** (and 34.0 pp) between
the two pools. We therefore report **54.7 pp as the violation of the invariance assumption** and
treat $p\approx1$ as scoped to the pools on which it was measured, not as a transferable constant.

**What it also shows, and we state rather than average away.** (a) **These zeros are correct**, not
spurious: the items genuinely contain no person, so a high `base` zero rate here is *accurate behaviour*,
not the failure mode the corpus exhibits. (b) The `permit` contract does **not** generalise uniformly:
it removes the zeros on both pools for three builds, but on Qwen3-VL-32B it abstains on 148 of 150 S-1
items while **still answering zero on 146 of 150 S-2 items** — a family × domain interaction, reported as
one. (c) Under the three-outcome `channel` contract the models take an explicit outlet on **99.3–100%** of
these items, which is why the pool's original eligibility window (which additionally required outlet use
$\le 95\%$) proved **unsatisfiable by construction** on a true-zero pool; we therefore report the window
both **as originally written** and as revised to require headroom only in the compared quantity (`base` zero rate
$\in[10\%,90\%]$). The eight `base` cells, cell by cell, with the two windows applied:

| build | pool | `base` zero rate | headroom in the compared quantity | `channel` outlet use | headroom under the **original** window |
|---|---|---|---|---|---|
| Qwen3-VL-32B-Instruct | S-1 | **100.0%** (150/150) | no | **100.0%** | no |
| Qwen3-VL-32B-Instruct | S-2 | **99.3%** (149/150) | no | **100.0%** | no |
| InternVL3.5-8B | S-1 | **98.0%** (147/150) | no | **100.0%** | no |
| InternVL3.5-8B | S-2 | **100.0%** (150/150) | no | **100.0%** | no |
| Phi-3.5-Vision | S-1 | **99.3%** (149/150) | no | **100.0%** | no |
| Phi-3.5-Vision | S-2 | **65.3%** (98/150) | yes | **100.0%** | no |
| gemma-3-12b | S-1 | **34.0%** (51/150) | yes | **100.0%** | no |
| gemma-3-12b | S-2 | **88.7%** (133/150) | yes | **99.3%** | no |

The labelling changes which cells are admissible and we give both counts: **3 of 8** cells have headroom in the compared quantity under the revised window and **0 of 8** pass the original one. The 5 that fail the revised window are the saturated cells of Qwen3-VL-32B (both pools), InternVL3.5-8B (both pools) and Phi-3.5-Vision (S-1); and no cell at all is admissible under the original window, since the least saturated cell still takes the explicit outlet on **100.0%** of its items, above the 95% the original window allowed. Under the revised window **only gemma-3-12b has headroom in both pools** (34.0% vs
88.7%, a 54.7 pp source gap), so only that build licenses a cross-source comparison, and the “both sources
agree in direction” reading of the other three is largely a consequence of saturation. **The licensing is a property of the window, and we report the whole
family rather than the one window we adopted:** recomputing the licence over a family of windows
gives gemma-3-12b under `base` zero rate $\in[10,90]$ and $\in[5,95]$ — i.e. under the natural
$\pm$5 pp choice as well as ours — but **no build** under $[20,80]$, $[15,85]$ or $[25,75]$;
the other three builds are licensed only under the degenerate full range $[0,100]$, exactly as the
saturation argument predicts. The conclusion is therefore **insensitive to the lower bound** (it
does not depend on our having picked 10%) but **sensitive to the window width**, and it must be
read that way rather than as a robust partition. (d) A repeat test on the anchor build, run at the **same four-worker concurrency as the table** over the
**full 300-item pool** and **three** independent passes, gave **900/900 pairwise itemwise agreement** in
both the parsed value and the raw string (150/150 in each pool). Because a zero count cannot bound its own
error, we report one-sided Clopper–Pearson bounds rather than the point estimate: **3.92 pp** treating each
**batch of four** as one independent unit (**n = 75**, the batches of a single pass), **0.99 pp** treating
items as independent (**n = 300**), and **77.6 pp** treating the two pools as the only independent units
(**n = 2**, the widest of the three). **All three passes sit in one session**, so none of the three carries
an across-session term: the cross-session spread is bounded separately by the three fresh service starts of
§M.40, whose largest value over every build, language and pool is **2.6 pp**. **The denominator, not just the bound, is the report:** pooling the
batches of all three passes (**n = 225**) gives **1.32 pp**, so we quote the *most conservative batch-level*
reading and do **not** quote the point estimate; **the pass/fail reading of this section is taken on that
batch level bound (3.92 pp)**, not on either of the other two. **These bounds are not the noise floor of §8.1** and the
two are not comparable: the **2.15–6.46 pp** figure there is the across-repeat term of the corpus runs,
whereas these are one-sided bounds on a **zero** count under three different independence assumptions; the
most conservative of them (**77.6 pp**) is a statement about clustering, not about instrument noise.

(e) **The parse rule is not load-bearing, and we report the quantity that bears on it.** The `pred`
values of this section come from an **offline re-parse of the stored raw replies** (rules in priority
order: fenced+quoted, the frozen pattern, first integer), because the frozen probe's pattern requires the
key to follow the brace while this batch emits quoted keys. Re-classifying all **3,600** items under
**seven** conventions — the frozen regular expression, strict `json.loads`, raw-keyword matching,
first-integer, the quoted-key rule alone, the full priority pipeline, and the classification as published — leaves the **zero / non-zero
boundary row-identical**: **0 disagreements**. The same holds over all **95,160** rows of the three tables
this bears on: the seven-family table of §M.19.2 (the largest spread in a family-level rate is
**0.0000 pp**; the §P1 verdict is 7 of 7 under every convention), the **52** (configuration × domain) cells
of §M.18.3 (**permit 46 of 52**, **channel 52 of 52** under all seven; per-cell spread **0.0000 pp**, no
verdict flips), and the ten zero rates of §M.18.8. Across **20** headline quantities the spread over the
seven re-parse rules enumerated above is
**0.0000 pp**, so **nothing reaches the 7 pp bar** at which a rate would have to be reported as an interval.
The only quantity that moves is the label **refusal versus unparsed** (**0** versus **4,266** in one arm) —
which is exactly what the re-parse was introduced to fix, and which changes no decision. The invariance is
an **empirical property of this corpus, not a theorem**: the 0.0000 pp follows from the rules agreeing item by item, not from differences that happen to cancel. The rule that could disagree is the
first-integer fallback, `re.compile(r'-?\d+')` applied to the stored reply with commas removed, and it can
only misread a cell if a reply carries **both** a refusal word and a digit. We counted that class rather than
assuming it away (`n2_adversarial_probe.py`): over the **95,160** stored rows of **654** files, **35,716**
contain one of the three refusal words (`abstain`, `cannot_judge`, `no_people`, matched as lower-case
substrings) and **0** contain a refusal word **and** a digit — so **the class is empty at the audited scope of this probe** (654 files, 95,160 rows — **the counts are the audit's own file list and are a snapshot of that date, not a fixed size**: the released corpus has grown since, and the same probe re-run on the current tree would report a larger scope without changing the empty class at the audited scope: 35,716 carry a refusal word, **0** carry a refusal word and a digit; **0** of those place the digit first, which is the only ordering the fallback can misread). We record the breakdown in full rather than the bare zero, because the scope of the count is itself a finding: whether a wider sample contains such a row is **not** decided here, and that is what makes
the invariance an empirical property of this corpus rather than a theorem. Extending the same criterion to the whole released set settles the question the paragraph above leaves open: over the **2,338** CSV files under `data/derived/` — **2,304** of them evaluable (the 34 that carry no `raw` column are not), **791,139** rows — **three** rows do contain a refusal word and a digit with the digit first, all of them LLaVA-OneVision-7B replies that state an incidental number in prose or in a multi-object JSON before reaching `{"count": "abstain"}`. All three are stored exactly as the frozen rule reads them (`parse_ok = 1`), so they are the rule's documented weakness rather than a defect in the records; each moves at most one item of its table. A separate convention difference is worth recording: 2,242 rows across eight files of `data/derived/p2_noise4/p2_probe_results_reparsed/` carry the refusal token in the `pred` column, where every other released file leaves `pred` empty and the token in `raw`. (*Reproduction: a released re-parse script.*) A constructed reply such as
`{"response": "no_people", "confidence": 0.85}` lies in exactly that class: keyword matching reads
`no_people` while the first-integer rule reads the `0` of `0.85`, so the two would disagree. The frozen
artefact is left byte-unchanged, so both readings remain available.

**Audited rows, in one place.** The four audits this appendix and its neighbours rest on, so that the
denominators can be read off without reassembling them from four sections:

| Audit | Rows | Where |
|---|---|---|
| Priority-pipeline agreement, **seven** conventions | **3,600** items | §M.21.9(e), above |
| Zero / non-zero boundary identity, **seven** conventions | **95,160** rows | §M.21.9(e), above |
| Prompt-experiment triple reading | **2,496** rows (832 items × 3 arms) | §M.6 (ledger §M.32) |
| Refusal token versus `pred` | **55,351** stored rows | §M.31.6 |
| **Total audited rows** | **156,607** | |

*Reproduction: `analysis/work/n2_rule_spread.py` and `n2_adversarial_probe.py`; 224 input files with md5s in
`n2_rule_spread_inventory.json`. An earlier form of this paragraph quoted a "**3,598 / 3,600 = 99.944%**"
agreement figure. That number compares two **classifiers** — one reading only the stored `pred` column, one
reading the `raw` substring first — and not two parse rules; with the classifier held fixed and only the
rule varied, the agreement is **3,600 of 3,600**. The corrected statement is the one above.*

The **denominator is every item the configuration was run on**, not the answered subset: the pooled
convention divides by $G$, the answered-only convention by $G_N$, and the gap between the two conventions
is Proposition 8. Exhaustiveness and channel purity are **assumptions, not measurements**, and nothing
above tests them: what §M.38/§M.40 measure is how the outlets are *used* on a verified-empty pool versus
a non-empty one, which is a necessary condition for the two-channel reading rather than a proof of it.
Neither assumption is relied on in §5.12, which compares configurations only within a fixed contract and
a fixed denominator.

Two consequences. **(i)** The error is a *known
function of a measured quantity* — it needs no assumption about which images are abstained on, only that
the two channels are exhaustive. **(ii)** It makes the cross-lineage comparison quantitative rather than
qualitative: the abstention rate of a lineage with $\kappa$ is identified to within $1/(\kappa+1)$, so the
paper's headline rate is identified to **0.18%** for Qwen3-VL-32B ($\kappa = 550.6$) and to **30.31%** for
InternVL2.5-8B ($\kappa = 2.3$) — which is precisely why §3.6 reports the two lineages separately instead of
pooling them, and why the scope note of §8.2 is a consequence of the arithmetic rather than a hedge.
**Scope:** the proposition is conditional on the two-channel exhaustiveness; a third channel (e.g. a
non-numeric answer counted as a refusal) would change $f$, which is why Appendix B.3 states the unified
criterion explicitly.

**Proposition 8 (the dual-convention gap is an identity, not a bound).** From Proposition 4,
$\rho_{\text{total}} - \rho_{\text{answered}} = -(1-w)(1+\rho_{\text{answered}})$, hence
$$\lvert \rho_{\text{total}} - \rho_{\text{answered}}\rvert \;\le\; (1-w)\,(1 + \lvert\rho_{\text{answered}}\rvert),$$
where the inequality is the exact identity restated with $\lvert\rho_{\text{answered}}\rvert$: it holds with
**equality if and only if** $\rho_{\text{answered}} \ge 0$, so for every cell measured here (all of which
have $\rho_{\text{answered}} < 0$) the identity $\lvert\rho_{\text{total}} - \rho_{\text{answered}}\rvert =
(1-w)\,(1+\rho_{\text{answered}})$ applies exactly while the $\lvert\rho_{\text{answered}}\rvert$ form is strict. The gap therefore **vanishes if and only if** either there is no abstention ($w = 1$) or the answered
subset reports zero ($\rho_{\text{answered}} = -1$); note that an *unbiased* answered subset
($\rho_{\text{answered}} = 0$) does **not** remove it — the gap is then exactly $-(1-w)$ — so it cannot be
removed by any change to the answering behaviour alone. Verified over the four dense and aerial
domains under the base arm: the identity gives 40.6–61.3 pp, and the observed gaps
**61.3 / 57.5 / 40.6 / 40.6 pp** reproduce it to rounding, the $|\rho_{\text{answered}}|$ form being
strict in all four cells because $\rho_{\text{answered}} < 0$ (Appendix J.5). This is the
quantitative reason a single-convention report is not merely incomplete but *uninterpretable*: the size of
the convention effect is a function of the abstention mass, which the report is trying to measure.

---

#### M.21.10 A constructed mix with a known true-zero base rate: what the identity does and does not show

We built three mixtures of the AI-TOD test census (226 items, all with ground-truth count > 0) with the
frozen S-1 true-zero pool (150 items, disjoint from the census) at realized $\pi$ = **5.04% / 19.86% /
39.89%**, and measured the answered-zero precision of four builds (3 fresh service starts each, 14,200
calls: 896 items × 4 builds × 3 starts = 10,752 in the `base` arm, plus 896 × 2 anchor exit-control arms
= 1,792, plus 138 × 4 × 3 transfer items = 1,656).

**(a) The identity is a gate, not a finding.** With $p$ measured on the mixture's own true-zero subset,
$|\text{precision}_{obs}-p\,\pi/q| \le$ **0.59 pp** in all 12 cells — as it must be: on a constructed mix
this equality is Bayes' rule, so it cannot fail and we do not report it as evidence.

**(b) The real test is transfer.** With $p$ measured instead on a **disjoint** true-zero subset, the
identity holds within 10 pp in **11 of 12** cells; the single miss is gemma-3-12b at the lowest $\pi$
(**+20.87 pp**), the least-powered cell ($N_2 = 12$; Wilson width **33.1 pp**, above the 20 pp at which
this appendix does not print a number). Its source is a within-S-1 fluctuation between two disjoint subsets
of the *same* pool (50.0% vs 32.6%), not the S-1/S-2 source gap of **54.7 pp** reported above; a
two-proportion exact test gives $p = 0.043$, **Holm-corrected $p = 0.52$**. We therefore report the transfer
test as **not uniformly met but not a refutation**.

**(c) The instrument reproduces the published column.** Re-measuring $p$ independently on 414 S-1 items
gives **100.0 / 97.8 / 99.3 / 32.6 %** for the four builds, against the **100.0 / 98.0 / 99.3 / 34.0 %**
printed above.

**(d) Scope, stated as a hard limit.** The construction could not exceed $\pi \approx 0.40$: the census
holds 226 items with ground truth > 0 and the frozen true-zero pool holds 150, giving a ceiling of
$150/376 = 0.399$. Nothing here speaks to $\pi = 0.5$, and nothing here measures the **corpus's** $\pi$ —
the experiment tests the identity's transferability, not the corpus base rate. **That ceiling is a property of that construction, not of the design**: (e) below rebuilds the mixture from the whole frozen true-zero pool and reaches **0.5703**.

*Reproduction: the analysis is `pi_analyze.py` over the per-item records of three fresh service starts per
build in `pi_res/`; the criteria were frozen before any rate was computed (`pi_criteria_frozen.json`, md5
`aca4444c7f681b0596db4e4a84578b62`). These artefacts are from the run reported here and are **not part of
the released reproduction package**.*

**(e) A higher base rate, and the reading rule it makes first-order.** We rebuilt the mixture from the whole **300**-item frozen true-zero pool rather than its S-1 half, lifting the construction's ceiling from $150/376 = 0.399$ to $300/526 = \mathbf{0.5703}$, and ran four builds × three fresh service starts in the `base` arm (**6,312** calls):

| build | parsed / 526 | true-zero parsed | $p$ | $q$ | $\text{precision}_{obs}$ | residual, nominal $\pi$ | residual, $\pi_{\rm eff}$ |
|---|---|---|---|---|---|---|---|
| Gemma-3-12B | 526 | 300 | 61.00–61.33% | 35.55–35.74% | 97.86–97.87% | +0.00 pp | +0.00 |
| Phi-3.5-Vision-4.2B | 523 | 300 | 82.00% | 69.79–69.98% | 67.21–67.40% | +0.38 pp | +0.00 |
| InternVL3.5-8B | 526 | 300 | 99.00% | 68.06% | 82.96% | +0.00 pp | +0.00 |
| LLaVA-OneVision-7B | 445–446 | 223–224 | 95.96–95.98% | 71.69–71.75% | 67.08–67.19% | −9.11 to −9.27 pp | ≤0.01 pp |

Read against the **parsed** subset the identity holds in every cell, as it must; read against the constructed $\pi$ it misses the 0.59 pp bound in three, all of them LLaVA-OneVision-7B, whose parse rate on this mixture is **84.6–84.8%** — on a build that leaves a seventh of the mixture unparsed we do not report the nominal-$\pi$ residual as a violation, and report those cells as **not evaluable** instead. The mechanism is not a property of $\pi$: that build leaves **81** items unparsed and **77** of them are true-zero against **4** census items, so the scored subset's true-zero share is $\pi_{\rm eff} = 0.501$, not 0.570, and the residual of the nominal form is exactly $p\,(\pi_{\rm eff}-\pi)/q$ — substituting that build's own $p$, $q$ and $\pi_{\rm eff}$ returns **−9.27 pp**. Against $\pi_{\rm eff}$ all twelve cells close to **≤0.01 pp**. The same parse asymmetry would displace the base rate by **6.5 pp** at $\pi = 0.399$ and **4.1 pp** at $\pi = 0.20$, so the construction should always be reported together with the base rate of the subset actually scored — a rule that only becomes visible when a build's non-response differs between the two halves of the mixture. The transfer test of (b) is not repeated here: all **300** true zeros entered the construction, so no disjoint subset is available.

**A transfer-refutation statistic that the protocol can compute about itself.** The identity above is a gate:
it holds by construction, so it cannot fail, and it therefore cannot tell a third party whether the
construction underlying it is admissible at all. One scalar can. Let $\alpha$ be the constructed pool's
measured true-zero content, $\theta$ the measured non-empty answered-zero rate, and $q_C$ the corpus's own
answered-zero rate. Any base rate $\pi_C$ that reconciles the two must satisfy
$q_C = \alpha\pi_C + (1-\pi_C)\theta$, so the construction requires $\theta \le q_C \le \alpha$ and

$$ \delta^\star := \frac{q_C^{\mathrm{meas}} - \theta^{\mathrm{meas}}}{\alpha^{\mathrm{meas}} - \theta^{\mathrm{meas}}}. $$

On the four builds, with $\alpha$ recomputed as the pooled rate over the **150**-item frozen true-zero pool
(three starts, $n = 2{,}653$–$2{,}688$) and $\theta$ the same pool's answered-zero rate on its non-empty
side, the protocol gives

| build | $\alpha$ (recomputed pool) | $\theta$ (recomputed pool) | $q_C$ (corpus, §M.19.16 cn-`base`) | $\delta^\star$ |
|---|---|---|---|---|
| Qwen3-VL-32B | 100.00% | 63.27% | 63.88% | **0.0165** |
| InternVL3.5-8B | 97.71% | 27.09% | 68.06% | **0.5802** |
| Phi-3.5-Vision-4.2B | 99.54% | 53.68% | 69.98% | **0.3555** |
| gemma-3-12b | 35.32% | 1.77% | 35.74% | **1.0125** |

A value below $1$ is a usable base rate; **a value above $1$ means the two are not jointly transferable on that build**: on gemma-3-12b no
$\pi_C \in [0,1]$ reconciles the corpus with the pool, because $\alpha = 35.32\% < q_C = 35.74\%$, so on that
build the two are not jointly transferable however well the identity holds within each. The quantity is exact
in $\alpha$ and must be reported **with $\alpha$'s caliber attached**: substituting the $p$ printed in
§M.21.10(e) for $\alpha$ on that construction's own 526-item mixture returns 0.5697 / 0.5756 / 0.5703 for
InternVL3.5-8B, Phi-3.5-Vision and gemma-3-12b — and the last is *exactly* that construction's nominal base
rate, which is the arithmetic reason the identity above can never fail there. The quantity this
sits beside is the abstention channel's coverage, which under the exhaustive two-channel assumption is the point $\kappa/(\kappa+1)$ (Proposition 7), not an identified set
(§M.21) — so the contract does not merely move a distribution: **it changes which quantities the report can bound.**

With `δ* = (q_C − θ)/(α − θ)`, **gemma-3-12b returns δ\* = 1.0125 > 1**, i.e. even at the largest α the construction permits, the corpus's own answered-zero rate cannot be produced — the joint transfer is **not reproducible** on that build — a **plug-in incompatibility on these pools, without a sampling-based transfer guarantee**. For reference, the frozen construction's own (designed, not measured) parameters return **δ\* = 0.5697 / 0.5756 / 0.5703**; the last of these **is** the construction's nominal base rate, which is the arithmetic reason the identity of §M.21.10(a) is a gate that cannot fail.

The reverse direction is equally tight: at the construction's π the pool surface reproduces the corpus rate to **∓0.10–0.16 pp**. **The coverage of the abstention channel is mis-stated if its lower endpoint is written as $1/(\kappa+1)$.** $\kappa$ is the ratio of answered zeros to textual refusals, so the missed-refusal share is $f=1/(\kappa+1)$ and the answered-zero channel therefore captures **at least** $\kappa/(\kappa+1)$ of the abstentions; $1/(\kappa+1)$ bounds $f$, not the coverage, and differs from the correct floor by a factor of $\kappa$ — on a corpus with **200 items, 100 answered zeros, 1 textual refusal and 99 ordinary answers** ($\kappa=100$) the true coverage is $100/101=\mathbf{99.01\%}$, and the printed "interval" $[1/101,0.5]=[0.99\%,50\%]$ **does not contain the truth**. Under the exhaustive two-channel assumption that coverage is exactly $\kappa/(\kappa+1)$ (Proposition 7); the item-denominated answered-zero rate $q_C$ has a different denominator — all items, not abstentions — and does not bound that conditional coverage without additional prevalence information, so no interval is claimed for it here. What does follow is that this quantity bounds the abstention channel's **coverage**, not its **precision**: $\kappa$ gives the precision **no lower bound at all** (§M.21), and the abstention-only arm (`â = b̂ = 0`) leaves the precision at the trivial $[0,1]$. The identification argument itself is not new as a **method**: Manski, C. F. (2021), *Epidemiology* 32(2), DOI `10.1097/EDE.0000000000001309`, already shows that a positive or negative predictive value is bounded only under a bound on prevalence, so what is added here is the **application** to this construction — the coverage identification just given, and the trivialisation of the precision to $[0,1]$ by the abstention-only arm — and not the identifiability result, which we cite rather than claim.

*Reproduction: the four builds × three starts are per-item records in the released package (the released per-build per-item records `E3_<build>_start{1,2,3}.csv`, twelve files); the mixture manifest (`pf_items_pi0570.json`, md5 `c43d7f94bc192ac0a2d9b697561d90ef`) and the frozen true-zero pool are those of §M.21.10.*

**(f) What a plugged-in $\hat\pi$ costs the headline.** Write the identity logarithmically, $\log\text{precision}=\log p+\log\pi-\log q$, and two regimes follow — and this appendix's sentences sit in different ones. Where $\pi$ and $q$ are measured **independently**, the corpus case, the relative errors add in quadrature, $(\delta P/P)^2=(\delta p/p)^2+(\delta\pi/\pi)^2+(\delta q/q)^2$, so the term §M.44 leaves open is a first-class part of the budget rather than a remainder: feeding §M.44's own numbers into it (a transfer error of 10.80 pp on the recovered proportion, a 95% half-width of 10.2–16.4 pp, and a binomial $q$ at $n=526$) puts **65% of the variance on $\pi$**, 25% on the transfer of $p$ and 10% on $q$. Where the mixture is **constructed**, $q=\pi p+(1-\pi)r$ is a function of $\pi$ and the same perturbation is damped by $\eta\equiv\partial\log\text{precision}/\partial\log\pi=1-(p-r)\pi/q$, computed from the same per-item records as (e): over the four builds $\eta$ runs from **0.050** to **0.770** — a **16-fold** spread — because it is governed by how often a build answers zero on the *non-empty* side, $r$ ranging from **1.8%** (Gemma-3-12B) to **53.4%** (Phi-3.5-Vision). Passing §M.44's resolution (17.8–28.7% relative on a proportion of 0.572) through $\eta$ moves the headline by **0.9% to 22.1%** depending on the build. **A single tolerance quoted for every build would therefore be wrong by more than an order of magnitude**, and any future attempt to close $\pi$ has to carry a build-dependent one.

### M.22 The adoption recipe: what a third party has to run, and what it then knows

The paper's two transferable outputs are a **contract diagnosis** and a **reporting convention**. Both are
cheap to apply to a model or benchmark this paper never touched, and neither needs the corpus, the
annotation boxes, or any retraining. The recipe is five steps.

1. **Fix the serving stack and record it** (engine, weight build, prompts, parser, temperature) — the control
   the earlier hosted re-query lacked (§M.1).
2. **Build two pools from a reference run** — items it answered exactly `0` and items it answered with a
   number — and run **three arms** on both: `base`, `permit` (allows an explicit `abstain`) and `channel`
   (three-way: a number, `cannot_judge`, `no_people`).
3. **Measure the channel, not only the rate.** Count answered zeros and textual refusals separately: if a
   family abstains mostly in prose, its answered-zero count *estimates* the abstention rate with relative
   error $1/(\kappa+1)$ (Proposition 7) — **30.31%** for InternVL2.5-8B, which is why the two lineages are
   never pooled.
4. **Report both conventions and the abstention mass**: pooled (zeros counted) *and* answered-only, with
   $w$ = answered share. Proposition 8 gives the gap; §5.12 measures its consequence — the same configurations
   reorder (Spearman **0.476–1.000**) and one configuration's bias moves by up to **48.2 pp**.
**When one convention can be reported instead of two, and when it cannot.** Step 4 says to report both
conventions. It does not say when one of them is redundant, and the test is arithmetic. Write
$a_u = P_u/G_u$ for a unit's pooled relative deviation (abstentions counted as zero), $w_u = G_{N,u}/G_u$
for its answered share, and $b_u = P_u/G_{N,u}$ for its answered-only deviation. Then $b_u = a_u/w_u$
identically, and for two units $u,v$ labelled so that $a_u > a_v$,

`gap(c) = (1 − w)(c − 1 − ρ_a)`, where `w = G_N/G` and `ρ_a = (P − G_N)/G_N` is the relative deviation on the answered subset.

$$ \text{the two conventions order } (u,v) \text{ oppositely} \iff 1 < \frac{a_u}{a_v} < \frac{w_u}{w_v}. $$

The proof is two lines: $b_u/b_v = (a_u/a_v)(w_v/w_u)$, and the two orders differ exactly when both factors
lie on opposite sides of $1$. Two consequences a third party can apply directly. **A certificate:** when
$|\Delta \log a| \ge |\Delta \log w|$ the pair is ordered the same way under both conventions and **one
convention suffices for that pair**; when $|\Delta \log a| < |\Delta \log w|$ the pair **must** be reported
twice. **A closed form for the damage:** the number of pairs whose order the convention flips is
$N_{\mathrm{inv}} = \#\{(u,v) : 1 < a_u/a_v < w_u/w_v\}$, so the two conventions cannot disagree at all
whenever $w$ is constant across the units being compared — the **answered share**, not the accuracy, is the
only channel through which a change of convention can reorder anything. On the nine FSC-147 configurations
the two orderings separate exactly this way: under the relative deviation $\rho$ **1 of 36** pairs invert and
under the mean absolute error **7 of 36**, a factor of seven that is structural rather than incidental — the
convention acts on a ratio family as a **multiplicative rescaling** (only pairs inside the window
$1 < a_u/a_v < w_u/w_v$ can move) and on a weighted-mean family as an **affine mixture**, which does not
factorise and therefore moves pairs outside that window.

5. **Decide.** If `permit` leaves **≤5%** of the base zeros still answered as 0, the zero is contract-set and
   a single-convention report is not comparable with one using the other convention; if the answered-only
   bias sits inside your own noise floor, that is **not** enough to make the convention immaterial *for
   those cells*: by **Proposition 8** the gap is exactly $-(1-w)(1+\rho_{\text{answered}})$, so it survives
   an unbiased answered subset and must be reported as a measured gap rather than inferred from the bias —
   say which, and report the number.

**The recipe is packaged as running code.** `adopt_contract_probe.py` sends the three arms to any
OpenAI-compatible endpoint given only an image directory (no dependency on this paper's corpora, annotations
or detectors; the prompt texts are byte-identical to the census probe), and `adopt_report.py` with the
frozen `adopt_criteria.json` prints the channel diagnosis, the **item-answered fraction** $w$ (a different quantity from the ground-truth-weighted $w$ of Proposition 4) and the two-convention
numbers with their verdicts. Both are in the reproduction package, and both were exercised end to end on a
held-out configuration before release.

**A failed call is not a removed zero.** The three kinds of non-numeric record are kept apart: an explicit
abstention (`abstain` / `cannot_judge` / `no_people`) is the contract working as designed, while a
**failure** — a timeout, an empty response or an output the frozen parser cannot read — is **not**. Failures
are listed separately, they stay in the denominator, and they make the residual a **lower bound** whose
conservative upper bound is printed beside it; with no decidable record at all the report prints
*undecidable* rather than an interval of zero width, and a missing arm record is listed rather than silently
dropped. `adopt_report.py --selftest` is the standing negative control: it injects a timeout and requires
the report to say *undecidable*.

**Worked example, one of the seven families end to end.** LLaVA-OneVision-7B, four domains, both pools,
$n = 150$ per domain, one serving session on the stack of §M.19.1: **235** base zeros, of which `permit`
leaves **5** (**2.1%**, Wilson [0.9%, 4.9%]) and `channel` fewer. **The failure count is zero here and is
still reported:** of the 235 `permit` records **226** are explicit abstentions and **4** are numeric
non-zero answers, so no record is undecidable and the residual's conservative upper bound equals its point
estimate. The same grid also exposes the family's own caveats — in the dense domains its `raw` output is prose in the prompt's language with no parseable
number (**38.8%** parsed on st_a), while in the aerial domains it answers `0` on **78.3%** of the items the
corpus answered 0. The third party therefore learns three things in one session: the contract removes its
zeros, its dense-domain numbers are not always parseable, and its aerial zeros are as frequent as the
corpus's. **Cost: one serving session — 3 arms × 2 pools × 4 domains × $n$, about 3,600 calls, tens of
minutes, no annotation, no training.**

**What the recipe does not give.** It does not predict *how large* a bias to expect (no magnitude law —
Proposition 3), it does not repair direction, and on a family whose dense-domain channel saturates (§M.19.4)
the outlet carries no selectivity there. Those three limits are stated rather than hidden: a recipe that
promised them would be promising what the measurements do not support.

---

### M.23 An annotation-free rule was looked for and not found — with the mechanism

The deployment gap left by §3.3 is a rule that decides *whether to trust a count* **without annotation
boxes**. Three natural signals were tested against a bar fixed before the runs (usable if, on a unit,
**AUC ≥ 0.65** for the event "relative error > 50%" **and** the mean bounded error on the most-agreeing 20%
is **≤ 0.6×** the mean over all items). All three are computable from a model's own behaviour, so a working
one would be deployable with no annotation, no detector and no training:

**A bar is not a criterion unless it is decidable at the sample size tested.** The AUC leg above is read
against a pre-registered threshold $\theta$; whether that reading can pass at all is a power question with a
one-line answer. With $n^-$ negative units and the Hanley–McNeil equal-variance form
$\mathrm{SE}(\mathrm{AUC}) \approx 1/(2\sqrt{n^-})$, the condition $\theta - \tfrac12 \ge z_{1-\alpha}\,
\mathrm{SE}$ inverts to

$$ n^- \;\ge\; \left\lceil \left(\frac{z_{1-\alpha}}{2(\theta - \tfrac12)}\right)^{2} \right\rceil , $$

which at $\theta = 0.65$ and $\alpha = 0.05$ requires $n^- \ge 31$. Our cross-wording units carry a median of
**17** negatives, **15 of 20** are below the bar, and one has $n^- = 0$, where the AUC is not defined at all.
Screening to the units that can be tested leaves **five**, of which **one** passes; under a true pass rate as
high as **0.52** the probability of seeing at most one is **0.1635**. The count of passing cells is therefore
not evidence about the signal — it is a statement about the sample sizes, and we report it as such.

| signal | how it is computed | units tested | units passing |
|---|---|---|---|
| **cross-scale agreement** | \|pred$_{640}$ − pred$_{1536}$\| / max(pred$_{1536}$,1), same prompt | 4 (3 families × dense/aerial) | **0** |
| **cross-phrasing agreement** | dispersion of the numeric answers across `base`/`bestA`/`bestB`/`bestC` | 20 (5 families × 4 domains) | **1** |
| **cross-family consensus** | \|pred$_F$ − median$_{G\neq F}$(pred$_G$)\| / max(\|median\|,1) | 21 (7 families × 3 domains) | **0** |
| **totals** | | **45** | **1** |

Three readings, and the third is the mechanism.

1. **The bar is not the obstacle**: on cross-phrasing the AUC leg alone reaches 0.79–0.94 on the 32B anchor in
   three domains, so the signals do carry *some* error information. What never holds is the deployment leg —
   keeping the most-agreeing 20% does not cut the error enough (median 20%/100% ratio **1.03** for consensus,
   0.04–2.00 for phrasing: as often worse as better).
2. **In the aerial domains consensus is anti-correlated** (AUC **0.16–0.44**): a family that deviates from its
   peers is *more* likely to be right, because the peers share the same domain-specific bias. Disagreement
   tracks shared bias, not truth.
3. **Why.** §M.19.8 shows the answer barely moves with scale (Δ ≤ 0.7 pp) and §M.19.7 that it moves with the
   *contract*, not the demand; so the difference between two encodings of one model — or between two models
   sharing a bias — is mostly noise plus shared bias. This is Proposition 1 one level up: not only
   **abstention** but **answer quality** is **not identified by these three signals**, so a quality signal must come
   from outside the answers (annotation geometry, §3.3/§M.20, or another modality).

**What this buys the paper.** The honest answer to "an annotation-free rule that works" is that the three
signals measured here do not form the deployment rule defined above: this closes the answer-level route **as specified here**, not every output-derived signal. Two outputs do transfer — the contract
diagnosis and the dual-convention reporting step of §M.22, whose consequence §5.12 measures.

*Reproduction: `code/analysis/b2_pilot{,_phrasing,_consensus}.py` and their frozen `b2_pilot*_result.json`;
inputs are the E2/E3 per-item CSVs under `data/derived/e3/` — no new inference.*

---

### M.24 The public-benchmark check: FSC-147, nine configurations, and one counterexample

§5.13 states the result; this appendix carries the full panel, the mechanism arms, and the diagnosis of the
counterexample. Design: **FSC-147** [7] at the resolution of its published release — the short side is fixed
at 384 px for all 6,146 images, the long side varying with aspect ratio (384–1229 on this sample), and
Appendix M.41 varies that scale — a **fixed-seed, GT-stratified
sample of 300 test images** (step-sampled over the GT-sorted test split, so the sample spans 7–3 000
objects), the corpus contracts reused verbatim, one image per prompt, `temperature 0`, `max_tokens 128`, up
to 4 096 context. The probe **imports the census probe** and reuses its prompt dictionary, parser and
transport rather than re-implementing them, so the instrument is the same one used on the nine corpora.

**The image count, stated once and with both calibers.** The release as distributed links to, and mirrors
redistribute, the pre-processed package `images_384_VarV2`, which holds **6,146** files — that is the object we
sample from, and it is why §M.41 and this section state **6,146**. The total usually quoted for FSC-147 in the
literature is **6,135** images (3,659 / 1,286 / 1,190 train/val/test), i.e. a **de-duplicated** count; the
difference of **eleven** is what the revision **FSC-133** (Hobley & Prisacariu, arXiv5.10203) records, namely eleven training
images that also appear in the validation or test split. Both figures are therefore correct under their own
caliber; we sample the package as distributed and say so, rather than silently reconciling the two.

#### M.24.1 Contract gate across nine configurations (nine checkpoints; the `lineage` column below carries the vendor label, not the six-lineage count)

| configuration | lineage | base answers 0 | still 0 under `permit` | 95% CI | still 0 under `channel` |
|---|---|---|---|---|---|
| Gemma-3-12B | Google | 248 / 300 | **0** (0.0%) | [0.0%, 1.5%] | 0 |
| InternVL3.5-8B | OpenGVLab | 273 / 300 | **0** | [0.0%, 1.4%] | 0 |
| Phi-3.5-Vision-4.2B | Microsoft | 255 / 300 | **2** (0.8%) | [0.2%, 2.8%] | 0 |
| LLaVA-OneVision-7B | community | 187 / 300 | **0** | [0.0%, 2.0%] | 0 |
| Qwen3-VL-8B | Qwen | 283 / 300 | **0** | [0.0%, 1.3%] | — |
| Qwen2.5-VL-3B | Qwen | 277 / 300 | **0** | [0.0%, 1.4%] | — |
| Qwen3-VL-4B | Qwen | 276 / 300 | **9** (3.3%) | [1.7%, 6.1%] | — |
| Qwen3-VL-30B-A3B (MoE) | Qwen | 201 / 300 | **12** (6.0%) | [3.4%, 10.1%] | — |
| **Qwen3-VL-32B (BF16)** | Qwen | 277 / 300 | **251** (90.6%) | [86.6%, 93.5%] | **0** |

**Failures are reported, not folded in.** On the LLaVA-OneVision-7B row **6** of the 187 `permit` records
are unparsable prose, so that row's residual is a lower bound: the conservative upper bound is 6/187 =
**3.2%**, still inside the 5% bar, and the six items are listed in the released per-item records. **No other
row of the table has an undecidable `permit` record**, so the remaining residuals stand as printed. The
general rule — an explicit abstention is the contract working, a failed or unparsable call is not — is
stated in §M.22.

**Eight of nine configurations comply** (residual ≤ 6%; the frozen criterion of §7.9 is ≤ 5%, under which the 12 of 201 = 6.0% of Qwen3-VL-30B-A3B also fails — both thresholds are reported rather than one); the ninth is the counterexample §5.13 reports and
§M.24.3 diagnoses.

#### M.24.2 The two conventions on this benchmark

| configuration | answered share | ρ, zeros counted | ρ, answered only |
|---|---|---|---|
| Gemma-3-12B | 17.3% | −94.3% | −50.3% |
| Phi-3.5-Vision-4.2B | 15.0% | −98.2% | −72.3% |
| Qwen3-VL-30B-A3B | 10.3% | −98.2% | −70.4% |
| Qwen2.5-VL-3B | 7.7% | −98.8% | −76.7% |
| InternVL3.5-8B | 9.0% | −98.9% | −79.2% |
| Qwen3-VL-32B | 7.7% | −99.2% | −84.8% |
| Qwen3-VL-4B | 8.0% | −99.4% | −88.4% |
| LLaVA-OneVision-7B | 6.3% | −99.7% | −91.7% |
| Qwen3-VL-8B | 5.7% | −99.8% | −94.4% |

Ranking: **Spearman 0.983**, **1 of 36** pairs inverted, top-1 unchanged. The `answered only` column rests on **answered-image subsets of 17, 19, 23, 23, 24, 27, 31, 45 and 52 of the 300 sampled images (median 24), and a 1,000-draw item bootstrap on those subsets puts the answered-only MAE at [21.8, 55.2] to [14.2, 34.9] — half-widths of 9.0 to 18.1 counts, i.e. **wider than the spread between configurations**, so the answered-only column is a direction reading and the correction above is quoted from the pooled quantities, which rest on all 300** images per configuration, while a single configuration's
measured bias moves by up to **44.0 pp**. On this benchmark the convention changes *magnitudes* everywhere
but the *ordering* essentially not — the opposite of the dense domains of §5.12 (Spearman 0.604, 17 of 91
inverted). That contrast is the honest scope of the leaderboard claim.

#### M.24.3 The counterexample, diagnosed

Of the 277 items the base arm answered `0`, `permit` leaves **251** still answering `{"count": 0}` for this
build and switches only **26** to `{"count": "abstain"}` — it **literally keeps answering zero** when merely
*permitted* to abstain. Under the three-option **`channel`** contract the same build leaves **0** zeros:
asked to choose among *a number*, `cannot_judge` and `no_people`, it uses an outlet every time. The same
build on ShanghaiTech-A leaves **0 of 62** under `permit` (§M.19.8).

The same comparison, run systematically over **all 43 (family × domain) cells** for which both outlet arms
exist, finds exactly **two** cells where the three-option wording strictly rescues the gate — Qwen3-VL-2B on
AI-TOD (permit residual **41.6%** → `channel` **0.0%**) and on VisDrone (**55.7%** → **0.0%**) — and no cell
in which the permission wording is the better of the two. So the counterexample is **not** a parser artefact,
**not** context truncation, and not a general property of
the build: it is a **wording × domain** interaction — here the outlet has to be *enumerated as an option*
rather than *permitted* — and it only surfaces when the domain changes. It also gives the recipe a cheap
fix: **offer the three options, not a permission**, which is what §M.22 step 2 already prescribes.

*Reproduction: `code/analysis/b1_fsc_full.py` over `data/derived/fsc_res/frozen384/` (28 CSVs: 9 configurations ×
base/permit, plus four mechanism arms) and `code/analysis/permit_vs_channel.py` over the E2/E3 census
(43 cells); probe `code/experiments/19g_probe_fsc.py`, which imports the census probe so prompts and parser
are byte-identical; images, annotations and splits from the public `isentropic/FSC147` repository.*


---

### M.25 The response spectrum's statistical structure and its calibration check

§7.3 states this material in condensed form and **keeps its own statement of the numbers**; this
appendix gives the same material at greater length. It is a **rewrite, not a transfer** — the two
are not sentence-identical — so a reader of the main text alone loses no claim, and no number below
is offered as new. The frozen values are in Appendices F.3, F.8, F.10 and F.11. Per-level intervals here are **resampling lower bounds** and understate the dominant term for any
contrast across sides: only **ten units on four sides** exist.

#### M.25.1 Statistical structure

**Statistical structure.** For the ten (knob × domain) units we took the isotonic-calibrated span with its
random half-sample split interval (**200 seeds**, F.9) and enumerated **all** single split points (Appendix F.3). Exactly one split
separates, by **1.6 pp** at permutation $p \approx 0.008$ **before** correction for the nine enumerated
split points — and that gap is itself **below this paper's own noise floor (2.15–6.46 pp)**, with the
smallest attainable corrected value is 0.075. We therefore report that separation as a **candidate
structure rather than an established partition**: one low-response unit alongside an **internally
continuous high-response spectrum** (33.5–150.7 pp, from F.9's **transcribed** column), and explicitly **not**
two anchor zones or bimodality, since with four knob **sides** collapsed into ten units a bimodality
test has very low power. (The six knobs of Appendix F.2 map onto four sides; the split-point enumeration of Appendix F.3 runs over
the ten units, not over the six knobs — the two counts are different populations, and the word "class" is
not used for either.) (Appendix M.9)

#### M.25.2 A shared calibration cannot remove the achievable span

**A shared calibration cannot remove the achievable span.** By **Proposition 5** a shared affine calibration
scales a span by its slope, so compressing one requires $s\ll1$. A **per-unit** deployable calibrator does
reach such scales, but it is the very caliber under which the ordering is not preserved (**M.37**); the
quantile map, which also compresses, is fittable from a labelled calibration set and deployable as a map,
but it **destroys the ordering** (**0.410** over the 36 units, M.37). The answer to the objection that span
is a calibration artefact is therefore not that compression is impossible, but that **no calibrator that
compresses the span leaves the units mutually comparable** (M.37). Span is also not a single construct, and
the noise floor is **2.15–6.46 pp** (Appendix F.8).

---

### M.26 Three short §7 results

Their conclusions are in the main text; the bodies are reproduced so that no wording is lost.

#### 7.4 Saturation slope: a same-lineage scale difference, verified two ways

Across the four configurations of one lineage the slope of the density-saturation relation is
$-0.00511$ to $-0.00382$ (range 0.00129, 27.5% relative); the three configurations that agree at about −0.005 do so as a cluster, with the 8B point as the outlier. 

*(Full detail in Appendix F.)*

#### The quantitative structure of relative deviation (no main-text section)

Per-level means and medians disagree at the sparse end for every configuration, and the disagreement is a
**magnification** rather than a shift; only Qwen3-VL-8B assigns the correct direction to all three curves
at magnified scale, consistent with its computed statistics. 

*(Full detail in Appendix A.)*

#### 7.8 Enumeration versus regression: what this corpus measures

Our finding that enumeration-style counting is more directionally controllable than regression-style
counting is measured on this corpus; the regress-then-round pipelines we test lose the property being
measured. No external work is cited here as independent corroboration of it.

*(Full detail in Appendix F.)*

---

### M.27 Does the convention change a *decision*? Tested three ways, and the answer depends on the convention

§5.12 shows that a single-convention report moves a configuration's measured bias by up to 48.2 pp. The
practical question is whether it also changes what a user *does*, so we tested three decision forms on the
data already in hand (9 configurations on FSC-147; 16–18 configurations per dataset on four corpus domains),
with the thresholds fixed before the runs:

| decision form | definition | cells tested | verdicts that change with the convention |
|---|---|---|---|
| **deliverability** | deployable iff ≥ θ of images fall inside a ±tol relative-error band | 5 datasets × 16–18 configurations × θ ∈ {0.30, 0.50, 0.70} × tol ∈ {10%, 20%, 50%} | **78** under this section's convention (an answered `0` is also an abstention; FSC-147 2, AI-TOD 20, ShanghaiTech-A 14, UCF-QNRF 10, VisDrone 32); **3** if only textual refusals are excluded (ShanghaiTech-A at tol 20%/θ 0.50 and tol 50%/θ 0.30, UCF-QNRF at tol 50%/θ = 0.70); a third reading, **75**, is not reproducible from the released files |
| **service level** | the same test read at a stated pass mark | as above | as above |
| **selection set** | the three best configurations per dataset under each convention's own metric | 5 datasets | **4 of 5** differ under this section's convention (FSC-147 alone is unchanged); **0 of 5** if only textual refusals are excluded, where only ranks inside a set swap |

**Convention A** counts an abstention (or an answered `0`) as full error; **convention B** removes abstained
items from the delivered set and scores only the answered ones.

**Two design choices in this analysis, stated because either reading is only as good as the test that
produced it.** (i) A single θ (0.70) would put *both* conventions outside the region where the statistics
differ, where the test can only ever return "no change"; the 3 × 3 grid above is used instead. (ii) Scoring
both conventions with the *same* metric would make the selection sets identical by construction; each
convention is therefore scored with its own metric (full-error for A, answered-only for B).

**Why the answer depends on the convention — and what that changes.** The convention changes *how large* an
error looks and, once the numerical `0` is read as an abstention, it also changes threshold verdicts (78
cells) and the top-ranked sets (4 of 5 datasets): heavily abstaining configurations are weak counters either
way, but which of two weak counters clears a pass mark, and which one ranks first, is convention-dependent.
This is the same fact §M.23 reports from the other direction — the answers themselves do not carry the
information a decision would need. The actionable reading is therefore narrow but not empty: under the
convention this section defines, the convention **can** move a user onto a different model, and what it
always changes is that the numbers become incomparable with everyone else's — so the quantity a report must
state alongside its convention is the **abstention mass**.

*Reproduction: `code/analysis/deploy_decision2.py` over `data/derived/fsc_res/frozen384/` and
`data/derived/{e3,e2_pools}/`; frozen result `deploy_decision2_result.json`. Thresholds (§M.27 table)
were frozen before the run.*

---

### M.28 The two remaining §5.11 consequences

§5.11 keeps the convention-gap numbers; the other two consequences, with their arithmetic, are below
(their per-cell tables are in Appendix J.6 either way).

**(b) The abstention rate rises with ground truth, and (c) the scale effect is domain-dependent.** The slope
of the deviation-vs-ground-truth relation **reverses sign** between conventions, and a 4× parameter increase
enlarges the directional span by **2.5–3.1×** in the dense domains but not in the aerial domain
(**0.66–1.18×**) *(per-cell tables: Appendix J.6)*.

---

### M.29 Two §5 results

Their conclusions are in the main text; the bodies are reproduced so that no wording is lost.

#### 5.4 Cross-domain abstention summary

Aggregating over domains, the abstention rate is **not** ordered by object count. It is highest in the
dense-crowd and aerial domains (ShanghaiTech-A 56.6%, VisDrone 68.2%, AI-TOD 68.1%) and essentially
zero in the clearly-resolved domains (ShanghaiTech-B 0%, sparse sets near 0%), while ShanghaiTech-B has
**more** targets per image (124) than VisDrone (22). Object count is therefore not the ordering
variable; §5.6 identifies what is.

**What would make a stratifier valid, without defining legibility.** The paragraph above leaves open what
the ordering variable is, and the test for a candidate is decidable from the same table. Let $M$ be a
per-image quantity used to stratify images and $A$ the abstention rate, and define

$$ \gamma_k(M) := \max\{\,|A(u) - A(v)| \;:\; u \ne v \text{ in the same } M\text{-stratum}\,\}. $$

Under the reading this paper already uses — $A$ is a monotone function of legibility, and legibility is a
function of $M$ —

$$ M \text{ is a legible stratifier} \iff \gamma_k(M) = 0, \quad\text{under the deterministic reading below; the converse is not claimed for general valid stratifiers}, $$

The fourth domain's abstention rate is **180/334 = 53.89%** on UCF-QNRF (`base` arm, all 334 items parsed), to be read against the counts already printed for the other domains. This supplies the widest pair the within-stratum criterion can be tested on: **UCF-QNRF carries 718.9 annotated heads per image on average and abstains on 53.89% of items, while VisDrone carries 22.4 and abstains on 68.2%** — a **32-fold** difference in the ordering variable accompanied by a **14.3 pp** abstention difference **in the opposite direction**. The monotonicity argument printed earlier is therefore not merely incomplete: the stronger within-stratum condition `γ_k(M) = 0` fails on this pair as well.

because a valid $M$ forces equal legibility, hence equal $A$, inside every stratum, while $\gamma_k = 0$
makes $M$'s partition a refinement of $A$'s, which is what validity means here. The criterion needs no
definition of legibility and one pair falsifies it, and the published stratifier fails it at four:
**ShanghaiTech-B (123.8 targets/image, 0%)** against **VisDrone (22.4, 68.2%)**, **AI-TOD (17.0, 68.1%)**
and **ShanghaiTech-A (433.3, 56.6%)**, and **UCF-QNRF (718.9, 53.9%)** against **ShanghaiTech-A**. The
UCF-QNRF rate is measured here on the **334** images of that corpus in the released item set — **180**
abstentions, **53.89%** — by the same instrument that returns **56.59%** on ShanghaiTech-A and **0.00%** on
ShanghaiTech-B, against the **56.6%** and **0%** printed in §5.4.

#### 5.10 Aerial domain: the legibility extreme

VisDrone and AI-TOD are the legibility extreme. Tiling gives limited relief (Appendix M.8): **the aerial bottleneck is instance
under-resolution, the crowd bottleneck is overlap**, and the two respond differently to the same
intervention. The contract effect is only partly effective: lowering the pixel budget raises
abstention monotonically in both lineages, but "forbid 0" works only partly for Qwen and hardly at all
for InternVL (Appendix C.4). (Appendix M.11)



---

### M.30 The excluded mechanism hypotheses

The main text keeps the conclusion — all three candidate explanations are excluded — and the bodies are
reproduced here so no wording is lost; the frozen per-arm numbers are in Appendix M.16.

#### 7.6 Three mechanism hypotheses, tested and excluded

To explain the strong directional effect of `forbid0` we tested three explanations; **all three are
excluded.** **Mediated effect — no**: tiling drives the 32B abstention rate from **56.6%** to **0.0%** (2×2: 6.0%, 3×3: 0.55%)
with the effect nearly unchanged (**+185 → +195 → +167 pp**), and 8B at **0.0%** abstention still shows
**+24 to +40 pp**, so abstention rate is not the mediator and the magnitude is governed by the domain. (Appendix M.16)

**A census-side corroboration of the same exclusion.** With the zero forbidden, the median
predicted/true ratio on the zero pool rises from **0.000** to **3.5–6.3** on the dense domains
(ShanghaiTech-A 4.027–6.281 across the three arms and two builds of one 32B checkpoint), yet the
**same arms stay below 1** in the aerial domains (`bestB` / `bestC`: 0.250 / 0.469 and 0.333 / 0.500 on
VisDrone; 0.500 / 0.833 and 0.511 / 0.662 on AI-TOD). Forbidding the zero thus overshoots in one domain
and leaves the sign untouched in the other — the mediator exclusion read a second way, and the same
domain conditionality §7.5 reports for the corpus arms (Appendix M.18).

*(Full detail in Appendix G.)*

---

---

---

### M.31 The prospective panel: rule, frame, verdicts, and what failed

Predictions, thresholds and the sampling rule were frozen before any data were collected
(`analysis/work/w1_prereg.json`, md5 `0a42e6e5bbfa89543ba9fc1522f1b075`; re-issued: external-check traces removed only, values and criteria unchanged); post-hoc decompositions are labelled. The
full frame with every candidate and exclusion reason, the per-cell coverage table with unparsed rates, and all CSV
files are released with the paper (`w1_bundle.tar.gz`, md5 `25308f6fbbbb7b8e1a780de501b36e0c`).

#### M.31.1 Rule and frame
The rule admits open-weight multimodal instruction-tuned families of at least two billion
parameters, obtainable at no more than 35 GB, loadable on one 80 GB device, and **not used anywhere in §3-§5**;
among those it takes the most lineage-novel first, one per lineage, up to six. It yielded six families in six
lineages **with no Qwen model among them** — `gemma-4-31B-it` (Google), `Idefics3-8B-Llama3` (HuggingFace),
`Step3-VL-10B` (StepFun), `MiniCPM-V-4_5` (OpenBMB), `deepseek-vl2-tiny` (DeepSeek) and `Molmo-7B-D-0924`
(AllenAI) — of which five lineages appear nowhere in §3-§5. One enrolled family sits above the rule's 35 GB admission line, and its footprint is quoted as the serving log records it: `gemma-4-31B-it`'s checkpoint is **58.25 GiB** on disk and it loads in **58.99 GiB** of device memory (`data/derived/p2_noise4/logs/serve_w1_gemma4_31b.log`); the family is retained on the loadability clause (one 80 GB device), and the caliber is GiB, as the log prints it. **This is a protocol deviation: clause (d)'s 35 GB line is not met, and the family is retained under clause (e) alone.** Attrition is recorded with causes: `MiniCPM-V-2_6`
failed the smoke gate by answering the `base` contract with a natural-language refusal on all four gate items and
producing no parseable JSON, so it is excluded (the gate forbids prompt edits) and its lineage slot passed to
`MiniCPM-V-4_5`; three further families entered only after infrastructure gaps were closed (`trust_remote_code` for
two, the `timm` package for one, `tensorflow` for Molmo's image processor), with no prompt, parser or threshold
changed; and the reserve family was dropped after its vision and speech adapters returned zero bytes twice. Cells:
96 on the zero pool, 72 on the non-zero pool, 24 on FSC-147.

#### M.31.2 Frozen predictions and their verdicts

| id | frozen criterion | outcome |
|---|---|---|
| P1 | >= 5 of 6 families with `permit` residual <= 2% | **failed**: 4 of 6 (0.00%, 0.00%, 0.00%, 0.18%, 7.23%, 48.28%); 20 of 24 cells <= 2% |
| P2 | contract knob >= resolution knob + 10 pp in >= 70% of qualifying cells; dense minus aerial >= 20 pp | **not fully established** — the first conjunct **passed** (10 of 12), the second is **not evaluable** (every qualifying cell is aerial, so no dense/aerial contrast exists to measure) |
| P3 | domain variance component exceeds family | **passed**: 0.0959 against 0.0037 (25.8×, computed from the **unrounded** components 0.0958905 / 0.00371446 — the printed four-decimal values divide to 25.9, so the ratio is quoted from the unrounded ones), bootstrap interval [0.0831, 0.1002] |
| P4 | (a) a dense domain with rank correlation < 0.90; (b) top family unchanged in >= 3 of 4 | (a) **passed** (0.83); (b) **failed** (changed in 2 of 4) |
| P5 | (a) a hosted model with base zero rate >= 5%; (b) >= 2 of 3 with `permit` residual <= 2% | (a) **failed** (0.0% for all three); (b) **passed** (3 of 3) |
| P6 | >= 5 of 6 families with the zero rate falling by less than 20 pp under exemplars | **failed**; five of six fell by 58-93 pp |

**The criteria are conjunctions, and the frozen file has no main/secondary layer.** Every `rule_pass` above
is a single frozen string whose parts are joined by a semicolon / "and": P2 (both contrasts), P4 ((a) and (b)) and
P5 ((a) and (b)) each carry **two** conjuncts, and the preregistration contains no field that ranks one
conjunct above the other. (The `secondary` field that P1 alone carries is a *separate, stricter* quantity —
24 cell-level and base-rate conditions — not a ranking of P1's own criterion.) A prediction therefore passes
only if **every** conjunct passes, and the full verdict is: **P1, P4, P5 and P6 failed; P2 is not fully
established (one conjunct passed, one not evaluable); P3 passed** — four outright failures, one partial, one
pass. Reading P2's first conjunct as a "main criterion" and its second as a "sub-item", or P4(b) and P5(a) as
sub-items, would impose a hierarchy that the frozen file does not contain.

**What the failures bound.** P1 bounds the `permit`-residual statement and P6 the **exemplar** statement, P4(b) the **convention** statement
about which family ranks first; P2's second conjunct and P5(a) are likewise boundaries. **No headline
claim rests on a failed conjunct**, and each is written into the main text as a bounded statement.

#### M.31.3 Where the gate holds (post-hoc), and the two boundaries
Base zero rate, then `permit` zero rate, then
`permit` abstention rate:

| family | st_a | ucf | visdrone | aitod |
|---|---|---|---|---|
| gemma-4-31B-it | 1.9% -> 0.0% (100%) | 8.0% -> 0.0% (100%) | 58.0% -> 0.0% (89%) | 40.0% -> 0.7% (91%) |
| Idefics3-8B-Llama3 | 4.9% -> 0.0% (99%) | 4.0% -> 0.0% (99%) | 52.0% -> 12.7% (50%) | 34.0% -> 14.0% (29%) |
| Step3-VL-10B | 0.0% -> 0.0% (100%) | 0.0% -> 0.0% (100%) | 40.7% -> 0.0% (80%) | 24.7% -> 0.0% (79%) |
| MiniCPM-V-4_5 | 1.0% -> 0.0% (100%) | 2.0% -> 0.0% (100%) | 82.0% -> 0.0% (99%) | 66.7% -> 0.0% (93%) |
| Molmo-7B-D-0924 | 1.9% -> 0.0% (100%) | 0.0% -> 0.0% (100%) | 75.3% -> 0.0% (100%) | 60.7% -> 0.0% (100%) |
| deepseek-vl2-tiny | 0.0% -> 0.0% (0%) | 0.0% -> 0.0% (0%) | 71.3% -> 91.3% (0%) | 50.7% -> 86.7% (0%) |

Two boundaries, separated deliberately. The sparse-aerial residual of Idefics3-8B is a counting error rather than a
refused outlet: the aerial zero pools have median ground truth three and five, its residual items two to three, and
it answers zero on items with one or two objects while abstaining on half that domain. deepseek-vl2-tiny differs in
kind — in the dense domains 97.3% and 99.0% of its replies are unparsable under both contracts, so its zero rate
there is uninterpretable, while in the aerial domains it keeps answering zero under `permit` and abstains on none;
it is a genuine family x domain outlet failure, of the kind §5.13 reports for the build that needed the outlet
enumerated as an option.

#### M.31.4 The exemplar condition
Three exemplar boxes per image from the benchmark's own annotations, normalised to a
0-1000 scale and given as text; no image is modified, so the comparison is on identical pixels.

| family | zero rate base -> exemplars | MAE over all images | median relative error when a number is given |
|---|---|---|---|
| gemma-4-31B-it | 88.7% -> 0.0% | 69.2 -> 28.6 | 90.5% -> 14.4% |
| MiniCPM-V-4_5 | 92.7% -> 0.0% | 69.6 -> 64.6 | 89.4% -> 25.0% |
| Molmo-7B-D-0924 | 58.0% -> 0.0% | 68.3 -> 59.8 | 93.8% -> 71.8% |
| Idefics3-8B-Llama3 | 89.0% -> 1.7% | 69.8 -> 64.1 | 97.4% -> 93.2% |
| Step3-VL-10B | 79.0% -> 3.0% | 77.6 -> 878.8 (75 of 300 scored) | 93.8% -> 92.3% |
| deepseek-vl2-tiny | 0.3% -> 67.7% | 44.7 -> 72.2 | 28.6% -> 96.3% |

The zero disappears in five of six families and the error falls materially in one; where accuracy does improve it
improves greatly, and where it does not the zero has been replaced by a wrong number. On a second axis, then, the
same distinction holds: **an expression of failure can be removed without removing the failure**.

#### M.31.5 Hosted endpoints
Three proprietary deployments answered the same 253 items, with the census probe and two endpoint-forced
changes (`max_tokens` 128 -> 2048, because thinking tokens consumed the original budget, and
`reasoning_effort: minimal`); prompts and parser are byte-identical and `finish_reason` is stored per item
(0.00% truncated). Under a number-only contract none answered zero (0.0%); permitted to abstain they abstained
on 98-100% of those items (residual 0.00%); their median relative error where they did answer was 34.1-46.7%
against 58.5-82.6% for the open families on the same items. The frozen criterion asking for a base zero rate of
at least 5% therefore fails, and we record that as a boundary of the phenomenon rather than as support for it.

#### M.31.6 An instrument defect
The census parser's first pattern requires the key to follow the brace
immediately, while standard JSON writes `{"count": ...}`; every such reply misses that pattern and is recovered only
by the integer fallback, and the abstention form `{"count": "abstain"}` contains no integer, so it is returned as
unparsed. Of 55,351 stored rows none carries an abstention token in `pred`, 25,108 contain an abstention word in the
raw reply (23,605 in quoted JSON form, none unquoted), and 23,602 quoted abstentions were recorded as parsing
failures. **No aggregate in this paper depends on the affected column**: abstention is counted by matching the raw
reply, and answering zero is a successful parse with value zero, which the integer fallback supplies. **This is the same defect as M.6** (where the digit is present and the value is recoverable) and as **M.19.12(e)** (where it is not); the boundary is whether the reply carries a digit. The panel's
analyses were re-run under raw matching after this was found, which is why the hosted table reads as abstention
rather than as failure to parse.

#### M.31.8 The four failed predictions in full (§5.14)

The main text states the failures in one sentence; the elaboration is reproduced here so that no wording is lost.

**Four predictions failed outright — P1, P4, P5 and P6 — with P2's second conjunct not evaluable and P3 passing (§M.31.2); the two elaborated below are the informative ones.** First, the convention can change the *choice*: the
top-ranked family changes between conventions in **two of four** domains (Spearman **0.83** on UCF-QNRF), so the
"the decision does not move" asymmetry of §5.12 is a property of that configuration set rather than of the
convention. Excluding the one family whose dense output is unparsable it still changes in one domain, where the
ranking is more convention-sensitive, not less (**0.40**). Second, the exemplar prediction is falsified: three
exemplar boxes remove the zero in five of six families (**58–93 pp**), yet the error over all images falls
materially in only one (MAE **69.2 → 28.6**) and barely in three (69.8 → 64.1; 69.6 → 64.6; 68.3 → 59.8).
Accuracy *conditional on giving a number* improves in three families (median relative error **90.5% → 14.4%**,
**89.4% → 25.0%**, 93.8% → 71.8%) and not in the other two (**97.4% → 93.2%**, **93.8% → 92.3%**). **Removing the
zero is therefore not the same as becoming able to count** (Appendix M.31.4).

---

### M.32 Measurement-fragility disclosures

**Two runner defects, and one dead parse branch.** Two defects in the measurement runners were found
and are disclosed in full in Appendix I.3; both affect only the collection path, not the reported
aggregates. A third instrument finding belongs with them for the same reason: the corpus runner's
structured-JSON branch never fires, because its pattern omits the quote before the key, so every stored
value came from its first-integer fallback. We audited all **2,496** rows of the three-arm prompt experiment (**832** items x 3 arms) and the two readings
agree in **100%** of them, so the finding has **zero** measured impact (Appendix M.6).

**Run-to-run non-determinism.** Nondeterminism in this regime is documented for LLM inference [52], [53] and for evaluation harnesses [54], [55]. With temperature 0 under 4-bit AWQ the per-image disagreement rate is
**22–27%** while the aggregate change in ME stays within **0.19** counts; for a hosted API, item-level
reproducibility falls to roughly **15%**. Where the corpus contains an independent re-run of the same
configuration, the aggregate $\rho$ differs by at most **0.81 pp** across the six such pairs
(Appendix J). Aggregate conclusions are robust; per-image conclusions must be
read against the noise band, and differences below **7 pp** are treated as indistinguishable.

**Graded isolation with a residue ledger.** Some remote result files were unavailable during collection
because of server-side errors. We isolate the affected runs in graded tiers and keep a ledger of exactly
which items were affected and which analyses were recomputed without them, so a reader can reverse the
cleaning (Appendix I).

**A census of anomalous predictions, with forced exclusion.** A single anomalous item can move a row's
headline figure by hundreds of percentage points; in one family each dataset contained **exactly one**
such item, which fully explained that row's apparent effect. Values at or above `1e5`, and one exact
sentinel, are excluded everywhere, with filtered and unfiltered values reported where material.



**No attention-based criterion**, since attention sharpness is very nearly uninformative about correctness
($R \approx 0.001$). **Per-cell intervals are lower bounds**: they resample images and therefore
under-state the uncertainty from the small number of levels within a cell.

---

### M.33 The two-channel assumption, its test, and its three residual limits

**The abstention identification rests on a two-channel assumption, which the discriminating experiment
now tests (§5.7, §3.6(d), Appendix M).** Proposition 1 shows that an answered zero does not identify
abstention from outputs alone, and Proposition 7 quantifies the residual error **under the assumption that
abstentions are expressed only as answered zeros or as textual refusals**. That assumption is testable: on
the items the corpus answered 0, offering an explicit abstention option produced **1591/1591** explicit
abstentions and no zeros, and forbidding it produced best estimates at a median of **2.463–9.452×** the true
count — so on that subset the third channel is excluded. The census (14 configurations, 5 usable domains,
item-level pairing) adds a fourth limit below and sharpens the first. Three limits remain. First, the
re-query varies weight precision **and** serving engine together in E1, so it shows the channel is
configuration-dependent without isolating which of the two causes it; the census holds the serving stack
fixed and varies **the contract and the build**, which is why it can separate the two kinds of answered zero
(§5.7) but cannot speak to hosted endpoints.
Second, the subset is selected
for being answered 0, so a genuine estimate of zero outside it is not excluded, and the corpus-wide
missed-refusal share therefore remains bounded by the two-channel argument rather than measured.
Third, in the dense domains the outlet **saturates**, so the census confirms the channel there but
cannot test whether the refusal is *selective*; that question is answerable only in the aerial domains,
where the outlet is exercised on 36–93% of items the corpus had answered with a number.
Appendix B.3 states the unified channel criterion explicitly so that the assumption can be replaced
wherever it is still load-bearing.

---

### M.34 Two §5.7 detail paragraphs

**The census version of the same statement (E2).** The same experiment run as a full census —
**six contracts × six domains × 14 configurations**, on the items each domain's corpus answered 0 and,
separately, on those it answered with a number — shows the effect at **item level**: pairing each item
against its own `base` answer, adding an abstention token removes the answered zero on **46 of 52**
(model × domain) cells outright, and the three-option `channel` contract on **52 of 52**. **This census is
also the control that E1 lacks**: E1 varied weight precision and serving engine together, whereas the census
holds the serving stack fixed — same weights, engine, prompts and parser — and varies **only the contract**
(and, separately, the build). Two boundaries come with it: the outlet **saturates in the dense domains**
(89–100% of items the corpus had answered with a number) and is **selective only in the aerial domains**
(36–93%); and the answered zero has two sources — **build-specific** in dense scenes (four builds of one 32B
checkpoint 62–99%, a fifth build 9%) and **domain-specific** in aerial scenes (11 of 12 configurations
62–99%) — the split quantified by a two-way decomposition: **38.7%** domain, **33.9%** build, **27.4%**
interaction, the five deployments of that checkpoint differing by up to **90.3 pp** densely against
**2.7–8.7 pp** aerially (Appendices M.18.4, M.18.8).

**A three-way corroboration that abstention is not the cause.** Three settings in which abstention is
excluded each still under-count, but by *different* amounts: the clean synthetic grid (no answered zero on
any of its 20 cells) by **up to 50%** (five independent renders; the single render tabulated in §J.8 reaches **−42.5%**), microscopy with its abstention channel closed (0.0% answered zeros over
1,210 items) by **−50.1%**, and real images restricted to the answered subset by **−19.8%** and
**−29.2%**. These are three domain-specific magnitudes, **not one common band**; what the three share is
that the under-count survives with abstention removed, and in the first two with resolution not the binding
limit. (Appendices J.7, J.8)

---

### M.35 What a published number would do under the other convention

A table that reports one convention without its abstention mass is not merely imprecise: on a public
benchmark the two terms have different sizes. Writing $w$ for the share of items on which a system emits no
count, the published convention (an abstention counted as a predicted zero) reports

$$\mathrm{MAE}_A = (1-w)\,\mathrm{MAE}_B + w\,\overline{\mathrm{GT}}_{\text{abstained}}$$

where $\mathrm{MAE}_B$ is the error on the items it did answer. The second term is the large one, because
abstention concentrates on the crowded items: on the public benchmark the abstained items average **71.8–77.0** objects (median **72.6** across the nine configurations) against a corpus-wide mean of **70.13**.

**Nine configurations, six lineages, one benchmark.** We recomputed both conventions for every configuration
of the public-benchmark panel on the same stratified test images:

| configuration | abstention share w | MAE under the published convention | MAE on answered items only | correction |
|---|---|---|---|---|
| InternVL3_5-8B | 91.0% | 69.4 | 33.9 | **35.5** |
| Phi-3.5-vision-instruct | 85.0% | 69.0 | 23.4 | **45.6** |
| Qwen2.5-VL-3B-Instruct | 92.3% | 69.7 | 41.1 | **28.5** |
| Qwen3-VL-30B-A3B-Instruct | 89.7% | 69.2 | 32.4 | **36.9** |
| Qwen3-VL-32B-Instruct | 92.3% | 69.6 | 39.0 | **30.6** |
| Qwen3-VL-4B-Instruct | 92.0% | 69.8 | 37.3 | **32.4** |
| Qwen3-VL-8B-Instruct | 94.3% | 70.0 | 40.5 | **29.5** |
| gemma3-12b | 82.7% | 67.4 | 30.5 | **36.9** |
| llava-onevision-qwen2-7b-ov | 93.7% | 69.9 | 37.0 | **32.9** |

The correction is **32.9** counts at the median and **45.6** at its largest, while the spread between the nine configurations under the published convention is only **2.6** counts — the convention effect is **12.7 times** that spread, which is the MAE range over nine configurations from six lineages and mixed precisions rather than a single-system factor. Rank correlation between the two conventions is **0.783** with **7 of 36** pairs inverting, so the published ordering is, to first order, an ordering of abstention propensity rather than of counting ability.

**Conversion table.** For a benchmark with this ground-truth distribution (mean abstained-item ground truth
about **72.6**), a system abstaining on a share $w$ of items has its published MAE separated from its answered-only MAE by the convention term:

| w | if the answered-only MAE is 10 | 30 | 60 |
|---|---|---|---|
| 20% | +12.5 | +8.5 | +2.5 |
| 40% | +25.0 | +17.0 | +5.0 |
| 60% | +37.5 | +25.5 | +7.5 |
| 80% | +50.1 | +34.1 | +10.1 |

Two consequences follow: a number reported this way should come with $w$, since two systems differing only in
abstention propensity can differ by tens of counts while failing equally where they do answer; and because the
identity needs no re-running, the abstention mass is recoverable from any stored output and is the quantity a
reader should ask for.

*Reproduction: the nine configurations' per-item records are in the released package at `data/derived/fsc_res/frozen384/` (nine `fsc_*_base.csv`); recomputing the identity and the table from them reproduces every cell printed here. The generator used for the table is `_retro_rank_and_m35.py`, **released in the package** at `code/analysis/`; its inputs are the nine released `fsc_*_base.csv` above. The abstained-item ground-truth means are 72.90 / 77.03 / 72.04 / 73.48 / 72.13 / 72.58 / 71.77 / 75.14 / 72.14 over the nine configurations, against the panel's corpus-wide mean of **70.13**. Each is computed on the **same item set as the table above** — all items of the stratified sample, with an item whose `pred` field is empty (an explicit textual refusal) counted as an abstention, which is what the table's $w$ counts. Two configurations, Qwen3-VL-30B-A3B and LLaVA-OneVision-7B, have unparsed items and are the only two for which the two item sets differ; reading their means on the parsed subset instead would move them to 72.08 and 77.07 and break the identity above on exactly those two rows, so we state the set here.*

---

### M.36 Can a new family's zero rate be predicted from its contract and domain?

The panel of M.31 permits one predictive test that needs no new data: **hold a family out entirely, fit on
the other five, and predict its cells.** The inputs are deliberately family-free — the contract arm and the
domain, plus that domain's zero-pool ground-truth statistics, which are identical across families because the
pool is defined by the census corpus. The target is the answered-zero rate of each (family, domain, contract)
cell, in per cent. The criterion was fixed before the run: a model counts as predictive only if its
leave-one-family-out MAE is at least 30% below the global-mean baseline **and** its predicted-versus-observed
correlation reaches 0.8.

| model | inputs | leave-one-family-out MAE (pp) | predicted vs observed correlation |
|---|---|---|---|
| M0 baseline | global mean | 24.3 | -0.321 |
| M1 | domain x contract mean | **11.7** | **0.673** |
| M2 | linear in [dense, permit, domain ground truth] | 17.4 | 0.607 |

**Verdict: partially predictive, and we do not upgrade it to a law.** Domain and contract alone reduce the error for an unseen family by **52%** (from 24.3 pp to 11.7 pp), and the ranking of cells is recovered at r = 0.673 — below the 0.8 bar fixed in advance, so the pre-registered criterion **fails**. What the numbers do support is a bounded statement worth stating exactly: knowing only which domain and which contract a new family faces, its answered-zero rate can be predicted to within about **12 pp** on average — a leave-one-family-out mean absolute prediction error, not a coverage bound — against a range that spans 0% to 91% across the panel; adding a linear term on the domain's ground-truth statistics does not improve on that (M2 is worse than M1), which is itself informative — the domain enters as a category, not through a smooth difficulty axis that these features capture.

Resampled at the item level (1,000 draws), the components separate: domain **0.0959** [**0.0875**, **0.1039**] (author-side, and its producer is not part of the released package, so this second interval is not independently recomputable; the interval of record is the frozen one above)
against family **0.0037** [**0.0024**, **0.0051**] — 25.8-fold, intervals not overlapping. This is a **second**
resampling of the same domain component, under a different scheme from the one of record: the frozen
`w1_quoted.json` carries **`[0.0831, 0.1002]`**, and that is the interval printed in M.31.2. The two differ in
scheme, not in conclusion — both exclude zero by a wide margin, and the verdict is read from neither alone — so
we print both rather than one, and label which artifact each comes from.

The residual is the part family identity still owns: twelve percentage points is the same order as the spread
between families within one domain under one contract, so "this contract will clear the zero for a new family"
is supported only in the dense domains (M.31.3), where five of six families sit at or below 8%.

The per-cell rates behind the table are the ones listed in **M.31.3** (base zero rate, `permit` zero rate,
`permit` abstention rate, for every family and domain); the machine-readable form, including the two
held-out-model predictions, is `w1_predict.json` in the released package.

Domains: `st_a` and `ucf` are dense, `visdrone` and `aitod` aerial; every cell is a zero-pool cell, so the base
rates are conditioned on items the census had answered zero.

---

### M.37 Which calibration calibers preserve the ordering

§7.3 scopes the ordering claim to two calibers. This section gives the measurement behind that scope.

**Design.** For each unit a third of its items is held out as a calibration fold (drawn once, reused across
levels); the calibration is fitted there and the pooled relative deviation recomputed at every level on the
rest. The calibrator is the deployable affine caliber used throughout this paper,
`pred' = a·pred + b`, fitted by regressing the ground truth on the prediction; the shared variant fits one
`(a, b)` for all units. 200 splits, fixed seed. **The fold is item-level and within-unit**: a calibrator is
never fitted on one domain and applied to another, so this section measures calibration *inside* a domain and
tests **no cross-domain transfer** of a calibration map.

**Two unit sets, reported separately.** (i) the **8** units of the frozen ordering object whose released records
carry per-item data (`res_ctrl` 6, `tiling` 2) — their reconstructed full-item spans reproduce
`span_equalcount_result.json` bit for bit; (ii) **36** units built from the same per-item records Appendix F draws on
(detector threshold, density regression, output contract, prompt family), eligible by the rule applied there
(at least 3 levels, at least 20 common items). The two sets come from different files and different item intersections, so
their spans are not comparable term by term.

| Calibrator | Spearman vs the uncalibrated ordering, 8 units | 36 units |
|---|---|---|
| none (held-out, no calibration) | 0.976 | 0.995 |
| shared affine, one `(a, b)` for all units | 0.976 | 0.995 |
| **per-unit affine, one `(a, b)` per unit** | **0.810** (P ≥ 0.9: 18%) | **0.536** (0%) |
| per-unit affine, refitted per level | 0.548 | 0.523 |
| per-unit isotonic | 0.571 | 0.521 |
| per-unit quantile map | 0.690 | 0.410 |

**A family with the abstention share as a second input is not an omitted row.** Every shape in the table above
is a function of the **prediction** alone, and a family $f(\text{pred}, w)$ cannot be fitted in this
protocol. Proposition 4's $w = G_N/G$ is a **ground-truth** quantity: it is not observable at deployment, and
it is not defined on a held-out **item**, so the held-out-third design above cannot estimate it. Its
observable analogue — the item-count answered fraction — does not recalibrate a prediction at all; it
changes the **estimand**, which is exactly the family of changes this paper reports as its two conventions
and quantifies in §5.12 (one configuration's bias moves by up to **48.2 pp** and the ranking falls from
Spearman **1.000** to **0.476**). The shape is therefore **measured under another name rather than absent**,
and we state that here rather than leaving the omission unexplained.

**Why the shared case is exact.** When the fitted coefficients do not vary with the level,
`rho'(l) = a·rho(l) + c_u` with `c_u` independent of the level, so `span' = |a|·span` holds exactly (asserted
to 1e-13). A shared calibrator therefore multiplies every span by one number, leaving the ordering invariant;
this is Proposition 5's `span -> s·span`.

**The scale factor.** The measured per-unit `s = |a|` spans **0.027–2.352** (median 0.863 over the 8 units,
0.488 over the 36), the shared fit gives `s` = 0.789 and 0.162. **What breaks the ordering is therefore not
compression but the heterogeneity of the map across units**; a per-unit calibrator is merely the extreme
case of it.

**The rung between those two ends — and it lands with the failure, not between them.** The comparison above
has only two rungs (one map for all units, or one map per unit), so we added the middle one: **one map per
knob** — six maps, each fitted by pooling that knob's domains. It reproduces all six pre-existing arms of
**both** frozen artefacts to max|Δ| = 0.0000, so it is directly comparable, and on the 36-unit set the
ordering falls to Spearman **0.790** (200-split 5–95% **0.728–0.833**) — **below the 0.9 bar in 200 of 200
splits**, against **0.995** for the single global map and **0.536** for a per-unit one. A per-knob
*isotonic* map gives 0.756 and a single global *isotonic* map 0.816. The mechanism is exact: the per-knob
map leaves the **within-knob** ordering untouched (identical within-knob Spearman in all six knobs, span
ratios constant to 2.2e-13) and the entire loss is **between knobs**, where the six factors span **7.7×**
(0.077–0.590), against a 979× spread across the 36 units (0.004–4.330) and a **single** factor for the
global fit.

**Only one global affine map keeps the magnitudes mutually comparable, and "shared" alone is not enough.**
After calibration the 36 spans retain a common scale only under a **single global affine** map (one factor
for every unit); the spread of per-unit retention is **1×** for it, **9×** for the per-knob map and **95×**
for a per-unit one — and a global **isotonic** map, although shared, already gives **898×**, because
span-multiplicativity requires a map that is both affine *and* level-independent, not merely monotone.
That is the quantitative form of the "shared isotonic lands in between" row above.

`A ≤ r_min` ⇔ the published ordering is preserved; `A > r_min` ⇔ a constructive counterexample **exists**.

**The threshold is a wall, not a tolerance, and it is set by the closest resolvable pair.** The rows above
differ in one respect only: whether the map's factor varies across units. Write $x_1 < \dots < x_{36}$ for
the uncalibrated spans and $s_u$ for the factor a caliber applies to unit $u$; a caliber is
**level-independent** when $s_u$ does not depend on the level, which is exactly the affine case of
Proposition 5. A pair $i < j$ is then inverted exactly when $s_i x_i > s_j x_j$, i.e. when
$\log s_i - \log s_j > \log(x_j/x_i)$, so with $A = \max_u s_u / \min_u s_u$,

$$ \text{the ordering is preserved for every such caliber} \iff A \le r_{\min} := \min\{x_j/x_i : x_i < x_j\}, $$

and the bound is attained: for the pair realising $r_{\min}$, taking $s_i = \max s$ and $s_j = \min s$
inverts it. (At $A = r_{\min}$ that pair can only tie, never invert, which is why the condition is stated
on the weak order.) On this table $r_{\min}$ is set by `det·zero-shot COCO (full grid)` at
**61.7181 pp** against `VLM·tiling / Qwen32B(ctile) / ucf / forbid0` at **61.6399 pp** — **0.13% apart** —
so $r_{\min} = 1.0013$. Two units, `det·in-domain(micro)/BBBC005 (full grid)` and its `tau@1536` sibling,
coincide exactly at **112.3128 pp**; a strict order does not exist there, and the radius is quoted on the
closest pair that does resolve. The consequence is narrower than a tolerance band and sharper than a
ranking: **every caliber whose factor varies across units by more than 0.13% has *some* factor assignment that reverses this ordering** — so no bound at that granularity *guarantees* preservation, and the per-knob map (7.7×) had no such guarantee to invoke. That is a statement about the *worst case over assignments*, not a claim that each individual map fails: a map that gives the larger factor to the larger reading can still keep the order. The loss then grows with $A$ monotonically. Over the same 36 units
the Kendall $\tau$ against the uncalibrated ordering is **1.0000** at $A = 1.000$ (the shared case, exact),
then **0.9111 / 0.8476 / 0.8381** as $A$ rises through **2.572× / 3.558× / 5.024×** for the equal-count and
extreme-dropping deflations, against Spearman **0.983 / 0.947 / 0.933**. The rungs are not a ladder of fit
quality; they are one wall, crossed once.

**This is a property of the unit set, not a universal.** On the 8-unit frozen set, which contains only
**two** knobs whose factors differ by 1.39×, the per-knob map is **indistinguishable** from the global one
(0.976, 200 of 200 splits at or above 0.9). The middle rung is therefore harmful in proportion to how
heterogeneous the unit set is **at knob granularity**, and any statement of this result carries that unit
count with it.

*Reproduction: `analysis/work/a39_perknob_rung.py` and `perknob_rung_8unit.py`; frozen results
`a39_perknob_rung_result.json` (md5 `643b71fcbdd2bdb38282e46b7ae72b68`) and `perknob_rung_8unit_result.json`
(md5 `63ceb33804756655956d873c13a8d62e`). Per-item records are those `a39_unit_calib_heldout.py` loads. The
5–95% figures are **200-split empirical quantiles, not bootstrap intervals**. A robustness pass dropping the
two retired reproductions is available and not run — **and carrying it out leaves the conclusion
unchanged and sharper**: on the 34-unit set the single global map still holds the ordering at **0.994**
(200 of 200 splits at or above 0.9) while the per-knob map falls to **0.722–0.724** (**0** of 200), so the
gap widens from **0.205** to **0.271–0.273** and the between-knob collapse deepens from **0.486** to
**0.371**; the two draws of the split protocol agree to within 0.002, so removing the units — not the
drawing — is the only variable (`a39_perknob_robust34.py`;
`a39_perknob_rung_robust34_result.json`). The middle rung's cost is therefore **not** caused by the two
retired units.*

**The ordering is specific to the pooled relative deviation, and does not transport across error
calibers.** A span is a range of *some* error measure, so we re-ranked the 36 units under two other
calibers. Under a dimensionless per-item log ratio ($\operatorname{median}(\ln(\text{pred}+1) -
\ln(\text{gt}+1))$) the Spearman against the $\rho$ ordering falls to **0.629**, and under a per-item rank
correlation — which is invariant under **any** monotone rescaling of either variable, and is therefore the
strongest form of the "the span is merely a scale artefact" objection — to **0.595**; the top-ranked unit
changes under both. The criterion a reviewer set for dismissing that objection was Spearman above 0.85, so
**the objection is not dismissed in this form**. It is also **not** an artefact of absolute magnitude:
pooling and per-item averaging agree at **0.965**, so what moves the ordering is the **functional form of
the error measure**, not the aggregation. We therefore state the ordering as an ordering **under the pooled
relative deviation**, the caliber in which every number in this paper is reported. Four subsets — all 36
units, the 34 without the retired reproductions, levels ≥ 4, and both restrictions together — all remain
below 0.85 (**0.580–0.754**), and the result is insensitive to whether each level's own item set or the
common intersection is used (**0.632 / 0.594**). Two related controls: against a **GT-shape-matched** subset
the ordering is unchanged (Spearman **0.983**, a drop of 0.017 against the reviewer's 0.2 threshold), but an
**absolute** ground-truth-profile match is **not constructible** from these records — the units'
ground-truth supports are nearly disjoint and the common profile is **9** items, below our own 20-item
eligibility floor — so that branch is left open rather than tested. Under a signed absolute count error the
Spearman is **0.634** (median) and **0.798** (mean), with the top unit unchanged in both.

*Reproduction: `n1_span_artefact_tests.py` and `n1b_extras.py`; frozen `n1_span_artefact_result.json`
(md5 `4c7c22b87da4192f367bdba44dd4fe16`) and `n1b_extras_result.json`
(md5 `605d626747b72fa254f016b8f3071f89`), with 68 per-item record files and their md5s in the JSON's
`file_inventory`. The random-deletion retention table there is computed over the 36-unit set and is **not**
the F.10 object (six detector ladders of 8–16 levels); the two are not comparable and are not pooled.*

**Which calibrators a deployer can actually use, and what they cost the ordering.** The ladder above tests
one global map and per-unit maps; a deployer's realistic options sit between them, so we fit **eleven map
shapes at five granularities** (global, per-domain, per-(domain × contract), per-knob, per-unit) on the same
36-unit set and the same split protocol, first reproducing all six pre-existing arms of **both** frozen
artefacts to Δ = **0.0000**.

| calibrator (granularity) | median ρ | 5–95% | P(≥0.9) | between-unit spread of spans | deployable |
|---|---|---|---|---|---|
| none; global affine; global Poisson scale; global slope-floored affine | **0.995** | 0.984–0.998 | **100%** | 22.3–22.7× | yes |
| global kernel regression | 0.841 | 0.772–0.888 | 2% | 31.8× | yes |
| global sigmoid (Platt-style) | 0.852 | 0.793–0.876 | 0% | 20.8× | yes |
| global log-count affine | 0.692 | 0.671–0.712 | 0% | 21.5× | yes |
| global monotone piecewise-linear | 0.585 | 0.559–0.614 | 0% | 27× | yes |
| **per-domain affine — 20 labelled images per configuration** | **0.732** | 0.585–0.846 | **0%** | 37.2× | **yes** |
| per-domain affine — 20 labelled images per domain | 0.730 | 0.494–0.898 | 4% | 37.0× | yes |
| per-domain affine — every labelled item of the domain | 0.736 | 0.682–0.790 | 0% | 42.1× | yes |
| per-(domain × contract) affine | 0.695 | 0.635–0.780 | 0% | 24.2× | yes |
| per-knob affine | 0.790 | 0.728–0.833 | 0% | 31.2× | needs a labelled sample per knob |
| per-unit affine | 0.536 | 0.428–0.647 | 0% | 11.3× | needs target labels per unit |
| per-unit, per-level affine / isotonic / quantile | 0.410–0.523 | — | 0% | 4.4–7× | no |
| **constant map** (negative control) | undefined | — | — | 0 | — |

**The two criteria are complementary, and that is stronger than the claim needs.** Median ρ ≥ 0.9 holds for
exactly five arms, and the between-unit spread of spans stays at ≈ **1.2×** for **exactly those same five**;
no other arm satisfies either. Those five leave the spread of spans **unchanged** (22.3–22.7× against 22.7×
uncalibrated): they rescale the caliber without making two units comparable. Conversely, every arm that
**does** pull the magnitudes toward a common scale — per-unit per-level 4.4×, per-unit isotonic 5×, per-unit
quantile 7×, per-unit affine 11× — sits at ρ 0.41–0.54 with P(≥0.9) = 0. **Among eleven map shapes at five
granularities there is no arm in between.** The best deployable *nonlinear* families reach only 0.841
(global kernel) and 0.852 (global sigmoid), below the bar and with no gain in comparability.

**The requirement is therefore not "per-unit" but "a factor that varies across units".** Every granularity a
deployment can actually fit already varies it enough to lose the ordering: per-domain **0.732**,
per-(domain × contract) **0.695**, per-knob **0.790**, per-unit **0.536** — none above 0.9 — and the damage
is worst **between** groups (group-level ρ **0.393** for per-domain, **0.486** for per-knob).

**One distinction we state explicitly, because it is the shape a counter-argument would take.** If
"compresses" is read as *reduces the median span*, then a single global affine does compress it, by **6.2×**
(83.0 → 13.4 pp), while holding the ordering at 0.995 with 200 of 200 splits above 0.9 — which is
Proposition 5 itself. What it cannot do is **make two units' spans mutually comparable**: one factor maps
22.7× to 22.3×. Our claim is therefore that **no deployable family equalises the magnitudes while preserving
the ordering**, not that none compresses them.

**Two limits of this table, and one defect it exposed.** Conformal calibration is **not scorable here** — it
emits intervals, whereas this table's estimand is a point statistic, and its nearest point-map relative is
the quantile row. Platt scaling is defined for a **binary** target and temperature scaling has no standard
regression form; we fit the nearest well-defined monotone point maps (a four-parameter sigmoid and a power
family) and label them as substitutes. The constant map is the negative control and is *undefined* rather
than poor, since it makes every span zero. **The defect**: the unit printed as `density·CSRNet / ladder` is
the **UCF** ladder — the label comes from the evaluation file name, which yields `ladder` where the domain is
`ucf` (and `st` where it is `st_a`). Neither its span nor its membership of the retired pair is affected, and
in the per-domain row above it forms a one-unit group; regrouping it with UCF would move that row slightly
**up**, not to 0.9. We leave the printed label as the frozen artefact has it.

*Reproduction: `analysis/work/n3_deployable_calibration.py` (`--nsplit`, `--diag-units`), with both
reproduction gates passing at Δ = 0.0000 against `a39_unit_calib_heldout_result.json` (md5
`392369af65f13dcbf7720bc612fbf5ee`) and `per_unit_affine_heldout_result.json` (md5
`7d1f4667efb44a8d5831b16e2bf0429d`). **A protocol trap worth recording for anyone extending this ladder:**
the calibration fold is drawn from a single `random.Random(SEED)` stream consumed in unit order, so any extra
draw taken from that stream de-synchronises every later unit's fold — it first showed up as a large
discrepancy on exactly the per-(unit, level) arms. The sampling here uses a second, separate stream.*

**Reproduction.** the three scripts named above; frozen results alongside them.

**Two of these units are retired reproductions, and we report the ordering without them.**
`density·CSRNet / st` (1451.3 pp) and `density·CSRNet / ladder` (387.4 pp) are the superseded
reproduction that §K retires as an implementation defect, yet they sit at the top of this bearing set and
set the impression that a span can reach a thousand pp. Removing both and recomputing the rank agreement
between the full-level spans and their equal-count $k=4$ counterparts leaves the ordering intact
(Spearman **0.980** on 29 units, bootstrap 95% interval **[0.930, 0.997]**, against **0.983** on all 31),
so the ordering claim does not rest on them — but the **largest span falls from 1432.9 pp to 367.1 pp**,
and the magnitude impression does. We therefore keep the ordering and drop the magnitude reading of this
set.

**The 36 units themselves.** The per-unit values behind the table above, so that the ordering can be
audited unit by unit rather than only in aggregate (all levels, and the equal-count $k=4$ deflation of
§F.10):

| unit | span (all levels) | span (equal-count, k=4) |
|---|---|---|
| density·CSRNet / st | 1451.3 | 1062.2 |
| density·CSRNet / ladder | 387.4 | 330.1 |
| VLM·prompt family / Qwen32B / ucf / base | 367.1 | 362.2 |
| VLM·prompt family / IVL / ucf / under | 325.3 | 324.4 |
| VLM·prompt family / IVL / ucf / over | 276.4 | 276.4 |
| VLM·tiling / Qwen32B(ctile) / ucf / choice | 260.4 | — |
| VLM·output contract / q32 | 259.4 | 259.4 |
| det·in-domain/VisDrone (full grid) | 204.9 | 164.3 |
| det·in-domain/VisDrone / tau@1536 | 195.7 | 195.7 |
| VLM·prompt family / Qwen32B / ucf / under | 189.0 | 188.8 |
| VLM·prompt family / Qwen32B / ucf / over | 187.3 | 155.2 |
| VLM·output contract / ivl | 160.7 | 160.7 |
| det·in-domain/VisDrone / tau@1024 | 159.3 | 159.3 |
| VLM·tiling / Qwen32B(ctile) / ucf / range | 114.6 | — |
| det·in-domain(micro)/BBBC005 (full grid) | 112.3 | 34.4 |
| det·in-domain(micro)/BBBC005 / tau@1536 | 112.3 | 112.3 |
| det·in-domain/VisDrone / tau@640 | 95.9 | 95.9 |
| VLM·prompt family / IVL / ucf / base | 73.5 | 73.5 |
| det·zero-shot COCO (full grid) | 61.7 | 32.5 |
| VLM·tiling / Qwen32B(ctile) / ucf / forbid0 | 61.6 | — |
| det·zero-shot COCO / tau@1536 | 55.5 | 55.5 |
| VLM·tiling / Qwen32B / ucf / base | 40.5 | 40.5 |
| VLM·tiling / Qwen32B(ctile) / ucf / base | 40.0 | — |
| det·in-domain(micro)/BBBC005 / tau@1024 | 36.0 | 36.0 |
| density·official DM-Count / ucf | 35.1 | 29.2 |
| VLM·tiling / Qwen8B(ctile) / ucf / base | 32.9 | — |
| density·official DM-Count / st_a | 32.6 | 32.0 |
| det·zero-shot COCO / tau@1024 | 30.3 | 30.3 |
| det·in-domain(micro)/BBBC005 / tau@640 | 29.3 | 29.3 |
| det·zero-shot COCO / tau@640 | 16.4 | 16.4 |
| VLM·pixel budget / q32 / visdrone | 14.6 | 4.6 |
| VLM·pixel budget / q32 / ucf | 14.1 | 8.8 |
| VLM·pixel budget / ivl / visdrone | 7.1 | 3.8 |
| VLM·pixel budget / q32 / st_a | 4.0 | 2.2 |
| VLM·pixel budget / ivl / ucf | 2.8 | 2.6 |
| VLM·pixel budget / ivl / st_a | 1.0 | 1.0 |

The unit-name prefix gives the implementation type (`det`, `density`, `VLM`); the `k=4` column is the
**common-four-level** deflation on each unit's **item intersection** (§F.10). Generated from the released
per-item records by `equalcount36_result.json` (md5 `bd70867b1453`) via `gen_m37_unit_table.py` — not transcribed.

---

**A different fold, and a shared monotone map.** With the calibration fold drawn as three **disjoint thirds**
rotated by split (a different subset from the one above), the per-unit families collapse as before (medians
**0.514 / 0.562 / 0.534 / 0.428**), a single shared **affine** map again preserves the ordering exactly
  (**0.984**, ≥0.9 in **100%** of 200 splits, identical to the no-calibration control), and a single shared
**isotonic** map lands in between at **0.810** (≥0.8 in **100%**, ≥0.9 in **0%**). The ordering is thus robust
to *shared* calibration of either kind and destroyed by **per-unit refitting** — as other operations
reported in this appendix also lower the 36-unit ordering (`a39_sharediso_fold2_result.json`).

**The same robustness on a unit set of the same per-item sources.** The three deflations of F.10 — equal-count
gridding, and removal of each ladder's highest and lowest level — were recomputed on the 36 units of this
section, which are built **only** from per-item records (**two** of those per-item counterparts, for the BBBC005
and DM-Count units, are held by the authors; §F.2). At the same level count (the 31 units with at least
four levels; equal-count target *k* = 4) the ordering is preserved at Spearman **0.983 / 0.987 / 0.983**,
against **0.999 / 0.981 / 0.991** for the 24-unit frozen set of F.10 (person-matched; **1.000 / 0.978 /
0.990** all-detections — the F.10 set carries both calibers and they are never pooled). On the whole 36-unit set, where the
equal-count target falls to *k* = 3, the three values are 0.933 / 0.947 / 0.983. The F.10 set remains the
pre-registered object; the set used here is its per-item counterpart, recomputable from the released
records, and it is the set on which the
calibration analysis above also runs.

*Reproduction: `eb2_equalcount36.py`; frozen result `equalcount36_result.json`.*

Both alternative explanations are now measured rather than assumed. Recomputing every unit's span on its **answered** items only — the convention that excludes the abstention term — leaves the ordering at Spearman **0.962** against the pooled one and does not change the top knob, so the spectrum is not an abstention-quality artefact. Normalising each span by its unit's median ground truth leaves **99.99%** of the ordering intact for every β we tried, and the ground-truth magnitude explains **under 1%** of the log-span variance (OLS, β̂ = 0.082); the single change is the **top** unit at β = 1. (*Reproduction: a released answered-only recomputation script.*)

### M.38 A true-zero control for the answered zero

§8.2 states the two-channel assumption on which Proposition 7 rests. This section reports the control that
tests it directly: whether an answered zero on a dense image is a *claim that nothing is there*, or a
*suppressed abstention*.

**The pool.** No corpus in this paper contains an image with ground truth zero (minimum counts: `st_a` 66,
`ucf` 65, `st_b` 9, VisDrone 1, AI-TOD 1). We therefore built one from the dense domain itself. For each
UCF-QNRF test image we slid a square window of side 0.35 x min(H, W) and kept only those windows whose box,
**expanded by 48 px**, contains **no annotated head point**; by the dataset's own annotation the correct
answer for such a window is zero. This gives **306** crops — **153 easy** and **153 hard**, split at the
median of a clutter proxy (the standard deviation of the Laplacian of the greyscale crop; medians 8.76 and
27.79).

**The test.** The frozen probe was run unchanged on both strata with the `base`, `permit` and `channel`
arms, on five families, under the serving configuration of M.19. The comparison pool is the census zero
pool: dense items with ground truth far above zero that the census had answered zero.

| pool | `base` answers 0 | `channel`: `no_people` | `channel`: `cannot_judge` |
|---|---|---|---|
| true zero, easy (153) | 54-84% | **47-87%** | 8-47% |
| true zero, hard (153) | 46-84% | **39-90%** | 5-52% |
| census zero pool, dense (103 and 150) | 0-1% | **0-1%** | **98-100%** |

**The outlet is used selectively and correctly.** On genuinely empty images the three-way contract returns
`no_people` on 47-87% of items, whereas on dense images that the census had answered zero the same models
return `no_people` on 0-1% and `cannot_judge` on 98-100%; the rate difference is 0.47 to 0.86 in absolute
terms for every family measured. An answered zero on a dense image is therefore **not** a claim of emptiness,
which is exactly the auxiliary channel Proposition 1 requires.

**The emptiness channel has to be enumerated, not merely permitted.** With only `abstain` available
(`permit`), the same models abstain on **78-100%** of the true-zero images: without a `no_people` option they
cannot report emptiness even when the answer is zero. This reproduces, on true zeros, the M.24.3 finding that
the outlet must be *enumerated as an option*.

**Boundary.** The separation is weakest for Gemma-3-12B, at 47% `no_people` against 47% `cannot_judge` on
the easy stratum; the other four families separate 69-87% against 8-31%. It is reported as family-dependent, not universal.

*Reproduction: `ea_build_z0.py` (pool), `20a_probe_truezero.py` (driver; imports the frozen probe and asserts
its md5), `ea_finalize.py`; frozen result `ea_truezero_result.json`; the pool and the per-item records are in
the released package. Because the frozen parser mis-records standard JSON as a parse failure (§8.1), every
rate here is computed by matching the raw response text — the convention already used for the abstention
statistics, and the **default of the released analysis** (`a5_judge.py`: `MATCH_MODE = 'raw'`; the corpus
parser's structural branch does **not** fire on `{"count": 120}`, per `corpus_parse_audit.py`). Parsing JSON
strictly will not reproduce these rates.*

---

### M.38.1 The same control on a second, source-disjoint pool

§M.38's true-zero pool is drawn from a single source. To ask whether the emptiness-outlet rate is a property
of the *design* or of the *pool*, we built a **second** verify-empty pool under the identical window rule
(square window of side $0.35 \times \min(H,W)$, expanded by 48 px, kept only if the expanded box contains no
annotated head point; stride $=$ side$/3$) but from an **entirely disjoint source**: UCF-QNRF **Train**
(1,201 images) instead of **Test**. Both pools take 1,500 empty and 1,500 non-empty windows
($\pi = 0.5000$), and both were machine-checked to be **disjoint** from the 300-item frozen true-zero pool and
from the 226-item census (both intersections empty). Four builds $\times$ three fresh service starts
$\times$ 2 pools, **36,000** calls per pool, on the same probe and the same serving geometry, so the two runs
differ in exactly one thing: the source of the pool.

| build | Train pool (s1 / s2 / s3) | Test pool (s1 / s2 / s3) | $\Delta$ |
|---|---|---|---|
| Gemma-3-12B | **40.67 / 40.67 / 40.80%** | 48.27 / 48.27 / 48.13% | **−7.51 pp** |
| Phi-3.5-vision | **77.99 / 78.08 / 78.13%** | 86.85 / 86.84 / 86.83% | **−8.78 pp** |
| InternVL3.5-8B | **77.47 / 77.47 / 77.53%** | 81.20 / 81.27 / 81.27% | **−3.76 pp** |
| LLaVA-OneVision-7B | **79.84 / 79.84 / 79.84%** | 86.07 / 86.07 / 85.99% | **−6.20 pp** |

**All four builds answer zero on the Train pool at a lower rate than on the Test pool** (−3.8 to −8.8 pp), and
each build's three starts agree to within **0.02–0.14 pp** (LLaVA-OneVision-7B's three starts are
bit-identical), so the shift is a property of the pool rather than of the sampling. On the non-empty half the
direction is **not** uniform (Phi-3.5-vision falls by 0.28 pp, InternVL3.5-8B rises by 0.2 pp and
LLaVA-OneVision-7B by 0.6 pp), so this pool sensitivity is specific to the empty side. This is the measurement
behind the paper's standing wording that the emptiness-outlet rate is **a rate on a stated pool**: the point
estimate moves by **4–9 pp** between two pools built to the same rule, while the **39–90%** band printed in
M.38 contains both.

*Evaluability.* Each pool yields **18 of 24 evaluable cells**. Every parse shortfall in both runs comes from
LLaVA-OneVision-7B, which falls below the 95% gate in all six of its cells in each pool (Test: 89.47% on the
empty half, 80.80–80.87% on the non-empty half; Train: 92.93% and 90.47–90.53%). Those cells are reported as
**not evaluable**, not as failures, and that build's parse rate on the same window rule also differs between
the two pools (92.93% against 89.47% on the empty half).

*Reproduction: both pools are built by the same generator with only the source directory changed, and both
frozen item lists and criteria files are released; the four-build runs are three fresh service starts each on
one card, and the per-item records for both pools are in the released package.*

### M.39 A language control for the corpus-level rates

Every corpus-level rate in this paper was measured with **Chinese** prompts. To test whether the conclusions
depend on that, we rendered the three contract arms into a byte-frozen, **semantically equivalent English**
version (frozen table md5 `a31bd97c6b70`) and re-ran them on **exactly the items already scored under
Chinese**, so that the comparison is paired item by item: 5,290 calls, five families, four pools — the two
true-zero strata of M.38 and the `st_a`/`ucf` census zero pools. The two census zero pools are **subsets of**
their domains, not the domains themselves — **103** and **150** items against the two domains' **182** and
**334** — so every rate below is a rate **within the subset**, not a whole-domain rate of §5.5. The
instrument is the frozen probe of M.19, imported rather than modified.

**The channel result is language-robust.** The `no_people` rate of the `channel` arm differs between the two
languages by **-7.2 to +2.6 pp** in every (family, pool) cell, with a per-item classification agreement of
**97.1%** (median; range 82-100%) across the **19** `channel` cells, and **95.4%** (median) across all **38**
arm × family × pool cells — two different populations, now reported separately. On the dense pools both languages give `no_people` at 0-1.3%. The M.38
verdict — that the outlet is used selectively and correctly — therefore does not depend on the prompt language.

**The answered-zero rate is not.** For the anchor lineage, Qwen3-VL-32B-Instruct answers zero on **60.2%** of
the dense pool — **62 of its 103** items — under Chinese and **17.5%** under English, a **42.7 pp** drop; the four other families sit at
approximately zero in both languages, so the sensitivity is concentrated in the lineage the corpus is built
from. On the true-zero strata the two languages differ in both directions and by at most 12.4 pp.

**Consequence.** The abstention shares of §5.5 are scoped to the prompt language and build measured here; the
M.38 control is unaffected.

**The share itself is language-dependent, and can leave its definitional domain.** We extended the English arm
to the **four headline cells** themselves (**BF16** build, `base` arm, same items as the Chinese records, using
the same frozen English table). The share $S$ is defined as the abstention term over the total under-count, so
it presumes the answered items under-count **on net**; under English that presumption fails in the densest
cell, where the answered-zero rate falls from **35.7% to 9.3%** on that same BF16 build — **not** from the
**56.6%** of §5.5, which is the **whole 182-item** domain on the corpus's own 4-bit build, so those two are
not the two ends of one contrast — and the answered term turns positive, so the ratio is **no longer a
share**: on this run $S$ is **undefined** rather than above 100% (the 82–94% range therefore does not transfer to English
as a range). **Leaving the unit interval is not, however, an English-only phenomenon:** of the twenty
(language × configuration) cells, §M.19.16(ii) records **three** outside it — **102.9%** on UCF-QNRF
`cn-base`, **610.8%** on ShanghaiTech-A `en-base`, and **undefined** on UCF-QNRF `en-base`. What the three
share is the **near-zero net deviation of the answered items**, not the prompt language; both languages
supply at least one. **That enumeration belongs to the BF16 build, and the cell set is itself build-dependent**
— re-running the English arms on the corpus's own 4-bit build (§M.46(c)) leaves **two** of the twenty cells
outside the interval, **both of them English**, and the Chinese cell that is outside on BF16 returns **inside**
it. What is build-robust is the mechanism, not the cell list: a cell leaves the interval when the answered
items stop under-counting on net, and on both builds that is what the affected cells have in common.
The two aerial cells are stable instead — AI-TOD **83.8% → 79.7%** and VisDrone **82.1% → 76.6%**
(−4.1 and −5.5 pp) — so the aerial conclusions are **not** language-sensitive, while the dense ones are. One
cell (UCF-QNRF) is **not measurable** at this setting: 203 of 334 items return HTTP 400 because their vision
tokens exceed `max-model-len`, which is an infrastructure limit rather than model behaviour, and we report it
as unmeasured rather than imputing it.

*Reproduction: `20b_probe_lang.py` (driver; imports the frozen probe and asserts its md5),
`ea_lang_manifest.py` (the paired item list), `ec_finalize.py`; frozen result `ec_lang_result.json`; the 38
per-cell records are in the released package. Rates are computed by matching the raw response text, as in
§8.1.*

### M.40 The true-zero pool under repetition: five builds, two languages, three service starts

**Design target:** **independently verified, mixed true-zero / non-zero images, at least four
builds, in two languages, across three service starts** (provenance: Appendix Z). The pool is the one of
§M.38 (windows over UCF-QNRF
whose expanded box contains **no annotated head point**, hence a correct answer of **0**; **306** of them,
split into **z0easy** and **z0hard** by a clutter proxy), and the non-zero control is the frozen non-zero
pool of §5.7 measured with the same probe.

**Design and controls.** Five builds (InternVL3.5-8B, Phi-3.5-vision-instruct, Qwen3-VL-32B-Instruct, gemma-3-12b, LLaVA-OneVision-7B) × three **fresh service starts** each × two languages (the frozen
Chinese arms and their byte-frozen English renderings) × the three contract arms. Each rate below is
**pooled over the three starts** — every item is one observation per start, and the intervals below are computed as if the 459 item × start records were independent, an i.i.d. reference and **not** a claim about the sampling unit: the **153 images are the unit** and each is measured three times. **We checked the clustering directly rather than assuming its direction**: resampling the three starts as clusters (2,000 draws, seed 20260930) gives intervals that are **narrower**, not wider — the three starts agree to within **2.61 pp** and more than half of the thirty cells are bit-identical across starts — so start clustering does **not** make the pooled intervals too narrow (median cluster width **0.0 pp** against a median Wilson width of **7.16 pp**; **0 of 10** `no_people` cells are wider under clustering), though that check addresses the three service starts alone and does **not** license reading the 153 images as an i.i.d. sample of the image population. A released clustering script reproduces the check from the released records; a cell of the 153-item
strata is replicated across the three starts (459 records) rather than resting on any single start; the spread **between** starts is reported
separately below. Four structural controls
were asserted before any statistic was computed, and all four pass (`ea2_integrity.py`): every row has
$gt = 0$; the three arms of a cell share identical item sets; the three service starts share identical item
sets; and the CN and EN sides share identical item sets.

**Is the outlet used, and used discriminatively?**

| build | pool | `channel` → `no_people` | `channel` → `cannot_judge` | `base` answers `0` |
|---|---|---|---|---|
| InternVL3.5-8B | true zero (z0easy) | **86.9% [83.54, 89.71]** | 8.7% [6.46, 11.65] | 78.0% [73.98, 81.54] |
| InternVL3.5-8B | true zero (z0hard) | **88.9% [85.68, 91.45]** | 4.6% [3.01, 6.89] | 77.8% [73.75, 81.34] |
| InternVL3.5-8B | non-zero (dense) | **1.7% [0.68, 4.40]** | 92.1% [87.92, 94.97] | **0.0% [0.00, 1.65]** |
| InternVL3.5-8B | non-zero (aerial) | **24.6% [19.16, 31.05]** | 38.7% [32.20, 45.61] | 1.0% [0.28, 3.59] |
| Phi-3.5-vision-instruct | true zero (z0easy) | **70.2% [65.81, 74.16]** | 29.8% [25.84, 34.19] | 78.4% [74.44, 81.95] |
| Phi-3.5-vision-instruct | true zero (z0hard) | **86.7% [83.30, 89.51]** | 13.3% [10.49, 16.70] | 81.0% [77.21, 84.37] |
| Phi-3.5-vision-instruct | non-zero (dense) | **0.0% [0.00, 1.65]** | 100.0% [98.35, 100.00] | **0.0% [0.00, 1.65]** |
| Phi-3.5-vision-instruct | non-zero (aerial) | **33.2% [27.00, 39.97]** | 66.8% [60.03, 73.00] | 11.1% [7.41, 16.17] |
| Qwen3-VL-32B-Instruct | true zero (z0easy) | **79.1% [75.13, 82.56]** | 13.1% [10.29, 16.46] | 84.3% [80.70, 87.35] |
| Qwen3-VL-32B-Instruct | true zero (z0hard) | **83.7% [80.00, 86.76]** | 6.8% [4.80, 9.43] | 83.7% [80.00, 86.76] |
| gemma-3-12b | true zero (z0easy) | **47.9% [43.40, 52.50]** | 46.2% [41.68, 50.76] | 52.7% [48.15, 57.25] |
| gemma-3-12b | true zero (z0hard) | **37.5% [33.17, 41.99]** | 52.7% [48.15, 57.25] | 46.2% [41.68, 50.76] |
| gemma-3-12b | non-zero (dense) | **0.0% [0.00, 1.65]** | 100.0% [98.35, 100.00] | **0.0% [0.00, 1.65]** |
| gemma-3-12b | non-zero (aerial) | **0.0% [0.00, 1.89]** | 72.4% [65.77, 78.11] | **0.0% [0.00, 1.89]** |
| LLaVA-OneVision-7B | true zero (z0easy) | **81.0% [77.21, 84.37]** | 19.0% [15.63, 22.79] | 72.5% [68.29, 76.43] |
| LLaVA-OneVision-7B | true zero (z0hard) | **90.2% [87.13, 92.59]** | 7.8% [5.72, 10.67] | 73.9% [69.65, 77.67] |
| LLaVA-OneVision-7B | non-zero (dense) | **0.0% [0.00, 1.65]** | 96.1% [92.70, 97.92] | **0.0% [0.00, 1.65]** |
| LLaVA-OneVision-7B | non-zero (aerial) | **43.7% [37.01, 50.66]** | 42.7% [36.04, 49.66] | 3.5% [1.71, 7.08] |

**Every cell carries a Wilson 95% interval — the zero cells and the non-zero cells alike.** This is the
convention the paper already applies to the hosted endpoints that never answer zero, now applied on both
sides of the contrast rather than only where the count happens to be zero: the non-zero pools have their own
$n$ (153 items × 3 starts = 459 on the true-zero strata; 229 and 199 on the dense and aerial non-zero pools)
and therefore their own sampling error, and quoting `97.1%` bare while quoting `0.0%` with a bound would
imply the two sides were held to different standards. Endpoints are printed to two decimals so that a bound
is never rounded into a bare zero — the upper bound of 0 of 9,180 observations is **0.04%**, not 0. The
intervals reproduce, cell for cell, the `≤1.6%` and `≤1.9%` bounds printed in earlier versions of this table
(0 of 229 and 0 of 199), which is a check that the same ruler is being used throughout.

**The same contrast as a single $2\times2$: outlet × item type.** The table above is read per build and per
stratum; pooling it into the factor the claim is about makes the size of the effect explicit. Counts are
observations, not items — one observation per (build × language × stratum × service start × item), so the
true-zero side rests on $5 \times 2 \times 2 \times 3 \times 153 = 9{,}180$ observations per arm and the
non-zero dense side on 916 (the frozen non-zero pool's own items across four builds; the two sides have
different item sets and different $n$, and no rate below is formed by mixing them):

| arm | pool | observations | `no_people` | `cannot_judge` | `zero` | other |
|---|---|---|---|---|---|---|
| `base` | true zero | 9,180 | **0** (0.0%, [0.00, 0.04]) | **0** (0.0%, [0.00, 0.04]) | **6,808** (74.2%, [73.26, 75.05]) | 2,372 |
| `base` | non-zero (dense) | 916 | **0** (0.0%, [0.00, 0.42]) | **0** (0.0%, [0.00, 0.42]) | **0** (0.0%, [0.00, 0.42]) | 916 |
| `permit` | true zero | 9,180 | **0** (0.0%, [0.00, 0.04]) | **0** (0.0%, [0.00, 0.04]) | **277** (3.0%, [2.69, 3.39]) | 8,903 |
| `permit` | non-zero (dense) | 916 | **0** (0.0%, [0.00, 0.42]) | **0** (0.0%, [0.00, 0.42]) | **0** (0.0%, [0.00, 0.42]) | 916 |
| `channel` | true zero | 9,180 | **6,925** (75.4%, [74.54, 76.31]) | **1,771** (19.3%, [18.50, 20.11]) | **0** (0.0%, [0.00, 0.04]) | 484 |
| `channel` | non-zero (dense) | 916 | **4** (0.4%, [0.17, 1.12]) | **889** (97.1%, [95.75, 97.97]) | **0** (0.0%, [0.00, 0.42]) | 23 |

**Every cell carries a Wilson 95% interval, zero and non-zero alike** — the same rule as the per-build
table above, applied on both sides of the contrast rather than only where the count happens to be zero: the
non-zero pools have their own $n$ (916 observations here, the frozen non-zero pool's own items across four
builds) and their own sampling error, and quoting `97.1%` without an interval while quoting `0.0%` with one
would imply the two sides were held to different standards. Endpoints below 1% are printed to two decimals
so that a bound is never rounded into a bare zero (the upper bound of 0 of 9,180 observations is **0.04%**,
not 0). Cells computed as `other` are reported as counts only, since they aggregate three different outlets.

Two things this table adds. First, the *base* and *permit* arms never use either labelled outlet on either
pool — the two-outlet behaviour is a property of the three-option `channel` contract alone, and the `permit`
route reaches its abstention through a different channel entirely (the residual 8,903 observations are
almost all `abstain`). Second, the `channel` arm's differential use is large in both directions and in
opposite directions: **75.4% vs 0.4%** for `no_people` and **19.3% vs 97.1%** for `cannot_judge`. The
true-zero pool is also **not** unanimous — 1,771 of 9,180 observations call a genuinely empty window
"cannot judge" — which is why §M.38's emptiness-outlet rate is quoted as a **rate on a stated pool** and
not as a rule, and why it is not called a precision: a precision would additionally need that pool's base
rate (see the coverage-versus-precision paragraph of M.21).

*Reproduction: `gen_m40_2x2.py` over `data/derived/ea2/` and `data/derived/e3/nonzero/` (package-relative); frozen
`m40_2x2_result.json`; both are re-derived from those frozen artifacts by `anchor_m40m41.py`.*

The outlets are used **discriminatively**: on verified-empty images the emptiness outlet dominates, while on
images that do contain people the same arm prefers `cannot_judge` — the behavioural content of the
two-outlet identification of Appendix M.21, now measured on independently verified zeros.

**Stability across service starts and languages.**

| build | `no_people` range over the three service starts | CN vs EN `no_people` (z0easy) |
|---|---|---|
| InternVL3.5-8B | 0.0–0.0 pp | 86.9% vs 86.3% |
| Phi-3.5-vision-instruct | 0.0–2.6 pp | 70.2% vs 69.5% |
| Qwen3-VL-32B-Instruct | 0.0–0.0 pp | 79.1% vs 79.7% |
| gemma-3-12b | 0.0–0.7 pp | 47.9% vs 53.8% |
| LLaVA-OneVision-7B | 0.0–0.0 pp | 81.0% vs 81.0% |

**Consistency with the single-start control of Appendix M.38.** On the same pool with one service start,
that appendix reported $\texttt{no\_people}$ on **47–87%** of the easy stratum and **39–90%** of the hard
stratum across its families. With three starts per build and five builds the same quantity, pooled over the
starts, is **47.9–86.9%** (easy) and **37.5–90.2%** (hard): the two independent measurements of the same
pool agree to within **1.5 pp** at their widest endpoint, which we report as the observed run-to-run scale
rather than attributing it to any single cause (the two runs differ in both session and pool order).

Two things follow. First, the **channel composition is service-stable** — its largest spread across the
three fresh starts, over every build, language and pool, is **2.6 pp** (Phi-3.5-vision-instruct cn). That
is a spread of a *share*; the **2.15–6.46 pp** band of §A.3 governs a difference in $\rho$. **These are
different quantities and we do not compare them**: "inside the band" is not evidence here, and the
stability claim rests on the measured **2.6 pp** upper bound alone — repeated serving moves the outlet
composition by at most that much. Second, the channel choice is
**language-invariant** on this pool even though the **rate** of answered zeros is language-sensitive (§5.5):
"which outlet" is stable, "how often" is not, which is why the paper separates the two.

*Reproduction: `ea_build_z0.py` (pool), `20a_probe_truezero.py` / `20b_probe_lang.py` (drivers importing the
frozen probe), analyzers `ea2_analyze.py`, `ea2_contrast.py`, `ea2_integrity.py`; frozen `ea2_z0_result.json`,
`ea2_contrast_result.json`; and `anchor_m40m41.py`, which re-derives the quantities in this appendix — and in
M.41 — from those frozen artifacts, checks the design constants against a frozen inventory of them, and fails
on any number that is not registered.*

#### M.40.1 Four production-process caveats, stated because the intervals above cannot show them

The four uncertainty-producing procedures behind the calibration and ranking figures of §5.14,
§7.3 and §M.37 were re-read at the source for this appendix. Three are **conventions a reader should hold
alongside the printed interval** rather than defects that change a printed value, and one has been
**corrected and recomputed**; they are collected here so that no printed interval is read as covering
contingencies it does not cover.

**(i) The rank convention was not uniform, and is now average-rank throughout.** `m37_ci_power.py` computed
Spearman by mapping each distinct value to its position in `sorted(...)` through a dictionary, so a **tie
took the largest rank**, while `n5_order_prereg.py` (the pre-registered ordering) and `span_equalcount.py`
both take the **average rank** and say so. The two conventions disagree exactly where the readings tie. The
per-unit span readings are rounded to two decimals in the frozen `equalcount36_result.json` and do tie, so
the correction is not cosmetic: under average ranks the same 2,000-draw unit bootstrap returns
**0.834–0.984** on the 36-unit, $k=3$ set and **0.943–0.996** on the 31-unit, $k=4$ set, the point estimates unchanged at 0.933 and 0.983. Both printed intervals were updated in
place and the generator now uses one shared average-rank helper. The clustered interval (0.913–0.994) and
the leave-one-knob-out range (0.883–0.970) come from separate frozen files and are unchanged.

**(ii) The per-domain calibration fold is drawn per unit and then pooled, so "the fold" is not a unit-level
held-out set.** In `n3_deployable_calibration.py` each unit shuffles its own item keys (`rng.shuffle(ks)`,
per unit), each unit's calibration fold is stored separately (`cal[u]`), and the fit is then taken over the
**union** of all units' calibration folds (`pack = lambda lst: [x for u in lst for lb in cal[u] for x in cal[u][lb]]`).
The printed statement that the fold is "item-level and within-unit" is therefore true of how each unit's fold
is *drawn* but not of how the mapping is *fitted*: one image can sit in unit A's calibration fold and unit B's
evaluation fold, and the global mapping sees every unit's fold. The released variant that does hold the fold
out per domain is the `per-domain` caliber row of the same table, which is why its correlation (0.732) sits
below the global rows (0.585 monotone / 0.692 log-count affine). **No printed number is withdrawn** — the table
prints both families — but the phrase should be read as "per-unit fold, globally fitted", and the two rows
should not be compared as if only the fit differed.

**(iii) The 20-image calibration budget draws observations, not unique images.** The same script builds
`allp` by expanding each calibration pool to its **level × item pairs** and then takes
`sub += allp[:min(20, len(allp))]`, so "20 labelled images per configuration" is, in the released code, the
first **20 observation pairs** of the expanded list — a configuration whose items appear at several levels
contributes several rows per image, and the first 20 rows need not be 20 distinct images. The direction of the
bias is toward **less** image diversity than the label claims, i.e. the 20-image budget is an optimistic
reading of the arm, not a conservative one. The arm's printed score (0.732 per-domain) is therefore a **floor
on the penalty** for a genuinely image-deduplicated budget; the arm would not improve if the budget were
deduplicated.

**(iv) The 12-cell family-level interval is a within-cell image resample, and the split-16 certification
selects its groups from the data.** `w1_judge.py (the per-cell row draw)` draws bootstrap rows inside the fixed
(family, domain) cell (`rows = raw[(f,d)]['_rows']`) and does not resample families, domains, or the
shared images that tie families together, so the printed `[0.0831, 0.1002]` on the domain variance component
is a **within-cell image-sampling interval**, not a population interval over untested families; the main text
labels it item-level and draws no population inference from it beyond the fixed panel. In parallel,
`a44_split16.py` sorts the units by `iso` and takes the low group as the first `k` of that ordering
(`lo_group = [r['lab'] for r in U[:k]]`) while `L222` reads the gap at a randomly sampled `k`-subset, so the
**group identity is chosen after seeing the data** and the combinatorial denominator (`C(n,k)`) does not by
itself certify the significance of the reported split — the certification applies to the pre-registered
uniform split, which is the reading the main text gives it. Neither of these two is recomputed here: both
would need the shared-image pairing to be re-derived across the released per-item files, which is a
data-production change rather than a reporting one. They are recorded as **stated calibers** so that the two
intervals are not read as covering the family-level and group-selection contingencies.

### M.41 Sensitivity to image resolution on FSC-147: 256, 384 and 768 pixels

The FSC-147 panel is re-run here at resolutions other than the one used for the main panel (provenance:
Appendix Z). The request has a
factual precondition, which changes what can honestly be delivered.

**The precondition.** The official release of FSC-147 contains the image set `images_384_VarV2`, whose 6,146
files all have a **short side of exactly 384** pixels, with the long side varying between 384 and 1918
according to aspect ratio; on our 300-image sample the short side is 384 throughout and the long side runs
384–1229 (median 514). Inside that package the scale is therefore fixed by the dataset and the canvas is
not. That package is what the dataset README links to and what mirrors redistribute; there is **no**
official original-resolution release. **The file count and the commonly quoted total differ in caliber.** The distributed package holds **6,146**
files, which is the object we sample from and the reason we call it *the* release; the count usually quoted for
FSC-147 is a **de-duplicated** one, lower by the images that appear in more than one split — the reconciliation,
with both figures, is stated once in §M.24. Wherever this appendix states an image count it states the count of
the package as distributed, and the sampling
in §5.13 and §D.3 is from that same package. A request for "the native resolution"
thus asks for something that is not distributed: the scale is a property of **the dataset**, not of our
pipeline. What **can** be varied is the scale handed to the model: **downward** on the short side to 256
pixels, which discards information the release does supply, or **upward** to 768 pixels, the same
information on a larger canvas. Both apply a **single linear scale to every image**, so aspect ratio and
content are preserved: 256 is a $0.667\times$ rescale ($0.444\times$ the area) and 768 a $2\times$ rescale
($4.000\times$ the area), the latter **upsampled** — it measures canvas size, not information content.

**Design.** Three scales measured with one probe family whose copies differ only in the image and output
directories — the prompts and the parser are imported from the same frozen module as the §5.6 panel — on the
same frozen 300-image sample and the same six arms: the four contract arms of the frozen panel plus the two
exemplar arms whose
resolution dependence the limitations section flags as uncontrolled. Three builds were run at all three scales, so every cell below is
a within-item, within-probe comparison.

| build | arm | zero@384 (release) | zero@256 ($0.444\times$ area) | Δ | zero@768up ($4.000\times$ area, upsampled) | Δ |
|---|---|---|---|---|---|---|
| InternVL3.5-8B | `base` | 91.0 | 91.0 | +0.0 | 91.0 | +0.0 |
| InternVL3.5-8B | `permit` | 0.0 | 0.0 | +0.0 | 0.0 | +0.0 |
| InternVL3.5-8B | `channel` | 0.0 | 0.0 | +0.0 | 0.0 | +0.0 |
| InternVL3.5-8B | `enumAbstain` | 0.0 | 0.0 | +0.0 | 0.0 | +0.0 |
| InternVL3.5-8B | `exemplar3` | 0.0 | 0.0 | +0.0 | 0.0 | +0.0 |
| InternVL3.5-8B | `exemplar3permit` | 0.0 | 0.0 | +0.0 | 0.0 | +0.0 |
| Phi-3.5-vision-instruct | `base` | 88.0 | 89.0 | +1.0 | 88.3 | +0.3 |
| Phi-3.5-vision-instruct | `permit` | 0.0 | 0.0 | +0.0 | 0.0 | +0.0 |
| Phi-3.5-vision-instruct | `channel` | 0.0 | 0.0 | +0.0 | 0.0 | +0.0 |
| Phi-3.5-vision-instruct | `enumAbstain` | 6.7 | 6.0 | -0.7 | 6.0 | -0.7 |
| Phi-3.5-vision-instruct | `exemplar3` | 19.3 | 25.7 | +6.4 | 8.3 | -11.0 |
| Phi-3.5-vision-instruct | `exemplar3permit` | 0.0 | 0.0 | +0.0 | 0.0 | +0.0 |
| gemma-3-12b | `base` | 83.0 | 83.3 | +0.3 | 82.7 | -0.3 |
| gemma-3-12b | `permit` | 0.0 | 0.0 | +0.0 | 0.0 | +0.0 |
| gemma-3-12b | `channel` | 0.0 | 0.0 | +0.0 | 0.0 | +0.0 |
| gemma-3-12b | `enumAbstain` | 0.0 | 0.0 | +0.0 | 0.0 | +0.0 |
| gemma-3-12b | `exemplar3` | 0.0 | 0.0 | +0.0 | 0.0 | +0.0 |
| gemma-3-12b | `exemplar3permit` | 0.0 | 0.0 | +0.0 | 0.0 | +0.0 |

| build | arm | abstain@384 | abstain@256 | abstain@768up |
|---|---|---|---|---|
| InternVL3.5-8B | `base` | 0.0 | 0.0 | 0.0 |
| InternVL3.5-8B | `permit` | 94.0 | 94.0 | 94.3 |
| InternVL3.5-8B | `channel` | 0.0 | 0.0 | 0.0 |
| InternVL3.5-8B | `enumAbstain` | 91.7 | 92.7 | 90.7 |
| InternVL3.5-8B | `exemplar3` | 0.0 | 0.0 | 0.0 |
| InternVL3.5-8B | `exemplar3permit` | 17.0 | 27.7 | 21.0 |
| Phi-3.5-vision-instruct | `base` | 0.0 | 0.0 | 0.0 |
| Phi-3.5-vision-instruct | `permit` | 99.7 | 99.7 | 99.7 |
| Phi-3.5-vision-instruct | `channel` | 0.0 | 0.0 | 0.0 |
| Phi-3.5-vision-instruct | `enumAbstain` | 12.7 | 10.7 | 12.0 |
| Phi-3.5-vision-instruct | `exemplar3` | 0.0 | 0.0 | 0.0 |
| Phi-3.5-vision-instruct | `exemplar3permit` | 100.0 | 100.0 | 99.3 |
| gemma-3-12b | `base` | 0.0 | 0.0 | 0.0 |
| gemma-3-12b | `permit` | 91.3 | 91.7 | 91.0 |
| gemma-3-12b | `channel` | 0.0 | 0.0 | 0.0 |
| gemma-3-12b | `enumAbstain` | 81.0 | 82.3 | 81.3 |
| gemma-3-12b | `exemplar3` | 0.0 | 0.0 | 0.0 |
| gemma-3-12b | `exemplar3permit` | 1.0 | 2.7 | 1.3 |

**What the sweep shows.** Across the grid the zero-answer rate moves by at most **17.4 pp** (Phi-3.5-vision-instruct,
`exemplar3`: **25.7%** at the 256-pixel scale against **8.3%** at 768) and the abstention rate by at most **10.7 pp**
(InternVL3.5-8B, `exemplar3permit`: **27.7%** against **17.0%**). The \(\Delta\) columns of the table above are
deviations from the 384 release column, and their largest value is **11.0 pp** for the same cell; the quantity that
bounds movement *across* scales is the span between the extreme scales, not the single-step deviation, and it is
the span that is quoted here.

**Which channel moves.** The split is not uniform: over the four contract arms the largest movement anywhere
in the grid is **2.0 pp** (Phi-3.5-vision-instruct, enumAbstain, the abstention rate), whereas the abstention rate of the
exemplar-permit arm moves by up to **10.7 pp** (InternVL3.5-8B at the 256-pixel scale).
The responses show this is behaviour, not parsing: the model answers the same item numerically at 384
pixels and returns the literal `{"count": "abstain"}` at 256, with no unparsed outputs in either
condition. Halving the linear scale thus makes the model decline when it has been shown exemplar boxes —
a *scale* form of the §5.8 legibility gate, on the hardest arm — while the contract arms move by at most
**2.0 pp**. We report the direction rather than a blanket claim that resolution does not matter.

**Consistency with §5.7.** The contract arms move by no more than **2.0 pp** even at $0.444\times$ the
area — the same sign that section reports for downscaling on the corpus domains, where blur rather than
scale gates abstention (0.6% at 15% of the pixels against 9.1% under blur). The movement we do see is
confined to the exemplar arm, a prompt condition that sweep does not cover: the two results agree, and
what differs is the arm.

**What this null is scoped to.** Three things keep it from being a claim that scale never matters. The
same sweep moves the exemplar arm by up to **10.7 pp**, so the manipulation is not inert; the corpus
census of §5.12 varies a *different* resolution knob — the **per-instance pixel budget**, which there
moves the zero rate by as much as **32.0 pp** — whereas the FSC-147 release fixes that budget and leaves
only the canvas; and that same census finds the *contract* knob moving the zero rate by at least **10 pp**
more than the resolution knob in 10 of its 12 qualifying cells, an order of magnitude above the at-most
**2.0 pp** seen here. That movement also sits below the **2.15–6.46 pp** across-repeat band of §A.3, and
the panel's same-scale replication noise (**≤0.5 pp** in 9 of the 12 cells present) means a shift of a
few points would have stood out against it. The result is therefore a bound on this panel, not an absence
of measurement. **Scope of the panel it bounds:** the 256- and 768-pixel columns were re-measured on **all
nine configurations** of the frozen FSC-147 panel (§M.24) — the three that also carry the full six arms
measured here, and the remaining six on the `base`/`permit` pair, which extends the *contract* reading to
those builds. The **same-resolution 384-pixel** column was re-measured only on those three, so the
across-repeat replication below is scoped to them; the other six keep their published 384-pixel columns
unchanged.

Arm ordering is preserved at all three scales and no arm changes which side of zero it falls on, so the
contract contrast of §5.6 is reproduced by both variants.

**A same-resolution replication, and the one arm that does not reproduce — resolved by a controlled re-run.**
Because the 384-pixel column was re-measured here with the same prompts and images, it also tests whether the
panel of §5.6 reproduces under a fresh batch and fresh service starts. **9 of the 12** cells present
in both agree to within **0.5 pp**; the largest disagreement is **36.0 pp** (Phi-3.5-vision-instruct, `enumAbstain`, the abstain rate: 12.7%
here against 48.7% in the published panel). Two explanations were live and the numbers above cannot separate
them: the **serving context limit** (the frozen panel was served at **4096** tokens and this sweep at
**8192**, every other setting identical — temperature 0, 128 output tokens, one image per prompt, 24
sequences, same prompt module, same 300 images) or **run-to-run noise**. To separate them we re-ran the
identical condition under **both limits, three fresh service starts
each**, over the same four arms, on the same 300 images with the same probe module (18 service starts, **21,600** calls; `ctxctrl_run.sh`, probe derived from the frozen 384 driver with the output directory as its
only change):

* **Phi-3.5-vision-instruct, `enumAbstain`:** **48.8%** at 4096 (three starts: 48.7 / 48.7 / 49.0, range
  **0.3 pp**) against **12.4%** at 8192 (12.7 / 12.3 / 12.3, range **0.4 pp**) — a **36.4 pp** gap against a
  within-configuration spread of **≤0.4 pp**, i.e. a factor of **91**.
* **The remaining ten cells move by ≤0.2 pp** between the limits; the only other mover is the *same* build's
  `permit` arm (**+4.6 pp**, 95.1% → 99.7%). The effect is therefore **build-specific** — the smallest build
  under test — rather than a general property of the context limit.
* **Both historical panels are reproduced cell for cell.** Same-context differences against the frozen 4096
  panel and against this sweep's own 8192 column are **≤0.3 pp in all 24 comparisons** (largest 0.27 pp),
  which is the check that the re-run measured the same thing the two original batches did.

The disagreement is therefore a property of the **serving stack — and of that build** — not of the images or
the prompts. This is why the deltas above are computed against the **in-sweep** 384 column, and it reinforces
§5.7 with a sharper reading than before: **an answered zero is a property of the serving configuration, and
a context-limit change can move one rate by tens of points while leaving ten of twelve cells untouched.**

*Reproduction: `fsc_res_analyze.py` (analyzer, raw-match caliber), `fsc_res_qc.py` (per-cell completeness and
parse-rate guard), `fsc_build_sc.py` (the 256/768 rebuilds; one linear scale per image, source and target
sizes logged), drivers `w1_fsc_probe_{384,256,768}.py` importing the frozen probe module; frozen
`fsc_res_result.json`. The context control adds `ctxctrl_run.sh` (the 18 starts), `ctxctrl_probe.py`
(byte-derived from `w1_fsc_probe_384.py`, differing only in that the output directory is a parameter),
`ctxctrl_analyze.py` (summary) and `_ctxctrl_indep_check.py` (the **independent** recomputation, which reads
the raw per-item CSVs, re-implements the raw-match classification and reproduces the frozen
`ctxctrl_result.json` cell by cell: **80 checks, 0 failures**). The frozen 384-pixel panel of §5.6 is itself
retained unchanged as the cross-check, and `anchor_m40m41.py` re-derives the quantities in this appendix —
and in M.40 — from the frozen artifacts, checks the design constants against a frozen inventory of them, and
fails on any number that is not registered.*

---

### M.42 The matched-travel pixel-budget ladder: the span follows travel only approximately

The ordering of §7.3 compares spans across knobs whose **travel** — the ratio between the loosest and the
tightest admitted level — differs from knob to knob. Appendix F.10 normalises each span by its knob's
relative travel and the ordering survives, which leaves the alternative explanation *weakened but not
excluded* (provenance: Appendix Z). A reviewer asked for the direct test rather than the normalisation:
re-run one knob on levels whose relative travel is **matched** to another knob's, and watch whether the
span follows the travel. Levels, comparison and criteria were fixed before the first call, and the runner
asserted the frozen file's digest at start-up.

**Design.** The knob is the VLM pixel budget, re-run on **8 geometric levels** whose endpoints are
**10.000×** apart — the travel of the in-domain detector ladder (threshold 0.05 to 0.50) — over the
**400** VisDrone images that the published pixel-budget row already used, with the paper's frozen counting
prompt and **three repeats in one serving session**: 9,600 calls. The published row is a 4-bit build and
the one used here is not, so the **primary comparison is made inside this run** (same session, same build,
same prompt) against the nested sub-arm whose travel, **5.180×**, is the closest within-run match to the
published non-zero travel of 5.242×; the published arms appear only as a declared cross-build aside.

| budget | ρ repeat 1 | repeat 2 | repeat 3 |
|---|---|---|---|
| 1,048,576 | −70.25 | −69.07 | −69.08 |
| 754,655 | −71.23 | −71.25 | −71.24 |
| 543,118 | −73.39 | −73.39 | −73.39 |
| 390,867 | −76.09 | −76.09 | −76.09 |
| 281,300 | −78.27 | −78.27 | −78.27 |
| 202,447 | −82.64 | −82.64 | −82.64 |
| 145,698 | −85.27 | −85.27 | −85.27 |
| 104,856 | −87.88 | −87.88 | −87.88 |

**C1 — does the span scale with travel? The pre-registered ratio is missed, and we report it as a miss.**
The full ladder spans **18.42 pp**; the nested 5.180× sub-arm spans **13.17 pp**, so **R = 1.399** against
a proportional expectation of **1.931** (0.724 of it), **below the pre-registered band 1.5–2.4**. Taken
over the whole range, however, the span-vs-travel curve rises monotonically at all seven steps and its
log–log slope is **1.140**; the ratio of span to travel is not constant (1.276 at *k* = 2, 2.543 at
*k* = 6, 1.842 at *k* = 8). The reading fixed in advance for this outcome is the one we adopt: the span
does **not** amplify in proportion to travel at that cut, so "the span is simply a function of travel" is
**weakened and not supported**, and the travel normalisation of Appendix F.10 is on the **conservative**
side. We do not upgrade any statement to "excluded" on the strength of it.

**C2 — at matched travel the two knobs are still an order of magnitude apart.** On the same 10.000×
travel the in-domain detector ladder spans **195.69 pp** at the finest input size (159.28 and 95.85 pp at
the other two), against **18.42 pp** for the pixel budget: after normalising both by travel the ratio is
**0.094** (0.116 and 0.192), outside the pre-registered comparability band [0.5, 2], and the ordering of
the two knobs does **not** flip. Matching travel therefore does not make two knobs comparable — which is
the opposite of what the alternative explanation needs, and is the reason the §7.3 ordering is not an
artefact of unequal travel.

**C3 — noise floor.** Item-level agreement across the three repeats is **3,190/3,200 = 99.69%**; the
per-repeat full-ladder spans are 17.64, 18.81 and 18.80 pp, a range of **1.17 pp = 6.37%** of the mean,
inside the pre-registered 20%.

*Reproduction: the frozen criteria, the runner and the per-item records of all 9,600 calls are released;
the analyser recomputes every number above and writes them to a frozen result file.*

### M.43 The value named in an instruction, and a pre-registered equal-level rescan

Two review requests share one question: is the §7.3 span, or its ordering, a property of the *levels* we
happened to choose? §M.19.13 had shown that the median answer tracks the value named in the instruction
(ρ = +1.00), which raises the possibility that some of the span is that naming and not the knob. And the
ordering evidence had never been re-run on an **independently pre-registered, equal-level** set, which is
the design precondition a reviewer said was missing. Both were run on the same 182-image dense pool, in
one serving session, with the criteria frozen first.

**The anchor audit, and what "neutralised" can mean.** Scanning the six knobs' instructions for digits
used as a named answer value leaves exactly **two** arms: the one that says "do not answer 0" (names `0`)
and the six-option arm (names `0, 10, 50, 100, 500, 1000`). The other two arms of that knob name no
value. We therefore re-ran the knob with those two arms **neutralised** — the named value removed from
the instruction and the behavioural instruction kept in words without digits — alongside the four arms
unchanged.

| arm | ρ | median answer |
|---|---|---|
| `base` (names nothing) | −54.38 | 100 |
| names `0`, prohibits it | +107.13 | 300 |
| interval arm (names nothing) | **+245.07** | 500 |
| six-option menu | +72.01 | 1000 |
| **span of the four** | **299.45 pp** | |

| neutralised arm | ρ | median answer |
|---|---|---|
| prohibition without the digit | +327.40 | 500 |
| menu removed | **+1391.67** | **5000** |
| **span of the four** | **1446.05 pp** | |

**The criterion is missed, and in the direction opposite to the objection.** Δ = **+1146.60 pp**, i.e.
**+382.9%** of the present span, against a pre-registered tolerance of 30%: removing the named value does
not shrink the span, it **enlarges** it, by lifting the answers (medians 100/300/500 rise to 500/5000).

**The cleaner test, which needs no paraphrase.** Removing the two naming arms **entirely**, with no
replacement, leaves the span at **299.45 pp — unchanged to the digit**. The reason is visible in the
table: the span's two endpoints are the **interval arm** (+245.07) and `base` (−54.38), neither of which
names a value. The two arms that do name one are interior points, so their contribution to the span is
**exactly zero**. The alternative explanation that the span is carried by the named value is therefore
not merely weakened here; on this pool it is **contradicted**, and we state the one confound we cannot
remove: for the six-option arm the menu *is* the mechanism, so deleting its digits also deletes the arm's
behaviour — the minimal paraphrase pair (prohibition with and without the digit) also rises, 107 → 327.

**A pre-registered equal-level rescan of the four VLM knobs.** Each of the four knobs that this machine
can drive was given **five levels fixed in advance**, on the same 182 images: the output contract (5
arms), the prompt family (5 wordings), the tiling grid (1, 2, 3, 4, 6) and the pixel budget
(1,048,576 → 50,000). The detector and density-regression knobs are the two the design's own six-knob list also contains. Both have
since been driven **on the same 182 images with their weights in hand**, and on this pool **neither seats**; we
report what they read rather than a proxy. The **detector** knob was run as a zero-shot COCO detector (yolo11n,
whole image — the dense-end instrument of Appendix D.1) over five input sizes fixed in advance (640/896/1024/1280/
1536 short side) with the confidence threshold held at 0.25. Its pooled deviation runs **−97.6 / −96.3 / −94.4 /
−99.0 / −98.1%**, a span of **4.6 pp**. That is a **floor effect**, not a small knob: at these densities a
zero-shot detector recovers 1–6% of the annotated count at every level, so the reading is pinned and its span
measures the floor; a 65-cell (threshold × size) grid agrees, its least severe cell reading **−74.4%**
(τ = 0.05, 1536). The **density-regression** knob was run with the **official DM-Count weight for this domain**
at the five multipliers fixed in advance (0.5 → 1.5): **−15.4 / −3.0 / −1.7 / −7.9 / −13.5%**, a span of
**13.7 pp**. That is *below* the **20.1–34.3 pp** this appendix prints for the knob, but the two are different
calibers — F.9's density row is isotonic-calibrated per (knob × domain) unit while this reading is uncalibrated
and pooled — so it is not read as a contradiction. The same ruler run instead on **CSRNet/st_a** gives
**−67.1 / −6.9 / +103.8 / +301.9 / +601.9%**, a span of **669 pp** and the **opposite sign** from the 1.0 level
on. **The density knob's response is therefore a property of the knob *and* the model, not of the knob alone** —
which is exactly the separation Appendix D.1 already imposes when it requires official and reproduction weights
to be reported separately. Neither row is folded into the ordering above: one is at the floor and the other
changes sign with the model, so the ordering statement stays the narrower one this section already makes. Both
readings come from a **different session** than the four rows above, so the 3.01 pp same-session floor does not
apply to them; both per-item ladders and the instrument are released
(`data/derived/p2e_a800/`).

| knob | span, this run | levels (ρ) |
|---|---|---|
| output contract | **343.55 pp** | −54.4 / +72.0 / +107.1 / −98.5 / +245.1 |
| prompt family | **1561.94 pp** | −53.8 / +1491.2 / −70.8 / +406.3 / +365.9 |
| tiling | **14.56 pp** | −51.5 / −55.2 / −47.1 / −44.5 / −40.6 |
| pixel budget | **31.65 pp** | −54.0 / −55.5 / −74.2 / −77.2 / −85.6 |

**Three pre-registered verdicts, one pass and two misses.** (a) The ordering of the four knobs is **not**
identical to the published one: this run ascending gives tiling < pixel budget < contract < prompt
family, the published per-unit medians give pixel budget < tiling < contract < prompt family, a Spearman
of **0.800** — the **two smallest knobs swap**. Restricting the published ladders to the *same* pool
(q32: 4.0 < 33.3 < 355.3 < 424.6; the other build: 1.0 < 33.3 < 204.6 < 660.1) gives the same picture,
so the swap is not an artefact of mixing pools. (b) The **top** of the ordering is unchanged —
the prompt family is the largest-response knob in all three sources; the contract knob's span
(**343.5 pp**) reproduces the published value for one build (**355.3 pp**) to **3%** across builds and
service starts. (c) Normalising each span by its knob's relative travel, which is definable only for the
two numeric knobs, **keeps their order** rather than flipping it: tiling 14.56 < pixel budget 31.65 raw, and 0.404 against 1.509 per unit of travel.

**Noise, and why the swap is not noise.** Three same-session repeats of one arm agree item-by-item on
**170/182 = 93.41%** of items and move that arm's ρ by **3.01 pp**. The two swapped knobs span 14.6 and
31.7 pp, i.e. **4.8× and 10.5×** that floor, so the swap is a property of the **level sets**, which differ
between the two designs (the published pixel-budget ladder admits the native level and stops at 200,000;
this one stops at 50,000; the published tiling ladder is whole/2×2…6×6, this one 1/2/3/4/6). The honest
statement is narrower than "the ordering replicates": **the top of the ordering replicates; the bottom two
knobs are level-set-dependent, and their ordering is not portable between level sets.**

**Two further domains were tried, and neither seats this knob.** The same pre-registered form — levels fixed in
advance, three fresh service starts, the pooled relative deviation and the span it defines — was run on **MTDC**
(maize tassels) and **GWHD** (wheat heads), two counting domains this ordering evidence had not used, at the
**eleven** input-scale levels that are the union of this section's eight matched-travel multipliers with the four
public labels of the released control ladders (the native label absorbs the duplicate), 250 sampled items per
domain per start, 16{,}500 calls in all. **The readings are degenerate**: the model answers **0** on **248–250 of
the 250 items at every level of both domains** (all 250 in **6 of the 22** domain-by-level cells, 249 of 250 in
the other 16), so the pooled deviation lies between **−100.00%** and **−99.98%** at every level and the span is
**0.02 pp (MTDC)** and **0.01 pp (GWHD)** — far outside the
**7.04–28.15 pp** band this section's own extension test allows. This is the **same failure mode as the detector
knob above**: on these two domains the answered-zero channel is saturated, so an input-scale knob has nothing to
move and the span measures the floor rather than the knob. **One confound belongs with that reading.** The probe
reuses this instrument's frozen prompt **verbatim**, and that prompt asks for the number of **people**, so no noun
is substituted here; on maize tassels and wheat heads the instruction is therefore itself mismatched to the
domain, and part of the answered-zero rate is instruction-appropriate rather than a model failure. §M.49 puts
**the same two domains to a noun-substituted instrument** and discloses that substitution; that is the instrument
which could actually seat this knob here, so a noun-substituted re-run at these eleven levels is the experiment
this null reading calls for — and until it is run we report the two domains as **not seating the knob** rather than
as a counterexample to the ordering, and record it as one more instance of the domain dominance this paper reports.
Comparability here is limited to *same instrument, same model, same geometry*: the
new levels only coincide with the released ladders' own five on four labels, so no same-grid claim is made, and
these readings are not from the same session as the four rows above (that section's 3.01 pp same-session floor
does not apply to them).

**The noun-substituted re-run, and what it changes.** The confound above was tested directly: the same eleven levels, the
same 250 sampled items per domain per start, three fresh service starts, **16,500 calls**, with **only the object noun phrase
substituted** — and a probe assertion that this substitution is the **only** difference (the rule §M.49 already uses). **The
answered-zero column does not survive it**: the number of domain-by-level cells in which all 250 items answer zero falls from
**6 of 22** to **0 of 22**, and the first cell's deviation moves from **−99.98%** to **−14.77%**. The two domains then behave
**differently**, and neither is the degenerate floor the original reading showed: **GWHD falls inside this section's own
extension band** (**26.30 pp**, band 7.04–28.15) while **MTDC overshoots it** (**57.36 pp**). Every one of the eleven paired
level differences is positive (medians **+62.46 pp** and **+39.09 pp**), so the substituted instrument counts far more than the
person-worded one. The honest reading is therefore the composite one: **on these two domains the knob does not seat under
either wording** — but **not for the same reason in the two cases**. The original reading is a floor produced by asking for
*people*; the substituted reading is a real response, excessive in one domain. Neither is a counterexample to the ordering
above, and no printed value changes. The re-run's own criteria, probe, per-cell records (66 files) and verdict are released
as `data/derived/p1n_a800/`.

*Reproduction: the frozen criteria (with all twelve instructions verbatim), the runner, the four per-item
record files — released as `data/derived/g56_res/g56_{arms,tile,budget,noise}.csv` — and the analyser are
released; the analyser recomputes both the within-run spans and the same-pool published spans from the released
per-item records. The eleven-level rescan's own criteria, runner, analyser, per-cell records (66 files) and
smoke/pilot controls are released as `data/derived/p1d_a800/`, so every number quoted in the paragraph above is
recomputable from the package; the density cross-check's own per-item ladder, from which the CSRNet row above is
computed, is released as `data/derived/p2e_a800/csrsta_ladder_st_a.csv`.*

### M.44 Recovering a known mixture proportion: an identity, its resolution, and the transfer that fails

Four reviewers asked for the experiment that would close the precision loop: mix the verified true-zero
windows of §M.38 with verified non-empty dense images in a **known** proportion, so that the true
proportion is known by construction, and check whether it is recovered. The request assumed new calls and
new annotation. Neither is needed, and the reason changes what the result can mean.

**The mixture is a weighted union of records already in hand.** Both sides of the mixture were measured
per item, per build, per service start and per language: **306** verified empty windows (windows over
UCF-QNRF whose expanded box contains no annotated head point, hence a correct answer of zero) and
**229** verified non-empty dense images (79 + 150, ground truth at least 66). Each item is an independent
call, so the mixture's answered-zero rate is the **weighted average** of the two rates, and the recovery
is computable offline, with no new call and no new label. The pool is used in full — **π_true =
306/(306+229) = 0.5719626** — with no sampling and no seed; four builds have both sides and are reported,
while the fifth has no non-empty pool and is listed as not covered.

**The criterion is met exactly, and that is why it is not evidence — stated before the numbers were
computed.** With â and b̂ the answered-zero rates on the empty and non-empty sides, the mixture's rate is
π·â + (1−π)·b̂ by construction, so the recovered π̂ = (z_obs − b̂)/(â − b̂) equals π_true **identically**.
It does: across all 24 (build × start × language) cells the difference is **zero to machine precision**
(≤ 1.1 × 10⁻¹⁴ pp). The frozen criteria file says in advance that this cell cannot fail and must not be
read as validation.

**What the design can and cannot resolve.** Propagating the mixture's own binomial interval gives a 95%
half-width on π̂ of **10.2 to 16.4 pp**, wider than the **7 pp** tolerance the request specifies in
**24 of 24** cells. Even with no systematic bias whatever, this design at n = 535 cannot resolve the
criterion it was given — reaching the 7 pp tolerance would take roughly **1,140–2,940** items, since the half-width scales as $n^{-1/2}$ (from the 10.2 and 16.4 pp half-widths at n = 535).

**The transfer test, which can fail, and does.** The failure mode the request names — "if p does not
transfer across domains the error reaches 54.7 pp" — is a **transfer** property, so we ran it as one:
fit (â, b̂) on build A, apply to build B's own mixture. Over the **72** ordered pairs the error has median
**10.80 pp** and maximum **35.23 pp**, and **40 of 72 (55.6%)** exceed the 7 pp tolerance. The structure
is systematic rather than scattered: on one service start, transfers **into** the smallest-response build
cost 18.6–35.2 pp while transfers among the three larger-response builds cost 1.4–5.1 pp. The same
quantity across the two prompt languages, within a build and service start, ranges from **−4.45 to
+8.71 pp**. This is the "p is not portable" statement of §8.2, now quantified on a mixture whose true
proportion is known rather than assumed.

**One negative result worth recording.** The estimator is undefined, not zero and not missing, for the two
abstention arms: on both sides of the mixture their answered-zero rate is **exactly 0** in all 24 cells —
they reach their abstention through the abstain, `no_people` and `cannot_judge` outlets — so â − b̂ = 0
and no proportion can be recovered from them. The precision loop therefore cannot be closed with the
channel arms either; what this appendix closes is the *estimator's* behaviour, not the paper's π.

*Reproduction: the frozen criteria, the analyser, and the released per-item records of both pools; every
rate, interval and transfer error above is recomputed from those records by the analyser.*

### M.45 The ordering under pre-registered statistics, and under a common error budget

Two requests press the §7.3 ordering from two sides: is it an artefact of *which* levels were compared, and
of *how much damage* each knob's extreme level is allowed to do? Both are answered from records that are
already published — no new calls, no new annotation — and both designs were frozen before any statistic was
computed.

**Common ground, and a gate that has to pass first.** Both analyses use the same 36-unit construction as
Appendix M.37, copied from the artefact that builds it, and both begin with a **replication gate**: the span
of every one of the 36 units must reproduce the frozen value to a relative error below $10^{-9}$ before
anything else runs. It does, **36 of 36** — so what follows is computed on the same units as M.37, not on a
reconstruction of them (the frozen spans are released, so this gate covers all **36** units; **two** of the 36
per-item counterparts, for the BBBC005 and DM-Count units, are held by the authors, §M.37, and are therefore
not rebuildable from this package).

**(a) A pre-registered ordering test on an independently chosen level set.** The published ordering ranks
units by their span over each ladder's **full** level set. The re-check restricts every unit to an **equal
number of levels chosen by a rule fixed in advance that looks only at the level count $\ell$**: $k = 3$
levels at ranks $\{0,\ \lfloor(\ell-1)/2\rfloor,\ \ell-1\}$, and, as a second variant, $k = 4$ at evenly
spaced ranks. Three is the smallest level count the eligibility rule admits, so the first variant is the
most aggressive admissible restriction; both variants keep the extremes, so this is a different deflation
from the "drop the extreme level" rule M.37 already reported. The companion statistics were named in
advance: a **per-unit item bootstrap** of **2,000** replicates (items resampled with replacement *within* a
unit, the same resampled indices used at every level, so the pairing and the common intersection are
preserved), percentile 95% intervals, and a **5,000-draw label-permutation** test with **Holm** correction
over the two variants.

| variant | Spearman vs. the published ordering | bootstrap 95% CI | corrected $p$ | verdict |
|---|---|---|---|---|
| $k=3$ levels | **0.9353** | **[0.9009, 0.9544]** | **0.0004** | **pass** |
| $k=4$ levels | **0.9330** | **[0.8994, 0.9544]** | **0.0004** | **pass** |

The pre-registered bar was Spearman $\ge 0.90$ **and** interval lower bound $\ge 0.80$ **and** corrected
$p \le 0.01$; both variants clear all three, and **no unit's span degenerates** under the restriction. The
companion calibrations were reported in the same table as required: under a **shared** affine map the
ordering is preserved **exactly** at $1.0000$, which is Proposition 5 again, and under a **per-unit** affine
map it falls to **0.5292** — the failure this paper already discloses in M.37 and §7.3.

**(b) The same ordering under a common error and cost budget.** The published ordering compares each knob
at its own extreme, and those extremes are not equally affordable. The second analysis therefore asks what
survives when every knob is held to the **same budget**: a pair of a unit's levels may be compared only if
their mean absolute errors are within a pre-registered factor $1+B$ of each other **and** their inference
costs are within a pre-registered factor $C$. Cost is a declared proxy (pixels for the pixel budget, calls
for tiling, squared input size for the detector ladders, the scale parameter for the density ladders); the
two knobs with **no cost dimension at all** — the output contract and the prompt family — are excluded
rather than assigned a fictitious cost, leaving 28 of the 36 units.

| $(B, C)$ | units that admit any pair | Spearman vs. the published ordering | top knob | median span retained |
|---|---|---|---|---|
| $(0.10, 2.0)$ — pre-registered | **14 of 28** | **0.7674** | **changes** | 0.477 |
| $(0.25, 4.0)$ — pre-registered | **20 of 28** | **0.8227** | **changes** | 0.582 |

**The criterion is missed, and we report it as missed.** Under a common budget the ordering is not
preserved and the largest-response knob changes: the full-level ordering puts the in-domain density
regression on top, the budget-matched ordering puts the in-domain detector ladder there. A post-hoc
diagnostic — labelled as post-hoc, because it is not in the frozen criteria — separates the two constraints:
releasing the error budget and keeping only the cost ceiling $(C = 2)$ leaves the ordering at **0.9275** with
the top knob **unchanged** and a median span retention of **1.000**, whereas releasing the cost ceiling and
keeping only the error budget $(B = 0.10)$ gives **0.8292** and a retention of **0.477**. **The error budget,
not the cost ceiling, is the binding constraint.** One number states the mechanism most plainly: the six
**pixel-budget** units admit **no admissible pair at all** at $B = 0.10$ — that knob cannot be moved within
a 10% error budget, so every span it contributes to the published ordering is bought with accuracy.

**What this changes, stated narrowly.** Part (a) strengthens the ordering claim against the specific
objection that it depends on the number of levels compared: on an independently chosen, equally sized,
deliberately unfavourable level set, it holds with intervals and a corrected $p$. Part (b) bounds it: the
ordering is **not** invariant to giving every knob the same error budget, and about half the units cannot be
compared at all under one. The accurate form of the §7.3 claim is therefore that the ordering is a property
of the **level sets compared** — preserved under level-count restriction, and preserved under shared
calibration, but **not** under error-budget matching — and the paper is amended to say so rather than to
claim the ordering in general.

*Reproduction: all of the parts above are released under `code/analysis/`. Part (a) is produced by
`span_equalcount.py` and `span_equalcount2.py`, with `equalcount36_result.json` as their frozen output. Part
(b) — the budget-matched ordering and its two post-hoc diagnostics — is produced by `n6_budget_matched.py`,
which imports the shared unit construction from `n5_order_prereg.py` (itself a verbatim copy of the builder in
`a39_unit_calib_heldout.py`), asserts its frozen criteria `n6_criteria_frozen.json` — generated by
`make_n6_criteria.py` and holding the pre-registered cost proxy — and writes `n6_result.json`. Both parts
rebuild the 36 units from the per-item records — **34** of the 36 counterparts are released; the two for the
BBBC005 and DM-Count units are held by the authors (§M.37) — and assert the frozen spans before computing
anything else.*

unit `u` **has a non-degenerate span** at budget `(B,C)` ⇔ `B ≥ min B*_{ij}` over pairs inside `L_u`; its span **reaches the full-level span** ⇔ `B ≥ max B*_{ij}` over the same pairs;
hence "the budget-matched ordering agrees with the published ordering on **all decisive pairs** ⇔ `B ≥ max B*`" (`max` over every decisive pair).

**Two qualifications on that equivalence, both constructive.** **(i) The right-hand branch must be read
as an existence statement over cost-feasible budget pairs, not as a universal one.** If the budget-matched
span is *defined* as the largest span realised by any pair the budget admits, then reaching the full-level
span needs only that *some* feasible pair attains the extremes, and `max B*` over **every** decisive pair is
stronger than necessary. Take two units with GT 100 and level predictions (110, 90), (205, 5), (121, 99):
the pooled ratios are 0/200, 10/200, 20/200 = 0 / 5 / 10 pp at MAE (10+10)/2, (105+95)/2, (21+1)/2 =
**10 / 100 / 11**. A budget of `B = 0.10` already makes levels 1 and 3 comparable (11/10 = 1.10 ≤ 1 + 0.10)
and therefore delivers the **full 10 pp span**, whereas `B ≥ max B*` over all three pairs requires
100/10 = 10, i.e. `B = 9`. The equivalence is therefore stated on the **cost-feasible** pair set, and the
cost constraint `C` is part of the definition rather than a side condition. **(ii) `G_N/G` is defined once,
in §M.21.1**, as the share of answered zeros among all emitted outputs (item-denominated); §3.8's $w$ is the
**ground-truth-weighted** answered share, and Table 2's coverage is the answered-zero channel's share of
abstentions. The three are written with distinct symbols in §M.21.1 and are not interchangeable.

### M.46 The recipe run on two corpora this paper never used, and the four English headline cells on one build

Both halves of this appendix answer a request of the form *"run your own protocol on material you have not
touched"*. Both corpora and both of the two additional families **do appear elsewhere in this paper** — which is why they were chosen — but the **residual of this recipe has never been reported on or for any of them**, and everything was fixed in advance: the item sets, the arms, the families and the criteria.

**(a) Two new corpora, two new families, 7,200 calls.** The claim under test is the transferable half of
§M.22's recipe — that the **contract gate** (the fraction of the `base` arm's answered zeros that a
`permit` arm still answers as zero) reproduces outside this paper's stack. Two corpora on which the recipe's residual has **never been reported** were obtained from public mirrors and used as released, with **no new annotation**: **JHU-Crowd++** (a fixed 300-image subsample of the release's **1,600-image test split**; ground truth from the release's own per-image count file) and **TallyQA-short** (a
non-FSC-147 visual-question-answering counting benchmark; 300 items with numeric answers). Four families
were run, **two of which have no previously reported residual** — Qwen2.5-VL-3B and Qwen3-VL-4B — alongside the
anchor build and one previously measured family as controls, over the three contract arms, 2 domains × 300
items × 3 arms × 4 families.

| family | JHU-Crowd++ | TallyQA-short | pooled | verdict |
|---|---|---|---|---|
| Qwen2.5-VL-3B-Instruct (**new**) | 0/2 = 0.00% *(95% upper bound 65.8%)* | 0/11 = 0.00% *(95% upper bound 25.9%)* | **0.00%** | pass |
| Qwen3-VL-4B-Instruct (**new**) | 0/24 = 0.00% *(95% upper bound 13.8%)* | 1/25 = 4.00% *(95% upper bound 19.5%)* | **2.04%** | pass |
| Qwen3-VL-32B-Instruct (anchor) | 0/70 = 0.00% *(95% upper bound 5.2%)* | 3/14 = **21.43%** *(95% upper bound 47.6%)* | **3.57%** | pass |
| InternVL3.5-8B (control) | 0/6 = 0.00% *(95% upper bound 39.0%)* | 0/8 = 0.00% *(95% upper bound 32.4%)* | **0.00%** | pass |

**Read the counts as well as the rates.** Several cells rest on 2–25 items, so their 95% upper bounds are wide (0 of 2 → up to 65.8%, 0 of 11 → up to 25.9%) and they are direction readings. **The interval family is named, because two are in use in this paper and they are not interchangeable:** the bound printed in the table above — and here — is the **Wilson two-sided 95% upper endpoint**, which is also the family the paper's Table 4 labels `(Wilson)`; the **Clopper–Pearson** single-sided limit on the same 0-of-2 cell is **77.6%**. Both are above the 5% residual, so the verdict does not turn on the choice, but the label must carry the family it was computed under. With that caveat, **all four families are inside the 5% residual** on the point estimate — which is what the pre-registered `pass` field is defined on, as §M.49 states — so the recipe's gate transfers to corpora and to families
this paper never touched. One cell is above the bar and is reported rather than pooled away: the anchor
build on TallyQA leaves **3 of 14** answered zeros (21.43%). The channel composition on the same runs shows
the outlets being used rather than ignored — numbers 35–52%, `cannot_judge` 46–64%, `no_people` 0.3–2.0%,
`abstain` 0.0%.

**Two conventions are declared rather than silently chosen.** TallyQA is a question-answering benchmark
whose questions differ from item to item, so the three arms were re-bound to the question with the
**contract-bearing clause kept byte-identical** and only the people-specific noun phrase removed; the
domain therefore runs in English while JHU-Crowd++ runs in Chinese, and that language difference is part of
the domain difference, not a factor under test. And the frozen parser records InternVL's output as
unparsable in **634 of 1,800** rows while the raw-text convention of §8.1 parses all of them — the two
numbers are the two conventions, and both are reported.

**The per-item records of this half are in the released tree, and the table above recomputes from them.**
All four families' `base` / `permit` / `channel` rows — 4 files, **1,800 data rows each, 7,200 rows in
total** — are released as `data/derived/g3_res/g3_<family>.csv`, carry a `family,domain,item,arm,gt,pred,
parse_ok,abstain,http_err,raw` header, and appear in `MANIFEST.csv`. The arithmetic of the table is two
counts per family: the **base zero count** (rows whose `base` arm answers the numerical `0`, i.e. `pred = '0'`)
and the **permit residual** (the subset of those items whose `permit` arm also answers `0`), each summed over the two domains, with the pooled rate the ratio of the two sums. Recomputed
from the released files: base zeros **13 / 49 / 84 / 14** for Qwen2.5-VL-3B, Qwen3-VL-4B, Qwen3-VL-32B and
InternVL3.5-8B (**160** in total, the figure §M.46(a) prints as the "eight" cells' original zeros), permit
residuals **0 / 1 / 3 / 0**, giving **0.00% / 2.04% / 3.57% / 0.00%** pooled and **0.00% / 4.00% /
21.43% / 0.00%** on TallyQA-short — the rates printed in the table above, cell for cell. *Entry point for
that recomputation (three lines, no repository state needed beyond the file):*
`python -c "import csv,collections as C; r=list(csv.DictReader(open('data/derived/g3_res/g3_Qwen3-VL-4B-Instruct.csv',encoding='utf-8-sig'))); z=lambda x:(x['pred'] or '').strip()=='0'; b={(x['domain'],x['item']) for x in r if x['arm']=='base' and z(x)}; p={(x['domain'],x['item']) for x in r if x['arm']=='permit' and z(x)}; print(len(b),len(b&p))"`
— it prints `49 1` for that family, i.e. the `1/25 = 4.00%` TallyQA-short cell and its `0/24` JHU-Crowd++
companion. The four files are the analysers' own inputs, not a re-derivation: the runners are
`code/analysis/g3_run.py` and `g3_res_matched.py`, and no aggregation script sits between them and the
table.

**(b) The four English headline cells, finally on one build.** §5.5's language scoping was measured on four
domains, but the four English cells came from a different weight build and one of them — UCF-QNRF — was
unmeasurable because its vision tokens exceeded the serving context. Re-run at a context of 16,384 tokens
**all 334 items return and none hits the limit** (0 of 334), so the cell is measurable and the "203 of 334
HTTP 400" of §M.39 is an infrastructure limit that a larger context removes. The three remaining cells were
then re-run on the **same build and the same session** so that the four are finally comparable.

| domain | English answered-zero | English ρ (answered) | **English S** | Chinese S |
|---|---|---|---|---|
| ShanghaiTech-A | 9.3% | **+28.05** | **undefined** ($\rho_{\text{total}} \ge 0$) | 0.9237 |
| VisDrone | 65.8% | −30.52 | **0.7961** | 0.7566 |
| AI-TOD | 64.2% | −38.79 | **0.7964** | 0.7871 |
| UCF-QNRF | 11.4% | +18.84 | **3.0778** | 0.8384 |

**The criterion fails, and it fails in two different ways.** Only **two of the four** cells keep $S$ inside
$[0,1]$; UCF-QNRF crosses to **3.08**, and ShanghaiTech-A's share is **undefined** because its net
deviation is an *over*-count ($\rho_{\text{total}} = +11.35$, against $\rho_{\text{answered}} = +28.05$
in the table above). Both failures have the same cause as the one
§M.19.16 already reports for the densest cell: once the answered items stop under-counting on net, the
ratio is no longer a share. The English arm is **not** uniformly the more extreme one: on the two aerial domains the
Chinese and English shares are within 4 pp, while on the dense domains the language moves the answered-zero
rate by **−26.4 pp** (ShanghaiTech-A, 35.7 → 9.3) and **−23.4 pp** (UCF-QNRF, 34.7 → 11.4) in the runs
tabulated above, against **−21.4** and **−18.4 pp** in §M.19.16's separate session on the same build; the
**18–22 pp** of §M.19.16 and the pair above are **not two readings of one band** — they are different
sessions, reported separately, and neither is substituted for the other, and neither is a change of sign.
As before, these four cells are reported as their own build and are
**not** tabulated against the published four-quarter-bit cells.

*Reproduction: the frozen criteria of both runs, the runner, the analysers and the per-item records of all
7,200 + 1,616 calls are released; the two corpora are public mirrors whose digests are recorded in the
frozen criteria.*

#### M.46(c) The four English headline cells on the corpus's **own** build

Part (b) ran them on the BF16 build and declared the deviation: the corpus baseline is a **4-bit
`compressed-tensors` AWQ** checkpoint, so the two were not comparable in absolute terms. That gap is now
closed. The five arms were re-run on **`cyankiwi/Qwen3-VL-32B-Instruct-AWQ-4bit`** (the public artifact the
baseline was served from; commit and per-shard digests frozen in the criteria file; the requantisation itself is an **AWQ INT4** conversion at **group size 32**, symmetric, of **`Qwen/Qwen3-VL-32B-Instruct`**, produced with **`llm-compressor`** and calibrated on **`HuggingFaceM4/FineVision`**, with **117** layers exempt from quantisation, and the artifact ships the recipe file it was built from), using the **same
runner** as (b) — the one this appendix already cites — and the same instrument, at temperature 0, over
**three independent service starts**, on the corpus pools: 4 domains × 5 arms × 3 starts = **17,130 calls,
0 unparsed**.

**The serving path, stated rather than implied.** These rows — and the fp8 rows of §M.19.15 / §M.19.17 — were
deployed on a machine whose compute capability is **8.0**. Weight-and-activation 8-bit inference requires
capability **8.9** in the runtime we used, so on this host the loader selects the **weight-only** 8-bit path
(the compressed-tensors `W8A16` scheme, whose documented floor is capability **7.5**) instead. The quantised
weights are the published ones and the build card above is unaltered, but **the numeric path is not the one a
deployment on 8.9-class hardware would take**, so these rows bound **the build**, not that path: they are
evidence about how a quantised *checkpoint* behaves, and no claim here turns on activation quantisation.

**A gate, honestly failed and then attributed.** The pre-registered check was that the new service reproduce
the archived per-item outputs of the baseline. It did not, on two items per domain, so **the gate is reported
as failed**. Two attribution controls were then run rather than the criterion being relaxed: at the paper's
own **batch ≤ 2** setting the `st_a` arm reproduces the archive **exactly, 103 of 103 items**, so the flips
there are concurrency, not the artifact; on `aitod` three runs agree with each other to the item and differ
from the archive on **2 of 154**, so that difference is reproducible and is carried as a **~1.3% item-level
stack band** on every absolute rate below.

**The language effect, per start, on the baseline build** ($\Delta = $ `en-base` $-$ `cn-base`, answered-zero
rate, pp):

| domain | start 1 | start 2 | start 3 | BF16 (§M.19.16) |
|---|---|---|---|---|
| ShanghaiTech-A | −15.9 | −14.8 | −14.8 | −21.4 |
| UCF-QNRF | −24.3 | −25.5 | −23.1 | −18.4 |
| VisDrone | +0.8 | +0.5 | +0.3 | +0.5 |
| AI-TOD | −0.4 | −0.9 | −0.4 | +0.4 |

The two dense domains move a lot and the two aerial ones do not, exactly as (b) found; three of the four
domains are same-signed across builds with overlapping intervals, so **the language effect is not an artifact
of one build**. AI-TOD is the exception and is reported as one: its four readings differ in sign, so that
cell is a **build × language interaction** — and its magnitude (0.9–1.3 pp) sits on the stack band above,
which is why it is stated rather than interpreted.

**A stronger form of the same fact.** On both dense domains the English zero set is a **proper subset** of
the Chinese one: across all three starts, items answered zero **only** under English number **0** (st_a
70/71/71 shared, 29/27/27 Chinese-only; UCF-QNRF 81–85 shared, 77–85 Chinese-only). The contract's language
therefore does not *add* zeros anywhere on those domains; it removes a fixed subset of them. The two aerial
domains have no such containment (a handful of items go each way), which is the same statement as $\Delta
\approx 0$.

**Repetition.** Across the three service starts, per-item agreement is **96.2–100%** (`neutral0` arms
99.1–100%; lowest cell `st_a`/`cn-base` 96.2%) and zero/non-zero agreement **97.9–100%**; the headline
answered-zero rates vary by at most **1.5 pp**. No reading below rests on choosing a start.

### M.47 Serving-stack factors, and the value named in the instruction, on real images

**(a) Which serving factor makes the answered zero move?** A reviewer proposed that the answered-zero rate
is a property of the **serving configuration** rather than of the model, and named four candidate factors —
weight precision, context limit, system message, concurrency — with a decision rule fixed in advance: *if
any single factor alone moves the rate by more than 30 pp, the answered zero must be reported as a serving
configuration property*. On the anchor build, one card, reference configuration = 8,192-token context, no
system message, eight concurrent workers, with **three fresh service starts** of the reference and each
factor varied **one at a time**: 7 configurations, 2 domains × 3 arms × 100 items, 4,200 calls.

| factor | setting | max change in answered-zero rate |
|---|---|---|
| context limit | 4,096 / 8,192 / 16,384 | **0.0 pp** — null never exercised (no item in these cells exceeds the context at any setting); see §M.41 for a context effect that was exercised |
| system message | none vs a fixed neutral sentence | **14.0 pp** (dense `base` 36.0% → 22.0%) |
| concurrency | 8 vs 1 worker | **1.0 pp** (dense `base` 36.0% → 37.0%) |
| weight precision | — | **not varied in this design** — the same checkpoint's five builds are compared in §M.18.8 |

**No factor reaches the 30 pp bar**, so on the three factors this machine can vary the answered zero is
**not** a serving-configuration property; the largest one is the system message, at 14 pp. The
**between-start spread is 0.0 pp** — three fresh service starts give identical rates in every cell. Two
limits are stated rather than smoothed: the context-limit row is a **null result that was never exercised**
(no item in these 200 exceeds the context at any of the three settings, so it says nothing about the 36.4 pp
context effect measured elsewhere on a pool that does), and only **four of the six** domain × arm cells are
comparable, because the abstention arms produce no numeric answer on the dense domain.

**(b) The value named in the instruction, on real images.** §M.19.13 established on a deterministic disc
grid that the median answer tracks the value named in the instruction. The same four anchors were run here
on **real** images (150 dense items, one arm per anchor, the anchor clause appended to the same base
prompt):

| anchor | median answer | answers exactly equal to the anchor |
|---|---|---|
| 5 | **5.0** | 46.7% |
| 50 | **50.0** | 96.7% |
| 100 | **100.0** | 97.3% |
| 800 | **800.0** | 99.3% |

The median equals the named value **exactly for all four anchors** ($\rho = 1.000$), so the grid result is
not a property of the grid. The compliance is not uniform in the tails: at anchor 5 fewer than half the
items are literally answered "5", while at 800 it is 99.3% — the smallest anchor is the one the model treats
as a floor rather than as a value to report.

### M.48 The penultimate layer, and whether the composition of a mixture matters

**(a) The penultimate layer: refusal, not collapse.** A reviewer asked for the $L_2$ norm of the
penultimate-layer representation, to separate *active refusal* from *representation collapse*. The probe
reads the hidden states at the position that predicts the first generated token, for all 65 tensors (the 64-layer build), on 135 items of
the same stratum as §M.19.14, under three arms.

**The instrument had to be certified first, and the first attempt at certifying it failed for a reason worth
recording.** The gate compares the in-process forward pass against the **same build's** vLLM records
item-by-item and requires the mismatch rate to be below a threshold. On the first attempt the threshold was
set at **5%** — and the platform's **own repeat noise** is **6.6%** (two runs of the same arm in the same
session disagree on 12 of 182 items, §M.45's companion measurement). A criterion set below the noise floor
cannot certify anything, so that run correctly returned "not measurable" and **no $L_2$ number was
published**; the threshold was re-fixed at 15% *before* the second run and the reason recorded. Under it the
gate passes (batch invariance 5.0%, itemwise against same-build vLLM 10.0%, identical aggregate zero rate
0.300 vs 0.300), and only then were the norms read.

| arm | median penultimate $L_2$ | ratio to `base` | median cosine to `base` |
|---|---|---|---|
| `base` | 1741.7 | 1.0000 | — |
| prohibition of zero | 1700.4 | **0.9763** | 0.9919 |
| naming zero | 1725.8 | **0.9908** | 0.9946 |

Both arms keep the magnitude within **2.4%** of the base arm and the direction within a cosine of 0.99, and
on the 76 items where the naming arm answers zero and the base arm does not, the ratio is still 0.9884. The
verdict under the pre-registered thresholds is therefore **active refusal, not collapse**: the
representation does not lose its magnitude, it changes where it points. That is §M.19.14's "a change of
direction rather than of magnitude" confirmed at the layer the reviewer named.

**(b) Does putting the two pools in one batch change anything?** The zero-call recovery of §M.44 treats a
mixture as the weighted union of its parts, which is exact only if the two kinds of item do not interact.
That was tested directly: 100 verified-empty windows and the non-empty dense items, run **interleaved in one
list** and again as **two separate lists**, on two builds whose weights are on this machine.

| build | true-zero side: one list vs two | non-empty side |
|---|---|---|
| InternVL3.5-8B | 0.760 vs 0.770 ⇒ **−1.0 pp** | 0.005 vs 0.005 ⇒ 0.0 pp |
| gemma-3-12b | 0.480 vs 0.480 ⇒ **0.0 pp** | 0.000 vs 0.000 ⇒ 0.0 pp |

Both sides stay inside the pre-registered 10 pp tolerance, so **composition is not a confound** and the
weighted-union approximation that §M.44 relies on stands. One deviation is declared: the criteria
pre-registered the non-empty side as the dense domain's first 400 published items, but that record contains
**182** items, so the mixture is 100 empty windows plus 182 non-empty images (interleaving rule unchanged).

*Reproduction: the frozen criteria of both probes, the guard, the runners, the analysers and the per-item
records of all calls are released; the guard's own failure at the original threshold is retained as an
artefact rather than deleted.*

### M.49 The knob ordering on two counting domains this paper never used

§7.3's ordering is measured inside this paper's own corpus. Two public counting domains that share neither
this paper's objects nor its images were used to test whether it travels: **MTDC** (maize tassels; Zou et al.,
*Plant Methods* 16, 2020; 361 images, 13,564 instances) and **GWHD 2021** (wheat heads; David et al., 2021;
6,512 images). **GWHD 2021** is released under **CC-BY-4.0**; **MTDC**'s own release terms restrict it to **academic purposes**, so it is used here under that licence and not re-licensed by us. Both are cited rather than re-released, and the exact digests of the copies
used are recorded in the frozen criteria. The protocol, the item sampling rule, the level sets, the criteria
and the two reporting rules were frozen **before** the runs; two amendments made before any data existed are
part of that record and are stated here rather than silently applied: the tiling knob was **dropped** (its
single-image cost is $k^2$, which the pre-registered budget had mis-stated) and the ordering test was
restated as a **cross-domain inequality** (two knobs give two unit-level objects per domain, so an in-domain
rank correlation is not defined). 200 items per domain, 11 levels, **three independent service starts**:
**13,200 calls, 0 unparsed**.

**The prompts are the instrument's, with one substitution.** Every arm is the frozen prompt of
§M.19's instrument — byte-identical except for the object noun phrase, which is replaced by the domain's own
phrase for a maize tassel (MTDC) or for a wheat head (GWHD). The frozen criteria file records the original and
the substituted string verbatim, and the probe asserts that this substitution is the only difference and
refuses to run otherwise. The JSON specification, the abstention wording and **both outlet tokens**
(`cannot_judge`, `no_people`) are unchanged; keeping the person-worded outlet in a maize domain is deliberate,
since the outlet token is part of the contract and changing it would confound contract with wording.

**The gate transfers.** On both domains `permit` and `channel` leave **0.00%** of the `base` arm's
answered zeros still answered zero (mtdc 0 of 25, gwhd 0 of 24; Wilson 95% upper bounds 13.3% and 13.8%, which
exceed the 5% bar and are printed rather than hidden — the point estimate is what the pre-registered `pass`
field is defined on). **Read the mechanism with the rate**: all 25 and all 24 of those items become
**abstentions**, and not one is converted into a correct count; the two arms themselves abstain on 71–99% of
items in these domains. "The zeros are removed" is therefore true and is *not* evidence that the contract
counts better.

**The ordering does not travel uniformly.** With the pooled relative deviation as the caliber, and
`span(contract)` versus `span(pixel budget)`:

| domain | contract span (s1/s2/s3) | pixel-budget span (s1/s2/s3) | pre-registered inequality |
|---|---|---|---|
| GWHD 2021 | 49.4 / 49.5 / 49.9 pp | 46.9 / 46.5 / 46.7 pp | **holds in all three** |
| MTDC | 79.4 / 78.7 / 80.3 pp | 80.0 / 79.8 / 79.5 pp | holds in **one** of three; fails domain-level |

The two domains are therefore reported **separately and as a split**, not pooled: on one the pre-registered
inequality holds on every start, on the other it is a ±1.1 pp knife-edge that fails on two of three. The
domain-level rule (all three starts) and the majority rule agree, and no "any start passes" reading is taken,
since that would be selecting a start.

**Two facts from these domains that the corpus does not show.** (i) The pixel-budget knob spans **46.9–80.0
pp** here, against 4.0–14.6 pp in §F.2: at the smallest budget the answered-zero count reaches 159 of 200
items, so the ladder is driven by a floor rather than by a graded response. (ii) The two knob spectra are
nearly equal on MTDC (79.4 vs 80.0 pp) for opposite reasons — the contract spectrum is carried by a single
arm that separates sharply, and the budget spectrum by monotone saturation — so equality of two spans does
not mean equality of two mechanisms.

**Direction consistency, and what could not be measured.** The pixel-budget spectra are monotone and
negative in both domains. The contract spectra have **named sign reversals** — on MTDC `{base, permit}`
negative against `{bestA, bestB, bestC}` positive; on GWHD three negative against two positive — and the signs
are identical across all three starts. The third quantity §7.3 asks for (the span over levels within
1.10× of the best MAE) is reported as **not measured**: the MAE-optimal level is in both domains a
heavily-abstaining arm (MTDC `channel` has 2 countable items, GWHD `permit` 11), so the 1.10× band admits
exactly one level and the pre-registered rule requires at least three. No proxy is substituted.

*Reproduction: the frozen criteria (`A_criteria_frozen.json`, including both pre-run amendments), the probe,
the item lists and all 13,200 per-item records are released with the paper; the probe asserts the instrument
digest and the byte-level prompt substitution before its first call, and each service start's readiness
timestamp, endpoint and criteria digest are recorded in the run log.*

## Appendix Z. Provenance and corrections

### Z.1 The move convention

This file is a **move, not a deletion**: every section moved out of the main text keeps its heading there
with a one- to two-sentence conclusion and a pointer here, so each claim can be checked against the same
rules and numbers. **Where the two disagree, the main text governs.** Section headings here name the
main-text section each block belongs to.

### Z.1b Private paths and their released equivalents

Some reproduction pointers in this file name the internal working tree in which the runs were made. Where a reader needs to find the same artefact inside the released package, this table is the mapping; **no number or claim depends on it**, and the released package is the authority.

| internal path (as used during the runs) | released equivalent |
|---|---|
| `analysis/e2xt_a800/{merged,nonzero}/` | `data/derived/e3/{merged,nonzero}/` |
| `analysis/e2xt_a800/{zero,anchors,ablate,ablate3,build,reps,env}/` | `data/derived/e3/` |
| `analysis/fsc_a800/` | `data/derived/fsc_res/frozen384/` |
| `analysis/fsc_res/` | `data/derived/fsc_res/<tag>/` |
| `analysis/ea2_z0/` | `data/derived/ea2/` |
| `analysis/e1_results_nonzero/` | `data/derived/e3/nonzero/` |
| `analysis/data/harvest_A/*.npz` | **not released** (detector box archives; see the note in §M.20) |
| `analysis/work/<name>.py` | `code/analysis/<name>.py` |

### Z.2 Where the review requests came from

Where this file says that a reviewer or a review panel asked for a particular measurement (**F.11**,
**M.31**, **M.39**–**M.48**, **M.24**), the request comes from the **multi-model simulated review**
described in the manuscript's declaration of generative-AI use: a panel of large language models was
asked to referee the manuscript, and we then answered the points it raised, including by running new
measurements. **No review by this journal has taken place, and the manuscript has not been submitted
before.** We state this because "the reviewers asked for" would otherwise be read as "this is a revised
manuscript", which it is not.

### Z.3 Corrections log

- **A guard threshold set below the platform's own repeat noise.** The probe of Appendix M.48(a)
  was first certified against a 5% itemwise tolerance, while the same build disagrees with itself
  on **6.6%** of items between two runs of the same arm in one session. A criterion below the
  noise floor cannot certify, so that run was reported as *not measurable* and no representation
  numbers were published. The tolerance was re-fixed at 15% **before** the second run, with the
  reason recorded in the frozen criteria, and the failed first attempt is retained as an artefact
  rather than deleted. The same class of error — a criterion below the resolution of the design —
  is reported for the mixture criterion of M.44.
- **Four further self-inflicted faults were found and fixed before any result was published:** a
  key lookup that wrote 1,128 mixture rows as errors; a malformed format string that made the
  certification gate exit as if it had failed; arms read from a frozen prompt table that does not
  contain them; and a ground-truth join keyed on file names while the reference keys are stems,
  which silently emptied one domain. Each was caught by a check whose output disagreed with the
  others, and each is described in the corresponding appendix.

- **A second pre-registered criterion is missed: the ordering does not survive a common error
  budget.** Appendix M.45(b) fixes an error factor and a cost ceiling in advance, compares a
  unit's levels only inside them, and finds the ordering at Spearman 0.77 with the top knob
  changed, with 14 of the 28 cost-bearing units admitting no admissible pair at all. The paper's
  own §7.3 sentence is amended to scope the ordering to the **level sets compared** rather than
  to claim it in general. The companion test in M.45(a) — an independently chosen, equally sized
  level set with a 2,000-replicate bootstrap and a corrected permutation $p$ — passes, and is
  reported alongside the miss rather than instead of it.

- **Two pre-registered criteria were missed and are not repaired after the fact.** The
  travel-matched ladder of M.42 misses its own ratio band (1.399 against [1.5, 2.4]) and the
  equal-level rescan of M.43 misses the "identical ordering" criterion (Spearman 0.800: the two
  smallest knobs swap); its travel-normalised criterion is **met**, not missed, and §M.43(c) reports it as a
  pass. Both are reported as misses in the
  sections that incurred them, the alternative explanations they bear on are adjusted rather than
  the criteria, and no claim is upgraded to "excluded" on their strength.

Every place where an earlier version of this material was wrong is listed here, with what was wrong, what
now stands, and the artefact that recomputes it.

- **The global abstention-to-refusal ratio and format drift.** An earlier analysis in this project, run on
  a smaller corpus, reported a **global** answered-zero-to-refusal ratio of about **313 : 1** with format
  drift of **zero**. The current corpus gives **12.1 : 1** and about **1.9%**, for two reasons: the corpus
  later gained a large number of InternVL results, whose refusal rate is markedly higher, and the earlier
  analysis did not parse the multi-tile `raw` of tiled experiments. The two lineage-stratified conclusions
  of §3.6(c) are unaffected, being the product of the re-computation rather than of the earlier ratio
  (`_parse_bug.py`, `_parse_diag.py`, `close_parse_issue.py`).
- **The additive-decomposition table of §J.1.** An earlier version mixed a derived re-run into one row,
  which made the appendix fail three lines of arithmetic. The table now uses the **canonical primary runs
  only**, i.e. the same runs as the table above it (`ea2_mixed_analyze.py`).
- **Two cells read as "below the bound".** That reading came from a mis-computed column and is
  **withdrawn**: the identity reproduces the measured dual-convention gap in all four domains to within
  **0.04 pp**.
- **The caliber-subtraction artefact in §F.10.** An earlier version of that appendix subtracted one
  caliber from the other — the ladder was built without filtering the `match` column, so its "levels"
  were double the truth (**16/32** instead of **8/16**) and its span was the all-detections maximum minus
  the person-matched minimum — and the apparent shrinkage that produced (**2.2–2.3×** in-domain,
  **5–10×** zero-shot, reported in one place as **2.2–5.0×**) was that **artefact** and is **withdrawn**.
  The corrected analysis is in `span_equalcount2.py`, which asserts per-ladder caliber uniqueness and
  reproduces those superseded values under `--reproduce-bug`.
- **"The objection is not supported" on the scanning grid.** That conclusion held only for the
  endpoint-preserving (quantile) construction; under **random** deletion to $k = 4$ the fine-grid ladders
  lose a median **38%** of their span (retention 0.51–0.67, 5th percentile 0.32, minimum 0.06). Both
  constructions are now reported (`f10_random_drop_result.json`, `f10_random_drop_order_result.json`).
- **The name of $1-f$.** An earlier version of the appendix in which it is defined named $1-f$
  "zero-channel precision"; that name **inverted the conditional** and is corrected, with no change to any
  measured value.
- **The E2 exit arms store abstention as a parse failure.** An earlier analysis read `pred` alone, which
  silently converted "abstention rate" into "parse-failure rate" and produced a self-contradictory
  $\Delta$zero without a matching $\Delta$abstention. That version is retained as a **void artefact**;
  abstention is counted by scanning all columns other than `pred`/`gt`, and the amended criteria only
  repair the instrument and leave every threshold unchanged.
- **Two design flaws in the decision analysis of §M.27.** An earlier version swept a single θ (0.70), at
  which both conventions fail everything — a threshold outside the region where the statistics differ,
  which can only ever return "no change" — and scored both conventions with the same metric, which makes
  the selection sets identical by construction. It is replaced by the 3 × 3 grid above and by each
  convention's own metric (`deploy_decision2.py`).
- **A "common band" asserted across three settings that do not share one.** An earlier version of §M.34
  read that the synthetic-grid floor, microscopy and the answered subset of real images "all land in
  **−18% to −29%**". That conjunction was wrong: the three are separate quantities on separate subsets, and
  only the third lies in that band (microscopy is **−50.1%** pooled; the synthetic grid reaches
  **−42.5%** in the single render tabulated in §J.8, and **45–50%** across five independent renders). The
  paragraph now states the three magnitudes separately and says explicitly that they are
  **not one common band**; no measured value changed. The per-cell table behind the synthetic figure is now
  printed in **§J.8**, so that number is traceable inside the submitted material rather than only in an
  internal record, and §1/§5.5/§5.7 quote the clean-input under-count as "**up to 50%**" — the five-render
  range — in place of the single render's **−42.5%**, which was the unconditional maximum of that one table
  rather than the narrower band that held for 14 of its 20 cells.
- **The two microscopy numbers are one quantity at two calibers.** §5.7 prints **−50.1%** and §J.7 printed
  **−53.8%** without saying how the two relate. They are the whole-domain pooled figure and the top count
  bin ($[60,101)$) of the same domain under the same convention; §J.7 now labels both calibers explicitly.


