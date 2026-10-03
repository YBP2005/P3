# P2-E 判定（detector + density 两行）

* **detector_primary_tau0.25**：span **4.6 pp** ｜ levels [-97.58, -96.27, -94.36, -98.96, -98.13] ｜ 每档 n [182, 182, 182, 182, 182]
* **density_official_dmcount**：span **13.71 pp** ｜ levels [-15.38, -3.02, -1.67, -7.86, -13.45] ｜ 每档 n [182, 182, 182, 182, 182]
* **density_csrnet_crosscheck**：span **668.92 pp** ｜ levels [-67.07, -6.9, 103.78, 301.85, 601.85] ｜ 每档 n [182, 182, 182, 182, 182]

## 判据

* C2-span-detector：`False`
* C3-span-density：`{'uncalibrated_span': 13.71, 'caliber_note': '与 F.2 的 20.1–34.3 pp（isotonic 校准）不可直接比；本行的主用途是进入六 knob 排序（与 §M.43 四行同口径）'}`
* C4-caliber-same-direction：`{'spearman_across_levels': 0.1, 'same_sign_levels': '2/5', 'pass': False, 'note': '两支同向要求逐档 dev 的 Spearman>0 且每档同号；只用 span 符号比是错的（恒正）'}`
* C5-ordering：`{'observed_ascending': ['detector', 'density', 'tiling', 'pixel_budget', 'output_contract', 'prompt_family'], 'published_ascending': ['pixel_budget', 'tiling', 'density', 'output_contract', 'detector', 'prompt_family'], 'spearman_vs_published': 0.2, 'knobs_off_their_published_rank': ['output_contract', 'tiling', 'pixel_budget', 'detector', 'density'], 'pass': False, 'note': '基准 = §F.2 中点的升序（显式写死）；不是"自身排序"'}`

## 口径红线（必须随结果一起报）

* The two new rows are NOT from the same serving session as M.43's four rows. They must be labelled as such wherever they are used, and M.43's 3.01 pp same-session noise floor must NOT be borrowed across sessions to argue about them.
* No proxy is substituted. If a knob cannot be driven, it stays 'not measured'.
* The density row is titled with its caliber ('official DM-Count' or 'CSRNet'). Appendix D.1 requires official and reproduction weights to be reported separately.
* Whole image only (upstream decision 2026-10-02). No 2x2 tiling in the primary reading; a tiled variant, if ever run, is a separate stratum and is never pooled with this one.
