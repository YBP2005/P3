# -*- coding: utf-8 -*-
"""Control experiment: apply the SAME unpack+dequant verifier to
 (a) the known-good b0 AWQ-4bit artifact (produced by cyankiwi/AWQ)
 (b) our author-RTN 4B artifact
against their respective BF16 source weights.
If (a) verifies but (b) does not, our RTN artifact is genuinely broken.
"""
import json, os, sys, glob
import torch
from safetensors import safe_open
from compressed_tensors.compressors.pack_quantized.helpers import unpack_from_int32


def index_of(d):
    p = os.path.join(d, "model.safetensors.index.json")
    if os.path.exists(p):
        return json.load(open(p))["weight_map"]
    fs = glob.glob(os.path.join(d, "*.safetensors"))
    with safe_open(fs[0], "pt") as f:
        return {k: os.path.basename(fs[0]) for k in f.keys()}


def check(art, src, gs, nlayers, label, dims=None):
    print("=== %s ===" % label)
    am = index_of(art)
    sm = index_of(src)
    packed_keys = sorted(k for k in am if k.endswith(".weight_packed"))
    if dims:
        packed_keys = [k for k in packed_keys if dims in k]
    print("   packed layers: %d | artifact shards: %d" % (len(packed_keys), len(set(am.values()))))
    step = max(1, len(packed_keys) // nlayers)
    worst = 0.0
    for k in packed_keys[::step][:nlayers]:
        base = k[:-len("_packed")]           # "...weight"
        with safe_open(os.path.join(art, am[k]), "pt") as f:
            packed = f.get_tensor(k)
            scale = f.get_tensor(base + "_scale").float()
            shape = tuple(f.get_tensor(base + "_shape").tolist())
            zp = f.get_tensor(base + "_zero_point") if (base + "_zero_point") in f.keys() else None
        q = unpack_from_int32(packed, 4, torch.Size(shape), packed_dim=1).float()
        if zp is not None:
            q = q - zp.float()
        out_f, in_f = shape
        ng = in_f // gs
        dq = (q.reshape(out_f, ng, gs) * scale.reshape(out_f, ng, 1)).reshape(out_f, in_f)
        with safe_open(os.path.join(src, sm[base]), "pt") as f:
            orig = f.get_tensor(base).float()
        err = (dq - orig).abs().max().item()
        amax = orig.abs().max().item()
        rel = err / max(amax, 1e-9)
        worst = max(worst, rel)
        print("   %-52s amax=%.4f maxerr=%.5f rel=%.4f zp=%s"
              % (base[-52:], amax, err, rel, "yes" if zp is not None else "no"))
    print("   WORST_REL=%.4f -> %s" % (worst, "PASS" if worst < 0.2 else "SUSPECT"))


B0 = "/root/models/Qwen3-VL-32B-Instruct-AWQ-4bit"
B0SRC = "/model/ModelScope/Qwen/Qwen3-VL-32B-Instruct"
ART4 = "/root/models/_dryrun_rtn_4b"
SRC4 = "/model/ModelScope/Qwen/Qwen3-VL-4B-Instruct"

check(B0, B0SRC, 32, 4, "b0 AWQ-4bit (KNOWN GOOD)", dims="layers.0.")
check(ART4, SRC4, 32, 4, "author-RTN 4B (MINE)", dims="layers.0.")
