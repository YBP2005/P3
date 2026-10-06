# `archives/` — superseded artefacts, kept for provenance only

## `a52_analyze.py.superseded_20261006`

* **What it is.** The analysis script exactly as it stood on the experiment host when the
  27-cell / 17,496-record A5-2 fit was produced (the fit that includes the third, FP8 build).
  43,618 bytes, md5 `bf873c5e7da083dae42cb379efe9af9d`. It is the copy named in the
  supplementary material as *the as-run copy*.
* **Do not use it for any analysis.** No number printed in the manuscript or in the
  supplementary material may be recomputed with this file. It is archived **only** so that the
  registered as-run readings stay traceable to the exact bytes that produced them.
* **Which corrections it lacks.** It predates **both** corrections that are present in the copy
  actually shipped with this package, `data/derived/a5_2_a800/env/a52_analyze.py`
  (md5 `77f87f49b0e447fba54ea2a0435f80c8`):
  1. it codes the legibility covariates by the original size radius instead of the
     pre-registered ordinal levels (`*_level` coding registered in the frozen criteria file);
  2. it does **not** apply the pre-registered whole-cell exclusion, so it fits every attained
     record — the *contrast* record set — rather than the *primary* one.
* **What to use instead.** The shipped copy above. Re-run over the same 27 released per-cell
  files it gives **primary n = 16,848, beta = -4.2356, CI [-4.6456, -3.8257]** and
  **contrast n = 17,496, beta = -4.4101, CI [-4.8165, -4.0037]**; both calibers PASS `C3` and
  FAIL `C4`. Both readings are printed side by side in the supplementary material's caliber and
  revision registration paragraph — neither is silently substituted for the other.

## Housekeeping

* Append-only: this notice is never edited and the superseded script is never deleted
  (it is renamed with the `.superseded_<date>` suffix rather than removed).
* Registered in the release-round change ledger; the frozen verdict and run sheet that quote
  `bf873c5e...` as the as-run copy are **not** modified.
