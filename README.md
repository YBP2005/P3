# Reproduction package — *Abstention dominates the aggregate under-count*

Source data, code, figures and audit scripts for the manuscript

> **Abstention dominates the aggregate under-count: signed error direction in object counting with
> vision-language models** (submitted to *Pattern Recognition*).

Everything reported in the paper is reproducible from the files here. No number in the manuscript was
typed in from memory: each is either computed by a script in `code/`, or taken from a per-image record in
`data/derived/`, and the arithmetic identities are re-checked by assertions (`code/analysis/en_check.py`).

## Contents

| Path | What it is |
|---|---|
| `data/derived/` | **All per-image prediction records** (1,112 CSV files) — the released corpus: detection ladders, tiling ladders, density-regression runs, prompt-family and contract arms, aerial and microscopy domains, VLM and detector families. |
| `data/derived/e2/` | The abstention-channel **census (E2)**: 558 result files = 14 configurations x 6 contracts x {zero pool, non-zero pool} over five usable domains (st_a, st_b, ucf, VisDrone, AI-TOD; CountBench is excluded — see *Known limitations*). Files prefixed `nz__` are the non-zero pool. |
| `data/derived/e1/` | The discriminating experiment (E1) on the abstention channel: 48 cells over five configurations x two domains x up to six arms. |
| `data/derived/corpus/` | The nine whole-image corpus tables behind the abstention decomposition. |
| `data/gold/` | Gold-standard counts (`counts.csv`) for ShanghaiTech and UCF-QNRF: file name -> target count. |
| `code/experiments/` | The runners that produced the corpus (one script per experiment, in the order they were run), including the E2 census drivers (`h20_exp_v6.sh`, `h20_exp_v7c.sh`) and `make_19e.py`, which derives the E2 probe `19e_probe_multi.py` from `19b_e1_probe.py` deterministically — it re-reverts its own patch set and asserts byte-identity with the original, so the six-line difference between the two probes is auditable rather than asserted. |
| `code/analysis/` | Measurement, auditing and verification scripts (see below). |
| `figures/` | The 13 finished figures (PNG). Fig. 1-4 of the manuscript are the first four of these. |
| `manuscript/` | English manuscript and supplementary material (Markdown source), the PR-layout `.docx` (`PaperB_manuscript_PR_layout.docx`), the Highlights file, the cover letter, the E1/E2 evidence records, the review-control evidence record, and the frozen pagination measurements. |
| `env/` | Serving configuration evidence (vLLM log for the self-hosted 4-bit stack) and, in `env/h20_v7c_logs/`, the E2 census run logs (serving starts, per-arm probe logs, per-cell wall-clock). |
| `MANIFEST.csv` | `path, bytes, md5` for **every** file in this package. |
| `LICENSE` | CC BY 4.0. |

## How to reproduce the main results

| Claim in the paper | Reproduce with |
|---|---|
| Abstention share of the under-count (82–94%, base arm; 42.5–99.4% over all arms) | `code/analysis/recompute_S.py` over `data/derived/corpus/` — prints `w`, `rho_answered`, `rho_total` and the closed form `S` per domain and arm. |
| The identity behind Proposition 4 / the dual-convention gap (61.3 / 57.5 / 40.6 / 40.6 pp) | same script; the identity `(1-w)(1+rho_ans)` reproduces every printed gap to <= 0.04 pp. |
| The abstention channel is set by the output contract (E1: 1591/1591 explicit abstentions, median 2.463-9.452x when abstention is forbidden) | `data/derived/e1/*.csv` (raw responses included); summarised by `code/analysis/e1_evidence.py`. |
| **The gate is the abstention token, not the enumeration demand** (E2 census: `enum`/`locate` arms produce zero explicit refusals while the same prompt plus one abstention token converts 98-100% of the items) | `code/analysis/e2_v7c_analysis.py` over `data/derived/e2/` (its §M.18.2 table); the arm prompts are in `code/experiments/19e_probe_multi.py`. |
| **Item-level pairing**: of the items a configuration answered 0, offering an abstention option removes the zero in 46 of 52 (model x domain) cells and the three-option `channel` contract in 52 of 52 | `code/analysis/e2_v7c_analysis.py`, section 3 of its report; the per-cell counts are re-derived from the raw CSVs by `code/analysis/verify_s11.py`. |
| **The two kinds of answered zero** (dense: build-specific, 9% vs 99% for two builds of one checkpoint; aerial: 11 of 12 configurations at 62-99%) | `code/analysis/e2_v7c_subset.py` (common-150 comparison) and `e2_v7c_analysis.py`. |
| The zero is not a parsing artefact (audit of all 2,496 corpus rows) | `code/analysis/corpus_parse_audit.py` over `data/derived/corpus/`. |
| The tiling ladder (56.6% -> 6.0% (2x2) -> 0.0% (4x4 and finer) on ShanghaiTech-A) | `code/analysis/tile_ladder.py` over `data/derived/tile_results/` + `data/gold/`. |
| **The span spectrum is not a function of the scanning grid** (ordering preserved at Spearman 0.964 / 0.977 / 0.993 over 24 knob x domain units; detector-threshold magnitudes fall 2.2-2.3x in-domain and 5-10x zero-shot under equal-count gridding) | `code/analysis/span_equalcount.py` over `data/derived/`; frozen result `code/analysis/span_equalcount_result.json`; written up in supplementary F.10/F.11. |
| **The dense-scene answered zero is build-specific** (variance decomposition: 38.7% domain / 33.9% build / 27.4% interaction; five deployments of one checkpoint differ by 90.3 pp on ShanghaiTech-A but 2.7-8.7 pp on the aerial domains) | `code/analysis/variance_decomp.py` over `data/derived/e2/`; frozen result `code/analysis/variance_decomp_result.json`; written up in supplementary M.18.8. |
| Pagination (33-34 pages, single column, 1.5 spacing, numbered) | `code/analysis/build_pr_docx.py` rebuilds the submission `.docx` under the journal's layout (10 pt text, 1.5 spacing, 4.3/4.8/4.3/4.8 cm margins) and `code/analysis/freeze_docx_measurement.py` times it with the word processor's own paginator; the frozen result is `manuscript/pagination_measurement.json`. `code/analysis/measure_pr_layout.py` gives the RTF-proxy reading with its **positive control** (injecting 600 words must change the page count) and is kept as `manuscript/pagination_measurement_rtf_proxy.json`. |
| Every structural/consistency assertion used before submission | `code/analysis/en_check.py`, `verify_objective.py`, `cite_guard.py`, `pr_compliance_check.py`, `verify_s11.py` |

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

`MANIFEST.csv` lists `path, bytes, md5` for every file. To verify after download:

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

No real credential, address or key is reproduced anywhere in this file.

> A note on how to check the claim above mechanically: the six placeholder strings in the table are named
> here on purpose, so *this* file contains them too. `README.md` is **not** one of the rewritten files — it
> is hand-written package documentation with no counterpart outside the package. The rewritten set is
> exactly the 160 rows below.

### Which files the sanitiser actually rewrote

**160** files in this package are therefore *not* byte-identical to the authors' source files. The table
gives the package-relative path, the number of substitutions made, the md5 of the source file, and the md5
of the copy shipped here. All md5 values are uppercase hex; the right-hand column is the value you will find
in `MANIFEST.csv` for that path.

| file in package | substitutions | md5 of the source file (before sanitisation) | md5 in this package (after) |
|---|---:|---|---|
| `code/analysis/A_analyze.py` | 3 | `CBA9DDA5C0F305CF8EC2BE8A9ECF1A3A` | `1915CEA82C7BB66FB9A73321D490F353` |
| `code/analysis/_audit_bootstrap.py` | 1 | `AAAA195B6E95A32DDFCD60AA6BE83206` | `21124A0082B92CE1853B29094E3A452A` |
| `code/analysis/_check_n1_coverage.py` | 3 | `6FE9432D9C54CAB8E7F844B6350654EA` | `F6FF9AFA1E801583FDC020625046FCD8` |
| `code/analysis/_ctx_pull.py` | 3 | `06F0D58BCEE0BFF5B1413536FD3E0B84` | `82B45156F6366B2003D6BBC2390A865B` |
| `code/analysis/_ctxctrl_indep_check.py` | 1 | `99443C1BA16A033E781935D7DEAC6BD2` | `4E25FEB1306BE3B10EDB185B4CFB1F9A` |
| `code/analysis/_dump_pp_sentences.py` | 2 | `E333D179358D4AA8C6ACD3EC76B340E3` | `725DEB6660BB9CD7890155263D50E66D` |
| `code/analysis/_f10_random_drop.py` | 1 | `815256F36DE285B53EE50AABB0DE3A62` | `7ED0A0FF0B50127123B3270CCDBDB675` |
| `code/analysis/_f10_range_check.py` | 1 | `F1208E96556763853056261727A14477` | `CF69588E65E1D3C12BC4441A84715234` |
| `code/analysis/_freeze_m40m41_facts.py` | 1 | `B647A02DABE2BA93E06EDEA68054D11B` | `06E8AEA144BAF4646DE9B840EB911B46` |
| `code/analysis/_normalize_numbers_refs.py` | 2 | `0BB319C09E62FC6F54EFED4E29B7BDBD` | `9B76C30EAAB5387208E016D5CD745B9E` |
| `code/analysis/_posctrl_white_vacuity.py` | 1 | `8755A737236ECFBFA59B9021E47B82F6` | `EED8E5F01A35B4D0624AED42C14CE0B3` |
| `code/analysis/_probe_f10_bug.py` | 2 | `0DAA33F25580290A481A745E0FDB0DC9` | `BB87CF169035599D04F0F23620DDD1D6` |
| `code/analysis/_variance_boot.py` | 2 | `B8696E8C8F64D31C37BD385187DF7027` | `5562CE5B3CF41EE2CA34E5CFDD4C3DC6` |
| `code/analysis/a39_perknob_robust34.py` | 2 | `BEDA5A4CEBF46AC67DC59A1E86DFA393` | `D09A6DEC8C788952CEA90A9F4903106E` |
| `code/analysis/a39_perknob_rung.py` | 2 | `8D546C35DB3E2EBF7EECE2B5DE2F54DA` | `3E8D9A2EC2EB4B5BA021BF232013E39E` |
| `code/analysis/a39_sharediso_fold2.py` | 2 | `12B82394A23B1E8E5E1E2B18B766CC5E` | `2F72CE02C20708AD32815ABA65BBDC51` |
| `code/analysis/a39_unit_calib_heldout.py` | 2 | `44CA725B85F3979C064680FFAC9056B4` | `1241A696B1C93885E182DE85856C3B12` |
| `code/analysis/a44_split16.py` | 2 | `89A55742C69814B2645F11EC343457F0` | `BAC46A9433421A66655048D4B7667944` |
| `code/analysis/a5_ablation_report.py` | 3 | `E1A541B887204CB10DD78F51D4C5CA45` | `C52334728A54AACCC3D812BBA1949C37` |
| `code/analysis/a5_criteria_freeze.py` | 1 | `89C690B7D37BE70377C6B7AF7D6DD902` | `9B3881A208A5293356A541717A8A074C` |
| `code/analysis/a5_mech_report.py` | 2 | `70807C288151DE81FF410F9644CF35B2` | `DFF51736C06C4DD1D1041F57D17442DF` |
| `code/analysis/a5_pull.py` | 5 | `71F138D1BB1FCC7F86F1D5B2E13E2BF6` | `7572607F4966A136B5740BD2B2132CD3` |
| `code/analysis/a5_qc_matrix.py` | 2 | `B58968A7A6F4DD6FCA743343527EC0A6` | `38C4119DE11BCF07D6C2A635A85797D8` |
| `code/analysis/a5_rawsamples.py` | 1 | `91373ABC5FE57F77423BB40AC6DFFC42` | `33C3BA487EBC203A5302F66F6F157B6E` |
| `code/analysis/a5_report.py` | 3 | `F9BE10D39CF03B3F378D8A23227A2780` | `C68C5719FA005BA1ED526843B671AD74` |
| `code/analysis/a5_two_kinds.py` | 2 | `36138653991084F75F5BDE26CA3CBA8C` | `68901903BDD30B26D4997E4CA6BE0393` |
| `code/analysis/a800_chain_families.py` | 4 | `6BCFEC78A515D3B894AE7321B6270909` | `940AC33092533E869640094453065D0F` |
| `code/analysis/a800_shutdown_check.py` | 4 | `9BE801A7A10A8359EDD81D4AD38F4F7E` | `73394B8303E49263E6C508961575183E` |
| `code/analysis/a_lightfree.py` | 3 | `C4C76667343A6F25A835A027BFECF241` | `70C33FBE798496F645A01EF366C48B75` |
| `code/analysis/a_lightfree_grid.py` | 2 | `3212B8BBF228EDBFE02FD10A3F0ADE82` | `7A3E6C0170E953B3B1B6126CD67AEBDB` |
| `code/analysis/a_lightfree_quote.py` | 1 | `643125902ECFE9C3D3E90EF7568FB6D4` | `0E2471D5E274C201EA38C7F0C34FCFFD` |
| `code/analysis/anchor_aux.py` | 5 | `E66B50670935E9AC165D3B39519452D8` | `444D3FB9A5E375F3F0DE8C4646C048CE` |
| `code/analysis/anchor_f10.py` | 3 | `01D6F2EB1BBAC8A014362D2723C01353` | `B2AEF5A8E8BA55B79BEBFF3446D63447` |
| `code/analysis/anchor_m40m41.py` | 1 | `AC1EDE747EFB2EA24BA9935CF7BFCA99` | `411343959D76ED65B1D22ED9974C1297` |
| `code/analysis/b1_fsc_analysis.py` | 2 | `6375ECFA999C00AC88A096000BE8250F` | `8CA8C7E084A5EACB7D47B8C87E6E930D` |
| `code/analysis/b1_fsc_full.py` | 2 | `79A9793E655DF37092226952981A3846` | `B9DDCB05C2EE0E472BBFE0CC46871C98` |
| `code/analysis/b1_fsc_quote.py` | 1 | `0700537C157EB716F190A6B936F37898` | `5D3553EBB7FDF0889E3654A699722D6D` |
| `code/analysis/b2_pilot.py` | 2 | `C99AE0E342A75B1BBE794531D055A347` | `E25AA881BDB244D85857899EEE9ADD94` |
| `code/analysis/b2_pilot_consensus.py` | 3 | `394D99953ECACC3427E0F1D1AC1196BE` | `56E8CF05430EA6F9C682B9910C787FE7` |
| `code/analysis/b2_pilot_phrasing.py` | 3 | `A1F5F9867958EA9D05D0B1971234484B` | `01AB768F5046E7FD68D4141B9A122800` |
| `code/analysis/build_coverletter_docx.py` | 3 | `3C09FF2C3B0C66479E13B4456DF60B61` | `955056B719F50EFDA781B08E72B6A749` |
| `code/analysis/build_highlights_docx.py` | 1 | `831682B967E595C686BD306B1E4B2D59` | `7AB481E3A7BBB197B9D40F72CBE4EBC4` |
| `code/analysis/build_paperB_pack.py` | 1 | `0041249432483D90F1BB985E6E247343` | `C3B9A7967C4233DD488EFA80DB360903` |
| `code/analysis/build_pr_docx.py` | 2 | `F8B80D65F99120A57F0DD691A37DA3A8` | `6695AF9130C918502E9396D3E516471A` |
| `code/analysis/build_span_panel.py` | 2 | `5D8A7C7DA0FD12376715BC8328D214D6` | `7B28B28B2D3A6BCBCD8C673533405BA6` |
| `code/analysis/check_citation_mapping.py` | 1 | `9A1F0F0C6F6BCB168D0CD4BA98C45F68` | `176B62A824E6992D5730C80D87166F20` |
| `code/analysis/cite_guard.py` | 1 | `B821B265286DFB26920FC33A11FC368C` | `B920F09F4D07524CCB5371D7213CDBEE` |
| `code/analysis/close_parse_issue.py` | 1 | `6C9D07B5F444F2E3A341169ED9ABDBC3` | `C49EE079C6CCCF51144B4F722C8EBF17` |
| `code/analysis/collect_round.py` | 1 | `8F61D79D90AA7C558732DB6B9B7C0878` | `36ABB14486533A2127D540ACA6876FEE` |
| `code/analysis/convention_rank.py` | 2 | `545A69597F4BD92D68531F26A2C2086A` | `E5B1BE1C6ECE3DAC28EFAFEB9AC56AE3` |
| `code/analysis/convention_rank_quote.py` | 1 | `6A8E89AA2B1A1ACF00263AE8DAEB501C` | `2239F0B3A412CD429E0F10FC748CB820` |
| `code/analysis/corpus_pi_zero.py` | 1 | `918324D7E1E2C57C6A24529859AE0352` | `87CE2A7A89DCB495696122C076BA592E` |
| `code/analysis/deploy_decision2.py` | 4 | `D99F6761765A99ECD9D2F8073432BA93` | `37594C15AC83458835D857A8AAAA6A91` |
| `code/analysis/dose_routeA_visdrone.py` | 1 | `20031B4652F13AE5666C604220220295` | `CACAA78AA614B6168357CE6ADB7347F7` |
| `code/analysis/e1_evidence.py` | 3 | `B4FC37D62BFEEBA85AA54856DFB68DBD` | `A31795AEB65B4006006081D508DCEFD7` |
| `code/analysis/e1_full_table.py` | 1 | `171A044F2A19EAABE28073D096DA0CE5` | `8DE0F50F273392908DB904C222531787` |
| `code/analysis/e2_all_models.py` | 1 | `1324F4EE8679311D747744AD958F8214` | `D7EF9916210F75E99667462AF5F197F4` |
| `code/analysis/e2_compare.py` | 2 | `E9B1FD589B6CFA01FAA991732555C60C` | `849707863B237FFD29475F3D5A62C059` |
| `code/analysis/e2_fetch_summarize.py` | 1 | `E56ED12767C4DA00856412B551E7A79D` | `A097FB583314DA7D79B25F2170927F2A` |
| `code/analysis/e2_full_analysis.py` | 1 | `DD73390FA5D728D40C2A7BEE2AF07B36` | `2035799C25848F835B1FCB296F1689DE` |
| `code/analysis/e2_key_questions.py` | 1 | `BA13127B219AF27B4234AA16642849E8` | `DDE112D8095E70B2AC4537F88AB076B0` |
| `code/analysis/e2_paired.py` | 2 | `BCD8C16F17DE4EFEFC8E7A2DD9D40C67` | `4D748A76E1D6ACACDCA8B1BD0AD877C4` |
| `code/analysis/e2_v7c_analysis.py` | 2 | `720B216E369A8A7B15967AAAF5735074` | `E7A12CB798D7F79E1F22C89218EA873E` |
| `code/analysis/e2_v7c_subset.py` | 2 | `863FDBF435096F7663F4F68DA7445B54` | `341A38426AE14BD600D4D6C1D1B087A3` |
| `code/analysis/e2_zero_by_model.py` | 1 | `112D0A463F88E078556ECD50D27938D6` | `38B11FF6CC8CA25C16B37AD226E2C2A5` |
| `code/analysis/ea2_analyze.py` | 2 | `BB35E047613DE09E4DC83B2EC0ABE145` | `11AE8D41D14A0043668111C7287A1A55` |
| `code/analysis/ea2_contrast.py` | 3 | `4FB843E4C8D099AEEE6313848476E970` | `A12BDA82CC16239DFD4D4685F328485A` |
| `code/analysis/ea2_integrity.py` | 1 | `6152DD4F05D57FCDF47A87BA2D1CA959` | `0A6F37E3E933D512639BD1180491F01C` |
| `code/analysis/ea2_mixed_analyze.py` | 2 | `A6DDAC729A5C81DFD8B01841A3B559B4` | `CBCB897AC445913EEC9086D83FEDCAD4` |
| `code/analysis/ea_finalize.py` | 2 | `706E1F66FE55F3B5B1FA9FC8792D17F9` | `674643C1F6CAE46792BF5CFA2CB7F833` |
| `code/analysis/ea_lang_manifest.py` | 1 | `3053B095793AB7D2E96D6D25C4D28CC2` | `A21AADBBEB9D6E000A5180B2F1DED1A3` |
| `code/analysis/eb2_equalcount36.py` | 2 | `B896C0D0C1A6FD30AFC4ECF07345FC9D` | `9AAF9921B7AFF14A8A5EDB776D9A71BD` |
| `code/analysis/ec_finalize.py` | 1 | `DC313FECFA99D5A7061290358DCCD872` | `C9590DC4717883ACA7718E010C6BF059` |
| `code/analysis/en_check.py` | 1 | `089FFC59B669AAD2F8B87DF6176924E1` | `028FDDD6CB892BFC302EBB7514D7E077` |
| `code/analysis/endgame_e1.py` | 1 | `3D3470C687F51BD5C43EBD46BF9FDE97` | `1D5A8A5FC036C833BF360E8AAA0A5C58` |
| `code/analysis/endgame_e2.py` | 1 | `48A220AF363ADF5B7E7027D35083B62D` | `394812C590FB96C5536B0767EB4A71B1` |
| `code/analysis/f10_grid8_declared.py` | 1 | `60AE490DF7651348BB5275BD1A13A84A` | `A0050EE90075961FBFB0C79B3124EC2F` |
| `code/analysis/f9_repro.py` | 1 | `F0E87B1333462F30DB515934FAB77D08` | `CCD8D30A23B4A05784080D9D88294B29` |
| `code/analysis/f9_transcribe_check.py` | 1 | `3E990A602533BCD6CF5FB1E1FDE71DA7` | `794CBA7F054CAD0E7592F135890EB724` |
| `code/analysis/fix_ref_periods.py` | 1 | `2E7ECD2B7B6C8A35293A95CE7DF0DDF6` | `62B18A6BDB39E16E7A39D81AD599E92F` |
| `code/analysis/fix_s38_labels.py` | 1 | `285EC95F4EB96537516DABDBC81272E9` | `2B73E4FE264281764A0B78472F51F420` |
| `code/analysis/freeze_docx_measurement.py` | 1 | `F9368B1D72F914F6AEA0B3E28CE3EF14` | `98456628B0A9B901AE0557773F3BB9B5` |
| `code/analysis/fsc_res_analyze.py` | 2 | `B53E39FF16E97586DB399F87A2E79EC1` | `07C7ECA5B404C4E8E52F5D28F4437172` |
| `code/analysis/full_suite.py` | 1 | `9A696B54E61AF66FC0E42011EE55C8E9` | `E7979FED07DBF244082B26F623F5FDEB` |
| `code/analysis/g15_levels.py` | 1 | `3EC96FE79E97023DDF9DCD49BA120FD3` | `F3037A0C57EF48E94AD674AF4E1EA9A6` |
| `code/analysis/g15_normalise.py` | 1 | `90B97C9E435B30896A47B6CF960D9F2A` | `157C2D56CBBB277FF4C7CD734C060989` |
| `code/analysis/g15_travel_extract.py` | 1 | `7C1000DBE0F55B140D4BE5D25F7ECE79` | `7A49BDFE34E95D2730B50A12BAE27BB7` |
| `code/analysis/g2_analyze.py` | 1 | `77019D621A07DA2FCD4DC4845AB02D6C` | `76B1462C23630DF0784903AF8CDDD034` |
| `code/analysis/gen_m37_unit_table.py` | 1 | `0F876A3371EB2D43F0F56041143A5379` | `A9398378327429DEA6227A1E6156A71F` |
| `code/analysis/gen_m40_2x2.py` | 3 | `AE6E3F6017ADC3A5ECDA047C398D9134` | `FCB0459A5F9A4853710DBC76C7C9D306` |
| `code/analysis/gen_m40_e2.py` | 3 | `8D740E1D9996C921E9DAB49D0B4982C1` | `0DF463349EA3D32A19EE990F29B48599` |
| `code/analysis/gen_m41_e1.py` | 2 | `734439D71D65F9D26F7BB90B56C3CA24` | `31FCED7DC3D408BE58F4646FC6FC9CBA` |
| `code/analysis/h20_rescue_compare.py` | 3 | `9A468BDE328B1A507BB079A4843DC983` | `A5AC76DB2861E9D0ADBBAB563D915F03` |
| `code/analysis/m219_wilson_bounds.py` | 1 | `4C51D8713202A304DA7D5AC989F675BB` | `BA061A497E6132FA33754621A82CFCCD` |
| `code/analysis/m37_ci_power.py` | 1 | `70A54EBB5A126F9ED1AD6FEF8726EAA5` | `430DD338EAB357F3E7281248FDF4E7DD` |
| `code/analysis/m40m41_facts.json` | 2 | `8BC6E0EA0CA4B9B19FC611A865A200F1` | `A2360E5CAC75E1E5854C3491184C1B7A` |
| `code/analysis/make_19f.py` | 2 | `BE772575A5D5E080B456035409AC708D` | `AD9204B3565138DA13E498E91537BFD4` |
| `code/analysis/make_sharediso_fold2.py` | 1 | `178A7DCBF6D76E82648267FA6D7C83CE` | `20876F530E5629A43F7F38507433F1FD` |
| `code/analysis/make_test_sheet.py` | 1 | `3BF3B6E817CF23BD13457D8A005929BC` | `591AF8325182B6986C15C0F899523740` |
| `code/analysis/measure_fix.py` | 1 | `C07D89FC6F721F56B1BD4E81654DA622` | `967600A7DAFF1D18F12B78B8989657A3` |
| `code/analysis/measure_pages.py` | 1 | `4D2DB0F5275402E0BDEE40E7B2E7D783` | `91F13DC17D7BA522341D582727BEA7FA` |
| `code/analysis/measure_pr_layout.py` | 2 | `ABED450B9EE27B4185522C3C8472BE00` | `99FEB13810733A1519A08188028963C5` |
| `code/analysis/move_s38_to_appendix.py` | 2 | `80AC19F669C1D8C58391730517593980` | `484F58151D7A8E480E3F27FA0ED2ADBF` |
| `code/analysis/move_s73_to_appendix.py` | 2 | `94C17E0F64FDA0E665346FAC06E8F810` | `90EE2DAEBF8DB2EC63813E4AC1D93562` |
| `code/analysis/move_s7_short.py` | 2 | `91B74924F13B3971DC24C4910E659440` | `6E2C0CB1C332DBBB8FFC07C4513FC22C` |
| `code/analysis/n1_span_artefact_tests.py` | 2 | `10D3C6E82087157BEC004F0F92E6CEC7` | `732EB6810320C367D7D3CDC5BC017412` |
| `code/analysis/n1b_extras.py` | 1 | `731E53E123D342134C7EC6471BC1BEAB` | `2C51D8EF3091A51468763EEFE3341E85` |
| `code/analysis/n2_adversarial_probe.py` | 1 | `663895001CEF9FCBB669A7A7EBBA4926` | `7920BA2B4CE7379774DC23BBFAAE86F2` |
| `code/analysis/n2_boundary_rule_audit.py` | 1 | `EBB02649D63D13AB761A3F52B15EC83B` | `96B8943811A0F405142D4978A1591788` |
| `code/analysis/n2_rule_spread.py` | 1 | `FA5253D7AAC962264A94FCA94BEFDD59` | `7D633D4856631DD04726DC05C88F6BC2` |
| `code/analysis/n3_deployable_calibration.py` | 2 | `2E5088E006D4A1EBF54F4C7715456066` | `CDD7F3FC52BE170A478CC94DEFCAA4E8` |
| `code/analysis/n4_cross_family_dense_panel.py` | 1 | `9C74DB226C1B785361807EBC7E069771` | `2402465EE5EEC2A7DE3E3F40E3FA7E74` |
| `code/analysis/named_uncited.py` | 1 | `34560CB41B6A36E936C4D6DBCE99935F` | `940F1B4F3A73B17F323A708343F88AF2` |
| `code/analysis/normalize_supp_lf.py` | 1 | `A67B9EAD0F6851D22A3950CE36E30F6E` | `BB47CE8B0F5C087FAA15116080DE0AD5` |
| `code/analysis/novelty_closure.py` | 1 | `71B72331552D7BEDA4B0B090DF740E20` | `81A582D4141E2E82F27B84167E4FB5FA` |
| `code/analysis/novelty_round2_compare.py` | 1 | `E0A7F643BE6FFD47CA320207814D45E0` | `9EAA40274D981E94C81222CE7EDADEC5` |
| `code/analysis/p4_decomp_verify.py` | 2 | `036562686E9F606578D9FB1E69AA1AED` | `FDF641E03123C830B3F53C4C5CB0C810` |
| `code/analysis/perknob_rung_8unit.py` | 1 | `6FD3B363CFD517727404EB7E01CFBDFD` | `A7A541777A9CAAB1EBC339D0C400B0BD` |
| `code/analysis/permit_vs_channel.py` | 3 | `C6C21B5A85FEB15A1B0A6583F40388AF` | `E9E420F5927B4122ED34212F7988440C` |
| `code/analysis/pr_compliance_check.py` | 3 | `6E4888F16542320937F38AD7A7B97810` | `D94DB8F59CBF7D927BA3ED843E6D6FE6` |
| `code/analysis/pred_w_caliber.py` | 1 | `EB17076740853482656F61F52AED50B5` | `1A3ACA9BD2C8B17D6537CC0B14131104` |
| `code/analysis/recompute_S.py` | 2 | `80839CE2EC05F570AADF6402F7DEB687` | `71D4095B8BD05FA109EBFC95157CE5EE` |
| `code/analysis/remeasure.py` | 2 | `FA85BEF5EE03F681EE4064258E71B0FB` | `F730F76CBB3534BDBF17AC7D730BFD12` |
| `code/analysis/renumber_refs.py` | 1 | `D03D89E5A1D796EF120D2CFFF667B59C` | `3DB18AA1C39F4F1F4C282B760534DD16` |
| `code/analysis/s15_five_build_S.py` | 2 | `C8BEE34CDE51AA67AD5BCD222DE96555` | `E62D429A0AF96E8DB4352ED8263A35AA` |
| `code/analysis/slim_pointers.py` | 1 | `1A2CAD3F5814AE6FB2F168D447509868` | `7E2B8B92677728EAA9931AD3CEA990C0` |
| `code/analysis/span_caliber_reconcile.py` | 1 | `754689681FDA0C67B0F7240902B4754F` | `68795670281592139A3A1C6CF2E6451E` |
| `code/analysis/span_equalcount.py` | 1 | `ACB867F0F92DC08112BA4CF5EAD16851` | `A10469273D9622FDFA55189383E5569C` |
| `code/analysis/span_equalcount2.py` | 1 | `79CE140C6D023A2BC75A5683BD62ABE6` | `F570A88098DABEF417261D3251BE6719` |
| `code/analysis/span_forest_norm.py` | 2 | `52C0DA72427F7DC3B7180429785A62AC` | `0DF50B7A0008ECF464EAF231D963DE66` |
| `code/analysis/synthetic_grid_cells.py` | 1 | `D9B47A860202787CC31B862B845D490F` | `DE3632E1A7A52DAB3F516A40391FF57E` |
| `code/analysis/test_parse_regression.py` | 1 | `880B657EBCC0EEF4407A94BF9AEDD164` | `9FF0B74772D48F66D98D5F38F6036D51` |
| `code/analysis/theme_decompose.py` | 1 | `B6F9101AA04EBAB370C5B6699C1EFF6D` | `D94E9A55ED376D0DD48FBF93A3A3C8F9` |
| `code/analysis/tile_ladder.py` | 3 | `1328B0C10BF80795A8F6778E08B3841C` | `5C38465D3AD45AE06D95C6F8570BD62D` |
| `code/analysis/variance_decomp.py` | 2 | `C06B743E6C87953D5B9B83A06AFDC684` | `F4B898FA9C76AF38095F0D3AD90A3766` |
| `code/analysis/verify_instr_identity.py` | 1 | `4EEBA068EE4D7407843DD6D02B6D82FA` | `8C1B45444150A54C4080CF3F7E2C5F18` |
| `code/analysis/verify_objective.py` | 1 | `4262F9F848288FF6D0F06EA47FF2F3EC` | `CB6A3C86403F291765D9CAB00043D342` |
| `code/analysis/verify_s11.py` | 1 | `39AC92550814686F23B9E47C9D30EC10` | `9A51A7E32F649369CAF5C3EFE4EF49A7` |
| `code/analysis/w0_audit.py` | 2 | `FC0D864ADBDC4E44A781663ADDC86AAA` | `EDB1D303D0F998ED5ADD1872101EB319` |
| `code/analysis/w0_frame.py` | 2 | `D35C5FBE33AD9D9D49D690D8341A1ED8` | `C768CF262041599BBCD84F3CF27A6A94` |
| `code/analysis/w0_frame3.py` | 2 | `6261B7034990B0CEEDA1C3C5C24F4111` | `4FFF2C055A51864F1B8E49CE6B65277E` |
| `code/analysis/w0_pools2.py` | 2 | `1B1E3A881967C26919A3AC62F3387497` | `68A42534E02665CA9F0707259B9E4435` |
| `code/analysis/w0_pull_probes.py` | 3 | `AAAB26EA41E89B3F628C582D3B9EC37F` | `A21D1459B725B924FBD5D0BF43683CB6` |
| `code/analysis/w1_finalize2.py` | 1 | `B59ED214A40A949F0BCADCD08F0877BC` | `C9092E6C1FD886A1C90CA621B34D0D6E` |
| `code/analysis/w1_frame_report.py` | 1 | `53520C8CB4376EBAEE7D1D06D6ADE9C4` | `3ADD28DCE78DA488979DDED1C27BDD43` |
| `code/analysis/w1_hosted.sh` | 1 | `EFA89850722EC8BD717EED2C73CB70AC` | `B474C757C5BA46C805CB9B7CF31FEC79` |
| `code/analysis/w1_judge.py` | 1 | `308D6D7728262F2E656A68676F31C95B` | `D9F9C2FC41BB0FA4DA8A81189438906F` |
| `code/analysis/w1_monitor.py` | 2 | `5D2BD3CDFD4EF83874703F232437B273` | `894E5FA9F30F707DD6AD27FAC181534B` |
| `code/analysis/w1_pagebudget.py` | 1 | `5EA391EE3AB18336E79B584EE301D90E` | `944C3FF1A402CDBCD135F2D5A96371B7` |
| `code/analysis/w1_unpack.py` | 3 | `C8042D20A4310F52EC9336DD71A8C33D` | `2C4161A1EAA7D6C9648E78176CCF3D53` |
| `code/experiments/h20_finish_pack.py` | 1 | `53800A56BBA837D97212C9AD28357760` | `B410941CF1AE1E984755AF14B2D0CFC7` |
| `code/experiments/h20_pull_all.py` | 1 | `679311B9136211BCDC76BFA878B9FFA0` | `092BA114F87677753B6834844FD6653F` |
| `code/experiments/newh20_sync.py` | 1 | `8A52D32C3083D935A8B7DDB675F9EBD9` | `1498514FF3D798604DECB15D9FD4F335` |
| `env/a800_logs_20260927/A800交接说明_给P3_20260926.md` | 1 | `4E58B4AB9CB3E86647C08BBB806AA3AA` | `7AE554772095669FBE556F79F5601F89` |
| `env/a800_logs_20260927/A800交接说明_给P3_20260927.md` | 1 | `9F3DBEBDD82B13B3AC4BC6960B3D9664` | `F50892F0674467E4007E3044D325752B` |
| `env/a800_logs_20260927/RUNNING.md` | 1 | `AB904CC2C17FD4FE042ED97CBBB864ED` | `3E7519B9FB9DF0739453ED9561333812` |
| `env/a800_logs_20260927/_FETCH_MANIFEST.txt` | 2 | `EE928D5475B740A60069CBAF8C6B06AD` | `A7289C3A1C1F28C4CFD6364C32A638FB` |
| `env/a800_missing_20260927/_FETCH_MANIFEST.txt` | 2 | `07A031C921AE341D37520A1070CC9733` | `060920439D38AB48267A8B43D3762444` |
| `manuscript/E2_evidence_record.md` | 2 | `5DC10DB6973AE87C27D16DC86DAE1AD0` | `2D27C099EA0CD30BED981FB9823622CD` |
| `manuscript/review_control_evidence.md` | 2 | `7052DE8CCB7FC67C57150619A570F742` | `C648AA81B75985825523170E44B8945F` |

**Three counts that are easy to confuse.** *Rewritten* — the shipped bytes differ from the authors' source
file — is **160** files, of which **153** are under `code/` (the other seven are the five text files under
`env/` and two under `manuscript/`); those 160 rows account for **269** substitutions in total. The number of
files that merely **contain** one of the six placeholders is **161**: the 160 rewritten ones plus this
`README.md`, which names the placeholders on purpose. An earlier revision of this section printed only 136
rows because the table had not yet been extended with the 24 scripts added to `code/analysis/` in the last
release batch — all of them sanitised by the same rule, each by 1–4 substitutions.

**The consequence, stated plainly.** Where the md5 of a script here differs from the md5 of the authors'
source file, that difference is **caused by this sanitisation** — it is not evidence that the script was
edited after the reported runs. A field that records the md5 of a *source file*, such as `script_md5` in a
frozen JSON, therefore refers to the **pre-sanitisation** bytes; where such a field does not equal the md5 of
the shipped copy, that is the expected outcome of the sanitisation described above — **not** an
inconsistency and **not** tampering. The live example is `code/analysis/A_result.json`, whose `script_md5` is
`CBA9DDA5C0F305CF8EC2BE8A9ECF1A3A` — the pre-sanitisation md5 of `A_analyze.py` — whereas `MANIFEST.csv`
records the shipped copy as `1915CEA82C7BB66FB9A73321D490F353`.

The same convention governs the md5 values printed **verbatim in the manuscript and the supplementary
material**: an md5 quoted there beside a script's name is the md5 of the authors' **pre-sanitisation source
file**. Where that script is one of the 160 rows above, the quoted value therefore differs from the copy
shipped here and from `MANIFEST.csv` — expected, not an inconsistency; where the sanitiser did not touch the
file, the two agree. The worked example is `n4_cross_family_dense_panel.py`, for which the reproduction note
of supplementary §M.19.15 prints md5 `9c74db226c1b785361807ebc7e069771` — the md5 of the authors' source
file — whereas the copy released here (one substitution, the authors' private working-directory prefix
replaced by `<WORKDIR>`) is `2402465EE5EEC2A7DE3E3F40E3FA7E74`, the row for it in the table above.

That explanation is deliberately narrow. Across the whole package there are **39** md5-valued JSON fields;
**28** match a file shipped here and **11** do not. Exactly one of the eleven is the sanitisation effect above
(`A_result.json.script_md5`). The other ten name entities that are deliberately **not** in this package and
are unrelated to the sanitiser: mirror/metadata digests (`zenodo_meta_md5` and `hf_mirror_meta_md5` in
`A_criteria_frozen.json`; `hf_api_meta_md5` in `B_criteria_frozen.json`), the manuscript skeleton that a
supplementary table was transcribed from (`transcribed_from_md5` in `f9_quoted.json`), the intermediate
`a39_unit_calib_heldout_result.json` (`a39_md5` in `m37_ci_power_result.json`), and the manuscript/RTF inputs
of the pagination positive-control measurement (`en_md5` plus four `rtf_md5` in
`pagination_measurement_rtf_proxy.json`).

### What the sanitiser did **not** touch

**Nothing under `data/` was altered.** Every one of the **2,767** files under `data/` is byte-identical to
the corresponding source file. Two independent checks say so: (i) a sanitiser substitution always leaves one
of the six placeholder patterns above in the file, and a scan of all 2,767 released data files finds **zero**
placeholder patterns — hence zero substitutions anywhere under `data/`; (ii) a per-file `path / bytes / md5`
manifest of `data/` taken before and after the release script ran is **unchanged**. In particular the 138
A-round and B-round products added in this revision (`data/derived/A_res_20260928/` 71 files,
`data/derived/B_res_20260928/` 67 files) are verified item by item against the `MD5SUMS_A.txt` /
`MD5SUMS_B.txt` manifest shipped beside them — both in the source directory and again in this package.

Only text files can be affected at all, and only the 160 rows above are. `data.zip` is a plain archive of
`data/` and inherits the same guarantee.

## License

Data, code and figures in this package are released under **Creative Commons Attribution 4.0 International
(CC BY 4.0)** — see `LICENSE`. Please cite the manuscript if you use them.
