# Reproduction package — *Abstention dominates the aggregate under-count*

Source data, code, figures and audit scripts for the manuscript

> **Abstention dominates the aggregate under-count: signed error direction in object counting with
> vision-language models** (submitted to *Pattern Recognition*).

Everything reported in the paper is reproducible from the files here. No number in the manuscript was
typed in from memory: each is either computed by a script in `code/`, or taken from a per-image record in
`data/derived/`, and the arithmetic identities are re-checked by assertions.

**Scope of that claim, stated because it is narrower than it may read.** The assertions live in
`code/analysis/en_check.py`, which is the authors' **pre-submission gate for the working tree**: it reads
Chinese-language source drafts, evidence records and frozen result files that are deliberately **not** part of
this released package — of its **56** required inputs, **36** (in **6** classes: source drafts, evidence
records, pagination/submission artefacts, reference-retrieval records, frozen analysis results and run logs)
are not here — so it **cannot be run from this package alone**. What is reproducible from this package is
every script in `code/` that reads only `data/derived/`, and each number those produce is the number printed
in the paper. This README, `*.md` in `manuscript/`, the figures, and `data.zip`/`MANIFEST.csv` recompute. The
gate is shipped for transparency, not as a runnable entry point; it is released unmodified and has not been
weakened for release.

## Contents

| Path | What it is |
|---|---|
| `data/derived/` | **All per-image prediction records** (2,338 CSV files **at the time of the §M.21.9(e) audit**; the corpus has grown since — the count is a snapshot, not a fixed size) — the released corpus: detection ladders, tiling ladders, density-regression runs, prompt-family and contract arms, aerial and microscopy domains, VLM and detector families. |
| `data/derived/e2/` | The abstention-channel **census (E2)**: 558 result files = 14 configurations x 6 contracts x {zero pool, non-zero pool} over five usable domains (st_a, st_b, ucf, VisDrone, AI-TOD; CountBench is excluded — see *Known limitations*). Files prefixed `nz__` are the non-zero pool. |
| `data/derived/e1/` | The discriminating experiment (E1) on the abstention channel: 48 cells over five configurations x two domains x up to six arms. |
| `data/derived/corpus/` | The nine whole-image corpus tables behind the abstention decomposition. |
| `data/gold/` | Gold-standard counts (`counts.csv`) for ShanghaiTech and UCF-QNRF: file name -> target count. |
| `code/experiments/` | The runners that produced the corpus (one script per experiment, in the order they were run), including the E2 census drivers (`h20_exp_v6.sh`, `h20_exp_v7c.sh`) and `make_19e.py`, which derives the E2 probe `19e_probe_multi.py` from `19b_e1_probe.py` deterministically — it re-reverts its own patch set and asserts byte-identity with the original, so the six-line difference between the two probes is auditable rather than asserted. |
| `code/analysis/` | Measurement, auditing and verification scripts (see below). **Prefix map:** where the supplementary material cites a reproducibility script as `analysis/work/<name>.py`, that file is released here as `code/analysis/<name>.py` — `analysis/work/` is the authoring path, not a directory of this package. Every script resolves its inputs through `code/analysis/_repro_root.py`; see **How to run: the package root** below. |
| `figures/` | The 14 finished figures (PNG). Fig. 1-4 of the manuscript are the first four of these. |
| `manuscript/` | English manuscript and supplementary material (Markdown source), the PR-layout `.docx` (`PaperB_manuscript_PR_layout.docx`), the Highlights file, the cover letter, the E1/E2 evidence records, the review-control evidence record, and the frozen pagination measurements. |
| `env/` | Serving configuration evidence (vLLM log for the self-hosted 4-bit stack) and, in `env/h20_v7c_logs/`, the E2 census run logs (serving starts, per-arm probe logs, per-cell wall-clock). |
| `MANIFEST.csv` | `path, bytes, md5` for every file in this package **except the manifest itself and the derived `data.zip`**, which is rebuilt from `data/` by the sync step and is therefore fully covered by the rows below it. (Disk file count and row count therefore differ by exactly those two.) |
| `LICENSE` | CC BY 4.0. |

## How to reproduce the main results

| Claim in the paper | Reproduce with |
|---|---|
| Abstention share of the under-count (82–94%, base arm; **0–99.4%** over all arms) | `code/analysis/recompute_S.py` over `data/derived/corpus/` — prints `w`, `rho_answered`, `rho_total` and the closed form `S` per domain and arm. (The `42.5%` that appears beside these numbers in the paper is a **relative-deviation floor** of Mode A, *not* an abstention share; see §5.7's parenthetical.) |
| The identity behind Proposition 4 / the dual-convention gap (61.3 / 57.5 / 40.6 / 40.6 pp) | same script; the identity `(1-w)(1+rho_ans)` reproduces every printed gap to <= 0.04 pp. |
| The abstention channel is set by the output contract (E1: 1591/1591 explicit abstentions, median 2.463-9.452x when abstention is forbidden) | `data/derived/e1/*.csv` (raw responses included); summarised by `code/analysis/e1_evidence.py`. |
| **The gate is the abstention token, not the enumeration demand** (E2 census: `enum`/`locate` arms produce zero explicit refusals while the same prompt plus one abstention token converts 98-100% of the items) | `code/analysis/e2_v7c_analysis.py` over `data/derived/e2/` (its §M.18.2 table); the arm prompts are in `code/experiments/19e_probe_multi.py`. |
| **Item-level pairing**: of the items a configuration answered 0, offering an abstention option removes the zero in 46 of 52 (model x domain) cells and the three-option `channel` contract in 52 of 52 | `code/analysis/e2_v7c_analysis.py`, section 3 of its report; the per-cell counts are re-derived from the raw CSVs by `code/analysis/verify_s11.py`. |
| **The two kinds of answered zero** (dense: build-specific, 9% vs 99% for two builds of one checkpoint; aerial: 11 of 12 configurations at 62-99%) | `code/analysis/e2_v7c_subset.py` (common-150 comparison) and `e2_v7c_analysis.py`. |
| The zero is not a parsing artefact (audit of all 2,496 corpus rows) | `code/analysis/corpus_parse_audit.py` over `data/derived/corpus/`. |
| The tiling ladder (56.6% -> 6.0% (2x2) -> 0.0% (4x4 and finer) on ShanghaiTech-A) | `code/analysis/tile_ladder.py` over `data/derived/tile_results/` + `data/gold/`. |
| **The span spectrum is not a function of the scanning grid** (ordering preserved at Spearman 0.999 / 0.981 / 0.991 over 24 knob x domain units; the detector-threshold **magnitudes** are governed by the caliber, not by the grid) | `code/analysis/span_equalcount2.py` over `data/derived/`; frozen result `code/analysis/span_equalcount2_result.json`; written up in supplementary F.10/F.11. **Withdrawn:** the superseded `span_equalcount.py` and its `span_equalcount_result.json` are kept here **byte-identical for audit only** — that pair is the caliber-mixed version, its numbers are withdrawn, and nothing in the manuscript quotes them (supplementary Z.3). |
| **The dense-scene answered zero is build-specific** (variance decomposition: 38.7% domain / 33.9% build / 27.4% interaction; five deployments of one checkpoint differ by 90.3 pp on ShanghaiTech-A but 2.7-8.7 pp on the aerial domains) | `code/analysis/variance_decomp.py` over `data/derived/e2/`; frozen result `code/analysis/variance_decomp_result.json`; written up in supplementary M.18.8. |
| Pagination (35 pages, single column, 1.5 spacing, numbered) | `code/analysis/build_pr_docx.py` rebuilds the submission `.docx` under the journal's layout (10 pt text, 1.5 spacing, 4.3/4.8/4.3/4.8 cm margins) and `code/analysis/freeze_docx_measurement.py` times it with the word processor's own paginator; the frozen result is `manuscript/pagination_measurement.json`. `code/analysis/measure_pr_layout.py` gives the RTF-proxy reading with its **positive control** (injecting 600 words must change the page count) and is kept as `manuscript/pagination_measurement_rtf_proxy.json`. **The measurement itself is *inside* this package and its two numbers are checkable here:** `manuscript/pagination_measurement.json` is registered in `MANIFEST.csv` and records `"pages": 35`, `"words": 11601`, `"tool": "Word 16.0 COM ComputeStatistics"`, `"limit_pages": 35` and `"margin_pages": 0`, and its `inputs.docx_md5` is **byte-identical** to the measured artefact shipped beside it, `manuscript/PaperB_manuscript_PR_layout.docx` — so *the result and the identity of the file measured* can both be verified without Word. **Re-running the measurement, however, needs the authors' machine**: the record's `inputs.docx` / `inputs.markdown` fields name the author-side paths, so `freeze_docx_measurement.py` cannot be re-executed from this package alone. That is a scope limit on *re-measurement*, not a missing record. |
| Every structural/consistency assertion used before submission | `code/analysis/en_check.py`, `verify_objective.py`, `cite_guard.py`, `pr_compliance_check.py`, `verify_s11.py` |

## How to run: the package root

**No script in this package hardcodes an author-machine path.** Every script under `code/` that resolves a
data path at all — **157** of them — imports `code/analysis/_repro_root.py` and resolves its inputs through
it, so the package can be unpacked into any directory and run from there:

```bash
unzip reproduction_package.zip -d /tmp/anywhere
cd /tmp/anywhere/code/analysis
python recompute_S.py            # reads ../../data/derived/... through the root resolver
python -c "import _repro_root as r; print(r.ROOT)"
```

The root is, in order: the environment variable **`PAPERB_ROOT`** if it is set, otherwise the repository
root inferred from the importing file's own location (`<root>/code/analysis/<script>.py` and the authors'
private `<root>/analysis/work/<script>.py` are both two levels down, so one inference serves both layouts).
A few scripts additionally read an author-side shared corpus drive; that path comes from **`PAPERB_SHARED`**
and defaults to a directory that exists only on the authors' machines.

`resolve(*parts)` (imported as `RP`) takes a **working-tree-relative** path. When the authors' working tree
is present it returns that path unchanged; otherwise it maps it onto the released layout through this
prefix map. `not_released(*parts)` (imported as `NR`) marks an input that is **not in this package**: on the
authors' machines it returns the real path, anywhere else it returns `<root>/_NOT_RELEASED/<tag>` — a
directory that deliberately does not exist, so the script stops with a readable "file not found" naming the
missing input rather than silently reading something else.

| authors' working path | released as |
|---|---|
| `analysis/work/<name>` | `code/analysis/<name>` |
| `analysis/e2xt_a800/<sub>` | `data/derived/e3/<sub>` |
| `analysis/e1_results_census` | `data/derived/e3/zero` |
| `analysis/e1_results_nonzero` | `data/derived/e3/nonzero` |
| `analysis/e1_5090/corpus` | `data/derived/corpus` |
| `analysis/e1_5090` | `data/derived/e1` |
| `analysis/e2_5090`, `analysis/e2_h20`, `analysis/e2_newh20` | `data/derived/e2` |
| `analysis/e2_newh20/logs_h20_v7c` | `env/h20_v7c_logs` |
| `analysis/fsc_res/<tag>` | `data/derived/fsc_res/<tag>` |
| `analysis/fsc_a800` | `data/derived/fsc_res/frozen384` |
| `analysis/ea2_z0` | `data/derived/ea2` |
| `analysis/A_res_20260928`, `analysis/B_res_20260928` | `data/derived/A_res_20260928`, `data/derived/B_res_20260928` |
| `analysis/h20_rescue_20260922/extract` | `data/derived/e2_pools` |
| `analysis/data/pod_mirror` | `data/derived/pA` (the five component directories that are released) |
| `analysis/g2_neutral0`, `analysis/p2_a800` | `data/derived/g2_neutral0`, `data/derived/p2_noise4` |
| `analysis/figures` | `figures` |
| `analysis/m5090_archive/unpacked_all/root/dense_results`, `.../tile_results` | `data/derived/dense_results`, `data/derived/tile_results` |
| `analysis/m5090_archive/unpacked/dense/shanghaitech/counts.csv` | `data/gold/shanghaitech_counts.csv` |
| `analysis/m5090_archive/unpacked/dense/ucf_qnrf/counts.csv` | `data/gold/ucf_qnrf_counts.csv` |
| `analysis/ctxctrl/ctxctrl_result.json` | `code/analysis/ctxctrl_result.json` |
| `repro_github/...` | `...` (this package) |
| `PaperB_英文稿_PR_20260919.md` | `manuscript/PaperB_manuscript_EN.md` |
| `PaperB_英文补充材料_PR_20260919.md` | `manuscript/PaperB_supplementary_EN.md` |
| `PaperB_E1证据_20260920.md` | `manuscript/E1_evidence_record.md` |
| `measurement_pr_docx.json` | `manuscript/pagination_measurement.json` |

Each row was checked by comparing the recursive file-name sets of the two directories (equality, or the
subset relation the wording states). Inputs **not** in the table are `NR`: the Chinese source drafts and
evidence records, the review-package sources, the model-review transcripts, the `m5090_archive` trees,
`analysis/data/**` (harvested detector boxes, e.g. `analysis/data/harvest_A/*.npz`) and the author-side
shared drive.

Two consequences, stated plainly. (i) A script whose inputs are all released runs from this package alone
(`recompute_S.py`, `tile_ladder.py`, `corpus_pi_zero.py`, `n4_cross_family_dense_panel.py` are examples).
(ii) A script that reads an `NR` input — `en_check.py` is the main one — **cannot** run from this package
alone; that is the scope limitation stated at the top of this file. And if you copy a **single** script out
of the tree, the `_repro_root` import fails and the script falls back to inferring the root from its own
location alone, i.e. without the prefix map above.

### Write-back policy: a released script does not edit a released artefact unless asked

Fourteen scripts in this package exist to make a one-off edit to the manuscript, the supplementary
material or an evidence record. **In v0610 every one of them was changed so that its default is
read-only**: it reads, computes and prints *what it would change*, and writes only when run with
`--apply`. The rule is deliberately uniform — *a released script must not modify a released artefact
unless explicitly asked* — because a per-script exception list is both harder to verify and harder to
document. The same round removed **eight** author-side editor backups and temp files
(`*.bak_before_*`, `*.tmp`) that earlier releases had carried into the package, and a narrow filter now
keeps that class of name out of every future release (`sync_repro.py` deletes any that reappear before
it recomputes `MANIFEST.csv`). This is why the package contains no `*.bak*` files today: run
`find . -name '*.bak*' -o -name '*.tmp'` and it prints nothing.

## Environment

* Python 3.11 with `numpy`, `pillow`, `matplotlib`, `paramiko` (the E1 and inspection scripts use only the
  standard library plus `pillow`).
* The released corpus was produced by a self-hosted **vLLM 0.29.0** server with a 4-bit
  `compressed-tensors` AWQ checkpoint of Qwen3-VL-32B-Instruct, compute dtype bfloat16, `max_seq_len` 8192,
  tensor parallel 1. The E1 experiment used a hosted endpoint in its vendor's OpenAI-compatible mode with
  `temperature 0` and `max_tokens 128`. Serving evidence: `env/`.
* The **E2 census** ran on a single H20 (97,871 MiB, driver 595.71.05) with the same vLLM 0.29.0 stack,
  `temperature 0`, `max-model-len` 8192, one image per prompt and `--workers 8`, over 14 locally served
  configurations (Qwen3-VL 2B / 4B / 8B / 30B-A3B (MoE) / 32B in AWQ-4bit, AWQ-8bit, GPTQ-W4, FP8 and BF16
  builds, Qwen2.5-VL 7B / 72B AWQ, InternVL2.5-8B-AWQ, InternVL3.5-38B-FP8). Every cell's wall-clock is in
  `env/h20_v7c_logs/exp_v7c.log`; the exact serving flags are in `code/experiments/h20_exp_v7c.sh`.
  One environment note matters for reproduction: the image was built for `sm_120`, so serving needs
  `VLLM_USE_FLASHINFER_SAMPLER=0` on this `sm_90` device.
* Pagination requires a word processor exposing `ComputeStatistics` (the paper used Word COM); that step is
  the only one that is not pure Python.

## Data provenance

All image corpora are **public**: ShanghaiTech A/B, UCF-QNRF, VisDrone-DET, AI-TOD, BBBC005 and the SFCHD
safety-helmet benchmark, plus the public counting benchmarks used on the VLM side. The images themselves are
**not** redistributed here (they remain under their own licences); `data/gold/counts.csv` gives the exact file
names and target counts, and every per-image record in `data/derived/` carries the `item` key, so the released
numbers can be recomputed from the public images. Synthetic count-controlled grids are generated by a script
in `code/experiments/` rather than collected.

## Integrity

`MANIFEST.csv` lists `path, bytes, md5` for every file **except itself and the derived `data.zip`** (2 rows fewer than the file count). To verify after download:

```bash
python - <<'PY'
import csv, hashlib, os
bad = 0
for row in csv.DictReader(open('MANIFEST.csv', encoding='utf-8')):
    p = row['path']
    h = hashlib.md5(open(p, 'rb').read()).hexdigest()
    if h != row['md5'] or os.path.getsize(p) != int(row['bytes']):
        print('MISMATCH', p); bad += 1
print('verified', 'all files' if not bad else '%d mismatches' % bad)
PY
```

## Known limitations of this package

* Several cells of the corpus have **derived re-runs** (tile/arm combinations re-executed during auditing);
  the paper's primary analyses use the canonical primary runs only. Both are present here, and the audit
  scripts exclude the derived re-runs explicitly.
* Weight-set ranges are reported rather than single values where implementations differ; the released records
  are the ones used for each reported range.
* The E1 comparison varies **both** weight precision and serving engine (a local 4-bit stack vs a hosted
  endpoint), so it establishes that the abstention channel is configuration-dependent without isolating which
  of the two causes it. This limitation is stated in the manuscript (§5.7, §8.2).
* **CountBench is not released as an experimental condition.** The corpus runner for that dataset places the
  caption text in the prompt, whereas the probe sends the image only, so the condition asks a people-counting
  question about non-people images. The cells exist in `data/derived/e2/` for completeness (they are part of
  the raw census) but are excluded from every number in the manuscript and are marked as ill-posed in the
  supplementary material (§M.18.6).
* **The `abstain` column of the aerial-domain corpus tables is a keyword proxy**, not a contract-offered
  abstention: it is set when a prediction is 0 or the raw text contains one of a small set of phrases. It is
  therefore mostly answered zeros, and the paper reads it that way.
* In the E2 census the zero pool of the aerial domains is a fixed-seed 150-item sample of a larger pool
  (VisDrone 273, AI-TOD 154); the sample is identical across configurations (verified by set intersection),
  and `code/analysis/e2_v7c_subset.py` reports every rate on the common subset so that configurations which
  ran the full pool remain comparable.
* The `channel` arm differs from `permit` in **two** ways (output key name and number of options), so that
  pair is not a single-variable contrast; it is used only as evidence about outlet wording.

## Sanitisation of the released files

**Read this before checking any `md5` by hand.** The files here were copied out of the authors' private
working tree by a release script that pushes every *text* file through a **sanitiser**, and then refuses to
publish at all unless a whole-package **leak gate** finds zero hits. The sanitiser is a plain textual
substitution. It is applied only to `.py .sh .md .txt .json .csv .log .yaml .yml .cfg .ini` files; anything
else is copied byte for byte. It replaces, **pattern by pattern**:

| pattern class | replaced with |
|---|---|
| the login password of the workstation that ran the GPU jobs | `<REDACTED-A800-PASSWORD>` |
| the IPv4 literal of that workstation | `<REDACTED-A800-HOST>` |
| an IPv4 literal in an obvious host context (`root@` followed by an address, or an address on a line that also mentions `paramiko`, `SSHClient`, `ssh -p` or `sftp`) | `<REDACTED-IP>` |
| a vendor API key in `sk-` form (20 or more key characters) | `<REDACTED-API-KEY>` |
| the authors' private working directories, in either slash style | `<WORKDIR>` / `<SHARED-DIR>` |
| the login password of the rented GPU pod that ran the H20 jobs (two passwords were in use) | `<REDACTED-POD-PASSWORD>` / `<REDACTED-POD-PASSWORD2>` |
| the host name of that pod, with or without a port (`*.podtcp.com`, `*.compshare.cn`; a narrow pattern, not a general `TLD` rule) | `<REDACTED-POD-HOST>` |
| that pod's IP address, registered as a literal in v0609 (it is the first field of the same login tuple as the two passwords above, and neither IP rule matched it) | `<REDACTED-POD-HOST>` |

No real credential, address or key is reproduced anywhere in this file.

> A note on how to check the claim above mechanically: the six placeholder strings in the table are named
> here on purpose, so *this* file contains them too. `README.md` is **not** one of the rewritten files — it
> is hand-written package documentation with no counterpart outside the package. The rewritten set is
> exactly the rows below.

### Which files the sanitiser actually rewrote

**30** files in this package are therefore *not* byte-identical to the authors' source files, and they account
for **58** substitutions in total. This is the sanitiser's own ledger, written by the release step
(`sync_repro.py`) rather than transcribed by hand; the right-hand column is the value you will find in
`MANIFEST.csv` for that path. Every one of them carries a **credential**, not a path: the path literals were
removed in v0608 (see *How to run*), so the only files the sanitiser still touches are the ones that name a
password, a host or a key.

| file in package | substitutions | md5 of the source file (before sanitisation) | md5 in this package (after) |
|---|---:|---|---|
| `code/analysis/_ctx_pull.py` | 2 | `6A6CD989E3D9135C29B9B7E069690D38` | `C9B5F27BF8CBC27AF4BD35166900FA18` |
| `code/analysis/a5_pull.py` | 2 | `DD869CF4ED649B8B792B5347F06BE025` | `8DA17D64F98ECE4B8CF44C92BDF4A7A5` |
| `code/analysis/a800_chain_families.py` | 2 | `92F93D941360C96BAB9602D6DDC053B1` | `8A25D73FEAD73BC5BEA69C2547BDBB19` |
| `code/analysis/a800_shutdown_check.py` | 2 | `E22E43ABC0B9B1002187F82341C12F40` | `D97D6A4A4DC4C16A9678EA06838AD58B` |
| `code/analysis/e1_evidence.py` | 2 | `B8408D49D611D346C59FEBB71965CB14` | `DBDCC539803D9BCDD6A6BA20A922792D` |
| `code/analysis/e2_fetch_summarize.py` | 2 | `7AAC24FE86373EEFCF3965D1DBBC3359` | `9E1238D161E114B3AAD8BD3F39D45B94` |
| `code/analysis/h20_conn.py` | 2 | `575657B5DE086AF12E8655156862EF62` | `F7BF8189B238C4449994ACA73EF8973F` |
| `code/analysis/m40m41_facts.json` | 2 | `8BC6E0EA0CA4B9B19FC611A865A200F1` | `A2360E5CAC75E1E5854C3491184C1B7A` |
| `code/analysis/w0_audit.py` | 2 | `FC0D864ADBDC4E44A781663ADDC86AAA` | `EDB1D303D0F998ED5ADD1872101EB319` |
| `code/analysis/w0_frame.py` | 2 | `D35C5FBE33AD9D9D49D690D8341A1ED8` | `C768CF262041599BBCD84F3CF27A6A94` |
| `code/analysis/w0_frame3.py` | 2 | `6261B7034990B0CEEDA1C3C5C24F4111` | `4FFF2C055A51864F1B8E49CE6B65277E` |
| `code/analysis/w0_pools2.py` | 2 | `1B1E3A881967C26919A3AC62F3387497` | `68A42534E02665CA9F0707259B9E4435` |
| `code/analysis/w0_pull_probes.py` | 2 | `9C339255F8280F8307B99B0708310751` | `312492CE1AA21559094F8AEEAC81ED60` |
| `code/analysis/w1_hosted.sh` | 1 | `EFA89850722EC8BD717EED2C73CB70AC` | `B474C757C5BA46C805CB9B7CF31FEC79` |
| `code/analysis/w1_monitor.py` | 2 | `5D2BD3CDFD4EF83874703F232437B273` | `894E5FA9F30F707DD6AD27FAC181534B` |
| `code/analysis/w1_unpack.py` | 2 | `44A03ADE17354487521719FEECBFAC29` | `F25CC0185ADCC1AEAB83D8F05C0C2FA7` |
| `code/experiments/h20_e2_scripts/h20_fetch_missing.py` | 2 | `3BDBA9B00BF6A1C54AA80CDDA3618F51` | `98DA53E2010BB5C1209C0289EA1312AF` |
| `code/experiments/h20_e2_scripts/newh20_fetch_packs.py` | 2 | `DCB280C8FDDFDCA163FFA47F063DD43C` | `E6C17656590D37BB69D23B39094DCA29` |
| `code/experiments/h20_e2_scripts/newh20_push.py` | 2 | `4F3F915B8DAD7E6699C89FB1BA825827` | `270E6DDB5EE04AB95D186A5570D2B46D` |
| `code/experiments/h20_e2_scripts/pull_domains.py` | 2 | `E158F019A7441BBE256F82DFEAB6EDEE` | `8D72709DBA61F648A139D1C327A6FD9E` |
| `code/experiments/h20_e2_scripts/pull_from_m.py` | 2 | `66035318C592519DDE8A723110EF4219` | `DEF4CA724FE6A2B9330FC96FA35BC02C` |
| `code/experiments/newh20.py` | 4 | `9E58DDF5047D794C946B5167C7D8777F` | `719B88C7FD32645DB5D41616CA6951E7` |
| `code/experiments/newh20_sync.py` | 2 | `AFA1D7342B71C5CC2626B0A27B5B2002` | `3767DF2EB12ED504FB50B60013D0DFE5` |
| `data/derived/a52_ext/A800_A5-2_扩构建_实测报告_20261006.md` | 2 | `77D163EFDF189FDAA2D90D8432D429E1` | `13E87462503E852B7E13358477071037` |
| `data/derived/a52_ext/A800_A5-2_最终报告_b1全量+b3定案_20261006.md` | 2 | `EE2B3A1D0D0672DE87A5EE23BB0196A6` | `5B642108D898DA09D8F7AB4DD4A06DD5` |
| `data/derived/a5_2_a800/env/_a52_criteria_frozen.json` | 2 | `758962A2643E1035698682ABEFEC5748` | `25972A82EEDE02EAEC59C4E53B9337BF` |
| `data/derived/a5_2_a800/env/_a52_运行单.md` | 4 | `708A0BDD7C9BFF33E1A2133BEB5F4D0C` | `2ADF3B07C164BA9D0EEFBD8C3A4682EA` |
| `env/a800_logs_20260927/A800交接说明_给P3_20260926.md` | 1 | `4E58B4AB9CB3E86647C08BBB806AA3AA` | `7AE554772095669FBE556F79F5601F89` |
| `env/a800_logs_20260927/A800交接说明_给P3_20260927.md` | 1 | `9F3DBEBDD82B13B3AC4BC6960B3D9664` | `F50892F0674467E4007E3044D325752B` |
| `env/a800_logs_20260927/RUNNING.md` | 1 | `AB904CC2C17FD4FE042ED97CBBB864ED` | `3E7519B9FB9DF0739453ED9561333812` |
| `env/a800_logs_20260927/_FETCH_MANIFEST.txt` | 2 | `EE928D5475B740A60069CBAF8C6B06AD` | `A7289C3A1C1F28C4CFD6364C32A638FB` |
| `env/a800_missing_20260927/_FETCH_MANIFEST.txt` | 2 | `07A031C921AE341D37520A1070CC9733` | `060920439D38AB48267A8B43D3762444` |
| `manuscript/E2_evidence_record.md` | 2 | `5DC10DB6973AE87C27D16DC86DAE1AD0` | `2D27C099EA0CD30BED981FB9823622CD` |
| `manuscript/review_control_evidence.md` | 2 | `EB1658CD01D61F6EE78B7C380C3BE991` | `44DDAF365938DCD2F707DB96A51875F1` |
| `data/derived/a52_api_six_20261007/analysis_manifest.md` | 7 | `B8BA0EEB4CFE99AB1E0A03995D20E00D` | `E98AFD1A0FA76E341C03826833F64E38` |

**Four counts that are easy to confuse**, each with the command that produces it (run from the
package root). The first two are about *paths*, the last two about the *sanitiser*.

1. **157** scripts resolve their inputs through the shared root: the **146** converted in v0608 plus the
   scripts added to the released set since. Each imports `code/analysis/_repro_root.py`:
   `grep -rl "from _repro_root import" code | wc -l` → **157**.
2. **0** of those scripts carries an author-machine path, and no script's *data* path is absolute:
   `grep -rEl "(^|[^A-Za-z0-9])[A-Za-z]:[\\\\/]" code --include='*.py' --include='*.sh'` → **3** files, and
   neither is a data path: `_repro_root.py` itself (its single env-overridable `PAPERB_SHARED` default) and
   `w0_frame.py`, where the match is the fragment `e:\n` inside a quoted Python-code template
   (`'except Exception as e:\n'`), and `derive_release_numbers.py`, which quotes that same fragment
   in its substitution strings below — none of the three is a path.
   Widening the same scan to **every** text file in the package gives **21** files, still none of them a
   script's data path. They are frozen artefacts and run logs whose recorded strings hold the authors'
   prefix in backslash-escaped form (e.g. `A_result.json`, `ea2_z0_result.json`, `fsc_res_result.json`,
   `n1_span_artefact_result.json`, `n2_rule_spread_inventory.json`, the per-image records under
   `data/derived/`, the `env/` handover notes, and this `README.md`, which quotes
   the `e:\n` fragment above). The frozen artefacts are **deliberately not modified** — they are reported
   results, and editing a result in order to tidy a string inside it would be the worse trade; the `env/`
   notes are handover prose, not code.
   *Before v0608* the same scan returned **152** files carrying the placeholder `<WORKDIR>`: **146** `.py`
   scripts (**143** under `code/analysis/`, **3** under `code/experiments/`) plus **6** non-scripts. Those are
   the "146 / 152" figures in this package's earlier history; they counted *files with a placeholder*, not
   files with wrong numbers, and they are no longer the live count because the placeholder is gone.
3. **35** files were rewritten by the sanitiser, in **75** substitutions (the table above). This set cannot be
   recomputed from this package alone — doing so needs the authors' pre-sanitisation sources, which are
   deliberately not released. What *is* checkable here is that the table agrees with the manifest: the
   `md5 in this package` column equals the `MANIFEST.csv` row for the same path (verified when this file was
   generated). *Before v0608* the same count was **160**, because the 146 scripts then carried a `<WORKDIR>`
   path and had to be rewritten too. **v0609 added three substitutions** (the pod IP literal above);
   it added no new file, because all three of those files were already being rewritten for their
   passwords. **v0610 changed none of these numbers**: it removed eight residue files instead (see
   *Write-back policy*), which took the package **at that revision** from **3,659** to **3,651** manifested
   files and left both the rewritten set and the substitution count untouched. **At this revision
   `MANIFEST.csv` registers 4766 files** (`wc -l MANIFEST.csv` minus the header) and `data/` holds **3838**
   of them — both are re-derived by `code/analysis/derive_release_numbers.py`.
4. **39** files merely *contain* one of the placeholder strings: `grep -rlE '<REDACTED-|<WORKDIR>|<SHARED-DIR>' . | wc -l`
   → **39** (the sanitiser's own rewritten set is count 3 above; the remainder only quote a placeholder
   string — this `README.md` does so on purpose).
   *Before v0608* the same count was **161** (160 + this file).

**The consequence, stated plainly.** Where the md5 of a script here differs from the md5 of the authors'
source file, that difference is **caused by this sanitisation** — it is not evidence that the script was
edited after the reported runs. A field that records the md5 of a *source file*, such as `script_md5` in a
frozen JSON, therefore refers to the **pre-sanitisation** bytes; where such a field does not equal the md5 of
the shipped copy, that is the expected outcome of the sanitisation described above — **not** an
inconsistency and **not** tampering. The live example is `code/analysis/A_result.json`, whose `script_md5` is
`CBA9DDA5C0F305CF8EC2BE8A9ECF1A3A` — the pre-sanitisation md5 of `A_analyze.py` — whereas `MANIFEST.csv`
records the shipped copy as `1915CEA82C7BB66FB9A73321D490F353`.

The same convention governs the md5 values printed **verbatim in the manuscript and the supplementary
material**, and **v0608 added a second and larger reason for a disagreement**. Rewriting the author-machine
paths changed the bytes of 146 scripts, so every digest those scripts are associated with — the
`script_md5` / `copied_from_md5` fields inside the frozen JSON results, and the digests printed in the
supplementary material's *Reproduction* notes — is now a **historical** digest. The numbers those scripts
compute are unaffected: only the literals that located their inputs changed, and neither the per-item records
nor any frozen result was touched.

Worked examples, each re-checked against `MANIFEST.csv` when this file was generated:

* `code/analysis/A_result.json` records `script_md5 = CBA9DDA5C0F305CF8EC2BE8A9ECF1A3A` — the
  pre-sanitisation digest of `A_analyze.py`. That script's bytes now hash to
  `code/analysis/A_analyze.py` both as the authors' source file and as the copy shipped here (the sanitiser no longer
  touches it, because the path literal it used to rewrite is gone).
* Supplementary §M.19.15 prints, for `n4_cross_family_dense_panel.py`, a **historical** digest
  `9c74db226c1b785361807ebc7e069771` and the digest of the copy shipped here,
  `code/analysis/n4_cross_family_dense_panel.py` — the latter is the `MANIFEST.csv` row for that path. **The script's behaviour did not
  change**, only the literals that located its inputs, so both numbers are stated rather than one of them
  being silently corrected.

Of the **32** distinct 32-hex digests printed in the manuscript and the supplementary material, **27**
equal the `MANIFEST.csv` md5 of a file this package ships, before or after v0608. The remaining **5** are
not shipped-file digests: `0a42e6e5bbfa89543ba9fc1522f1b075`, `758962a2643e1035698682abefec5748`, `9c74db226c1b785361807ebc7e069771`, `aca4444c7f681b0596db4e4a84578b62`, `d95d7466b482f575dc781d152e5ddf23`.

**The earlier accounting in this section is superseded.** A previous revision counted "39 md5-valued JSON
fields, 28 matching a shipped file and 11 not", and listed the eleven unmatched ones. The serialisation of
that count was not recorded, so it is not re-derived here; what replaces it is the two worked examples above,
which are mechanical. The named entities it listed as deliberately absent (`zenodo_meta_md5` /
`hf_mirror_meta_md5` in `A_criteria_frozen.json`, `hf_api_meta_md5` in `B_criteria_frozen.json`,
`transcribed_from_md5` in `f9_quoted.json`, `en_md5` and the `rtf_md5` values in
`pagination_measurement_rtf_proxy.json`) are still absent from this package and still unrelated to both the
sanitiser and the path refactor.



### What the sanitiser did **not** touch

**Almost nothing under `data/` was altered.** Of the **3838** files under `data/`, **5** are text files
the sanitiser rewrote (they are the `data/` rows of the table above); every one of the remaining **3833** is
byte-identical to the corresponding source file. Two independent checks say so: (i) a sanitiser substitution always leaves one
of the six placeholder patterns above in the file, and a scan of all 3838 released data files finds **3**
carrying one of them — the remaining rewritten data file carries a neutral internal-name placeholder
instead of a host/path placeholder; (ii) a per-file `path / bytes / md5`
manifest of `data/` taken before and after the release script ran differs **only in the rows the sanitiser
rewrote** (the table above). In particular the 138
A-round and B-round products added in this revision (`data/derived/A_res_20260928/` 71 files,
`data/derived/B_res_20260928/` 67 files) are verified item by item against the `MD5SUMS_A.txt` /
`MD5SUMS_B.txt` manifest shipped beside them — both in the source directory and again in this package.

Only text files can be affected at all, and only the rows in the table above are. `data.zip` is a plain archive of
`data/` and inherits the same guarantee.

## License

Data, code and figures in this package are released under **Creative Commons Attribution 4.0 International
(CC BY 4.0)** — see `LICENSE`. Please cite the manuscript if you use them.
