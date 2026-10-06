import os, sys, hashlib, json
from huggingface_hub import HfApi
DST = "/root/models/Qwen3-VL-32B-Instruct-FP8"
REPO = "Qwen/Qwen3-VL-32B-Instruct-FP8"
REV = "4bf2c2f39c37c0fede78bede4056e1f18cdf8109"
info = HfApi().model_info(REPO, files_metadata=True, revision=REV)
exp = {}
for s in info.siblings:
    lfs = getattr(s, "lfs", None)
    sha = (lfs or {}).get("sha256") if isinstance(lfs, dict) else getattr(lfs, "sha256", None)
    exp[s.rfilename] = (s.size, sha)
print("repo files=%d total_declared=%d" % (len(exp), sum(v[0] for v in exp.values())))
ok = bad = missing = 0
tot = 0
for f in sorted(exp):
    p = os.path.join(DST, f)
    if not os.path.exists(p):
        print("  MISSING", f); missing += 1; continue
    sz = os.path.getsize(p); tot += sz
    want_sz, want_sha = exp[f]
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for c in iter(lambda: fh.read(1 << 22), b""):
            h.update(c)
    got = h.hexdigest()
    s_ok = (sz == want_sz)
    h_ok = (want_sha is None) or (got == want_sha)
    if s_ok and h_ok:
        ok += 1
        print("  OK   %-42s %d sha256=%s%s" % (f, sz, got[:16], "" if want_sha else " (no lfs sha)"))
    else:
        bad += 1
        print("  BAD  %-42s size %d/%d sha %s/%s" % (f, sz, want_sz, got[:16], (want_sha or "")[:16]))
print("TOTAL_LOCAL_BYTES=%d" % tot)
print("VERIFY ok=%d bad=%d missing=%d -> %s" % (ok, bad, missing, "PASS" if bad == 0 and missing == 0 else "FAIL"))
