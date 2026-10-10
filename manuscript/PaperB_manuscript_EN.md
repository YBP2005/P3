# Answered-zero outputs dominate the aggregate under-count on dense scenes for one anchor build and language: signed error direction in object counting with vision-language models

---

## Abstract

Symmetric magnitudes look alike: a count of 100 and one of 150. We treat the **signed
error direction** as a measurable dimension and contribute **two findings plus the apparatus that makes
them checkable**: an **operationalisation** of abstention that separates a suppressed abstention
from a true zero, and the **dual-convention identities** that make under-counts readable. For **one anchor
build under Chinese base prompts** **answered-zero outputs** account for **82–94%** of the net
under-count under ground-truth-weighted share (**base arm**); contract interventions change **observable response channels**, not each base response's **latent state**; reading the zero contribution as abstention **requires channel purity and exhaustiveness**, and the **item-count** convention gives **53.9–68.2%**. The **answered-zero rate** drops **42.7 pp on the BF16 build under English** (§8.2).
Given an abstention option **1591/1591** calls abstain; forbidding it yields a **per-item median** of **2.463–9.452×** (§5.7, M.1).
The gate is **availability of an abstention token**, not demand. Abstention is a
behaviour, not a capability ceiling: gated by legibility, removable by tiling (**56.6% → 0.0%** on the anchor build) or, at a directional cost, by prompt relaxation
(**−82% → +234%**). Direction span is a property
of {implementation × training domain × data domain × protocol}, not a paradigm —
**2–3.4×** across implementations under a **shared** protocol (DM-Count **20.1–34.3 pp** vs
P2PNet [1] **10.1 pp**), **3.5×** under a domain swap,
and a defective reproduction as an **implementation defect** (§6.1, K).
What replicates under **shared calibration** is the **ordering** of these spans, not their magnitudes, and only under the **level sets and calibers compared** (§7.3).

## 1. Introduction

**Motivation and the evaluation gap.** In surveillance and resource scheduling the two error directions are
**asymmetric**: missing objects and double-counting are not equivalent, and most safety and inventory
settings prefer over- to under-counting. The error's **signed direction** has therefore remained
implicit. Our first question is: *can a counting system's error direction be manipulated
systematically, and what sets the range over which it can be moved?* (Appendix M.11)

**A prior question.** Before that, we examined a widely accepted premise: that
vision-language models (VLMs) systematically underestimate dense scenes, which prior work treats as a
**capability** problem. Re-classifying every outcome in our corpus (892 result files, ~**620k** records,
four VLM configurations, nine datasets), we find that **the dominant component of these
"underestimates" is not underestimation but abstention**: the model declines to estimate instances it
cannot individually ascertain, and expresses that refusal as the **literal answer "0"**. Under a ground-truth-weighted convention on one anchor build, answered-zero outputs account for **82–94%** of the net under-count
(**base contract arm, Chinese prompts**; the full range over arms and domains is in Appendix J.1);
the **answered-zero rate** drops **42.7 pp on the BF16 build under English prompts** (Appendix M.39)).

**Why separating the two is not a matter of terminology.** A model answering a literal 0 on 60% of
dense images and underestimating by 20% on the rest reads, conventionally, as *mild
underestimation* — whereas on six images in ten it **answers nothing at all**. The remedies are
opposite: retraining or calibration versus changing the **input protocol**. Worse, recording a refusal as
"predicted 0" makes it **masquerade as conservative**, which a safety deployment least wants.

**The second half of the gap.** Selective prediction and abstention-aware classification have
well-developed criteria [2], and regression now carries a reject option too [3], [4] — all treating
abstention as **explicit**: classification, question answering, reasoning, regression.
Counting differs: abstention is **implicit** (a literal 0, indistinguishable at the output level from
an estimate of zero); costs are **asymmetric**; and **no dependable confidence** exists for a rejection
rule. Abstention must be **operationalised** in the counting domain (§3.6, Proposition 1); our
contribution is bounded to the **output contract**, the **zero-counted versus answered-only**
conventions, and **ordering within pre-specified level sets**.

**Four properties of abstention.** **① Measurable, with a lineage-specific channel.** Rather than stipulate that `pred = 0`
means abstention, we give an **empirical criterion**: a lineage abstaining mainly in language would
show an answered-zero-to-refusal ratio approaching 0.

**② Gated by per-instance legibility, and by target count**, and **decoupled from directional bias**: on
count-controlled grids arrangement and blur alone drive abstention to 90%, while on clean synthetic dots the
same base arm neither abstains nor becomes directionally accurate (§5.6, §5.7).

**③ Switchable from both ends**, being a behaviour: tiling (**Fig. 1**) drops the ShanghaiTech-A [5] abstention rate from **56.6%** to **0.0%** (2×2: 6.0%, 3×3: 0.55%)
without harming direction.

**Fig. 1.** Tiling removes the ShanghaiTech-A abstention without harming direction.

**④ Removing abstention costs direction among the tested interventions.** Prompt relaxation (**Fig. 2**) also
drives abstention to zero but flips $\rho$ from **−82%** to **+234%…+345%**; **tiling is the only one that improves both.** *(Per-property numbers: Appendix L.)*

**Fig. 2.** The prompt-strength dose–response: relaxation also drives abstention to zero, but flips $\rho$ from −82% to +234%…+345%.

**Supporting result: the response spectrum of direction.** The signed direction can be moved
continuously, but its **achievable span is an empirical property of {implementation × training domain ×
data domain × protocol}, not of a paradigm**. What is established is the **ordering**, preserved at
**Spearman 0.981–0.999** when every ladder is re-estimated on a common level count with its extreme level
removed (Appendix F.10): the **ordering** is not a function of the scanning grid, the **magnitudes** are. What is **not**
established is a partition: the observed separating split is **1.6 pp**, below our own noise floor, so we
report a **candidate** only, and claim neither two anchor zones nor bimodality
(Appendices F.3, M.37, M.17).

**Contributions.** Two empirical findings, plus the apparatus that makes them checkable: the identities of §3.8
and the appendices, which are arithmetic, not findings, and whose role is that every headline number is
recomputed from the released records, or labelled a transcription or an author-side computation (Appendix F.9). 1. **Finding 1 — on dense scenes the aggregate under-count is mostly a suppressed abstention, and the
   suppression is set by the output contract.** Within the cells studied here, literal-zero outputs dominate
   the pooled under-count (§5.5); for InternVL2.5-8B [6] the answered-zero channel covers only 69.69% of
   abstentions (§3.6, Proposition 7); and **the outlet** is a property of the serving configuration, not of the lineage (the **rate** is not; Appendix M.47) — given an abstention token **1591/1591** calls abstain, and in a census fixing the
   stack and varying only the contract, item-level pairing removes the answered zero in **46 of 52**
   (model × domain) cells (**52 of 52** under the three-option contract; M.18.2–M.18.3), while the same grid on
   **seven families — four of them beyond the corpus's own, all unquantised — removes it in 7 of 7** (§5.7,
   M.19), two of the seven having offered only **9** and **156 zeros** to remove (**2** of the latter
   from the dense domains). The **frequency** claim stays bounded by lineage, build and domain; the per-cell
   bounds are stated in §8.2 and Appendices M.18–M.19.
2. **Finding 2 — per-instance legibility gates whether a model answers, and it is a diagnostic, not a
   repair.** We give the proxy, the effect structure under three controlled manipulations, and what it
   **cannot** do: it supports selective prediction (the most legible 20% of images reduce MAE by
   **31–66%**, selector AUC **0.753–0.786**) but **cannot repair direction** ($\rho$ attenuating only from
   **−85.0%** to **−53.4%**), and because it requires instance-level boxes it is a **diagnostic, not a
   deployment-time criterion** (§3.3, §7.1).
3. **The apparatus: a re-checkable measurement discipline.** The dual convention and its divergence
   condition (Proposition 2), the anomaly-exclusion rule, span variants against the noise floor
   (**2.15–6.46 pp**), and every split point enumerated, not searched (Appendix F.3). It yields one
   positive rule where a magnitude law is absent: the span **ordering** is robust, magnitudes are not,
   and a magnitude is quoted with the grid density and the calibration caliber that produced it
   (Propositions 3, 5; §7.3). The spectrum is reported as an **ordering, not as a finding**.

**Where each result binds.** The abstention results are measured on **seven families across four corpus domains plus a
nine-configuration panel on FSC-147 [7]**, and tested prospectively on an **independently sampled panel of six
further families in six lineages with no Qwen model** (§5.14); the direction results span **three families of implementations**.

## 2. Related Work

### 2.1 Detection-based counting versus density regression

Two families dominate counting: detection-based methods localise instances and count them, while density
regression predicts a density map whose integral is the count — the definitional formulation of the field
[8]; comparative work treats them as paradigms whose trade-offs are read on magnitude error.

### 2.2 Thresholds, operating points and cost-sensitive decisions

The detection literature has long studied the operating point, and cost-sensitive decision theory
formalises asymmetric losses. That apparatus supplies no measured answer for counting, which is this
section's job: the **counting error direction as a function of the operating point**, NMS IoU being a second such
knob, and "crossing zero" shown to be **not a single event** — the zero of the user-side error and that of the
total error differ by about 2.1–2.3 (§4.4, §4.7).

### 2.3 VLM counting, and abstention in the counting domain

VLM counting is an active area, with benchmarks showing that current models count poorly ([9] and
successors). A parallel and largely separate literature studies abstention: selective prediction [10], [11],
rejection options, abstention benchmarks for multimodal reasoning ([12], [13]), and
abstention knobs in video question answering ([14]); and VLM refusal moves with an image's mere presence in ways instructions do not
control [15] — acting on the tendency, not on the channel §5.7 manipulates. **The gap is that abstention rates are rarely
measured on counting tasks**, and that none addresses the **implicit** case: a literal
zero that the output level cannot distinguish from a genuine zero. On counting tasks we
**reproduce, not claim** the legibility gating — it is gated by per-instance legibility, and by object count — and for the
dominant lineage it appears as that literal zero (§3.6, §5.6).

### 2.4 A same-source study: numerosity stimuli under orthogonal manipulation

The numerosity tradition [16] and NumerosityVLM [17] likewise use synthetic stimuli under orthogonal
manipulation, but **answer a different question**:

**Table 1.** Positioning against the numerosity-stimulus literature of §2.4.

| Dimension | NumerosityVLM | This work |
|---|---|---|
| Stimuli | **10,800** synthetic images, **six** controlled conditions, **seven** VLMs | Synthetic **and** real; pixel budget, blur, contrast, crowding, tiling, prompt |
| Dependent variable | **Accuracy** | **Signed error direction and abstention** |
| Conclusion | Architecture explains most variance | Direction is governed by {implementation × training domain × data domain × protocol} |

### 2.5 Sparse counting and the head/person granularity problem

Sparse counting benchmarks (SFCHD [18], FSC-147 [7], CountBench [19], TallyQA [20]) [21] and the head/person
literature supply our sparse and external-validity settings.
Recent work notes that **counting granularity is left implicit**, and that most counting datasets lack
multi-granularity annotation ([22]; [23]); §3.2 turns this into a first-class variable.

### 2.6 VLM counting-failure mechanisms: our positioning

Recent work locates counting failure at the **reporting** stage ([24]; a hierarchy in [25]) and establishes
cross-paradigm counting comparison ([26]); **we cite that locus, not claim it**. Those works localise the failing stage — one decomposing counting into visual individuation,
magnitude awareness and symbolic mapping [27] — whereas our quantity is the
**composition of what it emits**: an answered `0` split
into a **suppressed abstention** recoverable by an output contract and a **genuine estimate of zero**, separated
on a fixed serving stack in §3.8 and §5.7.

### 2.7 Evaluation validity: non-determinism and aggregate metrics

Our VLM indicators came from single samples. Repeat sampling shows item-level reproducibility for a hosted
API to be about **15%**, while a locally controlled stack agrees at essentially 100% (batch ≤ 2); aggregates are
far more stable (Appendix A).

### 2.8 Crowded-scene occlusion counting

A dedicated benchmark evaluates VLMs on counting occluded objects (CAPTURe [28]). Its objects
remain **informative** behind the occluder and require inference, so it probes reasoning; our occlusion
factor asks instead whether an instance is still **ascertainable** given a pixel budget. The models do **not** perform
modal completion: when inference is possible they neither infer nor abstain, they simply under-report as
usual (−50% vs. −50%). (Appendix M.11)

## 3. Method

### 3.1 Counting conventions and metrics

Calibration conventions and their failure modes follow the standard taxonomy of Guo et al. [29]; stated for classification, it is a naming convention
for the counting map, not a validated calibration result.

All three families are evaluated against the same ground truth. Magnitude metrics are MAE, RMSE,
normalised MAE and tolerance-based scores; the principal **directional** quantity is the signed relative
deviation

$$\rho \;=\; \frac{\overline{\text{pred}} - \overline{\text{gt}}}{\overline{\text{gt}}}
\quad\text{(in percent, signed),}$$

Two uncertainty quantities are used here and they are **not interchangeable**: the **across-repeat** band of
§A.3 governs cross-model and cross-configuration comparisons, whereas a per-cell interval resamples images
and is therefore a **lower bound** (§A.2). The quantity has **two sub-conventions that must be labelled
separately** — the **pooled ratio** and the
**per-image ratio mean** — whose divergence condition is given by Proposition 2. Correlation coefficients
are always written $r$ and annotated as Pearson or Spearman. **Abstention** is an indicator in its own
right, never folded into tolerance-based scoring, and always reported as a **triad**: the rate, $\rho$ on
answered items only, and the ground-truth-weighted under-count share $S$ (Proposition 4), whose conditioning
event and denominator are not those of the Proposition 7 channel coverage. Density is summarised by OPM,
whose applicability boundary is §7.1.

### 3.2 Target granularity is a first-class, and widely ignored, variable

In counting, "one target" is not naturally determined: in a safety-helmet scene an annotation may define
the **head** or the **whole person**. Running both conventions on SFCHD shows that **changing the convention
changes the sign and magnitude of the conclusion** (§5.2). part of the spread across published counting numbers is a
granularity artefact, not a modelling difference, so **any counting evaluation must declare its target
granularity explicitly**.

### 3.3 Per-instance legibility: definition, operationalisation and boundaries

Our central independent variable is **per-instance legibility** — whether, under the given observation
conditions, a target instance is still sufficient to be judged an independent instance. It is **not a
property of the model** but of {observation conditions × annotation granularity}, and can therefore be
computed **before inference** from images and annotations.

**It is a multivariate construct; we do not assume a single sufficient proxy.** The three manipulable
factors are **instance size**, **blur** $\sigma$ (decoupled from resolution) and **overlap** (arrangement
at fixed size and blur). Their effects are **not equal**: under controlled frame pairing **blur is the
strongest single gate**, while the **per-instance pixel
budget is a covariate, not the gate** — informative within a domain, but at fixed scale it
co-varies with instances per image, and across the aerial and microscopy domains the two decouple (§5.6,
§5.10).

**The observable proxy.** For each instance $i$, take $a_i$, the pixels inside its annotation box **not
covered by another instance's box**; the image-level proxy is the median over instances,
$p = \operatorname{median}_i a_i$ (Appendix C.1). It is deliberately simple — no model, no inference, no
confidence signal — and its usefulness is demonstrated rather than assumed: as a selector it reaches
**AUC 0.753–0.786**, and keeping the most legible 20% of images cuts MAE by **31–66%** while
attenuating the relative deviation only from **−85.0%** to **−53.4%** (§7.1) — an ordering usable
**before inference**, not a repair of the direction.

**Boundaries — what this variable is and is not.** Legibility is a **secondary, stratifying variable** here, and its use is bounded accordingly. It supports **stratification, ranking and selective prediction**; it is **not** a
sufficient statistic, must **not** be compared across scales directly, and must not be read as "more pixels
is always better". Because it is defined on annotation boxes it is **not** a deployment-time decision rule,
and the obvious annotation-free substitute — the *same* functional form on **detector** boxes — does not
inherit its power (AUC **0.49–0.63**; M.20). It is also **not** an attention map or a confidence, and **not** OPM,
whose cross-domain Spearman correlation is only **+0.33** (§7.1).

### 3.4 Datasets and scene characteristics

FSC-147 is the counting-anything benchmark of Ranjan et al. [7]; CountQA [30] and PushupBench [31] are the corresponding VLM-counting benchmarks.

Nine datasets are characterised on **two** axes — the count axis (OPM) **and** the legibility axis
(Appendix D.3); OPM is used for **characterisation only**, since §7.1 shows it is not a legibility-consistent
gate. What matters for the central claim: VisDrone [32] and AI-TOD [33] have the **lowest** targets-per-image
(17–22) yet abstain **as often as** ShanghaiTech-A (433), 68% vs. 57% (**Proposition 6**).

### 3.5 Implementations

**Detection:** YOLOv12n [34] (tiling follows SAHI [35]) with nine variants plus budget × source-domain
combinations, zero-shot COCO [36] person detectors under a tiling protocol for the dense end, and two label
conventions; Faster R-CNN [37] and RetinaNet [38] supply a second and third family (fairness parameters in
D.2; M.11). **Vision-language models:** **Qwen3-VL-32B-Instruct** [39] on a self-hosted
4-bit AWQ [40] **community requantisation** (`cyankiwi/Qwen3-VL-32B-Instruct-AWQ-4bit`; Appendix M.46) and GPTQ-W4 [41] stacks cross-checked against a BF16 hosted API, with an 8B scale control, a Qwen2.5-VL-7B [42]
generation control and InternVL2.5-8B [6] as a second lineage; three directional arms use **byte-identical
prompts across datasets**, plus five prompt families and a seven-level prompt-strength dose, with **Chinese**
corpus prompts (language control: §5.5). **Density regression:** BL [43], CSRNet [44] and DM-Count [45]
trained on SFCHD [18], with public in-domain weights for the dense end.

### 3.6 Abstention: operationalisation and lineage stratification

Abstention is our leading indicator, so its operationalisation is stated item by item, not left as
"the predicted total is zero". Three points matter here.

**(a) Five mutually exclusive classes** — `normal`, `answer_zero`, `refuse`, `format_drift`, `api_error` —
with `api_error` excluded from the denominator. **(b) De-duplication** at file level (MD5) and at row level
by **identity of the experimental condition**, **not** by item. The class criteria, the de-duplication
protocol and the per-tile parsing of concatenated `raw` fields are given in Appendix B.1–B.2.

**(c) Is `pred = 0` a sufficient operationalisation? A two-lineage answer (the two lineages for which the ratio is measured).** We give an empirical
criterion, not a stipulation: a lineage that abstained mainly in natural language would show a low
ratio of answered-zero to textual refusal, approaching 0, and **the lower that ratio, the larger the
identification error $1/(\kappa+1)$ of Proposition 7** — the two statements point the same way. Over the
whole corpus (892 result files, ~620k records):

**Table 2.** Lineage-stratified abstention channel (the table behind §3.6(c) and Proposition 1).

| Lineage | Answered zero | Textual refusal | Ratio | Coverage by `pred = 0` |
|---|---|---|---|---|
| Qwen3-VL-32B [39] | 31,387 | 57 | **550.6 : 1** | **99.82%** |
| Qwen3-VL-8B | 3,392 | 0 | — (none) | **100%** |
| Qwen2.5-VL-7B | 980 | 0 | — (none) | **100%** |
| **InternVL2.5-8B** | 14,015 | **6,096** | **2.3 : 1** | **69.69%** |

**For the Qwen family — the source of all our abstention headlines — `pred = 0` covers **99.82%** of them**
(the three configurations: 0.18%, 0% and 0%). **For InternVL2.5-8B it covers only about seven
tenths**, the rest arriving as textual refusals. **Cross-lineage comparisons of abstention rate must
therefore define the channel per lineage.** The incompleteness is **lower-bounded, not
disclosed**: by Proposition 7, write $f=R/A$ and $R/N$ for relative missed detection and absolute omission; a lineage with ratio $\kappa$ identifies its **answered-zero rate** only conditionally, the equality
failing under an unverbalised true zero, within **at least** the missed-refusal share $1/(\kappa+1)$ — **0.18%** for Qwen3-VL-32B and
**30.31%** for InternVL2.5-8B — so any **answered-zero rate** quoted for a partially covered lineage carries that error bar, and the two lineages are never pooled
(§3.8, §8.2).

**(d) A consequence that corrects the mechanism.** What decides whether a refusal is expressed is the
**output contract**, and specifically whether it offers an **abstention token** — not how much
per-instance work the prompt demands. Prompts that *require* per-instance enumeration or localisation but expose only a numeric field produced
**zero explicit refusals** and went on answering **0** (Qwen3-VL-32B-AWQ on VisDrone: **258/273** under
`enum`, **263/273** under `locate`; both builds of that checkpoint reproduce it, Appendix M.18). Adding a
single abstention token to **the same** enumeration prompt converted **268/273** of those items into
explicit abstention, whereas relaxing the demand while still exposing only a number left the answered-zero count unchanged (**121 → 121**) or
slightly higher (**232 → 235**). **The operative gate is
therefore the availability of an abstention token, not the enumeration demand**. The legibility attribution consequently rests on the direct manipulations of
§5.6–5.7, with one boundary the same census imposes: under an abstention contract the **dense**
domains **saturate** (89–100% of items the corpus had answered with a number, 100% of those it had
answered 0), so the outlet carries no selectivity there and legibility-gating is demonstrable only in the
**aerial** domains, on **36–93%** of such items (Appendix M.18).

### 3.7 Anomalous records, exclusions and data hygiene

Anomalous-record removal, quarantine of unreadable key data, and the person-matched
recomputation are preconditions here, not refinements; the rules and the corpus-wide
scan behind them are in **Appendix I**.

### 3.8 Formal framework: what is identifiable from outputs

Eight statements are used later. All are **either identities of the reporting convention or decidability
statements** — not empirical findings — so they are stated compactly here; full derivations and scope
notes are in **Appendix M.21**.

**Proposition 1 (abstention is not identified by outputs alone).** `y = 0` is produced both by abstaining and
by estimating zero, so identification needs an auxiliary channel. **This holds only if the two
channels are exhaustive; a genuine zero that is also not verbalised would be a third, and our data do
not exclude one.** We use
$\kappa=\#\{y=0\}/\#\{\text{textual refusals}\}$ and report the measured value — the
missed-refusal share **0.18%** for Qwen3-VL-32B ($\kappa = 550.6$) and **30.31%** for InternVL2.5-8B ($\kappa = 2.3$) — the arithmetic reason §3.6 reports the two lineages separately, not pooled.

**Proposition 2 (the two conventions diverge exactly when the per-image ratio correlates with
ground truth).** $\rho_{\text{pooled}}-\bar\rho=\operatorname{Cov}_g(g,r)/\bar g$; abstention is itself
GT-dependent, but that alone does not fix the covariance's sign or size: it is **measured per domain, not assumed**. §5.12 reports those values. Both conventions are therefore reported side by side, their divergence fixed by that covariance.

**Proposition 3 (span is a functional of the admitted level set).** Any candidate predictor built from its
extremes is a **component of the definition** (partial correlation exactly $\pm 1$). That is why we withdraw
our own candidate and claim **availability** — decidable from the same quantities, since it holds iff
$\max_\ell q_\ell \ge 1$ at the loosest admitted level — but **not magnitude**: magnitude is not predicted by
any quantity we have been able to construct.

**Proposition 4 (the aggregate bias decomposes exactly).**
$\rho_{\text{total}}=-(1-w)+w\,\rho_{\text{answered}}$ with $w=G_N/G$, and the abstention share of the
under-count has the closed form $S=(1-w)/[1-w(1+\rho_{\text{answered}})]$, which is a share inside $[0,1]$ only when the net deviation is an under-count; where it is not, the two pp terms of Table 3 are the reported quantities (§8.2). This is a reporting identity of the same form as the answer-propensity / conditional-composition
decomposition we use elsewhere [46]; what is in question is where the movement goes on this corpus.

**Proposition 5 (span is equivariant, not invariant, under shared affine calibration).**
$\text{span}\mapsto s\cdot\text{span}$, so the objection that a large span is a calibration artefact
requires exhibiting $s\ll1$.

**Proposition 6 (targets-per-image is not a legibility-consistent stratifier).** VisDrone and AI-TOD have the
fewest targets (17–22) yet abstain as often as ShanghaiTech-A (433), which licenses stratifying by
legibility, not by density.

**Proposition 7 (under the two-channel assumption the identification error of the answered-zero channel is
$1/(\kappa+1)$, a lower bound).** Conditional on it, that error is a known function of a measured
quantity — **0.18%** for Qwen3-VL-32B and **30.31%** for InternVL2.5-8B — and because a third channel would
raise it, these are **lower bounds on the identification error, not upper bounds**. The assumption is **not
proven**: the quantity is a **coverage, not a precision** — it bounds how much abstention the channel
catches, not how many answered zeros are genuine. Two external true-zero pools now measure a **sensitivity, not a precision**: under `base` three of four builds answer zero on **98–100%** of aerial pool S-1, and only one **build** — gemma-3-12b — has headroom in both pools, so only its two-source comparison is licensed (the other three builds' two-source agreement there is largely a saturation product, Appendix M.21.9(c)), and $\pi$ remains unknown (Appendix M.21, M.21.10) — **whereas under `permit` the anchored build abstains on 148 of 150 S-1 items yet still answers zero on 146 of 150** of the second pool (Appendix M.21).
Third-channel sensitivity is in Appendix J.5.

**Proposition 8 (the dual-convention gap is an identity, not a bound).** From Proposition 4 the gap equals
$-(1-w)(1+\rho_{\text{answered}})$, i.e. **zero iff $w = 1$ or $\rho_{\text{answered}}=-1$**, and it
survives an unbiased answered subset — so a single-convention report is not merely incomplete but
uninterpretable.

### 3.9 Figures and tables

Figures **1–4** and Tables **1–6** appear where their claim is stated (**Appendix D.4**).

## 4. Results I: Detection — the threshold knob and the domain conditionality of its reach

*(A cross-paradigm control that supplies the direction knob; the headline finding is in §5.)*

### 4.1 Reachability of the zero crossing, and its domain conditionality

Detection is the only family here in which a **single scalar** moves the signed direction continuously
across zero: on VisDrone the in-domain detector's pooled $\rho$ — **person-matched** throughout this
section — travels from **+109.4%** to **−86.3%**, while the same architecture with COCO-pretrained
weights, on the same domain, item set and convention, covers only **16.4 / 30.3 / 55.5 pp** at the same three
input sizes 640 / 1024 / 1536 px, against **95.9 / 159.3 / 195.7 pp** for the in-domain weights (three levels),
and never crosses (all-detections, same eight-level grid: **63.1–156.0 pp** for the zero-shot
ladder and **352.8–508.3 pp** for the in-domain one; Appendix F.10). (Appendix M.37)

### 4.2 Refinement by density binning: the bound holds, but it is a per-tile bound

An earlier reading placed the boundary of reachability at a fixed image-level
density. Refining by ground-truth density bin on a fine grid (threshold step 0.005, bootstrap 10,000×)
shows the bound is real but **belongs to each effective tile, not to the image**: the last
reachable bin is reached by tiling, and what fails beyond it is the per-tile instance budget.

### 4.3 The fine $\tau$ ladder: where the boundary lies

The published ladders scan $\tau$ at different granularities, so the boundary is located on a **common grid**
(per-level tables in Appendix F.8). **The
threshold-cleaning curve of Fig. 3** separates reachable from unreachable levels; the fine-grid magnitudes are read with their grid density (§7.3).

**Fig. 3.** The threshold-cleaning curve separating reachable from unreachable levels.

To rule out a coarse-grid artefact we repeat the scan on a **fine grid** — $\tau$ from 0.02 to 0.90 in
steps of 0.005 (**177 points**), with **4,000× bootstrap image resampling** for the 95% interval of
$\tau^\*$; every weight file is matched to a unique result table by an `n_raw` fingerprint (**100%
match**). Tiling moves UCF from unreachable to reachable ($\tau^\*$ 0.121–0.152): protocol and threshold
jointly determine reachability. (M.9)

### 4.4 A second knob: NMS IoU and input scale

The threshold is not the only quantity bearing on reachability. **NMS IoU is a second knob**: it moves
$\tau^\*$ monotonically **0.038** (IoU 0.5) → **0.073** (0.6) → **0.121** (0.7), while inference input scale
matters much less — 640 / 1024 / 1280 give **0.117 / 0.121 / 0.131** (E.2). Controllability is
therefore a property of the **joint** configuration of threshold, NMS IoU and input protocol, not of one
scalar.

### 4.5 Tile granularity: a third knob, which can turn unreachable into reachable

Extending the ladder to **tile-512 and tile-256** across **two detector families** under the identical
protocol (E.3, M.16) gives two readings: **tile granularity can rescue an unreachable
configuration** — unreachable at tile-1024 becomes reachable at tile-512 — so unreachability is a **joint
property of {domain × protocol}**; and the pre-FPN architecture needs finer tiling to unseal the same domain.

### 4.6 The direction of $\tau^\*$ under finer tiling is not family-invariant

"Finer tiles raise $\tau^\*$" holds for RetinaNet — monotone on UCF-QNRF [47] (0.124 → 0.225 → 0.306)
and ShanghaiTech-A (unreachable → 0.124 → 0.237) — and **fails** for YOLO (UCF 0.121 → 0.176 → 0.173;
ShanghaiTech-A unreachable → 0.260 → 0.183).
### 4.7 "Crossing zero" must specify which zero

The phrase presumes the zero is unique; it is not. The cascade identity $\max\lvert\delta_U - (\delta_T - \delta_H)\rvert =
0$ holds **exactly per image** over the **6,033** held-out images — a **definitional identity**, so any two of the three
quantities determine the third (Appendix M.9).

## 5. Results II: Vision-language models — abstention is the leading failure mode

### 5.1 Screening and the full SFCHD cross-paradigm comparison

Screening on the sparse end (SFCHD, 12,066 images) across three arms and two stacks establishes the
baseline for the rest of the section: on sparse, clearly visible targets, the three-arm prompts move the
direction as expected but at small amplitudes, and abstention is negligible.

### 5.2 Target granularity changes the sign and magnitude of the conclusion

Running both target conventions on SFCHD (head-level versus whole-person) under the three directional
arms shows that $\rho$ and the abstention rate are **not interchangeable** between conventions.

### 5.3 Sparse-domain three-arm directional induction

On the full sparse set (12,066 items × 3 arms × 2 stacks) the prompts move the direction monotonically
and reproducibly, the *under* arm producing systematic under-counting and the *over* arm
over-counting. Because abstention is near zero here, this setting isolates **directional** control from
**abstention** control — a separation useful in §5.7.

### 5.4 Cross-domain abstention summary

Aggregating over domains, the abstention rate is **not** ordered by object count: it is highest in the
dense-crowd and aerial domains and essentially zero in the clearly-resolved ones, although the latter
carry **more** targets per image (§5.6 identifies the ordering variable). (M.29)

### 5.5 Decomposing the under-count: abstention versus answering

By **Proposition 4** the total under-count is an abstention term plus a scaled answering term, and the
**GT-weighted under-count share of zero-output items** has the closed form $S=(1-w)/[1-w(1+\rho_{\text{answered}})]$; evaluated here it gives **82–94%** on the four dense and aerial domains **under the base contract arm, Chinese prompts, one anchor build, and the ground-truth-weighted convention** (M.19.15: only the defining checkpoint's two precisions clear
50%) (three of twenty (language × build) cells leave the unit interval; M.18.9, M.19.16(ii), M.39, M.46(c)). **This is the quantitative core of the paper's central claim (a share of the under-count, not a precision; Proposition 7): the received
description "VLMs underestimate dense scenes" is mostly a description of refusals.** (Appendix M.9)

**Table 3.** Proposition 4's terms on the four headline domains.

| Domain (anchor build) | abstention term | answering term | $S$ | abstention rate, item-count convention |
|---|---|---|---|---|
| ShanghaiTech-A | **−76.41** | −4.67 | **94.2%** | 56.6% |
| UCF-QNRF | **−81.27** | −5.48 | **93.7%** | 53.9% |
| AI-TOD | **−67.17** | −12.99 | **83.8%** | 68.1% |
| VisDrone | **−58.39** | −12.71 | **82.1%** | 68.2% |

*(Terms are pp of the pooled relative deviation and sum to it exactly; $S$ is the ground-truth-weighted
share and the last column the same **rate** under the item-count convention. Appendix J.1.)*

### 5.6 Count and correctness under controlled rendering factors

A new synthetic-dot experiment holds rendering fixed: count predicts correctness, not abstention.
β = −4.2059, CI [−4.6465, −3.7653], 49.9% → 2.1% → 0.5% (11,232 = main-batch primary; **M.11.1**).

### 5.7 Abstention and under-counting are two separable failure modes

The title claims the **composition of the aggregate under-count**, not the absence of under-estimation: the
answered-only relative deviation is **−19.8%** (ShanghaiTech-A), **−29.2%** (UCF-QNRF), **−30.5%** (VisDrone)
and **−39.6%** (AI-TOD), each far outside the paper's own **7 pp** band (§A.3 — the across-repeat band of $\rho$, which is neither the 3.92 pp batch bound of Appendix M.21.9 nor a band for zero rates).

**Mode A: capacity-driven under-counting.** Even with ideal input the model under-counts by **up to 50%** in relative deviation (not an abstention share; Appendix J.8) — a floor set by the reporting stage, not by perception. **Mode B: mode collapse, whose extreme form is answering 0.** Triggered by loss of legibility, absent on clean input, switchable on by blur, overlap or a strict prompt.
**The channel is set by the output contract (Appendix M):** on the items that the corpus configuration
answered exactly 0, five configurations given an explicit abstention option abstained
in **1591 of 1591** successful calls and **never** answered 0, while forbidding abstention gave a **per-item
median** of **2.463–9.452×** the true count. The zero is therefore neither specific to the
quantised local deployment nor a universal family behaviour: the hosted checkpoint
matching the corpus configuration answers 0 on **25.8–31.7%** of these items, whereas `plus`, `flash`
and `235b` answer 0 on **0–0.4%** (all 48 cells: Appendix M, M.11).

**The cross-family result: the answered zero is set by the contract, not by the lineage (Appendix M.19).** A family's
chat template cannot be equalised across vendors — changing it moves an absolute rate by up to **56.6 pp**
— so no absolute rate is compared across families: every claim below is a **within-family paired** contrast
with the template held constant (Appendix M.19.1, M.19.8). Every
configuration above descends from two lineages, so we re-ran the same grid with the **identical instrument**
(same probe, prompts, parser, domains, pools, fixed seed and items, md5 `03edb14c98ff`) on **four further
open-weight families — Gemma-3-12B, InternVL3.5-8B, Phi-3.5-Vision-4.2B and LLaVA-OneVision-7B, all
unquantised official builds — together with three anchors: seven families.** Adding the
abstention token
removed the answered zero in **7 of 7**:

**Table 4.** The cross-family contract gate. The three rows tagged `(anchor)` use the community AWQ-4bit requantisation of §3.5.

| family (lineage) | base zeros | still 0 under `permit` | rate | 95% CI (Wilson) |
|---|---|---|---|---|
| Gemma-3-12B (Google) | 9 | 0 | **0.0%** | [0.0%, 29.9%] |
| InternVL3.5-8B (OpenGVLab) | 156 | 0 | **0.0%** | [0.0%, 2.4%] |
| Phi-3.5-Vision-4.2B (Microsoft) | 197 | 0 | **0.0%** | [0.0%, 1.9%] |
| LLaVA-OneVision-7B (community) | 235 | 5 | **2.1%** | [0.9%, 4.9%] |
| Qwen3-VL-32B-AWQ (anchor) | 685 | 1 | **0.1%** | [0.03%, 0.8%] |
| Qwen2.5-VL-72B-AWQ (anchor) | 214 | 0 | **0.0%** | [0.0%, 1.8%] |
| InternVL2.5-8B-AWQ (anchor) | 230 | 0 | **0.0%** | [0.0%, 1.6%] |

**The two modes decouple (Fig. 4).** On clean synthetic dots the base arm **never abstains** yet still
under-counts by **up to 50%**; in microscopy (BBBC005 [48]) abstention is **0.0%** while the bias reaches **−50.1%**.
Conversely, on dense crowds abstention is 50–70% while the answered-only bias is only −19.8% / −29.2%.

**Fig. 4.** The four-panel separation of the two failure modes: abstention and under-count decouple.

(Appendix M.34)

**Legibility is a usable selector, but cannot repair direction.** Keeping the most legible 20% reduces MAE
by **31–66%** while the relative deviation only attenuates from **−85.0%** to **−53.4%** — still a
systematic under-count of more than half (selector AUC **0.753–0.786**). What gates abstention is **blur, not resolution**: downscaling to
15% of the pixels gives almost no abstention (**0.6%**) whereas blurring the *same* image and frames gives
**9.1%** (**+8.6 pp**, paired, $n = 900$); the gate reproduces in three further lineages on a controlled disc
grid, where the permitted contract leaves no zeros (M.19.10).

### 5.8 The two routes to removing abstention, and their price

**Route A — tiling (raise legibility; preserves accuracy)** reduces the ShanghaiTech-A abstention rate from **56.6%** to **0.0%** while leaving direction intact, and lifts the suppressed directional authority
of prompts in the aerial domain (+13.9% whole-image to **+160.4%** at 3×3). **Route B** cannot obtain both. (M.8, M.11)

### 5.9 Model scale: what is bought is knowing whether to answer

Comparing 8B and 32B of one lineage (a clean 4× contrast), scale does not make answers more
accurate: the 8B model's answered-only deviation is **more negative** (Appendices L.1, M.8, M.11).

### 5.10 Aerial domain: the legibility extreme

VisDrone and AI-TOD are the legibility extreme, and their bottleneck is instance **under-resolution**
whereas the crowd bottleneck is overlap (Appendix M.29).

### 5.11 A quantitative consequence of abstention (two more in Appendix M.28)

**(a) Counting abstentions as zero inflates "under-estimation", so a dual convention is required.** On the same data the pooled relative deviation differs between "abstentions counted as 0" and "answered items only" by **61.3 pp** (ShanghaiTech-A), **57.5 pp** (UCF) and **40.6 pp** (AI-TOD and VisDrone)
(M.8). Proposition 4 expresses this gap as $-(1-w)(1+\rho_{\text{answered}})$, so these four values are a
**consistency check on the numbers printed in this paper**, not an independent empirical prediction.

### 5.12 What a single convention costs: the ranking moves

The two conventions are not bookkeeping alternatives. On the **same items** of our own census — up to
**fourteen** configurations over the **four** domains that admit a common item intersection, zero and
non-zero pools pooled within a domain, so that no rank difference can come from different denominators
(the quantities and denominators are defined in M.21) — the convention changes how large a
configuration's measured bias appears, and in the dense domains changes the order:

**Table 5.** What one convention costs. The two ranked columns use **two orderings**: the Spearman is on **|ρ|**, the inversion count on the **signed** ρ.

| domain | configurations | common n | Spearman between the two rankings | largest single \|Δρ\| | rank-pair inversions |
|---|---|---|---|---|---|
| ShanghaiTech-A | 14 | 144 | **0.604** | **48.2 pp** | 17 of 91 |
| UCF-QNRF | 14 | 249 | **0.864** | 36.2 pp | 11 of 91 |
| VisDrone | 8 | 277 | **1.000** | 9.4 pp | 0 of 28 |
| AI-TOD | 8 | 222 | **0.476** | 37.5 pp | 9 of 28 |

A single configuration's measured bias therefore differs by up to **48.2 pp** between the conventions, and
in the dense domains **28 of 182 rank pairs invert** (Spearman 0.604 and 0.864). The aerial domains split:
VisDrone is convention-invariant (**ρ = 1.000**, no inversion) while AI-TOD is the most sensitive cell of all
(**0.476**). A number quoted under one convention is thus not comparable with one quoted under the other —
the operational reading of Proposition 8, and what the released protocol of §7.9 reports as a matter of course.
*(Reproduction: `convention_rank.py`; frozen result `convention_rank_result.json`.)*

**What a decision costs depends on a second convention.** Three decision forms — a **deliverability verdict**, a **service level** and a **selection set** (the three best configurations per dataset) — over five datasets and a 3 × 3 grid
of θ × tol are evaluated under both readings of "answered": as *textual refusals only*, **three verdicts flip** and
the selection sets are **identical in five**; as §M.27 defines them — a numerical `0` is *also* an abstention —
**78 verdicts flip** and the sets differ in **4 of 5**. Whether the convention is a comparability or a decision
problem is convention-dependent; the decision-relevant quantity remains the abstention *mass* (§5.11, M.27).

### 5.13 The same two experiments on a public benchmark (FSC-147)

Everything above uses nine corpora this paper assembled. To check that neither the zero nor the
contract effect is a property of those datasets, we ran the **same instrument** (the same probe, not a re-implementation) on **FSC-147** [7] — a public counting benchmark of
natural images with a different object vocabulary and density range — on a fixed-seed, GT-stratified sample
of **300 test images**. This `instrument-as-is` panel measures responses to a fixed people-counting prompt
on FSC-147 images; since that target need not match the annotated category, these results give no
standard FSC-147 counting accuracy and no implicit abstention, so the readings we give bound the contract effect and do not
estimate it, and target-matched results need separate evaluation on those images:

**Table 6.** The contract gate on FSC-147 (`instrument-as-is`; five of the nine configurations in the panel; the full panel is Appendix M.24.1).

| configuration | base answers 0 | still 0 under `permit` | 95% CI |
|---|---|---|---|
| Gemma-3-12B | 248 / 300 | **0** (0.0%) | [0.0%, 1.5%] |
| InternVL3.5-8B | 273 / 300 | **0** (0.0%) | [0.0%, 1.4%] |
| Phi-3.5-Vision-4.2B | 255 / 300 | **2** (0.8%) | [0.2%, 2.8%] |
| LLaVA-OneVision-7B | 187 / 300 | **0** (0.0%) | [0.0%, 2.0%] |
| Qwen3-VL-32B (BF16) | 277 / 300 | **251** (90.6%) | [86.6%, 93.5%] |

Three readings, one of which is a counterexample, reported as one. **(i) The zero is not a property of
our corpora**: four of five families answer exactly `0` on **62–91%** of a public benchmark's images, so the
phenomenon is not an artefact of the nine datasets above.
**(ii) The gate replicates in eight of nine configurations (≤6%), seven at the frozen ≤5%.** Across the full panel
(Appendix M.24.1) `permit` leaves ≤ 6% of those zeros in **eight**; the exception is the **Qwen3-VL-32B
build, keeping 251 of 277** while the *same* build on ShanghaiTech-A leaves **0 of 62**
(§M.19.8). Its diagnosis is informative: under the three-option `channel` contract
that build leaves **0** zeros — for it the outlet must be **enumerated as an option**, not *permitted* (Appendix M.24.3). The gate is therefore
**family × domain × wording conditional, not universal**, and we state that explicitly, not as a
dense-only caveat. **(iii) Here the convention moves magnitudes, not the ρ ordering** (ρ by up to **44.0 pp**; Spearman **0.983 on the ρ ordering**, 1 inversion of 36) — the asymmetry §5.12 reports for the decision forms. Its sensitivity to the input scale is bounded in Appendix M.41. The two rank correlations behind this paragraph rest on the answered subset of the 300 sampled images, 17–52 images per configuration (Appendix M.24.2); those two figures carry no interval.

### 5.14 A prospective test on an independently sampled panel

Every family above was chosen by us. To test whether the two effects survive a panel the paper did not choose, we
**froze six predictions, their thresholds and the sampling rule before collecting any data** (preregistration
`0a42e6e5bbfa89543ba9fc1522f1b075`, re-issued, traces removed; values unchanged; rule and frame in Appendix M.31).
The rule takes one open-weight family per lineage, excludes every family used above, and yielded **six families in
six lineages with no Qwen model**, five of those lineages appearing nowhere in §3–§5. The pools are the census-defined ones, which do not depend on the
new models, and the instrument is the frozen probe, byte-identical in prompts and parser to the census probe.

**The gate replicates in the dense domains; the zero rate is a property of the
domain, not the family; the contract knob’s ordering margin passes its first conjunct only.**
Under `permit` the answered zero falls to **0.0%** in both dense domains for
all five families that honour the JSON contract; pooled over four domains **four of six** families reach ≤2%
(0.00%, 0.00%, 0.00%, 0.18%). The two exceptions are diagnostic, not fatal: Idefics3-8B leaves **7.23%** on sparse
aerial items whose ground truth is one to three objects — a missed tiny target, not a refused outlet — and
deepseek-vl2-tiny leaves **48.28%**, never abstaining in the aerial domains while its dense-domain output is 99%
unparsable, a format failure and a genuine family × domain outlet failure at once.
The contract knob moves the zero rate by at least 10 pp more than the resolution knob in **10 of 12** qualifying
cells (83%; exact binomial $P(X\ge10\mid n=12, p=1/2)=0.019$), while the resolution knob alone never moves it by more than **32.0 pp**. Decomposing the 24 cell-level
rates gives a variance component of **0.0959** for domain against **0.0037** for family — a factor of **25.8** —
with a bootstrap interval that excludes zero — the frozen record value **`[0.0831, 0.1002]`**, item level (Appendix M.31.2). That is a fixed, partially protocol-deviating panel statement, not a population interval over families.

**Four of the six pre-registered predictions failed outright** (a prediction fails unless every
conjunct passes; P2's second is not evaluable), and they bear on scope, not on the
measurement: the convention can change the top-ranked family in **two of four** domains, and the exemplar
arm removes the zero (by **58–93 pp** in five of six families) without making the counts accurate — **removing the zero is not the same as becoming able to count** (full verdicts and per-family numbers:
Appendix M.31.2–M.31.4). **On hosted endpoints the zero answer is contract-dependent, not absent.** Three proprietary deployments, on the same
**253** items, never answer zero under a number-only contract (**0.0%**; Wilson 95% upper bound **1.5%** on 0 of 253); permitted to abstain they abstain
explicitly on **98–100%** of those items (residual 0.00%); and their numbers are more accurate than the open
families' (**34–47%** median relative error against **59–83%**). An observable zero answer can therefore be
removed by the contract here too; whether the same latent state underlies it is **not identified**.

**What the same correction does to a published number.** The convention term is not a rounding detail: on
the public benchmark the two conventions differ by a median of **32.9** counts and by up to **45.6**, while
the spread between its nine configurations under the published convention is **2.6** counts — the convention
effect is **12.7 times** the between-system spread, and the two conventions reorder the panel (**seven of
36** pairs invert, Spearman **0.783** on the MAE ordering). Reporting one convention without the abstention mass therefore
publishes an ordering of abstention propensity; the correction needs no re-run, since
$\mathrm{MAE}_A=(1-w)\,\mathrm{MAE}_B+w\,\overline{\mathrm{GT}}_{\text{abstained}}$ recovers it from
any stored output (Appendix M.35).

## 6. Results III: Density regression — direction is a function of the input-scale protocol

### 6.1 Density regression has a scale freedom parameter that must be calibrated per domain

On the dense end, density regression is the most accurate family under a fixed protocol but the least
directionally controllable: its predicted totals scale multiplicatively with inference input size, so
$\rho$ is a function of the scale protocol, not of the model alone, and the family carries a
**scale freedom parameter that must be calibrated per domain**. Because a reproduction of CSRNet required
us to retire an implementation defect, all density-regression span figures here use the **official
DM-Count weights** on the identical item set and grid: **20.1–34.3 pp**, against **10.1 pp** for official
**P2PNet** weights [1], and 107–1433 pp for the retired reproduction.

### 6.2 Three further properties, and their protocols

Three further measurement properties matter here (**Appendix H**): a
counting-consistency term on the log ratio between the predicted integral and the ground-truth count
reduces the seed-to-seed spread by roughly an order of magnitude and removes most of the systematic
positive offset the uncorrected objective leaves behind — a **remedy for a training artefact**, not a new
architecture (H.1); the abstention rate is stable **only under greedy decoding**, since under
sampling it co-varies with temperature and sample count, so our protocol fixes temperature
at 0 (H.2); and the collapse of the VLM contract arm's output under overlap occurs for both 8B and 32B models
at comparable overlap levels, making it a property of the task structure, not of model capacity
(H.3).

## 7. Discussion

### 7.1 Legibility, not OPM, is the stratifying variable

The conventional density axis conflates "how many objects are there" with "how hard is each one to
ascertain". Across ten domain/dataset points the correlation between abstention rate and object count is
only $r = +0.33$, with no explanatory power, whereas the legibility proxy orders the same points
consistently. It is used here as a **stratifier**, not as the paper's primary claim: the contract result
(§5.7) and the convention result (§5.12) hold without it. A downstream user who wants a rule, not a
stratifier should read §7.7 and Appendix M.20 first.

### 7.2 Same-scale accuracy comparison across the three families

Bringing the three families to a common effective instance scale inverts the usual ranking (full table in
Appendix F.1). A single density-regression
number is not a comparable quantity unless the weight set is specified. (Appendix M.11)

### 7.3 The response spectrum of knobs: the ordering, and what is not predicted

**What this design can and cannot resolve.** Ten unit values on four sides — six knobs map onto four sides, and Appendix F.2 reconciles the three unit sets — resolve to the design's own noise
floor, **2.15–6.46 pp**, and the separating split (**1.6 pp**, corrected $p$ **≥0.075**) lies below it, so
**no gap whatsoever would be certified by this test**; a 5-vs-5 split would need **6.5 pp** for 80% power.
**We therefore do not claim a separable structure**; what the design supports is the **ordering**, specifically
under the **pooled relative deviation** (Appendix F.7, M.37). **The ordering is stable under the two obvious deflations, with intervals.** Re-estimated
on a **common level count** with each ladder's extreme level removed, it still comes out at Spearman
**0.999 / 0.981 / 0.991** over 24 (knob × domain) units, and at **0.983 / 0.987 / 0.983** on a **fully
recomputable** unit set at the same level count (31 units; Appendix M.37). A bootstrap that resamples whole units puts it at
**0.943–0.996** (31 units) and **0.834–0.984** (36 units, k=3), and **clustering by knob gives 0.913–0.994**, while the wider resampling gives **0.711–0.998**;
a label-permutation test gives $p<5\times10^{-5}$; leaving out any single knob (**36** units) keeps it at **0.883–0.970**; per-unit spans with caliber
intervals are plotted in **Fig. F.17** (Appendix F.12). It also comes out **exactly** the same under shared
affine calibration (Proposition 5: `span ↦ s·span`) and under no calibration — the M.37 held-out third gives
median **0.995**, interval **0.984–0.998**, above 0.9 in **200 of 200** splits — but not when each unit
is re-fitted independently: **0.810 / 0.536** over 8 / 36 units, per-unit family medians **0.41–0.54**
(isotonic **0.571 / 0.521**). Measured $s$ spans **0.027–2.352**, so a compressor must vary its factor **across units**; **no granularity validated here does so while preserving the ordering, so transfer is unverified rather than excluded** (per-domain
**0.732**; Appendix M.37). The claim is scoped to the first two calibers, and the VLM unit's build-sensitivity is bounded in **Appendix M.18.8**
(its level moves 90.3 pp across five builds; its contract effect does not). The *magnitudes* are
not caliber-portable: the in-domain detector ladders give **96–196 pp** person-matched and **353–508 pp**
all-detections, so a magnitude is quoted with its **caliber** (Appendix F.2; M.37).
**No scale-free form of the span — equal-count gridding, endpoint removal, or the three M.37 calibration
families — makes cross-knob magnitudes invariant, and the ordering also survives normalising each span by
its knob travel (Appendix F.10; M.37).** **On two counting domains this paper has never used it passes on one and is a knife-edge that fails on the other (M.49).** **Under a common error-and-cost budget the ordering is
not preserved and half the units admit no admissible pair at all (Appendix M.45).** **What the spectrum supports is an ordering rule, and we state it as one.** **Availability is decidable**:
"is `pred/gt ≥ 1` at the loosest admitted level?" predicts reachability with **zero exceptions** across three
lineages and nine cells. And **the ordering is the surviving quantity** within the level sets and calibers measured here: **quote a magnitude only with the grid density and the calibration caliber that produced it.** **We do not turn this into a deployment rule**: the ordering is descriptive, and our own candidate for the magnitude (Proposition 3) is a component of the definition and is withdrawn; the ordering itself is measured, not assumed.

### 7.4 The high response of the detector threshold is domain-conditional

The detector threshold is the largest-response knob, but its authority is **domain-conditional**: in the aerial domain the full in-domain ladder moves $\rho$ across the whole span, whereas in dense-crowd domains **no lineage reaches `pred/gt ≥ 1` at any threshold** and the span collapses close to the noise floor; the same architecture and knob give a **3.5×** smaller span under a training-domain swap alone (Appendix M.8).

### 7.5 Language-side contracts: channel independence, and one excluded branch

Two facts survive (per-arm numbers are labelled by model × domain × contract arm × convention, and each is a pooled relative deviation on the common item intersection; Appendix G.1). **`choice` rewrites the value without passing through abstention**: it moves the relative deviation across zero while the abstention rate barely moves, and it works in dense domains too. One correction: on the `choice` arm the 32B model shows a pooled deviation of
only +0.9%, but the grid's value 50 sits close to that domain's median GT (50.5) and 46.6% of answers land
on it — **a property of the grid design, not calibration**. (M.11)

### 7.6 Three mechanism hypotheses, tested and excluded

**All three candidate explanations are excluded** (mediator, `choice`-rewriting, `forbid0`-conversion), so we
treat the `forbid0` mechanism as **unresolved, not explained** (Appendix G.2); the tests and their per-arm numbers are in Appendix M.30.

### 7.7 Deployment implications: what a user can and cannot have

The legibility score can be read as a criterion for **"is this input still inside the model's nominal
operating range?"** — a requirement forming independently in the perception literature, where detectors fail
silently under blur, noise, compression and resolution change ([49]–[50]). **Legibility can decide whether to
answer; changing the direction requires changing the protocol, the prompt, or the family.** It is an **analytical diagnostic**, not a reporting or gating rule — it needs annotation boxes, so the
**adoption recipe** for a third party with none is in Appendix M.22. The three annotation-free signals
(cross-scale, cross-phrasing, cross-family agreement) were tested on **45** (family × domain) cells against a bar
fixed before the runs (AUC ≥ 0.65 *and* the error on the most-agreeing 20% at ≤ 0.6× the overall error): **1 of 45
passes**, and in the aerial domains the agreement signals are *anti*-correlated with error, because the other
models share the same domain-specific bias. Quality, like abstention (Proposition 1), is therefore **not
identified by the three tested output-level signals** (Appendices M.23, M.14).

### 7.8 Enumeration versus regression: what this corpus measures

Enumeration-style counting is more directionally controllable than regression-style counting on this
corpus: the regress-then-round pipelines we test lose the property being measured. (Appendix M.26)

### 7.9 An adoptable protocol, released as running code

The transferable object is a **protocol**, not a finding: `adopt_contract_probe.py` runs the three
arms against any OpenAI-compatible endpoint given only images — no dependency on
our corpora, annotations or detectors, and prompt texts byte-identical to the census probe — and
`adopt_report.py` prints the **channel diagnosis** with its Wilson interval and the **item-answered fraction** $w$
(not Proposition 4's ground-truth-weighted $w$); the two deviations need reference counts on the same scored subset, so without them only that diagnosis is licensed. Records are kept only for completely paired inputs: the base
arm's zero set is the denominator for every arm, and a missing arm reads as an undecidable partial, not a dropped denominator (M.22). Released API summaries give the checks only; the per-call records and the driver that lets one rebuild them ship with the package (M.11.2, M.37).
The thresholds are frozen in `adopt_criteria.json`
(residual ≤5% read from the point estimate — several cells rest on 2–25 items, so their upper bounds are wide: direction readings, M.46(a) ⇒ contract-set; >30% ⇒ record a counterexample and retry with the three-option wording; below the 7 pp noise floor ⇒ immaterial). Adoption costs one serving session
and yields the two quantities §5.3–§5.13 turn on, making these comparisons reproducible
elsewhere (M.22). In a first independent use it was run, unchanged, on two corpora whose recipe
residual had never been reported including a large unconstrained dense-crowd release (JHU-CROWD++ [51]), with the criteria
fixed before the runs (Appendix M.46).

## 8. Limitations

### 8.1 Disclosure of measurement fragility

Seven counts of measurement fragility are itemised with item-level impact in **Appendix M.32**: **Two runner defects**
and, separately, a dead parse branch; **Run-to-run non-determinism**, characterised below; **Graded isolation**, with a
residue ledger and **a census of anomalous predictions**; **No attention-based criterion**; and **Per-cell intervals are lower bounds**, the across-repeat term exceeding the interval width by roughly a factor of two where levels are few
(§A.2). No aggregate above depends on the affected runs (§3.7, §5.1). The aggregate change in ME is within
**0.19** counts, and where the corpus contains an independent re-run the aggregate $\rho$ differs by at most
**0.81 pp** across the six such pairs. Item-level claims are made only on our own stack: local stacks at batch ≤ 2 reproduce exactly, hosted endpoints do not (§A.3). Non-determinism is documented for LLM inference [52], [53] and for evaluation harnesses [54], [55].

### 8.2 Scope limitations

**The optimal input fidelity was not located**: whether **increasing** fidelity beyond the native scale becomes harmful was not measured — a non-monotonicity existing work suggests may exist. **The attribution boundary is behavioural, not anthropomorphic.** We read an answered zero as **mode
collapse** — output degenerating onto the mode or a prior integer — not as a human-like refusal, and claim
nothing about intent; the operationalisation is stated so that it can be replaced.

**The detector lineage is narrow**, resting on YOLO with RetinaNet and Faster R-CNN as secondary lineages; a
broader sweep would establish whether §4.1's and §4.5's properties are family or architecture properties. The exemplar condition is measured on **one benchmark, three boxes and
six families** (§5.14), so it bounds the zero without mapping the few-shot counting family; its **384-px**
resolution is the release's own short-side constraint, and **M.41** varies it (contract arms ≤ **2.0 pp**,
exemplar abstention **10.7 pp** across scales, **11.0 pp** in one step). The three hosted endpoints are
deployments we cannot pin to a build, so their numbers are dated, not frozen.

**The abstention interpretation rests on a two-channel assumption.** It is **partly testable**, and its observable part is
tested (§5.7): the controls measure the way the outlets are *used* on the pools we state, not whether every answered zero is latent abstention. The census **holds the serving stack fixed** and varies the contract and
the build; three residual limits are in **Appendix M.33**. A **true-zero control** bears on that condition: on **306** crops whose correct answer is zero by the dataset's own annotation, the
three-way contract returns `no_people` on **47–87%** of items **of the easy stratum**, whereas on dense items the census had
answered zero the same models return `no_people` on **0–1%** and `cannot_judge` on **98–100%** —
the two outlets' **sensitivity and specificity on stated pools**, **not** the channel's precision. **On these pools answering zero is correct behaviour**, so the control measures sensitivity and says nothing about the mixed corpus (§3.8; Appendices M.21, M.38, M.40).

**The corpus is dominated by one lineage, which bounds every frequency claim.** Most of the ~620k records
come from the Qwen family, so the abstractions' frequency statements are claims about that family and the
configurations measured alongside it, not about vision-language models in general. **The contract result is
not lineage-bound**: on the public benchmark FSC-147 it holds in **8 of 9 configurations** on the same `instrument-as-is` panel (§5.13) — with the Qwen3-VL-32B build
as the reported counterexample there. The abstention *completeness* claim still rests on the Qwen family ($\kappa = 550.6$) and the smaller
InternVL subset ($1/(\kappa+1) = $ **30.31%**). Every corpus-level rate was measured with **Chinese**
prompts, so we repeated the arms in a byte-frozen English rendering on the same items: the channel result
is language-robust (`no_people` differs by at most **7.2 pp**), but the answered-zero rate is not — the
anchor lineage answers zero on **60.2%** of the dense pool under Chinese and **17.5%** under English, a
**42.7 pp** drop **on the BF16 build** — a pooled dense-pool figure; the per-domain drops on the same build are **18–22 pp** and come from a different item set (Appendix M.39). The §5.5 shares are scoped to the prompt language and the **one anchor build** (**the share holds at
BF16, not the rate**; eight of nine fall short — the ninth is that checkpoint at BF16; M.19.15). The true-zero pools differ by **54.7 pp**, so $p\approx1$ is not transferable (Appendix M.21.9).
Two further limits: the abstention **share** leaves its unit interval when the net deviation is not an
under-count (§3.8) — three of twenty cells, unmeasured, not clipped, the Table 3 pp terms the fallback — and the
**English** prompt lowers the answered-zero rate on the dense domains only, by **15–26 pp** on the corpus's own
**third-party 4-bit** build, where two of the twenty cells stay outside the unit interval and every absolute rate
carries a **~1.3% item-level stack band** (M.19.16, M.46(c)). **The 8-bit rows were served weight-only, not weight-and-activation 8-bit** — the host's compute capability is **8.0** and W8A16 needs **8.9**, so the loader takes the weight-only path — and they therefore bound the build, not that path (M.46(c)).

**Domain composition is not systematic**: the nine datasets span a legibility range, not a stated population, so
domain-level statements describe these domains, not a distribution.

**The corpus was not pre-registered as a whole.** Only the sub-experiments explicitly marked as pre-registered
had their criteria written before the data were examined (Appendix G.1, G.2 quote each as frozen); the rest are
post hoc, including the tiling level, weight set and aggregation convention, so both conventions and the
weight-set range are reported wherever they diverge. **Statistical power for the spectrum is low** (four knob
sides, ten units), and the candidate claim rests on a permutation test over single split points plus bootstrap
intervals, not on a modality test.

## 9. Conclusions

We set out to make the **direction** of counting error measurable and found that, for one anchor build under
Chinese prompts and GT weighting, the observed failure is an answered-zero output rather than a signed under-estimate; the contributions are therefore **two findings, plus the apparatus
that makes them checkable**. The first is a **measurement dimension**: signed error direction, reported with
the convention under which it is read, because the two conventions differ by tens of percentage points on
the same data. The second is a
**observed contract-dependence of the answered zero**: the channel through which a model declines to answer is set by
the output contract, not by the lineage, so the outlet is a property of the serving configuration (§5.7). The spectrum replicates in its **ordering**, not its magnitudes, and then only under the **level sets and calibers compared**: with **ten** units and a
separation of **1.6 pp** below the noise floor (corrected $p\approx0.075$), it supports a **ranking**, and its per-cell intervals are sampling **lower bounds** (§8.1). The weakest parts are stated as such in
§8; the most consequential open question is whether the abstention channel can be given a statistical
guarantee, not a measured rate (§7.7). **Scope, stated where it binds.** Every frequency claim above holds **for the configurations and builds
measured**: within the dense domains five deployments of a **single** 32B checkpoint differ by up to
**90.3 pp** in their answered-zero rate but only **6–11 pp** on the abstention share itself, the quantity the
headline is about (Appendix M.18.9; the contrasts behind that boundary are in §8.2).

## Declaration of generative AI and AI-assisted technologies in the manuscript preparation process

During the preparation of this work the author(s) used a panel of large language models, accessed through their vendors' application programming interfaces, to simulate peer review of the manuscript and to audit the internal consistency of the reported numbers and cross-references. These tools were not used to generate the text; the author(s) reviewed and edited the content and take(s) full responsibility for the published article.

## CRediT author contribution statement

**Author contributions.** Conceptualization, methodology, software, validation, formal analysis, investigation, resources, data curation, writing — original draft, writing — review and editing, visualization, supervision, project administration: the author.

## Acknowledgements

None.

## Data availability

The image corpora are public datasets, cited above. The derived per-image prediction records, analysis scripts and run logs that recompute
the released aggregate numbers are released or flagged at https://github.com/YBP2005/P3 (CC BY 4.0), with per-file MD5s; the release-only gate and inputs absent from the package are in `README.md`. `MANIFEST.csv` lists the tree path by path with each file's byte count and MD5; an independent audit checked the bytes and the MD5s of a **selected subset** of those records and not of every one, so listed-file coverage holds for that subset alone, and integrity says nothing about whether the analyses are correct.

## Funding

This research did not receive any specific grant from funding agencies in the public, commercial, or
not-for-profit sectors.

## References

1. Song, Q., Wang, C., Jiang, Z., et al. Rethinking Counting and Localization in Crowds: A Purely Point-Based Framework. ICCV 2021. https://doi.org/10.1109/ICCV48922.2021.00335.

2. Narasimhan, H., Menon, A., Jitkrittum, W., et al. Plugin Estimators for Selective Classification with Out-of-Distribution Detection. preprint arXiv:2301.12386, 2023.

3. Geifman, Y., El-Yaniv, R. SelectiveNet: A Deep Neural Network with an Integrated Reject Option. ICML 2019. PMLR 97:2151-2159. https://proceedings.mlr.press/v97/geifman19a.html.

4. Denis, C., Hebiri, M., Zaoui, A. Regression with Reject Option and Application to kNN. NeurIPS 2020. preprint arXiv:2006.16597.

5. Zhang, Y., Zhou, D., Chen, S., Gao, S., Ma, Y. Single-Image Crowd Counting via Multi-Column Convolutional Neural Network. CVPR 2016. https://doi.org/10.1109/CVPR.2016.70.

6. Chen, Z., Wang, W., Cao, Y., et al. Expanding Performance Boundaries of Open-Source Multimodal Models with Model, Data, and Test-Time Scaling. preprint arXiv:2412.05271, 2024.

7. Ranjan, V., Sharma, U., Nguyen, T., Hoai, M. Learning To Count Everything. CVPR 2021. preprint arXiv:2104.08391.

8. Lempitsky, V., Zisserman, A. Learning To Count Objects in Images. NIPS 2010.

9. Guo, X., Huang, Z., Shi, Z., et al. Your Vision-Language Model Can't Even Count to 20: Exposing the Failures of VLMs in Compositional Counting (VLMCountBench). preprint arXiv:2510.04401, 2025.

10. Srinivasan, T., Hessel, J., Gupta, T., et al. Selective "Selective Prediction": Reducing Unnecessary Abstention in Vision-Language Reasoning. Findings of ACL 2024. preprint arXiv:2402.15610.

11. Chow, C. K. On optimum recognition error and reject tradeoff. IEEE Trans. Inf. Theory 16 (1970) 41-46. https://doi.org/10.1109/TIT.1970.1054406.

12. Madhusudhan, N., Yadav, V., Lacoste, A. Knowing When Not to Answer: Evaluating Abstention in Multimodal Reasoning Systems. preprint arXiv:2604.14799, 2026.

13. Pramono, F., Cai, J., Kulkarni, S. TRAPSBench: Vision-Language Models Encode but Fail to Express Epistemic Restraint. COLM 2026. preprint arXiv:2608.13167.

14. Ortiz, J. Explicit Abstention Knobs for Predictable Reliability in Video Question Answering. preprint arXiv:2601.00138, 2025.

15. Zhang, H., Feng, Y., Liu, H., et al. The Uncontrolled Variable: Vision-Language Refusal Is Conditioned on the Image-Attachment Interface, and Not Robust to Irrelevant Image Properties. preprint arXiv:2609.26174, 2026.

16. Trick, L. M., Pylyshyn, Z. W. Why are small and large numbers enumerated differently? A limited-capacity preattentive stage in vision. Psychol. Rev. 101(1):80–102, 1994. https://doi.org/10.1037/0033-295X.101.1.80.

17. Fu, Y., Li, F., Liu, X., et al. NumerosityVLM: A Cognitively Inspired Benchmark for Interpreting Numerosity Representations in Vision-Language Models. preprint arXiv:2608.15425, 2026.

18. Yu, F.-S., Li, J., Wang, X., et al. Large, Complex, and Realistic Safety Clothing and Helmet Detection: Dataset and Method. preprint arXiv:2306.02098, 2023.

19. Paiss, R., Ephrat, A., Tov, O., et al. Teaching CLIP to Count to Ten. ICCV 2023. https://doi.org/10.1109/ICCV51070.2023.00294.

20. Acharya, M., Kafle, K., Kanan, C. TallyQA: Answering Complex Counting Questions. AAAI 2019. https://doi.org/10.1609/AAAI.V33I01.33018076.

21. Djukic, N., Lukezic, A., Zavrtanik, V., et al. A Low-Shot Object Counting Network With Iterative Prototype Adaptation. ICCV 2023. preprint arXiv:2211.08217.

22. Liu, C., Wu, H., Xie, W. Count Anything at Any Granularity. preprint arXiv:2605.10887, 2026.

23. Huang, Z., Dai, M., Zhang, Y., et al. Point, Segment and Count: A Generalized Framework for Object Counting. CVPR 2024. preprint arXiv:2311.12386.

24. El-Shangiti, A., Nurgazy, A., AlQuabeh, H., et al. The Count Is There, but Misaligned: Understanding and Correcting Counting Failures in VLMs. preprint arXiv:2607.09544, 2026.

25. Anh, D., Irawan, P., Vo, T. Counting to Four is still a Chore for VLMs. preprint arXiv:2604.10039, 2026.

26. Nguyen, G., Huang, Y., Hoai, M. Can Current AI Models Count What We Mean, Not What They See? A Benchmark and Systematic Evaluation (PairTally). preprint arXiv:2509.13939, 2025.

27. Pang, X., Hou, Y., Wang, J., Sachan, M. Unveiling the Visual Counting Bottleneck in Vision-Language Models. ICML 2026. preprint arXiv:2605.30170.

28. Pothiraj, A., Stengel-Eskin, E., Cho, J., et al. CAPTURe: Evaluating Spatial Reasoning in Vision Language Models via Occluded Object Counting. ICCV 2025. preprint arXiv:2504.15485.

29. Guo, C., Pleiss, G., Sun, Y., et al. On Calibration of Modern Neural Networks. ICML 2017. preprint arXiv:1706.04599.

30. Tamarapalli, J., Grover, R., Pande, N., et al. CountQA: How Well Do MLLMs Count in the Wild? preprint arXiv:2508.06585, 2025.

31. Li, S., Chen, J., Sharma, K., et al. PushupBench: Your VLM is not good at counting pushups. preprint arXiv:2604.23407, 2026.

32. Zhu, P., Wen, L., Du, D., et al. Detection and Tracking Meet Drones Challenge. IEEE TPAMI 44(11), 2022. https://doi.org/10.1109/TPAMI.2021.3119563.

33. Wang, J., Yang, W., Guo, H., et al. Tiny Object Detection in Aerial Images. ICPR 2021. https://doi.org/10.1109/ICPR48806.2021.9413340.

34. Tian, Y., Ye, Q., Doermann, D. YOLOv12: Attention-Centric Real-Time Object Detectors. NeurIPS 2025. https://doi.org/10.52202/085713-2627.

35. Akyon, F., Altinuc, S., Temizel, A. Slicing Aided Hyper Inference and Fine-tuning for Small Object Detection. ICIP 2022. preprint arXiv:2202.06934.

36. Lin, T.-Y., Maire, M., Belongie, S., et al. Microsoft COCO: Common Objects in Context. ECCV 2014. https://doi.org/10.1007/978-3-319-10602-1_48.

37. Ren, S., He, K., Girshick, R., Sun, J. Faster R-CNN: Towards Real-Time Object Detection with Region Proposal Networks. IEEE TPAMI 39(6), 2017. https://doi.org/10.1109/TPAMI.2016.2577031.

38. Lin, T.-Y., Goyal, P., Girshick, R., et al. Focal Loss for Dense Object Detection. ICCV 2017. https://doi.org/10.1109/ICCV.2017.324.

39. Bai, S., Cai, Y., Chen, R., et al. Qwen3-VL Technical Report. preprint arXiv:2511.21631, 2025.

40. Lin, J., Tang, J., Tang, H., et al. AWQ: Activation-aware Weight Quantization for LLM Compression and Acceleration. preprint arXiv:2306.00978, 2023.

41. Frantar, E., Ashkboos, S., Hoefler, T., Alistarh, D. GPTQ: Accurate Post-Training Quantization for Generative Pre-trained Transformers. preprint arXiv:2210.17323, 2023.

42. Bai, S., Chen, K., Liu, X., et al. Qwen2.5-VL Technical Report. preprint arXiv:2502.13923, 2025.

43. Ma, Z., Wei, X., Hong, X., et al. Bayesian Loss for Crowd Count Estimation with Point Supervision. ICCV 2019. https://doi.org/10.1109/ICCV.2019.00624.

44. Li, Y., Zhang, X., Chen, D. CSRNet: Dilated Convolutional Neural Networks for Understanding the Highly Congested Scenes. CVPR 2018. https://doi.org/10.1109/CVPR.2018.00120.

45. Wang, B., Liu, H., Samaras, D., Nguyen, H. Distribution Matching for Crowd Counting. NeurIPS 2020. preprint arXiv:2009.13077.

46. Han, H. Off-Target Effects of Response-Style Alignment in a Korean 27B Language Model. preprint arXiv:2609.11291, 2026.

47. Idrees, H., Tayyab, M., Athrey, K., et al. Composition Loss for Counting, Density Map Estimation and Localization in Dense Crowds. ECCV 2018. https://doi.org/10.1007/978-3-030-01216-8_33.

48. Ljosa, V., Sokolnicki, K. L., Carpenter, A. E. Annotated high-throughput microscopy image sets for validation. Nat. Methods, 2012. https://doi.org/10.1038/nmeth.2083.

49. Becker, S., Weiss, S., Hübner, W., et al. Self-Aware Object Detection via Degradation Manifolds. preprint arXiv:2602.18394, 2026.

50. Kumar, D., Darabi, N., Tayebati, S., et al. Beyond Confidence: Adaptive Abstention in Dual-Threshold Conformal Prediction for Autonomous Systems. Proc. 2025 IEEE International Conference on Omni-layer Intelligent Systems. preprint arXiv:2502.07255.

51. Sindagi, V. A., Yasarla, R., Patel, V. M. JHU-CROWD++: Large-Scale Crowd Counting Dataset and A Benchmark Method. IEEE Trans. Pattern Anal. Mach. Intell., 2020. https://doi.org/10.1109/TPAMI.2020.3035969.

52. Yuan, J., Li, H., Ding, X., et al. Understanding and Mitigating Numerical Sources of Nondeterminism in LLM Inference. preprint arXiv:2506.09501, 2025.

53. Fu, T., Martínez, G., Conde, J., et al. Beyond Reproducibility: Token Probabilities Expose Large Language Model Nondeterminism. IEEE Trans. Comput., 2026. preprint arXiv:2601.06118.

54. Fang, Z., Jiang, Z., Chen, H., et al. Dataset-Level Metrics Attenuate Non-Determinism: A Fine-Grained Non-Determinism Evaluation in Diffusion Language Models. preprint arXiv:2604.13413, 2026.

55. Mustahsan, Z., Lim, A., Anand, M., et al. Stochasticity in Agentic Evaluations: Quantifying Inconsistency with Intraclass Correlation. preprint arXiv:2512.06710, 2025.

## Supplementary material

Item-level tables, protocols, convention notes and pre-registered criteria moved out of the main text are
provided as a **separate supplementary file** (appendices **A–M and Z**); where the two disagree, the main text
governs.

