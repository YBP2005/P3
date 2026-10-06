# -*- coding: utf-8 -*-
"""A5-2 ext b3: author self-quantization of Qwen3-VL-32B-Instruct (BF16) to 4-bit.

Toolchain (zero new installs, no AWQ):
  * algorithm      : RTN (round-to-nearest), weight-only INT4, symmetric, per-group
  * implementation : compressed_tensors 0.17.0 (apply_quantization_config / RTN fill /
                     compress_quantized_weights) + ModelCompressor (pack-quantized)
  * NO calibration data is used (RTN is data-free) -> recorded explicitly.
  * structural scope mirrors the existing b0 AWQ-4bit build: targets=["Linear"],
    the same `ignore` list (vision tower kept in BF16), format "pack-quantized".

Writes a checkpoint that vLLM 0.29 serves with --quantization compressed-tensors.
"""
import argparse, io, json, os, sys, time

import torch

t_start = time.time()


def log(msg):
    print("[%s] %s" % (time.strftime("%F_%T"), msg), flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True)
    ap.add_argument("--dst", required=True)
    ap.add_argument("--template", required=True, help="existing pack-quantized model dir (config template)")
    ap.add_argument("--group-size", type=int, default=None, help="default: copy template")
    ap.add_argument("--bits", type=int, default=4)
    ap.add_argument("--zp", type=int, default=0, help="zero_point value for symmetric packing")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--max-layers-verify", type=int, default=8)
    ap.add_argument("--dry", action="store_true", help="do not save; only report")
    A = ap.parse_args()

    torch.manual_seed(A.seed)

    tqc = json.load(io.open(os.path.join(A.template, "config.json"), encoding="utf-8"))["quantization_config"]
    gs = A.group_size or tqc["config_groups"]["group_0"]["weights"]["group_size"]
    ignore = list(tqc.get("ignore") or [])
    log("RTN INT4 | src=%s | dst=%s | group_size=%d bits=%d zp=%d seed=%d"
        % (A.src, A.dst, gs, A.bits, A.zp, A.seed))
    log("template=%s | ignore entries=%d | format=%s" % (A.template, len(ignore), tqc.get("format")))

    from compressed_tensors.quantization import (QuantizationArgs, QuantizationScheme,
                                                 QuantizationConfig, QuantizationStrategy,
                                                 QuantizationStatus)
    from compressed_tensors.quantization.lifecycle import apply_quantization_config, compress_quantized_weights

    cfg = QuantizationConfig(
        config_groups={"group_0": QuantizationScheme(
            targets=["Linear"],
            weights=QuantizationArgs(num_bits=A.bits, type="int", symmetric=True,
                                     strategy=QuantizationStrategy.GROUP,
                                     group_size=gs, dynamic=False, actorder=None),
            input_activations=None)},
        format="pack-quantized",
        ignore=ignore,
        quantization_status=QuantizationStatus.INITIALIZED)

    from transformers import AutoProcessor
    import transformers
    log("transformers %s | torch %s" % (transformers.__version__, torch.__version__))
    cls = getattr(transformers, "Qwen3VLForConditionalGeneration")
    log("loading model (bf16, cuda:0) ...")
    t0 = time.time()
    model = cls.from_pretrained(A.src, dtype=torch.bfloat16, device_map={"": 0},
                                trust_remote_code=True, low_cpu_mem_usage=True)
    model.eval()
    log("model loaded in %.1f s | gpu=%.1f GB"
        % (time.time() - t0, torch.cuda.memory_allocated() / 1e9))

    apply_quantization_config(model, cfg, run_compressed=False)

    # ---- RTN fill + immediate compress (keeps peak memory low) ----
    refs = {}
    nq = 0
    skipped_visual = []
    t0 = time.time()
    for name, mod in model.named_modules():
        scheme = getattr(mod, "quantization_scheme", None)
        if scheme is None or scheme.weights is None:
            continue
        w = getattr(mod, "weight", None)
        if w is None or w.dim() != 2:
            continue
        if "visual" in name:
            skipped_visual.append(name)
        out_f, in_f = w.shape
        if in_f % gs:
            pad = gs - (in_f % gs)
            w = torch.nn.functional.pad(w.data, (0, pad))
            in_f_p = in_f + pad
        else:
            in_f_p = in_f
        ng = in_f_p // gs
        amax = w.reshape(out_f, ng, gs).abs().amax(dim=-1)
        scale = (amax / float(2 ** (A.bits - 1) - 1)).clamp_min(1e-8)
        if len(refs) < A.max_layers_verify and "visual" not in name:
            refs[name] = (w.detach().float().cpu().clone(), out_f, in_f)
        mod.weight_scale.data.copy_(scale.to(mod.weight_scale.dtype))
        if getattr(mod, "weight_zero_point", None) is not None:
            mod.weight_zero_point.data.fill_(A.zp)
        mod.quantization_status = QuantizationStatus.INITIALIZED
        compress_quantized_weights(mod)
        nq += 1
        if nq % 50 == 0:
            log("   quantized %d modules ... gpu=%.1f GB" % (nq, torch.cuda.memory_allocated() / 1e9))
    log("RTN applied to %d Linear modules in %.1f s" % (nq, time.time() - t0))
    if skipped_visual:
        log("!! WARNING: %d vision modules were NOT ignored (first: %s)"
            % (len(skipped_visual), skipped_visual[:3]))
    else:
        log("vision tower: all model.visual.* left in BF16 (ignore list effective) ✓")

    # ---- pack (uint8/int8 -> int32 pack-quantized) ----
    from compressed_tensors.compressors import ModelCompressor
    model.config.quantization_config = dict(tqc)
    model.config.quantization_config["config_groups"]["group_0"]["weights"]["group_size"] = gs
    log("packing with ModelCompressor ...")
    t0 = time.time()
    comp = ModelCompressor.from_pretrained_model(model)
    comp.compress_model(model)
    log("packed in %.1f s | gpu=%.1f GB" % (time.time() - t0, torch.cuda.memory_allocated() / 1e9))

    # ---- round-trip verification on a few layers ----
    log("--- round-trip check (pack -> unpack -> dequant vs original) ---")
    worst = 0.0
    for name, (orig, out_f, in_f) in refs.items():
        mod = dict(model.named_modules())[name]
        try:
            dq = comp.decompress_model  # noqa
            from compressed_tensors.quantization.lifecycle.forward import dequantize
            wq = mod.weight
            sc = mod.weight_scale
            zp = getattr(mod, "weight_zero_point", None)
            d = dequantize(wq, sc, zp, mod.quantization_scheme.weights,
                           dtype=torch.float32, g_idx=getattr(mod, "weight_g_idx", None))
            d = d.reshape(out_f, in_f)
            err = (d.cpu().float() - orig).abs()
            rel = (err.max() / max(orig.abs().max().item(), 1e-9)).item()
            worst = max(worst, rel)
            log("   %-58s maxerr=%.5f rel=%.4f" % (name[-58:], err.max().item(), rel))
        except Exception as e:
            log("   %-58s verify FAILED %r" % (name[-58:], repr(e)[:120]))
    log("worst relative round-trip error = %.4f" % worst)

    if A.dry:
        log("DRY: not saving")
        return 0

    os.makedirs(A.dst, exist_ok=True)
    log("saving to %s ..." % A.dst)
    t0 = time.time()
    model.save_pretrained(A.dst, safe_serialization=True, max_shard_size="4GB")
    try:
        AutoProcessor.from_pretrained(A.src, trust_remote_code=True).save_pretrained(A.dst)
    except Exception as e:
        log("!! processor save failed: %r" % (repr(e)[:200]))
    log("saved in %.1f s" % (time.time() - t0))

    # re-assert quantization_config in the written config.json (belt and braces)
    cp = os.path.join(A.dst, "config.json")
    cj = json.load(io.open(cp, encoding="utf-8"))
    if "quantization_config" not in cj:
        cj["quantization_config"] = model.config.quantization_config
        json.dump(cj, io.open(cp, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
        log("re-injected quantization_config into config.json")
    else:
        log("quantization_config present in saved config.json ✓")

    n = tot = 0
    for r, _d, fs in os.walk(A.dst):
        for f in fs:
            n += 1
            tot += os.path.getsize(os.path.join(r, f))
    log("ARTIFACT files=%d bytes=%d (%.2f GB)" % (n, tot, tot / 1e9))
    log("TOTAL elapsed %.1f min" % ((time.time() - t_start) / 60.0))
    log("RTN_QUANT_DONE %s" % A.dst)
    return 0


if __name__ == "__main__":
    sys.exit(main())
