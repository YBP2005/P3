# -*- coding: utf-8 -*-
"""Verify the author-RTN checkpoint against the original BF16 weights.

Unpacks weight_packed (int32, 8x int4) with compressed-tensors' own helper,
dequantizes with weight_scale (group-wise) and compares to the source BF16 weight.
Proves the packing/dequant pipeline is self-consistent (independent of vLLM).
"""
import json, os, sys
import torch
from safetensors import safe_open
from compressed_tensors.compressors.pack_quantized.helpers import unpack_from_int32

ART = sys.argv[1]
SRC = sys.argv[2]
GS = int(sys.argv[3]) if len(sys.argv) > 3 else 32
BITS = 4
ZP = 0
NSAMPLE = int(sys.argv[4]) if len(sys.argv) > 4 else 6

# index of source shards
srci = json.load(open(os.path.join(SRC, "model.safetensors.index.json"))) if os.path.exists(
    os.path.join(SRC, "model.safetensors.index.json")) else None
def src_shard(key):
    if srci:
        return os.path.join(SRC, srci["weight_map"][key])
    return os.path.join(SRC, "model.safetensors")

art_files = [os.path.join(ART, f) for f in os.listdir(ART) if f.endswith(".safetensors")]
af = safe_open(art_files[0], "pt")
keys = [k for k in af.keys() if k.endswith(".weight_packed")]
print("artifact %s | packed layers=%d" % (ART, len(keys)))
step = max(1, len(keys) // NSAMPLE)
worst = 0.0
for k in keys[::step][:NSAMPLE]:
    base = k[:-len("_packed")]
    packed = af.get_tensor(k)
    scale = af.get_tensor(base + "_scale").float()
    shape = tuple(af.get_tensor(base + "_shape").tolist())
    q = unpack_from_int32(packed, BITS, torch.Size(shape), packed_dim=1).float()
    if ZP:
        q = q - ZP
    out_f, in_f = shape
    ng = in_f // GS
    q = q.reshape(out_f, ng, GS)
    dq = (q * scale.reshape(out_f, ng, 1)).reshape(out_f, in_f)
    with safe_open(src_shard(base), "pt") as sf:
        orig = sf.get_tensor(base).float()
    err = (dq - orig).abs()
    amax = orig.abs().max().item()
    rel = err.max().item() / max(amax, 1e-9)
    worst = max(worst, rel)
    print("  %-58s orig_amax=%.4f maxerr=%.5f rel=%.4f" % (base[-58:], amax, err.max().item(), rel))
print("WORST_REL_ERR=%.4f" % worst)
print("VERDICT:", "PASS" if worst < 0.15 else "SUSPECT")
